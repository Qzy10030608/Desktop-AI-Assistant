from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from services.desktop.qin.zongzheng.records.audit_event_schema import AuditEvent, make_audit_event, normalize_event


class AuditLedger:
    """Append-only long-term desktop audit ledger owned by Hubu."""

    def __init__(self, project_root: str | Path | None = None) -> None:
        self.project_root = Path(project_root or Path(__file__).resolve().parents[4]).expanduser().resolve()
        self.log_path = self.project_root / "data" / "logs" / "desktop" / "audit.jsonl"

    def append(self, event: AuditEvent | dict[str, Any]) -> dict[str, Any]:
        payload = normalize_event(event)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with self.log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")
        return payload

    def record(self, **kwargs: Any) -> dict[str, Any]:
        return self.append(make_audit_event(**kwargs))

    def read_tail(self, limit: int = 50) -> list[dict[str, Any]]:
        if not self.log_path.exists():
            return []
        lines = self.log_path.read_text(encoding="utf-8").splitlines()
        result: list[dict[str, Any]] = []
        for line in lines[-max(1, int(limit)):]:
            try:
                item = json.loads(line)
            except Exception:
                continue
            if isinstance(item, dict):
                result.append(item)
        return result


DesktopAuditLedger = AuditLedger
