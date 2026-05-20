from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal

DecisionCode = Literal[
    "deny",
    "confirm_required",
    "sandbox_only",
    "vm_only",
    "host_limited",
]

DECISION_DENY: DecisionCode = "deny"
DECISION_CONFIRM_REQUIRED: DecisionCode = "confirm_required"
DECISION_SANDBOX_ONLY: DecisionCode = "sandbox_only"
DECISION_VM_ONLY: DecisionCode = "vm_only"
DECISION_HOST_LIMITED: DecisionCode = "host_limited"

DECISION_ORDER: tuple[DecisionCode, ...] = (
    DECISION_DENY,
    DECISION_CONFIRM_REQUIRED,
    DECISION_SANDBOX_ONLY,
    DECISION_VM_ONLY,
    DECISION_HOST_LIMITED,
)

DECISION_LABELS: dict[DecisionCode, str] = {
    DECISION_DENY: "deny",
    DECISION_CONFIRM_REQUIRED: "confirm required",
    DECISION_SANDBOX_ONLY: "sandbox only",
    DECISION_VM_ONLY: "vm only",
    DECISION_HOST_LIMITED: "host limited",
}

DECISION_EXECUTION_ALLOWED: dict[DecisionCode, bool] = {
    DECISION_DENY: False,
    DECISION_CONFIRM_REQUIRED: False,
    DECISION_SANDBOX_ONLY: True,
    DECISION_VM_ONLY: True,
    DECISION_HOST_LIMITED: True,
}


@dataclass(frozen=True)
class DecisionProfile:
    code: DecisionCode
    label: str
    execution_allowed: bool
    requires_user_confirm: bool = False
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def normalize_decision(value: str | None) -> DecisionCode:
    raw = str(value or "").strip().lower()
    if raw in DECISION_ORDER:
        return raw  # type: ignore[return-value]
    return DECISION_DENY


def get_decision_profile(value: str | None) -> DecisionProfile:
    code = normalize_decision(value)
    return DecisionProfile(
        code=code,
        label=DECISION_LABELS[code],
        execution_allowed=DECISION_EXECUTION_ALLOWED[code],
        requires_user_confirm=code == DECISION_CONFIRM_REQUIRED,
    )


def is_execution_allowed(value: str | None) -> bool:
    return get_decision_profile(value).execution_allowed


def is_v25_runnable(value: str | None) -> bool:
    """V2.5 permits sandbox and VM test routes, never host routes."""

    return normalize_decision(value) in {DECISION_SANDBOX_ONLY, DECISION_VM_ONLY}

