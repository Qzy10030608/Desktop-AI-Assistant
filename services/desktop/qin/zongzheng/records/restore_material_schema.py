from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any
from uuid import uuid4

from services.desktop.desktop_models import now_iso


@dataclass
class RestoreMaterialRecord:
    checkpoint_id: str
    action: str
    target_id: str = ""
    target_name: str = ""
    execution_backend: str = ""
    target_environment: str = ""
    path_namespace: str = ""
    machine_id: str = ""
    agent_id: str = ""
    move_mode: str = ""
    relocate_strategy: str = ""
    source_path: str = ""
    dest_path: str = ""
    backup_original_path: str = ""
    junction_path: str = ""
    backup_path: str = ""
    quarantine_path: str = ""
    snapshot_id: str = ""
    restore_strategy: str = ""
    rollback_strategy: str = ""
    relocate_status: str = ""
    material_type: str = ""
    material_status: str = "prepared"
    retention_class: str = ""
    retention_policy: str = ""
    retain_until: str = ""
    cleanup_policy: str = ""
    restore_status: str = "pending"
    verify_status: str = "unverified"
    shaofu_location: str = ""
    confirm_mode: str = ""
    restore_token: str = ""
    material_scope: str = ""
    material_role: str = ""
    expire_at: str = ""
    keep: bool = False
    size_bytes: int = 0
    related_paths: list[str] = field(default_factory=list)
    deleted: bool = False
    deleted_at: str = ""
    delete_reason: str = ""
    display_environment: str = ""
    ai_command_id: str = ""
    ai_command_text: str = ""
    command_source: str = ""
    command_success: bool = False
    error: str = ""
    data: dict[str, Any] = field(default_factory=dict)
    material_id: str = field(default_factory=lambda: f"material_{uuid4().hex}")
    created_at: str = field(default_factory=now_iso)
    updated_at: str = field(default_factory=now_iso)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
