from __future__ import annotations

import traceback
from typing import Any

from PySide6.QtCore import QObject, Signal, Slot

from services.desktop.qin.gongbu.adapters.vm_adapter import get_default_vm_adapter


class VmFilesRefreshWorker(QObject):
    finished = Signal(object)
    failed = Signal(str)

    def __init__(
        self,
        *,
        root_id: str = "vm_drive_c",
        relative_path: str = "",
        scan_id: int = 0,
        reason: str = "manual_file_rescan",
        refresh_roots: bool = True,
    ) -> None:
        super().__init__()
        self.root_id = str(root_id or "vm_drive_c").strip() or "vm_drive_c"
        self.relative_path = str(relative_path or "").strip()
        self.scan_id = int(scan_id or 0)
        self.reason = str(reason or "manual_file_rescan").strip() or "manual_file_rescan"
        self.refresh_roots = bool(refresh_roots)

    @Slot()
    def run(self) -> None:
        try:
            adapter = get_default_vm_adapter()

            health: dict[str, Any] = adapter.health_check()
            if not bool(health.get("ok", False)):
                self.finished.emit({
                    "ok": False,
                    "scan_id": self.scan_id,
                    "reason": self.reason,
                    "root_id": self.root_id,
                    "relative_path": self.relative_path,
                    "health": health,
                    "roots": None,
                    "files": None,
                    "error": str(health.get("error", health.get("message", "VM health check failed"))),
                    "stage": "health_failed",
                })
                return

            roots: dict[str, Any] | None = None
            if self.refresh_roots:
                roots = adapter.list_file_roots()
                if not bool(roots.get("ok", False)):
                    self.finished.emit({
                        "ok": False,
                        "scan_id": self.scan_id,
                        "reason": self.reason,
                        "root_id": self.root_id,
                        "relative_path": self.relative_path,
                        "health": health,
                        "roots": roots,
                        "files": None,
                        "error": str(roots.get("error", roots.get("message", "VM file roots failed"))),
                        "stage": "roots_failed",
                    })
                    return

            files: dict[str, Any] = adapter.list_files(self.root_id, self.relative_path)

            self.finished.emit({
                "ok": bool(files.get("ok", False)),
                "scan_id": self.scan_id,
                "reason": self.reason,
                "root_id": self.root_id,
                "relative_path": self.relative_path,
                "health": health,
                "roots": roots,
                "files": files,
                "error": str(files.get("error", files.get("message", "")) or ""),
                "stage": "completed" if bool(files.get("ok", False)) else "files_failed",
            })

        except Exception:
            self.failed.emit(traceback.format_exc())
