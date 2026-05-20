from __future__ import annotations

from typing import Any, Dict

from services.desktop.qin.gongbu.adapters.vm_adapter import VmAdapter, get_default_vm_adapter
from services.desktop.qin.gongbu.vm_test.vm_action_payload_builder import build_vm_action_payload


class VmActionService:
    ALLOWED_ACTIONS = {
        "app.locate": "locate",
        "locate": "locate",
        "app.launch": "launch",
        "launch": "launch",
        "app.close": "close",
        "close": "close",
    }

    DENIED_ACTIONS = {
        "app.uninstall",
        "uninstall",
        "app.move",
        "app.relocate",
        "move",
        "app.update",
        "update",
    }

    def __init__(self, adapter: VmAdapter | None = None) -> None:
        self.adapter = adapter or get_default_vm_adapter()

    def execute(self, action: str, app_id: str) -> Dict[str, Any]:
        normalized_action = str(action or "").strip().lower()
        normalized_app_id = str(app_id or "").strip()
        if normalized_action in self.DENIED_ACTIONS:
            return self._result(
                ok=False,
                action=normalized_action,
                app_id=normalized_app_id,
                message="VM test does not allow uninstall / move / update yet.",
                error="action_denied",
            )
        operation = self.ALLOWED_ACTIONS.get(normalized_action)
        if operation is None:
            return self._result(
                ok=False,
                action=normalized_action,
                app_id=normalized_app_id,
                message=f"VM test does not support action: {normalized_action or '-'}",
                error="unsupported_action",
            )
        if not normalized_app_id:
            return self._result(
                ok=False,
                action=normalized_action,
                app_id="",
                message="VM test is missing app_id.",
                error="missing_app_id",
            )

        if operation == "locate":
            raw = self.adapter.locate_app(normalized_app_id)
        elif operation == "launch":
            raw = self.adapter.launch_app(normalized_app_id)
        else:
            raw = self.adapter.close_app(normalized_app_id)

        return self._normalize_agent_result(
            raw,
            action=f"app.{operation}",
            app_id=normalized_app_id,
        )

    def execute_desktop_task(self, task: dict, review_decision: dict) -> Dict[str, Any]:
        payload = build_vm_action_payload(task, review_decision)
        action = str(payload.get("action", "") or "").strip().lower()
        target = payload.get("target", {}) if isinstance(payload.get("target"), dict) else {}
        app_id = str(target.get("app_id", "") or target.get("platform_object_id", "") or "").strip()

        raw = self.adapter.execute_action(payload, timeout=self._timeout_for_action(action))
        if self._should_fallback_to_legacy_app_action(raw, action, app_id):
            if action == "app.locate":
                raw = self.adapter.locate_app(app_id)
            elif action == "app.launch":
                raw = self.adapter.launch_app(app_id)
            elif action == "app.close":
                raw = self.adapter.close_app(app_id)

        return self._normalize_desktop_task_result(
            raw,
            task=task,
            review_decision=review_decision,
            request_id=str(payload.get("request_id", "") or ""),
        )

    def locate_app(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self.execute("app.locate", str((payload or {}).get("app_id", "")))

    def launch_app(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self.execute("app.launch", str((payload or {}).get("app_id", "")))

    def close_app(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self.execute("app.close", str((payload or {}).get("app_id", "")))

    def _should_fallback_to_legacy_app_action(self, raw: Dict[str, Any], action: str, app_id: str) -> bool:
        if bool((raw or {}).get("ok", False)):
            return False
        if action not in {"app.locate", "app.launch", "app.close"} or not app_id:
            return False
        text = " ".join(
            str(value or "")
            for value in (
                (raw or {}).get("error"),
                (raw or {}).get("message"),
            )
        ).lower()
        return any(
            marker in text
            for marker in ("404", "405", "501", "not found", "unsupported", "method not allowed", "/action")
        )

    def _timeout_for_action(self, action: str) -> float:
        normalized = str(action or "").strip().lower()
        if normalized in {"file.inspect", "file.locate"}:
            return 8.0
        if normalized in {"file.open", "file.close", "file.close.all"}:
            return 15.0
        if normalized == "file.rename":
            return 30.0
        if normalized == "app.uninstall":
            return 120.0
        if normalized == "app.update":
            return 120.0
        if normalized in {"app.move", "app.relocate"}:
            return 900.0
        if normalized.startswith("file."):
            return 30.0
        return 8.0

    def _normalize_desktop_task_result(
        self,
        raw: Dict[str, Any],
        *,
        task: dict,
        review_decision: dict,
        request_id: str,
    ) -> Dict[str, Any]:
        payload = raw if isinstance(raw, dict) else {}
        data = payload.get("data", {}) if isinstance(payload.get("data"), dict) else {}
        action = str((task or {}).get("action", "") or "").strip()
        target_name = str((task or {}).get("target_name", "") or (task or {}).get("target_id", "") or "-").strip()
        hostname = str(payload.get("hostname", data.get("hostname", "")) or "")
        error = str(payload.get("error", data.get("error", "")) or "")
        message = str(payload.get("message", data.get("message", "")) or "").strip()
        if not message:
            message = "VM desktop task completed." if bool(payload.get("ok", False)) else "VM desktop task failed."
        agent_fields: Dict[str, Any] = {}
        for key in (
            "action",
            "app_id",
            "message",
            "target_path",
            "path",
            "folder",
            "source_path",
            "dest_path",
            "old_path",
            "new_path",
            "old_name",
            "new_name",
            "target_type",
            "object_type",
            "root_id",
            "relative_path",
            "open_handle",
            "pid",
            "pids",
            "window_title",
            "shell_entry",
            "locate_entry",
            "launch_target_kind",
            "launch_target_raw",
            "process_name",
            "process_names",
            "attempts",
            "returncode",
            "stdout",
            "stderr",
            "hostname",
            "error",
            "request_id",
            "url",
            "query",
            "engine",
            "http_status",
            "http_reason",
            "status",
            "package_version",
            "protocol_version",
            "checkpoint_id",
            "material_id",
            "material_status",
            "quarantine_path",
            "restore_strategy",
            "restore_token",
            "restore_mode",
            "retention_policy",
            "retain_until",
            "confirm_mode",
            "confirmed",
            "shaofu_location",
            "shaofu_bucket",
            "shaofu_domain",
            "manifest_path",
            "record_path",
        ):
            if key in payload and payload.get(key) not in (None, ""):
                agent_fields[key] = payload.get(key)
        return {
            "ok": bool(payload.get("ok", False)),
            "action": action,
            "adapter_id": "vm",
            "message": message,
            "data": {
                **data,
                **agent_fields,
                "current_action": action or "-",
                "current_target": target_name or "-",
                "review_result": "vm_test",
                "review_stage": str(review_decision.get("review_stage", "") or ""),
                "decision": str(review_decision.get("decision", "") or ""),
                "risk_level": str(review_decision.get("risk_level", "") or ""),
                "route_result": str(review_decision.get("route_result", "") or ""),
                "checkpoint_id": str(review_decision.get("checkpoint_id", "") or ""),
                "material_id": str(review_decision.get("material_id", "") or ""),
                "material_status": str(review_decision.get("material_status", "") or ""),
                "adapter_stage": "vm",
                "execution_allowed": bool(payload.get("ok", False)),
                "executed_in": "vm",
                "error": error,
                "hostname": hostname,
                "request_id": request_id or str(payload.get("request_id", "") or data.get("request_id", "") or ""),
                "vm_agent_action": str(payload.get("action", data.get("action", "")) or "").strip(),
                "vm_agent_message": message,
            },
        }

    def _normalize_agent_result(self, raw: Dict[str, Any], *, action: str, app_id: str) -> Dict[str, Any]:
        payload = raw if isinstance(raw, dict) else {}
        data = payload.get("data", {}) if isinstance(payload.get("data"), dict) else {}
        hostname = str(payload.get("hostname", data.get("hostname", "")) or "")
        error = str(payload.get("error", data.get("error", "")) or "")
        message = str(payload.get("message", "") or "").strip()
        if not message:
            message = "VM test completed." if bool(payload.get("ok", False)) else "VM test failed."
        agent_fields: Dict[str, Any] = {}
        for key in (
            "action",
            "app_id",
            "message",
            "path",
            "folder",
            "shell_entry",
            "locate_entry",
            "launch_target_kind",
            "launch_target_raw",
            "process_name",
            "process_names",
            "attempts",
            "returncode",
            "stdout",
            "stderr",
            "hostname",
            "error",
        ):
            if key in payload and payload.get(key) not in (None, ""):
                agent_fields[key] = payload.get(key)
        return {
            "ok": bool(payload.get("ok", False)),
            "action": action,
            "adapter_id": "vm",
            "message": message,
            "data": {
                **data,
                **agent_fields,
                "current_action": action,
                "current_target": app_id,
                "review_result": "vm_test",
                "adapter_stage": "vm",
                "execution_allowed": bool(payload.get("ok", False)),
                "executed_in": "vm",
                "app_id": app_id,
                "hostname": hostname,
                "error": error,
                "vm_agent_action": str(payload.get("action", "") or "").strip(),
                "vm_agent_message": message,
            },
        }

    def _result(
        self,
        *,
        ok: bool,
        action: str,
        app_id: str,
        message: str,
        error: str = "",
    ) -> Dict[str, Any]:
        return {
            "ok": bool(ok),
            "action": action,
            "adapter_id": "vm",
            "message": message,
            "data": {
                "current_action": action or "-",
                "current_target": app_id or "-",
                "review_result": "vm_test",
                "adapter_stage": "vm",
                "execution_allowed": False,
                "executed_in": "vm",
                "app_id": app_id,
                "error": error,
            },
        }
