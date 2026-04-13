import json
from pathlib import Path
from typing import Dict

from config import BASE_DIR # type: ignore


class TemporaryStyleService:
    def __init__(self):
        self.base_dir = Path(BASE_DIR)
        self.runtime_dir = self.base_dir / "data" / "runtime"
        self.state_file = self.runtime_dir / "temp_style_state.json"

        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        self._ensure_state_file()

    def _ensure_state_file(self):
        if not self.state_file.exists():
            self.clear()

    def _read_json(self) -> Dict:
        try:
            return json.loads(self.state_file.read_text(encoding="utf-8"))
        except Exception:
            return {
                "enabled": False,
                "scope": "next_1_turn",
                "remaining_turns": 0,
                "tone_hint": "",
                "length_hint": "",
                "catchphrase_boost": False,
                "notes": ""
            }

    def _write_json(self, data: Dict):
        self.state_file.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

    def get_state(self) -> Dict:
        return self._read_json()

    def set_state(
        self,
        scope: str = "next_1_turn",
        remaining_turns: int = 1,
        tone_hint: str = "",
        length_hint: str = "",
        catchphrase_boost: bool = False,
        notes: str = ""
    ):
        data = {
            "enabled": True,
            "scope": scope,
            "remaining_turns": remaining_turns,
            "tone_hint": tone_hint,
            "length_hint": length_hint,
            "catchphrase_boost": catchphrase_boost,
            "notes": notes
        }
        self._write_json(data)

    def clear(self):
        self._write_json({
            "enabled": False,
            "scope": "next_1_turn",
            "remaining_turns": 0,
            "tone_hint": "",
            "length_hint": "",
            "catchphrase_boost": False,
            "notes": ""
        })

    def consume_once(self):
        data = self._read_json()
        if not data.get("enabled", False):
            return

        remaining = int(data.get("remaining_turns", 0))
        remaining -= 1

        if remaining <= 0:
            self.clear()
            return

        data["remaining_turns"] = remaining
        self._write_json(data)