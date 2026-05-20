from __future__ import annotations

import stat
from datetime import datetime
from pathlib import Path
from typing import Any, Dict


class FilesystemReadonlyAdapter:
    """Readonly filesystem adapter for Qin desktop readonly V1."""

    def execute(self, task: dict) -> dict:
        action = str((task or {}).get("action", "")).strip()
        target_path = str((task or {}).get("target_path", "")).strip()

        if action == "filesystem.list_dir":
            return self.list_dir(target_path)
        if action == "filesystem.path_meta":
            return self.get_path_meta(target_path)

        return {
            "ok": False,
            "message": f"不支持的动作: {action}",
            "data": {},
        }

    def list_dir(self, path: str) -> dict:
        normalized = self._normalize_path(path)
        if normalized is None:
            return {
                "ok": False,
                "message": "缺少 target_path",
                "data": {},
            }
        if not normalized.exists():
            return {
                "ok": False,
                "message": f"路径不存在: {normalized}",
                "data": {},
            }
        if not normalized.is_dir():
            return {
                "ok": False,
                "message": f"目标不是目录: {normalized}",
                "data": {},
            }

        try:
            entries = [self._entry_to_dict(item) for item in self._iter_sorted_entries(normalized)]
        except Exception as exc:
            return {
                "ok": False,
                "message": f"列出目录失败: {exc}",
                "data": {},
            }

        return {
            "ok": True,
            "message": f"已列出目录内容: {normalized}",
            "data": {
                "path": str(normalized),
                "exists": True,
                "is_dir": True,
                "entries": entries,
            },
        }

    def get_path_meta(self, path: str) -> dict:
        normalized = self._normalize_path(path)
        if normalized is None:
            return {
                "ok": False,
                "message": "缺少 target_path",
                "data": {},
            }
        if not normalized.exists():
            return {
                "ok": False,
                "message": f"路径不存在: {normalized}",
                "data": {},
            }

        try:
            item_stat = normalized.stat()
        except Exception as exc:
            return {
                "ok": False,
                "message": f"读取路径元信息失败: {exc}",
                "data": {},
            }

        return {
            "ok": True,
            "message": f"已读取路径元信息: {normalized}",
            "data": {
                "path": str(normalized),
                "exists": True,
                "is_dir": normalized.is_dir(),
                "size": 0 if normalized.is_dir() else int(item_stat.st_size),
                "modified_at": self._format_timestamp(item_stat.st_mtime),
                "created_at": self._format_timestamp(item_stat.st_ctime),
                "suffix": normalized.suffix,
                "readonly": self._is_readonly(item_stat.st_mode),
            },
        }

    def _normalize_path(self, path: str) -> Path | None:
        text = str(path or "").strip()
        if not text:
            return None
        return Path(text).expanduser().resolve(strict=False)

    def _iter_sorted_entries(self, directory: Path) -> list[Path]:
        return sorted(
            list(directory.iterdir()),
            key=lambda item: (not item.is_dir(), item.name.lower()),
        )

    def _entry_to_dict(self, path: Path) -> Dict[str, Any]:
        item_stat = path.stat()
        is_dir = path.is_dir()
        return {
            "name": path.name,
            "path": str(path),
            "is_dir": is_dir,
            "size": 0 if is_dir else int(item_stat.st_size),
            "modified_at": self._format_timestamp(item_stat.st_mtime),
            "suffix": path.suffix,
        }

    def _is_readonly(self, mode: int) -> bool:
        return not bool(mode & stat.S_IWRITE)

    def _format_timestamp(self, timestamp: float) -> str:
        return datetime.fromtimestamp(timestamp).isoformat(timespec="seconds")
