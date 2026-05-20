from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any
from uuid import uuid4

from services.desktop.desktop_models import now_iso


@dataclass
class ActionCheckpointRecord:
    action: str
    target_id: str = ""
    target_name: str = ""
    target_path: str = ""
    target_type: str = ""
    backend: str = ""
    execution_backend: str = ""
    target_environment: str = ""
    path_namespace: str = ""
    machine_id: str = ""
    agent_id: str = ""
    route_result: str = ""
    decision: str = ""
    risk_level: str = ""
    before_state: dict[str, Any] = field(default_factory=dict)
    after_state: dict[str, Any] = field(default_factory=dict)
    material_id: str = ""
    material_type: str = ""
    restore_strategy: str = ""
    restore_status: str = ""
    material_status: str = ""
    move_mode: str = ""
    relocate_strategy: str = ""
    rollback_strategy: str = ""
    relocate_status: str = ""
    source_path: str = ""
    dest_path: str = ""
    backup_original_path: str = ""
    junction_path: str = ""
    backup_path: str = ""
    quarantine_path: str = ""
    data: dict[str, Any] = field(default_factory=dict)
    checkpoint_id: str = field(default_factory=lambda: f"checkpoint_{uuid4().hex}")
    created_at: str = field(default_factory=now_iso)
    updated_at: str = field(default_factory=now_iso)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
