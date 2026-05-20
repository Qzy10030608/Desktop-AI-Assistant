from __future__ import annotations

from typing import Any

from services.desktop.tianting.command_schema import make_receipt_packet


def build_dry_run_receipt(task_draft: dict[str, Any], extra: dict[str, Any] | None = None) -> dict[str, Any]:
    task = task_draft if isinstance(task_draft, dict) else {}
    action = str(task.get("action", "") or "")
    return make_receipt_packet(
        task_id=str(task.get("task_id", "") or ""),
        status="dry_run",
        action=action,
        safe_user_message=_message_for_action(action, "Dry-run completed. No real desktop action was executed."),
        llm_rephrase_allowed=True,
        safe_context_for_llm={
            "action": action,
            "status": "dry_run",
            "execution_allowed": False,
        },
        debug_summary=_debug_summary(task, extra=extra),
    )


def build_pending_choice_receipt(
    task_draft: dict[str, Any],
    candidates: list[dict[str, Any]] | None = None,
    pending_task_id: str = "",
) -> dict[str, Any]:
    task = task_draft if isinstance(task_draft, dict) else {}
    action = str(task.get("action", "") or "")
    safe_candidates = _safe_candidates(candidates or [])
    choice_type = "file_candidate" if action == "file.open" else "app_candidate"
    return make_receipt_packet(
        task_id=str(task.get("task_id", "") or ""),
        status="pending_user_choice",
        action=action,
        safe_user_message="我找到了多个可能的目标，请选择要继续哪一个。",
        llm_rephrase_allowed=True,
        safe_context_for_llm={
            "action": action,
            "status": "pending_user_choice",
            "candidate_count": len(safe_candidates),
            "suggested_reply": "我找到了多个可能的目标，请你选择第几个。",
        },
        debug_summary={**_debug_summary(task), "candidate_count": len(safe_candidates)},
        choice_request={
            "pending_task_id": str(pending_task_id or task.get("task_id", "") or ""),
            "choice_type": choice_type,
            "candidates": safe_candidates,
        },
    )


def build_choice_resolved_receipt(
    task_draft: dict[str, Any],
    selected_candidate: dict[str, Any],
    pending_task_id: str = "",
) -> dict[str, Any]:
    task = task_draft if isinstance(task_draft, dict) else {}
    candidate = selected_candidate if isinstance(selected_candidate, dict) else {}
    return make_receipt_packet(
        task_id=str(task.get("task_id", "") or ""),
        status="choice_resolved",
        action=str(task.get("action", "") or ""),
        safe_user_message=f"已选择：{candidate.get('label', '-')}。本轮仍未执行真实桌面动作。",
        llm_rephrase_allowed=True,
        safe_context_for_llm={
            "status": "choice_resolved",
            "selected_label": str(candidate.get("label", "") or ""),
            "pending_task_id": str(pending_task_id or ""),
        },
        debug_summary={**_debug_summary(task), "selected_candidate_id": str(candidate.get("candidate_id", "") or "")},
    )


def build_choice_cancelled_receipt(task_draft: dict[str, Any], pending_task_id: str = "") -> dict[str, Any]:
    task = task_draft if isinstance(task_draft, dict) else {}
    return make_receipt_packet(
        task_id=str(task.get("task_id", "") or ""),
        status="choice_cancelled",
        action=str(task.get("action", "") or ""),
        safe_user_message="已取消这个待选择任务，没有执行任何桌面动作。",
        llm_rephrase_allowed=True,
        safe_context_for_llm={"status": "choice_cancelled", "pending_task_id": str(pending_task_id or "")},
        debug_summary=_debug_summary(task),
    )


def build_choice_invalid_receipt(
    task_draft: dict[str, Any],
    pending_task_id: str = "",
    user_text: str = "",
) -> dict[str, Any]:
    task = task_draft if isinstance(task_draft, dict) else {}
    return make_receipt_packet(
        task_id=str(task.get("task_id", "") or ""),
        status="choice_invalid",
        action=str(task.get("action", "") or ""),
        safe_user_message="我没有匹配到这个选择，请按第几个来选，或说取消。",
        llm_rephrase_allowed=True,
        safe_context_for_llm={
            "status": "choice_invalid",
            "pending_task_id": str(pending_task_id or ""),
            "user_text": str(user_text or ""),
        },
        debug_summary=_debug_summary(task),
    )


def build_candidate_result_receipt(task_draft: dict[str, Any], candidate_result: dict[str, Any]) -> dict[str, Any]:
    task = task_draft if isinstance(task_draft, dict) else {}
    result = candidate_result if isinstance(candidate_result, dict) else {}
    candidates = result.get("candidates", []) if isinstance(result.get("candidates"), list) else []
    status = str(result.get("status", "") or "")
    if not candidates:
        if status == "need_user_clarification":
            return build_clarification_receipt(task, str(result.get("message", "") or "需要补充目标信息。"))
        return build_failed_receipt(task, str(result.get("message", "") or "没有生成候选。"))
    if len(candidates) == 1:
        candidate = candidates[0]
        return make_receipt_packet(
            task_id=str(task.get("task_id", "") or ""),
            status="candidate_ready",
            action=str(task.get("action", "") or ""),
            safe_user_message=f"已生成候选：{candidate.get('label', '-')}。本轮不会真实执行。",
            llm_rephrase_allowed=True,
            safe_context_for_llm={
                "status": "candidate_ready",
                "candidate_count": 1,
                "candidate_label": str(candidate.get("label", "") or ""),
            },
            debug_summary={**_debug_summary(task), "candidate_count": 1},
        )
    return build_pending_choice_receipt(task, candidates)


def build_clarification_receipt(task_draft: dict[str, Any], message: str = "") -> dict[str, Any]:
    task = task_draft if isinstance(task_draft, dict) else {}
    action = str(task.get("action", "") or "")
    return make_receipt_packet(
        task_id=str(task.get("task_id", "") or ""),
        status="need_user_clarification",
        action=action,
        safe_user_message=message or "I need one more detail before building the desktop task.",
        llm_rephrase_allowed=True,
        safe_context_for_llm={"action": action, "status": "need_user_clarification"},
        debug_summary={"missing": (task.get("needs", {}) if isinstance(task.get("needs"), dict) else {})},
    )


def build_failed_receipt(task_draft: dict[str, Any], message: str = "") -> dict[str, Any]:
    task = task_draft if isinstance(task_draft, dict) else {}
    action = str(task.get("action", "") or "")
    return make_receipt_packet(
        task_id=str(task.get("task_id", "") or ""),
        status="failed",
        action=action,
        safe_user_message=message or "The dry-run desktop task could not be built.",
        llm_rephrase_allowed=True,
        safe_context_for_llm={"action": action, "status": "failed"},
        debug_summary={"task_schema_version": str(task.get("schema_version", "") or "")},
    )


def build_app_launch_pending_choice_receipt(
    task: dict[str, Any],
    candidate_result: dict[str, Any],
    pending_task_id: str = "",
) -> dict[str, Any]:
    payload = task if isinstance(task, dict) else {}
    result = candidate_result if isinstance(candidate_result, dict) else {}
    candidates = result.get("candidates", []) if isinstance(result.get("candidates"), list) else []
    safe_candidates = _safe_app_launch_candidates(candidates)
    resolution_status = str(result.get("resolution_status", "") or "")
    receipt_status = "app_launch_need_confirmation" if resolution_status == "need_confirmation" else "app_launch_pending_user_choice"
    choice_type = str(result.get("choice_type", "") or "")
    if not choice_type:
        choice_type = "app_launch_confirmation" if resolution_status == "need_confirmation" else "app_launch_candidate"
    return make_receipt_packet(
        task_id=str(payload.get("task_id", "") or payload.get("request_id", "") or ""),
        status=receipt_status,
        action="app.launch",
        safe_user_message="我找到了多个可能的软件，请选择要打开哪一个。",
        llm_rephrase_allowed=True,
        safe_context_for_llm={
            "status": receipt_status,
            "candidate_count": len(safe_candidates),
            "suggested_reply": "我找到了多个可能的软件，请你选择第几个。",
        },
        debug_summary={
            **_debug_summary(payload),
            "candidate_count": len(safe_candidates),
            "resolution_status": str(result.get("resolution_status", "") or ""),
        },
        choice_request={
            "pending_task_id": str(pending_task_id or ""),
            "choice_type": choice_type,
            "candidates": safe_candidates,
            "ui_prompt_type": str(result.get("ui_prompt_type", "") or ""),
            "ui_actions": result.get("ui_actions", []) if isinstance(result.get("ui_actions"), list) else [],
        },
    )


def build_app_launch_need_permission_receipt(task: dict[str, Any], candidate_result: dict[str, Any]) -> dict[str, Any]:
    payload = task if isinstance(task, dict) else {}
    result = candidate_result if isinstance(candidate_result, dict) else {}
    return make_receipt_packet(
        task_id=str(payload.get("task_id", "") or payload.get("request_id", "") or ""),
        status="app_launch_need_permission",
        action="app.launch",
        safe_user_message=str(
            result.get("safe_user_message", "")
            or "目标对象尚未授权执行，请先在桌面配置的软件区设置权限。"
        ),
        llm_rephrase_allowed=True,
        safe_context_for_llm={
            "status": "app_launch_need_permission",
            "suggested_reply": "目标对象尚未授权执行，请先在桌面配置的软件区设置权限。",
        },
        debug_summary={
            **_debug_summary(payload),
            "resolution_status": str(result.get("resolution_status", "") or ""),
        },
    )


def build_app_launch_not_found_receipt(task: dict[str, Any], candidate_result: dict[str, Any]) -> dict[str, Any]:
    payload = task if isinstance(task, dict) else {}
    result = candidate_result if isinstance(candidate_result, dict) else {}
    return make_receipt_packet(
        task_id=str(payload.get("task_id", "") or payload.get("request_id", "") or ""),
        status="app_launch_not_found",
        action="app.launch",
        safe_user_message=str(
            result.get("safe_user_message", "")
            or "我没有在软件治理区找到这个可执行对象，请先刷新软件列表或在软件区添加它。"
        ),
        llm_rephrase_allowed=True,
        safe_context_for_llm={
            "status": "app_launch_not_found",
            "suggested_reply": "我没有在软件治理区找到这个可执行对象，请先刷新软件列表或在软件区添加它。",
        },
        debug_summary={
            **_debug_summary(payload),
            "resolution_status": str(result.get("resolution_status", "") or ""),
        },
    )


def build_app_launch_candidate_ready_receipt(task: dict[str, Any], candidate_result: dict[str, Any]) -> dict[str, Any]:
    payload = task if isinstance(task, dict) else {}
    result = candidate_result if isinstance(candidate_result, dict) else {}
    selected = result.get("selected_candidate", {}) if isinstance(result.get("selected_candidate"), dict) else {}
    return make_receipt_packet(
        task_id=str(payload.get("task_id", "") or payload.get("request_id", "") or ""),
        status="app_launch_candidate_ready",
        action="app.launch",
        safe_user_message=str(
            result.get("safe_user_message", "")
            or f"已匹配到软件“{selected.get('label', '目标软件')}”，将交给秦链审议执行。"
        ),
        llm_rephrase_allowed=True,
        safe_context_for_llm={
            "status": "app_launch_candidate_ready",
            "selected_label": str(selected.get("label", "") or ""),
        },
        debug_summary={
            **_debug_summary(payload),
            "resolution_status": str(result.get("resolution_status", "") or ""),
            "selected_candidate_id": str(selected.get("candidate_id", "") or ""),
        },
    )


def build_app_close_plan_ready_receipt(task_draft_or_task: dict[str, Any], target_material: dict[str, Any]) -> dict[str, Any]:
    task = task_draft_or_task if isinstance(task_draft_or_task, dict) else {}
    material = target_material if isinstance(target_material, dict) else {}
    close_plan = material.get("close_plan", {}) if isinstance(material.get("close_plan"), dict) else {}
    candidate = close_plan.get("selected_candidate", {}) if isinstance(close_plan.get("selected_candidate"), dict) else {}
    return make_receipt_packet(
        task_id=str(task.get("task_id", "") or task.get("request_id", "") or ""),
        status="app_close_plan_ready",
        action="app.close",
        safe_user_message=str(close_plan.get("safe_user_message", "") or "Application close plan is ready."),
        llm_rephrase_allowed=True,
        safe_context_for_llm={
            "status": "app_close_plan_ready",
            "resolution_status": str(close_plan.get("resolution_status", "") or ""),
            "close_strategy": str(close_plan.get("close_strategy", "") or ""),
            "selected_candidate_label": str(candidate.get("label", "") or ""),
        },
        debug_summary={
            **_debug_summary(task),
            "target_material_source": str(material.get("target_material_source", "") or ""),
            "close_plan_id": str(close_plan.get("plan_id", "") or ""),
        },
    )


def build_app_close_blocked_receipt(task: dict[str, Any], target_material: dict[str, Any]) -> dict[str, Any]:
    material = target_material if isinstance(target_material, dict) else {}
    close_plan = material.get("close_plan", {}) if isinstance(material.get("close_plan"), dict) else {}
    return make_receipt_packet(
        task_id=str((task or {}).get("task_id", "") or (task or {}).get("request_id", "") or ""),
        status="app_close_blocked",
        action="app.close",
        safe_user_message=str(material.get("safe_user_message", "") or "Application close was blocked by target material review."),
        llm_rephrase_allowed=True,
        safe_context_for_llm={
            "status": "app_close_blocked",
            "resolution_status": str(material.get("resolution_status", "") or ""),
            "close_strategy": str(close_plan.get("close_strategy", "") or ""),
        },
        debug_summary={
            **_debug_summary(task if isinstance(task, dict) else {}),
            "target_material_source": str(material.get("target_material_source", "") or ""),
            "close_plan_id": str(close_plan.get("plan_id", "") or ""),
        },
    )


def build_app_close_not_found_receipt(task: dict[str, Any], target_material: dict[str, Any]) -> dict[str, Any]:
    receipt = build_app_close_blocked_receipt(task, target_material)
    receipt["status"] = "app_close_not_found"
    receipt["safe_user_message"] = str(
        (target_material or {}).get("safe_user_message", "")
        or "No running application target was found."
    )
    if isinstance(receipt.get("safe_context_for_llm"), dict):
        receipt["safe_context_for_llm"]["status"] = "app_close_not_found"
    return receipt


def build_app_close_plan_receipt(task_draft_or_task: dict[str, Any], target_material: dict[str, Any]) -> dict[str, Any]:
    return build_app_close_plan_ready_receipt(task_draft_or_task, target_material)


def build_app_close_pending_choice_receipt(
    task: dict[str, Any],
    target_material: dict[str, Any],
    pending_task_id: str = "",
) -> dict[str, Any]:
    material = target_material if isinstance(target_material, dict) else {}
    close_plan = material.get("close_plan", {}) if isinstance(material.get("close_plan"), dict) else {}
    candidates = close_plan.get("candidates", []) if isinstance(close_plan.get("candidates"), list) else []
    safe_candidates = _safe_app_candidates(candidates)
    return make_receipt_packet(
        task_id=str((task or {}).get("task_id", "") or (task or {}).get("request_id", "") or ""),
        status="app_close_pending_user_choice",
        action="app.close",
        safe_user_message="我发现多个可能要关闭的对象，请选择一个。",
        llm_rephrase_allowed=True,
        safe_context_for_llm={
            "status": "app_close_pending_user_choice",
            "candidate_count": len(safe_candidates),
            "suggested_reply": "我发现多个可能要关闭的对象，请你选择第几个。",
        },
        debug_summary={
            **_debug_summary(task if isinstance(task, dict) else {}),
            "target_material_source": str(material.get("target_material_source", "") or ""),
            "close_plan_id": str(close_plan.get("plan_id", "") or ""),
            "candidate_count": len(safe_candidates),
        },
        choice_request={
            "pending_task_id": str(pending_task_id or close_plan.get("plan_id", "") or ""),
            "choice_type": "app_close_candidate",
            "candidates": safe_candidates,
        },
    )


def build_app_close_choice_resolved_receipt(
    task: dict[str, Any],
    selected_candidate: dict[str, Any],
    pending_task_id: str = "",
) -> dict[str, Any]:
    payload = task if isinstance(task, dict) else {}
    candidate = selected_candidate if isinstance(selected_candidate, dict) else {}
    return make_receipt_packet(
        task_id=str(payload.get("task_id", "") or payload.get("request_id", "") or ""),
        status="app_close_choice_resolved",
        action="app.close",
        safe_user_message=f"已选择要关闭的对象：{candidate.get('label', '-')}。尚未执行真实关闭。",
        llm_rephrase_allowed=True,
        safe_context_for_llm={
            "status": "app_close_choice_resolved",
            "pending_task_id": str(pending_task_id or ""),
            "selected_candidate_label": str(candidate.get("label", "") or ""),
            "next_step": "submit_selected_candidate_to_qin",
        },
        debug_summary={
            **_debug_summary(payload),
            "selected_candidate_id": str(candidate.get("candidate_id", "") or ""),
        },
    )


def build_app_close_choice_cancelled_receipt(task: dict[str, Any], pending_task_id: str = "") -> dict[str, Any]:
    payload = task if isinstance(task, dict) else {}
    return make_receipt_packet(
        task_id=str(payload.get("task_id", "") or payload.get("request_id", "") or ""),
        status="app_close_choice_cancelled",
        action="app.close",
        safe_user_message="已取消 app.close 候选选择，没有执行任何关闭动作。",
        llm_rephrase_allowed=True,
        safe_context_for_llm={
            "status": "app_close_choice_cancelled",
            "pending_task_id": str(pending_task_id or ""),
        },
        debug_summary=_debug_summary(payload),
    )


def build_app_close_choice_invalid_receipt(
    task: dict[str, Any],
    pending_task_id: str = "",
    user_text: str = "",
) -> dict[str, Any]:
    payload = task if isinstance(task, dict) else {}
    return make_receipt_packet(
        task_id=str(payload.get("task_id", "") or payload.get("request_id", "") or ""),
        status="app_close_choice_invalid",
        action="app.close",
        safe_user_message="没有匹配到这个 app.close 选择，请说第几个、客户端、游戏那个，或取消。",
        llm_rephrase_allowed=True,
        safe_context_for_llm={
            "status": "app_close_choice_invalid",
            "pending_task_id": str(pending_task_id or ""),
            "user_text": str(user_text or ""),
        },
        debug_summary=_debug_summary(payload),
    )


def build_app_close_done_receipt(task: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    payload = task if isinstance(task, dict) else {}
    data = result.get("data", {}) if isinstance(result.get("data"), dict) else {}
    return make_receipt_packet(
        task_id=str(payload.get("task_id", "") or payload.get("request_id", "") or ""),
        status="app_close_done",
        action="app.close",
        safe_user_message=str(result.get("message", "") or "Application close completed."),
        llm_rephrase_allowed=True,
        safe_context_for_llm={
            "status": "app_close_done",
            "close_plan_id": str(data.get("close_plan_id", "") or ""),
            "close_strategy": str(data.get("close_strategy", "") or ""),
            "selected_candidate_label": str(data.get("selected_candidate_label", "") or ""),
        },
        debug_summary={
            **_debug_summary(payload),
            "target_material_source": str(data.get("target_material_source", "") or ""),
            "heibingtai_verified": bool(data.get("heibingtai_verified", False)),
        },
    )


def build_app_close_failed_receipt(task: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    payload = task if isinstance(task, dict) else {}
    data = result.get("data", {}) if isinstance(result.get("data"), dict) else {}
    return make_receipt_packet(
        task_id=str(payload.get("task_id", "") or payload.get("request_id", "") or ""),
        status="app_close_failed",
        action="app.close",
        safe_user_message=str(result.get("message", "") or "Application close failed."),
        llm_rephrase_allowed=True,
        safe_context_for_llm={
            "status": "app_close_failed",
            "error": str(result.get("error", data.get("error", "")) or ""),
            "close_plan_id": str(data.get("close_plan_id", "") or ""),
        },
        debug_summary={
            **_debug_summary(payload),
            "target_material_source": str(data.get("target_material_source", "") or ""),
            "heibingtai_verified": bool(data.get("heibingtai_verified", False)),
        },
    )


def _safe_candidates(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    safe: list[dict[str, Any]] = []
    for index, candidate in enumerate(candidates, start=1):
        if not isinstance(candidate, dict):
            continue
        safe.append({
            "candidate_id": str(candidate.get("candidate_id", f"candidate_{index}") or f"candidate_{index}"),
            "display_index": int(candidate.get("display_index", index) or index),
            "label": str(candidate.get("label", candidate.get("name", "")) or ""),
            "kind": str(candidate.get("kind", "") or ""),
            "safe_location": str(candidate.get("safe_location", "") or ""),
            "file_ext": str(candidate.get("file_ext", "") or ""),
            "modified_hint": str(candidate.get("modified_hint", "") or ""),
            "score": candidate.get("score", 0.0),
            "recommended": bool(candidate.get("recommended", False)),
        })
    return safe


def _safe_app_candidates(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    safe: list[dict[str, Any]] = []
    for index, candidate in enumerate(candidates, start=1):
        if not isinstance(candidate, dict):
            continue
        safe.append({
            "candidate_id": str(candidate.get("candidate_id", f"app_candidate_{index}") or f"app_candidate_{index}"),
            "display_index": int(candidate.get("display_index", index) or index),
            "label": str(candidate.get("label", "") or ""),
            "target_type": str(candidate.get("target_type", "") or ""),
            "window_title": str(candidate.get("window_title", "") or ""),
            "confidence": str(candidate.get("confidence", "") or ""),
            "recommended": bool(candidate.get("recommended", False)),
            "can_soft_close": bool(candidate.get("can_soft_close", False)),
        })
    return safe


def _safe_app_launch_candidates(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    safe: list[dict[str, Any]] = []
    for index, candidate in enumerate(candidates, start=1):
        if not isinstance(candidate, dict):
            continue
        safe.append({
            "candidate_id": str(candidate.get("candidate_id", f"app_launch_candidate_{index}") or f"app_launch_candidate_{index}"),
            "display_index": int(candidate.get("display_index", index) or index),
            "label": str(candidate.get("label", "") or ""),
            "app_id": str(candidate.get("app_id", "") or ""),
            "kind": str(candidate.get("kind", "app") or "app"),
            "permission_state": str(candidate.get("effective_permission_state", candidate.get("permission_state", "")) or ""),
            "can_launch": bool(candidate.get("can_launch", False)),
            "score": candidate.get("score", 0.0),
            "recommended": bool(candidate.get("recommended", False)),
        })
    return safe


def _debug_summary(task: dict[str, Any], *, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "task_schema_version": str(task.get("schema_version", "") or ""),
        "review_required": bool(task.get("review_required", True)),
        "route_decided": bool((task.get("route_decision", {}) if isinstance(task.get("route_decision"), dict) else {}).get("decided", False)),
        "execution_allowed": bool(task.get("execution_allowed", False)),
        "extra": extra or {},
    }


def _message_for_action(action: str, fallback: str) -> str:
    labels = {
        "file.open": "File open dry-run completed. No file was opened.",
        "file.close": "File close dry-run completed. No file was closed.",
        "app.launch": "App launch dry-run completed. No app was launched.",
        "app.close": "App close dry-run completed. No app was closed.",
        "desktop.connection.enable": "Desktop connection enable dry-run completed. Connection state was not changed.",
        "desktop.connection.disable": "Desktop connection disable dry-run completed. Connection state was not changed.",
    }
    return labels.get(str(action or ""), fallback)
