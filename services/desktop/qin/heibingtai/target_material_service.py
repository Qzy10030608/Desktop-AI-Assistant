from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import uuid4


CLOSE_ACTIONS = {"file.close", "folder.close", "app.close"}


class TargetMaterialService:
    def __init__(self, project_root: str | Path | None = None) -> None:
        self.project_root = Path(project_root or Path(__file__).resolve().parents[4]).expanduser().resolve()

    def build_target_material(self, task: dict[str, Any]) -> dict[str, Any]:
        payload = task if isinstance(task, dict) else {}
        action = str(payload.get("action", "") or "").strip()
        if action == "app.close":
            return self._build_app_close_material(payload)
        request = build_target_material_request(payload)
        return {
            "schema_version": "target_material_v1",
            "action": action,
            "target_material_source": "heibingtai",
            "request": request,
            "close_plan": {},
            "resolution_status": "request_only" if action in {"file.close", "folder.close"} else "unsupported_action",
            "candidates": [],
            "needs_user_choice": False,
            "execution_allowed_by_material": False,
            "safe_user_message": str(request.get("note", "") or ""),
        }

    def _build_app_close_material(self, task: dict[str, Any]) -> dict[str, Any]:
        try:
            from services.desktop.qin.heibingtai.app_close_planner import (
                build_app_close_plan,
                build_plan_from_selected_candidate,
            )
            from services.desktop.qin.heibingtai.app_target_resolver import resolve_app_targets

            selected_candidate = self._selected_candidate_from_task(task)
            if selected_candidate:
                resolution = {
                    "schema_version": "app_target_resolution_v1",
                    "resolution_status": "resolved_unique",
                    "candidates": [selected_candidate],
                    "selected_candidate_source": "pending_task_choice",
                    "safe_user_message": "Heibingtai received a selected app close candidate.",
                }
                close_plan = build_plan_from_selected_candidate(selected_candidate, task=task)
            else:
                resolution = resolve_app_targets(task, project_root=self.project_root)
                close_plan = build_app_close_plan(resolution)
        except Exception as exc:
            resolution = {
                "schema_version": "app_target_resolution_v1",
                "resolution_status": "not_found",
                "candidates": [],
                "safe_user_message": f"Heibingtai app target resolution failed: {exc}",
            }
            close_plan = {
                "schema_version": "app_close_plan_v1",
                "plan_id": f"app_close_plan_{uuid4().hex}",
                "action": "app.close",
                "target_material_source": "heibingtai",
                "heibingtai_verified": True,
                "resolution_status": "not_found",
                "selected_candidate": {},
                "candidates": [],
                "close_strategy": "not_found",
                "allowed_execution": False,
                "needs_user_choice": False,
                "needs_user_confirm": False,
                "force_close_allowed": False,
                "safe_user_message": str(resolution.get("safe_user_message", "") or ""),
            }

        candidates = close_plan.get("candidates", []) if isinstance(close_plan.get("candidates"), list) else []
        return {
            "schema_version": "target_material_v1",
            "action": "app.close",
            "target_material_source": "heibingtai",
            "close_plan": close_plan,
            "resolution": resolution,
            "resolution_status": str(close_plan.get("resolution_status", "") or "not_found"),
            "candidates": candidates,
            "needs_user_choice": bool(close_plan.get("needs_user_choice", False)),
            "execution_allowed_by_material": bool(close_plan.get("allowed_execution", False)),
            "safe_user_message": str(close_plan.get("safe_user_message", "") or ""),
        }

    def _selected_candidate_from_task(self, task: dict[str, Any]) -> dict[str, Any]:
        """
        只接受真正的运行态关闭候选。

        不能只因为 candidate_id 存在，就把它当成最终关闭对象。
        软件治理区候选只是静态对象，不一定包含 hwnd / pid / can_soft_close。
        """
        arguments = task.get("arguments", {}) if isinstance(task.get("arguments"), dict) else {}

        for key in ("selected_candidate", "app_close_selected_candidate"):
            candidate = arguments.get(key)
            if not isinstance(candidate, dict):
                continue

            if not str(candidate.get("candidate_id", "") or "").strip():
                continue

            if self._candidate_has_runtime_close_material(candidate):
                return dict(candidate)

        return {}


    def _candidate_has_runtime_close_material(self, candidate: dict[str, Any]) -> bool:
        item = candidate if isinstance(candidate, dict) else {}

        if not bool(item.get("can_soft_close", False)):
            return False

        hwnd = str(item.get("hwnd", "") or "").strip()
        pid = str(item.get("pid", "") or "").strip()
        process_name = str(item.get("process_name", "") or "").strip()

        if hwnd:
            return True

        if pid:
            return True

        source = str(item.get("source", "") or "").lower()
        if process_name and "software_governance" not in source:
            return True

        return False


def build_target_material(task: dict[str, Any], project_root: str | Path | None = None) -> dict[str, Any]:
    return TargetMaterialService(project_root=project_root).build_target_material(task)


def build_target_material_request(task_draft: dict[str, Any]) -> dict[str, Any]:
    task = task_draft if isinstance(task_draft, dict) else {}
    action = str(task.get("action", "") or "").strip()
    target = task.get("target", {}) if isinstance(task.get("target"), dict) else {}
    request = {
        "schema_version": "target_material_request_v1",
        "request_id": f"target_material_req_{uuid4().hex}",
        "task_id": str(task.get("task_id", "") or ""),
        "action": action,
        "target_hint": {
            "kind": str(target.get("kind", "") or ""),
            "name_hint": str(target.get("name_hint", "") or ""),
            "app_hint": str(target.get("app_hint", "") or ""),
            "identity": str(target.get("identity", "") or ""),
            "time_hint": str(target.get("time_hint", "") or ""),
        },
        "dry_run_only": True,
        "execution_allowed": False,
        "close_material_required": action in CLOSE_ACTIONS,
    }

    if action in {"file.close", "folder.close"}:
        request.update({
            "runtime_resolution_plan": [
                "open_session_summary",
                "running_document_summary",
                "window_title_candidates",
                "document_adapter_capabilities",
            ],
            "uses_existing_concepts": [
                "close_coordinator",
                "running_document_resolver",
                "file_close_planner",
                "folder_close_planner",
            ],
            "note": "First stage requests close target material only; it does not invoke HostWindowsAdapter.",
        })
    elif action == "app.close":
        request.update({
            "needs_app_runtime_resolution": True,
            "do_not_trust_llm_process_name": True,
            "runtime_resolution_plan": [
                "software_object_summary",
                "running_process_candidates",
                "window_title_candidates",
                "launcher_child_process_candidates",
                "user_choice_if_ambiguous",
            ],
            "active_modules": ["app_target_resolver.py", "app_close_planner.py"],
            "note": "app.close resolves software runtime material before Host execution.",
        })
    else:
        request.update({
            "close_material_required": False,
            "note": "Action is not a close action handled by Heibingtai target material service.",
        })
    return request
