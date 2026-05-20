from __future__ import annotations

import time
from collections import defaultdict, deque
from typing import Deque

from services.desktop.qin.liyi.message_presenter import MessagePresenter


class ThrottleGuard:
    """Simple in-memory frequency guard for dangerous desktop actions."""

    def __init__(
        self,
        *,
        max_events: int = 6,
        window_seconds: float = 60.0,
        message_presenter: MessagePresenter | None = None,
    ) -> None:
        self.max_events = max(1, int(max_events))
        self.window_seconds = max(1.0, float(window_seconds))
        self.message_presenter = message_presenter or MessagePresenter()
        self._events: dict[str, Deque[float]] = defaultdict(deque)

    def review(self, task: dict, review_decision: dict) -> dict:
        action = str((task or {}).get("action", "") or "").strip().lower() or "-"
        now = time.monotonic()
        bucket = self._events[action]
        while bucket and now - bucket[0] > self.window_seconds:
            bucket.popleft()
        if len(bucket) >= self.max_events:
            return {
                "allowed": False,
                "review_stage": "bingbu_throttled",
                "reason": self.message_presenter.throttled(),
            }
        bucket.append(now)
        return {"allowed": True, "review_stage": "bingbu_allowed"}
