from __future__ import annotations

import time
from pathlib import Path
from typing import Any


LLM_THINKING_SCHEMA_VERSION = "jiuchasi_llm_thinking_v1"


class LLMThinkingOrchestrator:
    """
    天庭·纠察司：LLM 管家式判断编排。

    第一版只做目标提示：
    - 不执行。
    - 不授予权限。
    - 不返回 exe/process/path 作为可执行依据。
    - 只允许从 evidence 里的 known software labels 中选择一个 label hint。
    """

    def __init__(self, project_root: str | Path | None = None) -> None:
        self.project_root = Path(project_root or Path(__file__).resolve().parents[4]).expanduser().resolve()

    def think(
        self,
        *,
        user_text: str,
        action_hint: str = "",
        target_normalized: str = "",
        understanding_packet: dict[str, Any] | None = None,
        evidence_packet: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        evidence_packet = evidence_packet if isinstance(evidence_packet, dict) else {}
        labels = self._extract_known_software_labels(evidence_packet)

        result = {
            "schema_version": LLM_THINKING_SCHEMA_VERSION,
            "created_at_ts": int(time.time()),
            "ok": True,
            "user_text": str(user_text or ""),
            "action_hint": str(action_hint or ""),
            "target_normalized": str(target_normalized or ""),
            "llm_target_hint": {},
            "notes": [],
        }

        if self._should_ask_target_hint(action_hint=action_hint, target_normalized=target_normalized, labels=labels):
            result["llm_target_hint"] = self._build_target_hint(
                user_text=user_text,
                action_hint=action_hint,
                target_normalized=target_normalized,
                understanding_packet=understanding_packet or {},
                known_software_labels=labels,
            )
        else:
            result["notes"].append("llm_target_hint_skipped")

        return result

    def _should_ask_target_hint(
        self,
        *,
        action_hint: str,
        target_normalized: str,
        labels: list[str],
    ) -> bool:
        if not labels:
            return False

        action = str(action_hint or "").strip()
        target = str(target_normalized or "").strip()

        if action in {"app.launch", "app.close"}:
            return True

        # 用户可能是在问“软件区有没有某某”，这时也可以让 LLM 在 labels 里找候选。
        if target:
            return True

        return False

    def _build_target_hint(
        self,
        *,
        user_text: str,
        action_hint: str,
        target_normalized: str,
        understanding_packet: dict[str, Any],
        known_software_labels: list[str],
    ) -> dict[str, Any]:
        try:
            from services.desktop.tianting.llm_target_hint_service import LLMTargetHintService

            return LLMTargetHintService(project_root=self.project_root).build_hint(
                raw_user_text=user_text,
                action_hint=action_hint,
                target_normalized=target_normalized,
                understanding_packet=understanding_packet,
                known_software_labels=known_software_labels,
            )
        except Exception as exc:
            return {
                "schema_version": "llm_target_hint_v1",
                "ok": False,
                "source": "jiuchasi_orchestrator",
                "trusted": False,
                "target_label_hint": "",
                "confidence": 0.0,
                "requires_confirmation": True,
                "allow_direct_execution": False,
                "reason": "llm_target_hint_service_failed",
                "error_kind": exc.__class__.__name__,
                "error": str(exc),
            }

    def _extract_known_software_labels(self, evidence_packet: dict[str, Any]) -> list[str]:
        providers = evidence_packet.get("providers", {})
        if not isinstance(providers, dict):
            return []

        software = providers.get("software_governance", {})
        if not isinstance(software, dict):
            return []

        labels = software.get("labels", [])
        if not isinstance(labels, list):
            return []

        result: list[str] = []
        seen: set[str] = set()

        for label in labels:
            text = str(label or "").strip()
            key = text.casefold()
            if not text or key in seen:
                continue
            seen.add(key)
            result.append(text)

        return result