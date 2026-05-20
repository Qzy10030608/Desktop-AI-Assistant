from __future__ import annotations

from typing import Any
from uuid import uuid4


SUPPORTED_VM_ACTIONS = frozenset({
    "app.locate",
    "app.launch",
    "app.close",
    "app.uninstall",
    "app.move",
    "app.relocate",
    "app.update",
    "file.list",
    "file.inspect",
    "file.locate",
    "file.open",
    "file.close",
    "file.close.all",
    "file.delete",
    "file.move",
    "file.rename",
    "file.copy",
    "file.create",
    "file.mkdir",
    "file.touch",
    "file.restore",
    "folder.create",
    "folder.mkdir",
    "folder.move",
    "folder.delete",
    "folder.restore",
    "browser.search_open",
    "session.status",
    "session.cleanup",
})


def build_vm_action_payload(task: dict, review_decision: dict) -> dict[str, Any]:
    payload = dict(task or {})
    arguments = payload.get("arguments", {}) if isinstance(payload.get("arguments"), dict) else {}
    action = str(payload.get("action", "")).strip().lower()
    request_id = str(payload.get("request_id", "") or arguments.get("request_id", "")).strip() or uuid4().hex

    target: dict[str, Any] = {}
    for key in (
        "path",
        "target_path",
        "target_type",
        "object_type",
        "root_id",
        "relative_path",
        "process_name",
        "process_names",
        "open_handle",
        "pid",
        "pids",
        "window_title",
        "close_mode",
        "launch_target_kind",
        "launch_target_raw",
        "shell_entry",
        "locate_entry",
        "query",
        "engine",
        "browser_path",
        "platform_object_id",
        "app_id",
        "install_dir",
        "uninstall_string",
        "quiet_uninstall_string",
        "updater_path",
        "update_source_dir",
        "source_path",
        "old_path",
        "new_path",
        "old_name",
        "new_name",
        "dest_root",
        "dest_path",
        "move_target_path",
        "move_mode",
        "relocate_strategy",
        "relocate_target_mode",
        "restore_strategy",
        "restore_token",
        "quarantine_path",
        "original_path",
        "restore_mode",
        "rollback_strategy",
        "retention_policy",
        "retain_until",
        "expire_after_action_count",
        "expire_on_project_close",
        "overwrite",
        "shaofu_location",
        "confirm_mode",
        "path_namespace",
        "execution_backend",
        "target_environment",
        "machine_id",
        "agent_id",
        "checkpoint_id",
        "material_id",
        "file_actions_enabled",
        "confirmed",
        "permission_state",
        "effective_permission_state",
        "winget_id",
        "command",
        "name",
    ):
        value = arguments.get(key, payload.get(key))
        if value not in (None, "", []):
            target[key] = value

    if "target_path" not in target:
        target_path = str(payload.get("target_path", "") or "").strip()
        if target_path:
            target["target_path"] = target_path
            target.setdefault("path", target_path)
    elif "path" not in target:
        target_path = str(target.get("target_path", "") or "").strip()
        if target_path:
            target["path"] = target_path

    launch_target_kind = str(target.get("launch_target_kind", "") or "").strip()
    launch_target_raw = str(target.get("launch_target_raw", "") or "").strip()
    if launch_target_kind:
        target.setdefault("kind", launch_target_kind)
    if launch_target_kind == "appx":
        shell_entry = str(target.get("shell_entry", "") or launch_target_raw).strip()
        if shell_entry:
            target["shell_entry"] = shell_entry
        locate_entry = str(target.get("locate_entry", "") or shell_entry).strip()
        if locate_entry:
            target["locate_entry"] = locate_entry

    if action in {"app.move", "app.relocate"}:
        if "source_path" not in target:
            source_path = str(target.get("install_dir", target.get("path", "")) or "").strip()
            if source_path:
                target["source_path"] = source_path
        if "dest_path" not in target:
            move_target_path = str(target.get("move_target_path", "") or "").strip()
            if move_target_path:
                target["dest_path"] = move_target_path

    target_id = str(payload.get("target_id", "") or arguments.get("target_id", "")).strip()
    if target_id:
        target.setdefault("app_id", target_id)
        target.setdefault("platform_object_id", target_id)

    target_name = str(payload.get("target_name", "") or "").strip()
    if target_name:
        target["name"] = target_name

    options = {
        key: value
        for key, value in arguments.items()
        if key not in target and value not in (None, "", [])
    }

    return {
        "request_id": request_id,
        "protocol_version": "v4.agent.1",
        "action": action,
        "target": target,
        "options": options,
        "meta": {
            "source": "host_project",
            "test_backend": "vm",
            "review_stage": str(review_decision.get("review_stage", "") or ""),
            "decision": str(review_decision.get("decision", "") or ""),
            "risk_level": str(review_decision.get("risk_level", "") or ""),
            "route_result": str(review_decision.get("route_result", "") or ""),
        },
    }
