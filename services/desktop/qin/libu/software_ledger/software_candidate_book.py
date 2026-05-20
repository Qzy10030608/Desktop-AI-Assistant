from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, List

from services.desktop.software_models import SoftwareRecord


class SoftwareCandidateBook:
    def __init__(self, project_root: str | Path | None = None) -> None:
        self.project_root = Path(project_root or Path(__file__).resolve().parents[5]).expanduser().resolve()
        self.path = self.project_root / "data" / "user_prefs" / "apps.candidates.local.json"

    def read(self) -> List[SoftwareRecord]:
        if not self.path.exists():
            return []
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return []
        apps = data.get("apps", []) if isinstance(data, dict) else []
        result: List[SoftwareRecord] = []
        for item in apps or []:
            if not isinstance(item, dict):
                continue
            try:
                result.append(SoftwareRecord.from_dict(item))
            except Exception:
                continue
        return result

    def write(self, records: Iterable[SoftwareRecord]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"apps": [record.to_dict() for record in records]}
        self.path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
