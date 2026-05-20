from __future__ import annotations

from typing import Any

from services.desktop.qin.zongzheng.action_catalog import route_for_v25


class SandboxAdapter:
    """V2.5 default adapter that never performs real desktop actions."""

    adapter_id = "sandbox"

    def execute(self, task: dict) -> dict:
        payload = dict(task or {})
        action = str(payload.get("action", "")).strip()
        arguments = payload.get("arguments", {}) if isinstance(payload.get("arguments"), dict) else {}
        route_result = str(payload.get("route_result", "")).strip() or route_for_v25(action)
        target_name = (
            str(payload.get("target_name", "")).strip()
            or str(payload.get("target_path", "")).strip()
            or "-"
        )
        target_path = str(payload.get("target_path", "")).strip()
        target_type = str(payload.get("target_type", "")).strip() or "object"
        launch_target_kind = str(arguments.get("launch_target_kind", "") or "").strip() or "missing"
        launch_target_raw = str(arguments.get("launch_target_raw", "") or "").strip()
        platform = str(arguments.get("platform", "") or "").strip() or "unknown"
        platform_object_id = str(arguments.get("platform_object_id", "") or "").strip()
        platform_object_type = str(arguments.get("platform_object_type", "") or "").strip()
        entry_path = str(arguments.get("entry_path", "") or "").strip()
        install_dir = str(arguments.get("install_dir", "") or "").strip()
        candidate_kind = str(arguments.get("candidate_kind", "") or "").strip()
        route_confidence = str(arguments.get("route_confidence", "") or "").strip() or "low"
        destructive_messages = {
            "app.uninstall": "V2.5 dangerous action sandbox simulation; no real uninstall was executed.",
            "app.move": "V2.5 dangerous action sandbox simulation; no real move was executed.",
            "app.relocate": "V2.5 dangerous action sandbox simulation; no real relocation was executed.",
            "app.update": "V2.5 dangerous action sandbox simulation; no real update was executed.",
        }
        sandbox_text = destructive_messages.get(
            action,
            "V2.5 sandbox only; host execution is not enabled.",
        )

        return {
            "ok": True,
            "adapter_id": self.adapter_id,
            "message": sandbox_text,
            "data": {
                "current_action": action or "-",
                "current_target": target_name,
                "route_result": route_result,
                "review_stage": str(payload.get("review_stage", "sandbox_only")).strip() or "sandbox_only",
                "adapter_stage": self.adapter_id,
                "execution_allowed": False,
                "request_allowed": bool(payload.get("request_allowed", True)),
                "ui_effect_allowed": bool(payload.get("ui_effect_allowed", False)),
                "consume_permission": bool(payload.get("consume_permission", False)),
                "permission_state": str(
                    arguments.get("permission_state", payload.get("permission_state", ""))
                ).strip(),
                "effective_permission_state": str(
                    arguments.get(
                        "effective_permission_state",
                        payload.get("effective_permission_state", ""),
                    )
                ).strip(),
                "target_object": {
                    "name": target_name,
                    "path": target_path or "-",
                    "type": target_type,
                    "root_id": str(payload.get("root_id", "")).strip() or "-",
                    "target_id": str(payload.get("target_id", "")).strip(),
                },
                "launch_target_kind": launch_target_kind,
                "launch_target_raw": launch_target_raw,
                "platform": platform,
                "platform_object_id": platform_object_id,
                "platform_object_type": platform_object_type,
                "entry_path": entry_path,
                "install_dir": install_dir,
                "candidate_kind": candidate_kind,
                "route_confidence": route_confidence,
                "sandbox_text": sandbox_text,
            },
        }


def build_sandbox_result(task: dict[str, Any]) -> dict[str, Any]:
    return SandboxAdapter().execute(task)
