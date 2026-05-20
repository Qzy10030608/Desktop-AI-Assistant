from __future__ import annotations

from typing import Any

from services.desktop.qin.heibingtai.app_document_planner import AppDocumentPlanner
from services.desktop.qin.heibingtai.close_models import ClosePlan, CloseTask
from services.desktop.qin.heibingtai.close_receipt import base_close_data, merge_adapter_result
from services.desktop.qin.heibingtai.close_scope import (
    CLOSE_SCOPE_ALL_MATCHING_PATH,
    CLOSE_SCOPE_CURRENT,
    normalize_close_scope,
)
from services.desktop.qin.heibingtai.file_close_planner import FileClosePlanner
from services.desktop.qin.heibingtai.folder_close_planner import FolderClosePlanner
from services.desktop.qin.heibingtai.registered_resolver import RegisteredCloseResolver
from services.desktop.qin.heibingtai.unregistered_resolver import UnregisteredCloseResolver


class HeibingtaiCloseCoordinator:
    def __init__(
        self,
        *,
        open_session_service,
        host_adapter,
        event_store=None,
    ) -> None:
        self.open_session_service = open_session_service
        self.host_adapter = host_adapter
        self.event_store = event_store
        self.registered_resolver = RegisteredCloseResolver(open_session_service)
        self.unregistered_resolver = UnregisteredCloseResolver()
        self.folder_planner = FolderClosePlanner(self.registered_resolver, self.unregistered_resolver)
        self.file_planner = FileClosePlanner(
            self.registered_resolver,
            AppDocumentPlanner(host_adapter=host_adapter),
        )

    def handle(self, task: dict) -> dict:
        close_task = self._close_task_from_payload(task)
        if close_task.action == "folder.close":
            plan = self.folder_planner.plan(close_task)
            return self._execute_plan(plan)
        if close_task.action == "file.close":
            plan = self.file_planner.plan(close_task)
            return self._execute_plan(plan)
        return self._unsupported_action(close_task)

    def _close_task_from_payload(self, payload: dict) -> CloseTask:
        task = payload if isinstance(payload, dict) else {}
        arguments = task.get("arguments", {}) if isinstance(task.get("arguments"), dict) else {}
        action = str(task.get("action", "") or "").strip().lower()
        default_scope = CLOSE_SCOPE_ALL_MATCHING_PATH if action == "folder.close" else CLOSE_SCOPE_CURRENT
        return CloseTask(
            action=action,
            target_path=str(task.get("target_path", arguments.get("target_path", "")) or ""),
            target_type=str(task.get("target_type", arguments.get("target_type", "")) or ""),
            target_name=str(task.get("target_name", "") or ""),
            close_scope=normalize_close_scope(str(arguments.get("close_scope", "") or ""), default=default_scope),
            session_id=str(arguments.get("session_id", "") or ""),
            target_origin=str(arguments.get("target_origin", "auto") or "auto"),
            execution_backend=str(arguments.get("execution_backend", task.get("execution_backend", "host")) or "host"),
            command_source=str(arguments.get("command_source", "") or ""),
            arguments=dict(arguments),
        )

    def _execute_plan(self, plan: ClosePlan) -> dict:
        if plan.direct_result is not None:
            return self._merge_direct_result(plan, plan.direct_result)
        if not plan.adapter_task:
            return self._planned_skip(plan)
        adapter_result = self.host_adapter.execute(plan.adapter_task)
        data = merge_adapter_result(plan, adapter_result if isinstance(adapter_result, dict) else {})
        ok = bool(adapter_result.get("ok", False)) if isinstance(adapter_result, dict) else False
        message = str((adapter_result or {}).get("message", "") or plan.reason or "Close handled by Heibingtai.")
        result = {
            "ok": ok,
            "action": plan.action,
            "adapter_id": str((adapter_result or {}).get("adapter_id", "host_windows") or "host_windows"),
            "message": message,
            "error": str((adapter_result or {}).get("error", data.get("close_error", "")) or ""),
            "data": data,
        }
        if result["error"] and not data.get("close_error"):
            data["close_error"] = result["error"]
        return result

    def _merge_direct_result(self, plan: ClosePlan, direct_result: dict[str, Any]) -> dict:
        adapter_result = direct_result if isinstance(direct_result, dict) else {}
        data = merge_adapter_result(plan, adapter_result)
        ok = bool(adapter_result.get("ok", False))
        error = str(adapter_result.get("error", data.get("close_error", "")) or "")
        return {
            "ok": ok,
            "action": plan.action,
            "adapter_id": str(adapter_result.get("adapter_id", "heibingtai_document_adapter") or "heibingtai_document_adapter"),
            "message": str(adapter_result.get("message", "") or plan.reason or "Close handled by Heibingtai document adapter."),
            "error": error,
            "data": data,
        }

    def _planned_skip(self, plan: ClosePlan) -> dict:
        error = plan.reason or "unsupported_precise_close"
        data = base_close_data(plan)
        data.update({
            "error": error,
            "close_error": error,
            "matched_count": 0,
            "closed_count": 0,
            "skipped_count": 1,
        })
        return {
            "ok": False,
            "action": plan.action,
            "adapter_id": "host_windows",
            "message": self._skip_message(error),
            "error": error,
            "data": data,
        }

    def _unsupported_action(self, task: CloseTask) -> dict:
        plan = ClosePlan(
            action=task.action or "-",
            target_path=task.target_path,
            target_type=task.target_type,
            close_scope=task.close_scope,
            close_level="unsupported_heibingtai_action",
            target_origin=task.target_origin,
            strategy="unsupported_heibingtai_action",
            reason="unsupported_heibingtai_action",
        )
        data = base_close_data(plan)
        data["error"] = "unsupported_heibingtai_action"
        data["close_error"] = "unsupported_heibingtai_action"
        return {
            "ok": False,
            "action": task.action or "-",
            "adapter_id": "host_windows",
            "message": "Heibingtai only supports file.close and folder.close.",
            "error": "unsupported_heibingtai_action",
            "data": data,
        }

    def _skip_message(self, error: str) -> str:
        if error == "unregistered_file_close_not_supported":
            return "Unregistered file close is not supported by Heibingtai first version."
        if error == "unsupported_precise_close":
            return "Precise file close is not supported for this registered session."
        return "Close skipped by Heibingtai."
