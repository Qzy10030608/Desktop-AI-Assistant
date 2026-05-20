from __future__ import annotations

import os
from pathlib import Path
from typing import List

from services.desktop.tianting.sources.app_map_source import AppMapSource
from services.desktop.tianting.sources.appx_installed_apps_source import AppxInstalledAppsSource
from services.desktop.tianting.sources.base_source import SoftwareSourceBase
from services.desktop.tianting.sources.shortcut_source import ShortcutSource
from services.desktop.tianting.sources.system_app_seed_source import SystemAppSeedSource
from services.desktop.tianting.sources.uninstall_registry_source import UninstallRegistrySource


class PlatformSourceRegistry:
    def build_sources(self, *, scan_profile: str = "quick") -> List[SoftwareSourceBase]:
        profile = str(scan_profile or "quick").strip().lower()
        if profile not in {"quick", "full"}:
            profile = "quick"

        start_menu_dirs = [
            Path(os.environ.get("ProgramData", "")) / "Microsoft/Windows/Start Menu/Programs",
            Path(os.environ.get("APPDATA", "")) / "Microsoft/Windows/Start Menu/Programs",
        ]
        desktop_dirs = [
            Path(os.environ.get("PUBLIC", "")) / "Desktop",
            Path(os.environ.get("USERPROFILE", "")) / "Desktop",
        ]

        quick_sources: List[SoftwareSourceBase] = [
            AppMapSource(),
            SystemAppSeedSource(),
            ShortcutSource(source_id="start_menu_shortcut", directories=start_menu_dirs),
            ShortcutSource(source_id="desktop_shortcut", directories=desktop_dirs),
            AppxInstalledAppsSource(),
        ]

        if profile == "full":
            return [
                *quick_sources,
                UninstallRegistrySource(),
            ]

        return quick_sources
