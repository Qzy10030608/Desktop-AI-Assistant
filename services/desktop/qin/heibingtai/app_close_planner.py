from __future__ import annotations

from typing import Any
from uuid import uuid4


def build_app_close_plan(resolution: dict[str, Any]) -> dict[str, Any]:
    payload = resolution if isinstance(resolution, dict) else {}
    status = str(payload.get("resolution_status", "") or "not_found")
    candidates = payload.get("candidates", []) if isinstance(payload.get("candidates"), list) else []
    selected = candidates[0] if status == "resolved_unique" and candidates else {}
    can_soft_close = bool(selected.get("can_soft_close", False)) if isinstance(selected, dict) else False

    if status == "resolved_unique" and can_soft_close:
        strategy = "soft_window_close" if str(selected.get("hwnd", "") or "") else "soft_process_close"
        allowed = True
        needs_choice = False
        message = "Heibingtai prepared a soft application close plan."
    elif status == "ambiguous":
        strategy = "needs_user_choice"
        allowed = False
        needs_choice = True
        message = "Multiple running application targets were found. Please choose one before closing."
    else:
        strategy = "not_found"
        allowed = False
        needs_choice = False
        message = "No running application target was found."

    return {
        "schema_version": "app_close_plan_v1",
        "plan_id": f"app_close_plan_{uuid4().hex}",
        "action": "app.close",
        "target_material_source": "heibingtai",
        "heibingtai_verified": True,
        "resolution_status": status,
        "selected_candidate": selected if isinstance(selected, dict) else {},
        "candidates": candidates,
        "close_strategy": strategy,
        "allowed_execution": allowed,
        "needs_user_choice": needs_choice,
        "needs_user_confirm": False,
        "force_close_allowed": False,
        "safe_user_message": message,
    }


def build_plan_from_selected_candidate(
    selected_candidate: dict[str, Any],
    task: dict[str, Any] | None = None,
) -> dict[str, Any]:
    candidate = dict(selected_candidate) if isinstance(selected_candidate, dict) else {}
    hwnd = str(candidate.get("hwnd", "") or "").strip()
    process_name = str(candidate.get("process_name", "") or "").strip()
    target_type = str(candidate.get("target_type", "") or "").strip().lower()
    can_soft_close = bool(candidate.get("can_soft_close", False))

    if can_soft_close and hwnd:
        strategy = "soft_window_close"
        allowed = True
        message = "Heibingtai prepared a selected-candidate soft window close plan."
    elif can_soft_close and process_name and target_type in {"background_process", "tray_app", "tray_process"}:
        strategy = "tray_quit_required"
        allowed = False
        message = "The selected target appears to require tray/background quit material."
    elif can_soft_close and process_name:
        strategy = "soft_process_close"
        allowed = True
        message = "Heibingtai prepared a selected-candidate soft process close plan."
    else:
        strategy = "not_enough_material"
        allowed = False
        message = "The selected app candidate does not contain enough soft-close material."

    return {
        "schema_version": "app_close_plan_v1",
        "plan_id": f"app_close_plan_{uuid4().hex}",
        "action": "app.close",
        "target_material_source": "heibingtai",
        "heibingtai_verified": True,
        "resolution_status": "resolved_unique",
        "selected_candidate": candidate,
        "candidates": [candidate] if candidate else [],
        "close_strategy": strategy,
        "allowed_execution": allowed,
        "needs_user_choice": False,
        "needs_user_confirm": False,
        "force_close_allowed": False,
        "safe_user_message": message,
    }
