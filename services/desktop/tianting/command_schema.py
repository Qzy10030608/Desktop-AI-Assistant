from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


COMMAND_PUZZLE_VERSION = "desktop_command_puzzle_v1"
CONTEXT_PACK_VERSION = "desktop_context_pack_v1"
RECEIPT_PACKET_VERSION = "desktop_receipt_packet_v1"

SUPPORTED_ACTION_HINTS = {
    "file.open",
    "file.close",
    "folder.open",
    "folder.close",
    "app.launch",
    "app.close",
    "desktop.resolve",
    "desktop.connection.enable",
    "desktop.connection.disable",
}


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def normalize_action_hint(value: Any) -> str:
    text = str(value or "").strip().lower()
    aliases = {
        "open_file": "file.open",
        "close_file": "file.close",
        "open_folder": "folder.open",
        "close_folder": "folder.close",
        "launch_app": "app.launch",
        "close_app": "app.close",
        "resolve_desktop_target": "desktop.resolve",
        "enable_desktop_connection": "desktop.connection.enable",
        "disable_desktop_connection": "desktop.connection.disable",
    }
    text = aliases.get(text, text)
    return text if text in SUPPORTED_ACTION_HINTS else ""


def _safe_dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _safe_list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def make_command_puzzle(
    *,
    raw_user_text: str,
    actor_role: str = "normal_user",
    input_channel: str = "text",
    selected_action_hint: str = "",
    matched_actions: list[dict[str, Any]] | None = None,
    slots: dict[str, Any] | None = None,
    missing_slots: list[str] | None = None,
    needs: dict[str, Any] | None = None,
    confidence: float = 0.0,
    source: dict[str, Any] | None = None,
) -> dict[str, Any]:
    source_payload = _safe_dict(source)
    source_payload.setdefault("origin", "tianting")
    source_payload.setdefault("llm_trust", "untrusted")

    return {
        "schema_version": COMMAND_PUZZLE_VERSION,
        "raw_user_text": str(raw_user_text or ""),
        "actor_role": str(actor_role or "normal_user"),
        "input_channel": str(input_channel or "text"),
        "selected_action_hint": normalize_action_hint(selected_action_hint),
        "matched_actions": _safe_list(matched_actions),
        "slots": _safe_dict(slots),
        "missing_slots": [str(item) for item in _safe_list(missing_slots) if str(item or "").strip()],
        "needs": _safe_dict(needs),
        "confidence": max(0.0, min(1.0, float(confidence or 0.0))),
        "source": source_payload,
        "created_at": now_iso(),
    }


def make_context_pack(
    *,
    conversation_recent_summary: dict[str, Any] | None = None,
    desktop_recent_summary: dict[str, Any] | None = None,
    pending_task_summary: dict[str, Any] | None = None,
    shaofu_material_summary: dict[str, Any] | None = None,
    yushitai_event_summary: dict[str, Any] | None = None,
    observed_runtime_summary: dict[str, Any] | None = None,
    visibility_policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    policy = {
        "hide_full_path": True,
        "hide_pid": True,
        "hide_hwnd": True,
        "hide_policy_trace": True,
        "allowed_for_llm": True,
    }
    policy.update(_safe_dict(visibility_policy))
    return {
        "schema_version": CONTEXT_PACK_VERSION,
        "conversation_recent_summary": _safe_dict(conversation_recent_summary),
        "desktop_recent_summary": _safe_dict(desktop_recent_summary),
        "pending_task_summary": _safe_dict(pending_task_summary),
        "shaofu_material_summary": _safe_dict(shaofu_material_summary),
        "yushitai_event_summary": _safe_dict(yushitai_event_summary),
        "observed_runtime_summary": _safe_dict(observed_runtime_summary),
        "visibility_policy": policy,
        "created_at": now_iso(),
    }


def make_receipt_packet(
    *,
    receipt_type: str = "temporary_ui_receipt",
    task_id: str = "",
    status: str = "dry_run",
    action: str = "",
    safe_user_message: str = "",
    llm_rephrase_allowed: bool = True,
    safe_context_for_llm: dict[str, Any] | None = None,
    debug_summary: dict[str, Any] | None = None,
    choice_request: dict[str, Any] | None = None,
) -> dict[str, Any]:
    packet = {
        "schema_version": RECEIPT_PACKET_VERSION,
        "receipt_type": str(receipt_type or "temporary_ui_receipt"),
        "task_id": str(task_id or ""),
        "status": str(status or "dry_run"),
        "action": normalize_action_hint(action) or str(action or "").strip(),
        "safe_user_message": str(safe_user_message or ""),
        "llm_rephrase_allowed": bool(llm_rephrase_allowed),
        "safe_context_for_llm": _safe_dict(safe_context_for_llm),
        "debug_summary": _safe_dict(debug_summary),
        "created_at": now_iso(),
    }
    if choice_request is not None:
        packet["choice_request"] = _safe_dict(choice_request)
    return packet


def validate_command_puzzle(puzzle: dict[str, Any]) -> tuple[bool, list[str]]:
    if not isinstance(puzzle, dict):
        return False, ["puzzle_not_dict"]

    errors: list[str] = []
    if puzzle.get("schema_version") != COMMAND_PUZZLE_VERSION:
        errors.append("invalid_schema_version")
    if "raw_user_text" not in puzzle:
        errors.append("missing_raw_user_text")
    if "source" not in puzzle or not isinstance(puzzle.get("source"), dict):
        errors.append("missing_source")
    else:
        if str(puzzle["source"].get("llm_trust", "") or "") != "untrusted":
            errors.append("llm_source_must_be_untrusted")

    action = str(puzzle.get("selected_action_hint", "") or "").strip()
    if action and normalize_action_hint(action) != action:
        errors.append("unsupported_action_hint")

    for key in ("slots", "needs"):
        if not isinstance(puzzle.get(key), dict):
            errors.append(f"{key}_not_dict")
    if not isinstance(puzzle.get("matched_actions"), list):
        errors.append("matched_actions_not_list")
    if not isinstance(puzzle.get("missing_slots"), list):
        errors.append("missing_slots_not_list")

    return not errors, errors
