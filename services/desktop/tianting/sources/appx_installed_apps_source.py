from __future__ import annotations

import json
import subprocess
from typing import Any, Dict, Iterable, List

from services.desktop.tianting.sources.base_source import SoftwareSourceBase


APPX_DISPLAY_NAMES = {
    "Microsoft.WindowsCalculator": ("windows_calculator_appx", "windows_calculator", "计算器"),
    "Microsoft.Paint": ("windows_paint_appx", "windows_paint", "画图"),
    "Microsoft.WindowsNotepad": ("windows_notepad_appx", "windows_notepad", "记事本"),
    "Microsoft.ScreenSketch": ("windows_snipping_tool_appx", "windows_snipping_tool", "截图工具"),
    "Microsoft.WindowsSoundRecorder": ("windows_sound_recorder_appx", "windows_sound_recorder", "录音机"),
}


class AppxInstalledAppsSource(SoftwareSourceBase):
    source_id = "appx_installed_apps"

    def collect(
        self,
        *,
        existing_app_ids: Iterable[str] | None = None,
        app_map: Dict[str, Any] | None = None,
    ) -> List[Dict[str, Any]]:
        packages = self._read_appx_packages()
        results: List[Dict[str, Any]] = []
        for package in packages:
            name = str(package.get("Name", "")).strip()
            if name not in APPX_DISPLAY_NAMES:
                continue
            app_id, canonical_app_id, title = APPX_DISPLAY_NAMES[name]
            package_family = str(package.get("PackageFamilyName", "")).strip()
            install_location = str(package.get("InstallLocation", "")).strip()
            shell_target = f"shell:AppsFolder\\{package_family}!App" if package_family else ""
            results.append(
                {
                    "app_id": app_id,
                    "canonical_app_id": canonical_app_id,
                    "title": title,
                    "target_path": "",
                    "entry_path": shell_target,
                    "install_dir": install_location,
                    "launch_target_kind": "appx",
                    "launch_target_raw": shell_target,
                    "discover_source": self.source_id,
                    "connector_id": "windows_shell",
                    "platform": "windows",
                    "platform_object_type": "appx",
                    "platform_object_id": name,
                    "icon_source_path": "",
                    "icon_kind": "system",
                    "route_confidence": "medium",
                    "path_status": "appx_entry",
                    "builtin": True,
                }
            )
        return results

    def _read_appx_packages(self) -> List[Dict[str, Any]]:
        names = ",".join(f"'{name}'" for name in APPX_DISPLAY_NAMES)
        command = (
            f"$names = @({names}); "
            "Get-AppxPackage | Where-Object { $names -contains $_.Name } | "
            "Select-Object Name,PackageFamilyName,PackageFullName,InstallLocation | "
            "ConvertTo-Json -Depth 3"
        )
        try:
            completed = subprocess.run(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
            )
        except Exception:
            return []
        if completed.returncode != 0 or not str(completed.stdout or "").strip():
            return []
        try:
            data = json.loads(completed.stdout)
        except Exception:
            return []
        if isinstance(data, dict):
            return [data]
        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict)]
        return []
