from __future__ import annotations

import ctypes
import time
from pathlib import Path

from services.desktop.qin.heibingtai.document_adapters.document_adapter_result import adapter_error, adapter_ok


class DefaultAppDocumentAdapter:
    strategy = "wm_close_owned_single_document_window"
    level = "registered_file_single_document_window"
    BLOCKED_PROCESSES = {
        "code.exe",
        "winword.exe",
        "excel.exe",
        "powerpnt.exe",
        "wps.exe",
        "et.exe",
        "wpp.exe",
        "chrome.exe",
        "msedge.exe",
        "explorer.exe",
    }

    def __init__(self, *, host_adapter=None) -> None:
        self.host_adapter = host_adapter

    def close(self, task, session: dict) -> dict:
        process_name = str(session.get("process_name", "") or "").strip().lower()
        if process_name in self.BLOCKED_PROCESSES:
            return adapter_error(
                task,
                session,
                adapter="default_app",
                strategy=self.strategy,
                level=self.level,
                error="unsupported_precise_close",
                message="Default adapter refuses known multi-document applications.",
            )
        try:
            hwnd = int(str(session.get("hwnd", "") or "0"))
        except Exception:
            hwnd = 0
        if hwnd <= 0 or not ctypes.windll.user32.IsWindow(hwnd):
            return adapter_error(
                task,
                session,
                adapter="default_app",
                strategy=self.strategy,
                level=self.level,
                error="window_not_found",
                message="Registered single-document window was not found.",
            )
        title = self._window_title(hwnd)
        target_path = str(session.get("target_path", getattr(task, "target_path", "")) or "")
        if not self._title_matches_file(title, target_path):
            return adapter_error(
                task,
                session,
                adapter="default_app",
                strategy=self.strategy,
                level=self.level,
                error="default_app_window_title_mismatch",
                message="Registered window title no longer matches the target file.",
                extra={"window_title": title},
            )
        if not ctypes.windll.user32.PostMessageW(hwnd, 0x0010, 0, 0):
            return adapter_error(
                task,
                session,
                adapter="default_app",
                strategy=self.strategy,
                level=self.level,
                error="wm_close_failed",
                message="Failed to send WM_CLOSE to single-document window.",
                extra={"window_title": title},
            )
        time.sleep(0.8)
        if ctypes.windll.user32.IsWindow(hwnd):
            return adapter_error(
                task,
                session,
                adapter="default_app",
                strategy=self.strategy,
                level=self.level,
                error="needs_user_save_confirmation",
                message="Window is still open, likely waiting for user save confirmation.",
                extra={"window_title": title},
            )
        return adapter_ok(
            task,
            session,
            adapter="default_app",
            strategy=self.strategy,
            level=self.level,
            message="Single-document window closed with WM_CLOSE.",
            extra={"window_title": title},
        )

    def _window_title(self, hwnd: int) -> str:
        length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
        buffer = ctypes.create_unicode_buffer(length + 1)
        ctypes.windll.user32.GetWindowTextW(hwnd, buffer, length + 1)
        return str(buffer.value or "")

    def _title_matches_file(self, title: str, target_path: str) -> bool:
        if self.host_adapter is not None and hasattr(self.host_adapter, "_title_matches_file"):
            return bool(self.host_adapter._title_matches_file(title, target_path))
        name = Path(str(target_path or "")).name.lower()
        stem = Path(str(target_path or "")).stem.lower()
        normalized_title = str(title or "").lower()
        return bool((name and name in normalized_title) or (stem and stem in normalized_title))
