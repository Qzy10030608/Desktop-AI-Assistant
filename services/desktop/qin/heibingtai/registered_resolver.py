from __future__ import annotations

from services.desktop.qin.heibingtai.close_models import CloseTask


class RegisteredCloseResolver:
    def __init__(self, open_session_service) -> None:
        self.open_session_service = open_session_service

    def find_registered_session(self, task: CloseTask) -> dict | None:
        session = self.open_session_service.find_session(
            session_id=task.session_id,
            target_path=task.target_path,
            close_action=task.action,
        )
        if not isinstance(session, dict):
            return None
        data = session.get("data", {}) if isinstance(session.get("data", {}), dict) else {}
        merged = dict(data)
        merged.update(session)
        return merged
