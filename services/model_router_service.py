from typing import Any, Dict

from config import OLLAMA_HOST, OLLAMA_MODEL  # type: ignore
from services.model_registry_service import ModelRegistryService  # type: ignore


class ModelRouterService:
    def __init__(self, registry_service: ModelRegistryService):
        self.registry_service = registry_service

    def _fallback_model(self) -> Dict[str, Any]:
        return {
            "id": "fallback_ollama",
            "name": "Fallback Ollama",
            "provider": "ollama",
            "model_name": OLLAMA_MODEL,
            "host": OLLAMA_HOST,
            "type": "chat",
            "enabled": True,
            "available": False,
            "source": "fallback_default",
            "connect_timeout": 10,
            "read_timeout": 300,
            "num_ctx": 2048,
            "num_predict": -1,
            "temperature": 0.6,
            "top_p": 0.9,
            "keep_alive": "10m",
            "presence_enabled": True,
            "stream_visible": True,
            "repair_policy": "fallback_only",
            "hardware_level": "low",
            "speed_level": "medium",
            "family": "unknown",
            "size_tier": "medium",
            "family_override": "",
            "size_tier_override": "",
            "policy_override": {},
            "policy_profile": {},
            "policy_version": "v1",
            "policy_selected_at": "",
        }

    def _normalize_provider(self, provider: str | None) -> str:
        value = str(provider or "ollama").strip().lower()
        if value not in ("ollama", "local", "api"):
            return "ollama"
        return value

    def _normalize_model(self, model: Dict[str, Any] | None) -> Dict[str, Any]:
        result = self._fallback_model()
        if isinstance(model, dict):
            result.update(model)

        result["provider"] = self._normalize_provider(result.get("provider"))
        result["id"] = str(result.get("id", "fallback_ollama")).strip() or "fallback_ollama"
        result["name"] = str(result.get("name", "")).strip() or str(result.get("model_name", OLLAMA_MODEL)).strip()
        result["model_name"] = str(result.get("model_name", OLLAMA_MODEL)).strip() or OLLAMA_MODEL
        result["host"] = str(result.get("host", OLLAMA_HOST)).strip() or OLLAMA_HOST
        result["type"] = str(result.get("type", "chat")).strip() or "chat"
        result["enabled"] = bool(result.get("enabled", True))
        result["available"] = bool(result.get("available", False))
        result["source"] = str(result.get("source", "registry")).strip() or "registry"

        result["hardware_level"] = str(result.get("hardware_level", "low")).strip().lower() or "low"
        result["speed_level"] = str(result.get("speed_level", "medium")).strip().lower() or "medium"
        result["reply_prompt_mode"] = str(result.get("reply_prompt_mode", "")).strip().lower()
        result["repair_policy"] = str(result.get("repair_policy", "fallback_only")).strip().lower() or "fallback_only"
        result["presence_enabled"] = bool(result.get("presence_enabled", True))
        result["stream_visible"] = bool(result.get("stream_visible", True))
        result["connect_timeout"] = int(result.get("connect_timeout", 10) or 10)
        result["read_timeout"] = int(result.get("read_timeout", 300) or 300)
        result["num_ctx"] = int(result.get("num_ctx", 2048) or 2048)
        result["num_predict"] = int(result.get("num_predict", -1))
        result["temperature"] = float(result.get("temperature", 0.6))
        result["top_p"] = float(result.get("top_p", 0.9))
        result["keep_alive"] = str(result.get("keep_alive", "10m")).strip() or "10m"
        result["family"] = str(result.get("family", "unknown")).strip().lower() or "unknown"
        result["size_tier"] = str(result.get("size_tier", "medium")).strip().lower() or "medium"
        result["family_override"] = str(result.get("family_override", "")).strip().lower()
        result["size_tier_override"] = str(result.get("size_tier_override", "")).strip().lower()

        policy_override = result.get("policy_override", {})
        result["policy_override"] = policy_override if isinstance(policy_override, dict) else {}

        policy_profile = result.get("policy_profile", {})
        result["policy_profile"] = policy_profile if isinstance(policy_profile, dict) else {}

        result["policy_version"] = str(result.get("policy_version", "v1")).strip() or "v1"
        result["policy_selected_at"] = str(result.get("policy_selected_at", "")).strip()        
        return result

    def get_current_chat_model(self) -> Dict[str, Any]:
        current = self.registry_service.get_current_model()
        normalized = self._normalize_model(current)

        if normalized.get("available", False):
            return normalized

        provider = self._normalize_provider(normalized.get("provider"))
        best_same_provider = self.registry_service.get_best_available_model(provider=provider)
        if best_same_provider:
            return self._normalize_model(best_same_provider)

        best_any = self.registry_service.get_best_available_model()
        if best_any:
            return self._normalize_model(best_any)

        return normalized

    def has_available_chat_model(self, provider: str | None = None) -> bool:
        best = self.registry_service.get_best_available_model(provider=provider)
        return bool(best)

    def get_current_model_status(self) -> Dict[str, Any]:
        current = self.get_current_chat_model()
        return {
            "provider": self._normalize_provider(current.get("provider")),
            "model_name": str(current.get("model_name", "")).strip(),
            "available": bool(current.get("available", False)),
            "source": str(current.get("source", "")).strip(),
        }

    def get_current_provider(self) -> str:
        current_model = self.get_current_chat_model()
        return self._normalize_provider(current_model.get("provider"))

    def get_provider_display_name(self, provider: str) -> str:
        provider = self._normalize_provider(provider)
        return {
            "ollama": "Ollama",
            "local": "Local",
            "api": "API",
        }.get(provider, "Ollama")
    
    def get_current_reply_policy(self) -> Dict[str, Any]:
        model = self.get_current_chat_model()
        policy_profile = model.get("policy_profile", {})
        if not isinstance(policy_profile, dict):
            policy_profile = {}

        return {
            "family": str(model.get("family", "unknown")).strip().lower() or "unknown",
            "size_tier": str(model.get("size_tier", "medium")).strip().lower() or "medium",
            "policy_version": str(model.get("policy_version", "v1")).strip() or "v1",
            "policy_selected_at": str(model.get("policy_selected_at", "")).strip(),
            **policy_profile,
        }
    
    def get_reply_profile(self, request_type: str = "chat") -> Dict:
        model = self.get_current_chat_model()

        provider = self._normalize_provider(model.get("provider", "ollama"))
        hardware_level = str(model.get("hardware_level", "low")).strip().lower()
        speed_level = str(model.get("speed_level", "medium")).strip().lower()

        reply_prompt_mode = str(model.get("reply_prompt_mode", "")).strip().lower()
        if reply_prompt_mode in ("fast", "full"):
            prompt_mode = reply_prompt_mode
        else:
            prompt_mode = self._infer_prompt_mode(
                request_type=request_type,
                provider=provider,
                hardware_level=hardware_level,
                speed_level=speed_level,
            )

        presence_enabled = bool(model.get("presence_enabled", True))
        stream_visible = bool(model.get("stream_visible", True))

        repair_policy = str(model.get("repair_policy", "")).strip().lower()
        if repair_policy not in ("never", "fallback_only", "always"):
            repair_policy = "fallback_only"

        current_policy = self.get_current_reply_policy()

        return {
            "prompt_mode": prompt_mode,
            "presence_enabled": presence_enabled,
            "stream_visible": stream_visible,
            "repair_policy": repair_policy,
            "provider": provider,
            "hardware_level": hardware_level,
            "speed_level": speed_level,

            # 新增：后续给 chat_runtime / pipeline 用
            "family": current_policy.get("family", "unknown"),
            "size_tier": current_policy.get("size_tier", "medium"),
            "policy_profile": current_policy,
        }

    def _infer_prompt_mode(
        self,
        *,
        request_type: str,
        provider: str,
        hardware_level: str,
        speed_level: str,
    ) -> str:
        request_type = (request_type or "chat").strip().lower()

        if hardware_level == "low":
            return "fast"

        if speed_level == "fast":
            return "fast"

        if provider in ("api", "web"):
            if request_type in ("comfort", "task"):
                return "full"
            return "fast"

        if provider == "ollama":
            if request_type == "comfort" and hardware_level in ("mid", "high") and speed_level != "fast":
                return "full"
            return "fast"

        if provider == "local":
            if request_type == "task" and hardware_level in ("mid", "high"):
                return "full"
            return "fast"

        return "fast"