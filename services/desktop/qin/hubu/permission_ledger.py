from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any
from uuid import uuid4

from services.desktop.desktop_models import now_iso


@dataclass
class PermissionLedgerEntry:
    event_type: str
    action: str = ""
    subject_type: str = ""
    subject_key: str = ""
    permission_state: str = ""
    permission_source_type: str = ""
    permission_source_key: str = ""
    decision: str = ""
    reason: str = ""
    consumed: bool = False
    target_path: str = ""
    data: dict[str, Any] = field(default_factory=dict)
    entry_id: str = field(default_factory=lambda: f"perm_{uuid4().hex}")
    created_at: str = field(default_factory=now_iso)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class PermissionLedger:
    """Append-only permission ledger for V2.5 desktop governance."""

    def __init__(self, project_root: str | Path | None = None) -> None:
        self.project_root = Path(project_root or Path(__file__).resolve().parents[4]).expanduser().resolve()
        self.ledger_path = self.project_root / "data" / "logs" / "desktop" / "permission_ledger.jsonl"

    def append(self, entry: PermissionLedgerEntry) -> dict[str, Any]:
        payload = entry.to_dict()
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
        with self.ledger_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")
        return payload

    def record(
        self,
        *,
        event_type: str,
        action: str = "",
        subject_type: str = "",
        subject_key: str = "",
        permission_state: str = "",
        permission_source_type: str = "",
        permission_source_key: str = "",
        decision: str = "",
        reason: str = "",
        consumed: bool = False,
        target_path: str = "",
        data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self.append(
            PermissionLedgerEntry(
                event_type=event_type,
                action=action,
                subject_type=subject_type,
                subject_key=subject_key,
                permission_state=permission_state,
                permission_source_type=permission_source_type,
                permission_source_key=permission_source_key,
                decision=decision,
                reason=reason,
                consumed=consumed,
                target_path=target_path,
                data=data or {},
            )
        )

    def read_tail(self, limit: int = 50) -> list[dict[str, Any]]:
        if not self.ledger_path.exists():
            return []
        lines = self.ledger_path.read_text(encoding="utf-8").splitlines()
        result: list[dict[str, Any]] = []
        for line in lines[-max(1, int(limit)):]:
            try:
                item = json.loads(line)
            except Exception:
                continue
            if isinstance(item, dict):
                result.append(item)
        return result

