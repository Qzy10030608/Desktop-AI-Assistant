from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any
from uuid import uuid4

from services.desktop.desktop_models import now_iso


@dataclass
class SessionGrant:
    subject_type: str
    subject_key: str
    action: str
    permission_state: str
    session_id: str = ""
    grant_id: str = field(default_factory=lambda: f"session_grant_{uuid4().hex}")
    created_at: str = field(default_factory=now_iso)
    active: bool = True
    data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class SessionGrantService:
    """In-memory V2.5 session grant registry.

    Persistent session authorization can be added later without changing the
    caller-facing shape.
    """

    def __init__(self) -> None:
        self._grants: dict[str, SessionGrant] = {}

    def create_grant(
        self,
        *,
        subject_type: str,
        subject_key: str,
        action: str,
        permission_state: str,
        session_id: str = "",
        data: dict[str, Any] | None = None,
    ) -> SessionGrant:
        grant = SessionGrant(
            subject_type=str(subject_type or "").strip().lower(),
            subject_key=str(subject_key or "").strip(),
            action=str(action or "").strip().lower(),
            permission_state=str(permission_state or "").strip().lower(),
            session_id=str(session_id or "").strip(),
            data=data or {},
        )
        self._grants[grant.grant_id] = grant
        return grant

    def revoke(self, grant_id: str) -> bool:
        grant = self._grants.get(str(grant_id or "").strip())
        if grant is None:
            return False
        grant.active = False
        return True

    def allows(self, *, subject_type: str, subject_key: str, action: str) -> bool:
        normalized_type = str(subject_type or "").strip().lower()
        normalized_key = str(subject_key or "").strip()
        normalized_action = str(action or "").strip().lower()
        return any(
            grant.active
            and grant.subject_type == normalized_type
            and grant.subject_key == normalized_key
            and grant.action == normalized_action
            and grant.permission_state in {"allow", "once"}
            for grant in self._grants.values()
        )

    def list_active(self) -> list[dict[str, Any]]:
        return [grant.to_dict() for grant in self._grants.values() if grant.active]

