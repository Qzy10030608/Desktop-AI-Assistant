from __future__ import annotations

from typing import Any

from services.desktop.tianting.command_puzzle_builder import build_command_puzzle
from services.desktop.tianting.context_pack_service import build_context_pack
from services.desktop.tianting.desktop_understanding_service import build_desktop_understanding_packet


def build_puzzle_from_user_text(
    raw_user_text: str,
    llm_hint: Any = None,
    actor_role: str = "normal_user",
    input_channel: str = "text",
) -> dict[str, Any]:
    context_pack = build_context_pack()

    puzzle = build_command_puzzle(
        raw_user_text=raw_user_text,
        llm_hint=llm_hint,
        actor_role=actor_role,
        input_channel=input_channel,
        context_pack=context_pack,
    )

    action_hint = str(puzzle.get("selected_action_hint", "") or "")

    understanding_packet = build_desktop_understanding_packet(
        raw_user_text,
        action_hint=action_hint,
        puzzle=puzzle,
        input_channel=input_channel,
        actor_role=actor_role,
        context_pack=context_pack,
    )

    puzzle = dict(puzzle)
    puzzle["understanding_packet"] = understanding_packet

    return {
        "ok": True,
        "puzzle": puzzle,
        "context_pack": context_pack,
        "understanding_packet": understanding_packet,
        "executed": False,
        "note": "understanding_packet_created; no desktop action executed here",
    }