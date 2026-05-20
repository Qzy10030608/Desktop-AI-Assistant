from __future__ import annotations

from typing import Any, Dict

from services.desktop.qin.menxia.review_policy import get_review_policy
from services.desktop.qin.zongzheng.action_catalog import get_action, route_for_v25
from services.desktop.qin.zongzheng.decision_vocabulary import (
    DECISION_DENY,
    DECISION_SANDBOX_ONLY,
    DECISION_VM_ONLY,
)
from services.desktop.qin.zongzheng.risk_model import get_action_risk_profile

READONLY_ACTIONS = frozenset({
    "system_info.read_datetime",
    "weather.read_current",
    "calendar.read_events",
    "filesystem.list_dir",
    "filesystem.path_meta",
    "explorer.open_directory",
})

VALID_PERMISSION_STATES = frozenset({"allow", "once"})
VALID_ONCE_SOURCE_TYPES = frozenset({"root", "object", "app", "disk"})

VM_BRIDGE_ACTIONS = frozenset({
    "vm.connect",
    "vm.health_check",
    "vm.list_apps",
    "vm.list_files",
    "vm.cleanup",
})


class ReviewGate:
    """三省六部：门下省审议入口。"""

    def review_mode(self, mode: str) -> Dict[str, Any]:
        policy = get_review_policy(mode)
        allowed = policy["scope"] != "deny"
        return {
            "allowed": allowed,
            "mode": policy["mode"],
            "scope": policy["scope"],
            "reason": policy["reason"],
        }

    def review_readonly_action(self, mode: str, action: str) -> Dict[str, Any]:
        policy = get_review_policy(mode)
        normalized_action = str(action or "").strip().lower()

        if not policy["allow_readonly_actions"]:
            return {
                "allowed": False,
                "mode": policy["mode"],
                "action": normalized_action,
                "reason": "Readonly desktop actions are not enabled in the current mode.",
            }

        if normalized_action not in READONLY_ACTIONS:
            return {
                "allowed": False,
                "mode": policy["mode"],
                "action": normalized_action,
                "reason": "This action is not in the V1 readonly action allowlist.",
            }

        return {
            "allowed": True,
            "mode": policy["mode"],
            "action": normalized_action,
            "reason": "Readonly action accepted.",
        }

    def review_basic_object(self, mode: str, object_id: str, *, object_type: str = "root") -> Dict[str, Any]:
        policy = get_review_policy(mode)
        normalized_object_id = str(object_id or "").strip().lower()
        normalized_type = str(object_type or "root").strip().lower() or "root"

        if normalized_type == "root":
            if normalized_object_id and policy["show_roots"]:
                return {
                    "allowed": True,
                    "mode": policy["mode"],
                    "object_type": normalized_type,
                    "object_id": normalized_object_id,
                    "reason": "Root object accepted.",
                }

            return {
                "allowed": False,
                "mode": policy["mode"],
                "object_type": normalized_type,
                "object_id": normalized_object_id,
                "reason": "Root object is unavailable in the current mode.",
            }

        if normalized_type in {"app", "candidate"}:
            return {
                "allowed": False,
                "mode": policy["mode"],
                "object_type": normalized_type,
                "object_id": normalized_object_id,
                "reason": "V1 readonly execution does not support app objects.",
            }

        return {
            "allowed": False,
            "mode": policy["mode"],
            "object_type": normalized_type,
            "object_id": normalized_object_id,
            "reason": "Unsupported object type.",
        }

    def review_action(self, mode: str, action: str, *, object_id: str = "", object_type: str = "root") -> Dict[str, Any]:
        normalized_action = str(action or "").strip().lower()

        if normalized_action in READONLY_ACTIONS:
            action_decision = self.review_readonly_action(mode, normalized_action)
            if not action_decision["allowed"]:
                return action_decision

            object_decision = self.review_basic_object(mode, object_id, object_type=object_type)
            if object_id and not object_decision["allowed"]:
                return object_decision

            return {
                "allowed": True,
                "mode": action_decision["mode"],
                "action": normalized_action,
                "object_id": str(object_id or "").strip(),
                "object_type": object_type,
                "reason": "Readonly action and object accepted.",
            }

        return {
            "allowed": False,
            "mode": get_review_policy(mode)["mode"],
            "action": normalized_action,
            "reason": "Only readonly desktop actions are supported by the V1 entry.",
        }

    def review_v25_task(self, task: dict, mode: str) -> Dict[str, Any]:
        payload = dict(task or {})
        action = str(payload.get("action", "")).strip().lower()
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

        action_def = get_action(action)
        risk_profile = get_action_risk_profile(action) if action_def is not None else None
        route_result = route_for_v25(action)

        base_decision: Dict[str, Any] = {
            "allowed": False,
            "decision": DECISION_DENY,
            "mode": policy["mode"],
            "action": action,
            "action_scope": "",
            "risk_level": "critical",
            "reason": "",
            "route_result": route_result,
            "requires_confirm": False,
            "requires_vm_first": False,
            "host_reserved": False,
            "consume_permission": False,
            "permission_state": permission_state,
            "permission_source_type": permission_source_type,
            "permission_source_key": permission_source_key,
            "review_stage": "menxia_rejected",
        }

        request_hint = arguments.get("request_allowed")
        if request_hint is not None and not self._argument_bool(request_hint):
            base_decision["reason"] = "The page governance layer did not allow this V2.5 request."
            return base_decision

        if policy["scope"] == "deny":
            base_decision["reason"] = "Desktop governance is disabled in the current mode."
            return base_decision

        if action_def is None:
            base_decision["reason"] = f"Unsupported V2.5 desktop action: {action or '-'}"
            return base_decision

        base_decision.update({
            "action_scope": action_def.scope,
            "risk_level": risk_profile.level if risk_profile is not None else "critical",
            "requires_confirm": bool(risk_profile.requires_confirm) if risk_profile is not None else False,
            "requires_vm_first": bool(risk_profile.requires_vm_first) if risk_profile is not None else False,
            "host_reserved": bool(action_def.host_reserved),
        })

        if not action_def.v25_enabled:
            base_decision["reason"] = "This action is reserved for a later desktop governance version."
            return base_decision

        if action_def.scope == "app" and policy["mode"] not in {"trusted", "test"}:
            base_decision["reason"] = "Software governance actions require trusted or test mode in V2.5."
            return base_decision

        if action_def.scope == "file" and policy["mode"] not in {"restricted", "trusted", "test"}:
            base_decision["reason"] = "File governance actions require restricted, trusted, or test mode in V2.5."
            return base_decision

        if permission_state == "deny":
            base_decision["reason"] = "The target permission state is deny."
            return base_decision

        if permission_state == "unset":
            base_decision["reason"] = "The target permission state is unset."
            return base_decision

        if permission_state not in VALID_PERMISSION_STATES:
            base_decision["reason"] = f"Unsupported permission state: {permission_state}"
            return base_decision

        base_decision.update({
            "allowed": True,
            "decision": DECISION_SANDBOX_ONLY,
            "reason": "V2.5 action accepted for sandbox route.",
            "consume_permission": False,
            "review_stage": "sandbox_only",
        })
        return base_decision

    def review_desktop_task(self, task: dict, mode: str, *, test_backend: str) -> Dict[str, Any]:
        payload = dict(task or {})
        action = str(payload.get("action", "")).strip().lower()
        backend = str(test_backend or "sandbox").strip().lower() or "sandbox"
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

        action_def = get_action(action)
        risk_profile = get_action_risk_profile(action) if action_def is not None else None
        route_result = self._desktop_route_result(action_def, backend)

        base_decision: Dict[str, Any] = {
            "allowed": False,
            "decision": DECISION_DENY,
            "mode": policy["mode"],
            "action": action,
            "action_scope": "" if action_def is None else action_def.scope,
            "risk_level": "critical",
            "reason": "",
            "route_result": route_result,
            "requires_confirm": False,
            "requires_vm_first": False,
            "host_reserved": False,
            "consume_permission": False,
            "permission_state": permission_state,
            "permission_source_type": permission_source_type,
            "permission_source_key": permission_source_key,
            "review_stage": "menxia_rejected",
            "test_backend": backend,
        }

        request_hint = arguments.get("request_allowed")
        if request_hint is not None and not self._argument_bool(request_hint):
            base_decision["reason"] = "The page governance layer did not allow this desktop request."
            return base_decision

        if policy["scope"] == "deny":
            base_decision["reason"] = "Desktop governance is disabled in the current mode."
            return base_decision

        if action_def is None:
            base_decision["reason"] = f"Unsupported desktop action: {action or '-'}"
            return base_decision

        base_decision.update({
            "action_scope": action_def.scope,
            "risk_level": risk_profile.level if risk_profile is not None else "critical",
            "requires_confirm": bool(risk_profile.requires_confirm) if risk_profile is not None else False,
            "requires_vm_first": bool(risk_profile.requires_vm_first) if risk_profile is not None else False,
            "host_reserved": bool(action_def.host_reserved),
        })

        if action in READONLY_ACTIONS:
            readonly_decision = self.review_readonly_action(mode, action)
            if not bool(readonly_decision.get("allowed", False)):
                base_decision["reason"] = str(readonly_decision.get("reason", "") or "Readonly action rejected.")
                return base_decision
            base_decision.update({
                "allowed": True,
                "decision": DECISION_SANDBOX_ONLY,
                "reason": "Readonly action accepted.",
                "route_result": self._desktop_route_result(action_def, "sandbox"),
                "review_stage": "readonly_allowed",
                "consume_permission": False,
                "permission_state": "readonly",
            })
            return base_decision

        if backend == "host":
            host_enabled = self._argument_bool(arguments.get("host_execution_enabled", False))
            first_round_host_file_actions = {
                "file.open",
                "folder.open",
                "file.close",
                "folder.close",
                "file.create",
                "folder.create",
                "file.rename",
                "folder.rename",
                "file.delete",
                "folder.delete",
                "file.restore",
                "folder.restore",
            }

            if policy["mode"] != "trusted":
                base_decision["reason"] = "Host execution requires trusted mode."
                return base_decision

            if not host_enabled:
                base_decision["reason"] = "Host execution requires host_execution_enabled=true."
                return base_decision

            if not action_def.v25_enabled:
                base_decision["reason"] = "This action is reserved for a later desktop governance version."
                return base_decision

            if action_def.scope not in {"app", "file", "browser"}:
                base_decision["reason"] = f"Unsupported Host action scope: {action_def.scope or '-'}"
                return base_decision

            if action_def.scope == "file" and action not in first_round_host_file_actions:
                base_decision["reason"] = "This Host file action is reserved for a later desktop governance round."
                return base_decision

            if action_def.scope == "file" and not self._argument_bool(arguments.get("request_allowed", False)):
                base_decision["reason"] = "Host file actions require request_allowed=true."
                return base_decision

            if action in {"file.delete", "folder.delete", "file.restore", "folder.restore"} and not self._argument_bool(arguments.get("file_actions_enabled", False)):
                base_decision["reason"] = "Host delete/restore actions require file_actions_enabled=true."
                return base_decision

            if permission_state not in {"allow", "once"}:
                base_decision["reason"] = f"Unsupported Host permission state: {permission_state}"
                return base_decision

            if action in {"file.create", "folder.create"} and permission_state != "allow":
                base_decision["reason"] = "Host create actions require permission state allow."
                return base_decision

            if action in {"file.rename", "folder.rename"} and permission_state not in {"allow", "once"}:
                base_decision["reason"] = "Host rename actions require permission state allow or once."
                return base_decision

            if action in {"file.close", "folder.close"} and permission_state not in {"allow", "once"}:
                base_decision["reason"] = "Host close actions require permission state allow or once."
                return base_decision

            if action == "folder.close" and not self._has_session_or_target_path(payload, arguments):
                base_decision["reason"] = "Host folder.close actions require session_id or target_path."
                return base_decision

            if action == "file.close":
                file_close_target = self._file_close_target_resolution(payload, arguments)
                if not file_close_target["allowed"]:
                    base_decision["reason"] = "missing_target_reference"
                    base_decision.update(file_close_target)
                    return base_decision
                base_decision.update(file_close_target)

            if action in {"file.delete", "folder.delete", "file.restore", "folder.restore"} and permission_state != "allow":
                base_decision["reason"] = "Host delete/restore actions require permission state allow."
                return base_decision

            if action in {"file.restore", "folder.restore"} and not (
                str(arguments.get("restore_token", "") or "").strip()
                or str(arguments.get("material_id", "") or "").strip()
                or str(arguments.get("quarantine_path", "") or "").strip()
            ):
                base_decision["reason"] = "Host restore actions require restore_token, material_id, or quarantine_path."
                return base_decision

            base_decision.update({
                "allowed": True,
                "decision": "host_only",
                "reason": "Desktop action accepted for Host route.",
                "route_result": self._desktop_route_result(action_def, "host"),
                "review_stage": "host_only",
                "consume_permission": False,
            })
            return base_decision

        if backend == "vm" and policy["mode"] != "test":
            base_decision["reason"] = "VM test backend is only available when desktop_mode is test."
            base_decision["test_backend"] = ""
            return base_decision

        if action in VM_BRIDGE_ACTIONS:
            if backend == "sandbox":
                base_decision.update({
                    "allowed": True,
                    "decision": DECISION_SANDBOX_ONLY,
                    "reason": "VM bridge action accepted for sandbox receipt only.",
                    "route_result": "sandbox.vm_bridge",
                    "review_stage": "sandbox_only",
                })
                return base_decision

            if backend == "vm":
                base_decision.update({
                    "allowed": True,
                    "decision": DECISION_VM_ONLY,
                    "reason": "VM bridge action accepted for VM-only route.",
                    "route_result": "vm.bridge",
                    "review_stage": "vm_bridge_allowed",
                })
                return base_decision

        if backend == "sandbox":
            return self.review_v25_task(payload, mode)

        if backend != "vm":
            base_decision["reason"] = f"Unsupported test backend: {backend or '-'}"
            return base_decision

        if not action_def.v25_enabled:
            base_decision["reason"] = "This action is reserved for a later desktop governance version."
            return base_decision

        if action_def.scope == "app" and policy["mode"] not in {"trusted", "test"}:
            base_decision["reason"] = "App and browser VM test actions require trusted or test mode."
            return base_decision

        if action_def.scope == "file" and policy["mode"] not in {"restricted", "trusted", "test"}:
            base_decision["reason"] = "File VM test actions require restricted, trusted, or test mode."
            return base_decision

        if permission_state not in {"test", "allow", "once"}:
            base_decision["reason"] = f"Unsupported VM permission state: {permission_state}"
            return base_decision

        base_decision.update({
            "allowed": True,
            "decision": DECISION_VM_ONLY,
            "reason": "Desktop action accepted for VM-only route.",
            "route_result": self._desktop_route_result(action_def, backend),
            "review_stage": "vm_only",
            "consume_permission": False,
        })
        return base_decision

    def _desktop_route_result(self, action_def: Any, backend: str) -> str:
        normalized_backend = str(backend or "sandbox").strip().lower() or "sandbox"

        if action_def is None:
            return f"{normalized_backend}.unknown"

        if action_def.action_id.startswith("vm."):
            return f"{normalized_backend}.bridge" if normalized_backend == "vm" else f"{normalized_backend}.vm_bridge"

        if action_def.action_id.startswith("browser."):
            return f"{normalized_backend}.browser_governance"

        if action_def.scope == "app":
            return f"{normalized_backend}.software_governance"

        if action_def.scope == "file":
            return f"{normalized_backend}.file_governance"

        return f"{normalized_backend}.{action_def.scope}"

    def _has_session_or_target_path(self, payload: dict, arguments: dict) -> bool:
        return bool(
            str(arguments.get("session_id", "") or "").strip()
            or str(arguments.get("target_path", "") or "").strip()
            or str((payload or {}).get("target_path", "") or "").strip()
        )

    def _file_close_target_resolution(self, payload: dict, arguments: dict) -> dict[str, Any]:
        session_id = str(arguments.get("session_id", "") or "").strip()
        target_path = str(arguments.get("target_path", "") or "").strip() or str((payload or {}).get("target_path", "") or "").strip()
        target_name = str((payload or {}).get("target_name", "") or "").strip() or str(arguments.get("target_name", "") or "").strip()
        target_reference = (
            str((payload or {}).get("target_reference", "") or "").strip()
            or str(arguments.get("target_reference", "") or "").strip()
        )
        app_hint = str((payload or {}).get("app_hint", "") or "").strip() or str(arguments.get("app_hint", "") or "").strip()
        current_hint = (
            str((payload or {}).get("current_hint", "") or "").strip()
            or str(arguments.get("current_hint", "") or "").strip()
        )
        if session_id or target_path:
            return {
                "allowed": True,
                "target_resolution_required": False,
                "resolution_stage": "close",
                "target_name": target_name,
                "target_reference": target_reference,
                "app_hint": app_hint,
                "current_hint": current_hint,
            }
        if target_name or target_reference or app_hint or current_hint:
            return {
                "allowed": True,
                "target_resolution_required": True,
                "resolution_stage": "resolve_then_close",
                "target_name": target_name,
                "target_reference": target_reference,
                "app_hint": app_hint,
                "current_hint": current_hint,
                "reason": "file.close allowed for target resolution.",
            }
        return {
            "allowed": False,
            "target_resolution_required": True,
            "resolution_stage": "missing_target_reference",
            "target_name": target_name,
            "target_reference": target_reference,
            "app_hint": app_hint,
            "current_hint": current_hint,
            "error": "missing_target_reference",
        }

    def _argument_bool(self, value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return value != 0
        return str(value or "").strip().lower() in {"1", "true", "yes", "y", "on"}
