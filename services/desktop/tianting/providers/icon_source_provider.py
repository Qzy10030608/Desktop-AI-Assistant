from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict


class IconSourceProvider:
    PLATFORM_BADGES = {
        "steam": "steam_platform",
        "epic": "epic_platform",
        "battlenet": "battlenet_platform",
        "ea": "ea_platform",
    }

    def _clean_local_path(self, value: str) -> str:
        text = str(value or "").strip()
        if not text:
            return ""

        lower = text.lower()
        if lower.startswith(
            (
                "steam://",
                "epic://",
                "battlenet://",
                "origin://",
                "ea://",
                "http://",
                "https://",
                "shell:",
                "ms-settings:",
                "microsoft-edge:",
                "calculator:",
                "appx:",
            )
        ):
            return ""

        return text

    def _steam_app_id_from_item(self, item: Dict[str, Any]) -> str:
        platform_object_id = str(item.get("platform_object_id", "") or "").strip()
        if platform_object_id.isdigit():
            return platform_object_id

        raw = str(item.get("launch_target_raw", "") or "").strip()
        match = re.search(r"steam://rungameid/(\d+)", raw, re.IGNORECASE)
        if match:
            return match.group(1)

        return ""

    def _steam_root_candidates(self) -> list[Path]:
        result: list[Path] = []

        # 常见安装位置
        for raw in (
            r"C:\Program Files (x86)\Steam",
            r"C:\Program Files\Steam",
            r"D:\Steam",
            r"E:\Steam",
            r"F:\Steam",
            r"D:\steam",
            r"E:\steam",
            r"F:\steam",
        ):
            path = Path(raw)
            if path.exists():
                result.append(path)

        # 从注册表读取 SteamPath / InstallPath
        try:
            import winreg  # type: ignore

            registry_keys = [
                (winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam", "SteamPath"),
                (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam", "InstallPath"),
                (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Valve\Steam", "InstallPath"),
            ]

            for hive, subkey, value_name in registry_keys:
                try:
                    with winreg.OpenKey(hive, subkey) as key:
                        value, _value_type = winreg.QueryValueEx(key, value_name)
                    path = Path(str(value))
                    if path.exists():
                        result.append(path)
                except Exception:
                    continue
        except Exception:
            pass

        unique: list[Path] = []
        seen: set[str] = set()
        for path in result:
            normalized = str(path).lower()
            if normalized in seen:
                continue
            seen.add(normalized)
            unique.append(path)
        return unique

    def _steam_cached_icon_path(self, app_id: str) -> str:
        if not app_id:
            return ""

        for steam_root in self._steam_root_candidates():
            search_dirs = [
                steam_root / "steam" / "games",
                steam_root / "appcache" / "librarycache",
            ]

            exact_candidates = []
            for base_dir in search_dirs:
                exact_candidates.extend(
                    [
                        base_dir / f"{app_id}_icon.ico",
                        base_dir / f"{app_id}.ico",                      
                    ]
                )

            for candidate in exact_candidates:
                if candidate.exists():
                    return str(candidate)

            for base_dir in search_dirs:
                if not base_dir.exists():
                    continue
                try:
                    for pattern in (
                        f"{app_id}*icon*.ico",
                        f"{app_id}*.ico",
                        
                    ):
                        for candidate in base_dir.glob(pattern):
                            if candidate.exists():
                                return str(candidate)
                except Exception:
                    continue

        return ""

    def describe(self, item: Dict[str, Any]) -> Dict[str, str]:
        existing_icon = self._clean_local_path(item.get("icon_source_path", ""))
        target_path = self._clean_local_path(item.get("target_path", ""))
        entry_path = self._clean_local_path(item.get("entry_path", ""))
        launch_target_kind = str(item.get("launch_target_kind", "missing")).strip().lower()
        category = str(item.get("category", "unknown")).strip().lower()
        platform = str(item.get("platform", "unknown")).strip().lower() or "unknown"

        # 已经有图标来源时优先使用
        if existing_icon:
            return {"icon_source_path": existing_icon, "icon_kind": "local_object"}

        # 本地对象优先：exe / lnk / 普通文件 / 目录都允许交给 QFileIconProvider
        if target_path:
            return {"icon_source_path": target_path, "icon_kind": "local_object"}

        if entry_path:
            return {"icon_source_path": entry_path, "icon_kind": "launcher"}

        # Steam 平台对象：尝试找 Steam 本地图标缓存
        if platform == "steam":
            app_id = self._steam_app_id_from_item(item)
            cached_icon = self._steam_cached_icon_path(app_id)
            if cached_icon:
                return {"icon_source_path": cached_icon, "icon_kind": "steam_cached_icon"}
            return {"icon_source_path": "", "icon_kind": "steam_platform"}

        # 平台/协议入口：先给平台占位图标
        if launch_target_kind == "protocol":
            badge_kind = self.PLATFORM_BADGES.get(platform)
            if badge_kind:
                return {"icon_source_path": "", "icon_kind": badge_kind}
            return {"icon_source_path": "", "icon_kind": "protocol"}

        if launch_target_kind in {"appx", "shell_app"}:
            return {"icon_source_path": "", "icon_kind": "appx"}

        if category == "system_core":
            return {"icon_source_path": "", "icon_kind": "system"}

        return {"icon_source_path": "", "icon_kind": "missing"}
