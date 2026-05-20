from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from PySide6.QtCore import QObject, Signal


class HostFilesRefreshWorker(QObject):
    """
    Host 文件扫描 Worker。

    设计原则：
    - 只扫描当前目录的一层文件/文件夹元信息；
    - 不复制文件；
    - 不打开文件；
    - 不修改权限；
    - 不直接操作 UI；
    - 通过 progress / finished / failed 信号把结果交回 controller；
    - scan_id 用于避免旧扫描结果覆盖新扫描结果。
    """

    progress = Signal(dict)
    finished = Signal(dict)
    failed = Signal(dict)

    def __init__(
        self,
        *,
        root_path: str,
        max_entries: int = 2000,
        recursive: bool = False,
        trigger_source: str = "user",
        request_id: str = "",
        scan_id: int = 0,
    ) -> None:
        super().__init__()

        self.root_path = str(root_path or "").strip()
        self.max_entries = max(1, int(max_entries or 2000))
        self.recursive = bool(recursive)
        self.trigger_source = str(trigger_source or "user").strip().lower() or "user"
        self.request_id = str(request_id or "").strip()
        self.scan_id = int(scan_id or 0)

    def _base_payload(self) -> dict:
        return {
            "backend": "host",
            "source": "host_scan",
            "trigger_source": self.trigger_source,
            "request_id": self.request_id,
            "scan_id": self.scan_id,
        }

    def _emit_failed(
        self,
        *,
        root_path: str,
        current_path: str,
        error: str,
        message: str,
    ) -> None:
        payload = {
            **self._base_payload(),
            "ok": False,
            "root_path": str(root_path or ""),
            "current_path": str(current_path or root_path or ""),
            "error": str(error or ""),
            "message": str(message or error or "Host 文件扫描失败。"),
        }
        self.failed.emit(payload)

    def run(self) -> None:
        try:
            root = Path(self.root_path).expanduser().resolve(strict=False)

            if not root.exists():
                self._emit_failed(
                    root_path=self.root_path,
                    current_path=self.root_path,
                    error="path_not_found",
                    message="目标路径不存在。",
                )
                return

            if not root.is_dir():
                self._emit_failed(
                    root_path=str(root),
                    current_path=str(root),
                    error="path_not_directory",
                    message="目标路径不是目录。",
                )
                return

            rows: list[dict] = []
            errors: list[dict] = []
            truncated = False

            iterator = root.rglob("*") if self.recursive else root.iterdir()

            for index, child in enumerate(iterator, start=1):
                if index > self.max_entries:
                    truncated = True
                    break

                try:
                    stat = child.stat()
                    is_dir = child.is_dir()

                    rows.append(
                        {
                            "name": child.name,
                            "path": str(child),
                            "type": "directory" if is_dir else "file",
                            "object_type": "directory" if is_dir else "file",
                            "is_dir": is_dir,
                            "size": 0 if is_dir else int(stat.st_size),
                            "mtime": datetime.fromtimestamp(
                                stat.st_mtime,
                                timezone.utc,
                            ).isoformat(),
                            "permission_state": "inherited",
                            "permission_label": "继承",
                            "permission_text": "继承",
                            "source": "host_scan",
                            "backend": "host",
                        }
                    )

                except Exception as exc:
                    errors.append(
                        {
                            "path": str(child),
                            "error": str(exc),
                        }
                    )

                if index % 100 == 0:
                    self.progress.emit(
                        {
                            **self._base_payload(),
                            "ok": True,
                            "root_path": str(root),
                            "current_path": str(root),
                            "entries_count": len(rows),
                            "truncated": False,
                        }
                    )

            rows.sort(
                key=lambda item: (
                    not bool(item.get("is_dir", False)),
                    str(item.get("name", "") or "").lower(),
                )
            )

            self.finished.emit(
                {
                    **self._base_payload(),
                    "ok": True,
                    "root_path": str(root),
                    "current_path": str(root),
                    "scanned_at": datetime.now(timezone.utc).isoformat(),
                    "cache_status": "ready",
                    "entries_count": len(rows),
                    "truncated": truncated,
                    "errors": errors,
                    "rows": rows,
                }
            )

        except Exception as exc:
            self._emit_failed(
                root_path=self.root_path,
                current_path=self.root_path,
                error=str(exc),
                message=str(exc),
            )