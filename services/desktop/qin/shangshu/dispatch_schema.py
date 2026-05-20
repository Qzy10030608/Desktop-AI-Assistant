from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any
from uuid import uuid4

from services.desktop.desktop_models import now_iso
from services.desktop.qin.zongzheng.decision_vocabulary import DecisionCode


@dataclass
class DispatchTarget:
    target_id: str = ""
    target_name: str = ""
    target_type: str = ""
    target_path: str = ""
    root_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DispatchOrder:
    action: str
    adapter_id: str
    decision: DecisionCode
    target: DispatchTarget = field(default_factory=DispatchTarget)
    arguments: dict[str, Any] = field(default_factory=dict)
    order_id: str = field(default_factory=lambda: f"dispatch_{uuid4().hex}")
    review_id: str = ""
    route_result: str = ""
    mode: str = ""
    created_at: str = field(default_factory=now_iso)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["target"] = self.target.to_dict()
        return data


@dataclass
class DispatchResult:
    ok: bool
    action: str
    adapter_id: str
    message: str
    order_id: str = ""
    data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def target_from_task(task: dict[str, Any]) -> DispatchTarget:
    return DispatchTarget(
        target_id=str(task.get("target_id", "")).strip(),
        target_name=str(task.get("target_name", "")).strip(),
        target_type=str(task.get("target_type", "")).strip(),
        target_path=str(task.get("target_path", "")).strip(),
        root_id=str(task.get("root_id", "")).strip(),
    )

