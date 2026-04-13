from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class StreamReplyState:
    request_id: int
    user_text: str
    output_mode: str

    raw_buffer: str = ""
    latest_visible_text: str = ""
    last_candidate_text: str = ""
    stable_rounds: int = 0

    first_chunk_at: Optional[float] = None
    first_final_at: Optional[float] = None
    last_chunk_at: Optional[float] = None

    displayed: bool = False
    tts_started: bool = False
    message_widget: Any = None

    extra: dict = field(default_factory=dict)

    def append_piece(self, piece: str) -> str:
        now = time.time()
        if self.first_chunk_at is None:
            self.first_chunk_at = now
        self.last_chunk_at = now

        if piece:
            self.raw_buffer += piece
        return self.raw_buffer

    def update_candidate(self, text: str) -> bool:
        candidate = (text or "").strip()
        if not candidate:
            return False

        if candidate == self.last_candidate_text:
            self.stable_rounds += 1
        else:
            self.last_candidate_text = candidate
            self.stable_rounds = 1

        self.latest_visible_text = candidate

        if self.first_final_at is None:
            self.first_final_at = time.time()

        return True

    def is_stable(self, required_rounds: int = 2) -> bool:
        return bool(self.latest_visible_text) and self.stable_rounds >= required_rounds

    def mark_displayed(self, widget: Any = None):
        self.displayed = True
        if widget is not None:
            self.message_widget = widget

    def mark_tts_started(self):
        self.tts_started = True

    def set_widget(self, widget: Any):
        self.message_widget = widget