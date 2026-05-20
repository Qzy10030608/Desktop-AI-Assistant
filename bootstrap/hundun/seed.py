from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from bootstrap.hundun.path import get_project_root


def _read_json(path: Path, default: Dict[str, Any]) -> Dict[str, Any]:
    if not path.exists():
        return default
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else default
    except Exception:
        return default


def _fallback_defaults() -> Dict[str, Dict[str, Any]]:
    return {
        "desktop_mode": {
            "available_modes": ["disabled", "restricted", "trusted"],
            "default_mode": "disabled",
            "labels": {
                "disabled": "不启用",
                "restricted": "限制模式",
                "trusted": "信任模式",
            },
        },
        "perms": {
            "allow_file_search": True,
            "allow_file_open": True,
            "allow_folder_open": True,
            "allow_app_launch": True,
            "require_confirm_before_launch": True,
            "allow_screenshot": False,
            "allow_attach_app": False,
            "allow_close_app": False,
            "allow_write": False,
            "allow_delete": False,
        },
        "app_map": {
            "apps": []
        },
        "root_seed": {
            "roots": [
                {
                    "root_id": "project_root",
                    "title": "项目目录",
                    "path_token": "${PROJECT_ROOT}",
                    "enabled": True,
                    "index_enabled": True,
                    "allow_search": True,
                    "allow_open_file": True,
                    "allow_open_folder": True,
                    "allow_read_meta": True,
                }
            ]
        },
        "engine_map": {
            "engines": {
                "ollama": {
                    "enabled": True,
                    "provider": "ollama",
                    "default_host": "http://localhost:11434",
                    "needs_local_bind": False,
                },
                "gpt_sovits": {
                    "enabled": False,
                    "default_host": "127.0.0.1",
                    "default_port": 9880,
                    "api_script": "api_v2.py",
                    "tts_config": "GPT_SoVITS/configs/tts_infer.yaml",
                    "needs_local_bind": True,
                },
            }
        },
        "search_seed": {
            "enabled": False,
            "file_types": [],
            "max_depth": 5,
        },
        "init_seed": {
            "init_version": 1,
            "auto_make_local_files": True,
            "auto_discover_apps": True,
            "auto_discover_engines": True,
            "show_init_dialog_on_first_run": True,
        },
        "reply_policy": {},
    }


def load_defaults(project_root: str | Path | None = None) -> Dict[str, Dict[str, Any]]:
    root = get_project_root(project_root)
    defaults_dir = root / "data" / "defaults"
    fallback = _fallback_defaults()

    mapping = {
        "desktop_mode": defaults_dir / "desktop_mode.json",
        "perms": defaults_dir / "perms.json",
        "app_map": defaults_dir / "app_map.json",
        "root_seed": defaults_dir / "root_seed.json",
        "engine_map": defaults_dir / "engine_map.json",
        "search_seed": defaults_dir / "search_seed.json",
        "init_seed": defaults_dir / "init_seed.json",
        "reply_policy": defaults_dir / "reply_policy.json",
    }

    result: Dict[str, Dict[str, Any]] = {}
    for key, path in mapping.items():
        result[key] = _read_json(path, fallback[key])

    return result