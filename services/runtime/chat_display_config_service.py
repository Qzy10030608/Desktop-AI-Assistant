from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from config import USER_PREFS_DIR  # type: ignore


class ChatDisplayConfigService:
    SCHEMA_VERSION = "chat_display_config_v1"
    DEFAULT_ASSISTANT_DISPLAY_NAME = "AI"

    def __init__(self, path: str | Path | None = None):
        self.path = Path(path) if path is not None else Path(USER_PREFS_DIR) / "chat_display.local.json"

    def load_config(self) -> dict[str, Any]:
        data: dict[str, Any] = {}
        try:
            if self.path.exists():
                loaded = json.loads(self.path.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    data = loaded
        except Exception:
            data = {}

        return {
            "schema_version": self.SCHEMA_VERSION,
            "assistant_display_name": self._normalize_name(
                data.get("assistant_display_name", self.DEFAULT_ASSISTANT_DISPLAY_NAME)
            ),
            "updated_at": str(data.get("updated_at", "") or ""),
        }

    def save_config(self, config: dict[str, Any] | None) -> dict[str, Any]:
        source = config if isinstance(config, dict) else {}
        data = {
            "schema_version": self.SCHEMA_VERSION,
            "assistant_display_name": self._normalize_name(source.get("assistant_display_name", "")),
            "updated_at": datetime.now().isoformat(timespec="seconds"),
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return data

    def get_assistant_display_name(self) -> str:
        return self._normalize_name(self.load_config().get("assistant_display_name", ""))

    def set_assistant_display_name(self, name: str) -> dict[str, Any]:
        return self.save_config({"assistant_display_name": name})

    def assistant_reply_title(self, name: str | None = None) -> str:
        display_name = self._normalize_name(name if name is not None else self.get_assistant_display_name())
        return f"{display_name} 回复"

    def _normalize_name(self, value: Any) -> str:
        name = str(value or "").strip()
        return name or self.DEFAULT_ASSISTANT_DISPLAY_NAME
