from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class FileViewCacheService:
    def __init__(self, project_root: Path | str | None = None) -> None:
        self.project_root = Path(project_root or Path.cwd()).expanduser().resolve(strict=False)
        self.base_dir = self.project_root / "data" / "runtime" / "desktop" / "file_view_cache"
        self.host_dir = self.base_dir / "host"
        self.vm_dir = self.base_dir / "vm"

    def read_host_drives(self) -> dict:
        return self._read_json(self.host_dir / "drives.json", self.empty_state(root_path="", source="host_cache"))

    def write_host_drives(self, state: dict) -> dict:
        payload = dict(state or {})
        payload.setdefault("backend", "host")
        payload.setdefault("source", "host_cache")
        self._write_json(self.host_dir / "drives.json", payload)
        return payload

    def read_host_path_cache(self, root_path: str) -> dict:
        path = self._host_cache_path(root_path)
        fallback = self.empty_state(root_path=root_path, source="host_cache")
        return self._read_json(path, fallback)

    def write_host_path_cache(self, root_path: str, state: dict) -> dict:
        payload = dict(state or {})
        payload.setdefault("schema_version", "desktop_file_view_cache_v1")
        payload.setdefault("ok", True)
        payload["backend"] = "host"
        payload.setdefault("source", "host_scan")
        payload["root_path"] = str(payload.get("root_path") or root_path or "")
        payload["current_path"] = str(payload.get("current_path") or payload.get("root_path") or root_path or "")
        payload["path_hash"] = self.path_cache_key("host", payload["current_path"]).split("::", 1)[-1]
        payload.setdefault("cache_status", "ready")
        payload.setdefault("scanned_at", datetime.now(timezone.utc).isoformat())
        payload.setdefault("rows", [])
        payload["entries_count"] = len(payload["rows"]) if isinstance(payload.get("rows"), list) else 0
        self._write_json(self._host_cache_path(payload["current_path"]), payload)
        return payload

    def clear_host_path_cache(self, root_path: str) -> None:
        path = self._host_cache_path(root_path)
        try:
            path.unlink()
        except FileNotFoundError:
            return
        except Exception:
            return

    def path_cache_key(self, backend: str, path: str) -> str:
        backend_text = str(backend or "host").strip().lower() or "host"
        path_text = self._normalize_path(path)
        digest = hashlib.sha256(f"{backend_text}:{path_text}".encode("utf-8", errors="ignore")).hexdigest()
        return f"{backend_text}::{digest}"

    def empty_state(self, *, root_path: str, source: str = "empty", message: str = "") -> dict:
        root_text = str(root_path or "").strip()
        return {
            "ok": True,
            "backend": "host",
            "source": source,
            "trigger_source": "",
            "request_id": "",
            "root_path": root_text,
            "current_path": root_text,
            "path_hash": self.path_cache_key("host", root_text).split("::", 1)[-1] if root_text else "",
            "scanned_at": "",
            "cache_status": "empty",
            "entries_count": 0,
            "truncated": False,
            "errors": [],
            "message": message,
            "rows": [],
        }

    def _host_cache_path(self, root_path: str) -> Path:
        cache_key = self.path_cache_key("host", root_path).split("::", 1)[-1]
        return self.host_dir / f"cache_{cache_key}.json"

    def _normalize_path(self, path: str) -> str:
        text = str(path or "").strip().replace("/", "\\")
        try:
            text = str(Path(text).expanduser().resolve(strict=False))
        except Exception:
            pass
        return text.rstrip("\\").lower()

    def _read_json(self, path: Path, fallback: dict) -> dict:
        try:
            if not path.exists():
                return dict(fallback)
            data = json.loads(path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else dict(fallback)
        except Exception:
            return dict(fallback)

    def _write_json(self, path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
