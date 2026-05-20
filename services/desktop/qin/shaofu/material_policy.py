from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from services.desktop.qin.shaofu.backup_store import BackupStore
from services.desktop.qin.shaofu.quarantine_store import QuarantineStore
from services.desktop.qin.shaofu.restore_registry import RestoreRegistry
from services.desktop.qin.shaofu.snapshot_store import SnapshotStore
from services.desktop.qin.shaofu.storage_index import StorageIndex
from services.desktop.qin.yushitai.event_store import YushitaiEventStore
from services.desktop.qin.zongzheng.records.restore_material_schema import RestoreMaterialRecord


PROTECTED_DANGEROUS_ACTIONS = frozenset({
    "app.uninstall",
    "app.move",
    "app.relocate",
    "app.update",
    "file.delete",
    "folder.delete",
    "file.move",
    "folder.move",
    "file.rename",
    "folder.rename",
    "file.copy",
    "file.create",
    "folder.create",
    "file.mkdir",
    "folder.mkdir",
    "file.touch",
})


class MaterialPolicy:
    """Prepare restore material records. It does not execute the final action."""

    def __init__(
        self,
        project_root: str | Path | None = None,
        *,
        restore_registry: RestoreRegistry | None = None,
        storage_index: StorageIndex | None = None,
        backup_store: BackupStore | None = None,
        quarantine_store: QuarantineStore | None = None,
        snapshot_store: SnapshotStore | None = None,
        event_store: YushitaiEventStore | None = None,
    ) -> None:
        self.project_root = Path(project_root or Path(__file__).resolve().parents[4]).expanduser().resolve()
        self.restore_registry = restore_registry or RestoreRegistry(self.project_root)
        self.storage_index = storage_index or StorageIndex(self.project_root)
        self.backup_store = backup_store or BackupStore(self.project_root)
        self.quarantine_store = quarantine_store or QuarantineStore(self.project_root)
        self.snapshot_store = snapshot_store or SnapshotStore(self.project_root)
        self.event_store = event_store or YushitaiEventStore(self.project_root)

    def prepare_material(self, task: dict, review_decision: dict, checkpoint: dict[str, Any]) -> dict[str, Any]:
        self.storage_index.ensure_layout()
        payload = dict(task or {})
        arguments = payload.get("arguments", {}) if isinstance(payload.get("arguments"), dict) else {}
        action = str(payload.get("action", "") or "").strip().lower()
        checkpoint_id = str((checkpoint or {}).get("checkpoint_id", "") or arguments.get("checkpoint_id", "") or "")
        target_id = str(payload.get("target_id", "") or arguments.get("app_id", "") or arguments.get("target_id", "") or "")
        target_name = str(payload.get("target_name", "") or "")
        source_path = str(
            arguments.get("source_path", "")
            or arguments.get("old_path", "")
            or arguments.get("install_dir", "")
            or payload.get("target_path", "")
            or ""
        )
        dest_path = str(
            arguments.get("dest_path", "")
            or arguments.get("new_path", "")
            or arguments.get("move_target_path", "")
            or arguments.get("target_path", "")
            or ""
        )
        execution_backend = str(arguments.get("execution_backend", arguments.get("test_backend", "")) or "").strip()
        target_environment = str(arguments.get("target_environment", "") or "").strip()
        path_namespace = str(arguments.get("path_namespace", "") or "").strip()
        confirm_mode = self._confirm_mode(arguments, execution_backend=execution_backend)
        shaofu_location = self._shaofu_location(execution_backend, target_environment, path_namespace)
        retention_policy = str(arguments.get("retention_policy", "") or "").strip() or self._default_retention_policy(action)
        retain_until = str(arguments.get("retain_until", "") or "").strip() or self._default_retain_until(retention_policy)
        restore_token = str(arguments.get("restore_token", "") or "").strip()
        machine_id = str(arguments.get("machine_id", "") or "").strip()
        agent_id = str(arguments.get("agent_id", "") or "").strip()
        if self._is_sandbox_environment(execution_backend, target_environment, path_namespace):
            return {
                "checkpoint_id": checkpoint_id,
                "action": action,
                "target_id": target_id,
                "target_name": target_name,
                "execution_backend": execution_backend or "sandbox",
                "target_environment": target_environment or "sandbox_simulation",
                "path_namespace": path_namespace or "sandbox",
                "material_type": "none",
                "material_status": "not_required",
                "restore_status": "not_required",
                "verify_status": "not_required",
                "restore_strategy": "",
                "shaofu_location": "record",
                "confirm_mode": confirm_mode,
                "retention_policy": "record",
                "retain_until": "long_term_report",
                "restore_token": restore_token,
                "error": "",
                "data": {"shaofu_skipped": True, "skip_reason": "sandbox_has_no_real_restore_material"},
            }

        material = RestoreMaterialRecord(
            checkpoint_id=checkpoint_id,
            action=action,
            target_id=target_id,
            target_name=target_name,
            execution_backend=execution_backend,
            target_environment=target_environment,
            path_namespace=path_namespace,
            machine_id=machine_id,
            agent_id=agent_id,
            move_mode=str(arguments.get("move_mode", "") or "").strip(),
            relocate_strategy=str(arguments.get("relocate_strategy", "") or "").strip(),
            source_path=source_path,
            dest_path=dest_path,
            shaofu_location=shaofu_location,
            confirm_mode=confirm_mode,
            retention_policy=retention_policy,
            retain_until=retain_until,
            restore_token=restore_token,
        ).to_dict()
        policy = self._policy_for_action(action, arguments, material["material_id"])
        material.update(policy)
        if not material.get("shaofu_location"):
            material["shaofu_location"] = shaofu_location
        if not material.get("confirm_mode"):
            material["confirm_mode"] = confirm_mode
        if not material.get("retention_policy"):
            material["retention_policy"] = retention_policy
        if not material.get("retain_until"):
            material["retain_until"] = retain_until
        if not material.get("restore_token"):
            material["restore_token"] = restore_token or f"restore:{material['material_id']}"
        material["updated_at"] = material["created_at"]
        material["data"] = {
            "route_result": str(review_decision.get("route_result", "") or ""),
            "risk_level": str(review_decision.get("risk_level", "") or ""),
            "confirmed": bool(arguments.get("confirmed", False)),
            "confirm_mode": material.get("confirm_mode", confirm_mode),
            "shaofu_location": material.get("shaofu_location", shaofu_location),
            "retention_policy": material.get("retention_policy", retention_policy),
            "retain_until": material.get("retain_until", retain_until),
            "restore_token": material.get("restore_token", restore_token),
            **(policy.get("data", {}) if isinstance(policy.get("data"), dict) else {}),
        }
        self.restore_registry.append(material)
        self.storage_index.add_material(material)
        self._record_event(material)
        return material

    def should_block_for_material(self, material: dict[str, Any], review_decision: dict) -> bool:
        status = str((material or {}).get("material_status", "") or "").strip().lower()
        action = str((material or {}).get("action", "") or "").strip().lower()
        requires_confirm = bool(review_decision.get("requires_confirm", False))
        critical_or_high = str(review_decision.get("risk_level", "") or "").strip().lower() in {"critical", "high"}
        if action in PROTECTED_DANGEROUS_ACTIONS and (requires_confirm or critical_or_high):
            return status not in {"ready", "not_required"}
        return status in {"failed", "missing_strategy"}

    def _policy_for_action(self, action: str, arguments: dict[str, Any], material_id: str) -> dict[str, Any]:
        backend = str(
            arguments.get("execution_backend", "")
            or arguments.get("test_backend", "")
            or arguments.get("backend", "")
            or ""
        ).strip().lower()
        confirmed = self._truthy(arguments.get("confirmed", False))
        vm_confirmed = backend == "vm" and confirmed
        real_confirmed = backend in {"vm", "host"} and confirmed
        if action == "app.uninstall":
            install_dir = str(arguments.get("install_dir", "") or "").strip()
            uninstall_string = str(arguments.get("uninstall_string", "") or "").strip()
            quiet_uninstall_string = str(arguments.get("quiet_uninstall_string", "") or "").strip()
            if not (uninstall_string or quiet_uninstall_string):
                return {
                    "material_type": "uninstall_manifest",
                    "material_status": "missing_strategy",
                    "restore_strategy": "vm_real_uninstall_manual_reinstall_or_snapshot",
                    "error": "missing_uninstall_string",
                    "data": {
                        "install_dir": install_dir,
                        "source_path": str(arguments.get("source_path", "") or install_dir),
                        "vm_real_software_test": backend == "vm",
                    },
                }
            if real_confirmed:
                return {
                    "material_type": "uninstall_manifest",
                    "material_status": "ready",
                    "restore_strategy": "manual_reinstall_or_snapshot",
                    "snapshot_id": f"snapshot_{material_id}",
                    "data": {
                        "uninstall_string": uninstall_string,
                        "quiet_uninstall_string": quiet_uninstall_string,
                        "install_dir": install_dir,
                        "source_path": str(arguments.get("source_path", "") or install_dir),
                        "vm_real_software_test": backend == "vm",
                        "host_real_software": backend == "host",
                    },
                }
            return {
                "material_type": "uninstall_manifest",
                "material_status": "failed",
                "restore_strategy": "manual_reinstall_or_snapshot",
                "error": "confirmed_required",
            }
        if action in {"app.move", "app.relocate"}:
            source_path = str(arguments.get("source_path", "") or arguments.get("install_dir", "") or "").strip()
            dest_path = str(arguments.get("dest_path", "") or arguments.get("move_target_path", "") or "").strip()
            move_mode = str(arguments.get("move_mode", "") or "").strip()
            relocate_strategy = str(arguments.get("relocate_strategy", "") or "").strip()
            installed_relocate = move_mode == "installed_app_relocate" or action == "app.relocate"
            if not source_path:
                return {"material_type": "path_pair", "material_status": "failed", "restore_strategy": "move_back", "error": "missing_source_path"}
            if not dest_path and not (installed_relocate and backend == "vm"):
                return {"material_type": "path_pair", "material_status": "failed", "restore_strategy": "move_back", "error": "missing_dest_path"}
            if installed_relocate:
                if relocate_strategy == "move_update_paths":
                    planned_dest_path = dest_path or "__vm_agent_select__"
                    backup_original_path = f"{source_path}.__backup_pending"
                    return {
                        "material_type": "software_relocation_bundle",
                        "material_status": "ready" if real_confirmed else "failed",
                        "restore_strategy": "restore_paths_and_move_back",
                        "rollback_strategy": "restore_registry_shortcuts_services_and_move_back",
                        "retention_class": "critical_long",
                        "cleanup_policy": "never_until_verified",
                        "restore_status": "pending",
                        "verify_status": "unverified",
                        "material_scope": "software",
                        "material_role": "relocation_bundle",
                        "relocate_status": "prepared" if real_confirmed else "preflight_failed",
                        "move_mode": move_mode or "installed_app_relocate",
                        "relocate_strategy": "move_update_paths",
                        "dest_path": planned_dest_path,
                        "backup_original_path": backup_original_path,
                        "error": "" if real_confirmed else "confirmed_required",
                        "data": {
                            "source_path": source_path,
                            "planned_dest_path": planned_dest_path,
                            "dest_path": planned_dest_path,
                            "dest_path_generated_by": "vm_agent_select" if not dest_path else "explicit_path",
                            "backup_original_path": backup_original_path,
                            "move_mode": move_mode or "installed_app_relocate",
                            "relocate_strategy": "move_update_paths",
                            "relocate_target_mode": str(arguments.get("relocate_target_mode", "") or "vm_folder_dialog"),
                            "path_namespace": str(arguments.get("path_namespace", "") or ""),
                            "execution_backend": backend,
                            "target_environment": str(arguments.get("target_environment", "") or ""),
                            "machine_id": str(arguments.get("machine_id", "") or ""),
                            "agent_id": str(arguments.get("agent_id", "") or ""),
                            "process_name": str(arguments.get("process_name", "") or ""),
                            "process_names": arguments.get("process_names", []) if isinstance(arguments.get("process_names", []), list) else [],
                            "install_dir": str(arguments.get("install_dir", "") or source_path),
                            "uninstall_string": str(arguments.get("uninstall_string", "") or ""),
                            "quiet_uninstall_string": str(arguments.get("quiet_uninstall_string", "") or ""),
                            "vm_real_software_test": backend == "vm",
                            "host_real_software": backend == "host",
                            "is_admin_required": True,
                            "registry_backup_expected": True,
                            "shortcut_backup_expected": True,
                            "service_backup_expected": True,
                        },
                    }
                planned_dest_path = dest_path or "__vm_agent_auto__"
                backup_original_path = f"{source_path}.__backup_pending"
                return {
                    "material_type": "relocation_plan",
                    "material_status": "ready" if real_confirmed else "failed",
                    "restore_strategy": "remove_junction_restore_original",
                    "rollback_strategy": "delete_dest_restore_backup",
                    "relocate_status": "prepared" if real_confirmed else "preflight_failed",
                    "move_mode": move_mode or "installed_app_relocate",
                    "relocate_strategy": relocate_strategy or "copy_junction",
                    "dest_path": planned_dest_path,
                    "backup_original_path": backup_original_path,
                    "junction_path": source_path,
                    "error": "" if real_confirmed else "confirmed_required",
                    "data": {
                        "source_path": source_path,
                        "dest_path": planned_dest_path,
                        "dest_path_generated_by": "vm_agent" if not dest_path else "",
                        "backup_original_path": backup_original_path,
                        "junction_path": source_path,
                        "path_namespace": str(arguments.get("path_namespace", "") or ""),
                        "execution_backend": backend,
                        "target_environment": str(arguments.get("target_environment", "") or ""),
                        "machine_id": str(arguments.get("machine_id", "") or ""),
                        "agent_id": str(arguments.get("agent_id", "") or ""),
                        "vm_real_software_test": backend == "vm",
                        "host_real_software": backend == "host",
                        "is_admin_required": True,
                        "process_name": str(arguments.get("process_name", "") or ""),
                        "process_names": arguments.get("process_names", []) if isinstance(arguments.get("process_names", []), list) else [],
                    },
                }
            if real_confirmed:
                return {
                    "material_type": "path_pair",
                    "material_status": "ready",
                    "restore_strategy": "move_back",
                    "data": {
                        "source_path": source_path,
                        "dest_path": dest_path,
                        "vm_real_software_test": backend == "vm",
                        "host_real_software": backend == "host",
                    },
                }
            return {"material_type": "path_pair", "material_status": "failed", "restore_strategy": "move_back", "error": "confirmed_required"}
        if action == "app.update":
            if not (arguments.get("updater_path") or arguments.get("update_source_dir")):
                return {"material_type": "update_manifest", "material_status": "missing_strategy", "restore_strategy": "", "error": "missing_update_strategy"}
            if real_confirmed:
                return {
                    "material_type": "update_manifest",
                    "material_status": "ready",
                    "restore_strategy": "manual_restore_or_snapshot",
                    "backup_path": self.backup_store.reserve_path(material_id),
                    "data": {
                        "updater_path": str(arguments.get("updater_path", "") or ""),
                        "update_source_dir": str(arguments.get("update_source_dir", "") or ""),
                        "install_dir": str(arguments.get("install_dir", "") or ""),
                        "vm_real_software_test": backend == "vm",
                        "host_real_software": backend == "host",
                    },
                }
            return {"material_type": "update_manifest", "material_status": "failed", "restore_strategy": "manual_restore_or_snapshot", "error": "confirmed_required"}
        if action in {"file.delete", "folder.delete"}:
            target_type = str(arguments.get("target_type", "") or "").strip()
            if not target_type:
                target_type = "directory" if action == "folder.delete" else "file"

            run_id = str(arguments.get("yushitai_run_id", arguments.get("run_id", "")) or "").strip()
            run_backend = str(
                arguments.get("yushitai_run_backend", arguments.get("run_backend", backend))
                or backend
            ).strip().lower()

            original_path = str(
                arguments.get("original_path", "")
                or arguments.get("source_path", "")
                or arguments.get("target_path", "")
                or arguments.get("path", "")
                or ""
            ).strip()

            object_name = Path(original_path).name if original_path else str(material_id or "quarantine_object")
            if backend == "vm":
                return {
                    "material_type": "quarantine",
                    "material_status": "ready",
                    "restore_strategy": "quarantine",
                    "quarantine_path": str(arguments.get("quarantine_path", "") or f"vm_shaofu://{material_id}"),
                    "restore_token": str(arguments.get("restore_token", "") or f"vm_restore:{material_id}"),
                    "shaofu_location": "vm_temp",
                    "retention_policy": str(arguments.get("retention_policy", "") or "quarantine"),
                    "retain_until": str(arguments.get("retain_until", "") or self._default_retain_until("quarantine")),
                    "cleanup_policy": "cleanup_on_exit",
                    "data": {"vm_material_entity": "stored_inside_vm"},
                }
            quarantine_path = self.quarantine_store.reserve_path(
                material_id,
                run_backend=run_backend,
                run_id=run_id,
                object_name=object_name,
            )
            material_dir = str(Path(quarantine_path).parent)
            return {
                "material_type": "quarantine",
                "material_status": "ready",
                "status": "ready",
                "restore_strategy": "quarantine",
                "restore_status": "ready",
                "quarantine_path": quarantine_path,
                "original_path": original_path,
                "source_path": original_path,
                "target_type": target_type,
                "run_id": run_id,
                "run_backend": run_backend,
                "restore_action": "folder.restore" if action == "folder.delete" else "file.restore",
                "manifest_path": str(Path(material_dir) / "manifest.json"),
                "data": {
                    "original_path": original_path,
                    "quarantine_path": quarantine_path,
                    "target_type": target_type,
                    "run_id": run_id,
                    "run_backend": run_backend,
                    "restore_action": "folder.restore" if action == "folder.delete" else "file.restore",
                    "manifest_path": str(Path(material_dir) / "manifest.json"),
                },
            }
        if action == "file.move":
            return {"material_type": "path_pair", "material_status": "ready", "restore_strategy": "move_back"}
        if action == "file.rename":
            return {"material_type": "path_pair", "material_status": "ready", "restore_strategy": "rename_back"}
        if action == "file.copy":
            return {"material_type": "copy_manifest", "material_status": "ready", "restore_strategy": "delete_created_copy"}
        if action == "file.mkdir":
            return {"material_type": "metadata_snapshot", "material_status": "ready", "restore_strategy": "remove_created_dir"}
        if action == "file.touch":
            return {"material_type": "metadata_snapshot", "material_status": "ready", "restore_strategy": "remove_created_file"}
        return {"material_type": "none", "material_status": "not_required", "restore_strategy": ""}

    def _is_vm_workspace_path(self, path: str) -> bool:
        normalized = str(path or "").replace("/", "\\").lower()
        return "\\ai_vm_test\\" in normalized or "\\workspace\\apps\\" in normalized or "\\test_apps\\" in normalized

    def _shaofu_location(self, execution_backend: str, target_environment: str, path_namespace: str) -> str:
        backend = str(execution_backend or "").strip().lower()
        environment = str(target_environment or "").strip().lower()
        namespace = str(path_namespace or "").strip().lower()
        if backend == "vm" or environment == "virtual_machine" or namespace == "vm_windows":
            return "vm_temp"
        if backend == "host" or environment in {"host_machine", "local_host"} or namespace == "host_windows":
            return "host_runtime"
        return "record"

    def _confirm_mode(self, arguments: dict[str, Any], *, execution_backend: str) -> str:
        explicit = str(arguments.get("confirm_mode", "") or "").strip().lower()
        if explicit in {"none", "vm_auto_confirm", "user_confirmed", "user_rejected"}:
            return explicit
        if self._truthy(arguments.get("vm_auto_confirm", False)):
            return "vm_auto_confirm"
        if self._truthy(arguments.get("confirmed", False)):
            return "user_confirmed"
        if str(execution_backend or "").strip().lower() == "vm":
            return "none"
        return "none"

    def _default_retention_policy(self, action: str) -> str:
        normalized = str(action or "").strip().lower()
        if normalized.endswith(".delete"):
            return "quarantine"
        if normalized.endswith(".restore"):
            return "record"
        return "temp"

    def _default_retain_until(self, retention_policy: str) -> str:
        policy = str(retention_policy or "").strip().lower()
        if policy == "record":
            return "long_term_report"
        if policy == "temp":
            return "project_close"
        return (datetime.now(timezone.utc) + timedelta(days=14)).isoformat(timespec="seconds")

    def _truthy(self, value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return value != 0
        return str(value or "").strip().lower() in {"1", "true", "yes", "y", "on"}

    def _is_sandbox_environment(self, execution_backend: str, target_environment: str, path_namespace: str) -> bool:
        backend = str(execution_backend or "").strip().lower()
        environment = str(target_environment or "").strip().lower()
        namespace = str(path_namespace or "").strip().lower()
        return backend == "sandbox" or environment == "sandbox_simulation" or namespace == "sandbox"

    def _record_event(self, material: dict[str, Any]) -> None:
        try:
            status = str(material.get("material_status", "") or "")
            self.event_store.record(
                event_type="shaofu.material.prepared" if status == "ready" else "shaofu.material.not_ready",
                department="shaofu",
                action=str(material.get("action", "") or ""),
                backend=str(material.get("execution_backend", "") or "vm"),
                execution_backend=str(material.get("execution_backend", "") or "vm"),
                target_environment=str(material.get("target_environment", "") or ""),
                path_namespace=str(material.get("path_namespace", "") or ""),
                machine_id=str(material.get("machine_id", "") or ""),
                agent_id=str(material.get("agent_id", "") or ""),
                target={
                    "id": material.get("target_id", ""),
                    "name": material.get("target_name", ""),
                    "path": material.get("source_path", ""),
                },
                decision="vm_only" if status in {"ready", "not_required"} else "deny",
                reason=str(material.get("error", "") or status),
                result={"ok": status in {"ready", "not_required"}, "message": status},
                material=material,
                data={
                    "ok": status in {"ready", "not_required"},
                    "material_status": status,
                    "move_mode": material.get("move_mode", ""),
                    "relocate_strategy": material.get("relocate_strategy", ""),
                    "relocate_status": material.get("relocate_status", ""),
                },
            )
        except Exception:
            return
