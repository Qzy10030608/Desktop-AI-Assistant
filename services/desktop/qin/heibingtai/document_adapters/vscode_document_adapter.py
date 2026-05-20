from __future__ import annotations

import ctypes
import time
from pathlib import Path

from services.desktop.qin.heibingtai.document_adapters.document_adapter_result import adapter_error, adapter_ok


class VSCodeDocumentAdapter:
    strategy = "vscode_current_tab_ctrl_w"
    level = "registered_file_vscode_current_tab"

    def __init__(self, *, host_adapter=None) -> None:
        self.host_adapter = host_adapter

    def close(self, task, session: dict) -> dict:
        session_hwnd = str(session.get("hwnd", "") or "").strip()
        if self._is_resolved_candidate(session):
            if str(session.get("app_kind", "") or "").strip().lower() != "vscode":
                return self._extension_or_required(
                    task,
                    session,
                    "resolved_candidate_app_mismatch",
                    {"window_title": str(session.get("window_title", "") or ""), "hwnd": session_hwnd},
                )
            if not session_hwnd:
                return self._extension_or_required(
                    task,
                    session,
                    "vscode_window_not_found",
                    {"window_title": str(session.get("window_title", "") or ""), "hwnd": session_hwnd},
                )
            process_name = str(session.get("process_name", "") or "").strip().lower()
            if process_name and process_name != "code.exe":
                return self._extension_or_required(
                    task,
                    session,
                    "vscode_foreground_not_found",
                    {"window_title": str(session.get("window_title", "") or ""), "hwnd": session_hwnd},
                )
            if not self._title_matches_target(str(session.get("window_title", "") or ""), task, session):
                return self._extension_or_required(
                    task,
                    session,
                    "vscode_current_tab_not_target",
                    {"window_title": str(session.get("window_title", "") or ""), "hwnd": session_hwnd},
                )
            if session_hwnd and not self._focus_window(session_hwnd):
                return self._extension_or_required(
                    task,
                    session,
                    "vscode_foreground_not_found",
                    {"window_title": str(session.get("window_title", "") or ""), "hwnd": session_hwnd},
                )
            time.sleep(0.15)
        info = self._foreground_info()
        if not info:
            return self._extension_or_required(task, session, "vscode_foreground_not_found")
        process_name = str(info.get("process_name", "") or "").strip().lower()
        if process_name != "code.exe":
            return self._extension_or_required(task, session, "vscode_foreground_not_found")
        if session_hwnd and str(info.get("hwnd", "") or "").strip() != session_hwnd:
            return self._extension_or_required(task, session, "vscode_current_tab_not_target")
        title = str(info.get("window_title", "") or "")
        target_path = str(session.get("target_path", getattr(task, "target_path", "")) or "")
        if not self._title_matches_target(title, task, session):
            return self._extension_or_required(task, session, "vscode_current_tab_not_target", {"window_title": title})
        if not self._send_ctrl_w():
            return adapter_error(
                task,
                session,
                adapter="vscode",
                strategy=self.strategy,
                level=self.level,
                error="vscode_ctrl_w_failed",
                message="Failed to send Ctrl+W to VSCode.",
                extra={"window_title": title, "hwnd": str(info.get("hwnd", "") or "")},
            )
        return adapter_ok(
            task,
            session,
            adapter="vscode",
            strategy=self.strategy,
            level=self.level,
            message="VSCode current tab close requested.",
            extra={"window_title": title, "hwnd": str(info.get("hwnd", "") or "")},
        )

    def try_extension_close_by_uri(self, target_path: str) -> dict:
        return {"ok": False, "error": "vscode_extension_adapter_not_available", "target_path": target_path}

    def _extension_or_required(self, task, session: dict, error: str, extra: dict | None = None) -> dict:
        target_path = str(session.get("target_path", getattr(task, "target_path", "")) or "")
        extension = self.try_extension_close_by_uri(target_path)
        if bool(extension.get("ok", False)):
            return extension
        payload = {"extension_error": str(extension.get("error", "") or "vscode_extension_adapter_not_available")}
        if extra:
            payload.update(extra)
        final_error = error if error != "vscode_extension_adapter_not_available" else "vscode_document_adapter_required"
        return adapter_error(
            task,
            session,
            adapter="vscode",
            strategy=self.strategy,
            level=self.level,
            error=final_error,
            message="VSCode document adapter could not safely confirm the active target tab.",
            extra=payload,
        )

    def _foreground_info(self) -> dict:
        if self.host_adapter is not None and hasattr(self.host_adapter, "_get_foreground_window_info"):
            return self.host_adapter._get_foreground_window_info()
        return {}

    def _title_matches_file(self, title: str, target_path: str) -> bool:
        if self.host_adapter is not None and hasattr(self.host_adapter, "_title_matches_file"):
            return bool(self.host_adapter._title_matches_file(title, target_path))
        name = Path(str(target_path or "")).name.lower()
        stem = Path(str(target_path or "")).stem.lower()
        normalized_title = str(title or "").lower()
        return bool((name and name in normalized_title) or (stem and stem in normalized_title))

    def _title_matches_target(self, title: str, task, session: dict) -> bool:
        target_path = str(session.get("target_path", getattr(task, "target_path", "")) or "")
        if target_path and self._title_matches_file(title, target_path):
            return True
        target_name = str(session.get("target_name", getattr(task, "target_name", "")) or "").strip().lower()
        return bool(target_name and target_name in str(title or "").lower())

    def _is_resolved_candidate(self, session: dict) -> bool:
        return (
            str(session.get("material_type", "") or "") == "resolved_runtime_candidate"
            or str(session.get("target_origin", "") or "") == "resolved_runtime_candidate"
        )

    def _focus_window(self, hwnd: str) -> bool:
        if self.host_adapter is not None and hasattr(self.host_adapter, "_focus_window"):
            try:
                return bool(self.host_adapter._focus_window(int(hwnd)))
            except Exception:
                return False
        try:
            user32 = ctypes.windll.user32
            user32.ShowWindow(int(hwnd), 9)
            return bool(user32.SetForegroundWindow(int(hwnd)))
        except Exception:
            return False

    def _send_ctrl_w(self) -> bool:
        try:
            user32 = ctypes.windll.user32
            VK_CONTROL = 0x11
            VK_W = 0x57
            KEYEVENTF_KEYUP = 0x0002
            user32.keybd_event(VK_CONTROL, 0, 0, 0)
            user32.keybd_event(VK_W, 0, 0, 0)
            time.sleep(0.05)
            user32.keybd_event(VK_W, 0, KEYEVENTF_KEYUP, 0)
            user32.keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, 0)
            return True
        except Exception:
            return False
