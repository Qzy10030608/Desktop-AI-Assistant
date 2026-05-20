from __future__ import annotations

from pathlib import Path
from typing import Any


class BackupStore:
    def __init__(self, project_root: str | Path | None = None) -> None:
        self.project_root = Path(project_root or Path(__file__).resolve().parents[4]).expanduser().resolve()
        self.backup_dir = self.project_root / "data" / "runtime" / "desktop" / "shaofu" / "backups"

    def reserve_path(self, material_id: str, suffix: str = ".bak") -> str:
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        return str(self.backup_dir / f"{material_id}{suffix}")

    def describe(self) -> dict[str, Any]:
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        return {"backup_dir": str(self.backup_dir)}
