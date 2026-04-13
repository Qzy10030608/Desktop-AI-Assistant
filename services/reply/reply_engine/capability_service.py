from __future__ import annotations

from typing import Dict, Any

from .capability_store import CapabilityStore # type: ignore


class CapabilityService:
    def __init__(self):
        self.store = CapabilityStore()

    def build_model_key(self, backend: str, model_name: str) -> str:
        backend_text = (backend or "unknown").strip().lower()
        model_text = (model_name or "unknown").strip()
        return f"{backend_text}:{model_text}"

    def _default_capability_for_backend(self, backend: str) -> Dict[str, Any]:
        backend = (backend or "").strip().lower()

        if backend == "ollama":
            return {
                "backend": "ollama",
                "supports_structured_output": False,
                "supports_thinking_channel": False,
                "supports_repair_extract": True,
                "preferred_strategy": "repair_extract",
                "quality_tier": "small_local",
            }

        if backend == "api":
            return {
                "backend": "api",
                "supports_structured_output": True,
                "supports_thinking_channel": False,
                "supports_repair_extract": True,
                "preferred_strategy": "structured_json",
                "quality_tier": "api_high",
            }

        if backend == "web":
            return {
                "backend": "web",
                "supports_structured_output": False,
                "supports_thinking_channel": False,
                "supports_repair_extract": True,
                "preferred_strategy": "plain_fallback",
                "quality_tier": "web_mixed",
            }

        return {
            "backend": backend or "custom_local",
            "supports_structured_output": False,
            "supports_thinking_channel": False,
            "supports_repair_extract": True,
            "preferred_strategy": "repair_extract",
            "quality_tier": "custom_local",
        }

    def get_capability(self, backend: str, model_name: str) -> Dict[str, Any]:
        model_key = self.build_model_key(backend, model_name)
        base = self._default_capability_for_backend(backend)
        override = self.store.get(model_key)

        result = dict(base)
        result.update(override)

        result["model_key"] = model_key
        result["model_name"] = model_name
        return result

    def save_capability_override(self, backend: str, model_name: str, patch: Dict[str, Any]):
        model_key = self.build_model_key(backend, model_name)
        self.store.merge(model_key, patch or {})