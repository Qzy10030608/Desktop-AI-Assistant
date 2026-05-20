from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from bootstrap.hundun.bind import bind_tokens
from bootstrap.hundun.path import collect_machine_paths, get_project_root
from bootstrap.hundun.scan import discover_apps
from bootstrap.hundun.seed import load_defaults


def _read_json(path: Path, default: Dict[str, Any]) -> Dict[str, Any]:
    if not path.exists():
        return default
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else default
    except Exception:
        return default


def _write_json(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _old_json(root: Path, name: str, default: Dict[str, Any]) -> Dict[str, Any]:
    return _read_json(root / "data" / "user_prefs" / name, default)


def _build_machine_local(machine: Dict[str, str]) -> Dict[str, Any]:
    return {
        "schema_version": 1,
        "os": machine["OS"],
        "project_root": machine["PROJECT_ROOT"],
        "user_home": machine["USER_HOME"],
        "documents": machine["DOCUMENTS"],
        "downloads": machine["DOWNLOADS"],
        "desktop": machine["DESKTOP"],
        "appdata": machine["APPDATA"],
        "localappdata": machine["LOCALAPPDATA"],
        "programfiles": machine["PROGRAMFILES"],
        "programfiles_x86": machine["PROGRAMFILES_X86"],
    }


def _build_desktop_mode_local(old_mode: Dict[str, Any], defaults: Dict[str, Any]) -> Dict[str, Any]:
    current_mode = str(old_mode.get("current_mode", "")).strip() or str(defaults.get("default_mode", "disabled")).strip() or "disabled"
    return {
        "current_mode": current_mode,
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    }


def _build_roots_local(old_roots: Dict[str, Any], defaults_roots: Dict[str, Any], machine: Dict[str, str]) -> Dict[str, Any]:
    if old_roots.get("roots"):
        return old_roots

    bound = bind_tokens(defaults_roots, machine)
    return {
        "roots": list(bound.get("roots", []) or []),
    }


def _list_windows_drives() -> List[str]:
    drives: List[str] = []
    for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
        drive = Path(f"{letter}:/")
        if drive.exists():
            drives.append(f"{letter}:")
    return drives


def _build_disks_local(old_disks: Dict[str, Any]) -> Dict[str, Any]:
    existing = old_disks.get("disks", []) or []
    existing_map = {
        str(item.get("disk_id", "")).strip().upper(): item
        for item in existing
        if isinstance(item, dict) and str(item.get("disk_id", "")).strip()
    }
    rows = []
    for disk_id in _list_windows_drives():
        previous = existing_map.get(disk_id.upper(), {})
        rows.append({
            "disk_id": disk_id,
            "title": str(previous.get("title", disk_id)).strip() or disk_id,
            "permission_state": str(previous.get("permission_state", "unset")).strip().lower() or "unset",
            "allow_expand": bool(previous.get("allow_expand", False)),
            "allow_scan": bool(previous.get("allow_scan", False)),
            "allow_index": bool(previous.get("allow_index", False)),
            "updated_at": str(previous.get("updated_at", "")).strip(),
        })
    return {"disks": rows}


def _build_apps_local(old_apps: Dict[str, Any]) -> Dict[str, Any]:
    existing_apps = old_apps.get("apps", []) or []
    if existing_apps:
        return {"apps": existing_apps}

    return {"apps": []}
    # 只保留“发现到路径”的候选，初始化第一页体验会更清晰


def _build_apps_candidates_local(old_apps: Dict[str, Any], defaults_app_map: Dict[str, Any]) -> Dict[str, Any]:
    existing_apps = old_apps.get("apps", []) or []
    existing_app_ids: List[str] = []
    for item in existing_apps:
        if not isinstance(item, dict):
            continue
        app_id = str(item.get("app_id", "")).strip()
        if app_id:
            existing_app_ids.append(app_id)

    discovered = discover_apps(defaults_app_map, existing_app_ids)
    filtered = [item for item in discovered if item.get("target_path")]
    return {
        "apps": filtered,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }


def _build_search_local(old_search: Dict[str, Any], defaults_search: Dict[str, Any]) -> Dict[str, Any]:
    if old_search:
        return old_search
    return {
        "enabled": bool(defaults_search.get("enabled", False)),
        "roots": [],
        "file_types": list(defaults_search.get("file_types", []) or []),
        "max_depth": int(defaults_search.get("max_depth", 5) or 5),
    }


def _build_engines_local(old_machine: Dict[str, Any], defaults_engine: Dict[str, Any]) -> Dict[str, Any]:
    old_ollama = old_machine.get("ollama", {}) if isinstance(old_machine.get("ollama"), dict) else {}
    old_gpt = old_machine.get("gpt_sovits", {}) if isinstance(old_machine.get("gpt_sovits"), dict) else {}
    old_llm = old_machine.get("llm", {}) if isinstance(old_machine.get("llm"), dict) else {}

    default_engines = defaults_engine.get("engines", {}) if isinstance(defaults_engine.get("engines"), dict) else {}

    ollama_tpl = default_engines.get("ollama", {}) if isinstance(default_engines.get("ollama"), dict) else {}
    gpt_tpl = default_engines.get("gpt_sovits", {}) if isinstance(default_engines.get("gpt_sovits"), dict) else {}

    return {
        "llm": {
            "preferred_provider": str(old_llm.get("preferred_provider", "ollama")).strip() or "ollama",
            "fallback_provider": str(old_llm.get("fallback_provider", "ollama")).strip() or "ollama",
        },
        "engines": {
            "ollama": {
                "enabled": bool(old_ollama.get("enabled", ollama_tpl.get("enabled", True))),
                "provider": "ollama",
                "host": str(old_ollama.get("host", ollama_tpl.get("default_host", "http://localhost:11434"))).strip() or "http://localhost:11434",
            },
            "gpt_sovits": {
                "enabled": bool(old_gpt.get("enabled", gpt_tpl.get("enabled", False))),
                "root_dir": str(old_gpt.get("root_dir", "")).strip(),
                "python_exe": str(old_gpt.get("python_exe", "")).strip(),
                "host": str(old_gpt.get("host", gpt_tpl.get("default_host", "127.0.0.1"))).strip() or "127.0.0.1",
                "port": int(old_gpt.get("port", gpt_tpl.get("default_port", 9880)) or 9880),
                "api_script": str(old_gpt.get("api_script", gpt_tpl.get("api_script", "api_v2.py"))).strip() or "api_v2.py",
                "tts_config": str(old_gpt.get("tts_config", gpt_tpl.get("tts_config", "GPT_SoVITS/configs/tts_infer.yaml"))).strip() or "GPT_SoVITS/configs/tts_infer.yaml",
                "recent_valid_root_dirs": list(old_gpt.get("recent_valid_root_dirs", []) or []),
            },
        },
    }


def _build_install_local(old_install: Dict[str, Any], defaults_init: Dict[str, Any]) -> Dict[str, Any]:
    initialized = bool(old_install["initialized"]) if "initialized" in old_install else False
    return {
        "initialized": initialized,
        "init_version": int(defaults_init.get("init_version", 1) or 1),
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }


def _build_engine_runtime(old_machine: Dict[str, Any]) -> Dict[str, Any]:
    startup = old_machine.get("startup", {}) if isinstance(old_machine.get("startup"), dict) else {}
    old_ollama = old_machine.get("ollama", {}) if isinstance(old_machine.get("ollama"), dict) else {}
    old_gpt = old_machine.get("gpt_sovits", {}) if isinstance(old_machine.get("gpt_sovits"), dict) else {}

    return {
        "startup": {
            "auto_detect_engines": bool(startup.get("auto_detect_engines", True)),
            "last_startup_check_at": str(startup.get("last_startup_check_at", "")).strip(),
            "last_startup_status": str(startup.get("last_startup_status", "unknown")).strip() or "unknown",
        },
        "ollama": {
            "last_health_ok": bool(old_ollama.get("last_health_ok", False)),
            "last_error": str(old_ollama.get("last_error", "")).strip(),
        },
        "gpt_sovits": {
            "last_health_ok": bool(old_gpt.get("last_health_ok", False)),
            "last_error": str(old_gpt.get("last_error", "")).strip(),
        },
    }


def make_local_files(project_root: str | Path | None = None, force: bool = False) -> Dict[str, str]:
    root = get_project_root(project_root)
    defaults = load_defaults(root)
    machine = collect_machine_paths(root)

    user_prefs = root / "data" / "user_prefs"
    runtime = root / "data" / "runtime"
    user_prefs.mkdir(parents=True, exist_ok=True)
    runtime.mkdir(parents=True, exist_ok=True)

    old_machine = _old_json(root, "machine_profile.json", {})
    old_roots = _old_json(root, "desktop_root_book.json", {})
    old_disks = _old_json(root, "disks.local.json", {})
    old_apps = _old_json(root, "desktop_app_book.json", {})
    old_mode = _old_json(root, "desktop_modes.json", {})
    old_search = _old_json(root, "search_paths.json", {})
    old_install = _old_json(root, "install_manifest.json", {})

    files = {
        "machine": user_prefs / "machine.local.json",
        "mode": user_prefs / "desktop_mode.local.json",
        "roots": user_prefs / "roots.local.json",
        "disks": user_prefs / "disks.local.json",
        "apps": user_prefs / "apps.local.json",
        "apps_candidates": user_prefs / "apps.candidates.local.json",
        "search": user_prefs / "search.local.json",
        "install": user_prefs / "install.local.json",
    }

    builders = {
        "machine": _build_machine_local(machine),
        "mode": _build_desktop_mode_local(old_mode, defaults["desktop_mode"]),
        "roots": _build_roots_local(old_roots, defaults["root_seed"], machine),
        "disks": _build_disks_local(old_disks),
        "apps": _build_apps_local(old_apps),
        "apps_candidates": _build_apps_candidates_local(old_apps, defaults["app_map"]),
        "search": _build_search_local(old_search, defaults["search_seed"]),
        "install": _build_install_local(old_install, defaults["init_seed"]),
    }

    for key, path in files.items():
        if force or not path.exists():
            _write_json(path, builders[key])

    return {key: str(path) for key, path in files.items()}
