from __future__ import annotations

from services.desktop.qin.liyi.message_presenter import MessagePresenter


class SessionGuard:
    """Session-level emergency stop and circuit guard."""

    def __init__(self, *, message_presenter: MessagePresenter | None = None) -> None:
        self.message_presenter = message_presenter or MessagePresenter()
        self.emergency_stopped = False
        self.circuit_open = False

    def set_emergency_stop(self, stopped: bool) -> None:
        self.emergency_stopped = bool(stopped)

    def open_circuit(self) -> None:
        self.circuit_open = True

    def close_circuit(self) -> None:
        self.circuit_open = False

    def review(self, task: dict, review_decision: dict) -> dict:
        if self.emergency_stopped:
            return {
                "allowed": False,
                "review_stage": "bingbu_emergency_stop",
                "reason": self.message_presenter.emergency_stopped(),
            }
        if self.circuit_open:
            return {
                "allowed": False,
                "review_stage": "bingbu_circuit_open",
                "reason": self.message_presenter.circuit_open(),
            }
        return {"allowed": True, "review_stage": "bingbu_allowed"}
