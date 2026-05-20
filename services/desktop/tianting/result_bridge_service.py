from __future__ import annotations

from typing import Any

from services.desktop.language.language_service import DesktopLanguageService
from services.desktop.tianting.pending_task_service import resolve_choice

SUPPORTED_STATUSES = {
    "done",
    "failed",
    "pending_user_choice",
    "dry_run",
    "need_user_clarification",
    "candidate_ready",

    "choice_resolved",
    "choice_cancelled",
    "choice_invalid",
    "choice_ambiguous",

    "app_close_plan_ready",
    "app_close_pending_user_choice",
    "app_close_choice_resolved",
    "app_close_choice_cancelled",
    "app_close_choice_invalid",
    "app_close_not_found",
    "app_close_blocked",
    "app_close_done",
    "app_close_failed",

    "app_launch_pending_user_choice",
    "app_launch_need_permission",
    "app_launch_not_found",
    "app_launch_candidate_ready",
    "app_launch_need_confirmation",
    "app_launch_need_clarification",
    "app_launch_done",
    "app_launch_failed",
    "app_launch_blocked",
    "desktop_connection_disabled",
    "desktop_not_execution_mode",

    "web_command_reserved",
}

STATUS_MESSAGE_KEYS = {
    "done": "desktop.generic.done",
    "failed": "desktop.generic.failed",
    "dry_run": "desktop.generic.dry_run",
    "candidate_ready": "desktop.generic.candidate_ready",

    "choice_resolved": "desktop.generic.choice_resolved",
    "choice_cancelled": "desktop.generic.choice_cancelled",
    "choice_invalid": "desktop.generic.choice_invalid",
    "choice_ambiguous": "desktop.generic.choice_ambiguous",
    "pending_user_choice": "desktop.generic.pending_choice",
    "need_user_clarification": "desktop.generic.need_clarification",

    "app_launch_pending_user_choice": "desktop.app.launch.pending_choice",
    "app_launch_need_permission": "desktop.app.launch.need_permission",
    "app_launch_not_found": "desktop.app.launch.not_found",
    "app_launch_candidate_ready": "desktop.app.launch.candidate_ready",
    "app_launch_need_confirmation": "desktop.app.launch.need_confirmation",
    "app_launch_need_clarification": "desktop.app.launch.need_clarification",
    "app_launch_done": "desktop.app.launch.request_sent",
    "app_launch_failed": "desktop.app.launch.failed",
    "app_launch_blocked": "desktop.app.launch.blocked",
    "desktop_connection_disabled": "desktop.connection.not_enabled",
    "desktop_not_execution_mode": "desktop.connection.not_execution_mode",

    "app_close_plan_ready": "desktop.app.close.plan_ready",
    "app_close_pending_user_choice": "desktop.app.close.pending_choice",
    "app_close_choice_resolved": "desktop.app.close.choice_resolved",
    "app_close_choice_cancelled": "desktop.app.close.choice_cancelled",
    "app_close_choice_invalid": "desktop.app.close.choice_invalid",
    "app_close_not_found": "desktop.app.close.not_found",
    "app_close_blocked": "desktop.app.close.blocked",
    "app_close_done": "desktop.app.close.done",
    "app_close_failed": "desktop.app.close.failed",

    "web_command_reserved": "desktop.web.reserved",
}

INTERNAL_ERROR_MESSAGE_KEYS = {
    "unsupported host permission state": "desktop.app.launch.need_permission",
    "host sent launch request": "desktop.app.launch.request_sent",
    "missing_heibingtai_app_close_plan": "desktop.app.close.need_heibingtai",
}


def handle_receipt_packet(receipt_packet: dict[str, Any]) -> dict[str, Any]:
    return build_safe_output(receipt_packet)


def build_safe_output(receipt_packet: dict[str, Any], *, locale: str = "zh-CN") -> dict[str, Any]:
    packet = receipt_packet if isinstance(receipt_packet, dict) else {}
    status = str(packet.get("status", "") or "").strip()
    if status not in SUPPORTED_STATUSES:
        status = "failed"

    message_key, message_params = _message_key_for_payload(packet, status=status)
    message = _render_message(message_key, message_params, locale=locale)
    result = {
        "status": status,
        "message_key": message_key,
        "message_params": message_params,
        "safe_user_message": message,
        "action": str(packet.get("action", "") or ""),
        "receipt_type": str(packet.get("receipt_type", "") or "temporary_ui_receipt"),
        "llm_rephrase_allowed": bool(packet.get("llm_rephrase_allowed", False)),
        "choice_request": packet.get("choice_request", {}) if isinstance(packet.get("choice_request"), dict) else {},
    }
    if result["llm_rephrase_allowed"]:
        result["rephrase_material"] = {
            "status": status,
            "message_key": message_key,
            "message_params": message_params,
            "safe_context": packet.get("safe_context_for_llm", {})
            if isinstance(packet.get("safe_context_for_llm"), dict)
            else {},
        }
    return result


def resolve_pending_choice_from_user_text(user_text: str, pending_task_id: str | None = None) -> dict[str, Any]:
    result = resolve_choice(user_text, pending_task_id)
    status = str(result.get("status", "") or "")
    choice_type = str(result.get("choice_type", "") or "")
    mapped_status = status
    if choice_type == "app_close_candidate":
        mapped_status = {
            "choice_resolved": "app_close_choice_resolved",
            "choice_cancelled": "app_close_choice_cancelled",
            "choice_invalid": "app_close_choice_invalid",
            "choice_ambiguous": "app_close_choice_invalid",
        }.get(status, status)
    elif choice_type in {"app_launch_candidate", "app_launch_confirmation"}:
        mapped_status = {
            "choice_resolved": "choice_resolved",
            "choice_cancelled": "choice_cancelled",
            "choice_invalid": "choice_invalid",
            "choice_ambiguous": "choice_ambiguous",
        }.get(status, status)
    next_step = "ask_user_again"
    if mapped_status == "app_close_choice_resolved":
        next_step = "submit_selected_candidate_to_qin"
    elif choice_type in {"app_launch_candidate", "app_launch_confirmation"} and mapped_status == "choice_resolved":
        next_step = "submit_selected_candidate_to_qin"
    elif mapped_status in {"choice_resolved"}:
        next_step = "choice_resolved"
    elif mapped_status in {"app_close_choice_cancelled", "choice_cancelled"}:
        next_step = "cancelled"
    return {
        "ok": mapped_status in {"choice_resolved", "choice_cancelled", "app_close_choice_resolved", "app_close_choice_cancelled"},
        "status": mapped_status,
        "raw_choice_status": status,
        "pending_task_id": str(result.get("pending_task_id", "") or ""),
        "selected_candidate": result.get("selected_candidate", {})
        if isinstance(result.get("selected_candidate"), dict)
        else {},
        "original_task_draft": result.get("original_task_draft", {})
        if isinstance(result.get("original_task_draft"), dict)
        else {},
        "message_key": _message_key_for_choice_status(mapped_status),
        "message_params": _message_params_for_payload(result),
        "next_step": next_step,
        "executed": False,
        "allow_direct_execution": False,
    }


def to_safe_chat_message(payload: dict[str, Any], *, locale: str = "zh-CN") -> dict[str, Any]:
    data = payload if isinstance(payload, dict) else {}
    receipt = _find_receipt(data)
    status = str(data.get("status", (receipt or {}).get("status", "")) or "")
    message_key, message_params = _message_key_for_payload(data, receipt=receipt, status=status)
    message = _render_message(message_key, message_params, locale=locale)
    return {
        "ok": bool(data.get("ok", True)),
        "message_key": message_key,
        "message_params": message_params,
        "safe_user_message": message,
        "tts_text": message,
        "display_text": message,
        "choice_request": data.get("choice_request", (receipt or {}).get("choice_request", {}))
        if isinstance(data.get("choice_request", (receipt or {}).get("choice_request", {})), dict)
        else {},
        "ui_prompt_type": str(data.get("ui_prompt_type", (receipt or {}).get("ui_prompt_type", "")) or ""),
        "ui_actions": data.get("ui_actions", (receipt or {}).get("ui_actions", []))
        if isinstance(data.get("ui_actions", (receipt or {}).get("ui_actions", [])), list)
        else [],
        "debug_summary": {
            "status": status,
            "action": str(data.get("action", (receipt or {}).get("action", "")) or ""),
            "has_receipt": bool(receipt),
        },
    }


def _message_key_for_payload(
    data: dict[str, Any],
    *,
    receipt: dict[str, Any] | None = None,
    status: str = "",
) -> tuple[str, dict[str, Any]]:
    payload = data if isinstance(data, dict) else {}
    receipt_payload = receipt if isinstance(receipt, dict) else {}
    explicit_key = str(payload.get("message_key", receipt_payload.get("message_key", "")) or "").strip()
    params = _message_params_for_payload(payload, receipt=receipt_payload)
    if explicit_key:
        return explicit_key, params

    route = str(payload.get("route", receipt_payload.get("route", "")) or "").strip()
    if route == "need_clarification":
        return "desktop.generic.need_clarification", params
    if route == "web_command_reserved":
        return "desktop.web.reserved", params
    if route == "system_skill":
        return str(payload.get("message_key", "") or "desktop.generic.done"), params

    raw_text = " ".join(
        str(value or "")
        for value in (
            payload.get("message", ""),
            payload.get("safe_user_message", ""),
            receipt_payload.get("safe_user_message", ""),
            _nested_error(payload),
        )
    )
    lower_raw_text = raw_text.lower()
    for needle, key in INTERNAL_ERROR_MESSAGE_KEYS.items():
        if needle.lower() in lower_raw_text:
            return key, params

    normalized_status = str(status or payload.get("status", receipt_payload.get("status", "")) or "").strip()
    if normalized_status == "web_command_reserved":
        return "desktop.web.reserved", params
    return STATUS_MESSAGE_KEYS.get(normalized_status, "desktop.generic.failed"), params


def _message_key_for_choice_status(status: str) -> str:
    return STATUS_MESSAGE_KEYS.get(str(status or ""), "desktop.generic.need_clarification")


def _message_params_for_payload(
    data: dict[str, Any],
    *,
    receipt: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = data if isinstance(data, dict) else {}
    receipt_payload = receipt if isinstance(receipt, dict) else {}

    raw_nested_data = payload.get("data")
    nested_data: dict[str, Any] = raw_nested_data if isinstance(raw_nested_data, dict) else {}

    raw_qin_result = payload.get("qin_result")
    qin_result: dict[str, Any] = raw_qin_result if isinstance(raw_qin_result, dict) else {}

    raw_qin_data = qin_result.get("data")
    qin_data: dict[str, Any] = raw_qin_data if isinstance(raw_qin_data, dict) else {}

    raw_qin_receipt = qin_data.get("receipt_packet")
    qin_receipt: dict[str, Any] = raw_qin_receipt if isinstance(raw_qin_receipt, dict) else {}
    params: dict[str, Any] = {}

    # 1. 先合并所有 message_params
    for source in (receipt_payload, qin_receipt, qin_data, nested_data, qin_result, payload):
        if not isinstance(source, dict):
            continue
        raw_params = source.get("message_params")
        if isinstance(raw_params, dict):
            params.update(raw_params)

    def first_text(*values: Any) -> str:
        for value in values:
            text = str(value or "").strip()
            if text and text not in {"-", "None", "null"}:
                return text
        return ""

    def label_from_candidate(candidate: Any) -> str:
        if not isinstance(candidate, dict):
            return ""
        return first_text(
            candidate.get("label"),
            candidate.get("title"),
            candidate.get("target_name"),
            candidate.get("app_name"),
            candidate.get("name"),
            candidate.get("app_id"),
        )

    # 2. 候选对象优先
    for source in (payload, nested_data, qin_data, qin_result, receipt_payload, qin_receipt):
        if not isinstance(source, dict):
            continue
        target = label_from_candidate(source.get("selected_candidate")) or label_from_candidate(source.get("candidate"))
        if target:
            params["target"] = target
            return params

    # 3. 常规字段兜底
    for source in (payload, nested_data, qin_data, qin_result, receipt_payload, qin_receipt):
        if not isinstance(source, dict):
            continue
        target = first_text(
            source.get("target"),
            source.get("target_name"),
            source.get("target_label"),
            source.get("current_target"),
            source.get("app_name"),
            source.get("label"),
            source.get("launch_target_raw"),
            source.get("target_path"),
        )
        if target:
            params["target"] = target
            return params

    params.setdefault("target", "")
    return params


def _render_message(message_key: str, message_params: dict[str, Any], *, locale: str) -> str:
    language_service = DesktopLanguageService()
    profile = language_service.load_profile(locale)
    return language_service.render(profile, message_key, message_params)


def _find_receipt(data: dict[str, Any]) -> dict[str, Any]:
    for key in ("receipt", "receipt_packet"):
        value = data.get(key)
        if isinstance(value, dict):
            return value
    nested = data.get("data")
    if isinstance(nested, dict):
        value = nested.get("receipt_packet")
        if isinstance(value, dict):
            return value
    return {}


def _nested_error(data: dict[str, Any]) -> str:
    nested = data.get("data")
    if isinstance(nested, dict):
        return str(nested.get("error", "") or nested.get("message", "") or "")
    return ""


def _nested_current_target(data: dict[str, Any]) -> str:
    nested = data.get("data")
    if isinstance(nested, dict):
        return str(nested.get("current_target", "") or "")
    return ""
