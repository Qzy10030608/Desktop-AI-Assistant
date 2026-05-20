from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List


def _safe_paths() -> List[Path]:
    paths: List[Path] = []

    candidates = [
        os.environ.get("ProgramFiles", ""),
        os.environ.get("ProgramFiles(x86)", ""),
        os.environ.get("LOCALAPPDATA", ""),
        os.environ.get("APPDATA", ""),
    ]
    for item in candidates:
        if item:
            path = Path(item)
            if path.exists():
                paths.append(path)

    return paths


def _find_first_exe(exe_names: List[str]) -> str:
    for root in _safe_paths():
        for exe_name in exe_names:
            try:
                matches = list(root.rglob(exe_name))
            except Exception:
                matches = []
            if matches:
                return str(matches[0].resolve())
    return ""


def discover_apps(app_map: Dict[str, Any], existing_app_ids: List[str] | None = None) -> List[Dict[str, Any]]:
    existing_app_ids = existing_app_ids or []
    result: List[Dict[str, Any]] = []

    for item in app_map.get("apps", []):
        if not isinstance(item, dict):
            continue

        app_id = str(item.get("app_id", "")).strip()
        if not app_id or app_id in existing_app_ids:
            continue

        title = str(item.get("title", app_id)).strip() or app_id
        connector_id = str(item.get("connector_id", "windows_shell")).strip() or "windows_shell"
        discover = item.get("discover", {}) or {}
        defaults = item.get("defaults", {}) or {}

        exe_names = discover.get("exe_names", []) or []
        exe_names = [str(x).strip() for x in exe_names if str(x).strip()]

        found_path = _find_first_exe(exe_names)

        result.append({
            "app_id": app_id,
            "title": title,
            "target_path": found_path,
            "launch_args": [],
            "enabled": bool(defaults.get("enabled", False)),
            "allow_launch": bool(defaults.get("allow_launch", True)),
            "allow_attach": bool(defaults.get("allow_attach", False)),
            "allow_close": bool(defaults.get("allow_close", False)),
            "connector_id": connector_id,
            "discovered": bool(found_path),
            "discover_source": "filesystem_scan" if found_path else "not_found",
        })

    return result