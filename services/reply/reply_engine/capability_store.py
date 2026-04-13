from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Any

from config import RUNTIME_DIR  # type: ignore


class CapabilityStore:
    def __init__(self):
        self.runtime_dir = Path(RUNTIME_DIR)
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        self.file_path = self.runtime_dir / "model_capabilities.json"
        self._ensure_file()

    def _ensure_file(self):
        if self.file_path.exists():
            return
        self.file_path.write_text("{}", encoding="utf-8")

    def _read_json(self) -> Dict[str, Any]:
        try:
            return json.loads(self.file_path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _write_json(self, data: Dict[str, Any]):
        self.file_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def get(self, model_key: str) -> Dict[str, Any]:
        data = self._read_json()
        item = data.get(model_key, {})
        return item if isinstance(item, dict) else {}

    def set(self, model_key: str, capability: Dict[str, Any]):
        data = self._read_json()
        data[model_key] = capability or {}
        self._write_json(data)

    def merge(self, model_key: str, patch: Dict[str, Any]):
        current = self.get(model_key)
        current.update(patch or {})
        self.set(model_key, current)