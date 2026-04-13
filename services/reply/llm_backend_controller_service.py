from __future__ import annotations

from typing import Any, Dict, List, Tuple

import requests


class LLMBackendControllerService:
    """
    LLM 后端控制器
    -------------------------
    当前先做统一入口：
    - health_check
    - list_models
    - provider label
    后续再逐步接 local / api 真执行器
    """

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})

    def _normalize_timeout(self, timeout: int | Tuple[int, int]) -> Tuple[int, int]:
        if isinstance(timeout, tuple):
            return timeout
        return (3, timeout)

    def normalize_provider(self, provider: str | None) -> str:
        value = str(provider or "ollama").strip().lower()
        if value not in ("ollama", "local", "api"):
            return "ollama"
        return value

    def get_provider_label(self, provider: str | None) -> str:
        provider = self.normalize_provider(provider)
        return {
            "ollama": "Ollama",
            "local": "Local",
            "api": "API",
        }.get(provider, "Ollama")

    def health_check(
        self,
        provider: str | None = None,
        model_config: Dict[str, Any] | None = None,
        timeout: int | Tuple[int, int] = (3, 8),
    ) -> Dict[str, Any]:
        provider = self.normalize_provider(provider or (model_config or {}).get("provider"))

        if provider == "ollama":
            host = str((model_config or {}).get("host", "http://localhost:11434")).strip() or "http://localhost:11434"
            url = host.rstrip("/") + "/api/tags"
            try:
                resp = self.session.get(url, timeout=self._normalize_timeout(timeout))
                resp.raise_for_status()
                data = resp.json() if resp.content else {}
                models = data.get("models", []) if isinstance(data, dict) else []
                return {
                    "ok": True,
                    "provider": "ollama",
                    "host": host,
                    "model_count": len(models) if isinstance(models, list) else 0,
                    "error": "",
                }
            except Exception as e:
                return {
                    "ok": False,
                    "provider": "ollama",
                    "host": host,
                    "model_count": 0,
                    "error": str(e),
                }

        if provider == "local":
            return {
                "ok": False,
                "provider": "local",
                "error": "provider=local 当前只完成结构预留，尚未接入实际执行器。",
            }

        if provider == "api":
            return {
                "ok": False,
                "provider": "api",
                "error": "provider=api 当前只完成结构预留，尚未接入实际执行器。",
            }

        return {
            "ok": False,
            "provider": provider,
            "error": "未知 provider",
        }

    def list_models(
        self,
        provider: str | None = None,
        model_config: Dict[str, Any] | None = None,
        timeout: int | Tuple[int, int] = (3, 10),
    ) -> List[Dict[str, Any]]:
        provider = self.normalize_provider(provider or (model_config or {}).get("provider"))

        if provider != "ollama":
            return []

        host = str((model_config or {}).get("host", "http://localhost:11434")).strip() or "http://localhost:11434"
        url = host.rstrip("/") + "/api/tags"

        try:
            resp = self.session.get(url, timeout=self._normalize_timeout(timeout))
            resp.raise_for_status()
            data = resp.json() if resp.content else {}
            raw_models = data.get("models", []) if isinstance(data, dict) else []
            result: List[Dict[str, Any]] = []

            if isinstance(raw_models, list):
                for item in raw_models:
                    if not isinstance(item, dict):
                        continue
                    name = str(item.get("name", "")).strip()
                    if not name:
                        continue
                    result.append(
                        {
                            "id": f"ollama::{name}",
                            "name": name,
                            "provider": "ollama",
                            "model_name": name,
                            "host": host,
                            "type": "chat",
                            "enabled": True,
                        }
                    )

            return result
        except Exception:
            return []