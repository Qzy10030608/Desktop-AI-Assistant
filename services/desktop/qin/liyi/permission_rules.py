from __future__ import annotations

from typing import Literal

PermissionState = Literal["unset", "once", "allow", "deny"]

PERMISSION_UNSET: PermissionState = "unset"
PERMISSION_ONCE: PermissionState = "once"
PERMISSION_ALLOW: PermissionState = "allow"
PERMISSION_DENY: PermissionState = "deny"

PERMISSION_ORDER: tuple[PermissionState, ...] = (
    PERMISSION_UNSET,
    PERMISSION_ONCE,
    PERMISSION_ALLOW,
    PERMISSION_DENY,
)

PERMISSION_LABELS: dict[PermissionState, str] = {
    PERMISSION_UNSET: "否",
    PERMISSION_ONCE: "受限",
    PERMISSION_ALLOW: "是",
    PERMISSION_DENY: "否",
}

PERMISSION_COLORS: dict[PermissionState, str] = {
    PERMISSION_UNSET: "#F5F5F5",
    PERMISSION_ONCE: "#FACC15",
    PERMISSION_ALLOW: "#22C55E",
    PERMISSION_DENY: "#EF4444",
}


def normalize_permission_state(value: str | None) -> PermissionState:
    raw = str(value or "").strip().lower()
    if raw in PERMISSION_ORDER:
        return raw  # type: ignore[return-value]
    return PERMISSION_UNSET


def next_permission_state(value: str | None) -> PermissionState:
    current = normalize_permission_state(value)
    index = PERMISSION_ORDER.index(current)
    next_index = (index + 1) % len(PERMISSION_ORDER)
    return PERMISSION_ORDER[next_index]
