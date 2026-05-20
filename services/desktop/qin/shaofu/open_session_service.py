from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from services.desktop.qin.shaofu.restore_registry import RestoreRegistry
from services.desktop.qin.shaofu.storage_index import StorageIndex


class OpenSessionService:
    """Track Host windows opened by this system so close can stay precise."""

    def __init__(
        self,
        project_root: str | Path | None = None,
        *,
        restore_registry: RestoreRegistry | None = None,
        storage_index: StorageIndex | None = None,
    ) -> None:
        self.project_root = Path(project_root or Path(__file__).resolve().parents[4]).expanduser().resolve()
        self.restore_registry = restore_registry or RestoreRegistry(self.project_root)
        self.storage_index = storage_index or StorageIndex(self.project_root)

    def record_open(self, payload: dict[str, Any]) -> dict[str, Any]:
        data = dict(payload or {})
        session_id = str(data.get("session_id", "") or "").strip() or f"open_session_{uuid4().hex}"
        now = self._now_iso()
        record = {
            "session_id": session_id,
            "material_id": session_id,
            "material_type": "open_session",
            "material_status": "opened",
            "restore_status": "not_required",
            "action": str(data.get("action", "") or ""),
            "target_path": str(data.get("target_path", data.get("path", "")) or ""),
            "target_type": str(data.get("target_type", "") or ""),
            "opened_by": str(data.get("opened_by", "host_windows_adapter") or "host_windows_adapter"),
            "open_method": str(data.get("open_method", "") or ""),
            "app_kind": str(data.get("app_kind", "") or ""),
            "process_name": str(data.get("process_name", "") or ""),
            "pid": str(data.get("pid", "") or ""),
            "hwnd": str(data.get("hwnd", "") or ""),
            "window_title": str(data.get("window_title", "") or ""),
            "title_matched": bool(data.get("title_matched", False)),
            "resolved_pid": str(data.get("resolved_pid", "") or ""),
            "resolved_hwnd": str(data.get("resolved_hwnd", "") or ""),
            "document_adapter": str(data.get("document_adapter", "") or ""),
            "document_adapter_stage": str(data.get("document_adapter_stage", "") or ""),
            "close_action": str(data.get("close_action", "") or ""),
            "close_strategy": str(data.get("close_strategy", "") or ""),
            "close_scope": str(data.get("close_scope", "") or ""),
            "already_open": bool(data.get("already_open", False)),
            "focused_existing": bool(data.get("focused_existing", False)),
            "discovered_by_path": bool(data.get("discovered_by_path", False)),
            "matched_count": data.get("matched_count", 0),
            "status": "opened",
            "opened_at": now,
            "updated_at": now,
            "run_id": str(data.get("run_id", "") or ""),
            "run_backend": str(data.get("run_backend", "host") or "host"),
            "execution_backend": "host",
            "target_environment": "local_host",
            "path_namespace": "host_windows",
            "data": {key: value for key, value in data.items() if key not in {"data"}},
        }
        self._persist(record)
        return record

    def find_session(
        self,
        *,
        session_id: str = "",
        target_path: str = "",
        close_action: str = "",
    ) -> dict[str, Any] | None:
        normalized_session = str(session_id or "").strip()
        normalized_target = self._norm_path(target_path)
        normalized_close = str(close_action or "").strip().lower()
        seen: set[str] = set()
        for item in reversed(self.restore_registry.read_all(include_deleted=True)):
            if str(item.get("material_type", "") or "").strip() != "open_session":
                continue
            item_session_id = str(item.get("session_id", item.get("material_id", "")) or "").strip()
            if normalized_session and item_session_id == normalized_session:
                return item
            if not normalized_target:
                continue
            if item_session_id and item_session_id in seen:
                continue
            if self._norm_path(str(item.get("target_path", "") or "")) != normalized_target:
                continue
            if normalized_close and str(item.get("close_action", "") or "").strip().lower() != normalized_close:
                continue
            if item_session_id:
                seen.add(item_session_id)
            if str(item.get("status", "") or "").strip().lower() == "opened":
                return item
        return None

    def find_sessions_by_path(
        self,
        *,
        target_path: str = "",
        close_action: str = "",
        status: str = "opened",
    ) -> list[dict[str, Any]]:
        normalized_target = self._norm_path(target_path)
        normalized_close = str(close_action or "").strip().lower()
        normalized_status = str(status or "").strip().lower()
        if not normalized_target:
            return []
        seen: set[str] = set()
        sessions: list[dict[str, Any]] = []
        for item in reversed(self.restore_registry.read_all(include_deleted=True)):
            if str(item.get("material_type", "") or "").strip() != "open_session":
                continue
            session_id = str(item.get("session_id", item.get("material_id", "")) or "").strip()
            if session_id and session_id in seen:
                continue
            if self._norm_path(str(item.get("target_path", "") or "")) != normalized_target:
                continue
            if normalized_close and str(item.get("close_action", "") or "").strip().lower() != normalized_close:
                continue
            if session_id:
                seen.add(session_id)
            if normalized_status and str(item.get("status", "") or "").strip().lower() != normalized_status:
                continue
            sessions.append(item)
        return sessions

    def mark_close(self, session: dict[str, Any], result_data: dict[str, Any]) -> dict[str, Any]:
        now = self._now_iso()
        data = result_data if isinstance(result_data, dict) else {}
        error = str(data.get("error", "") or "")
        skipped_errors = {
            "unsupported_precise_tab_close",
            "explorer_active_tab_mismatch",
            "explorer_tab_not_supported",
        }
        status = "closed" if bool(data.get("close_succeeded", False)) else "close_failed"
        if status != "closed" and error in skipped_errors:
            status = "close_skipped"
        update = dict(session or {})
        update.update({
            "status": status,
            "material_status": status,
            "closed_at": now if status == "closed" else "",
            "close_attempted_at": now,
            "updated_at": now,
            "close_strategy": str(data.get("close_strategy", update.get("close_strategy", "")) or ""),
            "app_kind": str(data.get("app_kind", update.get("app_kind", "")) or ""),
            "hwnd": str(data.get("hwnd", update.get("hwnd", "")) or ""),
            "window_title": str(data.get("window_title", update.get("window_title", "")) or ""),
            "document_adapter": str(data.get("document_adapter", update.get("document_adapter", "")) or ""),
            "document_adapter_stage": str(
                data.get("document_adapter_stage", update.get("document_adapter_stage", "")) or ""
            ),
            "error": error,
            "close_error": error if status == "close_skipped" else str(data.get("close_error", "") or ""),
            "data": {
                **(update.get("data", {}) if isinstance(update.get("data"), dict) else {}),
                "close_result": data,
            },
        })
        self._persist(update)
        return update

    def mark_close_for_path(
        self,
        *,
        target_path: str,
        result_data: dict[str, Any],
        close_action: str = "folder.close",
    ) -> list[dict[str, Any]]:
        sessions = self.find_sessions_by_path(
            target_path=target_path,
            close_action=close_action,
            status="opened",
        )
        return [self.mark_close(session, result_data) for session in sessions]

    def record_discovered_close(
        self,
        *,
        target_path: str,
        result_data: dict[str, Any],
        close_action: str = "folder.close",
    ) -> dict[str, Any]:
        data = result_data if isinstance(result_data, dict) else {}
        session = self.record_open({
            "action": str(close_action or "").replace(".close", ".open"),
            "target_path": target_path,
            "target_type": "directory",
            "opened_by": "host_windows_adapter",
            "open_method": "explorer",
            "process_name": "explorer.exe",
            "close_action": close_action,
            "close_strategy": str(data.get("close_strategy", "wm_close_explorer_path") or "wm_close_explorer_path"),
            "close_scope": str(data.get("close_scope", "all_matching_path") or "all_matching_path"),
            "run_id": str(data.get("run_id", "") or ""),
            "run_backend": str(data.get("run_backend", "host") or "host"),
            "discovered_by_path": True,
            "matched_count": data.get("matched_count", 0),
        })
        session["discovered_by_path"] = True
        return self.mark_close(session, data)

    def _persist(self, record: dict[str, Any]) -> None:
        self.restore_registry.append(record)
        self.storage_index.update_material(record)

    def _norm_path(self, value: str) -> str:
        text = str(value or "").strip()
        if not text:
            return ""
        try:
            return str(Path(text).expanduser().resolve(strict=False)).rstrip("\\/").lower()
        except Exception:
            return text.rstrip("\\/").lower()

    def _now_iso(self) -> str:
        return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
