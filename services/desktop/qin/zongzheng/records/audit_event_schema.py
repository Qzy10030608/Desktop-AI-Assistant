from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any
from uuid import uuid4

from services.desktop.desktop_models import now_iso


@dataclass
class AuditEvent:
    event_type: str
    action: str = ""
    actor: str = "local_user"
    department: str = ""
    backend: str = ""
    execution_backend: str = ""
    target_environment: str = ""
    path_namespace: str = ""
    machine_id: str = ""
    agent_id: str = ""
    target: dict[str, Any] = field(default_factory=dict)
    decision: str = ""
    route_result: str = ""
    adapter_id: str = ""
    reason: str = ""
    review: dict[str, Any] = field(default_factory=dict)
    result: dict[str, Any] = field(default_factory=dict)
    checkpoint: dict[str, Any] = field(default_factory=dict)
    material: dict[str, Any] = field(default_factory=dict)
    data: dict[str, Any] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict)
    event_id: str = field(default_factory=lambda: f"audit_{uuid4().hex}")
    created_at: str = field(default_factory=now_iso)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def normalize_event(event: AuditEvent | dict[str, Any]) -> dict[str, Any]:
    if isinstance(event, AuditEvent):
        return event.to_dict()
    payload = dict(event or {})
    payload.setdefault("event_id", f"audit_{uuid4().hex}")
    payload.setdefault("created_at", now_iso())
    payload.setdefault("actor", "local_user")
    payload.setdefault("event_type", "desktop_event")
    for key in ("target", "review", "result", "checkpoint", "material", "data", "raw"):
        if not isinstance(payload.get(key), dict):
            payload[key] = {}
    for key in (
        "action", "department", "backend", "execution_backend", "target_environment",
        "path_namespace", "machine_id", "agent_id", "decision", "route_result",
        "adapter_id", "reason",
    ):
        payload[key] = str(payload.get(key, "") or "")
    return payload


def make_audit_event(**kwargs: Any) -> AuditEvent:
    fields = AuditEvent.__dataclass_fields__
    return AuditEvent(**{key: value for key, value in kwargs.items() if key in fields})
