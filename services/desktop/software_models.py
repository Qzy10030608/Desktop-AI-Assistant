from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List


@dataclass
class SecondaryLaunchDescriptor:
    platform: str = "unknown"
    platform_object_type: str = ""
    platform_object_id: str = ""
    launch_target_kind: str = "missing"
    launch_target_raw: str = ""
    install_dir: str = ""
    entry_path: str = ""
    icon_source_path: str = ""
    icon_kind: str = "missing"
    route_confidence: str = "low"
    detection_source: str = "unknown"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SoftwareRecord:
    app_id: str
    title: str
    target_path: str = ""
    permission_state: str = "unset"
    connector_id: str = "windows_shell"
    category: str = "unknown"
    candidate_kind: str = "weak_missing_path"
    candidate_strength: str = "weak"
    path_status: str = "missing"
    discover_source: str = "unknown"
    discovered: bool = False
    builtin: bool = False
    source: str = "candidate"
    enabled: bool = False
    allow_launch: bool = False
    allow_attach: bool = False
    allow_close: bool = False
    launch_args: List[str] = field(default_factory=list)
    platform: str = "unknown"
    platform_object_type: str = ""
    platform_object_id: str = ""
    launch_target_kind: str = "missing"
    launch_target_raw: str = ""
    install_dir: str = ""
    entry_path: str = ""
    icon_source_path: str = ""
    icon_kind: str = "missing"
    route_confidence: str = "low"
    visibility_reason: str = ""
    canonical_app_id: str = ""
    risk_hint: str = ""
    sensitivity: str = ""
    publisher: str = ""
    version: str = ""
    uninstall_string: str = ""
    registry_key: str = ""
    source_detail: str = ""
    identity_source: str = ""
    launch_source: str = ""
    registry_entry_status: str = ""
    risk_tags: List[str] = field(default_factory=list)
    hidden: bool = False
    manual_bound: bool = False
    manual_target_path: str = ""
    manual_launch_target_kind: str = "missing"
    manual_launch_target_raw: str = ""
    manual_entry_path: str = ""
    bind_source: str = ""
    bound_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SoftwareRecord":
        payload = dict(data or {})
        payload["launch_args"] = list(payload.get("launch_args", []) or [])
        payload["risk_tags"] = list(payload.get("risk_tags", []) or [])
        return cls(**{key: payload.get(key) for key in cls.__dataclass_fields__})


@dataclass
class SoftwareDetectionDecision:
    category: str = "unknown"
    candidate_kind: str = "weak_missing_path"
    visibility: str = "main"
    actionability: str = "display_only"
    is_secondary_route: bool = False
    route_confidence: str = "low"
    risk_tags: List[str] = field(default_factory=list)
    visibility_reason: str = ""
    launch_target_kind: str = "missing"
    launch_target_raw: str = ""
    platform: str = "unknown"
    platform_object_type: str = ""
    platform_object_id: str = ""
    install_dir: str = ""
    entry_path: str = ""
    icon_source_path: str = ""
    icon_kind: str = "missing"
    path_status: str = "missing"
    candidate_strength: str = "weak"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SoftwareViewRow:
    app_id: str
    title: str
    target_path: str = ""
    effective_target_path: str = ""
    path_short: str = "-"
    permission_state: str = "deny"
    permission_state_raw: str = "unset"
    effective_permission_state: str = "deny"
    permission_label: str = "否"
    permission_color: str = "#EF4444"
    status_badge: str = "发现"
    status_color: str = "#94A3B8"
    tooltip: str = ""
    status_tooltip: str = ""
    icon_text: str = "APP"
    icon_source_path: str = ""
    icon_kind: str = "missing"
    can_locate: bool = False
    can_launch: bool = False
    can_close: bool = False
    can_uninstall: bool = False
    can_move: bool = False
    can_update: bool = False
    can_clear: bool = True
    can_adjust: bool = False
    can_bind_path: bool = False
    candidate_kind: str = "weak_missing_path"
    candidate_strength: str = "weak"
    path_status: str = "missing"
    launch_target_kind: str = "missing"
    launch_target_raw: str = ""
    effective_launch_target_kind: str = "missing"
    effective_launch_target_raw: str = ""
    platform: str = "unknown"
    platform_object_id: str = ""
    platform_object_type: str = ""
    entry_path: str = ""
    install_dir: str = ""
    route_confidence: str = "low"
    manual_bound: bool = False
    allowed_actions: List[str] = field(default_factory=list)
    canonical_app_id: str = ""
    risk_hint: str = ""
    sensitivity: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
