from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ReplyEnvelope:
    raw_text: str = ""
    thinking_text: str = ""
    final_text: str = ""
    display_text: str = ""
    tts_text: str = ""
    source_type: str = ""
    model_key: str = ""
    strategy_used: str = ""
    confidence: float = 0.0
    needs_repair: bool = False
    debug_notes: str = ""