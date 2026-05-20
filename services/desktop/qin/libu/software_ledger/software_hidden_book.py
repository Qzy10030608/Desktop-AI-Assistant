from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, Set


class SoftwareHiddenBook:
    def __init__(self, project_root: str | Path | None = None) -> None:
        self.project_root = Path(project_root or Path(__file__).resolve().parents[5]).expanduser().resolve()
        self.path = self.project_root / "data" / "user_prefs" / "apps.hidden.local.json"

    def read_ids(self) -> Set[str]:
        if not self.path.exists():
            return set()
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return set()
        app_ids = data.get("app_ids", []) if isinstance(data, dict) else []
        return {str(item).strip() for item in app_ids or [] if str(item).strip()}

    def write_ids(self, app_ids: Iterable[str]) -> None:
        cleaned = sorted({str(item).strip() for item in app_ids if str(item).strip()})
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps({"app_ids": cleaned}, ensure_ascii=False, indent=2), encoding="utf-8")
