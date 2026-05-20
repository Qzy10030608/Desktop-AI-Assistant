from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List


class LocalRegistryService:
    """Unified read entry for desktop local registry files."""

    def __init__(self, project_root: str | Path | None = None) -> None:
        self.project_root = Path(project_root or Path(__file__).resolve().parents[4]).expanduser().resolve()
        self.user_prefs_dir = self.project_root / "data" / "user_prefs"

    def _path(self, name: str) -> Path:
        mapping = {
            "roots": self.user_prefs_dir / "roots.local.json",
            "apps": self.user_prefs_dir / "apps.local.json",
            "apps_candidates": self.user_prefs_dir / "apps.candidates.local.json",
        }
        return mapping[name]

    def _read_json(self, path: Path, default: Dict[str, Any]) -> Dict[str, Any]:
        if not path.exists():
            return default
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return default
        return data if isinstance(data, dict) else default

    def read_roots_local(self) -> List[Dict[str, Any]]:
        roots = self._read_json(self._path("roots"), {"roots": []}).get("roots", []) or []
        return [item for item in roots if isinstance(item, dict)]

    def read_apps_local(self) -> List[Dict[str, Any]]:
        apps = self._read_json(self._path("apps"), {"apps": []}).get("apps", []) or []
        return [item for item in apps if isinstance(item, dict)]

    def read_apps_candidates_local(self) -> List[Dict[str, Any]]:
        apps = self._read_json(self._path("apps_candidates"), {"apps": []}).get("apps", []) or []
        return [item for item in apps if isinstance(item, dict)]

    def read_bundle(self) -> Dict[str, Any]:
        roots = self.read_roots_local()
        apps = self.read_apps_local()
        candidates = self.read_apps_candidates_local()
        return {
            "roots": roots,
            "apps": apps,
            "apps_candidates": candidates,
            "root_count": len(roots),
            "app_count": len(apps),
            "candidate_count": len(candidates),
        }
