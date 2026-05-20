from __future__ import annotations

import ctypes
import time
from pathlib import Path

from services.desktop.qin.heibingtai.document_adapters.document_adapter_result import adapter_error, adapter_ok


class NotepadDocumentAdapter:
    strategy = "wm_close_notepad_owned_pid"
    level = "registered_file_owned_notepad"
    resolved_strategy = "notepad_resolved_hwnd_wm_close"
    resolved_level = "resolved_file_notepad_window_title"

    def __init__(self, *, host_adapter=None) -> None:
        self.host_adapter = host_adapter

    def close(self, task, session: dict) -> dict:
        if self._is_resolved_candidate(session):
            return self._close_resolved_candidate(task, session)
        if self.host_adapter is None:
            return adapter_error(
                task,
                session,
                adapter="notepad",
                strategy=self.strategy,
                level=self.level,
                error="notepad_host_adapter_missing",
                message="Notepad close requires Host adapter.",
            )
        target_path = str(session.get("target_path", getattr(task, "target_path", "")) or "")
        arguments = dict(getattr(task, "arguments", {}) or {})
        arguments["open_session_owned"] = True
        for key in (
            "session_id",
            "open_method",
            "process_name",
            "pid",
            "hwnd",
            "window_title",
            "close_strategy",
            "run_id",
            "run_backend",
        ):
            value = session.get(key, "")
            if value not in (None, ""):
                arguments[key] = value
        arguments.update({
            "target_path": target_path,
            "target_type": str(session.get("target_type", "file") or "file"),
            "close_scope": str(getattr(task, "close_scope", "") or "current"),
            "heibingtai_enabled": True,
            "target_origin": "registered",
            "close_level": self.level,
            "app_kind": str(session.get("app_kind", "notepad") or "notepad"),
        })
        return self.host_adapter.execute({
            "action": "file.close",
            "adapter_id": "host",
            "execution_backend": "host",
            "target_path": target_path,
            "target_type": str(session.get("target_type", "file") or "file"),
            "arguments": arguments,
        })

    def _close_resolved_candidate(self, task, session: dict) -> dict:
        if str(session.get("app_kind", "") or "").strip().lower() != "notepad":
            return adapter_error(
                task,
                session,
                adapter="notepad",
                strategy=self.resolved_strategy,
                level=self.resolved_level,
                error="resolved_candidate_app_mismatch",
                message="Resolved candidate is not a Notepad file view.",
            )
        hwnd_text = str(session.get("hwnd", "") or "").strip()
        try:
            hwnd = int(hwnd_text)
        except Exception:
            hwnd = 0
        if hwnd <= 0:
            return adapter_error(
                task,
                session,
                adapter="notepad",
                strategy=self.resolved_strategy,
                level=self.resolved_level,
                error="window_not_found",
                message="Resolved Notepad candidate does not have a valid hwnd.",
            )
        title = str(session.get("window_title", "") or "")
        if not self._title_matches_target(title, task, session):
            return adapter_error(
                task,
                session,
                adapter="notepad",
                strategy=self.resolved_strategy,
                level=self.resolved_level,
                error="notepad_window_title_not_target",
                message="Resolved Notepad window title does not match the requested target.",
                extra={"window_title": title, "hwnd": str(hwnd)},
            )
        if not self._post_wm_close(hwnd):
            return adapter_error(
                task,
                session,
                adapter="notepad",
                strategy=self.resolved_strategy,
                level=self.resolved_level,
                error="wm_close_failed",
                message="Failed to send WM_CLOSE to resolved Notepad window.",
                extra={"window_title": title, "hwnd": str(hwnd)},
            )
        time.sleep(0.8)
        if self._is_window(hwnd):
            return adapter_error(
                task,
                session,
                adapter="notepad",
                strategy=self.resolved_strategy,
                level=self.resolved_level,
                error="needs_user_save_confirmation",
                message="Notepad appears to be waiting for user save confirmation.",
                extra={"window_title": title, "hwnd": str(hwnd)},
            )
        return adapter_ok(
            task,
            session,
            adapter="notepad",
            strategy=self.resolved_strategy,
            level=self.resolved_level,
            message="Resolved Notepad window close requested.",
            extra={"window_title": title, "hwnd": str(hwnd)},
        )

    def _is_resolved_candidate(self, session: dict) -> bool:
        return (
            str(session.get("material_type", "") or "") == "resolved_runtime_candidate"
            or str(session.get("target_origin", "") or "") == "resolved_runtime_candidate"
        )

    def _title_matches_target(self, title: str, task, session: dict) -> bool:
        normalized_title = str(title or "").strip().lower()
        if not normalized_title:
            return False
        target_path = str(session.get("target_path", getattr(task, "target_path", "")) or "")
        target_name = str(session.get("target_name", getattr(task, "target_name", "")) or "")
        terms = []
        if target_path:
            path = Path(target_path)
            terms.extend([path.name, path.stem])
        if target_name:
            terms.append(target_name)
        return any(str(term or "").strip().lower() in normalized_title for term in terms if str(term or "").strip())

    def _post_wm_close(self, hwnd: int) -> bool:
        try:
            return bool(ctypes.windll.user32.PostMessageW(int(hwnd), 0x0010, 0, 0))
        except Exception:
            return False

    def _is_window(self, hwnd: int) -> bool:
        try:
            return bool(ctypes.windll.user32.IsWindow(int(hwnd)))
        except Exception:
            return False
