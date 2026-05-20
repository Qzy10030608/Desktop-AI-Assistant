from __future__ import annotations

import re
from pathlib import Path
from typing import Any


SYSTEM_NOISE_TITLES = {
    "system information",
    "task manager",
    "voiceaccess",
    "voice access",
    "windows media player",
    "windows powershell",
    "memory diagnostic",
    "windows memory diagnostic",
    "narrator",
    "odbc data source",
    "odbc data sources",
    "on screen keyboard",
    "control panel",
    "event viewer",
    "services",
    "registry editor",
    "command prompt",
}

SYSTEM_NOISE_BASENAMES = {
    "msinfo32.exe",
    "taskmgr.exe",
    "voiceaccess.exe",
    "wmplayer.exe",
    "powershell.exe",
    "mdsched.exe",
    "narrator.exe",
    "odbcad32.exe",
    "osk.exe",
    "control.exe",
    "eventvwr.exe",
    "services.msc",
    "regedit.exe",
    "cmd.exe",
}

UNINSTALL_PREFIXES = (
    "卸载",
    "移除",
    "uninstall",
    "uninstaller",
    "remove",
)

UNINSTALL_TITLE_WORDS = (
    "卸载",
    "uninstall",
    "uninstaller",
)


def normalize_vm_apps(raw_apps: list[dict]) -> dict[str, Any]:
    raw_records = [dict(item) for item in raw_apps if isinstance(item, dict)]
    hidden: list[dict[str, Any]] = []
    visible: list[dict[str, Any]] = []

    for app in raw_records:
        if is_system_noise_record(app):
            hidden.append(_hidden_record(app, reason="system_noise"))
        else:
            visible.append(app)

    groups: dict[str, list[dict[str, Any]]] = {}
    for app in visible:
        groups.setdefault(app_group_key(app), []).append(app)

    normalized_apps: list[dict[str, Any]] = []
    merged_uninstallers = 0
    seen_output_keys: set[str] = set()
    orphan_uninstallers: list[dict[str, Any]] = []

    for _key, records in groups.items():
        main = _pick_main_record(records)
        uninstallers = [item for item in records if is_uninstaller_record(item)]
        if main is None:
            orphan_uninstallers.extend(uninstallers or records)
            continue

        merged = dict(main)
        for uninstaller in uninstallers:
            if uninstaller is main:
                continue
            merge_uninstaller_into_main(merged, uninstaller)
            hidden.append(_hidden_record(uninstaller, reason="merged_uninstaller"))
            merged_uninstallers += 1

        output_key = _dedupe_key(merged)
        if output_key in seen_output_keys:
            hidden.append(_hidden_record(merged, reason="duplicate_after_merge"))
            continue
        seen_output_keys.add(output_key)
        normalized_apps.append(_finalize_app(merged))

    main_by_title = {
        normalize_title_for_group(str(item.get("title", item.get("name", "")) or "")): item
        for item in normalized_apps
    }
    for uninstaller in orphan_uninstallers:
        title_key = normalize_title_for_group(str(uninstaller.get("title", uninstaller.get("name", "")) or ""))
        main = main_by_title.get(title_key)
        if main is not None:
            merge_uninstaller_into_main(main, uninstaller)
            hidden.append(_hidden_record(uninstaller, reason="merged_uninstaller"))
            merged_uninstallers += 1
        else:
            hidden.append(_hidden_record(uninstaller, reason="uninstaller_without_main"))

    stats = {
        "raw": len(raw_records),
        "filtered_system": len([item for item in hidden if item.get("hidden_reason") == "system_noise"]),
        "merged_uninstallers": merged_uninstallers,
        "deduped": len(seen_output_keys),
        "final": len(normalized_apps),
        "hidden": len(hidden),
    }
    return {
        "apps": normalized_apps,
        "stats": stats,
        "hidden": hidden,
        "raw": raw_records,
    }


def is_uninstaller_record(app: dict) -> bool:
    title = str(app.get("title", app.get("name", "")) or "").strip()
    normalized = normalize_title_for_group(title)
    raw_title = title.strip().lower()
    if any(raw_title.startswith(prefix) for prefix in UNINSTALL_PREFIXES):
        return True
    if any(word in normalized for word in UNINSTALL_TITLE_WORDS):
        return True
    path = str(app.get("path", app.get("target_path", "")) or "").strip().lower()
    basename = Path(path).name.lower() if path else ""
    return basename in {"uninstall.exe", "uninst.exe", "uninstaller.exe"} or basename.startswith("unins")


def normalize_title_for_group(title: str) -> str:
    text = str(title or "").strip().lower()
    for prefix in UNINSTALL_PREFIXES:
        if text.startswith(prefix):
            text = text[len(prefix):].strip()
    text = re.sub(r"(?i)\buninstall(er)?\b", " ", text)
    text = re.sub(r"[\s\-_()（）【】\[\]{}:：]+", " ", text)
    return text.strip()


def app_group_key(app: dict) -> str:
    install_dir = _norm_path(str(app.get("install_dir", "") or ""))
    if install_dir and not _looks_like_start_menu_dir(install_dir):
        return f"dir:{install_dir}"

    path = _norm_path(str(app.get("path", app.get("target_path", "")) or ""))
    if path:
        parent = _norm_path(str(Path(path).parent))
        if parent and not _looks_like_start_menu_dir(parent):
            return f"dir:{parent}"

    title = normalize_title_for_group(str(app.get("title", app.get("name", "")) or ""))
    return f"title:{title or str(app.get('app_id', 'unknown'))}"


def is_system_noise_record(app: dict) -> bool:
    source = str(app.get("source", "") or "").strip().lower()
    app_id = str(app.get("app_id", "") or "").strip().lower()
    if source.startswith("fallback") or app_id in {"vm_notepad", "vm_calculator", "vm_paint", "vm_edge", "vm_chrome"}:
        return False

    title = normalize_title_for_group(str(app.get("title", app.get("name", "")) or ""))
    if title in SYSTEM_NOISE_TITLES or any(title.startswith(f"{item} ") for item in SYSTEM_NOISE_TITLES):
        return True

    path_values = [
        str(app.get("path", "") or ""),
        str(app.get("target_path", "") or ""),
        str(app.get("launch_target_raw", "") or ""),
        str(app.get("entry_path", "") or ""),
    ]
    for raw in path_values:
        basename = Path(raw).name.lower() if raw else ""
        if basename in SYSTEM_NOISE_BASENAMES:
            return True
    return False


def merge_uninstaller_into_main(main: dict, uninstaller: dict) -> dict:
    uninstall_string = str(main.get("uninstall_string", "") or "").strip()
    quiet_uninstall_string = str(main.get("quiet_uninstall_string", "") or "").strip()
    if not uninstall_string:
        uninstall_string = _uninstall_command_from_record(uninstaller)
    if not quiet_uninstall_string:
        quiet_uninstall_string = str(uninstaller.get("quiet_uninstall_string", "") or "").strip()
    main["uninstall_string"] = uninstall_string
    main["quiet_uninstall_string"] = quiet_uninstall_string
    if uninstall_string or quiet_uninstall_string:
        main["can_uninstall"] = True
    main.setdefault("merged_uninstaller_app_ids", [])
    if isinstance(main["merged_uninstaller_app_ids"], list):
        app_id = str(uninstaller.get("app_id", "") or "")
        if app_id:
            main["merged_uninstaller_app_ids"].append(app_id)
    return main


def _pick_main_record(records: list[dict[str, Any]]) -> dict[str, Any] | None:
    mains = [item for item in records if not is_uninstaller_record(item)]
    if not mains:
        return None
    return sorted(
        mains,
        key=lambda item: (
            0 if str(item.get("source", "") or "").lower().startswith("registry") else 1,
            0 if item.get("path") or item.get("target_path") else 1,
            str(item.get("title", item.get("name", "")) or "").lower(),
        ),
    )[0]


def _finalize_app(app: dict[str, Any]) -> dict[str, Any]:
    result = dict(app)
    result["permission_state"] = "test"
    result["status_text"] = str(result.get("status_text", "") or "VM测试")
    result["platform"] = "vm"
    result["platform_object_type"] = str(result.get("platform_object_type", "") or "vm_app")
    result["platform_object_id"] = str(result.get("platform_object_id", "") or result.get("app_id", ""))
    result["can_uninstall"] = bool(result.get("can_uninstall", False) or result.get("uninstall_string") or result.get("quiet_uninstall_string"))
    result["can_move"] = bool(result.get("can_move", False))
    result["can_update"] = bool(result.get("can_update", False))
    return result


def _hidden_record(app: dict, *, reason: str) -> dict[str, Any]:
    item = dict(app)
    item["hidden_reason"] = reason
    return item


def _uninstall_command_from_record(app: dict) -> str:
    for key in ("uninstall_string", "quiet_uninstall_string", "path", "target_path", "launch_target_raw", "entry_path"):
        value = str(app.get(key, "") or "").strip()
        if value:
            return value
    return ""


def _dedupe_key(app: dict) -> str:
    path = _norm_path(str(app.get("path", app.get("target_path", "")) or ""))
    if path:
        return f"path:{path}"
    install_dir = _norm_path(str(app.get("install_dir", "") or ""))
    title = normalize_title_for_group(str(app.get("title", app.get("name", "")) or ""))
    return f"{install_dir}|{title}"


def _norm_path(path: str) -> str:
    if not path:
        return ""
    try:
        return str(Path(path).expanduser().resolve(strict=False)).lower()
    except Exception:
        return str(path).strip().lower()


def _looks_like_start_menu_dir(path: str) -> bool:
    normalized = str(path or "").replace("/", "\\").lower()
    return "\\start menu\\" in normalized or normalized.endswith("\\desktop")
