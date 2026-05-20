from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from services.desktop.fengshen.plugin_contract_schema import manifest_from_dict


class PluginRegistryService:
    def __init__(self, project_root: str | Path | None = None) -> None:
        self.project_root = Path(project_root or Path(__file__).resolve().parents[3]).expanduser().resolve()
        self.fengshen_dir = self.project_root / "services" / "desktop" / "fengshen"

    def list_reserved_plugins(self) -> list[dict[str, Any]]:
        plugins: list[dict[str, Any]] = []
        for path in sorted(self.fengshen_dir.glob("*.reserved.json")):
            data = self._read_json(path)
            if not data:
                continue
            manifest = manifest_from_dict(data).to_dict()
            manifest["reserved"] = True
            manifest["can_execute"] = False
            plugins.append(manifest)
        return plugins

    def _read_json(self, path: Path) -> dict[str, Any]:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}


def list_reserved_plugins(project_root: str | Path | None = None) -> list[dict[str, Any]]:
    return PluginRegistryService(project_root).list_reserved_plugins()
