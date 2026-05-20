from __future__ import annotations

from typing import Any

from services.runtime.interaction.interaction_schema import build_receipt_material


class ReceiptMapper:
    """Map execution receipts into ReceiptMaterial without changing behavior."""

    SUPPORTED_ACTIONS = {
        "app.launch",
        "app.close",
        "folder.open",
        "file.open",
        "system_info.read_datetime",
    }

    def map_qin_result(self, *, result: dict[str, Any], task: dict[str, Any]) -> dict[str, Any]:
        payload = result if isinstance(result, dict) else {}
        task_payload = task if isinstance(task, dict) else {}
        data = payload.get("data", {}) if isinstance(payload.get("data"), dict) else {}
        receipt = data.get("receipt_packet", {}) if isinstance(data.get("receipt_packet"), dict) else {}

        action = self._first_text(
            payload.get("action"),
            data.get("current_action"),
            task_payload.get("action"),
        )
        if action and action not in self.SUPPORTED_ACTIONS:
            return build_receipt_material(
                source="receipt_mapper.qin_preview",
                route="desktop_command",
                status=self._first_text(payload.get("status"), data.get("status"), receipt.get("status")),
                ok=bool(payload.get("ok", False)),
                executed=self._first_bool(payload.get("executed"), data.get("executed"), payload.get("ok")),
                action=action,
                target=self._infer_target(payload, task_payload),
                safe_user_message=self._first_text(
                    payload.get("safe_user_message"),
                    payload.get("message"),
                    data.get("safe_user_message"),
                    receipt.get("safe_user_message"),
                ),
                qin_result=payload,
                raw_payload=payload,
                debug_refs={"supported": False},
            )

        message_params = self._first_dict(
            payload.get("message_params"),
            data.get("message_params"),
            receipt.get("message_params"),
        )
        safe_user_message = self._first_text(
            payload.get("safe_user_message"),
            payload.get("message"),
            data.get("safe_user_message"),
            receipt.get("safe_user_message"),
            data.get("error"),
            payload.get("error"),
        )

        return build_receipt_material(
            source="receipt_mapper.qin_preview",
            route="system_skill" if action.startswith("system_") else "desktop_command",
            status=self._first_text(payload.get("status"), data.get("status"), receipt.get("status")),
            ok=bool(payload.get("ok", False)),
            executed=self._first_bool(payload.get("executed"), data.get("executed"), payload.get("ok")),
            action=action,
            target=self._infer_target(payload, task_payload),
            message_key=self._first_text(
                payload.get("message_key"),
                data.get("message_key"),
                receipt.get("message_key"),
            ),
            message_params=message_params,
            safe_user_message=safe_user_message,
            display_text=self._first_text(payload.get("display_text"), data.get("display_text"), safe_user_message),
            tts_text=self._first_text(payload.get("tts_text"), data.get("tts_text")),
            qin_result=payload,
            raw_payload=payload,
            debug_refs={
                "supported": action in self.SUPPORTED_ACTIONS,
                "mapper_stage": "phase14_preview_only",
            },
        )

    def _infer_target(self, payload: dict[str, Any], task: dict[str, Any]) -> str:
        message_params = self._first_dict(payload.get("message_params"))
        target = task.get("target", {}) if isinstance(task.get("target"), dict) else {}
        arguments = task.get("arguments", {}) if isinstance(task.get("arguments"), dict) else {}
        return self._first_text(
            payload.get("target"),
            payload.get("target_name"),
            message_params.get("target"),
            task.get("target_name"),
            target.get("label_hint"),
            target.get("app_hint"),
            target.get("name_hint"),
            target.get("path_hint"),
            arguments.get("target_label"),
            arguments.get("target_name"),
            arguments.get("target_path"),
            arguments.get("path_hint"),
        )

    @staticmethod
    def _first_text(*values: Any) -> str:
        for value in values:
            text = str(value or "").strip()
            if text:
                return text
        return ""

    @staticmethod
    def _first_bool(*values: Any) -> bool:
        for value in values:
            if isinstance(value, bool):
                return value
        return False

    @staticmethod
    def _first_dict(*values: Any) -> dict[str, Any]:
        for value in values:
            if isinstance(value, dict):
                return dict(value)
        return {}
