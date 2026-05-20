from __future__ import annotations

from typing import Any
from uuid import uuid4


OPEN_ACTIONS = {"file.open", "app.launch"}
DIRECT_PATH_OPEN_ACTIONS = {"folder.open"}
CLOSE_ACTIONS = {"file.close", "folder.close", "app.close"}


def compile_desktop_task_draft(puzzle: dict[str, Any]) -> dict[str, Any]:
    payload = puzzle if isinstance(puzzle, dict) else {}
    action = str(payload.get("selected_action_hint", "") or "").strip()
    slots = payload.get("slots", {}) if isinstance(payload.get("slots"), dict) else {}
    puzzle_needs = payload.get("needs", {}) if isinstance(payload.get("needs"), dict) else {}
    needs = dict(puzzle_needs)

    understanding_packet = (
        payload.get("understanding_packet", {})
        if isinstance(payload.get("understanding_packet"), dict)
        else {}
    )
    understanding_decision = (
        understanding_packet.get("decision", {})
        if isinstance(understanding_packet.get("decision"), dict)
        else {}
    )
    normalized_target = str(understanding_packet.get("target_normalized", "") or "").strip()

    if action in OPEN_ACTIONS:
        needs["candidate_search"] = True

    if action in DIRECT_PATH_OPEN_ACTIONS:
        needs["candidate_search"] = False
    if action in CLOSE_ACTIONS:
        needs["target_material"] = True

    task_id = f"draft_{uuid4().hex}"

    base_arguments = {
        "draft_only": True,
        "actor_role": str(payload.get("actor_role", "") or ""),
        "input_channel": str(payload.get("input_channel", "") or ""),
        "do_not_execute": True,
        "understanding_packet": understanding_packet,
        "normalized_target": normalized_target,
        "understanding_decision": understanding_decision,
        "need_llm_hint": bool(understanding_decision.get("need_llm_hint", False)),
        "understanding_reason": str(understanding_decision.get("reason", "") or ""),
    }

    if not action:
        needs["user_clarification"] = True
        return {
            "schema_version": "desktop_task_draft_v1",
            "task_id": task_id,
            "source": "tianting_puzzle",
            "status": "need_user_clarification",
            "action": "",
            "target": _target_from_slots(slots, normalized_target=normalized_target),
            "arguments": base_arguments,
            "review_required": True,
            "execution_allowed": False,
            "route_decision": {"decided": False},
            "needs": needs,
            "original_puzzle_summary": _puzzle_summary(payload),
        }

    return {
        "schema_version": "desktop_task_draft_v1",
        "task_id": task_id,
        "source": "tianting_puzzle",
        "status": "draft",
        "action": action,
        "target": _target_from_slots(slots, normalized_target=normalized_target),
        "arguments": base_arguments,
        "review_required": True,
        "execution_allowed": False,
        "route_decision": {"decided": False},
        "needs": needs,
        "original_puzzle_summary": _puzzle_summary(payload),
    }


def _target_from_slots(slots: dict[str, Any], *, normalized_target: str = "") -> dict[str, Any]:
    kind = str(slots.get("target.kind", "") or "")
    name_hint = str(slots.get("target.name_hint", "") or "")
    app_hint = str(slots.get("target.app_hint", "") or "")

    if normalized_target:
        name_hint = normalized_target
        if kind == "app":
            app_hint = normalized_target

    return {
        "kind": kind,
        "name_hint": name_hint,
        "path_hint": str(slots.get("target.path_hint", "") or ""),
        "app_hint": app_hint,
        "time_hint": str(slots.get("target.time_hint", "") or ""),
        "format_hint": str(slots.get("target.format_hint", "") or ""),
        "identity": str(slots.get("target.identity", "") or ""),
    }


def _puzzle_summary(puzzle: dict[str, Any]) -> dict[str, Any]:
    understanding = (
        puzzle.get("understanding_packet", {})
        if isinstance(puzzle.get("understanding_packet"), dict)
        else {}
    )

    return {
        "schema_version": str(puzzle.get("schema_version", "") or ""),
        "raw_user_text": str(puzzle.get("raw_user_text", "") or ""),
        "actor_role": str(puzzle.get("actor_role", "") or ""),
        "input_channel": str(puzzle.get("input_channel", "") or ""),
        "confidence": puzzle.get("confidence", 0.0),
        "missing_slots": puzzle.get("missing_slots", []) if isinstance(puzzle.get("missing_slots"), list) else [],
        "target_normalized": str(understanding.get("target_normalized", "") or ""),
        "understanding_decision": understanding.get("decision", {})
        if isinstance(understanding.get("decision"), dict)
        else {},
    }