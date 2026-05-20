from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from services.desktop.qin.hubu.audit_ledger import AuditLedger
from services.desktop.qin.bingbu.session_guard import SessionGuard
from services.desktop.qin.bingbu.throttle_guard import ThrottleGuard
from services.desktop.qin.gongbu.executor import DesktopExecutor
from services.desktop.qin.gongbu.vm_test.vm_action_service import VmActionService
from services.desktop.qin.libu.action_checkpoint_registry import ActionCheckpointRegistry
from services.desktop.qin.libu.registry_service import LocalRegistryService
from services.desktop.qin.shaofu.backup_store import BackupStore
from services.desktop.qin.shaofu.file_quarantine_service import FileQuarantineService
from services.desktop.qin.shaofu.material_policy import MaterialPolicy
from services.desktop.qin.shaofu.open_session_service import OpenSessionService
from services.desktop.qin.shaofu.quarantine_store import QuarantineStore
from services.desktop.qin.shaofu.restore_registry import RestoreRegistry
from services.desktop.qin.shaofu.snapshot_store import SnapshotStore
from services.desktop.qin.xingbu.destructive_guard import DestructiveGuard
from services.desktop.qin.menxia.review_gate import ReviewGate
from services.desktop.qin.menxia.review_policy import get_review_policy
from services.desktop.qin.yushitai.event_store import YushitaiEventStore
from services.desktop.qin.yushitai.report_writer import ReportWriter
from services.desktop.language.language_service import DesktopLanguageService
from services.desktop.tiandi.mode_store import ModeStore

SYSTEM_SKILL_ACTIONS = frozenset({
    "system_info.read_datetime",
    "weather.read_current",
    "calendar.read_events",
})

VM_BRIDGE_ACTIONS = frozenset({
    "vm.connect",
    "vm.health_check",
    "vm.list_apps",
    "vm.list_files",
    "vm.cleanup",
})


class QinRuntimeService:
    """Facade service for Qin desktop governance runtime."""

    def __init__(
        self,
        project_root: str | Path | None = None,
        *,
        review_gate: ReviewGate | None = None,
        executor: DesktopExecutor | None = None,
        mode_store: ModeStore | None = None,
        local_registry: LocalRegistryService | None = None,
        audit_log: Any | None = None,
        audit_ledger: AuditLedger | None = None,
        event_store: YushitaiEventStore | None = None,
        session_guard: SessionGuard | None = None,
        throttle_guard: ThrottleGuard | None = None,
        destructive_guard: DestructiveGuard | None = None,
        checkpoint_registry: ActionCheckpointRegistry | None = None,
        material_policy: MaterialPolicy | None = None,
        restore_registry: RestoreRegistry | None = None,
        backup_store: BackupStore | None = None,
        quarantine_store: QuarantineStore | None = None,
        snapshot_store: SnapshotStore | None = None,
    ) -> None:
        self.project_root = Path(project_root or Path(__file__).resolve().parents[2]).expanduser().resolve()
        self.review_gate = review_gate or ReviewGate()
        self.executor = executor or DesktopExecutor(project_root=self.project_root)
        self.mode_store = mode_store or ModeStore(self.project_root)
        self.local_registry = local_registry or LocalRegistryService(self.project_root)
        self.audit_ledger = audit_ledger or audit_log or AuditLedger(self.project_root)
        self.audit_log = self.audit_ledger
        self.event_store = event_store or YushitaiEventStore(self.project_root)
        self.session_guard = session_guard or SessionGuard()
        self.throttle_guard = throttle_guard or ThrottleGuard()
        self.destructive_guard = destructive_guard or DestructiveGuard()
        self.checkpoint_registry = checkpoint_registry or ActionCheckpointRegistry(self.project_root, event_store=self.event_store)
        self.restore_registry = restore_registry or RestoreRegistry(self.project_root)
        self.backup_store = backup_store or BackupStore(self.project_root)
        self.quarantine_store = quarantine_store or QuarantineStore(self.project_root)
        self.snapshot_store = snapshot_store or SnapshotStore(self.project_root)
        self.file_quarantine_service = FileQuarantineService(
            self.project_root,
            restore_registry=self.restore_registry,
        )
        self.open_session_service = OpenSessionService(
            self.project_root,
            restore_registry=self.restore_registry,
        )
        self.material_policy = material_policy or MaterialPolicy(
            self.project_root,
            restore_registry=self.restore_registry,
            backup_store=self.backup_store,
            quarantine_store=self.quarantine_store,
            snapshot_store=self.snapshot_store,
        )

    def execute(self, task: dict) -> dict:
        action = str((task or {}).get("action", "")).strip()
        mode = self.mode_store.get_mode_state().current_mode

        mode_decision = self.review_gate.review_mode(mode)
        if not mode_decision["allowed"]:
            return self._error_result(action, mode_decision["reason"])

        root_id = str((task or {}).get("root_id", "")).strip()
        object_type = "root" if root_id else "system"
        action_decision = self.review_gate.review_action(
            mode,
            action,
            object_id=root_id,
            object_type=object_type,
        )
        if not action_decision["allowed"]:
            return self._error_result(action, action_decision["reason"])

        whitelist_check = self._validate_task_against_roots(task)
        if whitelist_check is not None:
            return self._error_result(action, whitelist_check)

        return self.executor.execute(task)

    def set_emergency_stop(self, stopped: bool) -> None:
        self.executor.set_emergency_stop(stopped)
        self.session_guard.set_emergency_stop(stopped)

    def _derive_desktop_execution_state(self, mode: str, requested_backend: str) -> dict[str, Any]:
        runtime_state = self.mode_store.get_runtime_state()

        desktop_mode = str(mode or "").strip().lower() or "disabled"
        requested = str(requested_backend or "").strip().lower()
        if not requested:
            requested = str(runtime_state.get("test_backend", "sandbox") or "sandbox").strip().lower()

        if requested not in {"sandbox", "vm"}:
            requested = "sandbox"

        if desktop_mode == "test":
            return {
                "desktop_mode": desktop_mode,
                "test_backend": requested,
                "execution_backend": requested,
                "host_execution_enabled": False,
            }

        if desktop_mode == "trusted":
            return {
                "desktop_mode": desktop_mode,
                "test_backend": "",
                "execution_backend": "host",
                "host_execution_enabled": True,
            }

        return {
            "desktop_mode": desktop_mode,
            "test_backend": "",
            "execution_backend": "none",
            "host_execution_enabled": False,
        }

    def execute_desktop_task(self, task: dict) -> dict:
        payload = dict(task or {})
        action = str(payload.get("action", "")).strip()
        arguments = payload.get("arguments", {}) if isinstance(payload.get("arguments"), dict) else {}
        mode = self.mode_store.get_mode_state().current_mode
        requested_backend = str(arguments.get("test_backend", payload.get("test_backend", ""))).strip().lower()
        execution_state = self._derive_desktop_execution_state(mode, requested_backend)
        test_backend = str(execution_state.get("test_backend", "") or "")
        effective_backend = str(execution_state.get("execution_backend", "none") or "none")
        host_execution_enabled = bool(execution_state.get("host_execution_enabled", False))

        arguments = dict(arguments)
        arguments["desktop_mode"] = mode
        arguments["host_execution_enabled"] = host_execution_enabled
        arguments["execution_backend"] = effective_backend
        if effective_backend == "host":
            arguments["target_environment"] = str(arguments.get("target_environment", "") or "local_host")
            arguments["path_namespace"] = str(arguments.get("path_namespace", "") or "host_windows")
            arguments["agent_id"] = str(arguments.get("agent_id", "") or "host_windows_adapter")

        if mode == "test":
            arguments["test_backend"] = test_backend or effective_backend
        else:
            arguments["test_backend"] = ""
            arguments.pop("vm_auto_confirm", None)

        payload["arguments"] = arguments
        if action in SYSTEM_SKILL_ACTIONS:
            review_decision = self.review_gate.review_desktop_task(
                payload,
                mode,
                test_backend="sandbox",
            )
            if not bool(review_decision.get("allowed", False)):
                result = self._desktop_task_rejected_result(payload, review_decision, test_backend="sandbox")
                self._record_desktop_result(payload, result, review_decision=review_decision)
                return result

            if action == "system_info.read_datetime":
                result = self._execute_system_info_read_datetime(payload)
            elif action == "weather.read_current":
                result = self._system_skill_reserved_result(
                    payload,
                    status="system_weather_not_configured",
                    message_key="desktop.system.weather.not_configured",
                    capability_group="system_info",
                    risk_level="low_network",
                    executed=False,
                )
            else:
                result = self._system_skill_reserved_result(
                    payload,
                    status="system_calendar_need_permission",
                    message_key="desktop.system.calendar.need_permission",
                    capability_group="system_info",
                    risk_level="personal_read",
                    executed=False,
                )
            self._record_desktop_result(payload, result, review_decision=review_decision)
            return result

        if (
            effective_backend == "host"
            and action == "app.launch"
            and not self._app_launch_task_has_governed_target(payload)
        ):
        
        
            launch_resolution = self._prepare_host_app_launch_candidate(payload)
            status = str(launch_resolution.get("resolution_status", "") or "")
            if status == "resolved_unique":
                selected = launch_resolution.get("selected_candidate", {})
                if isinstance(selected, dict):
                    self._inject_app_launch_candidate(payload, selected)
            elif status in {"multiple_candidates", "need_confirmation"}:
                result = self._app_launch_pending_choice_result(payload, launch_resolution)
                return result
            elif status in {"need_permission", "not_found", "need_clarification"}:
                result = self._app_launch_candidate_blocked_result(payload, launch_resolution)
                self._record_desktop_result(payload, result, review_decision={
                    "allowed": False,
                    "decision": "deny",
                    "reason": str(launch_resolution.get("safe_user_message", "") or status),
                    "review_stage": f"libu_app_launch_{status}",
                    "route_result": "libu.target_candidate",
                    "test_backend": "host",
                })
                return result

        if (
            effective_backend == "host"
            and action == "app.close"
            and not self._app_close_task_has_governed_target(payload)
        ):
            close_permission_resolution = self._prepare_host_app_close_permission_candidate(payload)
            status = str(close_permission_resolution.get("resolution_status", "") or "")

            if status == "resolved_unique":
                selected = close_permission_resolution.get("selected_candidate", {})
                if isinstance(selected, dict):
                    self._inject_app_close_permission_candidate(payload, selected)

            elif status in {"multiple_candidates", "need_confirmation"}:
                result = self._app_close_permission_pending_result(
                    payload,
                    close_permission_resolution,
                )
                return result

            elif status in {"need_permission", "not_found", "need_clarification"}:
                result = self._app_close_permission_blocked_result(
                    payload,
                    close_permission_resolution,
                )
                self._record_desktop_result(payload, result, review_decision={
                    "allowed": False,
                    "decision": "deny",
                    "reason": str(close_permission_resolution.get("safe_user_message", "") or status),
                    "review_stage": f"libu_app_close_{status}",
                    "route_result": "libu.target_candidate",
                    "test_backend": "host",
                })
                return result

        review_decision = self.review_gate.review_desktop_task(
            payload,
            mode,
            test_backend=effective_backend if effective_backend in {"sandbox", "vm", "host"} else test_backend,
        )

        if not bool(review_decision.get("allowed", False)):
            result = self._desktop_task_rejected_result(
                payload,
                review_decision,
                test_backend=effective_backend if effective_backend else test_backend,
            )
            self._record_desktop_result(payload, result, review_decision=review_decision)
            return result

        if action in VM_BRIDGE_ACTIONS:
            result = self._desktop_task_bridge_result(payload, review_decision, test_backend=test_backend)
            self._record_desktop_result(payload, result, review_decision=review_decision)
            return result

        if effective_backend == "sandbox":
            result = self.execute_v2_sandbox(payload)
            self._record_desktop_result(payload, result, review_decision=review_decision)
            return result

        if effective_backend == "vm":
            guard_result = self._review_vm_pre_execution(payload, review_decision)
            if not bool(guard_result.get("allowed", False)):
                blocked_decision = dict(review_decision)
                blocked_decision.update({
                    "allowed": False,
                    "decision": str(guard_result.get("decision", "deny") or "deny"),
                    "reason": str(guard_result.get("reason", "") or "VM pre-execution guard rejected the task."),
                    "review_stage": str(guard_result.get("review_stage", "vm_pre_execution_rejected") or "vm_pre_execution_rejected"),
                })
                result = self._desktop_task_rejected_result(payload, blocked_decision, test_backend=test_backend)
                self._attach_guard_data(result, guard_result)
                self._record_desktop_result(
                    payload,
                    result,
                    review_decision=blocked_decision,
                    checkpoint=guard_result.get("checkpoint") if isinstance(guard_result.get("checkpoint"), dict) else None,
                    material=guard_result.get("material") if isinstance(guard_result.get("material"), dict) else None,
                )
                return result

            checkpoint = guard_result.get("checkpoint") if isinstance(guard_result.get("checkpoint"), dict) else None
            material = guard_result.get("material") if isinstance(guard_result.get("material"), dict) else None
            if checkpoint:
                review_decision = dict(review_decision)
                review_decision["checkpoint_id"] = str(checkpoint.get("checkpoint_id", "") or "")
                if material:
                    review_decision["material_id"] = str(material.get("material_id", "") or "")
                    review_decision["material_status"] = str(material.get("material_status", "") or "")
                arguments = payload.get("arguments", {}) if isinstance(payload.get("arguments"), dict) else {}
                arguments = dict(arguments)
                arguments["checkpoint_id"] = review_decision["checkpoint_id"]
                if material:
                    arguments["material_id"] = review_decision["material_id"]
                    arguments["material_status"] = review_decision["material_status"]
                    for key in (
                        "confirm_mode",
                        "shaofu_location",
                        "retention_policy",
                        "retain_until",
                        "restore_token",
                        "quarantine_path",
                    ):
                        value = material.get(key, "")
                        if value not in (None, ""):
                            arguments[key] = value
                payload["arguments"] = arguments

            result = VmActionService().execute_desktop_task(payload, review_decision)
            if checkpoint:
                try:
                    result_data = result.get("data", {}) if isinstance(result.get("data", {}), dict) else {}
                    self.checkpoint_registry.update_checkpoint(
                        str(checkpoint.get("checkpoint_id", "") or ""),
                        {
                            "action": action,
                            "target_id": str(payload.get("target_id", "") or ""),
                            "target_name": str(payload.get("target_name", "") or ""),
                            "backend": test_backend,
                            "execution_backend": str(result_data.get("execution_backend", test_backend) or test_backend),
                            "target_environment": str(result_data.get("target_environment", "") or ""),
                            "path_namespace": str(result_data.get("path_namespace", "") or ""),
                            "restore_status": str(result_data.get("restore_status", "executed" if bool(result.get("ok", False)) else "execution_failed") or ""),
                            "verify_status": str(result_data.get("verify_status", "") or ""),
                            "relocate_status": str(result_data.get("relocate_status", "") or ""),
                            "relocate_strategy": str(result_data.get("relocate_strategy", "") or ""),
                            "relocate_target_mode": str(result_data.get("relocate_target_mode", "") or ""),
                            "source_path": str(result_data.get("source_path", "") or ""),
                            "dest_path": str(result_data.get("dest_path", "") or ""),
                            "selected_root": str(result_data.get("selected_root", "") or ""),
                            "final_app_dir": str(result_data.get("final_app_dir", "") or ""),
                            "backup_original_path": str(result_data.get("backup_original_path", "") or ""),
                            "registry_backup_path": str(result_data.get("registry_backup_path", "") or ""),
                            "shortcut_backup_dir": str(result_data.get("shortcut_backup_dir", "") or ""),
                            "service_backup_path": str(result_data.get("service_backup_path", "") or ""),
                            "updated_registry_keys": result_data.get("updated_registry_keys", []),
                            "updated_shortcuts": result_data.get("updated_shortcuts", []),
                            "updated_services": result_data.get("updated_services", []),
                            "service_stop_attempts": result_data.get("service_stop_attempts", []),
                            "process_stop_attempts": result_data.get("process_stop_attempts", result_data.get("close_attempts", [])),
                            "target_exe": str(result_data.get("target_exe", "") or ""),
                            "launch_verified": bool(result_data.get("launch_verified", False)),
                            "restore_strategy": str(result_data.get("restore_strategy", "") or ""),
                            "rollback_strategy": str(result_data.get("rollback_strategy", "") or ""),
                            "machine_id": str(result_data.get("machine_id", "") or ""),
                            "agent_id": str(result_data.get("agent_id", "") or ""),
                            "junction_path": str(result_data.get("junction_path", "") or ""),
                            "after_state": {
                                "ok": bool(result.get("ok", False)),
                                "message": str(result.get("message", "") or ""),
                            },
                            "data": {"result": result},
                        },
                    )
                except Exception:
                    pass
            self._record_desktop_result(payload, result, review_decision=review_decision, checkpoint=checkpoint, material=material)
            return result
        
        if effective_backend == "host":
            guard_result = self._review_host_pre_execution(payload, review_decision)

            if not bool(guard_result.get("allowed", False)):
                blocked_decision = dict(review_decision)
                blocked_decision.update({
                    "allowed": False,
                    "decision": str(guard_result.get("decision", "deny") or "deny"),
                    "reason": str(guard_result.get("reason", "") or "Host pre-execution guard rejected the task."),
                    "review_stage": str(
                        guard_result.get("review_stage", "host_pre_execution_rejected")
                        or "host_pre_execution_rejected"
                    ),
                })
                result = self._desktop_task_rejected_result(payload, blocked_decision, test_backend="host")
                self._attach_guard_data(result, guard_result)
                self._record_desktop_result(
                    payload,
                    result,
                    review_decision=blocked_decision,
                    checkpoint=guard_result.get("checkpoint") if isinstance(guard_result.get("checkpoint"), dict) else None,
                    material=guard_result.get("material") if isinstance(guard_result.get("material"), dict) else None,
                )
                return result

            checkpoint = guard_result.get("checkpoint") if isinstance(guard_result.get("checkpoint"), dict) else None
            material = guard_result.get("material") if isinstance(guard_result.get("material"), dict) else None

            if checkpoint:
                review_decision = dict(review_decision)
                review_decision["checkpoint_id"] = str(checkpoint.get("checkpoint_id", "") or "")

                arguments = payload.get("arguments", {}) if isinstance(payload.get("arguments"), dict) else {}
                arguments = dict(arguments)
                arguments["checkpoint_id"] = review_decision["checkpoint_id"]
                payload["arguments"] = arguments

            if material:
                review_decision = dict(review_decision)
                review_decision["material_id"] = str(material.get("material_id", "") or "")
                review_decision["material_status"] = str(material.get("material_status", "") or "")
                arguments = payload.get("arguments", {}) if isinstance(payload.get("arguments"), dict) else {}
                arguments = dict(arguments)
                arguments["material_id"] = review_decision.get("material_id", "")
                arguments["material_status"] = review_decision.get("material_status", "")

                for key in (
                    "confirm_mode",
                    "shaofu_location",
                    "retention_policy",
                    "retain_until",
                    "restore_token",
                    "quarantine_path",
                    "original_path",
                    "source_path",
                    "target_type",
                    "run_id",
                    "run_backend",
                    "restore_action",
                    "manifest_path",
                ):
                    value = material.get(key, "")
                    if value not in (None, ""):
                        arguments[key] = value
                payload["arguments"] = arguments

            executor_task = dict(payload)
            executor_task["adapter_id"] = "host"
            executor_task["execution_backend"] = "host"

            action = str(payload.get("action", "") or "").strip().lower()
            target_material_for_record: dict[str, Any] | None = None
            if action == "app.close":
                target_material = self._prepare_host_app_close_material(executor_task)
                target_material_for_record = target_material
                if not bool(target_material.get("execution_allowed_by_material", False)):
                    if bool(target_material.get("needs_user_choice", False)):
                        pending_task = self._create_app_close_pending_task(executor_task, target_material)
                        pending_task_id = str(pending_task.get("pending_task_id", "") or "")
                        receipt_packet = self._build_app_close_pending_receipt(
                            executor_task,
                            target_material,
                            pending_task_id=pending_task_id,
                        )
                        result = {
                            "ok": True,
                            "action": action,
                            "adapter_id": "heibingtai",
                            "message": str(
                                target_material.get(
                                    "safe_user_message",
                                    "Multiple running application targets were found. Please choose one.",
                                )
                                or ""
                            ),
                            "data": {
                                "current_action": action,
                                "current_target": str(executor_task.get("target_name", "") or "-"),
                                "status": "app_close_pending_user_choice",
                                "target_material_source": "heibingtai",
                                "resolution_status": str(target_material.get("resolution_status", "") or "ambiguous"),
                                "needs_user_choice": True,
                                "requires_user_choice": True,
                                "pending_task_id": pending_task_id,
                                "choice_type": "app_close_candidate",
                                "execution_allowed": False,
                                "execution_allowed_by_material": False,
                                "app_close_plan": target_material.get("close_plan", {})
                                if isinstance(target_material.get("close_plan"), dict)
                                else {},
                                "candidates": target_material.get("candidates", [])
                                if isinstance(target_material.get("candidates"), list)
                                else [],
                                "receipt_packet": receipt_packet,
                            },
                        }
                        self._record_desktop_result(
                            executor_task,
                            result,
                            review_decision=review_decision,
                            checkpoint=checkpoint,
                            material=target_material,
                        )
                        return result

                    blocked_decision = dict(review_decision)
                    status = str(target_material.get("resolution_status", "") or "blocked")
                    blocked_decision.update({
                        "allowed": False,
                        "decision": "deny",
                        "reason": str(target_material.get("safe_user_message", "") or "Heibingtai app close material blocked execution."),
                        "review_stage": "heibingtai_app_close_pending_user_choice"
                        if bool(target_material.get("needs_user_choice", False))
                        else f"heibingtai_app_close_{status}",
                    })
                    result = self._desktop_task_rejected_result(executor_task, blocked_decision, test_backend="host")
                    result_data = result.get("data", {}) if isinstance(result.get("data"), dict) else {}
                    result_data = dict(result_data)
                    result_data.update({
                        "target_material_source": "heibingtai",
                        "status": "app_close_pending_user_choice"
                        if bool(target_material.get("needs_user_choice", False))
                        else f"app_close_{status}",
                        "resolution_status": status,
                        "needs_user_choice": bool(target_material.get("needs_user_choice", False)),
                        "requires_user_choice": bool(target_material.get("needs_user_choice", False)),
                        "execution_allowed_by_material": False,
                        "app_close_plan": target_material.get("close_plan", {}) if isinstance(target_material.get("close_plan"), dict) else {},
                        "candidates": target_material.get("candidates", []) if isinstance(target_material.get("candidates"), list) else [],
                        "error": "app_close_target_ambiguous"
                        if bool(target_material.get("needs_user_choice", False))
                        else f"app_close_target_{status}",
                    })
                    result["data"] = result_data
                    self._record_desktop_result(
                        executor_task,
                        result,
                        review_decision=blocked_decision,
                        checkpoint=checkpoint,
                        material=target_material,
                    )
                    return result

                arguments = executor_task.get("arguments", {}) if isinstance(executor_task.get("arguments"), dict) else {}
                arguments = dict(arguments)
                close_plan = target_material.get("close_plan", {}) if isinstance(target_material.get("close_plan"), dict) else {}
                arguments.update({
                    "target_material_source": "heibingtai",
                    "heibingtai_verified": True,
                    "app_close_plan": close_plan,
                    "close_plan_id": str(close_plan.get("plan_id", "") or ""),
                })
                executor_task["arguments"] = arguments
                payload["arguments"] = arguments

            if action in {"file.close", "folder.close"}:
                from services.desktop.qin.gongbu.adapters.host_windows_adapter import HostWindowsAdapter
                from services.desktop.qin.heibingtai.close_coordinator import HeibingtaiCloseCoordinator

                result = HeibingtaiCloseCoordinator(
                    open_session_service=self.open_session_service,
                    host_adapter=HostWindowsAdapter(),
                    event_store=self.event_store,
                ).handle(executor_task)
            else:
                result = self.executor.execute(executor_task)
            result_data = result.get("data", {}) if isinstance(result.get("data", {}), dict) else {}
            result_data = dict(result_data)
            result_data.update({
                "review_result": "approved" if bool(review_decision.get("allowed", False)) else "rejected",
                "review_reason": str(review_decision.get("reason", "") or ""),
                "review_stage": str(review_decision.get("review_stage", "host_only") or "host_only"),
                "decision": str(review_decision.get("decision", "host_only") or "host_only"),
                "route_result": str(review_decision.get("route_result", "") or ""),
                "risk_level": str(review_decision.get("risk_level", "") or ""),
                "requires_confirm": bool(review_decision.get("requires_confirm", False)),
                "requires_vm_first": bool(review_decision.get("requires_vm_first", False)),
                "host_reserved": bool(review_decision.get("host_reserved", False)),
                "permission_state": str(review_decision.get("permission_state", "") or ""),
                "effective_permission_state": str(review_decision.get("permission_state", "") or ""),
                "request_allowed": bool(review_decision.get("allowed", False)),
                "execution_allowed": bool(result.get("ok", False)),
                "desktop_mode": mode,
                "current_mode": mode,
                "test_backend": "",
                "execution_backend": "host",
                "host_execution_enabled": True,
                "target_environment": str(result_data.get("target_environment", "local_host") or "local_host"),
                "path_namespace": str(result_data.get("path_namespace", "host_windows") or "host_windows"),
            })
            if checkpoint:
                result_data["checkpoint_id"] = str(checkpoint.get("checkpoint_id", "") or "")
            if material:
                result_data["material_id"] = str(material.get("material_id", "") or "")
                result_data["material_status"] = str(material.get("material_status", "") or "")
            result["data"] = result_data
            self._finalize_host_file_quarantine_result(payload, result, material)
            self._finalize_host_open_session_result(payload, result)

            self._record_desktop_result(
                payload,
                result,
                review_decision=review_decision,
                checkpoint=checkpoint,
                material=material or target_material_for_record,
            )
            return result
        result = self._desktop_task_rejected_result(
            payload,
            {
                **review_decision,
                "reason": f"Unsupported execution backend: {effective_backend or '-'}",
                "decision": "deny",
                "review_stage": "menxia_rejected",
            },
            test_backend=effective_backend,
        )
        self._record_desktop_result(payload, result, review_decision=review_decision)
        return result

    def _execute_system_info_read_datetime(self, task: dict) -> dict:
        payload = dict(task or {})
        arguments = payload.get("arguments", {}) if isinstance(payload.get("arguments"), dict) else {}
        locale = str(arguments.get("locale", "") or "zh-CN")
        include_time = self._argument_bool(arguments.get("include_time", True))
        include_date = self._argument_bool(arguments.get("include_date", False))
        include_weekday = self._argument_bool(arguments.get("include_weekday", False))

        now = datetime.now()
        time_text = now.strftime("%H:%M")
        date_text = now.strftime("%Y-%m-%d")
        weekday_text = self._localized_weekday(now.weekday(), locale)
        result_text = self._format_datetime_result(
            locale,
            time_text=time_text,
            date_text=date_text,
            weekday_text=weekday_text,
            include_time=include_time,
            include_date=include_date,
            include_weekday=include_weekday,
        )
        message_params = {
            "result": result_text,
            "datetime": result_text,
            "time": time_text,
            "date": date_text,
            "weekday": weekday_text,
        }
        safe_user_message = DesktopLanguageService().render(
            DesktopLanguageService().load_profile(locale),
            "desktop.system.datetime.done",
            message_params,
        )
        return {
            "ok": True,
            "action": "system_info.read_datetime",
            "status": "system_info_datetime_done",
            "message_key": "desktop.system.datetime.done",
            "message_params": message_params,
            "safe_user_message": safe_user_message,
            "message": safe_user_message,
            "executed": True,
            "data": {
                "current_action": "system_info.read_datetime",
                "status": "system_info_datetime_done",
                "read_only": True,
                "risk_level": "low",
                "capability_group": "system_info",
                "message_key": "desktop.system.datetime.done",
                "message_params": message_params,
                "safe_user_message": safe_user_message,
                "time": time_text,
                "date": date_text,
                "weekday": weekday_text,
            },
        }

    def _system_skill_reserved_result(
        self,
        task: dict,
        *,
        status: str,
        message_key: str,
        capability_group: str,
        risk_level: str,
        executed: bool,
    ) -> dict:
        arguments = (task or {}).get("arguments", {}) if isinstance((task or {}).get("arguments"), dict) else {}
        locale = str(arguments.get("locale", "") or "zh-CN")
        language_service = DesktopLanguageService()
        safe_user_message = language_service.render(
            language_service.load_profile(locale),
            message_key,
            {},
        )
        return {
            "ok": True,
            "action": str((task or {}).get("action", "") or ""),
            "status": status,
            "message_key": message_key,
            "message_params": {},
            "safe_user_message": safe_user_message,
            "message": safe_user_message,
            "executed": bool(executed),
            "data": {
                "current_action": str((task or {}).get("action", "") or ""),
                "status": status,
                "read_only": True,
                "risk_level": risk_level,
                "capability_group": capability_group,
                "message_key": message_key,
                "message_params": {},
                "safe_user_message": safe_user_message,
            },
        }

    def _localized_weekday(self, weekday_index: int, locale: str) -> str:
        normalized = str(locale or "").lower()
        zh = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
        en = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        ja = ["月曜日", "火曜日", "水曜日", "木曜日", "金曜日", "土曜日", "日曜日"]
        table = ja if normalized.startswith("ja") else en if normalized.startswith("en") else zh
        return table[int(weekday_index) % 7]

    def _format_datetime_result(
        self,
        locale: str,
        *,
        time_text: str,
        date_text: str,
        weekday_text: str,
        include_time: bool,
        include_date: bool,
        include_weekday: bool,
    ) -> str:
        normalized = str(locale or "").lower()
        if normalized.startswith("en"):
            parts: list[str] = []
            if include_date:
                parts.append(date_text)
            if include_weekday:
                parts.append(weekday_text)
            if include_time:
                parts.append(time_text)
            return "It is " + ", ".join(parts or [time_text]) + "."
        if normalized.startswith("ja"):
            parts = []
            if include_date:
                parts.append(date_text)
            if include_weekday:
                parts.append(weekday_text)
            if include_time:
                parts.append(f"{time_text[:2]}時{time_text[3:]}分")
            return "現在は" + "、".join(parts or [f"{time_text[:2]}時{time_text[3:]}分"]) + "です。"
        parts = []
        if include_date:
            parts.append(date_text)
        if include_weekday:
            parts.append(weekday_text)
        if include_time:
            parts.append(f"{time_text[:2]}点{time_text[3:]}分")
        return "现在是" + "，".join(parts or [f"{time_text[:2]}点{time_text[3:]}分"]) + "。"

    def _desktop_task_bridge_result(self, task: dict, review_decision: dict, *, test_backend: str) -> dict:
        payload = dict(task or {})
        action = str(payload.get("action", "") or "").strip()
        arguments = payload.get("arguments", {}) if isinstance(payload.get("arguments"), dict) else {}
        target_name = str(payload.get("target_name", "") or "VM bridge").strip()
        request_allowed = bool(review_decision.get("allowed", False))
        vm_route = str(test_backend or "").strip().lower() == "vm"
        desktop_mode = str(arguments.get("desktop_mode", self.mode_store.get_mode_state().current_mode) or "")
        return {
            "ok": request_allowed,
            "action": action,
            "adapter_id": "vm" if vm_route else "sandbox",
            "message": str(review_decision.get("reason", "") or "VM bridge reviewed.").strip(),
            "data": {
                "current_action": action or "-",
                "current_target": target_name,
                "review_result": "approved" if request_allowed else "rejected",
                "review_reason": str(review_decision.get("reason", "") or ""),
                "review_stage": str(review_decision.get("review_stage", "") or ""),
                "decision": str(review_decision.get("decision", "") or ""),
                "risk_level": str(review_decision.get("risk_level", "") or ""),
                "route_result": str(review_decision.get("route_result", "") or ""),
                "permission_state": str(review_decision.get("permission_state", "") or ""),
                "execution_allowed": bool(request_allowed and vm_route),
                "request_allowed": request_allowed,
                "test_backend": str(test_backend or "").strip(),
                "execution_backend": str(test_backend or "").strip(),
                "desktop_mode": desktop_mode,
                "current_mode": desktop_mode,
                "host_execution_enabled": False,
                "adapter_stage": "vm_bridge_review",
            },
        }

    def _review_vm_pre_execution(self, task: dict, review_decision: dict) -> dict:
        session_result = self.session_guard.review(task, review_decision)
        if not bool(session_result.get("allowed", False)):
            return session_result

        throttle_result = self.throttle_guard.review(task, review_decision)
        if not bool(throttle_result.get("allowed", False)):
            return throttle_result

        destructive_result = self.destructive_guard.review(task, review_decision)
        if not bool(destructive_result.get("allowed", False)):
            return destructive_result

        if bool(destructive_result.get("requires_confirm", False)) and bool(destructive_result.get("confirmed", False)):
            self._prepare_host_shaofu_arguments(task)
            try:
                checkpoint = self.checkpoint_registry.create_checkpoint(task, review_decision)
            except Exception as exc:
                return {
                    "allowed": False,
                    "decision": "deny",
                    "review_stage": "libu_checkpoint_failed",
                    "reason": f"Libu checkpoint creation failed: {exc}",
                }
            if not self._should_prepare_shaofu_material(task):
                arguments = (task or {}).get("arguments", {}) if isinstance((task or {}).get("arguments", {}), dict) else {}
                material = {
                    "checkpoint_id": str(checkpoint.get("checkpoint_id", "") or ""),
                    "action": str((task or {}).get("action", "") or ""),
                    "material_type": "none",
                    "material_status": "not_required",
                    "restore_status": "not_required",
                    "verify_status": "not_required",
                    "shaofu_location": "record",
                    "confirm_mode": self._confirm_mode(arguments, execution_backend=str(arguments.get("execution_backend", "") or "")),
                    "retention_policy": "record",
                    "retain_until": "long_term_report",
                    "restore_token": str(arguments.get("restore_token", "") or ""),
                    "data": {"shaofu_skipped": True, "skip_reason": "sandbox_has_no_real_restore_material"},
                }
                return {
                    "allowed": True,
                    "review_stage": "shaofu_material_skipped",
                    "checkpoint": checkpoint,
                    "material": material,
                }
            try:
                material = self.material_policy.prepare_material(task, review_decision, checkpoint)
                self.checkpoint_registry.attach_material(str(checkpoint.get("checkpoint_id", "") or ""), material)
            except Exception as exc:
                material = {
                    "material_status": "failed",
                    "error": str(exc),
                }
                return {
                    "allowed": False,
                    "decision": "deny",
                    "review_stage": "shaofu_material_failed",
                    "reason": f"Shaofu material preparation failed: {exc}",
                    "checkpoint": checkpoint,
                    "material": material,
                }
            if self.material_policy.should_block_for_material(material, review_decision):
                status = str(material.get("material_status", "") or "")
                error = str(material.get("error", "") or "")
                return {
                    "allowed": False,
                    "decision": "deny",
                    "review_stage": "shaofu_missing_strategy" if status == "missing_strategy" else "shaofu_material_failed",
                    "reason": error or f"Shaofu material is not ready: {status or '-'}",
                    "checkpoint": checkpoint,
                    "material": material,
                }
            return {
                "allowed": True,
                "review_stage": "shaofu_material_prepared",
                "checkpoint": checkpoint,
                "material": material,
            }

        return {"allowed": True, "review_stage": "vm_pre_execution_allowed"}

    def _review_host_pre_execution(self, task: dict, review_decision: dict) -> dict:
        """
        Host 真实执行前审查。

        Host 全量开放不是绕过三省六部：
        - 仍经过 session_guard
        - 仍经过 throttle_guard
        - 仍经过 destructive_guard
        - 危险动作需要 confirmed=True
        - 需要少府材料时必须准备
        """
        session_result = self.session_guard.review(task, review_decision)
        if not bool(session_result.get("allowed", False)):
            return session_result

        throttle_result = self.throttle_guard.review(task, review_decision)
        if not bool(throttle_result.get("allowed", False)):
            return throttle_result

        destructive_result = self.destructive_guard.review(task, review_decision)
        if not bool(destructive_result.get("allowed", False)):
            return destructive_result

        if bool(destructive_result.get("requires_confirm", False)) and not bool(destructive_result.get("confirmed", False)):
            return destructive_result

        if bool(destructive_result.get("requires_confirm", False)) and bool(destructive_result.get("confirmed", False)):
            try:
                checkpoint = self.checkpoint_registry.create_checkpoint(task, review_decision)
            except Exception as exc:
                return {
                    "allowed": False,
                    "decision": "deny",
                    "review_stage": "libu_checkpoint_failed",
                    "reason": f"Libu checkpoint creation failed: {exc}",
                }

            try:
                material = self.material_policy.prepare_material(task, review_decision, checkpoint)
                self.checkpoint_registry.attach_material(str(checkpoint.get("checkpoint_id", "") or ""), material)
            except Exception as exc:
                material = {
                    "material_status": "failed",
                    "error": str(exc),
                }
                return {
                    "allowed": False,
                    "decision": "deny",
                    "review_stage": "shaofu_material_failed",
                    "reason": f"Shaofu material preparation failed: {exc}",
                    "checkpoint": checkpoint,
                    "material": material,
                }

            if self.material_policy.should_block_for_material(material, review_decision):
                status = str(material.get("material_status", "") or "")
                error = str(material.get("error", "") or "")
                return {
                    "allowed": False,
                    "decision": "deny",
                    "review_stage": "shaofu_missing_strategy" if status == "missing_strategy" else "shaofu_material_failed",
                    "reason": error or f"Shaofu material is not ready: {status or '-'}",
                    "checkpoint": checkpoint,
                    "material": material,
                }

            return {
                "allowed": True,
                "review_stage": "shaofu_material_prepared",
                "checkpoint": checkpoint,
                "material": material,
            }

        action = str((task or {}).get("action", "") or "").strip().lower()
        if action in {"file.close", "folder.close"}:
            self._prepare_host_close_arguments(task)
        if action in {"file.restore", "folder.restore"}:
            material, error = self._resolve_restore_material_for_task(task)
            if material is None:
                return {
                    "allowed": False,
                    "decision": "deny",
                    "review_stage": "shaofu_restore_material_missing",
                    "reason": error or "Restore material not found.",
                    "material": {"error": error or "material_not_found"},
                }
            try:
                checkpoint = self.checkpoint_registry.create_checkpoint(task, review_decision)
                self.checkpoint_registry.attach_material(str(checkpoint.get("checkpoint_id", "") or ""), material)
            except Exception:
                checkpoint = None
            return {
                "allowed": True,
                "review_stage": "shaofu_restore_material_ready",
                "checkpoint": checkpoint if isinstance(checkpoint, dict) else None,
                "material": material,
            }

        checkpoint_material_actions = {
            "app.uninstall",
            "app.move",
            "app.relocate",
            "app.update",
            "file.create",
            "folder.create",
            "file.delete",
            "folder.delete",
            "file.move",
            "folder.move",
            "file.rename",
            "folder.rename",
            "file.copy",
            "file.mkdir",
            "folder.mkdir",
            "file.touch",
        }
        if self._should_prepare_shaofu_material(task) and action in checkpoint_material_actions:
            self._prepare_host_shaofu_arguments(task)
            try:
                checkpoint = self.checkpoint_registry.create_checkpoint(task, review_decision)
            except Exception as exc:
                return {
                    "allowed": False,
                    "decision": "deny",
                    "review_stage": "libu_checkpoint_failed",
                    "reason": f"Libu checkpoint creation failed: {exc}",
                }

            try:
                material = self.material_policy.prepare_material(task, review_decision, checkpoint)
                self.checkpoint_registry.attach_material(str(checkpoint.get("checkpoint_id", "") or ""), material)
            except Exception as exc:
                material = {
                    "material_status": "failed",
                    "error": str(exc),
                }
                return {
                    "allowed": False,
                    "decision": "deny",
                    "review_stage": "shaofu_material_failed",
                    "reason": f"Shaofu material preparation failed: {exc}",
                    "checkpoint": checkpoint,
                    "material": material,
                }

            if self.material_policy.should_block_for_material(material, review_decision):
                status = str(material.get("material_status", "") or "")
                error = str(material.get("error", "") or "")
                return {
                    "allowed": False,
                    "decision": "deny",
                    "review_stage": "shaofu_missing_strategy" if status == "missing_strategy" else "shaofu_material_failed",
                    "reason": error or f"Shaofu material is not ready: {status or '-'}",
                    "checkpoint": checkpoint,
                    "material": material,
                }

            return {
                "allowed": True,
                "review_stage": "shaofu_material_prepared",
                "checkpoint": checkpoint,
                "material": material,
            }

        return {
            "allowed": True,
            "review_stage": "host_pre_execution_allowed",
        }

    def _prepare_host_close_arguments(self, task: dict) -> None:
        payload = task if isinstance(task, dict) else {}
        action = str(payload.get("action", "") or "").strip().lower()
        if action not in {"file.close", "folder.close"}:
            return
        arguments = payload.get("arguments", {}) if isinstance(payload.get("arguments"), dict) else {}
        arguments = dict(arguments)
        session = self.open_session_service.find_session(
            session_id=str(arguments.get("session_id", "") or ""),
            target_path=str(payload.get("target_path", arguments.get("target_path", "")) or ""),
            close_action=action,
        )
        if session:
            arguments["open_session_owned"] = True
            for key in (
                "session_id",
                "open_method",
                "process_name",
                "pid",
                "hwnd",
                "window_title",
                "close_strategy",
                "target_path",
                "target_type",
                "run_id",
                "run_backend",
            ):
                value = session.get(key, "")
                if value not in (None, ""):
                    arguments[key] = value
            payload["target_path"] = str(session.get("target_path", payload.get("target_path", "")) or "")
            payload["target_type"] = str(session.get("target_type", payload.get("target_type", "")) or "")
        if action == "folder.close":
            arguments.setdefault("close_scope", "all_matching_path")
            target_path = str(payload.get("target_path", arguments.get("target_path", "")) or "")
            if target_path:
                arguments["target_path"] = target_path
        payload["arguments"] = arguments

    def _prepare_host_app_close_material(self, task: dict) -> dict[str, Any]:
        payload = task if isinstance(task, dict) else {}
        action = str(payload.get("action", "") or "").strip().lower()
        if action != "app.close":
            return {
                "schema_version": "target_material_v1",
                "action": action,
                "target_material_source": "heibingtai",
                "resolution_status": "unsupported_action",
                "execution_allowed_by_material": False,
                "safe_user_message": "Heibingtai app close material is only for app.close.",
            }
        try:
            from services.desktop.qin.heibingtai.target_material_service import TargetMaterialService

            return TargetMaterialService(self.project_root).build_target_material(payload)
        except Exception as exc:
            return {
                "schema_version": "target_material_v1",
                "action": "app.close",
                "target_material_source": "heibingtai",
                "close_plan": {},
                "resolution_status": "not_found",
                "candidates": [],
                "needs_user_choice": False,
                "execution_allowed_by_material": False,
                "safe_user_message": f"Heibingtai app close material failed: {exc}",
            }

    def _prepare_host_app_launch_candidate(self, task: dict) -> dict[str, Any]:
        payload = task if isinstance(task, dict) else {}
        action = str(payload.get("action", "") or "").strip().lower()
        arguments = payload.get("arguments", {}) if isinstance(payload.get("arguments"), dict) else {}
        selected = (
            arguments.get("selected_candidate")
            if isinstance(arguments.get("selected_candidate"), dict)
            else arguments.get("app_launch_selected_candidate")
            if isinstance(arguments.get("app_launch_selected_candidate"), dict)
            else None
        )
        if action != "app.launch":
            return {
                "schema_version": "target_candidate_result_v1",
                "action": action,
                "resolution_status": "unsupported_action",
                "candidates": [],
                "selected_candidate": None,
                "safe_user_message": "吏部 app.launch 候选补全只处理 app.launch。",
            }
        if isinstance(selected, dict):
            permission = str(
                selected.get("effective_permission_state", selected.get("permission_state", "unset"))
                or "unset"
            ).strip().lower()
            if permission == "restricted":
                permission = "once"
            if permission in {"allow", "once"}:
                return {
                    "schema_version": "target_candidate_result_v1",
                    "action": "app.launch",
                    "resolution_status": "resolved_unique",
                    "candidates": [selected],
                    "selected_candidate": selected,
                    "safe_user_message": f"已选择软件“{selected.get('label', '目标软件')}”，将交给秦链审议执行。",
                    "debug_summary": {"source": "selected_candidate"},
                }
            return {
                "schema_version": "target_candidate_result_v1",
                "action": "app.launch",
                "resolution_status": "need_permission",
                "candidates": [selected],
                "selected_candidate": selected,
                "safe_user_message": f"我找到了“{selected.get('label', '目标软件')}”，但它还没有被授权执行。请先在桌面配置的软件区将它设置为允许或受限。",
                "debug_summary": {"permission_state": permission},
            }
        try:
            from services.desktop.qin.libu.target_candidate_service import resolve_app_launch_target

            return resolve_app_launch_target(payload, project_root=self.project_root)
        except Exception as exc:
            return {
                "schema_version": "target_candidate_result_v1",
                "action": "app.launch",
                "resolution_status": "not_found",
                "candidates": [],
                "selected_candidate": None,
                "safe_user_message": f"软件候选解析失败，已阻止启动：{exc}",
                "debug_summary": {"error": str(exc)},
            }

    def _app_close_task_has_governed_target(self, task: dict) -> bool:
        payload = task if isinstance(task, dict) else {}
        arguments = payload.get("arguments", {}) if isinstance(payload.get("arguments"), dict) else {}

        permission = str(
            arguments.get(
                "effective_permission_state",
                arguments.get("permission_state", "unset"),
            )
            or "unset"
        ).strip().lower()

        if permission == "restricted":
            permission = "once"

        if permission not in {"allow", "once"}:
            return False

        return bool(
            str(arguments.get("app_id", payload.get("target_id", "")) or "").strip()
            or str(arguments.get("target_name", payload.get("target_name", "")) or "").strip()
            or str(arguments.get("target_label", "") or "").strip()
        )

    def _prepare_host_app_close_permission_candidate(self, task: dict) -> dict[str, Any]:
        """
        app.close 的 ReviewGate 前置权限补齐。

        注意：
        - 这里只补软件治理区静态材料；
        - 不在这里关闭窗口；
        - 不在这里生成 close_plan；
        - close_plan 仍然必须由黑冰台 TargetMaterialService / AppClosePlanner 生成。
        """
        payload = dict(task or {})
        arguments = payload.get("arguments", {}) if isinstance(payload.get("arguments"), dict) else {}

        selected = (
            arguments.get("selected_candidate")
            if isinstance(arguments.get("selected_candidate"), dict)
            else arguments.get("app_close_selected_candidate")
            if isinstance(arguments.get("app_close_selected_candidate"), dict)
            else None
        )

        # 1. 如果来自纠察司 / pending 的 selected_candidate 是轻量候选，
        #    先尝试用软件治理区 row 补齐权限、app_id、process_name。
        if isinstance(selected, dict):
            enriched = self._app_close_enrich_selected_candidate_from_governance(payload, selected)
            permission = self._normalize_app_close_permission(
                enriched.get("effective_permission_state", enriched.get("permission_state", "unset"))
            )

            if permission in {"allow", "once"}:
                return {
                    "schema_version": "target_candidate_result_v1",
                    "action": "app.close",
                    "resolution_status": "resolved_unique",
                    "candidates": [enriched],
                    "selected_candidate": enriched,
                    "safe_user_message": f"已匹配到要关闭的软件“{enriched.get('label', '目标软件')}”，将进入黑冰台安全关闭流程。",
                    "message_key": "desktop.app.close.plan_ready",
                    "message_params": {
                        "target": str(enriched.get("label", "") or enriched.get("target_name", "") or "目标软件"),
                        "candidate_count": 1,
                    },
                    "debug_summary": {
                        "source": "selected_candidate_enriched_from_governance",
                        "permission_state": permission,
                        "close_plan_generated": False,
                    },
                }

            if permission == "deny":
                print(
                    "[AppClosePermissionBridge] permission_denied "
                    f"hint={str(selected.get('label', '') or selected.get('target_label', '') or '')!r} "
                    f"permission={permission!r}"
                )
                return {
                    "schema_version": "target_candidate_result_v1",
                    "action": "app.close",
                    "resolution_status": "need_permission",
                    "candidates": [enriched],
                    "selected_candidate": enriched,
                    "safe_user_message": f"我找到了“{enriched.get('label', '目标软件')}”，但它还没有被授权关闭。请先在桌面配置的软件区将它设置为允许或受限。",
                    "message_key": "desktop.app.close.blocked",
                    "message_params": {
                        "target": str(enriched.get("label", "") or enriched.get("target_name", "") or "目标软件"),
                        "candidate_count": 1,
                    },
                    "debug_summary": {
                        "permission_state": permission,
                        "close_plan_generated": False,
                    },
                }

            # 如果还是 unset，不要立刻阻断。
            # 继续走软件治理区候选解析兜底。
            print(
                "[AppClosePermissionBridge] governance_match_missing "
                f"hint={str(selected.get('label', '') or selected.get('target_label', '') or '')!r}"
            )

        # 2. 没有 selected_candidate，或者 selected_candidate 无法补齐时，
        #    复用 app.launch 的软件治理区候选能力做“关闭对象权限补齐”。
        try:
            from services.desktop.qin.libu.target_candidate_service import resolve_app_launch_target

            lookup_task = dict(payload)
            lookup_task["action"] = "app.launch"

            lookup_arguments = lookup_task.get("arguments", {}) if isinstance(lookup_task.get("arguments"), dict) else {}
            lookup_arguments = dict(lookup_arguments)
            lookup_arguments["close_permission_lookup_only"] = True
            lookup_task["arguments"] = lookup_arguments

            result = resolve_app_launch_target(lookup_task, project_root=self.project_root)
            result = dict(result)
            result["action"] = "app.close"

            selected_candidate = result.get("selected_candidate")
            label = ""
            if isinstance(selected_candidate, dict):
                selected_candidate = self._app_close_enrich_selected_candidate_from_governance(
                    payload,
                    selected_candidate,
                )
                result["selected_candidate"] = selected_candidate
                result["candidates"] = [selected_candidate]
                label = str(
                    selected_candidate.get("label", "")
                    or selected_candidate.get("target_name", "")
                    or ""
                ).strip()

            message_params = result.get("message_params", {}) if isinstance(result.get("message_params"), dict) else {}
            message_params = dict(message_params)
            if label and not str(message_params.get("target", "") or "").strip():
                message_params["target"] = label
            result["message_params"] = message_params

            status = str(result.get("resolution_status", "") or "")
            permission = "unset"
            if isinstance(selected_candidate, dict):
                permission = self._normalize_app_close_permission(
                    selected_candidate.get(
                        "effective_permission_state",
                        selected_candidate.get("permission_state", "unset"),
                    )
                )

            if status == "resolved_unique" and permission in {"allow", "once"}:
                result["safe_user_message"] = f"已匹配到要关闭的软件“{label or '目标软件'}”，将进入黑冰台安全关闭流程。"
                result["message_key"] = "desktop.app.close.plan_ready"

            elif status == "resolved_unique" and permission not in {"allow", "once"}:
                result["resolution_status"] = "need_permission"
                result["safe_user_message"] = f"我找到了“{label or '目标软件'}”，但它还没有被授权关闭。请先在桌面配置的软件区将它设置为允许或受限。"
                result["message_key"] = "desktop.app.close.blocked"

            elif status == "need_permission":
                result["safe_user_message"] = f"我找到了“{label or '目标软件'}”，但它还没有被授权关闭。请先在桌面配置的软件区将它设置为允许或受限。"
                result["message_key"] = "desktop.app.close.blocked"

            elif status == "not_found":
                result["safe_user_message"] = "我没有在软件治理区找到要关闭的软件，请先确认软件名称或刷新软件列表。"
                result["message_key"] = "desktop.app.close.not_found"

            elif status == "need_clarification":
                result["safe_user_message"] = "请说明要关闭哪个软件。"
                result["message_key"] = "desktop.app.close.need_clarification"

            elif status in {"multiple_candidates", "need_confirmation"}:
                result["safe_user_message"] = result.get("safe_user_message") or "我找到了可能的软件，请确认要关闭哪一个。"
                result["message_key"] = "desktop.app.close.pending_choice"

            debug = result.get("debug_summary", {}) if isinstance(result.get("debug_summary"), dict) else {}
            debug = dict(debug)
            debug["source"] = "app_close_permission_lookup_via_libu"
            debug["close_plan_generated"] = False
            debug["permission_state"] = permission
            result["debug_summary"] = debug

            return result

        except Exception as exc:
            return {
                "schema_version": "target_candidate_result_v1",
                "action": "app.close",
                "resolution_status": "not_found",
                "candidates": [],
                "selected_candidate": None,
                "safe_user_message": f"关闭目标权限解析失败，已阻止关闭：{exc}",
                "message_key": "desktop.app.close.not_found",
                "message_params": {"target": str(payload.get("target_name", "") or "")},
                "debug_summary": {"error": str(exc)},
            }

    def _app_close_enrich_selected_candidate_from_governance(
        self,
        task: dict,
        selected_candidate: dict[str, Any],
    ) -> dict[str, Any]:
        selected = selected_candidate if isinstance(selected_candidate, dict) else {}
        hints = self._app_close_governance_hints(task, selected)
        if not hints:
            print("[AppClosePermissionBridge] governance_match_missing hint=''")
            return {}

        rows = self._read_software_governance_rows()
        for hint in hints:
            normalized_hint = self._normalize_exact_app_label(hint)
            if not normalized_hint:
                continue
            matched = None
            for row in rows:
                title = str(row.get("title", "") or "").strip()
                if not title:
                    continue
                if title == hint or self._normalize_exact_app_label(title) == normalized_hint:
                    matched = row
                    break
            if not isinstance(matched, dict):
                continue

            permission = self._normalize_app_close_permission(
                matched.get(
                    "effective_permission_state",
                    matched.get("permission_state_raw", matched.get("permission_state", "unset")),
                )
            )
            selected_label = str(matched.get("title", "") or selected.get("label", "") or hint).strip()
            if permission in {"deny", "unset", "unknown", ""}:
                print(
                    "[AppClosePermissionBridge] permission_denied "
                    f"hint={hint!r} permission={permission!r}"
                )
                enriched = dict(selected)
                enriched.update({
                    "label": str(selected.get("label", "") or selected_label),
                    "target_name": str(selected.get("target_name", "") or selected_label),
                    "target_label": str(selected.get("target_label", "") or selected_label),
                    "app_id": str(matched.get("app_id", selected.get("app_id", "")) or ""),
                    "canonical_app_id": str(matched.get("canonical_app_id", selected.get("canonical_app_id", "")) or ""),
                    "permission_state": permission,
                    "effective_permission_state": permission,
                    "permission_source_type": str(matched.get("permission_source_type", "software_governance") or "software_governance"),
                    "permission_source_key": str(matched.get("permission_source_key", matched.get("app_id", "")) or ""),
                    "source": "software_governance_exact_for_close",
                })
                return enriched

            process_name = str(
                matched.get("process_name", "")
                or self._process_name_from_path(str(matched.get("effective_target_path", matched.get("target_path", "")) or ""))
                or ""
            ).strip()
            process_names = matched.get("process_names", [])
            if not isinstance(process_names, list):
                process_names = []
            if process_name and process_name not in process_names:
                process_names = [process_name, *process_names]

            enriched = dict(selected)
            enriched.update({
                "label": str(selected.get("label", "") or selected_label),
                "name": str(selected.get("name", "") or selected_label),
                "target_name": str(selected.get("target_name", "") or selected_label),
                "target_label": str(selected.get("target_label", "") or selected_label),
                "title": selected_label,
                "app_id": str(matched.get("app_id", selected.get("app_id", "")) or ""),
                "canonical_app_id": str(matched.get("canonical_app_id", selected.get("canonical_app_id", "")) or ""),
                "target_path": str(matched.get("effective_target_path", matched.get("target_path", selected.get("target_path", ""))) or ""),
                "launch_target_raw": str(matched.get("effective_launch_target_raw", matched.get("launch_target_raw", "")) or ""),
                "process_name": process_name,
                "process_names": process_names,
                "permission_state": permission,
                "effective_permission_state": permission,
                "permission_source": str(matched.get("_source", matched.get("permission_source", "software_governance")) or "software_governance"),
                "permission_source_type": str(matched.get("permission_source_type", "software_governance") or "software_governance"),
                "permission_source_key": str(matched.get("permission_source_key", matched.get("app_id", "")) or ""),
                "source": "software_governance_exact_for_close",
            })
            print(
                "[AppClosePermissionBridge] exact_governance_match "
                f"hint={hint!r} selected={selected_label!r} permission={permission!r}"
            )
            print(
                "[AppClosePermissionBridge] permission_ready_for_heibingtai "
                f"target={selected_label!r} permission={permission!r}"
            )
            return enriched

        print(f"[AppClosePermissionBridge] governance_match_missing hint={hints[0]!r}")
        return {}

    def _app_close_governance_hints(self, task: dict, selected_candidate: dict[str, Any]) -> list[str]:
        payload = task if isinstance(task, dict) else {}
        selected = selected_candidate if isinstance(selected_candidate, dict) else {}
        arguments = payload.get("arguments", {}) if isinstance(payload.get("arguments"), dict) else {}
        target = payload.get("target", {}) if isinstance(payload.get("target"), dict) else {}
        values: list[str] = []

        def add(value: Any) -> None:
            text = str(value or "").strip()
            if text and text not in values:
                values.append(text)

        for key in ("target_label", "label", "name", "target_name"):
            add(selected.get(key, ""))
        for key in ("target_label_hint", "llm_target_hint", "app_hint", "app_name", "target_name"):
            add(arguments.get(key, ""))
        for key in ("label_hint", "app_hint", "name_hint"):
            add(target.get(key, ""))
        add(payload.get("target_name", ""))
        return values

    def _read_software_governance_rows(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        try:
            from services.desktop.software_view_cache_service import SoftwareViewCacheService

            state = SoftwareViewCacheService(self.project_root).read()
            cache_rows = state.get("rows", []) if isinstance(state.get("rows", []), list) else []
            for row in cache_rows:
                if isinstance(row, dict):
                    item = dict(row)
                    item.setdefault("_source", "software_view_cache")
                    rows.append(item)
        except Exception:
            pass
        if rows:
            return rows
        try:
            from services.desktop.qin.libu.software_ledger import SoftwareCandidateBook, SoftwareTrustedBook

            for source, book in (
                ("software_trusted_book", SoftwareTrustedBook(self.project_root)),
                ("software_candidate_book", SoftwareCandidateBook(self.project_root)),
            ):
                for record in book.read():
                    item = record.to_dict()
                    item["_source"] = source
                    rows.append(item)
        except Exception:
            pass
        return rows

    def _normalize_exact_app_label(self, value: Any) -> str:
        return "".join(str(value or "").strip().casefold().split())

    def _normalize_app_close_permission(self, value: Any) -> str:
        text = str(value or "unset").strip().lower() or "unset"
        if text in {"allow", "once", "deny", "unset", "unknown"}:
            return text
        if text == "restricted":
            return "once"
        if text in {"\u662f", "\u5141\u8bb8"}:
            return "allow"
        if text in {"\u53d7\u9650"}:
            return "once"
        if text in {"\u5426", "\u62d2\u7edd"}:
            return "deny"
        return "unknown"

    def _process_name_from_path(self, path_text: str) -> str:
        try:
            name = Path(str(path_text or "")).name
            return name if name.lower().endswith(".exe") else ""
        except Exception:
            return ""

    def _inject_app_close_permission_candidate(self, task: dict, candidate: dict[str, Any]) -> None:
        """
        app.close 的软件治理区候选注入。

        这里不执行关闭，只把治理区候选补齐后交给黑冰台。
        """
        payload = task if isinstance(task, dict) else {}
        item = candidate if isinstance(candidate, dict) else {}

        arguments = payload.get("arguments", {}) if isinstance(payload.get("arguments"), dict) else {}
        arguments = dict(arguments)

        enriched_candidate = dict(item)

        label = str(
            enriched_candidate.get("label", "")
            or enriched_candidate.get("target_label", "")
            or enriched_candidate.get("target_name", "")
            or enriched_candidate.get("title", "")
            or payload.get("target_name", "")
            or ""
        ).strip()

        if label:
            enriched_candidate.setdefault("label", label)
            enriched_candidate.setdefault("name", label)
            enriched_candidate.setdefault("target_name", label)
            enriched_candidate.setdefault("target_label", label)
            enriched_candidate.setdefault("title", label)

        permission = self._normalize_app_close_permission(
            enriched_candidate.get(
                "effective_permission_state",
                enriched_candidate.get("permission_state", "unset"),
            )
        )

        enriched_candidate["permission_state"] = permission
        enriched_candidate["effective_permission_state"] = permission
        enriched_candidate["source"] = str(
            enriched_candidate.get("source", "")
            or "software_governance_exact_for_close"
        )

        process_name = str(enriched_candidate.get("process_name", "") or "").strip()
        process_names = enriched_candidate.get("process_names", [])
        if not isinstance(process_names, list):
            process_names = []

        if process_name and process_name not in process_names:
            process_names = [process_name, *process_names]

        values = {
            "app_id": enriched_candidate.get("app_id", ""),
            "canonical_app_id": enriched_candidate.get("canonical_app_id", ""),
            "target_name": label,
            "target_label": label,
            "target_path": enriched_candidate.get("target_path", ""),
            "launch_target_raw": enriched_candidate.get("launch_target_raw", ""),
            "process_name": process_name,
            "process_names": process_names,
            "permission_state": permission,
            "effective_permission_state": permission,
            "permission_source": enriched_candidate.get("permission_source", ""),
            "permission_source_type": enriched_candidate.get("permission_source_type", "software_governance"),
            "permission_source_key": enriched_candidate.get(
                "permission_source_key",
                enriched_candidate.get("app_id", ""),
            ),
            "candidate_source": "libu_app_close_permission_lookup",
            "request_allowed": True,
            "app_close_permission_checked": True,
            "app_close_permission_candidate_label": label,
        }

        for key, value in values.items():
            if value not in (None, ""):
                arguments[key] = value

        # 关键：
        # 只有“运行态候选”才允许写入 selected_candidate / app_close_selected_candidate。
        # 治理区静态候选只能作为补材线索，不能让 TargetMaterialService 跳过 AppTargetResolver。
        if self._app_close_candidate_has_runtime_material(enriched_candidate):
            arguments["selected_candidate"] = enriched_candidate
            arguments["app_close_selected_candidate"] = enriched_candidate
            arguments["target_material_selected_candidate"] = enriched_candidate
        else:
            arguments.pop("selected_candidate", None)
            arguments.pop("app_close_selected_candidate", None)
            arguments.pop("target_material_selected_candidate", None)

        arguments["app_close_governed_candidate"] = enriched_candidate
        arguments["target_material_governance_candidate"] = enriched_candidate

        # 关键：不要保留 permission_only。
        # 权限补齐后必须继续进入黑冰台 close_plan。
        arguments.pop("app_close_permission_only", None)

        payload["arguments"] = arguments

        if label and not str(payload.get("target_name", "") or "").strip():
            payload["target_name"] = label

        if not str(payload.get("target_id", "") or "").strip():
            payload["target_id"] = str(enriched_candidate.get("app_id", "") or "")

        payload["target_type"] = "app"

    def _inject_app_launch_candidate(self, task: dict, candidate: dict[str, Any]) -> None:
        payload = task if isinstance(task, dict) else {}
        item = candidate if isinstance(candidate, dict) else {}
        arguments = payload.get("arguments", {}) if isinstance(payload.get("arguments"), dict) else {}
        arguments = dict(arguments)

        permission = str(item.get("effective_permission_state", item.get("permission_state", "unset")) or "unset").strip().lower()
        if permission == "restricted":
            permission = "once"
        for key, value in {
            "app_id": item.get("app_id", ""),
            "canonical_app_id": item.get("canonical_app_id", ""),
            "target_name": item.get("label", ""),
            "target_label": item.get("label", ""),
            "target_path": item.get("target_path", ""),
            "shell_entry": item.get("shell_entry", ""),
            "launch_target_raw": item.get("launch_target_raw", item.get("shell_entry", "")),
            "launch_target_kind": item.get("launch_target_kind", ""),
            "process_name": item.get("process_name", ""),
            "process_names": item.get("process_names", []),
            "permission_state": permission,
            "effective_permission_state": permission,
            "permission_source": item.get("permission_source", ""),
            "permission_source_type": item.get("permission_source_type", "software_governance"),
            "permission_source_key": item.get("permission_source_key", item.get("app_id", "")),
            "candidate_source": "libu_target_candidate_service",
            "request_allowed": True,
        }.items():
            if value not in (None, ""):
                arguments[key] = value

        payload["target_name"] = str(item.get("label", payload.get("target_name", "")) or "")
        payload["target_path"] = str(item.get("target_path", payload.get("target_path", "")) or "")
        payload["target_type"] = "app"
        payload["target_id"] = str(item.get("app_id", payload.get("target_id", "")) or "")
        payload["arguments"] = arguments

    def _app_launch_task_has_governed_target(self, task: dict) -> bool:
        payload = task if isinstance(task, dict) else {}
        arguments = payload.get("arguments", {}) if isinstance(payload.get("arguments"), dict) else {}
        permission = str(
            arguments.get("effective_permission_state", arguments.get("permission_state", "unset"))
            or "unset"
        ).strip().lower()
        if permission == "restricted":
            permission = "once"
        if permission not in {"allow", "once"}:
            return False
        return bool(
            str(arguments.get("app_id", payload.get("target_id", "")) or "").strip()
            and (
                str(arguments.get("launch_target_raw", "") or "").strip()
                or str(arguments.get("target_path", payload.get("target_path", "")) or "").strip()
            )
        )

    def _app_launch_pending_choice_result(self, task: dict, candidate_result: dict[str, Any]) -> dict[str, Any]:
        pending_task_id = ""
        resolution_status = str(candidate_result.get("resolution_status", "") or "multiple_candidates")
        choice_type = str(candidate_result.get("choice_type", "") or "")
        if not choice_type:
            choice_type = "app_launch_confirmation" if resolution_status == "need_confirmation" else "app_launch_candidate"
        result_status = "app_launch_need_confirmation" if resolution_status == "need_confirmation" else "app_launch_pending_user_choice"
        ui_prompt_type = str(candidate_result.get("ui_prompt_type", "") or ("confirm_or_choose" if resolution_status == "need_confirmation" else "choose_one"))
        try:
            from services.desktop.tianting.pending_task_service import create_pending_task

            pending_task = create_pending_task(
                original_action="app.launch",
                original_user_text=str((task or {}).get("target_name", "") or "app.launch"),
                candidates=candidate_result.get("candidates", [])
                if isinstance(candidate_result.get("candidates"), list)
                else [],
                original_task_draft=task if isinstance(task, dict) else {},
                original_puzzle_summary={
                    "raw_user_text": str((task or {}).get("target_name", "") or ""),
                    "action": "app.launch",
                    "source": "qin_runtime_libu",
                },
                choice_type=choice_type,
                selected_candidate=candidate_result.get("selected_candidate", {})
                if isinstance(candidate_result.get("selected_candidate"), dict)
                else {},
                ui_prompt_type=ui_prompt_type,
                message_key=str(candidate_result.get("message_key", "") or ""),
                message_params=candidate_result.get("message_params", {})
                if isinstance(candidate_result.get("message_params"), dict)
                else {},
            )
            pending_task_id = str(pending_task.get("pending_task_id", "") or "")
        except Exception:
            pending_task_id = ""

        receipt_packet = self._build_app_launch_pending_receipt(task, candidate_result, pending_task_id=pending_task_id)
        return {
            "ok": True,
            "action": "app.launch",
            "adapter_id": "libu",
            "message": str(candidate_result.get("safe_user_message", "") or "我找到了多个可能的软件，请选择要打开哪一个。"),
            "data": {
                "current_action": "app.launch",
                "current_target": str((task or {}).get("target_name", "") or "-"),
                "status": result_status,
                "resolution_status": resolution_status,
                "needs_user_choice": True,
                "requires_user_choice": True,
                "pending_task_id": pending_task_id,
                "choice_type": choice_type,
                "ui_prompt_type": ui_prompt_type,
                "ui_actions": candidate_result.get("ui_actions", [])
                if isinstance(candidate_result.get("ui_actions"), list)
                else [],
                "message_key": str(candidate_result.get("message_key", "") or ""),
                "message_params": candidate_result.get("message_params", {})
                if isinstance(candidate_result.get("message_params"), dict)
                else {},
                "execution_allowed": False,
                "candidates": candidate_result.get("candidates", [])
                if isinstance(candidate_result.get("candidates"), list)
                else [],
                "selected_candidate": candidate_result.get("selected_candidate", {})
                if isinstance(candidate_result.get("selected_candidate"), dict)
                else {},
                "receipt_packet": receipt_packet,
            },
        }

    def _app_close_candidate_has_runtime_material(self, candidate: dict[str, Any]) -> bool:
        """
        判断 app.close 候选是否已经是黑冰台运行态候选。

        治理区静态候选通常只有：
        - app_id
        - target_path
        - process_name
        - permission_state

        这些不够直接生成 close_plan。
        必须让 AppTargetResolver 再查运行窗口 / 进程。
        """
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

        if process_name and str(item.get("source", "") or "").find("software_governance") < 0:
            return True

        return False
    def _app_close_permission_pending_result(self, task: dict, candidate_result: dict[str, Any]) -> dict[str, Any]:
        resolution_status = str(candidate_result.get("resolution_status", "") or "multiple_candidates")
        choice_type = "app_close_candidate"
        pending_task_id = ""

        try:
            from services.desktop.tianting.pending_task_service import create_pending_task

            pending_task = create_pending_task(
                original_action="app.close",
                original_user_text=str((task or {}).get("target_name", "") or "app.close"),
                candidates=candidate_result.get("candidates", [])
                if isinstance(candidate_result.get("candidates"), list)
                else [],
                original_task_draft=task if isinstance(task, dict) else {},
                original_puzzle_summary={
                    "raw_user_text": str((task or {}).get("target_name", "") or ""),
                    "action": "app.close",
                    "source": "qin_runtime_libu_app_close_permission",
                },
                choice_type=choice_type,
                selected_candidate=candidate_result.get("selected_candidate", {})
                if isinstance(candidate_result.get("selected_candidate"), dict)
                else {},
                ui_prompt_type="confirm_or_choose" if resolution_status == "need_confirmation" else "choose_one",
                message_key=str(candidate_result.get("message_key", "") or "desktop.app.close.pending_choice"),
                message_params=candidate_result.get("message_params", {})
                if isinstance(candidate_result.get("message_params"), dict)
                else {},
            )
            pending_task_id = str(pending_task.get("pending_task_id", "") or "")
        except Exception:
            pending_task_id = ""

        return {
            "ok": True,
            "action": "app.close",
            "adapter_id": "libu",
            "message": str(candidate_result.get("safe_user_message", "") or "我找到了多个可能的软件，请选择要关闭哪一个。"),
            "data": {
                "current_action": "app.close",
                "current_target": str((task or {}).get("target_name", "") or "-"),
                "status": "app_close_pending_user_choice",
                "resolution_status": resolution_status,
                "needs_user_choice": True,
                "requires_user_choice": True,
                "pending_task_id": pending_task_id,
                "choice_type": choice_type,
                "ui_prompt_type": "confirm_or_choose" if resolution_status == "need_confirmation" else "choose_one",
                "ui_actions": candidate_result.get("ui_actions", [])
                if isinstance(candidate_result.get("ui_actions"), list)
                else [],
                "message_key": str(candidate_result.get("message_key", "") or "desktop.app.close.pending_choice"),
                "message_params": candidate_result.get("message_params", {})
                if isinstance(candidate_result.get("message_params"), dict)
                else {},
                "execution_allowed": False,
                "candidates": candidate_result.get("candidates", [])
                if isinstance(candidate_result.get("candidates"), list)
                else [],
                "selected_candidate": candidate_result.get("selected_candidate", {})
                if isinstance(candidate_result.get("selected_candidate"), dict)
                else {},
            },
        }

    def _app_close_permission_blocked_result(self, task: dict, candidate_result: dict[str, Any]) -> dict[str, Any]:
        status = str(candidate_result.get("resolution_status", "") or "need_permission")
        message_params = candidate_result.get("message_params", {}) if isinstance(candidate_result.get("message_params"), dict) else {}

        mapped_status = {
            "need_permission": "app_close_blocked",
            "not_found": "app_close_not_found",
            "need_clarification": "need_user_clarification",
        }.get(status, f"app_close_{status}")

        message_key = str(candidate_result.get("message_key", "") or "")
        if not message_key:
            message_key = {
                "need_permission": "desktop.app.close.blocked",
                "not_found": "desktop.app.close.not_found",
                "need_clarification": "desktop.generic.need_clarification",
            }.get(status, "desktop.app.close.failed")

        return {
            "ok": False,
            "action": "app.close",
            "adapter_id": "libu",
            "message": str(candidate_result.get("safe_user_message", "") or "关闭对象未满足执行条件。"),
            "message_key": message_key,
            "message_params": message_params,
            "data": {
                "current_action": "app.close",
                "current_target": str((task or {}).get("target_name", "") or message_params.get("target", "-") or "-"),
                "status": mapped_status,
                "resolution_status": status,
                "execution_allowed": False,
                "candidates": candidate_result.get("candidates", [])
                if isinstance(candidate_result.get("candidates"), list)
                else [],
                "message_key": message_key,
                "message_params": message_params,
            },
        }

    def _app_launch_candidate_blocked_result(self, task: dict, candidate_result: dict[str, Any]) -> dict[str, Any]:
        status = str(candidate_result.get("resolution_status", "") or "need_permission")
        if status == "not_found":
            receipt_packet = self._build_app_launch_not_found_receipt(task, candidate_result)
        elif status == "need_clarification":
            receipt_packet = {
                "schema_version": "desktop_receipt_packet_v1",
                "receipt_type": "temporary_ui_receipt",
                "status": "need_user_clarification",
                "action": "app.launch",
                "message_key": "desktop.app.launch.need_clarification",
                "message_params": candidate_result.get("message_params", {})
                if isinstance(candidate_result.get("message_params"), dict)
                else {},
            }
        else:
            receipt_packet = self._build_app_launch_need_permission_receipt(task, candidate_result)
        return {
            "ok": False,
            "action": "app.launch",
            "adapter_id": "libu",
            "message": str(candidate_result.get("safe_user_message", "") or "软件对象未满足执行条件。"),
            "data": {
                "current_action": "app.launch",
                "current_target": str((task or {}).get("target_name", "") or "-"),
                "status": f"app_launch_{status}",
                "resolution_status": status,
                "execution_allowed": False,
                "candidates": candidate_result.get("candidates", [])
                if isinstance(candidate_result.get("candidates"), list)
                else [],
                "receipt_packet": receipt_packet,
            },
        }

    def _build_app_launch_pending_receipt(self, task: dict, candidate_result: dict[str, Any], *, pending_task_id: str) -> dict[str, Any]:
        try:
            from services.desktop.qin.yushitai.receipt_packet_builder import build_app_launch_pending_choice_receipt

            return build_app_launch_pending_choice_receipt(task, candidate_result, pending_task_id=pending_task_id)
        except Exception as exc:
            return {"status": "app_launch_pending_user_choice", "safe_user_message": "我找到了多个可能的软件，请选择要打开哪一个。", "debug_summary": {"error": str(exc)}}

    def _build_app_launch_need_permission_receipt(self, task: dict, candidate_result: dict[str, Any]) -> dict[str, Any]:
        try:
            from services.desktop.qin.yushitai.receipt_packet_builder import build_app_launch_need_permission_receipt

            return build_app_launch_need_permission_receipt(task, candidate_result)
        except Exception as exc:
            return {"status": "app_launch_need_permission", "safe_user_message": str(candidate_result.get("safe_user_message", "") or "目标对象尚未授权执行，请先在桌面配置的软件区设置权限。"), "debug_summary": {"error": str(exc)}}

    def _build_app_launch_not_found_receipt(self, task: dict, candidate_result: dict[str, Any]) -> dict[str, Any]:
        try:
            from services.desktop.qin.yushitai.receipt_packet_builder import build_app_launch_not_found_receipt

            return build_app_launch_not_found_receipt(task, candidate_result)
        except Exception as exc:
            return {"status": "app_launch_not_found", "safe_user_message": str(candidate_result.get("safe_user_message", "") or "我没有在软件治理区找到这个可执行对象。"), "debug_summary": {"error": str(exc)}}

    def _create_app_close_pending_task(self, task: dict, target_material: dict[str, Any]) -> dict[str, Any]:
        payload = task if isinstance(task, dict) else {}
        arguments = payload.get("arguments", {}) if isinstance(payload.get("arguments"), dict) else {}
        candidates = target_material.get("candidates", []) if isinstance(target_material.get("candidates"), list) else []
        original_user_text = str(
            arguments.get("raw_user_text", "")
            or arguments.get("user_text", "")
            or payload.get("target_name", "")
            or "app.close"
        )
        try:
            from services.desktop.tianting.pending_task_service import create_pending_task

            return create_pending_task(
                original_action="app.close",
                original_user_text=original_user_text,
                candidates=candidates,
                original_task_draft=payload,
                original_puzzle_summary={
                    "raw_user_text": original_user_text,
                    "action": "app.close",
                    "source": "qin_runtime_heibingtai",
                },
                choice_type="app_close_candidate",
            )
        except Exception:
            return {}

    def _build_app_close_pending_receipt(
        self,
        task: dict,
        target_material: dict[str, Any],
        *,
        pending_task_id: str,
    ) -> dict[str, Any]:
        try:
            from services.desktop.qin.yushitai.receipt_packet_builder import build_app_close_pending_choice_receipt

            return build_app_close_pending_choice_receipt(
                task,
                target_material,
                pending_task_id=pending_task_id,
            )
        except Exception as exc:
            return {
                "schema_version": "desktop_receipt_packet_v1",
                "receipt_type": "temporary_ui_receipt",
                "status": "app_close_pending_user_choice",
                "action": "app.close",
                "safe_user_message": "Multiple app close candidates require user choice.",
                "llm_rephrase_allowed": True,
                "safe_context_for_llm": {"pending_task_id": pending_task_id},
                "debug_summary": {"error": str(exc)},
            }

    def _prepare_host_shaofu_arguments(self, task: dict) -> None:
        payload = task if isinstance(task, dict) else {}
        action = str(payload.get("action", "") or "").strip().lower()
        if action not in {"file.delete", "folder.delete"}:
            return
        arguments = payload.get("arguments", {}) if isinstance(payload.get("arguments"), dict) else {}
        arguments = dict(arguments)
        if not str(arguments.get("yushitai_run_id", arguments.get("run_id", "")) or "").strip():
            mode = str(arguments.get("desktop_mode", self.mode_store.get_mode_state().current_mode) or "")
            run_id = self._ensure_yushitai_run(
                "host",
                desktop_mode=mode or "trusted",
                test_backend="",
                execution_backend="host",
                host_execution_enabled=True,
            )
            arguments["yushitai_run_id"] = run_id
            arguments["yushitai_run_backend"] = "host"
        target_path = str(payload.get("target_path", arguments.get("target_path", "")) or "").strip()
        arguments.setdefault("source_path", target_path)
        arguments.setdefault("original_path", target_path)
        arguments.setdefault("target_path", target_path)
        arguments.setdefault("target_type", "directory" if action == "folder.delete" else "file")
        payload["arguments"] = arguments

    def _resolve_restore_material_for_task(self, task: dict) -> tuple[dict[str, Any] | None, str]:
        payload = task if isinstance(task, dict) else {}
        arguments = payload.get("arguments", {}) if isinstance(payload.get("arguments"), dict) else {}
        material, error = self.file_quarantine_service.material_for_restore(arguments)
        if material is None:
            return None, error
        original_path = str(material.get("original_path", material.get("source_path", "")) or "").strip()
        quarantine_path = str(material.get("quarantine_path", "") or "").strip()
        arguments = dict(arguments)
        for key in (
            "material_id",
            "checkpoint_id",
            "restore_token",
            "target_type",
            "run_id",
            "run_backend",
            "manifest_path",
        ):
            value = material.get(key, "")
            if value not in (None, ""):
                arguments[key] = value
        arguments["original_path"] = original_path
        arguments["source_path"] = original_path
        arguments["target_path"] = original_path
        arguments["quarantine_path"] = quarantine_path
        arguments["execution_backend"] = "host"
        arguments["executed_in"] = "host"
        payload["target_path"] = original_path
        payload["target_name"] = str(payload.get("target_name", "") or Path(original_path).name)
        payload["target_type"] = str(material.get("target_type", payload.get("target_type", "")) or "")
        payload["arguments"] = arguments
        return material, ""

    def _finalize_host_file_quarantine_result(
        self,
        task: dict,
        result: dict,
        material: dict[str, Any] | None,
    ) -> None:
        if not isinstance(result, dict) or not bool(result.get("ok", False)):
            return
        payload = task if isinstance(task, dict) else {}
        action = str(payload.get("action", result.get("action", "")) or "").strip().lower()
        if action not in {"file.delete", "folder.delete", "file.restore", "folder.restore"}:
            return
        data = result.get("data", {}) if isinstance(result.get("data", {}), dict) else {}
        material_data = dict(material or {})
        if not material_data:
            material_data = self.file_quarantine_service.find_material(
                restore_token=str(data.get("restore_token", "") or ""),
                material_id=str(data.get("material_id", "") or ""),
                quarantine_path=str(data.get("quarantine_path", "") or ""),
            ) or {}
        if not material_data:
            return
        try:
            if action in {"file.delete", "folder.delete"}:
                updated = self.file_quarantine_service.mark_quarantined(material_data, data)
            else:
                updated = self.file_quarantine_service.mark_restored(material_data, data)
        except Exception as exc:
            result_data = dict(data)
            result_data["shaofu_update_error"] = str(exc)
            result["data"] = result_data
            return
        result_data = dict(data)
        for key in (
            "material_id",
            "checkpoint_id",
            "restore_token",
            "run_id",
            "run_backend",
            "original_path",
            "quarantine_path",
            "restore_action",
            "manifest_path",
            "target_type",
            "status",
            "material_status",
            "restore_status",
        ):
            value = updated.get(key, "")
            if value not in (None, ""):
                result_data[key] = value
        result["data"] = result_data

    def _finalize_host_open_session_result(self, task: dict, result: dict) -> None:
        if not isinstance(result, dict):
            return
        payload = task if isinstance(task, dict) else {}
        action = str(payload.get("action", result.get("action", "")) or "").strip().lower()
        if action not in {"file.open", "folder.open", "file.close", "folder.close"}:
            return
        data = result.get("data", {}) if isinstance(result.get("data", {}), dict) else {}
        result_data = dict(data)
        arguments = payload.get("arguments", {}) if isinstance(payload.get("arguments"), dict) else {}
        target_path = str(result_data.get("target_path", payload.get("target_path", arguments.get("target_path", ""))) or "")
        if action in {"file.open", "folder.open"}:
            if not bool(result.get("ok", False)):
                return
            run_id = self._ensure_yushitai_run(
                "host",
                desktop_mode=str(arguments.get("desktop_mode", self.mode_store.get_mode_state().current_mode) or "trusted"),
                test_backend="",
                execution_backend="host",
                host_execution_enabled=True,
            )
            session = self.open_session_service.record_open({
                **result_data,
                "action": action,
                "target_path": target_path,
                "target_type": str(result_data.get("target_type", payload.get("target_type", "")) or ""),
                "run_id": run_id,
                "run_backend": "host",
            })
            for key in (
                "session_id",
                "material_id",
                "open_method",
                "pid",
                "hwnd",
                "window_title",
                "close_action",
                "close_strategy",
                "run_id",
                "run_backend",
            ):
                value = session.get(key, "")
                if value not in (None, ""):
                    result_data[key] = value
            result["data"] = result_data
            return

        close_data = dict(result_data)
        close_data["close_succeeded"] = bool(result.get("ok", False))
        if action == "folder.close":
            run_id = self._ensure_yushitai_run(
                "host",
                desktop_mode=str(arguments.get("desktop_mode", self.mode_store.get_mode_state().current_mode) or "trusted"),
                test_backend="",
                execution_backend="host",
                host_execution_enabled=True,
            )
            close_data.setdefault("run_id", run_id)
            close_data.setdefault("run_backend", "host")
            target_origin = str(result_data.get("target_origin", arguments.get("target_origin", "auto")) or "auto").strip().lower()
            if target_origin in {"registered", "mixed"}:
                updated_sessions = self.open_session_service.mark_close_for_path(
                    target_path=target_path,
                    result_data=close_data,
                    close_action="folder.close",
                )
            else:
                updated_sessions = []
            result_data["open_session_updates"] = len(updated_sessions)
            result_data["closed_session_ids"] = [
                str(item.get("session_id", "") or "")
                for item in updated_sessions
                if str(item.get("session_id", "") or "")
            ]
            if updated_sessions:
                updated = updated_sessions[0]
                for key in (
                    "session_id",
                    "material_id",
                    "status",
                    "close_error",
                    "closed_at",
                    "close_attempted_at",
                    "close_strategy",
                    "run_id",
                    "run_backend",
                ):
                    value = updated.get(key, "")
                    if value not in (None, ""):
                        result_data[key] = value
            result["data"] = result_data
            return

        session = self.open_session_service.find_session(
            session_id=str(result_data.get("session_id", arguments.get("session_id", "")) or ""),
            target_path=target_path,
            close_action=action,
        )
        if not session:
            return
        updated = self.open_session_service.mark_close(session, close_data)
        for key in (
            "session_id",
            "material_id",
            "status",
            "closed_at",
            "close_attempted_at",
            "close_strategy",
            "pid",
            "hwnd",
            "window_title",
            "run_id",
            "run_backend",
        ):
            value = updated.get(key, "")
            if value not in (None, ""):
                result_data[key] = value
        result["data"] = result_data

    def _should_prepare_shaofu_material(self, task: dict) -> bool:
        payload = dict(task or {})
        arguments = payload.get("arguments", {}) if isinstance(payload.get("arguments"), dict) else {}
        execution_backend = str(
            arguments.get("execution_backend", arguments.get("test_backend", payload.get("test_backend", ""))) or ""
        ).strip().lower()
        target_environment = str(arguments.get("target_environment", "") or "").strip().lower()
        path_namespace = str(arguments.get("path_namespace", "") or "").strip().lower()
        if execution_backend == "sandbox" or target_environment == "sandbox_simulation" or path_namespace == "sandbox":
            return False
        return (
            execution_backend in {"vm", "host"}
            or target_environment in {"virtual_machine", "local_host", "host_machine"}
            or path_namespace in {"vm_windows", "host_windows"}
        )

    def execute_v2_sandbox(self, task: dict) -> dict:
        payload = dict(task or {})
        action = str(payload.get("action", "")).strip()
        mode = self.mode_store.get_mode_state().current_mode
        policy = get_review_policy(mode)
        arguments = payload.get("arguments", {}) if isinstance(payload.get("arguments"), dict) else {}
        permission_state = (
            str(arguments.get("effective_permission_state", arguments.get("permission_state", "unset")))
            .strip()
            .lower()
            or "unset"
        )
        permission_source_type = str(arguments.get("permission_source_type", "")).strip().lower()
        permission_source_key = str(arguments.get("permission_source_key", "")).strip()
        target_name = str(payload.get("target_name", "")).strip() or str(payload.get("target_path", "")).strip() or "-"
        target_path = str(payload.get("target_path", "")).strip()
        target_type = str(payload.get("target_type", "")).strip() or "object"

        review_decision = self.review_gate.review_v25_task(payload, mode)
        route_result = str(review_decision.get("route_result", "")).strip() or self._route_v2_action(action)

        if (
            bool(review_decision.get("allowed", False))
            and target_path
            and route_result.startswith("sandbox.file")
            and action != "file.disk_rescan"
        ):
            whitelist_result = self._validate_task_against_roots({
                "action": "filesystem.path_meta",
                "target_path": target_path,
                "root_id": str(payload.get("root_id", "")).strip(),
            })
            if whitelist_result:
                review_decision = dict(review_decision)
                review_decision.update({
                    "allowed": False,
                    "decision": "deny",
                    "reason": whitelist_result,
                    "review_stage": "menxia_rejected",
                    "consume_permission": False,
                })

        request_allowed = bool(review_decision.get("allowed", False))
        ui_effect_hint = arguments.get("apply_ui_allowed", action == "file.navigate")
        ui_effect_allowed = bool(
            request_allowed
            and action == "file.navigate"
            and self._argument_bool(ui_effect_hint)
        )
        consume_permission = bool(review_decision.get("consume_permission", False))

        executor_result: dict[str, Any] | None = None
        if request_allowed:
            executor_task = dict(payload)
            executor_task.update({
                "adapter_id": "sandbox",
                "route_result": route_result,
                "review_stage": str(review_decision.get("review_stage", "sandbox_only")).strip() or "sandbox_only",
                "request_allowed": request_allowed,
                "ui_effect_allowed": ui_effect_allowed,
                "consume_permission": consume_permission,
                "permission_state": permission_state,
                "effective_permission_state": permission_state,
            })
            executor_result = self.executor.execute(executor_task)

        result = self._build_v25_compatible_result(
            payload=payload,
            policy_mode=str(policy["mode"]),
            review_decision=review_decision,
            executor_result=executor_result,
            route_result=route_result,
            permission_state=permission_state,
            permission_source_type=permission_source_type,
            permission_source_key=permission_source_key,
            request_allowed=request_allowed,
            ui_effect_allowed=ui_effect_allowed,
            consume_permission=consume_permission,
            target_name=target_name,
            target_path=target_path,
            target_type=target_type,
        )
        self._audit_v25_result(result)
        return result

    def _build_v25_compatible_result(
        self,
        *,
        payload: dict[str, Any],
        policy_mode: str,
        review_decision: dict[str, Any],
        executor_result: dict[str, Any] | None,
        route_result: str,
        permission_state: str,
        permission_source_type: str,
        permission_source_key: str,
        request_allowed: bool,
        ui_effect_allowed: bool,
        consume_permission: bool,
        target_name: str,
        target_path: str,
        target_type: str,
    ) -> dict:
        action = str(payload.get("action", "")).strip()
        arguments = payload.get("arguments", {}) if isinstance(payload.get("arguments"), dict) else {}
        executor_data = (
            executor_result.get("data", {})
            if isinstance(executor_result, dict) and isinstance(executor_result.get("data", {}), dict)
            else {}
        )
        review_reason = str(review_decision.get("reason", "")).strip()
        sandbox_text = "本次为 V2.5 沙盒测试，未真实执行。"
        sandbox_text = {
            "app.uninstall": "V2.5 危险动作沙盒模拟，未真实卸载。",
            "app.move": "V2.5 危险动作沙盒模拟，未真实移动。",
            "app.relocate": "V2.5 危险动作沙盒模拟，未真实迁移。",
            "app.update": "V2.5 危险动作沙盒模拟，未真实更新。",
        }.get(action, "本次为 V2.5 沙盒测试，未真实执行。")
        ok = bool(request_allowed and (executor_result is None or executor_result.get("ok", False)))
        adapter_id = (
            str(executor_result.get("adapter_id", "")).strip()
            if isinstance(executor_result, dict)
            else ""
        ) or "sandbox"
        message = (
            str(executor_result.get("message", "")).strip()
            if isinstance(executor_result, dict)
            else ""
        ) or sandbox_text

        target_object = {
            "name": target_name,
            "path": target_path or "-",
            "type": target_type,
            "root_id": str(payload.get("root_id", "")).strip() or "-",
            "target_id": str(payload.get("target_id", "")).strip(),
        }
        if isinstance(executor_data.get("target_object"), dict):
            merged_target = dict(executor_data["target_object"])
            merged_target.update({key: value for key, value in target_object.items() if value})
            target_object = merged_target

        data = {
            "current_action": action or "-",
            "current_target": target_name,
            "current_mode": policy_mode,
            "desktop_mode": str(arguments.get("desktop_mode", policy_mode) or policy_mode),
            "execution_backend": str(arguments.get("execution_backend", "none") or "none"),
            "host_execution_enabled": self._argument_bool(arguments.get("host_execution_enabled", False)),
            "review_result": "通过" if request_allowed else "拒绝",
            "review_reason": review_reason,
            "route_result": route_result,
            "permission_state": permission_state,
            "effective_permission_state": permission_state,
            "request_allowed": request_allowed,
            "ui_effect_allowed": ui_effect_allowed,
            "execution_allowed": False,
            "consume_permission": consume_permission,
            "governed_scope": self._governed_scope_for_action(action),
            "review_stage": str(review_decision.get("review_stage", "sandbox_only" if request_allowed else "menxia_rejected")),
            "permission_source_type": permission_source_type,
            "permission_source_key": permission_source_key,
            "target_object": target_object,
            "sandbox_text": sandbox_text,
            "decision": str(review_decision.get("decision", "")),
            "risk_level": str(review_decision.get("risk_level", "")),
            "requires_vm_first": bool(review_decision.get("requires_vm_first", False)),
            "host_reserved": bool(review_decision.get("host_reserved", False)),
        }
        data.update({
            key: value
            for key, value in executor_data.items()
            if key not in {"target_object", "execution_allowed", "request_allowed", "ui_effect_allowed", "consume_permission"}
        })
        data["execution_allowed"] = False
        data["request_allowed"] = request_allowed
        data["ui_effect_allowed"] = ui_effect_allowed
        data["consume_permission"] = consume_permission
        data["sandbox_text"] = sandbox_text

        return {
            "ok": ok,
            "action": action,
            "adapter_id": adapter_id,
            "message": message,
            "data": data,
        }

    def _audit_v25_result(self, result: dict) -> None:
        try:
            data = result.get("data", {}) if isinstance(result.get("data", {}), dict) else {}
            target = data.get("target_object", {}) if isinstance(data.get("target_object", {}), dict) else {}
            self.audit_ledger.record(
                event_type="v25_desktop_sandbox",
                action=str(result.get("action", "")).strip(),
                backend="sandbox",
                department="hubu",
                target=target,
                decision=str(data.get("decision", data.get("review_stage", ""))).strip(),
                route_result=str(data.get("route_result", "")).strip(),
                adapter_id=str(result.get("adapter_id", "")).strip(),
                reason=str(data.get("review_reason", "")).strip(),
                data={
                    "mode": data.get("current_mode", ""),
                    "ok": bool(result.get("ok", False)),
                    "review_result": data.get("review_result", ""),
                    "permission_state": data.get("permission_state", ""),
                    "permission_source_type": data.get("permission_source_type", ""),
                    "permission_source_key": data.get("permission_source_key", ""),
                },
            )
        except Exception:
            return

    def _desktop_task_rejected_result(self, task: dict, review_decision: dict, *, test_backend: str) -> dict:
        payload = dict(task or {})
        action = str(payload.get("action", "")).strip()
        arguments = payload.get("arguments", {}) if isinstance(payload.get("arguments"), dict) else {}
        target_name = str(payload.get("target_name", "") or payload.get("target_path", "") or payload.get("target_id", "") or "-")
        reason = str(review_decision.get("reason", "") or "Desktop task rejected.").strip()
        execution_backend = str(arguments.get("execution_backend", test_backend) or test_backend).strip()
        desktop_mode = str(arguments.get("desktop_mode", self.mode_store.get_mode_state().current_mode) or "").strip()
        return {
            "ok": False,
            "action": action,
            "adapter_id": str(test_backend or "").strip() or "",
            "message": reason,
            "data": {
                "current_action": action or "-",
                "current_target": target_name,
                "review_result": "rejected",
                "review_reason": reason,
                "review_stage": str(review_decision.get("review_stage", "menxia_rejected") or "menxia_rejected"),
                "decision": str(review_decision.get("decision", "deny") or "deny"),
                "risk_level": str(review_decision.get("risk_level", "") or ""),
                "route_result": str(review_decision.get("route_result", "") or ""),
                "permission_state": str(review_decision.get("permission_state", "") or ""),
                "execution_allowed": False,
                "request_allowed": False,
                "desktop_mode": desktop_mode,
                "current_mode": desktop_mode,
                "host_execution_enabled": self._argument_bool(arguments.get("host_execution_enabled", False)),
                "test_backend": str(test_backend or "").strip(),
                "execution_backend": execution_backend,
                "target_environment": str(arguments.get("target_environment", "") or "").strip(),
                "path_namespace": str(arguments.get("path_namespace", "") or "").strip(),
                "shaofu_location": str(arguments.get("shaofu_location", "") or "").strip(),
                "confirm_mode": self._confirm_mode(arguments, execution_backend=execution_backend),
                "retention_policy": str(arguments.get("retention_policy", "") or "").strip(),
                "retain_until": str(arguments.get("retain_until", "") or "").strip(),
                "restore_token": str(arguments.get("restore_token", "") or "").strip(),
                "machine_id": str(arguments.get("machine_id", "") or "").strip(),
                "agent_id": str(arguments.get("agent_id", "") or "").strip(),
            },
        }

    def _normalize_desktop_result(
        self,
        task: dict,
        result: dict,
        *,
        review_decision: dict | None = None,
    ) -> None:
        payload = dict(task or {})
        arguments = payload.get("arguments", {}) if isinstance(payload.get("arguments"), dict) else {}
        review = dict(review_decision or {})
        data = result.get("data", {}) if isinstance(result.get("data", {}), dict) else {}
        data = dict(data)

        action = str(result.get("action", payload.get("action", data.get("action", data.get("current_action", "")))) or "").strip()
        adapter_id = str(
            result.get("adapter_id", data.get("adapter_id", payload.get("adapter_id", arguments.get("adapter_id", "")))) or ""
        ).strip()
        target_path = str(
            data.get(
                "target_path",
                payload.get(
                    "target_path",
                    arguments.get("target_path", data.get("path", arguments.get("source_path", ""))),
                ),
            )
            or ""
        ).strip()
        error = str(result.get("error", data.get("error", "")) or "").strip()
        message = str(result.get("message", "") or "").strip()
        backend = self._resolve_desktop_record_backend(payload, result)

        if not adapter_id and backend in {"host", "vm", "sandbox"}:
            adapter_id = "host_windows" if backend == "host" else backend
        if backend in {"host", "vm", "sandbox"}:
            if not str(data.get("execution_backend", "") or "").strip():
                data["execution_backend"] = backend
            if not str(data.get("executed_in", "") or "").strip():
                data["executed_in"] = backend

        data.update({
            "action": str(data.get("action", "") or action),
            "current_action": str(data.get("current_action", "") or action or "-"),
            "adapter_id": str(data.get("adapter_id", "") or adapter_id),
            "target_path": target_path,
            "error": error,
            "review_result": str(
                data.get("review_result", "approved" if bool(review.get("allowed", False)) else "rejected")
                or ""
            ),
            "review_stage": str(data.get("review_stage", review.get("review_stage", "")) or ""),
            "route_result": str(data.get("route_result", review.get("route_result", "")) or ""),
        })

        result.update({
            "ok": bool(result.get("ok", False)),
            "action": action,
            "adapter_id": adapter_id,
            "message": message,
            "error": error,
            "data": data,
        })

    def _record_desktop_result(
        self,
        task: dict,
        result: dict,
        *,
        review_decision: dict | None = None,
        checkpoint: dict[str, Any] | None = None,
        material: dict[str, Any] | None = None,
    ) -> None:
        payload = dict(task or {})
        if not isinstance(result, dict):
            return
        self._normalize_desktop_result(payload, result, review_decision=review_decision)
        data = result.get("data", {}) if isinstance(result.get("data", {}), dict) else {}
        if bool(data.get("yushitai_recorded", False)):
            return
        arguments = payload.get("arguments", {}) if isinstance(payload.get("arguments"), dict) else {}
        review = dict(review_decision or {})
        desktop_mode = str(arguments.get("desktop_mode", self.mode_store.get_mode_state().current_mode) or "").strip()
        backend = str(arguments.get("test_backend", data.get("test_backend", data.get("executed_in", ""))) or "").strip()
        execution_backend = str(data.get("execution_backend", arguments.get("execution_backend", backend)) or backend).strip()
        record_backend = self._resolve_desktop_record_backend(payload, result, execution_backend=execution_backend)
        if record_backend == "sandbox":
            return
        if record_backend not in {"host", "vm"}:
            return
        target_environment = str(arguments.get("target_environment", "") or data.get("target_environment", "") or "").strip()
        path_namespace = str(arguments.get("path_namespace", "") or data.get("path_namespace", "") or "").strip()
        confirm_mode = self._confirm_mode(arguments, execution_backend=execution_backend)
        shaofu_location = str(
            arguments.get("shaofu_location", data.get("shaofu_location", (material or {}).get("shaofu_location", ""))) or ""
        ).strip()
        retention_policy = str(
            arguments.get("retention_policy", data.get("retention_policy", (material or {}).get("retention_policy", ""))) or ""
        ).strip()
        retain_until = str(arguments.get("retain_until", data.get("retain_until", (material or {}).get("retain_until", ""))) or "").strip()
        restore_token = str(
            arguments.get("restore_token", data.get("restore_token", (material or {}).get("restore_token", ""))) or ""
        ).strip()
        machine_id = str(data.get("machine_id", arguments.get("machine_id", "")) or "").strip()
        agent_id = str(data.get("agent_id", arguments.get("agent_id", "")) or "").strip()
        action = str(result.get("action", payload.get("action", "")) or "").strip()
        department = self._department_for_stage(str(data.get("review_stage", review.get("review_stage", "")) or ""))
        event = {
            "event_type": "desktop_action_result",
            "action": action,
            "backend": record_backend,
            "desktop_mode": desktop_mode,
            "execution_backend": execution_backend,
            "executed_in": record_backend,
            "target_environment": target_environment,
            "path_namespace": path_namespace,
            "machine_id": machine_id,
            "agent_id": agent_id,
            "department": department,
            "target": {
                "id": str(payload.get("target_id", arguments.get("app_id", "")) or ""),
                "name": str(data.get("current_target", payload.get("target_name", "-")) or "-"),
                "path": str(data.get("target_path", payload.get("target_path", arguments.get("target_path", ""))) or ""),
                "type": str(payload.get("target_type", "") or ""),
            },
            "decision": str(data.get("decision", review.get("decision", "")) or ""),
            "route_result": str(data.get("route_result", review.get("route_result", "")) or ""),
            "adapter_id": str(result.get("adapter_id", "") or ""),
            "reason": str(data.get("review_reason", data.get("error", result.get("message", ""))) or ""),
            "message": str(result.get("message", "") or ""),
            "error": str(result.get("error", data.get("error", "")) or ""),
            "ok": bool(result.get("ok", False)),
            "target_path": str(data.get("target_path", payload.get("target_path", arguments.get("target_path", ""))) or ""),
            "session_id": str(data.get("session_id", arguments.get("session_id", "")) or ""),
            "close_strategy": str(data.get("close_strategy", arguments.get("close_strategy", "")) or ""),
            "heibingtai_enabled": bool(data.get("heibingtai_enabled", False)),
            "close_family": str(data.get("close_family", "") or ""),
            "close_level": str(data.get("close_level", "") or ""),
            "target_origin": str(data.get("target_origin", "") or ""),
            "requires_user_choice": bool(data.get("requires_user_choice", False)),
            "document_adapter": str(data.get("document_adapter", "") or ""),
            "document_adapter_stage": str(data.get("document_adapter_stage", "") or ""),
            "document_fullname": str(data.get("document_fullname", "") or ""),
            "document_saved": data.get("document_saved", ""),
            "save_state": str(data.get("save_state", "") or ""),
            "requires_user_save_confirmation": bool(data.get("requires_user_save_confirmation", False)),
            "close_error": str(data.get("close_error", data.get("error", "")) or ""),
            "close_scope": str(data.get("close_scope", arguments.get("close_scope", "")) or ""),
            "matched_count": data.get("matched_count", 0),
            "closed_count": data.get("closed_count", 0),
            "skipped_count": data.get("skipped_count", 0),
            "failed_hwnds": data.get("failed_hwnds", []),
            "skip_reasons": data.get("skip_reasons", {}),
            "material_id": str(data.get("material_id", (material or {}).get("material_id", "")) or ""),
            "checkpoint_id": str(data.get("checkpoint_id", (checkpoint or {}).get("checkpoint_id", "")) or ""),
            "restore_token": str(data.get("restore_token", arguments.get("restore_token", (material or {}).get("restore_token", ""))) or ""),
            "quarantine_path": str(data.get("quarantine_path", arguments.get("quarantine_path", (material or {}).get("quarantine_path", ""))) or ""),
            "review_result": str(data.get("review_result", "approved" if bool(review.get("allowed", False)) else "rejected") or ""),
            "review_stage": str(data.get("review_stage", review.get("review_stage", "")) or ""),
            "review": review,
            "result": {
                "ok": bool(result.get("ok", False)),
                "message": str(result.get("message", "") or ""),
                "adapter_id": str(result.get("adapter_id", "") or ""),
                "executed_in": str(data.get("executed_in", record_backend) or record_backend),
                "http_status": data.get("http_status", ""),
                "error": str(result.get("error", data.get("error", "")) or ""),
            },
            "checkpoint": checkpoint or {},
            "material": material or {},
            "data": {
                "ok": bool(result.get("ok", False)),
                "current_action": action,
                "current_target": str(data.get("current_target", payload.get("target_name", "-")) or "-"),
                "review_result": str(data.get("review_result", "approved" if bool(review.get("allowed", False)) else "rejected") or ""),
                "review_stage": data.get("review_stage", ""),
                "route_result": str(data.get("route_result", review.get("route_result", "")) or ""),
                "adapter_id": str(result.get("adapter_id", "") or ""),
                "executed_in": record_backend,
                "risk_level": data.get("risk_level", review.get("risk_level", "")),
                "desktop_mode": desktop_mode,
                "current_mode": desktop_mode,
                "host_execution_enabled": self._argument_bool(arguments.get("host_execution_enabled", False)),
                "test_backend": backend,
                "execution_backend": execution_backend,
                "target_environment": target_environment,
                "path_namespace": path_namespace,
                "shaofu_location": shaofu_location,
                "confirm_mode": confirm_mode,
                "retention_policy": retention_policy,
                "retain_until": retain_until,
                "restore_token": restore_token,
                "session_id": str(data.get("session_id", arguments.get("session_id", "")) or ""),
                "close_strategy": str(data.get("close_strategy", arguments.get("close_strategy", "")) or ""),
                "heibingtai_enabled": bool(data.get("heibingtai_enabled", False)),
                "close_family": str(data.get("close_family", "") or ""),
                "close_level": str(data.get("close_level", "") or ""),
                "target_origin": str(data.get("target_origin", "") or ""),
                "requires_user_choice": bool(data.get("requires_user_choice", False)),
                "document_adapter": str(data.get("document_adapter", "") or ""),
                "document_adapter_stage": str(data.get("document_adapter_stage", "") or ""),
                "document_fullname": str(data.get("document_fullname", "") or ""),
                "document_saved": data.get("document_saved", ""),
                "save_state": str(data.get("save_state", "") or ""),
                "requires_user_save_confirmation": bool(data.get("requires_user_save_confirmation", False)),
                "close_error": str(data.get("close_error", data.get("error", "")) or ""),
                "close_scope": str(data.get("close_scope", arguments.get("close_scope", "")) or ""),
                "matched_count": data.get("matched_count", 0),
                "closed_count": data.get("closed_count", 0),
                "skipped_count": data.get("skipped_count", 0),
                "original_path": str(arguments.get("original_path", data.get("original_path", (material or {}).get("original_path", ""))) or ""),
                "quarantine_path": str(arguments.get("quarantine_path", data.get("quarantine_path", (material or {}).get("quarantine_path", ""))) or ""),
                "target_path": str(data.get("target_path", payload.get("target_path", arguments.get("target_path", ""))) or ""),
                "source_path": str(arguments.get("source_path", data.get("source_path", "")) or ""),
                "dest_path": str(arguments.get("dest_path", data.get("dest_path", "")) or ""),
                "old_path": str(arguments.get("old_path", data.get("old_path", "")) or ""),
                "new_path": str(arguments.get("new_path", data.get("new_path", "")) or ""),
                "old_name": str(arguments.get("old_name", data.get("old_name", "")) or ""),
                "new_name": str(arguments.get("new_name", data.get("new_name", "")) or ""),
                "root_id": str(arguments.get("root_id", payload.get("root_id", data.get("root_id", ""))) or ""),
                "relative_path": str(arguments.get("relative_path", payload.get("relative_path", data.get("relative_path", ""))) or ""),
                "request_id": str(data.get("request_id", arguments.get("request_id", payload.get("request_id", ""))) or ""),
                "checkpoint_id": str(data.get("checkpoint_id", "") or (checkpoint or {}).get("checkpoint_id", "") or ""),
                "material_id": str(data.get("material_id", "") or (material or {}).get("material_id", "") or ""),
                "machine_id": machine_id,
                "agent_id": agent_id,
                "move_mode": arguments.get("move_mode", data.get("move_mode", "")),
                "relocate_strategy": arguments.get("relocate_strategy", data.get("relocate_strategy", "")),
            },
            "raw": {"task": payload, "result": result},
        }
        run_id = ""
        try:
            run_id = self._ensure_yushitai_run(
                record_backend,
                desktop_mode=desktop_mode,
                test_backend=backend if record_backend == "vm" else "",
                execution_backend=record_backend,
                host_execution_enabled=self._argument_bool(arguments.get("host_execution_enabled", False)) or record_backend == "host",
            )
            self.event_store.append(event)
            result_data = dict(data)
            result_data.update({
                "yushitai_recorded": True,
                "yushitai_run_backend": record_backend,
                "yushitai_run_id": run_id,
            })
            result["data"] = result_data
        except Exception:
            pass
        try:
            self.audit_ledger.append(event)
        except Exception:
            pass
        try:
            ReportWriter(self.project_root).generate_report(
                stage="v3_v4_desktop_test",
                runtime_state={
                    "desktop_mode": desktop_mode,
                    "test_backend": backend,
                    "current_mode": desktop_mode,
                    "execution_backend": record_backend,
                    "host_execution_enabled": self._argument_bool(arguments.get("host_execution_enabled", False)) or record_backend == "host",
                },
            )
        except Exception:
            pass

    def _resolve_desktop_record_backend(self, task: dict, result: dict, *, execution_backend: str = "") -> str:
        payload = dict(task or {})
        arguments = payload.get("arguments", {}) if isinstance(payload.get("arguments"), dict) else {}
        data = result.get("data", {}) if isinstance(result.get("data", {}), dict) else {}
        candidates = (
            execution_backend or data.get("execution_backend", ""),
            data.get("executed_in", ""),
            data.get("adapter_stage", ""),
            result.get("adapter_id", data.get("adapter_id", payload.get("adapter_id", ""))),
            arguments.get("execution_backend", ""),
        )
        for raw in candidates:
            value = str(raw or "").strip().lower()
            if value in {"host", "host_windows"}:
                return "host"
            if value == "vm":
                return "vm"
            if value == "sandbox":
                return "sandbox"
        return "none"

    def _ensure_yushitai_run(
        self,
        backend: str,
        *,
        desktop_mode: str,
        test_backend: str,
        execution_backend: str,
        host_execution_enabled: bool,
    ) -> str:
        normalized_backend = str(backend or "").strip().lower()
        if normalized_backend not in {"host", "vm"}:
            return ""
        meta = ReportWriter(self.project_root).ensure_session_run(
            run_backend=normalized_backend,
            desktop_mode=desktop_mode or ("trusted" if normalized_backend == "host" else "test"),
            test_backend=test_backend or ("vm" if normalized_backend == "vm" else ""),
            execution_backend=execution_backend or normalized_backend,
            host_execution_enabled=bool(host_execution_enabled or normalized_backend == "host"),
        )
        return str(meta.get("run_id", "") or "")

    def _audit_desktop_task_result(self, result: dict) -> None:
        try:
            data = result.get("data", {}) if isinstance(result.get("data", {}), dict) else {}
            self.audit_ledger.record(
                event_type="desktop_task",
                action=str(result.get("action", "")).strip(),
                backend=str(data.get("test_backend", data.get("executed_in", "")) or ""),
                department="hubu",
                target={"name": data.get("current_target", "-")},
                decision=str(data.get("decision", data.get("review_stage", ""))).strip(),
                route_result=str(data.get("route_result", "")).strip(),
                adapter_id=str(result.get("adapter_id", "")).strip(),
                reason=str(data.get("review_reason", data.get("error", ""))).strip(),
                data={
                    "ok": bool(result.get("ok", False)),
                    "review_stage": data.get("review_stage", ""),
                    "risk_level": data.get("risk_level", ""),
                    "test_backend": data.get("test_backend", data.get("executed_in", "")),
                },
            )
        except Exception:
            return

    def _attach_guard_data(self, result: dict, guard_result: dict) -> None:
        data = result.get("data", {}) if isinstance(result.get("data"), dict) else {}
        checkpoint = guard_result.get("checkpoint") if isinstance(guard_result.get("checkpoint"), dict) else {}
        material = guard_result.get("material") if isinstance(guard_result.get("material"), dict) else {}
        if checkpoint:
            data["checkpoint_id"] = str(checkpoint.get("checkpoint_id", "") or "")
        if material:
            data["material_id"] = str(material.get("material_id", "") or "")
            data["material_status"] = str(material.get("material_status", "") or "")
            data["material_error"] = str(material.get("error", "") or "")
            data["error"] = data.get("error") or data["material_error"]
        result["data"] = data

    def _confirm_mode(self, arguments: dict[str, Any], *, execution_backend: str = "") -> str:
        explicit = str((arguments or {}).get("confirm_mode", "") or "").strip().lower()
        if explicit in {"none", "vm_auto_confirm", "user_confirmed", "user_rejected"}:
            return explicit
        if self._argument_bool((arguments or {}).get("vm_auto_confirm", False)):
            return "vm_auto_confirm"
        if self._argument_bool((arguments or {}).get("confirmed", False)):
            return "user_confirmed"
        return "none"

    def _department_for_stage(self, stage: str) -> str:
        normalized = str(stage or "").strip().lower()
        if normalized.startswith("menxia"):
            return "menxia"
        if normalized.startswith("bingbu"):
            return "bingbu"
        if normalized.startswith("xingbu"):
            return "xingbu"
        if normalized.startswith("libu"):
            return "libu"
        if normalized.startswith("shaofu"):
            return "shaofu"
        if normalized.startswith("vm") or normalized.startswith("gongbu"):
            return "gongbu"
        return "qin_runtime"

    def _validate_task_against_roots(self, task: dict) -> str | None:
        action = str((task or {}).get("action", "")).strip()
        if action == "system_info.read_datetime":
            return None

        target_path = str((task or {}).get("target_path", "")).strip()
        if not target_path:
            return "缺少 target_path"

        root_id = str((task or {}).get("root_id", "")).strip().lower()
        roots = self.local_registry.read_roots_local()
        enabled_roots = [item for item in roots if bool(item.get("enabled", False))]
        if not enabled_roots:
            return "当前没有可用的根目录白名单。"

        normalized_target = Path(target_path).expanduser().resolve(strict=False)
        if root_id:
            matched_root = next(
                (
                    item for item in enabled_roots
                    if str(item.get("root_id", "")).strip().lower() == root_id
                ),
                None,
            )
            if matched_root is None:
                return f"根目录白名单中不存在对象: {root_id}"
            if not self._is_path_under_root(normalized_target, matched_root):
                return "目标路径不在指定根目录白名单范围内。"
            return None

        for item in enabled_roots:
            if self._is_path_under_root(normalized_target, item):
                return None
        return "目标路径不在根目录白名单范围内。"

    def _is_path_under_root(self, target_path: Path, root_item: dict[str, Any]) -> bool:
        root_path = str(root_item.get("path", "")).strip()
        if not root_path:
            return False
        try:
            normalized_root = Path(root_path).expanduser().resolve(strict=False)
            target_path.relative_to(normalized_root)
            return True
        except Exception:
            return False

    def _route_v2_action(self, action: str) -> str:
        if action.startswith("file."):
            return "sandbox.file_governance"
        if action.startswith("app."):
            return "sandbox.software_governance"
        return "sandbox.unknown"

    def _governed_scope_for_action(self, action: str) -> str:
        normalized_action = str(action or "").strip().lower()
        if normalized_action == "file.disk_rescan":
            return "scan_governance"
        if normalized_action.startswith("file."):
            return "file_governance"
        if normalized_action.startswith("app."):
            return "software_governance"
        return "unknown"

    def _argument_bool(self, value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return value != 0
        return str(value or "").strip().lower() in {"1", "true", "yes", "y", "on"}

    def _review_v2_action(self, mode: str, action: str, *, permission_state: str) -> tuple[bool, str]:
        normalized_action = str(action or "").strip().lower()
        if mode == "disabled":
            return False, "当前模式为不启用，V2 沙盒测试未开放。"

        normalized_permission = str(permission_state or "unset").strip().lower() or "unset"
        if normalized_permission == "deny":
            return False, "当前对象权限为禁止，已在 V2 沙盒审议阶段拦截。"
        if normalized_permission == "unset":
            return False, "当前对象权限为未设置，需要先调整为允许或仅一次后才能进入 V2 沙盒测试。"

        file_actions = {"file.navigate", "file.inspect", "file.open", "file.disk_rescan"}
        software_actions = {"app.locate", "app.launch", "app.close"}

        if normalized_action in file_actions:
            return True, "文件治理动作已通过 V2 沙盒审议。"
        if normalized_action in software_actions:
            if mode != "trusted":
                return False, "限制模式下软件治理区不进入可操作态。"
            return True, "软件治理动作已通过 V2 沙盒审议。"
        return False, f"不支持的 V2 沙盒动作: {normalized_action or '-'}"

    def _error_result(self, action: str, message: str) -> dict:
        return {
            "ok": False,
            "action": action,
            "adapter_id": "",
            "message": str(message or "").strip() or "执行失败",
            "data": {},
        }
