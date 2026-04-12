from __future__ import annotations

import json
import os
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, List


class MachineProfileService:
    """
    机器配置服务
    -------------------------
    作用：
    1. 保存每台电脑自己的本地路径与连接信息
    2. 统一提供 GPT-SoVITS / Ollama 的机器级配置
    3. 记录最近成功路径与有限候选路径
    4. 避免以后换电脑时再去硬改 config.py
    """

    def __init__(self, project_root: str | None = None):
        if project_root:
            self.project_root = Path(project_root).expanduser().resolve()
        else:
            # bootstrap/ 的上一层就是项目根目录
            self.project_root = Path(__file__).resolve().parent.parent

        self.user_prefs_dir = self.project_root / "data" / "user_prefs"
        self.profile_path = self.user_prefs_dir / "machine_profile.json"

        self.user_prefs_dir.mkdir(parents=True, exist_ok=True)
        self._ensure_profile_file()

    @property
    def profile_path_str(self) -> str:
        return str(self.profile_path)

    def _env_int(self, key: str, default: int) -> int:
        raw = os.environ.get(key, "").strip()
        if not raw:
            return default
        try:
            return int(raw)
        except Exception:
            return default

    def _default_profile(self) -> Dict[str, Any]:
        return {
            "schema_version": 2,
            "startup": {
                "auto_detect_engines": True,
                "last_startup_check_at": "",
                "last_startup_status": "unknown",
            },
            "ollama": {
                "enabled": True,
                "provider": "ollama",
                "host": os.environ.get("OLLAMA_HOST", "http://localhost:11434").strip()
                or "http://localhost:11434",
                "last_health_ok": False,
                "last_error": "",
            },
            "gpt_sovits": {
                "enabled": True,
                "root_dir": os.environ.get("GPT_SOVITS_ROOT", "").strip(),
                "python_exe": os.environ.get("GPT_SOVITS_PYTHON_EXE", "").strip(),
                "host": os.environ.get("GPT_SOVITS_HOST", "127.0.0.1").strip() or "127.0.0.1",
                "port": self._env_int("GPT_SOVITS_PORT", 9880),
                "api_script": os.environ.get("GPT_SOVITS_API_SCRIPT", "api_v2.py").strip() or "api_v2.py",
                "tts_config": os.environ.get(
                    "GPT_SOVITS_TTS_CONFIG",
                    "GPT_SoVITS/configs/tts_infer.yaml",
                ).strip() or "GPT_SoVITS/configs/tts_infer.yaml",
                "last_health_ok": False,
                "last_error": "",
                "recent_valid_root_dirs": [],
            },
            "llm": {
                "preferred_provider": "ollama",
                "fallback_provider": "ollama",
            },
            "desktop": {
                "vscode_path": "",
                "default_project_dir": "",
            },
            "search_paths": {
                "enabled": False,
                "roots": [],
                "max_depth": 5,
            },
        }

    def _read_json(self) -> Dict[str, Any]:
        if not self.profile_path.exists():
            return {}
        try:
            data = json.loads(self.profile_path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _write_json(self, data: Dict[str, Any]) -> None:
        self.profile_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _merge_dict(self, base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        result = deepcopy(base)
        for key, value in override.items():
            if isinstance(value, dict) and isinstance(result.get(key), dict):
                result[key] = self._merge_dict(result[key], value)
            else:
                result[key] = value
        return result

    def _ensure_profile_file(self) -> None:
        if self.profile_path.exists():
            current = self._read_json()
            merged = self._merge_dict(self._default_profile(), current)
            if merged != current:
                self._write_json(merged)
            return

        self._write_json(self._default_profile())

    def get_profile(self) -> Dict[str, Any]:
        current = self._read_json()
        return self._merge_dict(self._default_profile(), current)

    def save_profile(self, profile: Dict[str, Any]) -> None:
        merged = self._merge_dict(self._default_profile(), profile or {})
        self._write_json(merged)

    def update_section(self, section: str, data: Dict[str, Any]) -> None:
        profile = self.get_profile()
        block = profile.get(section, {})
        if not isinstance(block, dict):
            block = {}
        block.update(data or {})
        profile[section] = block
        self.save_profile(profile)

    def append_recent_valid_gpt_root(self, root_dir: str) -> None:
        root_dir = str(root_dir or "").strip()
        if not root_dir:
            return

        profile = self.get_profile()
        gpt = profile.get("gpt_sovits", {})
        recent = list(gpt.get("recent_valid_root_dirs", []) or [])
        recent = [item for item in recent if str(item).strip() and str(item).strip() != root_dir]
        recent.insert(0, root_dir)
        gpt["recent_valid_root_dirs"] = recent[:8]
        profile["gpt_sovits"] = gpt
        self.save_profile(profile)

    def get_recent_valid_gpt_roots(self) -> List[str]:
        profile = self.get_profile()
        gpt = profile.get("gpt_sovits", {})
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
            "host": str(ollama.get("host", "http://localhost:11434")).strip()
            or "http://localhost:11434",
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
            "enabled": bool(gpt.get("enabled", True)),
            "root_dir": str(gpt.get("root_dir", "")).strip(),
            "python_exe": str(gpt.get("python_exe", "")).strip(),
            "host": str(gpt.get("host", "127.0.0.1")).strip() or "127.0.0.1",
            "port": int(gpt.get("port", 9880) or 9880),
            "api_script": str(gpt.get("api_script", "api_v2.py")).strip() or "api_v2.py",
            "tts_config": str(
                gpt.get("tts_config", "GPT_SoVITS/configs/tts_infer.yaml")
            ).strip() or "GPT_SoVITS/configs/tts_infer.yaml",
            "last_health_ok": bool(gpt.get("last_health_ok", False)),
            "last_error": str(gpt.get("last_error", "")).strip(),
            "recent_valid_root_dirs": list(gpt.get("recent_valid_root_dirs", []) or []),
        }

    def set_ollama_health(self, ok: bool, error: str = "") -> None:
        self.update_section(
            "ollama",
            {
                "last_health_ok": bool(ok),
                "last_error": str(error or "").strip(),
            },
        )

    def set_gpt_sovits_health(self, ok: bool, error: str = "") -> None:
        self.update_section(
            "gpt_sovits",
            {
                "last_health_ok": bool(ok),
                "last_error": str(error or "").strip(),
            },
        )

    def set_startup_status(self, status: str, checked_at: str) -> None:
        self.update_section(
            "startup",
            {
                "last_startup_status": str(status or "unknown"),
                "last_startup_check_at": str(checked_at or ""),
            },
        )