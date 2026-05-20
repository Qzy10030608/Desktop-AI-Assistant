from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict


class ExplorerAdapter:
    """Minimal explorer adapter that only opens directories."""

    def execute(self, task: dict) -> Dict[str, Any]:
        action = str((task or {}).get("action", "")).strip()
        target_path = str((task or {}).get("target_path", "")).strip()
        if action != "explorer.open_directory":
            return {
                "ok": False,
                "message": f"不支持的动作: {action}",
                "data": {},
            }
        return self.open_directory(target_path)

    def open_directory(self, target_path: str | Path) -> Dict[str, Any]:
        if os.name != "nt":
            return {
                "ok": False,
                "message": "当前环境不是 Windows，无法打开文件资源管理器。",
                "data": {},
            }

        path = Path(target_path).expanduser().resolve(strict=False)
        if not path.exists():
            return {
                "ok": False,
                "message": f"目标目录不存在: {path}",
                "data": {},
            }
        if not path.is_dir():
            return {
                "ok": False,
                "message": f"目标不是目录: {path}",
                "data": {},
            }

        try:
            os.startfile(str(path))
        except Exception as exc:
            return {
                "ok": False,
                "message": f"打开目录失败: {exc}",
                "data": {},
            }

        return {
            "ok": True,
            "message": f"已打开目录: {path}",
            "data": {
                "path": str(path),
                "exists": True,
                "is_dir": True,
            },
        }
