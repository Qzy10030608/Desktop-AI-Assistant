from services.desktop.tianting.sources.app_map_source import AppMapSource
from services.desktop.tianting.sources.appx_installed_apps_source import AppxInstalledAppsSource
from services.desktop.tianting.sources.base_source import SoftwareSourceBase
from services.desktop.tianting.sources.platform_source_registry import PlatformSourceRegistry
from services.desktop.tianting.sources.shortcut_source import ShortcutSource
from services.desktop.tianting.sources.system_app_seed_source import SystemAppSeedSource
from services.desktop.tianting.sources.uninstall_registry_source import UninstallRegistrySource

__all__ = [
    "AppMapSource",
    "AppxInstalledAppsSource",
    "PlatformSourceRegistry",
    "ShortcutSource",
    "SoftwareSourceBase",
    "SystemAppSeedSource",
    "UninstallRegistrySource",
]
