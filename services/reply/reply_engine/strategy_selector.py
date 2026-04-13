from __future__ import annotations

from typing import Dict, Any


class StrategySelector:
    def select(self, capability: Dict[str, Any], evaluation: Dict[str, Any]) -> str:
        preferred = str(capability.get("preferred_strategy", "")).strip()

        supports_structured_output = bool(capability.get("supports_structured_output", False))
        supports_thinking_channel = bool(capability.get("supports_thinking_channel", False))
        supports_repair_extract = bool(capability.get("supports_repair_extract", True))

        if preferred == "structured_json" and supports_structured_output:
            return "structured_json"

        if preferred == "thinking_split" and supports_thinking_channel:
            return "thinking_split"

        if preferred == "repair_extract" and supports_repair_extract:
            if evaluation.get("needs_repair", True):
                return "repair_extract"
            return "direct_use"

        if supports_structured_output:
            return "structured_json"

        if supports_thinking_channel:
            return "thinking_split"

        if supports_repair_extract:
            if evaluation.get("needs_repair", True):
                return "repair_extract"
            return "direct_use"

        return "plain_fallback"