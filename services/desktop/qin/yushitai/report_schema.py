from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any
from uuid import uuid4

from services.desktop.desktop_models import now_iso


@dataclass
class YushitaiReport:
    metadata: dict[str, Any] = field(default_factory=dict)
    summary: dict[str, Any] = field(default_factory=dict)
    system_state: dict[str, Any] = field(default_factory=dict)
    exit_matrix: dict[str, Any] = field(default_factory=dict)
    department_coverage: dict[str, Any] = field(default_factory=dict)
    vm_quality: dict[str, Any] = field(default_factory=dict)
    dangerous_action_supervision: dict[str, Any] = field(default_factory=dict)
    checkpoints: dict[str, Any] = field(default_factory=dict)
    recent_failures: list[dict[str, Any]] = field(default_factory=list)
    risk_assessment: dict[str, Any] = field(default_factory=dict)
    recommendations: list[str] = field(default_factory=list)
    raw_refs: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def new_report_metadata(*, stage: str = "v3_03_preflight") -> dict[str, Any]:
    created_at = now_iso()
    timestamp = created_at.replace(":", "").replace("-", "").replace(".", "")
    return {
        "report_id": f"yushitai_report_{timestamp}_{uuid4().hex[:8]}",
        "stage": stage,
        "created_at": created_at,
    }
