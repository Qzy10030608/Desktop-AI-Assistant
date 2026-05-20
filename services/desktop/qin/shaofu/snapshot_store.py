from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from services.desktop.desktop_models import now_iso


class SnapshotStore:
    def __init__(self, project_root: str | Path | None = None) -> None:
        self.project_root = Path(project_root or Path(__file__).resolve().parents[4]).expanduser().resolve()
        self.snapshot_dir = self.project_root / "data" / "runtime" / "desktop" / "shaofu" / "snapshots"

    def write_snapshot(self, snapshot_id: str, data: dict[str, Any]) -> str:
        self.snapshot_dir.mkdir(parents=True, exist_ok=True)
        path = self.snapshot_dir / f"{snapshot_id}.json"
        payload = dict(data or {})
        payload.setdefault("created_at", now_iso())
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
        return str(path)

    def describe(self) -> dict[str, Any]:
        self.snapshot_dir.mkdir(parents=True, exist_ok=True)
        return {"snapshot_dir": str(self.snapshot_dir)}
