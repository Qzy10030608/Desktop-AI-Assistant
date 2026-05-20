from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from bootstrap.hundun.make import make_local_files
from bootstrap.hundun.path import get_project_root


def _read_json(path: Path, default: Dict[str, Any]) -> Dict[str, Any]:
    if not path.exists():
        return default
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else default
    except Exception:
        return default


def ensure_local_data_files(project_root: str | Path | None = None, force: bool = False) -> Dict[str, str]:
    return make_local_files(project_root=project_root, force=force)


def _local_path(name: str, project_root: str | Path | None = None) -> Path:
    root = get_project_root(project_root)
    base = root / "data" / "user_prefs"
    mapping = {
        "machine": base / "machine.local.json",
        "mode": base / "desktop_mode.local.json",
        "roots": base / "roots.local.json",
        "disks": base / "disks.local.json",
        "apps": base / "apps.local.json",
        "apps_candidates": base / "apps.candidates.local.json",
        "search": base / "search.local.json",
        "engines": base / "engines.local.json",
        "install": base / "install.local.json",
    }
    return mapping[name]


def _runtime_path(name: str, project_root: str | Path | None = None) -> Path:
    root = get_project_root(project_root)
    base = root / "data" / "runtime"
    mapping = {
        "engine_runtime": base / "engine_runtime.json",
        "desktop_runtime": base / "desktop_runtime.json",
    }
    return mapping[name]


def get_machine_local(project_root: str | Path | None = None) -> Dict[str, Any]:
    return _read_json(_local_path("machine", project_root), {})


def get_engines_local(project_root: str | Path | None = None) -> Dict[str, Any]:
    return _read_json(_local_path("engines", project_root), {"engines": {}, "llm": {}})


def get_engine_config(engine_key: str, project_root: str | Path | None = None) -> Dict[str, Any]:
    data = get_engines_local(project_root)
    engines = data.get("engines", {}) if isinstance(data.get("engines"), dict) else {}
    item = engines.get(engine_key, {})
    return item if isinstance(item, dict) else {}


def get_desktop_mode_local(project_root: str | Path | None = None) -> Dict[str, Any]:
    return _read_json(_local_path("mode", project_root), {"current_mode": "disabled"})


def get_roots_local(project_root: str | Path | None = None) -> Dict[str, Any]:
    return _read_json(_local_path("roots", project_root), {"roots": []})


def get_disks_local(project_root: str | Path | None = None) -> Dict[str, Any]:
    return _read_json(_local_path("disks", project_root), {"disks": []})


def get_apps_local(project_root: str | Path | None = None) -> Dict[str, Any]:
    return _read_json(_local_path("apps", project_root), {"apps": []})


def get_apps_candidates_local(project_root: str | Path | None = None) -> Dict[str, Any]:
    return _read_json(_local_path("apps_candidates", project_root), {"apps": []})


def get_search_local(project_root: str | Path | None = None) -> Dict[str, Any]:
    return _read_json(_local_path("search", project_root), {"enabled": False, "roots": [], "file_types": [], "max_depth": 5})


def get_install_local(project_root: str | Path | None = None) -> Dict[str, Any]:
    return _read_json(_local_path("install", project_root), {"initialized": False})


def get_engine_runtime(project_root: str | Path | None = None) -> Dict[str, Any]:
    return _read_json(_runtime_path("engine_runtime", project_root), {
        "startup": {
            "auto_detect_engines": True,
            "last_startup_check_at": "",
            "last_startup_status": "unknown",
        },
        "ollama": {"last_health_ok": False, "last_error": ""},
        "gpt_sovits": {"last_health_ok": False, "last_error": ""},
    })
