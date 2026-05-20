from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from services.desktop.desktop_models import now_iso


class DeveloperModeService:
    def __init__(self, project_root: str | Path | None = None) -> None:
        self.project_root = Path(project_root or Path(__file__).resolve().parents[2])
        self.path = self.project_root / "data" / "user_prefs" / "developer.local.json"

    def _default_state(self) -> Dict[str, Any]:
        return {
            "developer_mode_enabled": False,
            "updated_at": "",
        }

    def get_state(self) -> Dict[str, Any]:
        if not self.path.exists():
            return self._default_state()
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return self._default_state()
        if not isinstance(data, dict):
            return self._default_state()
        state = self._default_state()
        state.update({
            "developer_mode_enabled": bool(data.get("developer_mode_enabled", False)),
            "updated_at": str(data.get("updated_at", "") or ""),
        })
        return state

    def is_enabled(self) -> bool:
        return bool(self.get_state().get("developer_mode_enabled", False))

    def set_enabled(self, enabled: bool) -> Dict[str, Any]:
        state = {
            "developer_mode_enabled": bool(enabled),
            "updated_at": now_iso(),
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        return state
