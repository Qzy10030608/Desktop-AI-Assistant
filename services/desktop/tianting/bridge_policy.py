from __future__ import annotations

from typing import Any

from services.desktop.tianting.command_schema import normalize_action_hint


NORMAL_USER_ACTIONS = {
    "file.open",
    "file.close",
    "app.launch",
    "app.close",
    "desktop.connection.enable",
    "desktop.connection.disable",
}

DEVELOPER_HINT_KEYS = {"test_backend", "sandbox", "vm", "debug", "dry_run"}


def evaluate_bridge_policy(puzzle: dict[str, Any], actor_role: str = "normal_user") -> dict[str, Any]:
    payload = puzzle if isinstance(puzzle, dict) else {}
    role = str(actor_role or payload.get("actor_role", "normal_user") or "normal_user").strip().lower()
    action = normalize_action_hint(payload.get("selected_action_hint", ""))
    slots = payload.get("slots", {}) if isinstance(payload.get("slots"), dict) else {}
    debug_hint_present = any(str(key).lower() in DEVELOPER_HINT_KEYS for key in slots.keys())

    allowed = bool(action)
    reason = "Bridge policy accepted for Qin review."
    if not action:
        allowed = False
        reason = "No supported action hint was selected."
    elif role != "developer" and action not in NORMAL_USER_ACTIONS:
        allowed = False
        reason = "This action is not available for normal users."
    elif role != "developer" and debug_hint_present:
        allowed = False
        reason = "Normal users cannot use test, Sandbox, VM, or debug hints."

    return {
        "allowed": allowed,
        "actor_role": role,
        "action": action,
        "requires_qin_review": True,
        "allow_direct_execution": False,
        "developer_hint_allowed": role == "developer",
        "reason": reason,
    }
