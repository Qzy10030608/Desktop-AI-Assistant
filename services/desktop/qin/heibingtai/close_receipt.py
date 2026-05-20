from __future__ import annotations

from typing import Any

from services.desktop.qin.heibingtai.close_models import ClosePlan


def close_family_for_action(action: str) -> str:
    normalized = str(action or "").strip().lower()
    if normalized == "folder.close":
        return "folder_close"
    if normalized == "file.close":
        return "file_close"
    return "unknown_close"


def base_close_data(plan: ClosePlan) -> dict[str, Any]:
    return {
        "heibingtai_enabled": True,
        "close_family": close_family_for_action(plan.action),
        "close_level": plan.close_level,
        "target_origin": plan.target_origin,
        "close_scope": plan.close_scope,
        "close_strategy": plan.strategy,
        "close_error": "",
        "requires_user_choice": bool(plan.requires_user_choice),
        "matched_count": 0,
        "closed_count": 0,
        "skipped_count": 0,
        "failed_hwnds": [],
        "skip_reasons": {},
        "target_path": plan.target_path,
        "target_type": plan.target_type,
        "app_kind": "",
        "process_name": "",
        "pid": "",
        "hwnd": "",
        "window_title": "",
        "document_adapter": "",
        "document_adapter_stage": "",
        "document_fullname": "",
        "document_saved": "",
        "save_state": "",
        "requires_user_save_confirmation": False,
    }


def merge_adapter_result(plan: ClosePlan, adapter_result: dict[str, Any]) -> dict[str, Any]:
    data = base_close_data(plan)
    adapter_data = adapter_result.get("data", {}) if isinstance(adapter_result.get("data", {}), dict) else {}
    data.update(adapter_data)
    data.update({
        "heibingtai_enabled": True,
        "close_family": close_family_for_action(plan.action),
        "close_level": plan.close_level,
        "target_origin": plan.target_origin,
        "close_scope": adapter_data.get("close_scope", plan.close_scope),
        "close_strategy": adapter_data.get("close_strategy", plan.strategy),
        "requires_user_choice": bool(plan.requires_user_choice),
        "target_path": adapter_data.get("target_path", plan.target_path),
        "target_type": adapter_data.get("target_type", plan.target_type),
    })
    error = str(adapter_result.get("error", "") or adapter_data.get("error", "") or adapter_data.get("close_error", "") or "")
    if error:
        data["close_error"] = error
    return data
