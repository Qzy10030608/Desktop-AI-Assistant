from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Iterable, List

from services.desktop.tianting.providers.launch_target_provider import LaunchTargetProvider
from services.desktop.tianting.sources.base_source import SoftwareSourceBase


def _first_existing(paths: Iterable[Path]) -> str:
    for path in paths:
        try:
            if path.exists():
                return str(path.resolve(strict=False))
        except Exception:
            continue
    return ""


class SystemAppSeedSource(SoftwareSourceBase):
    source_id = "system_app_seed"

    def __init__(self) -> None:
        self.launch_target_provider = LaunchTargetProvider()
        windows_dir = Path(os.environ.get("WINDIR", r"C:\Windows"))
        program_files_x86 = Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"))
        program_files = Path(os.environ.get("ProgramFiles", r"C:\Program Files"))
        local_app_data = Path(os.environ.get("LOCALAPPDATA", ""))
        self.system32 = windows_dir / "System32"
        self.syswow64 = windows_dir / "SysWOW64"
        self.edge_candidates = [
            program_files_x86 / "Microsoft/Edge/Application/msedge.exe",
            program_files / "Microsoft/Edge/Application/msedge.exe",
            local_app_data / "Microsoft/Edge/Application/msedge.exe",
        ]

    def collect(
        self,
        *,
        existing_app_ids: Iterable[str] | None = None,
        app_map: Dict[str, Any] | None = None,
    ) -> List[Dict[str, Any]]:
        seeds = [
            self._local_app("windows_notepad", "记事本", "notepad", [self.system32 / "notepad.exe", self.syswow64 / "notepad.exe"]),
            self._appx_app(
                "windows_calculator",
                "计算器",
                "Microsoft.WindowsCalculator",
                r"shell:AppsFolder\Microsoft.WindowsCalculator_8wekyb3d8bbwe!App",
            ),
            self._local_app("windows_paint_legacy", "画图", "paint", [self.system32 / "mspaint.exe", self.syswow64 / "mspaint.exe"]),
            self._appx_app(
                "windows_paint",
                "画图",
                "Microsoft.Paint",
                r"shell:AppsFolder\Microsoft.Paint_8wekyb3d8bbwe!App",
            ),
            self._appx_app(
                "windows_snipping_tool",
                "截图工具",
                "Microsoft.ScreenSketch",
                r"shell:AppsFolder\Microsoft.ScreenSketch_8wekyb3d8bbwe!App",
            ),
            self._appx_app(
                "windows_sound_recorder",
                "录音机",
                "Microsoft.WindowsSoundRecorder",
                r"shell:AppsFolder\Microsoft.WindowsSoundRecorder_8wekyb3d8bbwe!App",
            ),
            self._local_app("microsoft_edge", "Microsoft Edge", "edge", self.edge_candidates),
            self._local_app(
                "windows_powershell",
                "Windows PowerShell",
                "powershell",
                [self.system32 / "WindowsPowerShell/v1.0/powershell.exe", self.syswow64 / "WindowsPowerShell/v1.0/powershell.exe"],
                sensitivity="admin_sensitive",
            ),
            self._local_app(
                "windows_explorer",
                "Windows Explorer",
                "explorer",
                [Path(os.environ.get("WINDIR", r"C:\Windows")) / "explorer.exe"],
                sensitivity="system_test_tool",
            ),
        ]
        return [item for item in seeds if item.get("target_path") or item.get("launch_target_raw")]

    def _base(self, app_id: str, title: str, platform_object_id: str, sensitivity: str = "") -> Dict[str, Any]:
        item = {
            "app_id": app_id,
            "canonical_app_id": app_id,
            "title": title,
            "discover_source": self.source_id,
            "connector_id": "windows_shell",
            "platform": "windows",
            "platform_object_type": "system_app",
            "platform_object_id": platform_object_id,
            "route_confidence": "high",
            "builtin": True,
        }
        if sensitivity:
            item["risk_hint"] = sensitivity
            item["sensitivity"] = sensitivity
        return item

    def _local_app(
        self,
        app_id: str,
        title: str,
        platform_object_id: str,
        candidates: Iterable[Path],
        *,
        sensitivity: str = "",
    ) -> Dict[str, Any]:
        target = _first_existing(candidates)
        item = self._base(app_id, title, platform_object_id, sensitivity=sensitivity)
        item.update(self.launch_target_provider.classify_target(target))
        item["platform"] = "windows"
        item["platform_object_type"] = "system_app"
        item["platform_object_id"] = platform_object_id
        item["icon_source_path"] = target
        item["icon_kind"] = "system"
        return item

    def _appx_app(self, app_id: str, title: str, platform_object_id: str, shell_target: str) -> Dict[str, Any]:
        item = self._base(app_id, title, platform_object_id)
        item.update(
            {
                "target_path": "",
                "entry_path": shell_target,
                "install_dir": "",
                "launch_target_kind": "appx",
                "launch_target_raw": shell_target,
                "icon_source_path": "",
                "icon_kind": "system",
                "path_status": "appx_entry",
            }
        )
        return item
