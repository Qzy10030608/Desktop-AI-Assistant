from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class CloseTask:
    action: str
    target_path: str = ""
    target_type: str = ""
    target_name: str = ""
    close_scope: str = ""
    session_id: str = ""
    target_origin: str = "auto"
    execution_backend: str = "host"
    command_source: str = ""
    arguments: dict[str, Any] = field(default_factory=dict)


@dataclass
class ClosePlan:
    action: str
    target_path: str
    target_type: str
    close_scope: str
    close_level: str
    target_origin: str
    strategy: str
    adapter_task: dict[str, Any] = field(default_factory=dict)
    direct_result: dict[str, Any] | None = None
    requires_user_choice: bool = False
    reason: str = ""
    candidates: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class CloseResult:
    ok: bool
    action: str
    message: str
    close_level: str
    target_origin: str
    close_scope: str
    data: dict[str, Any] = field(default_factory=dict)
