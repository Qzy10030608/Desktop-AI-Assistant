from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from services.desktop.desktop_models import now_iso
from services.desktop.qin.yushitai.event_store import YushitaiEventStore
from services.desktop.qin.zongzheng.records.checkpoint_schema import ActionCheckpointRecord


class ActionCheckpointRegistry:
    """Append-only checkpoint registry for dangerous desktop actions."""

    def __init__(self, project_root: str | Path | None = None, *, event_store: YushitaiEventStore | None = None) -> None:
        self.project_root = Path(project_root or Path(__file__).resolve().parents[4]).expanduser().resolve()
        self.path = self.project_root / "data" / "logs" / "desktop" / "action_checkpoints.jsonl"
        self.event_store = event_store or YushitaiEventStore(self.project_root)

    def create_checkpoint(self, task: dict, review_decision: dict) -> dict[str, Any]:
        payload = dict(task or {})
        arguments = payload.get("arguments", {}) if isinstance(payload.get("arguments"), dict) else {}
        checkpoint = ActionCheckpointRecord(
            action=str(payload.get("action", "") or "").strip(),
            target_id=str(payload.get("target_id", arguments.get("app_id", "")) or "").strip(),
            target_name=str(payload.get("target_name", "") or "").strip(),
            target_path=str(payload.get("target_path", "") or "").strip(),
            target_type=str(payload.get("target_type", "") or "").strip(),
            backend=str(arguments.get("test_backend", payload.get("test_backend", "")) or "").strip(),
            execution_backend=str(arguments.get("execution_backend", arguments.get("test_backend", payload.get("test_backend", ""))) or "").strip(),
            target_environment=str(arguments.get("target_environment", "") or "").strip(),
            path_namespace=str(arguments.get("path_namespace", "") or "").strip(),
            machine_id=str(arguments.get("machine_id", "") or "").strip(),
            agent_id=str(arguments.get("agent_id", "") or "").strip(),
            route_result=str(review_decision.get("route_result", "") or "").strip(),
            decision=str(review_decision.get("decision", "") or "").strip(),
            risk_level=str(review_decision.get("risk_level", "") or "").strip(),
            before_state={
                "target_path": str(payload.get("target_path", "") or "").strip(),
                "install_dir": str(arguments.get("install_dir", "") or "").strip(),
                "source_path": str(arguments.get("source_path", arguments.get("old_path", "")) or "").strip(),
                "old_path": str(arguments.get("old_path", "") or "").strip(),
                "new_path": str(arguments.get("new_path", arguments.get("dest_path", "")) or "").strip(),
                "old_name": str(arguments.get("old_name", "") or "").strip(),
                "new_name": str(arguments.get("new_name", "") or "").strip(),
            },
            source_path=str(arguments.get("source_path", arguments.get("old_path", arguments.get("install_dir", ""))) or "").strip(),
            dest_path=str(arguments.get("dest_path", arguments.get("new_path", arguments.get("move_target_path", ""))) or "").strip(),
            move_mode=str(arguments.get("move_mode", "") or "").strip(),
            relocate_strategy=str(arguments.get("relocate_strategy", "") or "").strip(),
            restore_strategy=str(arguments.get("restore_strategy", "") or "").strip(),
            rollback_strategy=str(arguments.get("rollback_strategy", "") or "").strip(),
            data={
                "platform_object_id": str(arguments.get("platform_object_id", "") or "").strip(),
                "install_dir": str(arguments.get("install_dir", "") or "").strip(),
                "confirmed": bool(arguments.get("confirmed", False)),
                "move_mode": str(arguments.get("move_mode", "") or "").strip(),
                "relocate_strategy": str(arguments.get("relocate_strategy", "") or "").strip(),
                "path_namespace": str(arguments.get("path_namespace", "") or "").strip(),
                "root_id": str(arguments.get("root_id", payload.get("root_id", "")) or "").strip(),
                "relative_path": str(arguments.get("relative_path", payload.get("relative_path", "")) or "").strip(),
                "machine_id": str(arguments.get("machine_id", "") or "").strip(),
                "agent_id": str(arguments.get("agent_id", "") or "").strip(),
            },
        )
        record = self.append(checkpoint.to_dict())
        self._record_event("libu.checkpoint.created", record)
        return record

    def attach_material(self, checkpoint_id: str, material: dict[str, Any]) -> dict[str, Any]:
        patch = {
            "checkpoint_id": str(checkpoint_id or "").strip(),
            "material_id": str((material or {}).get("material_id", "") or ""),
            "material_type": str((material or {}).get("material_type", "") or ""),
            "material_status": str((material or {}).get("material_status", "") or ""),
            "restore_strategy": str((material or {}).get("restore_strategy", "") or ""),
            "rollback_strategy": str((material or {}).get("rollback_strategy", "") or ""),
            "move_mode": str((material or {}).get("move_mode", "") or ""),
            "relocate_strategy": str((material or {}).get("relocate_strategy", "") or ""),
            "relocate_status": str((material or {}).get("relocate_status", "") or ""),
            "restore_status": "material_attached",
            "backup_path": str((material or {}).get("backup_path", "") or ""),
            "quarantine_path": str((material or {}).get("quarantine_path", "") or ""),
            "updated_at": now_iso(),
            "data": {"material": dict(material or {})},
        }
        record = self.append(patch)
        self._record_event("libu.checkpoint.material_attached", record, material=material)
        return record

    def update_checkpoint(self, checkpoint_id: str, patch: dict[str, Any]) -> dict[str, Any]:
        payload = dict(patch or {})
        payload["checkpoint_id"] = str(checkpoint_id or payload.get("checkpoint_id", "") or "").strip()
        payload["updated_at"] = now_iso()
        record = self.append(payload)
        self._record_event("libu.checkpoint.updated", record)
        return record

    def append(self, checkpoint: ActionCheckpointRecord | dict[str, Any]) -> dict[str, Any]:
        payload = checkpoint.to_dict() if isinstance(checkpoint, ActionCheckpointRecord) else dict(checkpoint or {})
        payload.setdefault("updated_at", now_iso())
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")
        return payload

    def _record_event(self, event_type: str, checkpoint: dict[str, Any], *, material: dict[str, Any] | None = None) -> None:
        try:
            self.event_store.record(
                event_type=event_type,
                department="libu",
                action=str(checkpoint.get("action", "") or ""),
                backend=str(checkpoint.get("backend", "") or ""),
                execution_backend=str(checkpoint.get("execution_backend", checkpoint.get("backend", "")) or ""),
                target_environment=str(checkpoint.get("target_environment", "") or ""),
                path_namespace=str(checkpoint.get("path_namespace", "") or ""),
                machine_id=str(checkpoint.get("machine_id", "") or ""),
                agent_id=str(checkpoint.get("agent_id", "") or ""),
                target={
                    "id": checkpoint.get("target_id", ""),
                    "name": checkpoint.get("target_name", ""),
                    "path": checkpoint.get("target_path", ""),
                    "type": checkpoint.get("target_type", ""),
                },
                decision=str(checkpoint.get("decision", "") or ""),
                route_result=str(checkpoint.get("route_result", "") or ""),
                checkpoint=checkpoint,
                material=material or {},
                data={"ok": True},
            )
        except Exception:
            return
