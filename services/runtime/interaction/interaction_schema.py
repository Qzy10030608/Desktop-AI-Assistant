"""Standard dict schemas for the language interaction orchestration layer.

This module intentionally has no dependency on UI, LLM, Qin, Jiuchasi,
PendingTaskService, or ResultBridgeService. It only normalizes plain dicts.
"""

from __future__ import annotations

from typing import Any


INTERACTION_CONTEXT_SCHEMA = "interaction_context_v1"
ROUTE_UNDERSTANDING_PACKET_SCHEMA = "route_understanding_packet_v1"
INTERACTION_RESULT_SCHEMA = "interaction_result_v1"
RECEIPT_MATERIAL_SCHEMA = "receipt_material_v1"
MEMORY_UPDATE_PLAN_SCHEMA = "memory_update_plan_v1"


def _text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(value)


def _bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    return bool(value)


def _float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def build_interaction_context(
    *,
    request_id: Any = "",
    raw_user_text: Any = "",
    input_channel: Any = "",
    from_voice: Any = False,
    actor_role: Any = "",
    locale: Any = "",
    desktop_mode: Any = "",
    execution_backend: Any = "",
    yushitai_run_id: Any = "",
    pending_task_id: Any = "",
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a normalized interaction context for future orchestration."""

    extra_data = _dict(extra)
    normalized_input_channel = _text(input_channel).strip() or (
        "voice" if _bool(from_voice) else "text"
    )
    normalized_pending_task_id = _text(pending_task_id).strip()

    context = {
        "schema_version": INTERACTION_CONTEXT_SCHEMA,
        "request_id": _text(request_id),
        "raw_user_text": _text(raw_user_text),
        "input_channel": normalized_input_channel,
        "from_voice": _bool(from_voice),
        "actor_role": _text(actor_role).strip() or "normal_user",
        "locale": _text(locale).strip() or "zh-CN",
        "desktop_mode": _text(desktop_mode),
        "execution_backend": _text(execution_backend),
        "yushitai_run_id": _text(yushitai_run_id),
        "has_pending": bool(normalized_pending_task_id),
        "pending_task_id": normalized_pending_task_id,
        "memory_refs": _list(extra_data.get("memory_refs")),
        "history_refs": _list(extra_data.get("history_refs")),
        "debug": _dict(extra_data.get("debug")),
    }

    for key, value in extra_data.items():
        if key not in context:
            context[key] = value
    return context


def build_route_understanding_packet(
    *,
    raw_user_text: Any = "",
    route: Any = "chat_reply",
    action_hint: Any = "",
    target_text: Any = "",
    target_type: Any = "",
    target_category: Any = "",
    confidence: Any = 0.0,
    source: Any = "",
    needs_jiuchasi: Any = False,
    needs_qin: Any = False,
    needs_pending: Any = False,
    candidates: Any = None,
    raw_route: Any = None,
    decision: Any = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a route understanding packet without using Jiuchasi internals."""

    extra_data = _dict(extra)
    packet = {
        "schema_version": ROUTE_UNDERSTANDING_PACKET_SCHEMA,
        "raw_user_text": _text(raw_user_text),
        "route": _text(route).strip() or "chat_reply",
        "action_hint": _text(action_hint),
        "target_text": _text(target_text),
        "target_type": _text(target_type),
        "target_category": _text(target_category),
        "confidence": _float(confidence),
        "source": _text(source),
        "needs_jiuchasi": _bool(needs_jiuchasi),
        "needs_qin": _bool(needs_qin),
        "needs_pending": _bool(needs_pending),
        "candidates": _list(candidates),
        "raw_route": _dict(raw_route),
        "decision": _dict(decision),
    }

    for key, value in extra_data.items():
        if key not in packet:
            packet[key] = value
    return packet


def build_interaction_result(
    *,
    handled: Any = False,
    route: Any = "chat_reply",
    status: Any = "",
    ok: Any = True,
    executed: Any = False,
    raw_user_text: Any = "",
    action: Any = "",
    target: Any = "",
    safe_user_message: Any = "",
    display_text: Any = "",
    tts_text: Any = "",
    ui_prompt: Any = None,
    should_start_chat_worker: Any = True,
    qin_result: Any = None,
    jiuchasi_result: Any = None,
    pending_task_id: Any = "",
    memory_update_plan: Any = None,
    debug_refs: Any = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the normalized result returned to ChatRuntimeService."""

    extra_data = _dict(extra)
    result = {
        "schema_version": INTERACTION_RESULT_SCHEMA,
        "handled": _bool(handled),
        "route": _text(route).strip() or "chat_reply",
        "status": _text(status),
        "ok": _bool(ok, True),
        "executed": _bool(executed),
        "raw_user_text": _text(raw_user_text),
        "action": _text(action),
        "target": _text(target),
        "safe_user_message": _text(safe_user_message),
        "display_text": _text(display_text),
        "tts_text": _text(tts_text),
        "ui_prompt": _dict(ui_prompt),
        "should_start_chat_worker": _bool(should_start_chat_worker, True),
        "qin_result": _dict(qin_result),
        "jiuchasi_result": _dict(jiuchasi_result),
        "pending_task_id": _text(pending_task_id),
        "memory_update_plan": _dict(memory_update_plan),
        "debug_refs": _dict(debug_refs),
    }

    for key, value in extra_data.items():
        if key not in result:
            result[key] = value
    return result


def build_chat_passthrough_result(context: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return a non-handled result so ChatRuntimeService can start ChatWorker."""

    context_data = _dict(context)
    return build_interaction_result(
        handled=False,
        route="chat_reply",
        status="passthrough_chat",
        ok=True,
        executed=False,
        raw_user_text=context_data.get("raw_user_text", ""),
        should_start_chat_worker=True,
        debug_refs={"context_schema": context_data.get("schema_version", "")},
    )


def build_direct_reply_result(
    context: dict[str, Any] | None = None,
    safe_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Wrap an already-safe payload as an interaction result."""

    context_data = _dict(context)
    payload = _dict(safe_payload)
    display_text = _text(payload.get("display_text")) or _text(payload.get("safe_user_message"))
    tts_text = _text(payload.get("tts_text")) or display_text

    return build_interaction_result(
        handled=True,
        route=payload.get("route", "direct_reply"),
        status=payload.get("status", ""),
        ok=payload.get("ok", True),
        executed=payload.get("executed", False),
        raw_user_text=payload.get("raw_user_text", context_data.get("raw_user_text", "")),
        action=payload.get("action", ""),
        target=payload.get("target", payload.get("target_name", "")),
        safe_user_message=payload.get("safe_user_message", display_text),
        display_text=display_text,
        tts_text=tts_text,
        ui_prompt=payload.get("ui_prompt", {}),
        should_start_chat_worker=False,
        qin_result=payload.get("qin_result", {}),
        jiuchasi_result=payload.get("jiuchasi_result", {}),
        pending_task_id=payload.get("pending_task_id", context_data.get("pending_task_id", "")),
        memory_update_plan=payload.get("memory_update_plan", {}),
        debug_refs=payload.get("debug_refs", {}),
    )


def build_receipt_material(
    *,
    source: Any = "",
    route: Any = "",
    status: Any = "",
    ok: Any = True,
    executed: Any = False,
    action: Any = "",
    target: Any = "",
    message_key: Any = "",
    message_params: Any = None,
    safe_user_message: Any = "",
    display_text: Any = "",
    tts_text: Any = "",
    ui_prompt: Any = None,
    qin_result: Any = None,
    jiuchasi_result: Any = None,
    pending_result: Any = None,
    system_result: Any = None,
    raw_payload: Any = None,
    debug_refs: Any = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Normalize existing results as factual receipt material.

    This function only standardizes fields. It does not decide success, render
    language, or call any bridge/service.
    """

    extra_data = _dict(extra)
    normalized_safe_message = _text(safe_user_message)
    normalized_display_text = _text(display_text) or normalized_safe_message
    normalized_tts_text = _text(tts_text) or normalized_display_text
    receipt = {
        "schema_version": RECEIPT_MATERIAL_SCHEMA,
        "source": _text(source),
        "route": _text(route),
        "status": _text(status),
        "ok": _bool(ok, True),
        "executed": _bool(executed),
        "action": _text(action),
        "target": _text(target),
        "message_key": _text(message_key),
        "message_params": _dict(message_params),
        "safe_user_message": normalized_safe_message,
        "display_text": normalized_display_text,
        "tts_text": normalized_tts_text,
        "ui_prompt": _dict(ui_prompt),
        "qin_result": _dict(qin_result),
        "jiuchasi_result": _dict(jiuchasi_result),
        "pending_result": _dict(pending_result),
        "system_result": _dict(system_result),
        "raw_payload": _dict(raw_payload),
        "debug_refs": _dict(debug_refs),
    }

    for key, value in extra_data.items():
        if key not in receipt:
            receipt[key] = value
    return receipt


def build_memory_update_plan(
    *,
    enabled: Any = False,
    reason: Any = "",
    memory_domain: Any = "",
    term: Any = "",
    target_label: Any = "",
    target_app_id: Any = "",
    canonical_app_id: Any = "",
    aliases: Any = None,
    confidence: Any = 0.0,
    source: Any = "",
    requires_user_confirm: Any = True,
    confirmed: Any = False,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Describe a future memory write without writing anything."""

    extra_data = _dict(extra)
    plan = {
        "schema_version": MEMORY_UPDATE_PLAN_SCHEMA,
        "enabled": _bool(enabled),
        "reason": _text(reason),
        "memory_domain": _text(memory_domain),
        "term": _text(term),
        "target_label": _text(target_label),
        "target_app_id": _text(target_app_id),
        "canonical_app_id": _text(canonical_app_id),
        "aliases": _list(aliases),
        "confidence": _float(confidence),
        "source": _text(source),
        "requires_user_confirm": _bool(requires_user_confirm, True),
        "confirmed": _bool(confirmed),
        "debug": _dict(extra_data.get("debug")),
    }

    for key, value in extra_data.items():
        if key not in plan:
            plan[key] = value
    return plan


def build_interaction_result_from_receipt(
    context: dict[str, Any] | None = None,
    receipt_material: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Wrap receipt material as an interaction result without business logic."""

    context_data = _dict(context)
    receipt = _dict(receipt_material)
    pending_result = _dict(receipt.get("pending_result"))
    memory_plan = _dict(receipt.get("memory_update_plan"))
    if not memory_plan:
        memory_plan = _dict(receipt.get("memory_plan"))

    return build_interaction_result(
        handled=True,
        route=receipt.get("route", ""),
        status=receipt.get("status", ""),
        ok=receipt.get("ok", True),
        executed=receipt.get("executed", False),
        raw_user_text=context_data.get("raw_user_text", receipt.get("raw_user_text", "")),
        action=receipt.get("action", ""),
        target=receipt.get("target", ""),
        safe_user_message=receipt.get("safe_user_message", ""),
        display_text=receipt.get("display_text", receipt.get("safe_user_message", "")),
        tts_text=receipt.get("tts_text", receipt.get("display_text", receipt.get("safe_user_message", ""))),
        ui_prompt=receipt.get("ui_prompt", {}),
        should_start_chat_worker=False,
        qin_result=receipt.get("qin_result", {}),
        jiuchasi_result=receipt.get("jiuchasi_result", {}),
        pending_task_id=receipt.get(
            "pending_task_id",
            pending_result.get("pending_task_id", context_data.get("pending_task_id", "")),
        ),
        memory_update_plan=memory_plan,
        debug_refs=receipt.get("debug_refs", {}),
        extra={
            "receipt_material": receipt,
            "pending_result": pending_result,
            "system_result": _dict(receipt.get("system_result")),
        },
    )


def is_interaction_result(value: Any) -> bool:
    return (
        isinstance(value, dict)
        and value.get("schema_version") == INTERACTION_RESULT_SCHEMA
    )


def is_receipt_material(value: Any) -> bool:
    return (
        isinstance(value, dict)
        and value.get("schema_version") == RECEIPT_MATERIAL_SCHEMA
    )


def is_memory_update_plan(value: Any) -> bool:
    return (
        isinstance(value, dict)
        and value.get("schema_version") == MEMORY_UPDATE_PLAN_SCHEMA
    )
