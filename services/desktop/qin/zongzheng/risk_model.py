from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal

from services.desktop.qin.zongzheng.action_catalog import get_action
from services.desktop.qin.zongzheng.decision_vocabulary import (
    DECISION_DENY,
    DECISION_HOST_LIMITED,
    DECISION_SANDBOX_ONLY,
    DECISION_VM_ONLY,
    DecisionCode,
)

RiskLevel = Literal["low", "medium", "high", "critical"]


@dataclass(frozen=True)
class RiskProfile:
    key: str
    level: RiskLevel
    default_decision: DecisionCode
    requires_confirm: bool = False
    requires_vm_first: bool = False
    host_reserved: bool = False
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


RISK_PROFILES: dict[str, RiskProfile] = {
    "ui_only": RiskProfile(
        key="ui_only",
        level="low",
        default_decision=DECISION_SANDBOX_ONLY,
        notes="Only changes the desktop governance UI state.",
    ),
    "readonly": RiskProfile(
        key="readonly",
        level="low",
        default_decision=DECISION_SANDBOX_ONLY,
        notes="Reads metadata or returns a sandbox receipt.",
    ),
    "scan": RiskProfile(
        key="scan",
        level="medium",
        default_decision=DECISION_SANDBOX_ONLY,
        notes="May enumerate local resources in later stages.",
    ),
    "host_visible": RiskProfile(
        key="host_visible",
        level="medium",
        default_decision=DECISION_SANDBOX_ONLY,
        host_reserved=True,
        notes="Would become visible on the host in V3.",
    ),
    "vm_file_open": RiskProfile(
        key="vm_file_open",
        level="medium",
        default_decision=DECISION_VM_ONLY,
        requires_vm_first=True,
        host_reserved=True,
        notes="Opens a file or folder in the VM during file action testing.",
    ),
    "network_search": RiskProfile(
        key="network_search",
        level="medium",
        default_decision=DECISION_VM_ONLY,
        requires_vm_first=True,
        host_reserved=True,
        notes="Opens a browser search and must stay in the VM during testing.",
    ),
    "vm_connection": RiskProfile(
        key="vm_connection",
        level="medium",
        default_decision=DECISION_VM_ONLY,
        requires_confirm=False,
        requires_vm_first=False,
        host_reserved=False,
        notes="Connects to the VM bridge after governance review.",
    ),
    "file_write": RiskProfile(
        key="file_write",
        level="high",
        default_decision=DECISION_VM_ONLY,
        requires_confirm=True,
        requires_vm_first=True,
        host_reserved=True,
        notes="Writes file data and must pass VM validation before host rollout.",
    ),
    "file_create": RiskProfile(
        key="file_create",
        level="medium",
        default_decision=DECISION_VM_ONLY,
        requires_confirm=False,
        requires_vm_first=False,
        host_reserved=True,
        notes="Creates VM test files or folders without host execution.",
    ),
    "file_move": RiskProfile(
        key="file_move",
        level="high",
        default_decision=DECISION_VM_ONLY,
        requires_confirm=False,
        requires_vm_first=True,
        host_reserved=True,
        notes="Moves or copies VM test file objects without host execution.",
    ),
    "file_delete": RiskProfile(
        key="file_delete",
        level="critical",
        default_decision=DECISION_VM_ONLY,
        requires_confirm=True,
        requires_vm_first=True,
        host_reserved=True,
        notes="Deletes VM test file objects; VM Agent must still enforce confirmed=true.",
    ),
    "file_restore": RiskProfile(
        key="file_restore",
        level="high",
        default_decision=DECISION_VM_ONLY,
        requires_confirm=False,
        requires_vm_first=True,
        host_reserved=True,
        notes="Restores VM Shaofu file material without host execution.",
    ),
    "process_start": RiskProfile(
        key="process_start",
        level="high",
        default_decision=DECISION_VM_ONLY,
        requires_confirm=False,
        requires_vm_first=True,
        host_reserved=True,
        notes="Starts a process and must pass VM validation before host rollout.",
    ),
    "process_stop": RiskProfile(
        key="process_stop",
        level="high",
        default_decision=DECISION_VM_ONLY,
        requires_confirm=False,
        requires_vm_first=True,
        host_reserved=True,
        notes="Stops a process and must pass VM validation before host rollout.",
    ),
    "destructive": RiskProfile(
        key="destructive",
        level="critical",
        default_decision=DECISION_DENY,
        requires_confirm=True,
        requires_vm_first=True,
        host_reserved=True,
        notes="Reserved for future versions; disabled in V2.5.",
    ),
    "destructive_simulation": RiskProfile(
        key="destructive_simulation",
        level="critical",
        default_decision=DECISION_SANDBOX_ONLY,
        requires_confirm=True,
        requires_vm_first=True,
        host_reserved=True,
        notes="Dangerous action simulation only; no real uninstall, move, or update in V2.5.",
    ),
    "installed_app_relocate": RiskProfile(
        key="installed_app_relocate",
        level="critical",
        default_decision=DECISION_VM_ONLY,
        requires_confirm=True,
        requires_vm_first=True,
        host_reserved=True,
        notes="Relocates installed software in the VM; host execution remains reserved.",
    ),
}


def get_risk_profile_by_key(key: str | None) -> RiskProfile:
    return RISK_PROFILES.get(str(key or "").strip().lower(), RISK_PROFILES["destructive"])


def get_action_risk_profile(action: str | None) -> RiskProfile:
    definition = get_action(action)
    if definition is None:
        return RISK_PROFILES["destructive"]
    return get_risk_profile_by_key(definition.risk_key)


def default_decision_for_action(action: str | None) -> DecisionCode:
    definition = get_action(action)
    if definition is None:
        return DECISION_DENY
    if definition.v25_enabled:
        risk = get_action_risk_profile(action)
        if risk.default_decision == DECISION_HOST_LIMITED:
            return DECISION_SANDBOX_ONLY
        return risk.default_decision
    return DECISION_DENY


def requires_vm_first(action: str | None) -> bool:
    return get_action_risk_profile(action).requires_vm_first


def is_host_reserved(action: str | None) -> bool:
    definition = get_action(action)
    return bool(definition and definition.host_reserved)
