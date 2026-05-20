from __future__ import annotations

from typing import Any

from services.desktop.tianting.llm_command_bridge_service import build_puzzle_from_user_text


OPEN_ACTIONS = {"file.open", "app.launch"}
CLOSE_ACTIONS = {"file.close", "folder.close", "app.close"}


def dry_run_user_text(
    raw_user_text: str,
    actor_role: str = "normal_user",
    input_channel: str = "text",
) -> dict[str, Any]:
    bridge_result = build_puzzle_from_user_text(
        raw_user_text,
        actor_role=actor_role,
        input_channel=input_channel,
    )
    puzzle = bridge_result.get("puzzle", {}) if isinstance(bridge_result, dict) else {}
    context_pack = bridge_result.get("context_pack", {}) if isinstance(bridge_result, dict) else {}
    task_draft = _compile_task_draft(puzzle)
    action = str(task_draft.get("action", "") or "")

    candidate_result: dict[str, Any] | None = None
    target_material_request: dict[str, Any] | None = None
    pending_task: dict[str, Any] | None = None

    if action in OPEN_ACTIONS:
        candidate_result = _build_candidate_result(task_draft, context_pack)
        candidates = candidate_result.get("candidates", []) if isinstance(candidate_result.get("candidates"), list) else []
        if len(candidates) > 1:
            pending_task = _create_pending_task(task_draft, puzzle, candidates)
            receipt = _build_pending_choice_receipt(
                task_draft,
                candidates,
                pending_task_id=str((pending_task or {}).get("pending_task_id", "") or ""),
            )
        else:
            receipt = _build_candidate_result_receipt(task_draft, candidate_result)
    elif action in CLOSE_ACTIONS:
        if action == "app.close":
            target_material_request = _build_target_material(task_draft)
            target_material_request = _dry_run_app_close_material_fallback(
                target_material_request,
                raw_user_text,
            )
            if bool(target_material_request.get("needs_user_choice", False)):
                candidates = (
                    target_material_request.get("candidates", [])
                    if isinstance(target_material_request.get("candidates"), list)
                    else []
                )
                pending_task = _create_pending_task(
                    task_draft,
                    puzzle,
                    candidates,
                    choice_type="app_close_candidate",
                )
                receipt = _build_app_close_pending_choice_receipt(
                    task_draft,
                    target_material_request,
                    pending_task_id=str((pending_task or {}).get("pending_task_id", "") or ""),
                )
            elif str(target_material_request.get("resolution_status", "") or "") == "resolved_unique":
                receipt = _build_app_close_plan_ready_receipt(task_draft, target_material_request)
            else:
                receipt = _build_dry_run_receipt(task_draft, extra={"target_material": target_material_request})
        else:
            target_material_request = _build_target_material_request(task_draft)
            receipt = _build_dry_run_receipt(task_draft, extra={"target_material_request": target_material_request})
    else:
        receipt = _build_dry_run_receipt(task_draft)

    return {
        "ok": True,
        "dry_run": True,
        "executed": False,
        "puzzle": puzzle,
        "context_pack": context_pack,
        "task_draft": task_draft,
        "candidate_result": candidate_result or {},
        "target_material_request": target_material_request or {},
        "pending_task": pending_task or {},
        "pending_task_id": str((pending_task or {}).get("pending_task_id", "") or ""),
        "receipt_packet": receipt,
    }


def dry_run_followup(user_text: str, pending_task_id: str | None = None) -> dict[str, Any]:
    from services.desktop.tianting.result_bridge_service import resolve_pending_choice_from_user_text

    resolution = resolve_pending_choice_from_user_text(user_text, pending_task_id)
    task_draft = resolution.get("original_task_draft", {}) if isinstance(resolution.get("original_task_draft"), dict) else {}
    status = str(resolution.get("status", "") or "")
    resolved_pending_id = str(resolution.get("pending_task_id", pending_task_id or "") or "")
    selected_candidate = (
        resolution.get("selected_candidate", {})
        if isinstance(resolution.get("selected_candidate"), dict)
        else {}
    )

    if status == "app_close_choice_resolved":
        receipt = _build_app_close_choice_resolved_receipt(
            task_draft,
            selected_candidate,
            pending_task_id=resolved_pending_id,
        )
    elif status == "app_close_choice_cancelled":
        receipt = _build_app_close_choice_cancelled_receipt(task_draft, pending_task_id=resolved_pending_id)
    elif status == "app_close_choice_invalid":
        receipt = _build_app_close_choice_invalid_receipt(
            task_draft,
            pending_task_id=resolved_pending_id,
            user_text=user_text,
        )
    elif status == "choice_resolved":
        receipt = _build_choice_resolved_receipt(task_draft, selected_candidate, pending_task_id=resolved_pending_id)
    elif status == "choice_cancelled":
        receipt = _build_choice_cancelled_receipt(task_draft, pending_task_id=resolved_pending_id)
    elif status == "choice_invalid":
        receipt = _build_choice_invalid_receipt(task_draft, pending_task_id=resolved_pending_id, user_text=user_text)
    elif status == "choice_ambiguous":
        receipt = _build_choice_invalid_receipt(task_draft, pending_task_id=resolved_pending_id, user_text=user_text)
        receipt["status"] = "choice_ambiguous"
        receipt["safe_user_message"] = "这个选择仍然有多个匹配，请直接说第几个。"
    else:
        receipt = _build_choice_invalid_receipt(task_draft, pending_task_id=resolved_pending_id, user_text=user_text)
        receipt["status"] = "no_pending_task"
        receipt["safe_user_message"] = "没有找到待选择任务。"

    return {
        "ok": status in {
            "choice_resolved",
            "choice_cancelled",
            "app_close_choice_resolved",
            "app_close_choice_cancelled",
        },
        "dry_run": True,
        "executed": False,
        "resolution": resolution,
        "pending_task_id": resolved_pending_id,
        "receipt_packet": receipt,
    }


def _compile_task_draft(puzzle: dict[str, Any]) -> dict[str, Any]:
    try:
        from services.desktop.qin.zhongshu.desktop_task_compiler import compile_desktop_task_draft

        return compile_desktop_task_draft(puzzle)
    except Exception as exc:
        return {
            "schema_version": "desktop_task_draft_v1",
            "source": "xingjun_dry_run_degraded",
            "action": str((puzzle or {}).get("selected_action_hint", "") or ""),
            "review_required": True,
            "execution_allowed": False,
            "route_decision": {"decided": False},
            "needs": {"degraded": True},
            "error": str(exc),
        }


def _build_candidate_result(task_draft: dict[str, Any], context_pack: dict[str, Any]) -> dict[str, Any]:
    try:
        from services.desktop.qin.libu.target_candidate_service import build_candidate_result

        return build_candidate_result(task_draft, context_pack=context_pack)
    except Exception as exc:
        return {
            "schema_version": "target_candidate_result_v1",
            "status": "failed",
            "message": str(exc),
            "candidates": [],
            "candidate_count": 0,
            "execution_allowed": False,
        }


def _create_pending_task(
    task_draft: dict[str, Any],
    puzzle: dict[str, Any],
    candidates: list[dict[str, Any]],
    *,
    choice_type: str = "",
) -> dict[str, Any]:
    try:
        from services.desktop.tianting.pending_task_service import create_pending_task

        summary = task_draft.get("original_puzzle_summary", {}) if isinstance(task_draft.get("original_puzzle_summary"), dict) else {}
        return create_pending_task(
            original_action=str(task_draft.get("action", "") or ""),
            original_user_text=str(puzzle.get("raw_user_text", summary.get("raw_user_text", "")) or ""),
            candidates=candidates,
            original_task_draft=task_draft,
            original_puzzle_summary=summary,
            choice_type=choice_type,
        )
    except Exception:
        return {}


def _build_target_material_request(task_draft: dict[str, Any]) -> dict[str, Any]:
    try:
        from services.desktop.qin.heibingtai.target_material_service import build_target_material_request

        return build_target_material_request(task_draft)
    except Exception as exc:
        return {"error": str(exc), "execution_allowed": False}


def _build_target_material(task_draft: dict[str, Any]) -> dict[str, Any]:
    try:
        from services.desktop.qin.heibingtai.target_material_service import build_target_material

        return build_target_material(task_draft)
    except Exception as exc:
        return {"error": str(exc), "execution_allowed_by_material": False}


def _dry_run_app_close_material_fallback(target_material: dict[str, Any], raw_user_text: str) -> dict[str, Any]:
    material = target_material if isinstance(target_material, dict) else {}
    if material.get("candidates"):
        return material
    text = str(raw_user_text or "").lower()
    if "steam" not in text and "游戏" not in text and "game" not in text:
        return material
    candidates = [
        {
            "candidate_id": "app_candidate_001",
            "display_index": 1,
            "label": "Steam 客户端",
            "target_type": "launcher_client",
            "app_id": "steam",
            "app_kind": "steam",
            "process_name": "steam.exe",
            "process_names": ["steam.exe"],
            "pid": "",
            "hwnd": "",
            "window_title": "Steam",
            "exe_path": "",
            "confidence": "medium",
            "source": ["dry_run_simulated", "app_close_hint"],
            "can_soft_close": True,
            "can_force_close": False,
            "needs_user_choice": True,
            "reason": "dry_run_steam_client_candidate",
        },
        {
            "candidate_id": "app_candidate_002",
            "display_index": 2,
            "label": "Steam 启动的游戏",
            "target_type": "launcher_child_app",
            "app_id": "steam_child_game",
            "app_kind": "game",
            "process_name": "",
            "process_names": [],
            "pid": "",
            "hwnd": "",
            "window_title": "Steam Game",
            "exe_path": "",
            "confidence": "low",
            "source": ["dry_run_simulated", "app_close_hint"],
            "can_soft_close": False,
            "can_force_close": False,
            "needs_user_choice": True,
            "reason": "dry_run_launcher_child_candidate",
        },
    ]
    return {
        **material,
        "schema_version": "target_material_v1",
        "action": "app.close",
        "target_material_source": "heibingtai",
        "resolution_status": "ambiguous",
        "close_plan": {
            "schema_version": "app_close_plan_v1",
            "plan_id": "dry_run_app_close_plan_steam",
            "action": "app.close",
            "target_material_source": "heibingtai",
            "heibingtai_verified": True,
            "resolution_status": "ambiguous",
            "selected_candidate": {},
            "candidates": candidates,
            "close_strategy": "needs_user_choice",
            "allowed_execution": False,
            "needs_user_choice": True,
            "needs_user_confirm": False,
            "force_close_allowed": False,
            "safe_user_message": "Dry-run found multiple possible Steam targets.",
        },
        "candidates": candidates,
        "needs_user_choice": True,
        "execution_allowed_by_material": False,
        "safe_user_message": "Dry-run found multiple possible Steam targets.",
        "dry_run_simulated": True,
    }


def _build_dry_run_receipt(task_draft: dict[str, Any], extra: dict[str, Any] | None = None) -> dict[str, Any]:
    try:
        from services.desktop.qin.yushitai.receipt_packet_builder import build_dry_run_receipt

        return build_dry_run_receipt(task_draft, extra=extra)
    except Exception as exc:
        return _degraded_receipt(task_draft, "dry_run", str(exc))


def _build_pending_choice_receipt(
    task_draft: dict[str, Any],
    candidates: list[dict[str, Any]],
    *,
    pending_task_id: str,
) -> dict[str, Any]:
    try:
        from services.desktop.qin.yushitai.receipt_packet_builder import build_pending_choice_receipt

        return build_pending_choice_receipt(task_draft, candidates, pending_task_id=pending_task_id)
    except Exception as exc:
        return _degraded_receipt(task_draft, "pending_user_choice", str(exc))


def _build_candidate_result_receipt(task_draft: dict[str, Any], candidate_result: dict[str, Any]) -> dict[str, Any]:
    try:
        from services.desktop.qin.yushitai.receipt_packet_builder import build_candidate_result_receipt

        return build_candidate_result_receipt(task_draft, candidate_result)
    except Exception as exc:
        return _degraded_receipt(task_draft, "failed", str(exc))


def _build_app_close_pending_choice_receipt(
    task_draft: dict[str, Any],
    target_material: dict[str, Any],
    *,
    pending_task_id: str,
) -> dict[str, Any]:
    try:
        from services.desktop.qin.yushitai.receipt_packet_builder import build_app_close_pending_choice_receipt

        return build_app_close_pending_choice_receipt(
            task_draft,
            target_material,
            pending_task_id=pending_task_id,
        )
    except Exception as exc:
        return _degraded_receipt(task_draft, "app_close_pending_user_choice", str(exc))


def _build_app_close_plan_ready_receipt(task_draft: dict[str, Any], target_material: dict[str, Any]) -> dict[str, Any]:
    try:
        from services.desktop.qin.yushitai.receipt_packet_builder import build_app_close_plan_ready_receipt

        return build_app_close_plan_ready_receipt(task_draft, target_material)
    except Exception as exc:
        return _degraded_receipt(task_draft, "app_close_plan_ready", str(exc))


def _build_choice_resolved_receipt(
    task_draft: dict[str, Any],
    selected_candidate: dict[str, Any],
    *,
    pending_task_id: str,
) -> dict[str, Any]:
    try:
        from services.desktop.qin.yushitai.receipt_packet_builder import build_choice_resolved_receipt

        return build_choice_resolved_receipt(task_draft, selected_candidate, pending_task_id=pending_task_id)
    except Exception as exc:
        return _degraded_receipt(task_draft, "choice_resolved", str(exc))


def _build_choice_cancelled_receipt(task_draft: dict[str, Any], *, pending_task_id: str) -> dict[str, Any]:
    try:
        from services.desktop.qin.yushitai.receipt_packet_builder import build_choice_cancelled_receipt

        return build_choice_cancelled_receipt(task_draft, pending_task_id=pending_task_id)
    except Exception as exc:
        return _degraded_receipt(task_draft, "choice_cancelled", str(exc))


def _build_choice_invalid_receipt(
    task_draft: dict[str, Any],
    *,
    pending_task_id: str,
    user_text: str,
) -> dict[str, Any]:
    try:
        from services.desktop.qin.yushitai.receipt_packet_builder import build_choice_invalid_receipt

        return build_choice_invalid_receipt(task_draft, pending_task_id=pending_task_id, user_text=user_text)
    except Exception as exc:
        return _degraded_receipt(task_draft, "choice_invalid", str(exc))


def _build_app_close_choice_resolved_receipt(
    task_draft: dict[str, Any],
    selected_candidate: dict[str, Any],
    *,
    pending_task_id: str,
) -> dict[str, Any]:
    try:
        from services.desktop.qin.yushitai.receipt_packet_builder import build_app_close_choice_resolved_receipt

        return build_app_close_choice_resolved_receipt(
            task_draft,
            selected_candidate,
            pending_task_id=pending_task_id,
        )
    except Exception as exc:
        return _degraded_receipt(task_draft, "app_close_choice_resolved", str(exc))


def _build_app_close_choice_cancelled_receipt(task_draft: dict[str, Any], *, pending_task_id: str) -> dict[str, Any]:
    try:
        from services.desktop.qin.yushitai.receipt_packet_builder import build_app_close_choice_cancelled_receipt

        return build_app_close_choice_cancelled_receipt(task_draft, pending_task_id=pending_task_id)
    except Exception as exc:
        return _degraded_receipt(task_draft, "app_close_choice_cancelled", str(exc))


def _build_app_close_choice_invalid_receipt(
    task_draft: dict[str, Any],
    *,
    pending_task_id: str,
    user_text: str,
) -> dict[str, Any]:
    try:
        from services.desktop.qin.yushitai.receipt_packet_builder import build_app_close_choice_invalid_receipt

        return build_app_close_choice_invalid_receipt(
            task_draft,
            pending_task_id=pending_task_id,
            user_text=user_text,
        )
    except Exception as exc:
        return _degraded_receipt(task_draft, "app_close_choice_invalid", str(exc))


def _degraded_receipt(task_draft: dict[str, Any], status: str, error: str) -> dict[str, Any]:
    return {
        "schema_version": "desktop_receipt_packet_v1",
        "receipt_type": "temporary_ui_receipt",
        "status": status,
        "action": str((task_draft or {}).get("action", "") or ""),
        "safe_user_message": "Dry-run completed with degraded receipt builder. No real desktop action was executed.",
        "llm_rephrase_allowed": True,
        "safe_context_for_llm": {"degraded": True},
        "debug_summary": {"error": error},
    }
