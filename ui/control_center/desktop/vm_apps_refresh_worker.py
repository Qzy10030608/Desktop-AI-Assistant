from __future__ import annotations

import traceback
from typing import Any

from PySide6.QtCore import QObject, Signal, Slot

from services.desktop.qin.gongbu.adapters.vm_adapter import get_default_vm_adapter


class VmAppsRefreshWorker(QObject):
    finished = Signal(object)
    failed = Signal(str)

    def __init__(self, *, reason: str = "manual_rescan") -> None:
        super().__init__()
        self.reason = str(reason or "manual_rescan").strip() or "manual_rescan"

    @Slot()
    def run(self) -> None:
        try:
            adapter = get_default_vm_adapter()
            health: dict[str, Any] = adapter.health_check()
            if not bool(health.get("ok", False)):
                self.finished.emit({
                    "ok": False,
                    "health": health,
                    "apps": None,
                    "reason": self.reason,
                    "error": str(health.get("error", health.get("message", "VM health check failed"))),
                })
                return

            apps: dict[str, Any] = adapter.list_apps()
            self.finished.emit({
                "ok": bool(apps.get("ok", False)),
                "health": health,
                "apps": apps,
                "reason": self.reason,
                "error": str(apps.get("error", apps.get("message", "")) or ""),
            })
        except Exception:
            self.failed.emit(traceback.format_exc())
