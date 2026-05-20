from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any, Dict, Iterable, List

from services.desktop.tianting.providers.launch_target_provider import LaunchTargetProvider
from services.desktop.tianting.sources.base_source import SoftwareSourceBase


def _slugify(value: str) -> str:
    text = str(value or "").strip().lower()
    if not text:
        return ""
    return re.sub(r"[^a-z0-9]+", "_", text).strip("_")


class ShortcutSource(SoftwareSourceBase):
    def __init__(self, *, source_id: str, directories: Iterable[Path]) -> None:
        self.source_id = source_id
        self.directories = list(directories)
        self.launch_target_provider = LaunchTargetProvider()

    def collect(
        self,
        *,
        existing_app_ids: Iterable[str] | None = None,
        app_map: Dict[str, Any] | None = None,
    ) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        lnk_paths: List[Path] = []
        url_paths: List[Path] = []

        for base_dir in self.directories:
            if not str(base_dir).strip() or not base_dir.exists():
                continue

            for path in base_dir.rglob("*"):
                suffix = path.suffix.lower()
                if suffix == ".lnk":
                    lnk_paths.append(path)
                elif suffix == ".url":
                    url_paths.append(path)

        lnk_details = self._resolve_lnk_batch(lnk_paths)
        for path in lnk_paths:
            detail = lnk_details.get(str(path), {})
            raw_target = str(detail.get("target_path", "")).strip()
            target_info = self.launch_target_provider.classify_target(raw_target)
            item = self._shortcut_item(path, target_info)
            item["shortcut_kind"] = "lnk"
            item["shortcut_parse_status"] = str(detail.get("status", "failed") or "failed")
            arguments = str(detail.get("arguments", "")).strip()
            if arguments:
                item["launch_args"] = [arguments]
            working_directory = str(detail.get("working_directory", "")).strip()
            if working_directory and not item.get("install_dir"):
                item["install_dir"] = working_directory
            description = str(detail.get("description", "")).strip()
            if description:
                item["source_detail"] = description
            icon_source_path = self._clean_icon_location(str(detail.get("icon_location", "")).strip())
            if icon_source_path:
                item["icon_source_path"] = icon_source_path
                item["icon_kind"] = "shortcut_icon"
            results.append(item)

        for path in url_paths:
            raw_target = self._resolve_url_target(path)
            target_info = self.launch_target_provider.classify_target(raw_target)
            item = self._shortcut_item(path, target_info)
            item["shortcut_kind"] = "url"
            item["shortcut_parse_status"] = "resolved" if raw_target else "failed"
            icon_source_path = self._resolve_url_icon_location(path)
            if icon_source_path:
                item["icon_source_path"] = icon_source_path
                item["icon_kind"] = "shortcut_icon"
            results.append(item)

        return results

    def _shortcut_item(self, path: Path, target_info: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "app_id": _slugify(path.stem),
            "title": path.stem.strip(),
            "discover_source": self.source_id,
            **target_info,
        }

    def _lnk_timeout_seconds(self) -> float:
        return 20.0 if self.source_id == "start_menu_shortcut" else 10.0

    def _resolve_lnk_batch(self, shortcut_paths: List[Path]) -> Dict[str, Dict[str, Any]]:
        if not shortcut_paths:
            return {}

        path_texts = [str(path) for path in shortcut_paths]
        script = r"""
$ErrorActionPreference = 'Continue'
$raw = [Console]::In.ReadToEnd()
$paths = @()
if ($raw.Trim()) {
    $payload = ConvertFrom-Json -InputObject $raw
    $paths = @($payload.paths)
}
$shell = New-Object -ComObject WScript.Shell
$results = foreach ($path in $paths) {
    try {
        $shortcut = $shell.CreateShortcut([string]$path)
        [PSCustomObject]@{
            Path = [string]$path
            TargetPath = [string]$shortcut.TargetPath
            Arguments = [string]$shortcut.Arguments
            WorkingDirectory = [string]$shortcut.WorkingDirectory
            IconLocation = [string]$shortcut.IconLocation
            Description = [string]$shortcut.Description
            Ok = $true
            Error = ''
        }
    } catch {
        [PSCustomObject]@{
            Path = [string]$path
            TargetPath = ''
            Arguments = ''
            WorkingDirectory = ''
            IconLocation = ''
            Description = ''
            Ok = $false
            Error = [string]$_.Exception.Message
        }
    }
}
$results | ConvertTo-Json -Depth 4 -Compress
"""
        try:
            completed = subprocess.run(
                [
                    "powershell",
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-Command",
                    script,
                ],
                input=json.dumps({"paths": path_texts}, ensure_ascii=False),
                capture_output=True,
                text=True,
                timeout=self._lnk_timeout_seconds(),
                check=False,
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
            )
        except subprocess.TimeoutExpired:
            return {
                path: {
                    "target_path": "",
                    "arguments": "",
                    "working_directory": "",
                    "icon_location": "",
                    "description": "",
                    "status": "timeout",
                }
                for path in path_texts
            }
        except Exception:
            return {
                path: {
                    "target_path": "",
                    "arguments": "",
                    "working_directory": "",
                    "icon_location": "",
                    "description": "",
                    "status": "failed",
                }
                for path in path_texts
            }

        if completed.returncode != 0:
            return {
                path: {
                    "target_path": "",
                    "arguments": "",
                    "working_directory": "",
                    "icon_location": "",
                    "description": "",
                    "status": "failed",
                }
                for path in path_texts
            }

        try:
            parsed = json.loads(str(completed.stdout or "").strip() or "[]")
        except Exception:
            parsed = []
        if isinstance(parsed, dict):
            rows = [parsed]
        elif isinstance(parsed, list):
            rows = [row for row in parsed if isinstance(row, dict)]
        else:
            rows = []

        details: Dict[str, Dict[str, Any]] = {}
        for row in rows:
            path = str(row.get("Path", "")).strip()
            if not path:
                continue
            target_path = str(row.get("TargetPath", "")).strip()
            ok = bool(row.get("Ok", False))
            details[path] = {
                "target_path": target_path,
                "arguments": str(row.get("Arguments", "")).strip(),
                "working_directory": str(row.get("WorkingDirectory", "")).strip(),
                "icon_location": str(row.get("IconLocation", "")).strip(),
                "description": str(row.get("Description", "")).strip(),
                "status": "resolved" if ok and target_path else "failed",
            }

        for path in path_texts:
            details.setdefault(
                path,
                {
                    "target_path": "",
                    "arguments": "",
                    "working_directory": "",
                    "icon_location": "",
                    "description": "",
                    "status": "failed",
                },
            )
        return details

    def _resolve_lnk_icon_location(self, shortcut_path: Path) -> str:
        if shortcut_path.suffix.lower() != ".lnk":
            return ""

        ps_path = str(shortcut_path).replace("'", "''")
        command = (
            "$shell = New-Object -ComObject WScript.Shell; "
            f"$shortcut = $shell.CreateShortcut('{ps_path}'); "
            "$shortcut.IconLocation"
        )

        try:
            completed = subprocess.run(
                [
                    "powershell",
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-Command",
                    command,
                ],
                capture_output=True,
                text=True,
                timeout=3,
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
            )
        except Exception:
            return ""

        raw = str(completed.stdout or "").strip()
        return self._clean_icon_location(raw)

    def _resolve_url_target(self, shortcut_path: Path) -> str:
        try:
            text = shortcut_path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            try:
                text = shortcut_path.read_text(encoding="mbcs", errors="ignore")
            except Exception:
                return ""

        for line in text.splitlines():
            normalized = line.strip()
            if normalized.lower().startswith("url="):
                return normalized.split("=", 1)[1].strip()
        return ""

    def _resolve_url_icon_location(self, shortcut_path: Path) -> str:
        try:
            text = shortcut_path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            try:
                text = shortcut_path.read_text(encoding="mbcs", errors="ignore")
            except Exception:
                return ""

        icon_file = ""
        for line in text.splitlines():
            normalized = line.strip()
            if normalized.lower().startswith("iconfile="):
                icon_file = normalized.split("=", 1)[1].strip()
                break

        return self._clean_icon_location(icon_file)

    def _clean_icon_location(self, value: str) -> str:
        text = str(value or "").strip().strip('"')
        if not text:
            return ""

        # 常见格式：C:\xxx\icon.ico,0
        if "," in text:
            possible_path = text.rsplit(",", 1)[0].strip().strip('"')
        else:
            possible_path = text

        if not possible_path:
            return ""

        lower = possible_path.lower()
        if lower.startswith(("steam://", "http://", "https://")):
            return ""

        path = Path(possible_path)
        if path.exists():
            return str(path)

        return ""
