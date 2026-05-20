from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, Iterable, List

from services.desktop.tianting.providers.launch_target_provider import LaunchTargetProvider
from services.desktop.tianting.sources.base_source import SoftwareSourceBase

try:
    import winreg  # type: ignore
except Exception:  # pragma: no cover - non-Windows fallback
    winreg = None  # type: ignore


def _slugify(value: str) -> str:
    text = str(value or "").strip().lower()
    if not text:
        return ""
    return re.sub(r"[^a-z0-9]+", "_", text).strip("_")


class UninstallRegistrySource(SoftwareSourceBase):
    source_id = "uninstall_registry"

    def __init__(self) -> None:
        self.launch_target_provider = LaunchTargetProvider()

    def collect(self, *, existing_app_ids: Iterable[str] | None = None, app_map: Dict[str, Any] | None = None) -> List[Dict[str, Any]]:
        if winreg is None:
            return []
        roots = [
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
            (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
        ]
        results: List[Dict[str, Any]] = []
        for hive, subkey in roots:
            try:
                with winreg.OpenKey(hive, subkey) as root_key:
                    count = int(winreg.QueryInfoKey(root_key)[0] or 0)
                    for index in range(count):
                        try:
                            child_name = winreg.EnumKey(root_key, index)
                            with winreg.OpenKey(root_key, child_name) as child_key:
                                item = self._candidate_from_registry(child_key, registry_key=f"{subkey}\\{child_name}")
                                if item is not None:
                                    results.append(item)
                        except Exception:
                            continue
            except Exception:
                continue
        return results

    def _candidate_from_registry(self, key: Any, *, registry_key: str = "") -> Dict[str, Any] | None:
        display_name = self._query_value(key, "DisplayName")
        if not display_name:
            return None
        display_icon = self._query_value(key, "DisplayIcon")
        install_location = self._query_value(key, "InstallLocation")
        uninstall_string = self._query_value(key, "UninstallString")
        publisher = self._query_value(key, "Publisher")
        version = self._query_value(key, "DisplayVersion")

        icon_path = self._extract_executable_path(display_icon)
        target = icon_path if self._is_safe_launch_candidate(icon_path) else ""
        launch_source = "display_icon" if target else ""
        unsafe_entry = bool(icon_path and not target)

        if not target and install_location:
            target = self._find_executable_in_directory(Path(install_location))
            launch_source = "install_location_exe" if target else ""
        if not target and uninstall_string:
            unsafe_entry = unsafe_entry or bool(self._extract_executable_path(uninstall_string))

        target_info = self.launch_target_provider.classify_target(target)
        item = {
            "app_id": _slugify(display_name) or _slugify(publisher),
            "title": display_name,
            "discover_source": self.source_id,
            "identity_source": self.source_id,
            "launch_source": launch_source,
            "publisher": publisher,
            "version": version,
            "uninstall_string": uninstall_string,
            "registry_key": registry_key,
            "source_detail": "Windows uninstall registry",
            "registry_entry_status": "unsafe_registry_entry" if unsafe_entry and not target else "identity_only" if not target else "launch_candidate",
            **target_info,
        }
        if icon_path:
            item["icon_source_path"] = icon_path
        return item

    def _query_value(self, key: Any, value_name: str) -> str:
        try:
            value, _value_type = winreg.QueryValueEx(key, value_name)
            return str(value or "").strip()
        except Exception:
            return ""

    def _extract_executable_path(self, raw_value: str) -> str:
        text = str(raw_value or "").strip()
        if not text:
            return ""
        quoted = re.findall(r'"([^"]+\.exe)"', text, flags=re.IGNORECASE)
        if quoted:
            return self.launch_target_provider.normalize_path(quoted[0])
        bare = re.findall(r"([A-Za-z]:[^,\n\r]+?\.exe)", text, flags=re.IGNORECASE)
        if bare:
            return self.launch_target_provider.normalize_path(bare[0])
        return ""

    def _find_executable_in_directory(self, directory: Path) -> str:
        if not directory.exists() or not directory.is_dir():
            return ""
        try:
            for candidate in directory.iterdir():
                if candidate.is_file() and candidate.suffix.lower() == ".exe" and self._is_safe_launch_candidate(str(candidate)):
                    return str(candidate.resolve(strict=False))
        except Exception:
            return ""
        return ""

    def _is_safe_launch_candidate(self, path: str) -> bool:
        text = str(path or "").strip().lower()
        if not text:
            return False
        filename = Path(text).name
        blocked_fragments = {
            "uninstall",
            "unins",
            "setup",
            "update",
            "helper",
            "service",
            "driver",
            "crash",
            "telemetry",
            "dpinst",
            "rundll32",
            "msiexec",
        }
        return not any(fragment in filename or fragment in text for fragment in blocked_fragments)
