from __future__ import annotations

import ctypes
import json
import subprocess
from pathlib import Path
from typing import Any
from uuid import uuid4


SYSTEM_PROCESS_NAMES = {
    "cmd.exe",
    "conhost.exe",
    "explorer.exe",
    "powershell.exe",
    "pwsh.exe",
    "services.exe",
    "taskmgr.exe",
    "wininit.exe",
    "winlogon.exe",
}


class AppTargetResolver:
    """Resolve app.close runtime targets without executing close actions."""

    def __init__(self, project_root: str | Path | None = None) -> None:
        self.project_root = Path(project_root or Path(__file__).resolve().parents[4]).expanduser().resolve()

    def resolve(self, task: dict[str, Any]) -> dict[str, Any]:
        payload = task if isinstance(task, dict) else {}
        hint = self._target_hint(payload)
        app_hint = hint["app_hint"]
        candidates = self._resolve_candidates(payload, app_hint)
        status = self._resolution_status(candidates)
        return {
            "schema_version": "app_target_resolution_v1",
            "resolution_id": f"app_resolution_{uuid4().hex}",
            "action": "app.close",
            "resolution_status": status,
            "target_hint": hint,
            "candidates": candidates,
            "candidate_count": len(candidates),
            "do_not_trust_llm_process_name": True,
            "safe_user_message": self._message_for_status(status),
        }

    def _resolve_candidates(self, task: dict[str, Any], app_hint: str) -> list[dict[str, Any]]:
        windows = self._visible_windows()
        ledger_matches = self._software_ledger_matches(app_hint)
        candidates: list[dict[str, Any]] = []

        for window in windows:
            candidate = self._candidate_from_window(window, app_hint, ledger_matches)
            if candidate:
                candidates.append(candidate)

        if not candidates:
            for process in self._process_matches(app_hint, ledger_matches):
                candidates.append(self._candidate_from_process(process, app_hint, ledger_matches))

        if not candidates and ledger_matches:
            for item in ledger_matches[:3]:
                candidates.append(self._candidate_from_ledger(item))

        return self._dedupe_and_rank(candidates)

    def _target_hint(self, task: dict[str, Any]) -> dict[str, str]:
        arguments = task.get("arguments", {}) if isinstance(task.get("arguments"), dict) else {}
        target = task.get("target", {}) if isinstance(task.get("target"), dict) else {}
        puzzle_summary = (
            task.get("original_puzzle_summary", {})
            if isinstance(task.get("original_puzzle_summary"), dict)
            else {}
        )
        values = [
            task.get("target_name", ""),
            task.get("target_path", ""),
            puzzle_summary.get("raw_user_text", ""),
            target.get("name_hint", ""),
            target.get("app_hint", ""),
            arguments.get("app_id", ""),
            arguments.get("app_name", ""),
            arguments.get("target_name", ""),
            arguments.get("target_path", ""),
            arguments.get("process_name", ""),
        ]
        process_names = arguments.get("process_names", [])
        if isinstance(process_names, list):
            values.extend(process_names)
        app_hint = " ".join(str(value or "").strip() for value in values if str(value or "").strip())
        return {
            "app_hint": app_hint,
            "task_target_name": str(task.get("target_name", "") or ""),
            "task_target_path": str(task.get("target_path", "") or ""),
            "llm_process_name_hint": str(arguments.get("process_name", "") or ""),
        }

    def _candidate_from_window(
        self,
        window: dict[str, Any],
        app_hint: str,
        ledger_matches: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        process_name = str(window.get("process_name", "") or "").strip().lower()
        title = str(window.get("window_title", "") or "").strip()
        if not self._matches_hint(app_hint, process_name, title):
            return None
        label = self._label_for(process_name, title, ledger_matches)
        target_type = self._target_type_for(process_name, title)
        return {
            "candidate_id": f"app_candidate_{uuid4().hex[:8]}",
            "label": label,
            "target_type": target_type,
            "app_id": self._app_id_for(process_name, ledger_matches),
            "app_kind": self._app_kind_for(process_name, ledger_matches),
            "process_name": process_name,
            "process_names": [process_name] if process_name else [],
            "pid": str(window.get("pid", "") or ""),
            "hwnd": str(window.get("hwnd", "") or ""),
            "window_title": title,
            "exe_path": str(window.get("exe_path", "") or ""),
            "confidence": self._confidence_for(app_hint, process_name, title),
            "source": self._sources("window_title", "process_name", ledger_matches),
            "can_soft_close": True,
            "can_force_close": False,
            "needs_user_choice": False,
            "reason": "",
        }

    def _candidate_from_process(
        self,
        process: dict[str, Any],
        app_hint: str,
        ledger_matches: list[dict[str, Any]],
    ) -> dict[str, Any]:
        process_name = str(process.get("process_name", "") or "").strip().lower()
        return {
            "candidate_id": f"app_candidate_{uuid4().hex[:8]}",
            "label": self._label_for(process_name, "", ledger_matches),
            "target_type": self._target_type_for(process_name, ""),
            "app_id": self._app_id_for(process_name, ledger_matches),
            "app_kind": self._app_kind_for(process_name, ledger_matches),
            "process_name": process_name,
            "process_names": [process_name] if process_name else [],
            "pid": str(process.get("pid", "") or ""),
            "hwnd": "",
            "window_title": "",
            "exe_path": str(process.get("exe_path", "") or ""),
            "confidence": "medium" if self._matches_hint(app_hint, process_name, "") else "low",
            "source": self._sources("process_name", "", ledger_matches),
            "can_soft_close": bool(process_name),
            "can_force_close": False,
            "needs_user_choice": False,
            "reason": "background_process_no_visible_window",
        }

    def _candidate_from_ledger(self, item: dict[str, Any]) -> dict[str, Any]:
        title = str(item.get("title", "") or item.get("app_id", "") or "Unknown app")
        exe_path = str(item.get("exe_path", "") or item.get("launch_target_raw", "") or "")
        process_name = Path(exe_path).name.lower() if exe_path.lower().endswith(".exe") else ""
        return {
            "candidate_id": f"app_candidate_{uuid4().hex[:8]}",
            "label": title,
            "target_type": "unknown_app",
            "app_id": str(item.get("app_id", "") or ""),
            "app_kind": str(item.get("app_kind", "") or ""),
            "process_name": process_name,
            "process_names": [process_name] if process_name else [],
            "pid": "",
            "hwnd": "",
            "window_title": "",
            "exe_path": exe_path,
            "confidence": "low",
            "source": ["software_ledger"],
            "can_soft_close": bool(process_name),
            "can_force_close": False,
            "needs_user_choice": False,
            "reason": "ledger_only_runtime_unresolved",
        }

    def _visible_windows(self) -> list[dict[str, Any]]:
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
                process_name = self._process_name_for_pid(int(pid.value or 0)).lower()
                windows.append({
                    "hwnd": str(int(hwnd or 0)),
                    "pid": str(int(pid.value or 0)),
                    "process_name": process_name,
                    "window_title": title,
                    "exe_path": self._process_path_for_pid(int(pid.value or 0)),
                })
            except Exception:
                return True
            return True

        try:
            user32.EnumWindows(enum_proc_type(callback), None)
        except Exception:
            return []
        return windows

    def _process_matches(self, app_hint: str, ledger_matches: list[dict[str, Any]]) -> list[dict[str, Any]]:
        process_names = set()
        for item in ledger_matches:
            for key in ("exe_path", "launch_target_raw"):
                value = str(item.get(key, "") or "")
                if value.lower().endswith(".exe"):
                    process_names.add(Path(value).name.lower())
        normalized_hint = app_hint.lower()
        if "steam" in normalized_hint:
            process_names.add("steam.exe")
        if "code" in normalized_hint or "vscode" in normalized_hint or "visual studio code" in normalized_hint:
            process_names.add("code.exe")
        if "browser" in normalized_hint or "浏览器" in normalized_hint:
            process_names.update({"msedge.exe", "chrome.exe", "firefox.exe"})
        if not process_names:
            return []

        results: list[dict[str, Any]] = []
        script = "Get-Process | Select-Object ProcessName,Id,Path | ConvertTo-Json -Compress -Depth 3"
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
        try:
            data = json.loads(str(completed.stdout or "").strip() or "[]")
        except Exception:
            return []
        rows = data if isinstance(data, list) else [data]
        for row in rows:
            if not isinstance(row, dict):
                continue
            name = str(row.get("ProcessName", "") or "").strip()
            process_name = f"{name}.exe".lower() if name and not name.lower().endswith(".exe") else name.lower()
            if process_name in process_names:
                results.append({
                    "process_name": process_name,
                    "pid": str(row.get("Id", "") or ""),
                    "exe_path": str(row.get("Path", "") or ""),
                })
        return results

    def _software_ledger_matches(self, app_hint: str) -> list[dict[str, Any]]:
        try:
            from services.desktop.qin.heibingtai.software_capability_index import SoftwareCapabilityIndex

            index = SoftwareCapabilityIndex(self.project_root).build_index()
        except Exception:
            return []
        tokens = self._tokens(app_hint)
        matches: list[dict[str, Any]] = []
        for item in index.values():
            haystack = " ".join(
                str(item.get(key, "") or "")
                for key in ("app_id", "app_kind", "title", "exe_path", "launch_target_raw")
            ).lower()
            if tokens and not any(token in haystack for token in tokens):
                continue
            matches.append(dict(item))
        return matches

    def _dedupe_and_rank(self, candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
        by_key: dict[str, dict[str, Any]] = {}
        for candidate in candidates:
            process_name = str(candidate.get("process_name", "") or "").lower()
            hwnd = str(candidate.get("hwnd", "") or "")
            pid = str(candidate.get("pid", "") or "")
            key = hwnd or pid or process_name or str(candidate.get("label", "") or "")
            if not key or process_name in SYSTEM_PROCESS_NAMES:
                continue
            existing = by_key.get(key)
            if existing is None or self._rank(candidate) > self._rank(existing):
                by_key[key] = candidate
        ranked = sorted(by_key.values(), key=self._rank, reverse=True)
        for index, item in enumerate(ranked, start=1):
            item["candidate_id"] = f"app_candidate_{index:03d}"
            item["display_index"] = index
        if len(ranked) > 1:
            for item in ranked:
                item["needs_user_choice"] = True
        return ranked

    def _resolution_status(self, candidates: list[dict[str, Any]]) -> str:
        if not candidates:
            return "not_found"
        high = [item for item in candidates if str(item.get("confidence", "") or "") == "high"]
        if len(candidates) == 1 and high:
            return "resolved_unique"
        return "ambiguous"

    def _matches_hint(self, app_hint: str, process_name: str, title: str) -> bool:
        tokens = self._tokens(app_hint)
        if not tokens:
            return False
        haystack = f"{process_name} {title}".lower()
        if "steam" in tokens:
            return "steam" in haystack
        if "browser" in tokens or "浏览器" in app_hint:
            return any(name in haystack for name in ("chrome", "msedge", "firefox", "browser", "edge"))
        if "vscode" in tokens or "code" in tokens:
            return "code.exe" in haystack or "visual studio code" in haystack or "vscode" in haystack
        return any(token in haystack for token in tokens)

    def _tokens(self, value: str) -> list[str]:
        text = str(value or "").strip().lower()
        if not text:
            return []
        synonyms = {
            "steam": "steam",
            "浏览器": "browser",
            "browser": "browser",
            "chrome": "chrome",
            "edge": "edge",
            "firefox": "firefox",
            "vscode": "vscode",
            "visual studio code": "vscode",
            "code": "code",
        }
        tokens = [word for word in text.replace("\\", " ").replace("/", " ").replace(".", " ").split() if word]
        for key, normalized in synonyms.items():
            if key in text and normalized not in tokens:
                tokens.append(normalized)
        return tokens

    def _target_type_for(self, process_name: str, title: str) -> str:
        haystack = f"{process_name} {title}".lower()
        if "steam" in haystack and process_name == "steam.exe":
            return "launcher_client"
        if "steam" in haystack:
            return "launcher_child_app"
        if title:
            return "app_window"
        if process_name:
            return "background_process"
        return "unknown_app"

    def _confidence_for(self, app_hint: str, process_name: str, title: str) -> str:
        tokens = self._tokens(app_hint)
        haystack = f"{process_name} {title}".lower()
        if tokens and any(token in haystack for token in tokens):
            return "high"
        if process_name:
            return "medium"
        return "low"

    def _label_for(self, process_name: str, title: str, ledger_matches: list[dict[str, Any]]) -> str:
        if title:
            return title
        for item in ledger_matches:
            title_value = str(item.get("title", "") or "").strip()
            if title_value:
                return title_value
        if process_name:
            return Path(process_name).stem
        return "Unknown app"

    def _app_id_for(self, process_name: str, ledger_matches: list[dict[str, Any]]) -> str:
        for item in ledger_matches:
            app_id = str(item.get("app_id", "") or "")
            if app_id:
                return app_id
        return Path(process_name).stem if process_name else ""

    def _app_kind_for(self, process_name: str, ledger_matches: list[dict[str, Any]]) -> str:
        for item in ledger_matches:
            app_kind = str(item.get("app_kind", "") or "")
            if app_kind:
                return app_kind
        name = process_name.lower()
        if name == "steam.exe":
            return "steam"
        if name in {"chrome.exe", "msedge.exe", "firefox.exe"}:
            return "browser"
        if name == "code.exe":
            return "vscode"
        return ""

    def _sources(self, first: str, second: str, ledger_matches: list[dict[str, Any]]) -> list[str]:
        sources = [first]
        if second:
            sources.append(second)
        if ledger_matches:
            sources.append("software_ledger")
        return list(dict.fromkeys(sources))

    def _rank(self, candidate: dict[str, Any]) -> tuple[int, int, int]:
        confidence_rank = {"high": 3, "medium": 2, "low": 1}.get(str(candidate.get("confidence", "") or ""), 0)
        hwnd_rank = 1 if str(candidate.get("hwnd", "") or "") else 0
        soft_rank = 1 if bool(candidate.get("can_soft_close", False)) else 0
        return confidence_rank, hwnd_rank, soft_rank

    def _message_for_status(self, status: str) -> str:
        if status == "resolved_unique":
            return "Heibingtai resolved one application runtime target."
        if status == "ambiguous":
            return "Heibingtai found multiple possible application targets; user choice is required."
        return "Heibingtai could not find a running application target."

    def _process_name_for_pid(self, pid: int) -> str:
        if int(pid or 0) <= 0:
            return ""
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        try:
            kernel32 = ctypes.windll.kernel32
            handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, int(pid))
        except Exception:
            return ""
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
            try:
                kernel32.CloseHandle(handle)
            except Exception:
                pass

    def _process_path_for_pid(self, pid: int) -> str:
        if int(pid or 0) <= 0:
            return ""
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        try:
            kernel32 = ctypes.windll.kernel32
            handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, int(pid))
        except Exception:
            return ""
        if not handle:
            return ""
        try:
            size = ctypes.c_ulong(32768)
            buffer = ctypes.create_unicode_buffer(size.value)
            if not kernel32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
                return ""
            return str(buffer.value or "")
        except Exception:
            return ""
        finally:
            try:
                kernel32.CloseHandle(handle)
            except Exception:
                pass


def resolve_app_targets(task: dict[str, Any], project_root: str | Path | None = None) -> dict[str, Any]:
    return AppTargetResolver(project_root=project_root).resolve(task)
