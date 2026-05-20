from __future__ import annotations

from pathlib import Path
from typing import Any


class QuarantineStore:
    def __init__(self, project_root: str | Path | None = None) -> None:
        self.project_root = Path(project_root or Path(__file__).resolve().parents[4]).expanduser().resolve()
        self.quarantine_dir = self.project_root / "data" / "runtime" / "desktop" / "shaofu" / "quarantine"

    def reserve_path(
        self,
        material_id: str,
        *,
        run_backend: str = "",
        run_id: str = "",
        object_name: str = "",
    ) -> str:
        self.quarantine_dir.mkdir(parents=True, exist_ok=True)
        backend = str(run_backend or "").strip().lower()
        run = str(run_id or "").strip()
        name = self._safe_name(object_name)
        if backend in {"host", "vm"} and run and name:
            return str(self.quarantine_dir / backend / run / str(material_id or "").strip() / name)
        return str(self.quarantine_dir / material_id)

    def describe(self) -> dict[str, Any]:
        self.quarantine_dir.mkdir(parents=True, exist_ok=True)
        return {"quarantine_dir": str(self.quarantine_dir)}

    def _safe_name(self, value: str) -> str:
        text = str(value or "").strip()
        if not text:
            return ""
        for ch in '<>:"/\\|?*':
            text = text.replace(ch, "_")
        return text.strip(" .")
