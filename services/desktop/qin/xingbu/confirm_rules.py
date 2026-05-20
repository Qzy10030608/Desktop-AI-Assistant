from __future__ import annotations

from typing import Any


DANGEROUS_APP_ACTIONS = frozenset({
    "app.uninstall",
    "app.move",
    "app.relocate",
    "app.update",
})

V3_CONFIRM_REQUIRED_ACTIONS = frozenset({
    "app.uninstall",
    "app.move",
    "app.relocate",
    "app.update",
    "file.delete",
    "folder.delete",
})

V3_BASIC_APP_ACTIONS = frozenset({
    "app.locate",
    "app.launch",
    "app.close",
})


class ConfirmRules:
    """Confirmation rules for dangerous desktop actions."""

    def requires_confirmation(self, task: dict, review_decision: dict[str, Any]) -> bool:
        action = str((task or {}).get("action", "") or "").strip().lower()
        if action in V3_BASIC_APP_ACTIONS:
            return False
        if action in V3_CONFIRM_REQUIRED_ACTIONS:
            return True
        return bool(review_decision.get("requires_confirm", False))

    def is_confirmed(self, task: dict) -> bool:
        arguments = (task or {}).get("arguments", {})
        if not isinstance(arguments, dict):
            arguments = {}
        return self._truthy(arguments.get("confirmed", (task or {}).get("confirmed", False)))

    def _truthy(self, value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return value != 0
        return str(value or "").strip().lower() in {"1", "true", "yes", "y", "on", "confirmed"}
