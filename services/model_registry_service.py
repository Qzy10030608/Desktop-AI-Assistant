import json
from pathlib import Path
from typing import Dict, List, Optional
from services.reply.model_reply_policy_service import ModelReplyPolicyService  # type: ignore
from bootstrap.machine_profile_service import MachineProfileService
from config import (  # type: ignore
    BASE_DIR,
    CURRENT_MODEL_FILE,
    MODEL_REGISTRY_DIR,
    OLLAMA_CONNECT_TIMEOUT,
    OLLAMA_HOST,
    OLLAMA_MODEL,
    OLLAMA_NUM_CTX,
    OLLAMA_NUM_PREDICT,
    OLLAMA_READ_TIMEOUT,
    OLLAMA_TEMPERATURE,
    OLLAMA_TOP_P,
)


class ModelRegistryService:
    def __init__(self, machine_profile_service: Optional[MachineProfileService] = None):
        self.machine_profile_service = machine_profile_service or MachineProfileService(BASE_DIR)
        self.base_dir = Path(BASE_DIR)
        self.models_dir = Path(MODEL_REGISTRY_DIR)
        self.runtime_dir = self.base_dir / "data" / "runtime"

        self.registry_file = self.models_dir / "model_registry.json"
        self.current_model_file = Path(CURRENT_MODEL_FILE)

        self.models_dir.mkdir(parents=True, exist_ok=True)
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        self.policy_service = ModelReplyPolicyService()

        self._ensure_registry_file()
        self._ensure_current_model_file()

    def _default_host(self) -> str:
        try:
            return self.machine_profile_service.get_ollama_host()
        except Exception:
            return OLLAMA_HOST

    def _default_model_data(self) -> Dict:
        data = {
            "id": "ollama_default",
            "name": "Default Ollama",
            "enabled": True,
            "provider": "ollama",
            "model_name": OLLAMA_MODEL,
            "type": "chat",
            "host": self._default_host(),
            "connect_timeout": OLLAMA_CONNECT_TIMEOUT,
            "read_timeout": OLLAMA_READ_TIMEOUT,
            "num_ctx": OLLAMA_NUM_CTX,
            "num_predict": OLLAMA_NUM_PREDICT,
            "temperature": OLLAMA_TEMPERATURE,
            "top_p": OLLAMA_TOP_P,
            "keep_alive": "10m",
            "reply_prompt_mode": "",
            "presence_enabled": True,
            "stream_visible": True,
            "repair_policy": "fallback_only",
            "supports_style_rewrite": True,
            "supports_reasoning": False,
            "supports_tools": False,
            "hardware_level": "low",
            "speed_level": "medium",
            "api_base": "",
            "api_key": "",
            "executable_path": "",
            "model_path": "",
            "available": False,
            "source": "fallback_default",

            # 新增：模型回复策略字段
            "family": "",
            "size_tier": "",
            "family_override": "",
            "size_tier_override": "",
            "policy_override": {},
            "policy_profile": {},
            "policy_version": "v1",
            "policy_selected_at": "",
        }
        return self.policy_service.enrich_model_profile(data)

    def _read_json(self, path: Path) -> Dict:
        if not path.exists():
            return {}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _write_json(self, path: Path, data: Dict):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _normalize_model(self, model: Dict) -> Dict:
        base = self._default_model_data()
        result = dict(base)
        result.update(model or {})

        provider = str(result.get("provider", "ollama")).strip().lower()
        if provider not in ("ollama", "local", "api"):
            provider = "ollama"
        result["provider"] = provider

        result["id"] = str(result.get("id", "")).strip() or "ollama_default"
        result["name"] = str(result.get("name", "")).strip() or str(result.get("model_name", "")).strip() or "Unnamed Model"
        result["model_name"] = str(result.get("model_name", OLLAMA_MODEL)).strip() or OLLAMA_MODEL
        result["type"] = str(result.get("type", "chat")).strip() or "chat"
        result["host"] = str(result.get("host", self._default_host())).strip() or self._default_host()

        result["enabled"] = bool(result.get("enabled", True))
        result["connect_timeout"] = int(result.get("connect_timeout", OLLAMA_CONNECT_TIMEOUT) or OLLAMA_CONNECT_TIMEOUT)
        result["read_timeout"] = int(result.get("read_timeout", OLLAMA_READ_TIMEOUT) or OLLAMA_READ_TIMEOUT)
        result["num_ctx"] = int(result.get("num_ctx", OLLAMA_NUM_CTX) or OLLAMA_NUM_CTX)
        result["num_predict"] = int(result.get("num_predict", OLLAMA_NUM_PREDICT))
        result["temperature"] = float(result.get("temperature", OLLAMA_TEMPERATURE))
        result["top_p"] = float(result.get("top_p", OLLAMA_TOP_P))
        result["keep_alive"] = str(result.get("keep_alive", "10m")).strip() or "10m"

        result["reply_prompt_mode"] = str(result.get("reply_prompt_mode", "")).strip().lower()
        result["presence_enabled"] = bool(result.get("presence_enabled", True))
        result["stream_visible"] = bool(result.get("stream_visible", True))
        result["repair_policy"] = str(result.get("repair_policy", "fallback_only")).strip().lower() or "fallback_only"

        result["supports_style_rewrite"] = bool(result.get("supports_style_rewrite", True))
        result["supports_reasoning"] = bool(result.get("supports_reasoning", False))
        result["supports_tools"] = bool(result.get("supports_tools", False))
        result["hardware_level"] = str(result.get("hardware_level", "low")).strip().lower() or "low"
        result["speed_level"] = str(result.get("speed_level", "medium")).strip().lower() or "medium"

        result["api_base"] = str(result.get("api_base", "")).strip()
        result["api_key"] = str(result.get("api_key", "")).strip()
        result["executable_path"] = str(result.get("executable_path", "")).strip()
        result["model_path"] = str(result.get("model_path", "")).strip()

        result["available"] = bool(result.get("available", False))
        result["source"] = str(result.get("source", "registry")).strip() or "registry"

        result["family"] = str(result.get("family", "")).strip().lower()
        result["size_tier"] = str(result.get("size_tier", "")).strip().lower()
        result["family_override"] = str(result.get("family_override", "")).strip().lower()
        result["size_tier_override"] = str(result.get("size_tier_override", "")).strip().lower()

        policy_override = result.get("policy_override", {})
        result["policy_override"] = policy_override if isinstance(policy_override, dict) else {}

        policy_profile = result.get("policy_profile", {})
        result["policy_profile"] = policy_profile if isinstance(policy_profile, dict) else {}

        result["policy_version"] = str(result.get("policy_version", "v1")).strip() or "v1"
        result["policy_selected_at"] = str(result.get("policy_selected_at", "")).strip()

        result = self.policy_service.enrich_model_profile(result)
        return result

    def _ensure_registry_file(self):
        if self.registry_file.exists():
            data = self.get_registry()
            self.save_registry(data)
            return

        data = {
            "default_chat_model_id": "ollama_default",
            "models": [self._default_model_data()],
        }
        self._write_json(self.registry_file, data)

    def _ensure_current_model_file(self):
        if self.current_model_file.exists():
            return

        self._write_json(
            self.current_model_file,
            {"model_id": self.get_default_model_id()},
        )

    def get_registry(self) -> Dict:
        data = self._read_json(self.registry_file)
        models = data.get("models", [])
        if not isinstance(models, list):
            models = []

        normalized_models: List[Dict] = []
        has_default = False
        for item in models:
            if not isinstance(item, dict):
                continue
            model = self._normalize_model(item)
            normalized_models.append(model)
            if model.get("id") == "ollama_default":
                has_default = True

        if not has_default:
            normalized_models.insert(0, self._default_model_data())

        default_chat_model_id = str(data.get("default_chat_model_id", "")).strip()
        if not default_chat_model_id:
            default_chat_model_id = "ollama_default"

        return {
            "default_chat_model_id": default_chat_model_id,
            "models": normalized_models,
        }

    def save_registry(self, data: Dict) -> None:
        registry = self.get_registry()
        registry.update(data or {})

        models = registry.get("models", [])
        final_models: List[Dict] = []
        if isinstance(models, list):
            for item in models:
                if isinstance(item, dict):
                    final_models.append(self._normalize_model(item))

        if not any(m.get("id") == "ollama_default" for m in final_models):
            final_models.insert(0, self._default_model_data())

        registry["models"] = final_models

        default_id = str(registry.get("default_chat_model_id", "")).strip()
        if not default_id or not any(m.get("id") == default_id for m in final_models):
            best = self.get_best_available_model_from_list(final_models)
            registry["default_chat_model_id"] = str(best.get("id", "ollama_default")).strip() or "ollama_default"

        self._write_json(self.registry_file, registry)

    def list_models(self, provider: Optional[str] = None) -> List[Dict]:
        registry = self.get_registry()
        models = registry.get("models", [])
        result: List[Dict] = []

        for item in models:
            if not isinstance(item, dict):
                continue
            normalized = self._normalize_model(item)
            if provider and str(normalized.get("provider", "")).strip().lower() != str(provider).strip().lower():
                continue
            result.append(normalized)

        return result

    def list_enabled_models(self, provider: Optional[str] = None) -> List[Dict]:
        return [item for item in self.list_models(provider=provider) if item.get("enabled", True)]

    def list_available_models(self, provider: Optional[str] = None) -> List[Dict]:
        return [
            item
            for item in self.list_enabled_models(provider=provider)
            if bool(item.get("available", False))
        ]
    def list_connection_candidate_models(self, provider: Optional[str] = None) -> List[Dict]:
        enabled_models = self.list_enabled_models(provider=provider)
        available_models = [
            item for item in enabled_models
            if bool(item.get("available", False))
        ]

        if available_models:
            return available_models

        return enabled_models
    def split_connection_models(self, provider: Optional[str] = None) -> Dict[str, List[Dict]]:
        enabled_models = self.list_enabled_models(provider=provider)

        available: List[Dict] = []
        unavailable: List[Dict] = []

        for item in enabled_models:
            if bool(item.get("available", False)):
                available.append(item)
            else:
                unavailable.append(item)

        return {
            "available": available,
            "unavailable": unavailable,
        }
    def get_model_by_id(self, model_id: str) -> Dict:
        model_id = (model_id or "").strip()
        if not model_id:
            return {}

        for item in self.list_models():
            if str(item.get("id", "")).strip() == model_id:
                return item
        return {}

    def find_model_by_any_key(self, value: str) -> Dict:
        key = (value or "").strip()
        if not key:
            return {}

        for item in self.list_models():
            if (
                str(item.get("id", "")).strip() == key
                or str(item.get("name", "")).strip() == key
                or str(item.get("model_name", "")).strip() == key
            ):
                return item
        return {}

    def is_model_available(self, model_id: str) -> bool:
        model = self.get_model_by_id(model_id)
        return bool(model.get("available", False)) if model else False

    def get_best_available_model_from_list(self, models: List[Dict], provider: Optional[str] = None) -> Dict:
        for item in models:
            normalized = self._normalize_model(item)
            if provider and str(normalized.get("provider", "")).strip().lower() != str(provider).strip().lower():
                continue
            if normalized.get("enabled", True) and normalized.get("available", False):
                return normalized
        return {}

    def get_best_available_model(self, provider: Optional[str] = None) -> Dict:
        return self.get_best_available_model_from_list(self.list_models(), provider=provider)

    def get_default_model_id(self) -> str:
        registry = self.get_registry()
        default_id = str(registry.get("default_chat_model_id", "")).strip()

        if default_id:
            model = self.get_model_by_id(default_id)
            if model and model.get("enabled", True) and model.get("available", False):
                return default_id

        best = self.get_best_available_model()
        if best:
            return str(best.get("id", "")).strip()

        models = self.list_models()
        if models:
            return str(models[0].get("id", "")).strip()

        return "ollama_default"

    def get_current_model_id(self) -> str:
        data = self._read_json(self.current_model_file)

        raw_value = (
            str(data.get("model_id", "")).strip()
            or str(data.get("id", "")).strip()
            or str(data.get("model_name", "")).strip()
            or str(data.get("name", "")).strip()
        )

        if raw_value:
            found = self.find_model_by_any_key(raw_value)
            if found:
                return str(found.get("id", "")).strip()

        return self.get_default_model_id()

    def set_current_model(self, model_id: str):
        valid = self.find_model_by_any_key(model_id)
        final_model = self._normalize_model(valid) if valid else self.get_current_model()
        final_id = str(final_model.get("id", "")).strip() or self.get_default_model_id()

        if valid:
            self.upsert_model(final_model)
        self._write_json(self.current_model_file, {"model_id": final_id})

    def get_current_model(self) -> Dict:
        current_id = self.get_current_model_id()
        current = self.get_model_by_id(current_id)
        if current and current.get("enabled", True) and current.get("available", False):
            return current

        current_provider = str(current.get("provider", "")).strip().lower() if current else ""
        best_same_provider = self.get_best_available_model(provider=current_provider) if current_provider else {}
        if best_same_provider:
            return best_same_provider

        best_any = self.get_best_available_model()
        if best_any:
            return best_any

        if current:
            return current

        models = self.list_models()
        if models:
            return models[0]

        return self._default_model_data()

    def upsert_model(self, model: Dict) -> Dict:
        normalized = self._normalize_model(model)
        registry = self.get_registry()
        models = registry.get("models", [])
        final_models: List[Dict] = []
        replaced = False

        for item in models:
            if not isinstance(item, dict):
                continue
            old_id = str(item.get("id", "")).strip()
            if old_id == normalized["id"]:
                final_models.append(normalized)
                replaced = True
            else:
                final_models.append(self._normalize_model(item))

        if not replaced:
            final_models.append(normalized)

        registry["models"] = final_models
        self.save_registry(registry)
        return normalized

    def sync_runtime_models(self, provider: str, runtime_models: List[Dict]) -> List[Dict]:
        provider = str(provider or "").strip().lower()
        registry = self.get_registry()
        existing = registry.get("models", [])
        if not isinstance(existing, list):
            existing = []

        runtime_map: Dict[str, Dict] = {}
        for item in runtime_models:
            if not isinstance(item, dict):
                continue
            normalized = self._normalize_model(
                {
                    **item,
                    "provider": provider,
                    "enabled": True,
                    "available": True,
                    "source": "runtime_discovered",
                }
            )
            runtime_map[normalized["id"]] = normalized

        final_models: List[Dict] = []
        seen_runtime_ids = set()

        for item in existing:
            if not isinstance(item, dict):
                continue
            normalized = self._normalize_model(item)

            if str(normalized.get("provider", "")).strip().lower() != provider:
                final_models.append(normalized)
                continue

            model_id = str(normalized.get("id", "")).strip()
            if model_id in runtime_map:
                merged = dict(normalized)
                merged.update(runtime_map[model_id])
                final_models.append(self._normalize_model(merged))
                seen_runtime_ids.add(model_id)
                continue

            if normalized.get("source") in ("runtime_discovered", "fallback_default"):
                normalized["available"] = False

            final_models.append(self._normalize_model(normalized))

        for model_id, model in runtime_map.items():
            if model_id not in seen_runtime_ids:
                final_models.append(model)

        registry["models"] = final_models

        best = self.get_best_available_model_from_list(final_models, provider=provider)
        if best:
            registry["default_chat_model_id"] = str(best.get("id", "ollama_default")).strip() or "ollama_default"

        self.save_registry(registry)
        return self.list_models(provider=provider)