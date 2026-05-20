from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from services.desktop.desktop_models import now_iso


@dataclass
class DesktopReceipt:
    ok: bool
    action: str
    adapter_id: str
    title: str
    message: str
    decision: str = ""
    route_result: str = ""
    created_at: str = field(default_factory=now_iso)
    data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ReceiptService:
    """Build user-facing desktop governance receipts.

    This service is for readable UI messages only. It is not the audit source.
    """

    def build_sandbox_receipt(
        self,
        *,
        action: str,
        target_name: str = "",
        adapter_id: str = "sandbox",
        decision: str = "sandbox_only",
        route_result: str = "",
        reason: str = "",
        data: dict[str, Any] | None = None,
    ) -> DesktopReceipt:
        target_text = str(target_name or "").strip() or "-"
        reason_text = str(reason or "").strip() or "Action accepted by V2.5 sandbox route."
        return DesktopReceipt(
            ok=True,
            action=str(action or "").strip(),
            adapter_id=adapter_id,
            title="V2.5 sandbox receipt",
            message=f"Sandbox only; no real desktop action was executed. Target: {target_text}. {reason_text}",
            decision=decision,
            route_result=route_result,
            data=data or {},
        )

    def build_rejection_receipt(
        self,
        *,
        action: str,
        reason: str,
        adapter_id: str = "",
        decision: str = "deny",
        route_result: str = "",
        data: dict[str, Any] | None = None,
    ) -> DesktopReceipt:
        return DesktopReceipt(
            ok=False,
            action=str(action or "").strip(),
            adapter_id=adapter_id,
            title="Desktop action rejected",
            message=str(reason or "").strip() or "Desktop action was rejected.",
            decision=decision,
            route_result=route_result,
            data=data or {},
        )

    def from_result(self, result: dict[str, Any]) -> DesktopReceipt:
        data = result.get("data", {}) if isinstance(result.get("data", {}), dict) else {}
        return DesktopReceipt(
            ok=bool(result.get("ok", False)),
            action=str(result.get("action", "")).strip(),
            adapter_id=str(result.get("adapter_id", "")).strip(),
            title="Desktop action result",
            message=str(result.get("message", "")).strip(),
            decision=str(data.get("review_stage", data.get("decision", ""))).strip(),
            route_result=str(data.get("route_result", "")).strip(),
            data=data,
        )

