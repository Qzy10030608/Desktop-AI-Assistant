from __future__ import annotations

from typing import Any

from services.desktop.tianting.command_memory_service import CommandMemoryService
from services.desktop.tianting.target_text_normalizer import normalize_target_text


class DesktopUnderstandingService:
    """
    天庭理解层：望闻问切第一版。

    不执行、不授权、不决定 backend。
    这里只生成 understanding_packet。
    """

    def __init__(self, memory_service: CommandMemoryService | None = None) -> None:
        self.memory_service = memory_service or CommandMemoryService()

    def build_packet(
        self,
        raw_user_text: str,
        *,
        action_hint: str,
        puzzle: dict[str, Any] | None = None,
        input_channel: str = "text",
        actor_role: str = "normal_user",
        context_pack: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        puzzle_payload = puzzle if isinstance(puzzle, dict) else {}
        slots = puzzle_payload.get("slots", {}) if isinstance(puzzle_payload.get("slots"), dict) else {}

        slot_target = (
            str(slots.get("target.app_hint", "") or "").strip()
            or str(slots.get("target.name_hint", "") or "").strip()
            or str(raw_user_text or "").strip()
        )

        normalized = normalize_target_text(
            slot_target,
            action_hint=action_hint,
        )

        target_normalized = str(normalized.get("normalized_target", "") or "").strip()
        if not target_normalized and slot_target:
            target_normalized = str(slot_target or "").strip()
            normalized["fallback_used"] = "slot_target_when_normalized_empty"
        memory = self.memory_service.expand_target_terms(
            target_normalized or raw_user_text,
            action_hint=action_hint,
            input_channel=input_channel,
            actor_role=actor_role,
        )

        memory_terms = memory.get("terms", []) if isinstance(memory.get("terms"), list) else []
        memory_matched = bool(memory.get("matched", False))
        memory_confidence = float(memory.get("confidence", 0.0) or 0.0)

        decision = self._decide(
            action_hint=action_hint,
            target_normalized=target_normalized,
            memory_matched=memory_matched,
            memory_confidence=memory_confidence,
        )

        packet = {
            "schema_version": "desktop_understanding_packet_v1",
            "raw_user_text": str(raw_user_text or ""),
            "action_hint": str(action_hint or ""),
            "input_channel": str(input_channel or "text"),
            "actor_role": str(actor_role or "normal_user"),
            "target_raw": slot_target,
            "target_normalized": target_normalized,
            "normalization": normalized,
            "evidence": {
                "memory": memory,
                "memory_terms": memory_terms,
                "context_pack_version": str((context_pack or {}).get("schema_version", "") or ""),
            },
            "decision": decision,
            "execution_allowed": False,
            "note": "understanding_only",
        }

        print(
            "[Understanding] "
            f"action={action_hint} "
            f"raw={raw_user_text!r} "
            f"target={target_normalized!r} "
            f"decision={decision.get('status', '')} "
            f"need_llm={decision.get('need_llm_hint', False)} "
            f"reason={decision.get('reason', '')}"
        )

        return packet

    def _decide(
        self,
        *,
        action_hint: str,
        target_normalized: str,
        memory_matched: bool,
        memory_confidence: float,
    ) -> dict[str, Any]:
        if not target_normalized:
            return {
                "status": "need_clarification",
                "reason": "missing_normalized_target",
                "need_llm_hint": False,
                "need_user_question": True,
            }

        if memory_matched and memory_confidence >= 0.78:
            return {
                "status": "memory_hint_ready",
                "reason": "memory_matched",
                "need_llm_hint": False,
                "need_user_question": memory_confidence < 0.86,
            }

        if str(action_hint or "").startswith(("app.", "file.", "folder.")):
            return {
                "status": "need_llm_hint",
                "reason": "local_memory_not_enough",
                "need_llm_hint": True,
                "need_user_question": True,
            }

        return {
            "status": "unknown",
            "reason": "unsupported_action_for_understanding",
            "need_llm_hint": False,
            "need_user_question": True,
        }


def build_desktop_understanding_packet(
    raw_user_text: str,
    *,
    action_hint: str,
    puzzle: dict[str, Any] | None = None,
    input_channel: str = "text",
    actor_role: str = "normal_user",
    context_pack: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return DesktopUnderstandingService().build_packet(
        raw_user_text,
        action_hint=action_hint,
        puzzle=puzzle,
        input_channel=input_channel,
        actor_role=actor_role,
        context_pack=context_pack,
    )