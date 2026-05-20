from __future__ import annotations

import traceback
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, Signal, Slot

from services.desktop.desktop_whitelist_service import DesktopWhitelistService


class SoftwareScanWorker(QObject):
    finished = Signal(object)
    failed = Signal(str)
    progress = Signal(object)
    log = Signal(str)

    def __init__(self, project_root: str | Path, *, scan_profile: str = "quick") -> None:
        super().__init__()
        self.project_root = Path(project_root)
        self.scan_profile = str(scan_profile or "quick").strip().lower()

    @Slot()
    def run(self) -> None:
        try:
            service = DesktopWhitelistService(self.project_root)
            result: Any = service.rescan_candidates(
                progress_callback=self._emit_progress,
                scan_profile=self.scan_profile,
            )
        except Exception:
            self.failed.emit(traceback.format_exc())
            return
        self.finished.emit(result)

    def _emit_progress(self, payload: object) -> None:
        if isinstance(payload, dict):
            self.progress.emit(dict(payload))
            message = str(payload.get("message", "") or "").strip()
            if message:
                self.log.emit(message)
