from __future__ import annotations

from pathlib import Path

from services.desktop.qin.heibingtai.close_models import CloseTask


class UnregisteredCloseResolver:
    def resolve_path(self, task: CloseTask) -> dict:
        target_path = str(task.target_path or "").strip()
        exists = False
        is_dir = False
        if target_path:
            try:
                path = Path(target_path).expanduser()
                exists = path.exists()
                is_dir = path.is_dir()
            except Exception:
                exists = False
                is_dir = False
        return {
            "target_path": target_path,
            "exists": exists,
            "is_dir": is_dir,
            "target_origin": "unregistered",
        }
