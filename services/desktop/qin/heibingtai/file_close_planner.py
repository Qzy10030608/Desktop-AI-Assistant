from __future__ import annotations

from services.desktop.qin.heibingtai.app_document_planner import AppDocumentPlanner
from services.desktop.qin.heibingtai.close_models import ClosePlan, CloseTask
from services.desktop.qin.heibingtai.close_scope import CLOSE_SCOPE_CURRENT, normalize_close_scope
from services.desktop.qin.heibingtai.file_target_resolver import FileTargetResolver


class FileClosePlanner:
    def __init__(
        self,
        registered_resolver,
        app_document_planner: AppDocumentPlanner | None = None,
        file_target_resolver: FileTargetResolver | None = None,
    ) -> None:
        self.registered_resolver = registered_resolver
        self.app_document_planner = app_document_planner or AppDocumentPlanner()
        self.file_target_resolver = file_target_resolver or FileTargetResolver()

    def plan(self, task: CloseTask) -> ClosePlan:
        scope = normalize_close_scope(task.close_scope, default=CLOSE_SCOPE_CURRENT)
        session = self.registered_resolver.find_registered_session(task)
        target_type = task.target_type or "file"
        if not session:
            if self._has_resolvable_reference(task):
                return self._plan_resolution_only(task, target_type, scope)
            return ClosePlan(
                action="file.close",
                target_path=task.target_path,
                target_type=target_type,
                close_scope=scope,
                close_level="unregistered_file_top_window_reserved",
                target_origin="unregistered",
                strategy="unsupported_precise_close",
                reason="unregistered_file_close_not_supported",
            )

        target_path = str(session.get("target_path", task.target_path) or task.target_path)
        direct_result = self.app_document_planner.close_registered_file(task, session)
        direct_data = direct_result.get("data", {}) if isinstance(direct_result.get("data", {}), dict) else {}
        return ClosePlan(
            action="file.close",
            target_path=target_path,
            target_type=str(session.get("target_type", target_type) or target_type),
            close_scope=scope,
            close_level=str(direct_data.get("close_level", "registered_file_precise_close_reserved") or "registered_file_precise_close_reserved"),
            target_origin="registered",
            strategy=str(direct_data.get("close_strategy", "unsupported_precise_close") or "unsupported_precise_close"),
            direct_result=direct_result,
        )

    def _plan_resolution_only(self, task: CloseTask, target_type: str, scope: str) -> ClosePlan:
        resolver_result = self.file_target_resolver.resolve(self._resolver_task(task, target_type))
        resolution_state = str(resolver_result.get("resolution_state", "") or "")
        candidates = resolver_result.get("candidates", [])
        if not isinstance(candidates, list):
            candidates = []
        requires_user_choice = resolution_state == "ambiguous_candidates"

        error = str(resolver_result.get("error", "") or "")
        ok = False
        message = "File close target resolution completed without executing close."
        if resolution_state == "resolved_unique":
            candidate = resolver_result.get("selected_candidate", {})
            if isinstance(candidate, dict):
                app_kind = str(candidate.get("app_kind", "") or "").strip().lower()
                if app_kind in {
                    "notepad",
                    "vscode",
                    "office_word",
                    "office_excel",
                    "office_powerpoint",
                    "wps_writer",
                    "wps_spreadsheet",
                    "wps_presentation",
                }:
                    return self._plan_resolved_candidate_close(task, target_type, scope, resolver_result, candidate)
            error = "resolved_unique_adapter_not_enabled"
            message = "File close target was resolved, but this document adapter is not enabled for resolved candidates."
        elif resolution_state == "ambiguous_candidates":
            error = "requires_user_choice"
            message = "Multiple file close candidates were found. User choice is required."
        elif resolution_state == "not_found":
            error = "file_view_not_resolved"
            message = "No matching file view candidate was found."

        data = dict(resolver_result)
        data.update({
            "ok": ok,
            "resolution_ok": bool(resolver_result.get("ok", False)),
            "close_strategy": "resolution_only",
            "close_error": error,
            "error": error,
            "matched_count": int(data.get("candidate_count", len(candidates)) or 0),
            "closed_count": 0,
            "skipped_count": 0,
            "requires_user_choice": requires_user_choice,
        })
        if error == "resolved_unique_adapter_not_enabled":
            self._apply_close_llm_hint({"error": error}, data)

        direct_result = {
            "ok": ok,
            "action": "file.close",
            "adapter_id": "heibingtai_file_target_resolver",
            "message": message,
            "error": error,
            "data": data,
        }
        return ClosePlan(
            action="file.close",
            target_path=task.target_path,
            target_type=target_type,
            close_scope=scope,
            close_level="unregistered_file_target_resolution",
            target_origin="unregistered",
            strategy="resolution_only",
            direct_result=direct_result,
            requires_user_choice=requires_user_choice,
            reason=error,
            candidates=candidates,
        )

    def _plan_resolved_candidate_close(
        self,
        task: CloseTask,
        target_type: str,
        scope: str,
        resolver_result: dict,
        candidate: dict,
    ) -> ClosePlan:
        pseudo_session = self._pseudo_session_from_candidate(task, candidate)
        direct_result = self.app_document_planner.close_registered_file(task, pseudo_session)
        direct_data = direct_result.get("data", {}) if isinstance(direct_result.get("data", {}), dict) else {}
        resolution_fields = self._resolution_fields(resolver_result)
        direct_data.update(resolution_fields)
        self._apply_close_llm_hint(direct_result, direct_data)
        direct_result["data"] = direct_data
        return ClosePlan(
            action="file.close",
            target_path=str(candidate.get("target_path", task.target_path) or task.target_path),
            target_type=target_type,
            close_scope=scope,
            close_level=str(direct_data.get("close_level", "resolved_file_candidate_close") or "resolved_file_candidate_close"),
            target_origin="resolved_runtime_candidate",
            strategy=str(direct_data.get("close_strategy", "resolved_window_title_close") or "resolved_window_title_close"),
            direct_result=direct_result,
            requires_user_choice=False,
            reason=str(direct_result.get("error", "") or ""),
            candidates=resolver_result.get("candidates", []) if isinstance(resolver_result.get("candidates", []), list) else [],
        )

    def _apply_close_llm_hint(self, direct_result: dict, data: dict) -> None:
        target_name = str(data.get("target_name", "") or data.get("target_reference_raw", "") or "").strip() or "目标文件"
        document_adapter = str(data.get("document_adapter", "") or "").strip().lower()
        close_succeeded = bool(data.get("close_succeeded", False))
        try:
            closed_count = int(data.get("closed_count", 0) or 0)
        except Exception:
            closed_count = 0
        error = str(direct_result.get("error", "") or data.get("error", "") or data.get("close_error", "") or "")

        if close_succeeded or closed_count > 0:
            data["user_action_required"] = ""
            if document_adapter == "notepad":
                data["llm_reply_hint"] = f"我已关闭 Notepad 中的“{target_name}”。"
            elif document_adapter == "vscode":
                data["llm_reply_hint"] = f"我已关闭 VSCode 当前标签页中的“{target_name}”。"
            elif document_adapter == "office":
                data["llm_reply_hint"] = self._office_llm_hint(data, target_name)
            elif document_adapter == "wps":
                data["llm_reply_hint"] = self._wps_llm_hint(data, target_name)
            else:
                data["llm_reply_hint"] = f"我已关闭“{target_name}”。"
            return

        if error in {"office_com_not_available", "wps_com_not_available", "wps_document_adapter_required"}:
            data["llm_reply_hint"] = f"我已找到“{target_name}”，但当前 WPS/Office 接口不可用，无法安全自动关闭。"
            data["user_action_required"] = "adapter_unavailable"
            return

        if error == "resolved_unique_adapter_not_enabled":
            label = ""
            selected = data.get("selected_candidate", {})
            if isinstance(selected, dict):
                label = str(selected.get("label", "") or selected.get("window_title", "") or "")
            data["llm_reply_hint"] = f"我已定位到“{label or target_name}”，但该类型暂未开放自动关闭。"
            data["user_action_required"] = "unsupported_auto_close_adapter"

    def _office_llm_hint(self, data: dict, target_name: str) -> str:
        app_kind = str(data.get("app_kind", "") or "").strip().lower()
        app_label = {
            "office_word": "Word",
            "office_excel": "Excel",
            "office_powerpoint": "PowerPoint",
        }.get(app_kind, "Office")
        return f"我已向 {app_label} 发送关闭“{target_name}”的请求。如果出现保存提示，请你手动确认。"

    def _wps_llm_hint(self, data: dict, target_name: str) -> str:
        app_kind = str(data.get("app_kind", "") or "").strip().lower()
        app_label = {
            "wps_writer": "WPS 文字",
            "wps_spreadsheet": "WPS 表格",
            "wps_presentation": "WPS 演示",
        }.get(app_kind, "WPS")
        return f"我已向 {app_label}发送关闭“{target_name}”的请求。如果出现保存提示，请你手动确认。"

    def _pseudo_session_from_candidate(self, task: CloseTask, candidate: dict) -> dict:
        target_name = str(candidate.get("target_name", task.target_name) or task.target_name)
        target_path = str(
            candidate.get("document_fullname", "")
            or candidate.get("target_path", "")
            or task.target_path
            or ""
        )
        return {
            "session_id": str(candidate.get("candidate_id", "") or ""),
            "material_id": str(candidate.get("candidate_id", "") or ""),
            "material_type": "resolved_runtime_candidate",
            "target_origin": "resolved_runtime_candidate",
            "target_path": target_path,
            "target_name": target_name,
            "target_type": "file",
            "app_kind": str(candidate.get("app_kind", "") or ""),
            "process_name": str(candidate.get("process_name", "") or ""),
            "pid": str(candidate.get("pid", "") or ""),
            "hwnd": str(candidate.get("hwnd", "") or ""),
            "window_title": str(candidate.get("window_title", "") or ""),
            "document_adapter": str(candidate.get("document_adapter", "") or ""),
            "open_method": "resolved_running_window",
            "close_strategy": "resolved_window_title_close",
            "open_session_owned": False,
            "candidate": dict(candidate),
        }

    def _resolution_fields(self, resolver_result: dict) -> dict:
        keys = (
            "target_reference_raw",
            "target_name",
            "app_hint",
            "current_hint",
            "resolution_state",
            "candidate_count",
            "candidates",
            "selected_candidate",
            "selected_candidate_id",
            "llm_reply_hint",
            "user_action_required",
            "needs_open_app_choice",
        )
        return {key: resolver_result.get(key) for key in keys if key in resolver_result}

    def _resolver_task(self, task: CloseTask, target_type: str) -> dict:
        arguments = dict(task.arguments or {})
        return {
            "action": "file.close",
            "target_path": task.target_path,
            "target_type": target_type,
            "target_name": task.target_name,
            "target_reference": str(arguments.get("target_reference", "") or ""),
            "app_hint": str(arguments.get("app_hint", "") or ""),
            "current_hint": str(arguments.get("current_hint", "") or ""),
            "arguments": arguments,
        }

    def _has_resolvable_reference(self, task: CloseTask) -> bool:
        arguments = task.arguments if isinstance(task.arguments, dict) else {}
        return any(
            str(value or "").strip()
            for value in (
                task.target_path,
                task.target_name,
                arguments.get("target_reference", ""),
                arguments.get("app_hint", ""),
                arguments.get("current_hint", ""),
            )
        )
