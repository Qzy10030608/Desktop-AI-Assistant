from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, List

from bootstrap.hundun.load import (
    get_engine_config,
    get_engine_runtime,
    get_engines_local,
    get_machine_local,
    get_project_root,
    get_search_local,
)


class MachineProfileService:
    """
    过渡兼容桥：
    1. 优先读取新的 local/runtime 文件
    2. 对旧代码继续提供 machine_profile 风格接口
    3. 这一轮先不让 TTS / LLM 业务直接崩
    """

    def __init__(self, project_root: str | None = None):
        self.project_root = get_project_root(project_root)

        self.user_prefs_dir = self.project_root / "data" / "user_prefs"
        self.runtime_dir = self.project_root / "data" / "runtime"
        self.profile_path = self.user_prefs_dir / "machine.local.json"

    @property
    def profile_path_str(self) -> str:
        return str(self.profile_path)

    def _read_json(self, path: Path, default: Dict[str, Any]) -> Dict[str, Any]:
        if not path.exists():
            return default
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else default
        except Exception:
            return default

    def _write_json(self, path: Path, data: Dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def _merge_dict(self, base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        result = deepcopy(base)
        for key, value in override.items():
            if isinstance(value, dict) and isinstance(result.get(key), dict):
                result[key] = self._merge_dict(result[key], value)
            else:
                result[key] = value
        return result

    def get_profile(self) -> Dict[str, Any]:
        machine = get_machine_local(self.project_root)
        engines_bundle = get_engines_local(self.project_root)
        runtime = get_engine_runtime(self.project_root)
        search_local = get_search_local(self.project_root)

        ollama = get_engine_config("ollama", self.project_root)
        gpt = get_engine_config("gpt_sovits", self.project_root)
        llm = engines_bundle.get("llm", {}) if isinstance(engines_bundle.get("llm"), dict) else {}

        return {
            "schema_version": 3,
            "startup": runtime.get("startup", {}),
            "ollama": {
                "enabled": bool(ollama.get("enabled", True)),
                "provider": "ollama",
                "host": str(ollama.get("host", "http://localhost:11434")).strip() or "http://localhost:11434",
                "last_health_ok": bool(runtime.get("ollama", {}).get("last_health_ok", False)),
                "last_error": str(runtime.get("ollama", {}).get("last_error", "")).strip(),
            },
            "gpt_sovits": {
                "enabled": bool(gpt.get("enabled", False)),
                "root_dir": str(gpt.get("root_dir", "")).strip(),
                "python_exe": str(gpt.get("python_exe", "")).strip(),
                "host": str(gpt.get("host", "127.0.0.1")).strip() or "127.0.0.1",
                "port": int(gpt.get("port", 9880) or 9880),
                "api_script": str(gpt.get("api_script", "api_v2.py")).strip() or "api_v2.py",
                "tts_config": str(gpt.get("tts_config", "GPT_SoVITS/configs/tts_infer.yaml")).strip() or "GPT_SoVITS/configs/tts_infer.yaml",
                "last_health_ok": bool(runtime.get("gpt_sovits", {}).get("last_health_ok", False)),
                "last_error": str(runtime.get("gpt_sovits", {}).get("last_error", "")).strip(),
                "recent_valid_root_dirs": list(gpt.get("recent_valid_root_dirs", []) or []),
            },
            "llm": {
                "preferred_provider": str(llm.get("preferred_provider", "ollama")).strip() or "ollama",
                "fallback_provider": str(llm.get("fallback_provider", "ollama")).strip() or "ollama",
            },
            "desktop": {
                "vscode_path": "",
                "default_project_dir": str(machine.get("project_root", "")).strip(),
            },
            "search_paths": search_local,
        }

    def save_profile(self, profile: Dict[str, Any]) -> None:
        # 这轮不再保存旧总包，只做分流写入
        profile = profile or {}
        if "startup" in profile:
            self.update_section("startup", profile.get("startup", {}))
        if "ollama" in profile:
            self.update_section("ollama", profile.get("ollama", {}))
        if "gpt_sovits" in profile:
            self.update_section("gpt_sovits", profile.get("gpt_sovits", {}))
        if "llm" in profile:
            self.update_section("llm", profile.get("llm", {}))
        if "search_paths" in profile:
            self.update_section("search_paths", profile.get("search_paths", {}))

    def update_section(self, section: str, data: Dict[str, Any]) -> None:
        data = data or {}

        if section in {"ollama", "gpt_sovits", "llm"}:
            path = self.user_prefs_dir / "engines.local.json"
            current = self._read_json(path, {"llm": {}, "engines": {}})
            if section == "llm":
                block = current.get("llm", {})
                if not isinstance(block, dict):
                    block = {}
                block.update(data)
                current["llm"] = block
            else:
                engines = current.get("engines", {})
                if not isinstance(engines, dict):
                    engines = {}
                block = engines.get(section, {})
                if not isinstance(block, dict):
                    block = {}
                block.update(data)
                engines[section] = block
                current["engines"] = engines
            self._write_json(path, current)
            return

        if section == "startup":
            path = self.runtime_dir / "engine_runtime.json"
            current = self._read_json(path, {})
            block = current.get("startup", {})
            if not isinstance(block, dict):
                block = {}
            block.update(data)
            current["startup"] = block
            self._write_json(path, current)
            return

        if section == "search_paths":
            path = self.user_prefs_dir / "search.local.json"
            current = self._read_json(path, {})
            current.update(data)
            self._write_json(path, current)
            return

    def append_recent_valid_gpt_root(self, root_dir: str) -> None:
        root_dir = str(root_dir or "").strip()
        if not root_dir:
            return

        path = self.user_prefs_dir / "engines.local.json"
        current = self._read_json(path, {"llm": {}, "engines": {}})
        engines = current.get("engines", {})
        if not isinstance(engines, dict):
            engines = {}
        gpt = engines.get("gpt_sovits", {})
        if not isinstance(gpt, dict):
            gpt = {}

        recent = list(gpt.get("recent_valid_root_dirs", []) or [])
        recent = [item for item in recent if str(item).strip() and str(item).strip() != root_dir]
        recent.insert(0, root_dir)
        gpt["recent_valid_root_dirs"] = recent[:8]

        engines["gpt_sovits"] = gpt
        current["engines"] = engines
        self._write_json(path, current)

    def get_recent_valid_gpt_roots(self) -> List[str]:
        gpt = self.get_gpt_sovits_config()
        result: List[str] = []
        for item in gpt.get("recent_valid_root_dirs", []) or []:
            value = str(item or "").strip()
            if value:
                result.append(value)
        return result

    def get_preferred_llm_provider(self) -> str:
        profile = self.get_profile()
        llm = profile.get("llm", {})
        provider = str(llm.get("preferred_provider", "ollama")).strip().lower()
        return provider or "ollama"

    def get_ollama_config(self) -> Dict[str, Any]:
        profile = self.get_profile()
        ollama = profile.get("ollama", {})
        if not isinstance(ollama, dict):
            ollama = {}

        return {
            "enabled": bool(ollama.get("enabled", True)),
            "provider": "ollama",
            "host": str(ollama.get("host", "http://localhost:11434")).strip() or "http://localhost:11434",
            "last_health_ok": bool(ollama.get("last_health_ok", False)),
            "last_error": str(ollama.get("last_error", "")).strip(),
        }

    def get_ollama_host(self) -> str:
        return self.get_ollama_config()["host"]

    def get_gpt_sovits_config(self) -> Dict[str, Any]:
        profile = self.get_profile()
        gpt = profile.get("gpt_sovits", {})
        if not isinstance(gpt, dict):
            gpt = {}

        return {
            "enabled": bool(gpt.get("enabled", False)),
            "root_dir": str(gpt.get("root_dir", "")).strip(),
            "python_exe": str(gpt.get("python_exe", "")).strip(),
            "host": str(gpt.get("host", "127.0.0.1")).strip() or "127.0.0.1",
            "port": int(gpt.get("port", 9880) or 9880),
            "api_script": str(gpt.get("api_script", "api_v2.py")).strip() or "api_v2.py",
            "tts_config": str(gpt.get("tts_config", "GPT_SoVITS/configs/tts_infer.yaml")).strip() or "GPT_SoVITS/configs/tts_infer.yaml",
            "last_health_ok": bool(gpt.get("last_health_ok", False)),
            "last_error": str(gpt.get("last_error", "")).strip(),
            "recent_valid_root_dirs": list(gpt.get("recent_valid_root_dirs", []) or []),
        }

    def set_ollama_health(self, ok: bool, error: str = "") -> None:
        path = self.runtime_dir / "engine_runtime.json"
        current = self._read_json(path, {})
        block = current.get("ollama", {})
        if not isinstance(block, dict):
            block = {}
        block.update({
            "last_health_ok": bool(ok),
            "last_error": str(error or "").strip(),
        })
        current["ollama"] = block
        self._write_json(path, current)

    def set_gpt_sovits_health(self, ok: bool, error: str = "") -> None:
        path = self.runtime_dir / "engine_runtime.json"
        current = self._read_json(path, {})
        block = current.get("gpt_sovits", {})
        if not isinstance(block, dict):
            block = {}
        block.update({
            "last_health_ok": bool(ok),
            "last_error": str(error or "").strip(),
        })
        current["gpt_sovits"] = block
        self._write_json(path, current)

    def set_startup_status(self, status: str, checked_at: str) -> None:
        path = self.runtime_dir / "engine_runtime.json"
        current = self._read_json(path, {})
        block = current.get("startup", {})
        if not isinstance(block, dict):
            block = {}
        block.update({
            "last_startup_status": str(status or "unknown"),
            "last_startup_check_at": str(checked_at or ""),
        })
        current["startup"] = block
        self._write_json(path, current)
