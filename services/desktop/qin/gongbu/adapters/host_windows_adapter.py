from __future__ import annotations

import ctypes
import json
import os
import shutil
import subprocess
import time
import webbrowser
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus
from urllib.parse import unquote


class HostWindowsAdapter:
    adapter_id = "host_windows"

    def execute(self, task: dict) -> dict:
        payload = dict(task or {})
        action = str(payload.get("action", "") or "").strip().lower()

        handlers = {
            "app.locate": self._app_locate,
            "app.launch": self._app_launch,
            "app.close": self._app_close,
            "file.open": self._file_open,
            "file.close": self._file_close,
            "folder.open": self._folder_open,
            "folder.close": self._folder_close,
            "file.create": self._file_create,
            "file.touch": self._file_create,
            "folder.create": self._folder_create,
            "file.mkdir": self._folder_create,
            "folder.mkdir": self._folder_create,
            "file.rename": self._rename_path,
            "folder.rename": self._rename_path,
            "file.move": self._move_path,
            "folder.move": self._move_path,
            "file.copy": self._copy_path,
            "file.delete": self._delete_path,
            "folder.delete": self._delete_path,
            "file.restore": self._restore_path,
            "folder.restore": self._restore_path,
            "browser.search_open": self._browser_search_open,
        }

        handler = handlers.get(action)
        if handler is None:
            return self._error(action, f"Host action is not implemented yet: {action or '-'}")

        try:
            return handler(payload)
        except Exception as exc:
            return self._error(action, f"Host execution failed: {exc}")

    def _args(self, task: dict) -> dict[str, Any]:
        return task.get("arguments", {}) if isinstance(task.get("arguments"), dict) else {}

    def _target_path(self, task: dict) -> str:
        args = self._args(task)
        return (
            str(args.get("target_path", "") or "").strip()
            or str(task.get("target_path", "") or "").strip()
            or str(args.get("source_path", "") or "").strip()
        )

    def _dest_path(self, task: dict) -> str:
        args = self._args(task)
        return (
            str(args.get("dest_path", "") or "").strip()
            or str(args.get("target_new_path", "") or "").strip()
            or str(args.get("new_path", "") or "").strip()
            or str(task.get("dest_path", "") or "").strip()
        )

    def _truthy(self, value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return value != 0
        return str(value or "").strip().lower() in {"1", "true", "yes", "y", "on", "confirmed"}

    def _app_locate(self, task: dict) -> dict:
        args = self._args(task)
        path = (
            str(args.get("install_dir", "") or "").strip()
            or self._target_path(task)
            or str(args.get("effective_target_path", "") or "").strip()
        )
        if not path:
            return self._error("app.locate", "Missing locate path.")

        p = Path(path)
        folder = p if p.is_dir() else p.parent
        if not folder.exists():
            return self._error("app.locate", f"Path does not exist: {folder}")

        subprocess.Popen(["explorer.exe", str(folder)], shell=False)
        return self._ok("app.locate", "Host opened locate folder.", {"path": str(path), "folder": str(folder)})

    def _app_launch(self, task: dict) -> dict:
        args = self._args(task)
        launch_raw = str(args.get("launch_target_raw", "") or "").strip()
        target = launch_raw or self._target_path(task)

        if not target:
            return self._error("app.launch", "Missing launch target.")

        os.startfile(target)  # noqa: S606
        return self._ok("app.launch", "Host sent launch request.", {"launch_target_raw": target})

    def _app_close(self, task: dict) -> dict:
        args = self._args(task)
        close_plan = args.get("app_close_plan", {}) if isinstance(args.get("app_close_plan"), dict) else {}
        if (
            str(args.get("target_material_source", "") or "") != "heibingtai"
            or not self._truthy(args.get("heibingtai_verified", False))
            or not close_plan
        ):
            return self._error("app.close", "app.close 需要黑冰台目标材料，已拒绝直接关闭。", {
                "error": "missing_heibingtai_app_close_plan",
                "target_material_source": str(args.get("target_material_source", "") or ""),
                "heibingtai_verified": bool(self._truthy(args.get("heibingtai_verified", False))),
                "close_strategy": "missing_heibingtai_app_close_plan",
                "matched_count": 0,
                "closed_count": 0,
                "skipped_count": 0,
                "skip_reasons": {},
            })

        if str(close_plan.get("resolution_status", "") or "") != "resolved_unique":
            return self._error("app.close", "黑冰台 app.close 目标未唯一解析，已拒绝执行。", {
                "error": "heibingtai_app_close_plan_not_resolved",
                **self._app_close_plan_context(close_plan),
                "matched_count": 0,
                "closed_count": 0,
                "skipped_count": 0,
            })

        if not self._truthy(close_plan.get("allowed_execution", False)):
            return self._error("app.close", "黑冰台 app.close plan 未允许执行，已拒绝关闭。", {
                "error": "heibingtai_app_close_plan_not_allowed",
                **self._app_close_plan_context(close_plan),
                "matched_count": 0,
                "closed_count": 0,
                "skipped_count": 0,
            })

        if self._truthy(args.get("force_close", False)) or self._truthy(close_plan.get("force_close_allowed", False)):
            return self._error("app.close", "app.close 当前只允许软关闭，不允许强制关闭。", {
                "error": "force_close_not_allowed_for_heibingtai_app_close",
                **self._app_close_plan_context(close_plan),
                "matched_count": 0,
                "closed_count": 0,
                "skipped_count": 1,
            })

        candidate = close_plan.get("selected_candidate", {}) if isinstance(close_plan.get("selected_candidate"), dict) else {}
        hwnd = self._safe_int(candidate.get("hwnd", ""))
        process_name = str(candidate.get("process_name", "") or "").strip()
        context = self._app_close_plan_context(close_plan)

        if hwnd > 0:
            requested = self._post_wm_close(hwnd)
            data = {
                **context,
                "close_attempts": [{
                    "process_name": process_name,
                    "pid": str(candidate.get("pid", "") or ""),
                    "main_window_handle": str(hwnd),
                    "closed": bool(requested),
                    "skipped": not bool(requested),
                    "skip_reason": "" if requested else "wm_close_failed",
                }],
                "process_names": [process_name] if process_name else [],
                "matched_count": 1,
                "closed_count": 1 if requested else 0,
                "skipped_count": 0 if requested else 1,
                "skip_reasons": {} if requested else {str(hwnd): "wm_close_failed"},
            }
            if requested:
                return self._ok("app.close", "Host requested Heibingtai verified application window to close.", data)
            return self._error("app.close", "Heibingtai verified window close request failed.", {
                "error": "wm_close_failed",
                **data,
            })

        if process_name:
            close_result = self._close_process_main_windows([process_name])
            matched_count = int(close_result.get("matched_count", 0) or 0)
            closed_count = int(close_result.get("closed_count", 0) or 0)
            data = {
                **close_result,
                **context,
                "close_strategy": str(close_plan.get("close_strategy", "") or "soft_process_close"),
            }
            if closed_count > 0:
                return self._ok("app.close", "Host requested Heibingtai verified application process window to close.", data)
            return self._error("app.close", "No matching Heibingtai verified application window was closed.", {
                "error": "process_window_not_found" if matched_count <= 0 else "close_main_window_failed",
                **data,
            })

        return self._error("app.close", "Heibingtai close plan does not contain a soft-close target.", {
            "error": "heibingtai_close_plan_missing_soft_target",
            **context,
            "matched_count": 0,
            "closed_count": 0,
            "skipped_count": 1,
        })

    def _file_open(self, task: dict) -> dict:
        path = self._target_path(task)
        if not path:
            return self._error("file.open", "Missing file path.")
        p = Path(path)
        if not p.exists() or not p.is_file():
            return self._error("file.open", f"File does not exist: {path}")
        policy_service, capability_index = self._file_open_planning_services()
        policy = policy_service.get_policy_for_path(str(p)) if policy_service else self._fallback_file_open_policy(p)
        policy_key = str(policy.get("extension_key", "") or ("no_extension" if not p.suffix else p.suffix.lower()))
        app_kinds = self._policy_app_kinds(policy)

        if (
            policy_key == "no_extension"
            and bool(policy.get("requires_user_choice", False))
            and policy_service
            and not policy_service.has_user_rule_for_key("no_extension")
        ):
            return self._error("file.open", "Open app choice is required for a file without extension.", {
                **self._file_open_policy_data(policy),
                "path": str(p),
                "target_path": str(p),
                "target_type": "file",
                "error": "needs_open_app_choice",
                "needs_open_app_choice": True,
                "open_app_candidates": self._open_app_candidates(app_kinds, capability_index),
                "llm_reply_hint": "这个文件没有扩展名，请选择用 VSCode 还是记事本打开。",
                "user_action_required": "choose_open_app",
                "close_action": "file.close",
                "close_strategy": "unsupported_precise_close",
            })

        denied: list[dict[str, str]] = []
        unavailable: list[dict[str, str]] = []
        for app_kind in app_kinds:
            if app_kind == "default_app":
                continue
            capability = capability_index.get(app_kind) if capability_index else None
            if not capability or not bool(capability.get("available", False)):
                unavailable.append({"app_kind": app_kind, "reason": "app_not_available"})
                continue
            if not bool(capability.get("can_open", False)):
                denied.append({
                    "app_kind": app_kind,
                    "permission_state": str(capability.get("permission_state", "") or ""),
                })
                continue
            executable = self._capability_executable(app_kind, capability)
            if not executable:
                unavailable.append({"app_kind": app_kind, "reason": "missing_executable"})
                continue
            launch = self._launch_file_with_app(app_kind, executable, p)
            if not launch.get("ok"):
                unavailable.append({"app_kind": app_kind, "reason": str(launch.get("error", "launch_failed") or "launch_failed")})
                continue
            time.sleep(1.0)
            window = self._find_file_window_for_app(app_kind, p, int(launch.get("pid", 0) or 0))
            title_matched = bool(window.get("title_matched", False))
            close_strategy = self._close_strategy_for_opened_app(app_kind, title_matched)
            return self._ok("file.open", self._file_open_message(app_kind, title_matched), {
                **self._file_open_policy_data(policy),
                "path": str(p),
                "target_path": str(p),
                "target_type": "file",
                "open_method": self._open_method_for_app_kind(app_kind),
                "app_kind": app_kind,
                "process_name": str(window.get("process_name", "") or self._process_name_for_app_kind(app_kind)),
                "pid": str(window.get("pid", "") or launch.get("pid", "") or ""),
                "hwnd": str(window.get("hwnd", "") or ""),
                "window_title": str(window.get("window_title", "") or ""),
                "title_matched": title_matched,
                "resolved_pid": str(window.get("pid", "") or ""),
                "resolved_hwnd": str(window.get("hwnd", "") or ""),
                "document_adapter": self._document_adapter_for_app_kind(app_kind),
                "document_adapter_stage": "window_title_resolved" if title_matched else "open_dispatched_but_window_unresolved",
                "open_dispatched": True,
                "app_permission_state": str(capability.get("permission_state", "") or ""),
                "app_permission_error": "",
                "close_action": "file.close",
                "close_strategy": close_strategy,
            })

        if bool(policy.get("allow_windows_default", False)):
            return self._file_open_with_windows_default(p, policy)

        error = "app_permission_denied" if denied else "app_not_available"
        return self._error("file.open", "No permitted application is available to open this file.", {
            **self._file_open_policy_data(policy),
            "path": str(p),
            "target_path": str(p),
            "target_type": "file",
            "error": error,
            "app_permission_error": error,
            "app_permission_denied": denied,
            "app_unavailable": unavailable,
            "needs_open_app_choice": False,
            "open_app_candidates": self._open_app_candidates(app_kinds, capability_index),
            "llm_reply_hint": "没有可用或已授权的软件可以打开这个文件。",
            "user_action_required": "grant_or_choose_open_app",
            "close_action": "file.close",
            "close_strategy": "unsupported_precise_close",
        })

    def _file_open_planning_services(self):
        try:
            from services.desktop.qin.heibingtai.file_open_policy_service import FileOpenPolicyService
            from services.desktop.qin.heibingtai.software_capability_index import SoftwareCapabilityIndex

            project_root = Path(__file__).resolve().parents[5]
            return FileOpenPolicyService(project_root), SoftwareCapabilityIndex(project_root)
        except Exception:
            return None, None

    def _fallback_file_open_policy(self, path: Path) -> dict[str, Any]:
        suffix = path.suffix.lower() or "no_extension"
        if suffix == ".txt":
            return {
                "extension_key": ".txt",
                "preferred_app_kind": "notepad",
                "fallback_app_kinds": [],
                "open_mode": "specified_app_first",
                "close_adapter": "notepad",
                "allow_windows_default": True,
                "requires_user_choice": False,
            }
        return {
            "extension_key": suffix,
            "preferred_app_kind": "default_app",
            "fallback_app_kinds": [],
            "open_mode": "windows_default_allowed",
            "close_adapter": "default_app",
            "allow_windows_default": True,
            "requires_user_choice": False,
        }

    def _policy_app_kinds(self, policy: dict[str, Any]) -> list[str]:
        result: list[str] = []
        preferred = str(policy.get("preferred_app_kind", "") or "").strip().lower()
        if preferred:
            result.append(preferred)
        fallbacks = policy.get("fallback_app_kinds", [])
        if isinstance(fallbacks, list):
            result.extend(str(item or "").strip().lower() for item in fallbacks if str(item or "").strip())
        return list(dict.fromkeys(result))

    def _file_open_policy_data(self, policy: dict[str, Any]) -> dict[str, Any]:
        fallbacks = policy.get("fallback_app_kinds", [])
        if not isinstance(fallbacks, list):
            fallbacks = []
        return {
            "open_policy_key": str(policy.get("extension_key", "") or ""),
            "preferred_app_kind": str(policy.get("preferred_app_kind", "") or ""),
            "fallback_app_kinds": [str(item or "") for item in fallbacks],
            "open_mode": str(policy.get("open_mode", "") or ""),
            "allow_windows_default": bool(policy.get("allow_windows_default", False)),
            "requires_user_choice": bool(policy.get("requires_user_choice", False)),
        }

    def _open_app_candidates(self, app_kinds: list[str], capability_index) -> list[dict[str, Any]]:
        candidates: list[dict[str, Any]] = []
        for app_kind in app_kinds:
            if not app_kind or app_kind == "default_app":
                continue
            capability = capability_index.get(app_kind) if capability_index else None
            label = str((capability or {}).get("title", "") or self._app_label_for_kind(app_kind))
            candidates.append({
                "app_kind": app_kind,
                "label": label,
                "available": bool((capability or {}).get("available", app_kind == "notepad")),
                "can_open": bool((capability or {}).get("can_open", app_kind == "notepad")),
                "permission_state": str((capability or {}).get("permission_state", "") or ""),
                "document_adapter": self._document_adapter_for_app_kind(app_kind),
            })
        return candidates

    def _capability_executable(self, app_kind: str, capability: dict[str, Any]) -> str:
        if app_kind == "notepad":
            return str(capability.get("exe_path", "") or "notepad.exe")
        for key in ("exe_path", "launch_target_raw"):
            value = str(capability.get(key, "") or "").strip().strip('"')
            if not value:
                continue
            if value.lower().endswith(".exe"):
                return value
        return ""

    def _launch_file_with_app(self, app_kind: str, executable: str, path: Path) -> dict[str, Any]:
        try:
            if app_kind == "vscode":
                process = subprocess.Popen([executable, "--reuse-window", str(path)], shell=False)
            else:
                process = subprocess.Popen([executable, str(path)], shell=False)
            return {"ok": True, "pid": str(process.pid)}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def _file_open_with_windows_default(self, path: Path, policy: dict[str, Any]) -> dict:
        os.startfile(str(path))  # noqa: S606
        time.sleep(1.0)
        window = self._get_foreground_window_info()
        title_matched = self._title_matches_file(str(window.get("window_title", "") or ""), str(path))
        process_name = str(window.get("process_name", "") or "").strip()
        app_kind = self._infer_app_kind(process_name, str(window.get("window_title", "") or ""), str(path))
        if not title_matched:
            window = {}
            app_kind = "default_app"
        close_strategy = self._close_strategy_for_opened_app(app_kind, title_matched)
        return self._ok("file.open", "Host sent Windows default open request.", {
            **self._file_open_policy_data(policy),
            "path": str(path),
            "target_path": str(path),
            "target_type": "file",
            "open_method": "windows_default",
            "app_kind": app_kind,
            "pid": str(window.get("pid", "") or ""),
            "hwnd": str(window.get("hwnd", "") or ""),
            "process_name": str(window.get("process_name", "") or ""),
            "window_title": str(window.get("window_title", "") or ""),
            "title_matched": title_matched,
            "resolved_pid": str(window.get("pid", "") or ""),
            "resolved_hwnd": str(window.get("hwnd", "") or ""),
            "document_adapter": self._document_adapter_for_app_kind(app_kind),
            "document_adapter_stage": "window_title_resolved" if title_matched else "open_dispatched_but_window_unresolved",
            "open_dispatched": True,
            "app_permission_state": "",
            "app_permission_error": "",
            "close_action": "file.close",
            "close_strategy": close_strategy,
        })

    def _find_file_window_for_app(self, app_kind: str, path: Path, process_pid: int = 0) -> dict[str, Any]:
        expected_processes = set(self._process_names_for_app_kind(app_kind))
        best: dict[str, Any] = {}
        for window in self._enum_top_windows_info():
            process_name = str(window.get("process_name", "") or "").strip().lower()
            if expected_processes and process_name not in expected_processes:
                continue
            if process_pid and str(window.get("pid", "") or "") == str(process_pid):
                best = dict(window)
            if self._title_matches_file(str(window.get("window_title", "") or ""), str(path)):
                best = dict(window)
                best["title_matched"] = True
                return best
        if best:
            best["title_matched"] = self._title_matches_file(str(best.get("window_title", "") or ""), str(path))
        return best

    def _enum_top_windows_info(self) -> list[dict[str, Any]]:
        try:
            user32 = ctypes.WinDLL("user32", use_last_error=True)
        except Exception:
            return []
        windows: list[dict[str, Any]] = []
        enum_proc_type = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
        user32.EnumWindows.argtypes = [enum_proc_type, ctypes.c_void_p]
        user32.EnumWindows.restype = ctypes.c_bool
        user32.IsWindowVisible.argtypes = [ctypes.c_void_p]
        user32.IsWindowVisible.restype = ctypes.c_bool
        user32.GetWindowTextLengthW.argtypes = [ctypes.c_void_p]
        user32.GetWindowTextLengthW.restype = ctypes.c_int
        user32.GetWindowTextW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_int]
        user32.GetWindowTextW.restype = ctypes.c_int
        user32.GetWindowThreadProcessId.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_ulong)]
        user32.GetWindowThreadProcessId.restype = ctypes.c_ulong

        def callback(hwnd, _lparam) -> bool:
            try:
                if not user32.IsWindowVisible(hwnd):
                    return True
                length = user32.GetWindowTextLengthW(hwnd)
                if length <= 0:
                    return True
                buffer = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buffer, length + 1)
                title = str(buffer.value or "").strip()
                if not title:
                    return True
                pid = ctypes.c_ulong()
                user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                windows.append({
                    "hwnd": str(int(hwnd or 0)),
                    "pid": str(int(pid.value or 0)),
                    "process_name": self._process_name_for_pid(int(pid.value or 0)).lower(),
                    "window_title": title,
                })
            except Exception:
                return True
            return True

        try:
            user32.EnumWindows(enum_proc_type(callback), None)
        except Exception:
            return []
        return windows

    def _process_names_for_app_kind(self, app_kind: str) -> list[str]:
        mapping = {
            "notepad": ["notepad.exe"],
            "vscode": ["code.exe"],
            "office_word": ["winword.exe"],
            "office_excel": ["excel.exe"],
            "office_powerpoint": ["powerpnt.exe"],
            "wps_writer": ["wps.exe"],
            "wps_spreadsheet": ["et.exe"],
            "wps_presentation": ["wpp.exe"],
        }
        return mapping.get(str(app_kind or "").strip().lower(), [])

    def _process_name_for_app_kind(self, app_kind: str) -> str:
        names = self._process_names_for_app_kind(app_kind)
        return names[0] if names else ""

    def _document_adapter_for_app_kind(self, app_kind: str) -> str:
        normalized = str(app_kind or "").strip().lower()
        if normalized == "vscode":
            return "vscode"
        if normalized.startswith("office"):
            return "office"
        if normalized.startswith("wps"):
            return "wps"
        if normalized == "notepad":
            return "notepad"
        return "default_app"

    def _close_strategy_for_opened_app(self, app_kind: str, title_matched: bool) -> str:
        normalized = str(app_kind or "").strip().lower()
        if normalized == "notepad":
            return "wm_close_notepad_resolved_hwnd" if title_matched else "wm_close_notepad_owned_pid"
        if normalized in {"vscode", "office_word", "office_excel", "office_powerpoint", "wps_writer", "wps_spreadsheet", "wps_presentation"}:
            return "app_document_adapter_required" if title_matched else "unsupported_precise_close"
        if normalized == "default_app":
            return "wm_close_owned_single_document_window" if title_matched else "unsupported_precise_close"
        return "unsupported_precise_close"

    def _open_method_for_app_kind(self, app_kind: str) -> str:
        normalized = str(app_kind or "").strip().lower()
        if normalized == "notepad":
            return "notepad"
        if normalized == "vscode":
            return "vscode"
        if normalized.startswith("office") or normalized.startswith("wps"):
            return "specified_app"
        return "specified_app"

    def _file_open_message(self, app_kind: str, title_matched: bool) -> str:
        if title_matched:
            return f"Host opened file with {self._app_label_for_kind(app_kind)}."
        return "Host dispatched file open request, but the document window was not resolved."

    def _app_label_for_kind(self, app_kind: str) -> str:
        return {
            "vscode": "Visual Studio Code",
            "office_word": "Microsoft Word",
            "office_excel": "Microsoft Excel",
            "office_powerpoint": "Microsoft PowerPoint",
            "wps_writer": "WPS Writer",
            "wps_spreadsheet": "WPS Spreadsheet",
            "wps_presentation": "WPS Presentation",
            "notepad": "记事本",
            "default_app": "Windows 默认应用",
        }.get(str(app_kind or "").strip().lower(), str(app_kind or "应用"))

    def _folder_open(self, task: dict) -> dict:
        path = self._target_path(task)
        if not path:
            return self._error("folder.open", "Missing folder path.")
        p = Path(path)
        if not p.exists() or not p.is_dir():
            return self._error("folder.open", f"Folder does not exist: {path}")
        existing_windows = self._find_explorer_windows(str(p))
        focusable_windows = [
            item for item in existing_windows
            if self._paths_equal(str(item.get("current_path", "") or ""), str(p))
        ]
        if focusable_windows:
            window = focusable_windows[0]
            try:
                hwnd = int(window.get("hwnd", 0) or 0)
            except Exception:
                hwnd = 0
            focused = self._focus_window(hwnd)
            return self._ok("folder.open", "Host focused existing folder window.", {
                "path": str(p),
                "target_path": str(p),
                "target_type": "directory",
                "open_method": "explorer",
                "process_name": "explorer.exe",
                "hwnd": str(hwnd) if hwnd > 0 else "",
                "window_title": str(window.get("window_title", window.get("title", "")) or ""),
                "current_path": str(window.get("current_path", "") or ""),
                "close_action": "folder.close",
                "close_strategy": "wm_close_explorer_path",
                "close_scope": "all_matching_path",
                "already_open": True,
                "focused_existing": focused,
                "matched_count": len(existing_windows),
                "matched_hwnds": [str(item.get("hwnd", "") or "") for item in existing_windows],
            })
        subprocess.Popen(["explorer.exe", str(p)], shell=False)
        time.sleep(0.4)
        windows = self._find_explorer_windows(str(p))
        focusable_windows = [
            item for item in windows
            if self._paths_equal(str(item.get("current_path", "") or ""), str(p))
        ]
        window = focusable_windows[0] if focusable_windows else (windows[0] if windows else {})
        return self._ok("folder.open", "Host opened folder.", {
            "path": str(p),
            "target_path": str(p),
            "target_type": "directory",
            "open_method": "explorer",
            "process_name": "explorer.exe",
            "hwnd": str(window.get("hwnd", "") or ""),
            "window_title": str(window.get("window_title", window.get("title", "")) or ""),
            "current_path": str(window.get("current_path", "") or ""),
            "close_action": "folder.close",
            "close_strategy": "wm_close_explorer_path",
            "close_scope": "all_matching_path",
            "already_open": False,
            "focused_existing": False,
            "matched_count": len(windows),
        })

    def _file_close(self, task: dict) -> dict:
        args = self._args(task)
        path = self._target_path(task)
        session_id = str(args.get("session_id", "") or "").strip()
        open_method = str(args.get("open_method", "") or "").strip().lower()
        process_name = str(args.get("process_name", "") or "").strip().lower()
        pid_text = str(args.get("pid", "") or "").strip()
        close_context = self._heibingtai_close_context(args)
        if not self._truthy(args.get("open_session_owned", False)):
            return self._error("file.close", "File close requires an open_session owned by this system.", {
                **close_context,
                "error": "unowned_window_not_supported",
                "session_id": session_id,
                "target_path": path,
                "close_strategy": "wm_close_notepad_owned_pid",
            })
        if open_method != "notepad" and process_name != "notepad.exe":
            return self._error("file.close", "Precise close is only supported for owned Notepad sessions.", {
                **close_context,
                "error": "unsupported_precise_close",
                "session_id": session_id,
                "target_path": path,
                "close_strategy": "unsupported_precise_close",
            })
        if not pid_text:
            return self._error("file.close", "File close requires an owned open_session pid.", {
                **close_context,
                "error": "unowned_window_not_supported",
                "session_id": session_id,
                "target_path": path,
                "close_strategy": "wm_close_notepad_owned_pid",
            })
        try:
            pid = int(pid_text)
        except Exception:
            return self._error("file.close", "Invalid Notepad pid.", {
                **close_context,
                "error": "unowned_window_not_supported",
                "session_id": session_id,
                "target_path": path,
                "close_strategy": "wm_close_notepad_owned_pid",
            })
        window = self._find_window_for_pid(pid, expected_name=Path(path).name if path else "")
        hwnd = int(window.get("hwnd", 0) or 0)
        if hwnd <= 0:
            return self._error("file.close", "Owned Notepad window was not found.", {
                **close_context,
                "error": "window_not_found",
                "session_id": session_id,
                "target_path": path,
                "pid": str(pid),
                "close_strategy": "wm_close_notepad_owned_pid",
            })
        if not self._post_wm_close(hwnd):
            return self._error("file.close", "Failed to send WM_CLOSE to Notepad.", {
                **close_context,
                "error": "wm_close_failed",
                "session_id": session_id,
                "target_path": path,
                "pid": str(pid),
                "hwnd": str(hwnd),
                "window_title": str(window.get("title", "") or ""),
                "close_strategy": "wm_close_notepad_owned_pid",
            })
        time.sleep(0.8)
        if self._is_process_running(pid):
            return self._error("file.close", "Notepad is waiting for user save confirmation.", {
                **close_context,
                "error": "needs_user_save_confirmation",
                "session_id": session_id,
                "target_path": path,
                "pid": str(pid),
                "hwnd": str(hwnd),
                "window_title": str(window.get("title", "") or ""),
                "close_strategy": "wm_close_notepad_owned_pid",
            })
        return self._ok("file.close", "Host closed Notepad file window.", {
            **close_context,
            "target_path": path,
            "target_type": "file",
            "session_id": session_id,
            "pid": str(pid),
            "hwnd": str(hwnd),
            "window_title": str(window.get("title", "") or ""),
            "close_strategy": "wm_close_notepad_owned_pid",
            "close_succeeded": True,
        })

    def _folder_close(self, task: dict) -> dict:
        args = self._args(task)
        path = self._target_path(task)
        session_id = str(args.get("session_id", "") or "").strip()
        close_scope = str(args.get("close_scope", "") or "all_matching_path").strip().lower()
        close_context = self._heibingtai_close_context(args)
        if not path:
            return self._error("folder.close", "Missing folder path.", {
                **close_context,
                "error": "missing_target_path",
                "session_id": session_id,
                "target_path": path,
                "matched_count": 0,
                "closed_count": 0,
                "closed_hwnds": [],
                "close_scope": close_scope,
                "close_strategy": "wm_close_explorer_path",
            })
        matches = self._find_explorer_windows(path)
        if not matches:
            return self._error("folder.close", "No Explorer folder window matched target_path.", {
                **close_context,
                "error": "window_not_found",
                "session_id": session_id,
                "target_path": path,
                "matched_count": 0,
                "closed_count": 0,
                "closed_hwnds": [],
                "close_scope": close_scope,
                "close_strategy": "wm_close_explorer_path",
            })
        closed_hwnds: list[str] = []
        failed_hwnds: list[str] = []
        skip_reasons: dict[str, str] = {}
        seen_hwnds: set[str] = set()
        for window in matches:
            try:
                hwnd = int(window.get("hwnd", 0) or 0)
            except Exception:
                hwnd = 0
            if hwnd <= 0:
                continue
            hwnd_text = str(hwnd)
            if hwnd_text in seen_hwnds:
                continue
            seen_hwnds.add(hwnd_text)
            if close_scope == "all_matching_path":
                if not bool(window.get("path_matched", True)):
                    failed_hwnds.append(hwnd_text)
                    skip_reasons[hwnd_text] = "path_not_matched"
                    continue
                if self._post_wm_close(hwnd):
                    closed_hwnds.append(hwnd_text)
                else:
                    failed_hwnds.append(hwnd_text)
                    skip_reasons[hwnd_text] = "wm_close_failed"
                continue
            current = self._get_current_explorer_window_path(hwnd)
            current_path = str(current.get("current_path", "") or "")
            is_tabbed_possible = bool(
                current.get("is_tabbed_explorer_possible", False)
                or window.get("is_tabbed_explorer_possible", False)
            )
            if not current_path:
                failed_hwnds.append(hwnd_text)
                skip_reasons[hwnd_text] = "explorer_tab_not_supported" if is_tabbed_possible else "explorer_active_tab_mismatch"
                continue
            if not self._paths_equal(current_path, path):
                failed_hwnds.append(hwnd_text)
                skip_reasons[hwnd_text] = "explorer_active_tab_mismatch"
                continue
            if self._post_wm_close(hwnd):
                closed_hwnds.append(hwnd_text)
            else:
                failed_hwnds.append(hwnd_text)
        if not closed_hwnds:
            error = self._folder_close_error(skip_reasons)
            message = (
                "Explorer tab close is not safely supported when target tab is not active."
                if error == "unsupported_precise_tab_close"
                else "Failed to send WM_CLOSE to matching Explorer windows."
            )
            return self._error("folder.close", message, {
                **close_context,
                "error": error,
                "close_error": error,
                "session_id": session_id,
                "target_path": path,
                "matched_count": len(matches),
                "closed_count": 0,
                "skipped_count": len(skip_reasons),
                "closed_hwnds": [],
                "failed_hwnds": failed_hwnds,
                "skip_reasons": skip_reasons,
                "close_scope": close_scope,
                "close_strategy": "wm_close_explorer_path",
                "matched_windows": matches,
            })
        return self._ok("folder.close", "Host closed Explorer folder windows.", {
            **close_context,
            "target_path": path,
            "target_type": "directory",
            "session_id": session_id,
            "matched_count": len(matches),
            "closed_count": len(closed_hwnds),
            "skipped_count": len(skip_reasons),
            "closed_hwnds": closed_hwnds,
            "failed_hwnds": failed_hwnds,
            "skip_reasons": skip_reasons,
            "close_scope": close_scope,
            "close_strategy": "wm_close_explorer_path",
            "matched_windows": matches,
            "close_succeeded": True,
        })

    def _file_create(self, task: dict) -> dict:
        path = self._target_path(task)
        if not path:
            return self._error("file.create", "Missing file path.")
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.touch(exist_ok=True)
        return self._ok(str(task.get("action", "file.create") or "file.create"), "Host created file.", {"path": str(p)})

    def _folder_create(self, task: dict) -> dict:
        path = self._target_path(task)
        if not path:
            return self._error("folder.create", "Missing folder path.")
        p = Path(path)
        p.mkdir(parents=True, exist_ok=True)
        return self._ok(str(task.get("action", "folder.create") or "folder.create"), "Host created folder.", {"path": str(p)})

    def _rename_path(self, task: dict) -> dict:
        source = self._target_path(task)
        dest = self._dest_path(task)
        action = str(task.get("action", "rename") or "rename")
        if not source or not dest:
            return self._error(action, "Missing source_path or dest_path.")

        src = Path(source)
        dst = Path(dest)
        if not src.exists():
            return self._error(action, f"Source path does not exist: {src}")

        dst.parent.mkdir(parents=True, exist_ok=True)
        src.rename(dst)
        return self._ok(action, "Host renamed path.", {"source_path": str(src), "dest_path": str(dst)})

    def _move_path(self, task: dict) -> dict:
        source = self._target_path(task)
        dest = self._dest_path(task)
        action = str(task.get("action", "move") or "move")
        if not source or not dest:
            return self._error(action, "Missing source_path or dest_path.")

        src = Path(source)
        dst = Path(dest)
        if not src.exists():
            return self._error(action, f"Source path does not exist: {src}")

        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))
        return self._ok(action, "Host moved path.", {"source_path": str(src), "dest_path": str(dst)})

    def _copy_path(self, task: dict) -> dict:
        source = self._target_path(task)
        dest = self._dest_path(task)
        if not source or not dest:
            return self._error("file.copy", "Missing source_path or dest_path.")

        src = Path(source)
        dst = Path(dest)
        if not src.exists() or not src.is_file():
            return self._error("file.copy", f"Source file does not exist: {src}")

        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(src), str(dst))
        return self._ok("file.copy", "Host copied file.", {"source_path": str(src), "dest_path": str(dst)})

    def _delete_path(self, task: dict) -> dict:
        action = str(task.get("action", "") or "").strip().lower()
        args = self._args(task)
        path = self._target_path(task)
        quarantine = str(args.get("quarantine_path", "") or "").strip()
        target_type = str(args.get("target_type", "") or "").strip().lower()

        if not quarantine:
            return self._error(action, "Missing quarantine_path.", {"error": "missing_quarantine_path"})

        if not path:
            return self._error(action, "Missing delete path.", {"error": "missing_source_path"})

        p = Path(path)
        if not p.exists():
            return self._error(action, f"Path does not exist: {p}", {"error": "source_not_found", "original_path": str(p)})
        if action == "file.delete" and p.is_dir():
            return self._error(action, f"Source is not a file: {p}", {"error": "source_type_mismatch", "original_path": str(p)})
        if action == "folder.delete" and not p.is_dir():
            return self._error(action, f"Source is not a folder: {p}", {"error": "source_type_mismatch", "original_path": str(p)})

        q = Path(quarantine)
        if q.exists():
            return self._error(action, f"Quarantine path already exists: {q}", {"error": "quarantine_exists", "quarantine_path": str(q), "original_path": str(p)})

        q.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(p), str(q))
        return self._ok(action, "Host quarantined folder." if action == "folder.delete" else "Host quarantined file.", {
            "action": action,
            "path": str(p),
            "original_path": str(p),
            "source_path": str(p),
            "quarantine_path": str(q),
            "target_type": target_type or ("directory" if action == "folder.delete" else "file"),
            "material_id": str(args.get("material_id", "") or ""),
            "checkpoint_id": str(args.get("checkpoint_id", "") or ""),
            "restore_token": str(args.get("restore_token", "") or ""),
            "restore_action": "folder.restore" if action == "folder.delete" else "file.restore",
            "run_id": str(args.get("yushitai_run_id", args.get("run_id", "")) or ""),
            "run_backend": "host",
        })

    def _restore_path(self, task: dict) -> dict:
        action = str(task.get("action", "") or "").strip().lower()
        args = self._args(task)
        original = (
            str(args.get("original_path", "") or "").strip()
            or str(args.get("source_path", "") or "").strip()
            or self._target_path(task)
        )
        quarantine = str(args.get("quarantine_path", "") or "").strip()
        target_type = str(args.get("target_type", "") or "").strip().lower()
        if not args.get("restore_token") and not args.get("material_id") and not quarantine:
            return self._error(action, "Missing restore material.", {"error": "material_not_found"})
        if not quarantine:
            return self._error(action, "Missing quarantine_path.", {"error": "missing_quarantine_path"})
        if not original:
            return self._error(action, "Missing original_path.", {"error": "missing_original_path", "quarantine_path": quarantine})

        q = Path(quarantine)
        dst = Path(original)
        if not q.exists():
            return self._error(action, f"Quarantine path does not exist: {q}", {"error": "quarantine_not_found", "quarantine_path": str(q), "original_path": str(dst)})
        if dst.exists():
            return self._error(action, f"Destination already exists: {dst}", {"error": "destination_exists", "quarantine_path": str(q), "original_path": str(dst)})
        if action == "file.restore" and q.is_dir():
            return self._error(action, f"Quarantine object is not a file: {q}", {"error": "source_type_mismatch", "quarantine_path": str(q), "original_path": str(dst)})
        if action == "folder.restore" and not q.is_dir():
            return self._error(action, f"Quarantine object is not a folder: {q}", {"error": "source_type_mismatch", "quarantine_path": str(q), "original_path": str(dst)})

        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(q), str(dst))
        return self._ok(action, "Host restored folder." if action == "folder.restore" else "Host restored file.", {
            "action": action,
            "path": str(dst),
            "target_path": str(dst),
            "original_path": str(dst),
            "quarantine_path": str(q),
            "target_type": target_type or ("directory" if action == "folder.restore" else "file"),
            "material_id": str(args.get("material_id", "") or ""),
            "checkpoint_id": str(args.get("checkpoint_id", "") or ""),
            "restore_token": str(args.get("restore_token", "") or ""),
            "run_id": str(args.get("yushitai_run_id", args.get("run_id", "")) or ""),
            "run_backend": "host",
        })

    def _browser_search_open(self, task: dict) -> dict:
        args = self._args(task)
        raw_url = str(args.get("url", "") or args.get("target_url", "") or "").strip()
        query = str(args.get("query", "") or args.get("search_query", "") or task.get("target_name", "") or "").strip()
        url = raw_url or (f"https://www.google.com/search?q={quote_plus(query)}" if query else "")
        if not url:
            return self._error("browser.search_open", "Missing URL or search query.")
        webbrowser.open(url)
        return self._ok("browser.search_open", "Host opened browser search.", {"url": url, "query": query})

    def _host_app_close_block_reason(self, task: dict) -> tuple[bool, str]:
        args = self._args(task)
        category = str(args.get("category", "") or "").strip().lower()
        candidate_kind = str(args.get("candidate_kind", "") or "").strip().lower()
        path_status = str(args.get("path_status", "") or "").strip().lower()
        platform = str(args.get("platform", "") or "").strip().lower()
        platform_type = str(args.get("platform_object_type", "") or "").strip().lower()
        launch_kind = str(args.get("launch_target_kind", "") or "").strip().lower()
        target_path = self._target_path(task).replace("/", "\\").lower()
        blocked_categories = {
            "system",
            "system_core",
            "admin",
            "admin_tool",
            "driver",
            "runtime",
            "runtime_env",
            "driver_or_runtime",
            "platform",
            "installer_bundle",
            "diagnostics_only",
        }
        if category in blocked_categories:
            return True, f"blocked_category:{category}"
        if candidate_kind in blocked_categories:
            return True, f"blocked_candidate_kind:{candidate_kind}"
        if path_status in {"driver_or_runtime", "installer_bundle", "system_core", "diagnostics_only"}:
            return True, f"blocked_path_status:{path_status}"
        if platform in {"steam"}:
            return True, "blocked_platform:steam"
        if platform and platform not in {"unknown", "local", "windows", "host"}:
            return True, f"blocked_platform:{platform}"
        if platform_type:
            return True, f"blocked_platform_object:{platform_type}"
        if launch_kind == "protocol":
            return True, "blocked_protocol_entry"
        if "\\windows\\system32\\" in target_path or "\\windows\\syswow64\\" in target_path:
            return True, "blocked_windows_system_path"
        return False, ""

    def _close_process_main_windows(self, names: list[str]) -> dict[str, object]:
        process_names = sorted({
            Path(str(name or "").strip()).stem
            for name in names
            if str(name or "").strip()
        })
        if not process_names:
            return {
                "close_attempts": [],
                "matched_count": 0,
                "closed_count": 0,
                "skipped_count": 0,
                "skip_reasons": {},
                "process_names": [],
            }
        script = rf"""
$names = @({", ".join(self._ps_quote(name) for name in process_names)})
$attempts = @()
$matched = 0
$closed = 0
$skipped = 0
foreach ($name in $names) {{
    try {{
        $processes = @(Get-Process -Name $name -ErrorAction SilentlyContinue)
        foreach ($proc in $processes) {{
            if ([int64]$proc.MainWindowHandle -le 0) {{
                $skipped += 1
                $attempts += [pscustomobject]@{{
                    process_name = [string]$proc.ProcessName
                    pid = [string]$proc.Id
                    main_window_handle = [string]$proc.MainWindowHandle
                    closed = $false
                    skipped = $true
                    skip_reason = "main_window_not_found"
                }}
                continue
            }}
            $matched += 1
            $requested = $false
            try {{
                $requested = [bool]$proc.CloseMainWindow()
            }} catch {{
                $requested = $false
            }}
            if ($requested) {{ $closed += 1 }} else {{ $skipped += 1 }}
            $attempts += [pscustomobject]@{{
                process_name = [string]$proc.ProcessName
                pid = [string]$proc.Id
                main_window_handle = [string]$proc.MainWindowHandle
                closed = $requested
                skipped = (-not $requested)
                skip_reason = if ($requested) {{ "" }} else {{ "close_main_window_failed" }}
            }}
        }}
    }} catch {{}}
}}
$skipReasons = @{{}}
foreach ($attempt in $attempts) {{
    if ($attempt.skipped -and $attempt.skip_reason) {{
        $skipReasons[[string]$attempt.pid] = [string]$attempt.skip_reason
    }}
}}
[pscustomobject]@{{
    close_attempts = $attempts
    process_names = $names
    matched_count = $matched
    closed_count = $closed
    skipped_count = $skipped
    skip_reasons = $skipReasons
}} | ConvertTo-Json -Compress -Depth 4
"""
        try:
            completed = subprocess.run(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
                capture_output=True,
                text=True,
                timeout=5,
                shell=False,
            )
        except Exception:
            completed = None
        if completed is None or completed.returncode != 0:
            return {
                "close_attempts": [],
                "matched_count": 0,
                "closed_count": 0,
                "skipped_count": len(process_names),
                "skip_reasons": {name: "process_query_failed" for name in process_names},
                "process_names": process_names,
            }
        try:
            data = json.loads(str(completed.stdout or "").strip() or "{}")
        except Exception:
            data = {}
        return data if isinstance(data, dict) else {}

    def _force_taskkill_app_close(self, names: list[str]) -> dict:
        attempts = []
        for name in names:
            completed = subprocess.run(
                ["taskkill", "/IM", name, "/T"],
                capture_output=True,
                text=True,
                shell=False,
            )
            attempts.append({
                "process_name": name,
                "returncode": completed.returncode,
                "stdout": completed.stdout,
                "stderr": completed.stderr,
            })
        closed_count = len([item for item in attempts if item["returncode"] == 0])
        data = {
            "close_strategy": "taskkill_force_confirmed",
            "close_attempts": attempts,
            "matched_count": len(attempts),
            "closed_count": closed_count,
            "skipped_count": len(attempts) - closed_count,
            "skip_reasons": {
                str(item.get("process_name", "")): "taskkill_failed"
                for item in attempts
                if item.get("returncode") != 0
            },
        }
        if closed_count > 0:
            return self._ok("app.close", "Host force close requested.", data)
        return self._error("app.close", "Host force close failed or process does not exist.", {
            "error": "process_window_not_found",
            **data,
        })

    def _find_explorer_window(self, target_path: str) -> dict[str, str]:
        windows = self._find_explorer_windows(target_path)
        return windows[0] if windows else {}

    def _find_explorer_windows(self, target_path: str) -> list[dict[str, str]]:
        normalized = self._normalize_path(target_path)
        if not normalized:
            return []
        script = rf"""
$target = {self._ps_quote(normalized)}
$targetPath = {self._ps_quote(target_path)}
$items = @()
$signature = @'
[DllImport("user32.dll", CharSet = CharSet.Unicode)]
public static extern int GetWindowText(System.IntPtr hWnd, System.Text.StringBuilder text, int count);
'@
try {{
    Add-Type -MemberDefinition $signature -Name WinText -Namespace HostExplorerSafeClose -ErrorAction SilentlyContinue | Out-Null
}} catch {{}}
function Get-TopWindowTitle([IntPtr]$hwnd) {{
    try {{
        $builder = New-Object System.Text.StringBuilder 512
        [HostExplorerSafeClose.WinText]::GetWindowText($hwnd, $builder, $builder.Capacity) | Out-Null
        return [string]$builder.ToString()
    }} catch {{
        return ""
    }}
}}
function Resolve-ExplorerPath([object]$window) {{
    try {{
        $url = [string]$window.LocationURL
        if (-not $url) {{ return "" }}
        $uri = [Uri]$url
        return [Uri]::UnescapeDataString($uri.LocalPath)
    }} catch {{
        return ""
    }}
}}
function Normalize-ExplorerPath([string]$path) {{
    try {{
        if (-not $path) {{ return "" }}
        return [System.IO.Path]::GetFullPath($path).TrimEnd('\').ToLowerInvariant()
    }} catch {{
        return ""
    }}
}}
$shell = New-Object -ComObject Shell.Application
foreach ($window in $shell.Windows()) {{
    try {{
        $full = [string]$window.FullName
        if (-not $full.ToLowerInvariant().EndsWith("explorer.exe")) {{ continue }}
        $path = Resolve-ExplorerPath $window
        if (-not $path) {{ continue }}
        $fullPath = Normalize-ExplorerPath $path
        if (-not $fullPath) {{ continue }}
        $hwnd = [string]$window.HWND
        $items += [pscustomobject]@{{
            hwnd = $hwnd
            title = [string]$window.LocationName
            window_title = Get-TopWindowTitle ([IntPtr]([int64]$window.HWND))
            location = $path
            current_path = ""
            target_path = $targetPath
            normalized = $fullPath
            path_matched = ($fullPath -eq $target)
            is_tabbed_explorer_possible = $false
        }}
    }} catch {{}}
}}
$results = @()
foreach ($group in ($items | Group-Object hwnd)) {{
    $groupItems = @($group.Group)
    $paths = @($groupItems | Select-Object -ExpandProperty normalized -Unique)
    $activePath = ""
    $tabbed = $paths.Count -gt 1
    if ($paths.Count -eq 1) {{
        $activePath = [string]$groupItems[0].location
    }} else {{
        $topTitle = ([string]$groupItems[0].window_title).ToLowerInvariant()
        if ($topTitle) {{
            $nameMatches = @($groupItems | Where-Object {{
                $name = ([string]$_.title).ToLowerInvariant()
                $name -and ($topTitle -eq $name -or $topTitle.StartsWith($name + " -"))
            }})
            $matchedPaths = @($nameMatches | Select-Object -ExpandProperty normalized -Unique)
            if ($matchedPaths.Count -eq 1) {{
                $active = @($nameMatches | Where-Object {{ $_.normalized -eq $matchedPaths[0] }})[0]
                $activePath = [string]$active.location
            }}
        }}
    }}
    foreach ($item in $groupItems) {{
        if (-not $item.path_matched) {{ continue }}
        $item.current_path = $activePath
        $item.is_tabbed_explorer_possible = $tabbed
        $results += $item
    }}
}}
@($results) | Select-Object hwnd,title,window_title,location,current_path,target_path,path_matched,is_tabbed_explorer_possible | ConvertTo-Json -Compress
"""
        try:
            completed = subprocess.run(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
                capture_output=True,
                text=True,
                timeout=5,
                shell=False,
            )
        except Exception:
            return []
        if completed.returncode != 0:
            return []
        text = str(completed.stdout or "").strip()
        if not text:
            return []
        try:
            data = json.loads(text)
        except Exception:
            return []
        if isinstance(data, dict):
            return [data]
        if not isinstance(data, list):
            return []
        return [item for item in data if isinstance(item, dict)]

    def _get_current_explorer_window_path(self, hwnd: int) -> dict[str, object]:
        if int(hwnd or 0) <= 0:
            return {}
        script = rf"""
$targetHwnd = {self._ps_quote(str(int(hwnd)))}
$items = @()
$signature = @'
[DllImport("user32.dll", CharSet = CharSet.Unicode)]
public static extern int GetWindowText(System.IntPtr hWnd, System.Text.StringBuilder text, int count);
'@
try {{
    Add-Type -MemberDefinition $signature -Name WinText -Namespace HostExplorerSafeClose -ErrorAction SilentlyContinue | Out-Null
}} catch {{}}
function Get-TopWindowTitle([IntPtr]$hwnd) {{
    try {{
        $builder = New-Object System.Text.StringBuilder 512
        [HostExplorerSafeClose.WinText]::GetWindowText($hwnd, $builder, $builder.Capacity) | Out-Null
        return [string]$builder.ToString()
    }} catch {{
        return ""
    }}
}}
function Resolve-ExplorerPath([object]$window) {{
    try {{
        $url = [string]$window.LocationURL
        if (-not $url) {{ return "" }}
        $uri = [Uri]$url
        return [Uri]::UnescapeDataString($uri.LocalPath)
    }} catch {{
        return ""
    }}
}}
function Normalize-ExplorerPath([string]$path) {{
    try {{
        if (-not $path) {{ return "" }}
        return [System.IO.Path]::GetFullPath($path).TrimEnd('\').ToLowerInvariant()
    }} catch {{
        return ""
    }}
}}
$shell = New-Object -ComObject Shell.Application
foreach ($window in $shell.Windows()) {{
    try {{
        $full = [string]$window.FullName
        if (-not $full.ToLowerInvariant().EndsWith("explorer.exe")) {{ continue }}
        $hwnd = [string]$window.HWND
        if ($hwnd -ne $targetHwnd) {{ continue }}
        $path = Resolve-ExplorerPath $window
        if (-not $path) {{ continue }}
        $normalized = Normalize-ExplorerPath $path
        if (-not $normalized) {{ continue }}
        $items += [pscustomobject]@{{
            hwnd = $hwnd
            title = [string]$window.LocationName
            window_title = Get-TopWindowTitle ([IntPtr]([int64]$window.HWND))
            location = $path
            normalized = $normalized
        }}
    }} catch {{}}
}}
$paths = @($items | Select-Object -ExpandProperty normalized -Unique)
$activePath = ""
$tabbed = $paths.Count -gt 1
if ($paths.Count -eq 1) {{
    $activePath = [string]$items[0].location
}} elseif ($paths.Count -gt 1) {{
    $topTitle = ([string]$items[0].window_title).ToLowerInvariant()
    if ($topTitle) {{
        $nameMatches = @($items | Where-Object {{
            $name = ([string]$_.title).ToLowerInvariant()
            $name -and ($topTitle -eq $name -or $topTitle.StartsWith($name + " -"))
        }})
        $matchedPaths = @($nameMatches | Select-Object -ExpandProperty normalized -Unique)
        if ($matchedPaths.Count -eq 1) {{
            $active = @($nameMatches | Where-Object {{ $_.normalized -eq $matchedPaths[0] }})[0]
            $activePath = [string]$active.location
        }}
    }}
}}
[pscustomobject]@{{
    hwnd = $targetHwnd
    current_path = $activePath
    window_title = if ($items.Count -gt 0) {{ [string]$items[0].window_title }} else {{ "" }}
    tab_path_count = $paths.Count
    is_tabbed_explorer_possible = $tabbed
}} | ConvertTo-Json -Compress
"""
        try:
            completed = subprocess.run(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
                capture_output=True,
                text=True,
                timeout=5,
                shell=False,
            )
        except Exception:
            return {}
        if completed.returncode != 0:
            return {}
        text = str(completed.stdout or "").strip()
        if not text:
            return {}
        try:
            data = json.loads(text)
        except Exception:
            return {}
        return data if isinstance(data, dict) else {}

    def _find_window_for_pid(self, pid: int, *, expected_name: str = "") -> dict[str, object]:
        user32 = ctypes.windll.user32
        result: dict[str, object] = {}
        expected = str(expected_name or "").strip().lower()

        def callback(hwnd: int, _lparam: int) -> bool:
            if not user32.IsWindowVisible(hwnd):
                return True
            process_id = ctypes.c_ulong()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(process_id))
            if int(process_id.value) != int(pid):
                return True
            length = user32.GetWindowTextLengthW(hwnd)
            buffer = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buffer, length + 1)
            title = str(buffer.value or "")
            if expected and expected not in title.lower():
                return True
            result.update({"hwnd": hwnd, "title": title})
            return False

        enum_proc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.c_int)(callback)
        user32.EnumWindows(enum_proc, 0)
        return result

    def _post_wm_close(self, hwnd: int) -> bool:
        if int(hwnd or 0) <= 0:
            return False
        return bool(ctypes.windll.user32.PostMessageW(int(hwnd), 0x0010, 0, 0))

    def _focus_window(self, hwnd: int) -> bool:
        if int(hwnd or 0) <= 0:
            return False
        try:
            user32 = ctypes.windll.user32
            user32.ShowWindow(int(hwnd), 9)
            return bool(user32.SetForegroundWindow(int(hwnd)))
        except Exception:
            return False

    def _get_foreground_window_info(self) -> dict[str, object]:
        try:
            user32 = ctypes.windll.user32
            hwnd = int(user32.GetForegroundWindow() or 0)
            if hwnd <= 0:
                return {}
            process_id = ctypes.c_ulong()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(process_id))
            length = user32.GetWindowTextLengthW(hwnd)
            buffer = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buffer, length + 1)
            pid = int(process_id.value or 0)
            return {
                "hwnd": str(hwnd),
                "pid": str(pid),
                "process_name": self._process_name_for_pid(pid),
                "window_title": str(buffer.value or ""),
            }
        except Exception:
            return {}

    def _process_name_for_pid(self, pid: int) -> str:
        if int(pid or 0) <= 0:
            return ""
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, int(pid))
        if not handle:
            return ""
        try:
            size = ctypes.c_ulong(32768)
            buffer = ctypes.create_unicode_buffer(size.value)
            if not kernel32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
                return ""
            return Path(str(buffer.value or "")).name
        except Exception:
            return ""
        finally:
            kernel32.CloseHandle(handle)

    def _infer_app_kind(self, process_name: str, window_title: str = "", target_path: str = "") -> str:
        name = str(process_name or "").strip().lower()
        if name == "code.exe":
            return "vscode"
        if name == "winword.exe":
            return "office_word"
        if name == "excel.exe":
            return "office_excel"
        if name == "powerpnt.exe":
            return "office_powerpoint"
        if name == "wps.exe":
            return "wps_writer"
        if name == "et.exe":
            return "wps_spreadsheet"
        if name == "wpp.exe":
            return "wps_presentation"
        if name == "notepad.exe":
            return "notepad"
        return "default_app"

    def _title_matches_file(self, window_title: str, target_path: str) -> bool:
        title = str(window_title or "").strip().lower()
        path = Path(str(target_path or ""))
        file_name = path.name.lower()
        stem = path.stem.lower()
        if not title or not file_name:
            return False
        if file_name in title:
            return True
        return bool(stem and stem in title)

    def _is_process_running(self, pid: int) -> bool:
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        STILL_ACTIVE = 259
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, int(pid))
        if not handle:
            return False
        try:
            code = ctypes.c_ulong()
            if not kernel32.GetExitCodeProcess(handle, ctypes.byref(code)):
                return False
            return int(code.value) == STILL_ACTIVE
        finally:
            kernel32.CloseHandle(handle)

    def _normalize_path(self, value: str) -> str:
        text = str(value or "").strip()
        if not text:
            return ""
        try:
            return str(Path(unquote(text)).expanduser().resolve(strict=False)).rstrip("\\/").lower()
        except Exception:
            return text.rstrip("\\/").lower()

    def _paths_equal(self, left: str, right: str) -> bool:
        normalized_left = self._normalize_path(left)
        normalized_right = self._normalize_path(right)
        return bool(normalized_left and normalized_right and normalized_left == normalized_right)

    def _folder_close_error(self, skip_reasons: dict[str, str]) -> str:
        reasons = {str(value or "") for value in skip_reasons.values()}
        if "explorer_active_tab_mismatch" in reasons:
            return "unsupported_precise_tab_close"
        if "explorer_tab_not_supported" in reasons:
            return "explorer_tab_not_supported"
        return "unsupported_precise_close"

    def _heibingtai_close_context(self, args: dict[str, Any]) -> dict[str, Any]:
        if not self._truthy(args.get("heibingtai_enabled", False)):
            return {}
        return {
            "heibingtai_enabled": True,
            "close_level": str(args.get("close_level", "") or ""),
            "target_origin": str(args.get("target_origin", "") or ""),
            "close_scope": str(args.get("close_scope", "") or ""),
            "app_kind": str(args.get("app_kind", "") or ""),
            "process_name": str(args.get("process_name", "") or ""),
        }

    def _app_close_plan_context(self, close_plan: dict[str, Any]) -> dict[str, Any]:
        plan = close_plan if isinstance(close_plan, dict) else {}
        candidate = plan.get("selected_candidate", {}) if isinstance(plan.get("selected_candidate"), dict) else {}
        return {
            "target_material_source": "heibingtai",
            "heibingtai_verified": bool(plan.get("heibingtai_verified", False)),
            "close_plan_id": str(plan.get("plan_id", "") or ""),
            "close_strategy": str(plan.get("close_strategy", "") or ""),
            "resolution_status": str(plan.get("resolution_status", "") or ""),
            "selected_candidate_label": str(candidate.get("label", "") or ""),
            "selected_candidate_target_type": str(candidate.get("target_type", "") or ""),
            "selected_candidate_process_name": str(candidate.get("process_name", "") or ""),
            "selected_candidate_pid": str(candidate.get("pid", "") or ""),
            "selected_candidate_hwnd": str(candidate.get("hwnd", "") or ""),
            "selected_candidate_window_title": str(candidate.get("window_title", "") or ""),
        }

    def _safe_int(self, value: Any) -> int:
        try:
            return int(str(value or "0").strip())
        except Exception:
            return 0

    def _ps_quote(self, value: str) -> str:
        return "'" + str(value or "").replace("'", "''") + "'"

    def _ok(self, action: str, message: str, data: dict | None = None) -> dict:
        return {
            "ok": True,
            "adapter_id": self.adapter_id,
            "message": message,
            "data": {
                "current_action": action,
                "adapter_stage": self.adapter_id,
                "execution_allowed": True,
                "execution_backend": "host",
                "executed_in": "host",
                "target_environment": "local_host",
                "path_namespace": "host_windows",
                **(data or {}),
            },
        }

    def _error(self, action: str, message: str, data: dict | None = None) -> dict:
        return {
            "ok": False,
            "adapter_id": self.adapter_id,
            "message": message,
            "data": {
                "current_action": action or "-",
                "adapter_stage": self.adapter_id,
                "execution_allowed": False,
                "execution_backend": "host",
                "executed_in": "host",
                "target_environment": "local_host",
                "path_namespace": "host_windows",
                **(data or {}),
            },
        }
