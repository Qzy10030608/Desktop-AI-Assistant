from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any
from uuid import uuid4

from services.desktop.desktop_models import now_iso
from services.desktop.qin.hubu.permission_ledger import PermissionLedger

ONCE_PERMISSION_STATE = "once"
CONSUMED_PERMISSION_STATE = "unset"
VALID_ONCE_SOURCE_TYPES = frozenset({"root", "object", "app", "disk"})


@dataclass
class OnceGrantConsumption:
    consume_permission: bool
    consumed: bool
    next_permission_state: str = CONSUMED_PERMISSION_STATE
    reason: str = ""
    source_type: str = ""
    source_key: str = ""
    consumption_id: str = field(default_factory=lambda: f"once_{uuid4().hex}")
    consumed_at: str = field(default_factory=now_iso)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class OnceGrantService:
    """Evaluate and record one-time desktop grants.

    This service only defines V2.5 consumption semantics. The caller still owns
    the actual state update until the UI runtime is fully migrated.
    """

    def __init__(self, ledger: PermissionLedger | None = None) -> None:
        self.ledger = ledger

    def should_consume(
        self,
        *,
        permission_state: str,
        permission_source_type: str,
        permission_source_key: str,
        request_allowed: bool,
    ) -> bool:
        return bool(
            request_allowed
            and str(permission_state or "").strip().lower() == ONCE_PERMISSION_STATE
            and str(permission_source_type or "").strip().lower() in VALID_ONCE_SOURCE_TYPES
            and str(permission_source_key or "").strip()
        )

    def consume(
        self,
        *,
        action: str,
        permission_state: str,
        permission_source_type: str,
        permission_source_key: str,
        request_allowed: bool,
        target_path: str = "",
    ) -> OnceGrantConsumption:
        source_type = str(permission_source_type or "").strip().lower()
        source_key = str(permission_source_key or "").strip()
        should_consume = self.should_consume(
            permission_state=permission_state,
            permission_source_type=source_type,
            permission_source_key=source_key,
            request_allowed=request_allowed,
        )
        result = OnceGrantConsumption(
            consume_permission=should_consume,
            consumed=should_consume,
            reason="once grant consumed" if should_consume else "once grant not consumed",
            source_type=source_type,
            source_key=source_key,
        )
        if self.ledger is not None:
            self.ledger.record(
                event_type="once_consumption",
                action=action,
                permission_state=permission_state,
                permission_source_type=source_type,
                permission_source_key=source_key,
                decision="consumed" if should_consume else "not_consumed",
                reason=result.reason,
                consumed=should_consume,
                target_path=target_path,
                data={"consumption_id": result.consumption_id},
            )
        return result

