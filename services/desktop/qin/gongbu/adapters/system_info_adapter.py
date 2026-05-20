from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from bootstrap.hundun.path import collect_machine_paths


class SystemInfoAdapter:
    """Readonly system info adapter for Qin V1."""

    def __init__(self, project_root: str | Path | None = None) -> None:
        self.project_root = project_root

    def get_current_time(self) -> str:
        return datetime.now().strftime("%H:%M:%S")

    def get_current_date(self) -> str:
        return datetime.now().strftime("%Y-%m-%d")

    def get_basic_paths(self) -> Dict[str, str]:
        machine_paths = collect_machine_paths(self.project_root)
        return {
            "project_root": machine_paths["PROJECT_ROOT"],
            "user_home": machine_paths["USER_HOME"],
            "documents": machine_paths["DOCUMENTS"],
            "downloads": machine_paths["DOWNLOADS"],
            "desktop": machine_paths["DESKTOP"],
            "appdata": machine_paths["APPDATA"],
            "localappdata": machine_paths["LOCALAPPDATA"],
            "programfiles": machine_paths["PROGRAMFILES"],
            "programfiles_x86": machine_paths["PROGRAMFILES_X86"],
        }

    def snapshot(self) -> Dict[str, Any]:
        return {
            "current_time": self.get_current_time(),
            "current_date": self.get_current_date(),
            "paths": self.get_basic_paths(),
        }

    def execute(self, task: dict) -> dict:
        action = str((task or {}).get("action", "")).strip()
        if action != "system_info.read_datetime":
            return {
                "ok": False,
                "message": f"不支持的动作: {action}",
                "data": {},
            }
        return {
            "ok": True,
            "message": "已读取当前时间与日期",
            "data": self.snapshot(),
        }
