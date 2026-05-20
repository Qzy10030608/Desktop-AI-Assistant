from __future__ import annotations

import traceback
from typing import Any

from PySide6.QtCore import QObject, Signal, Slot

from services.desktop.qin.gongbu.adapters.vm_adapter import get_default_vm_adapter


class VmConnectWorker(QObject):
    finished = Signal(object)
    failed = Signal(str)

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
                    "files": None,
                    "error": str(health.get("error", health.get("message", "VM health check failed"))),
                })
                return

            apps: dict[str, Any] = adapter.list_apps()
            files: dict[str, Any] = adapter.list_files()
            self.finished.emit({
                "ok": bool(apps.get("ok", False)),
                "health": health,
                "apps": apps,
                "files": files,
                "error": str(apps.get("error", apps.get("message", ""))),
            })
        except Exception:
            self.failed.emit(traceback.format_exc())

