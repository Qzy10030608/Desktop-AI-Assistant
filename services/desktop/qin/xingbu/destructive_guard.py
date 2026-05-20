from __future__ import annotations

from typing import Any

from services.desktop.qin.liyi.message_presenter import MessagePresenter
from services.desktop.qin.xingbu.confirm_rules import ConfirmRules
from services.desktop.qin.zongzheng.decision_vocabulary import DECISION_CONFIRM_REQUIRED


class DestructiveGuard:
    """Block dangerous actions until the caller supplies an explicit confirmation."""

    def __init__(
        self,
        *,
        confirm_rules: ConfirmRules | None = None,
        message_presenter: MessagePresenter | None = None,
    ) -> None:
        self.confirm_rules = confirm_rules or ConfirmRules()
        self.message_presenter = message_presenter or MessagePresenter()

    def review(self, task: dict, review_decision: dict[str, Any]) -> dict[str, Any]:
        if not self.confirm_rules.requires_confirmation(task, review_decision):
            return {"allowed": True, "requires_confirm": False}

        if self.confirm_rules.is_confirmed(task):
            return {"allowed": True, "requires_confirm": True, "confirmed": True}

        action = str((task or {}).get("action", "") or "").strip()
        risk_level = str(review_decision.get("risk_level", "") or "").strip()
        return {
            "allowed": False,
            "requires_confirm": True,
            "confirmed": False,
            "decision": DECISION_CONFIRM_REQUIRED,
            "review_stage": "xingbu_confirm_required",
            "reason": self.message_presenter.confirm_required(action=action, risk_level=risk_level),
        }
