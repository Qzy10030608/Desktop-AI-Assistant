from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any, Dict

from services.desktop.tianting.providers.install_dir_provider import InstallDirProvider
from services.desktop.tianting.providers.protocol_parser import ProtocolParser


class LaunchTargetProvider:
    def __init__(self) -> None:
        self.protocol_parser = ProtocolParser()
        self.install_dir_provider = InstallDirProvider()

    def normalize_path(self, value: str) -> str:
        text = str(value or "").strip().strip('"')
        if not text:
            return ""
        lower = text.lower()
        if lower.startswith(
            (
                "shell:",
                "steam://",
                "http://",
                "https://",
                "ms-settings:",
                "microsoft-edge:",
                "calculator:",
                "appx:",
            )
        ):
            return ""
        text = text.split(",")[0].strip().strip('"')
        try:
            return str(Path(text).expanduser().resolve(strict=False))
        except Exception:
            return text

    def classify_target(self, raw_value: str) -> Dict[str, Any]:
        text = str(raw_value or "").strip().strip('"')
        lowered = text.lower()
        if lowered.startswith("shell:"):
            return {
                "platform": "windows",
                "platform_object_type": "shell_app",
                "platform_object_id": "",
                "launch_target_kind": "shell_app",
                "launch_target_raw": text,
                "target_path": "",
                "entry_path": text,
                "install_dir": "",
                "route_confidence": "medium",
            }
        if lowered.startswith("appx:"):
            return {
                "platform": "windows",
                "platform_object_type": "appx",
                "platform_object_id": "",
                "launch_target_kind": "appx",
                "launch_target_raw": text,
                "target_path": "",
                "entry_path": text,
                "install_dir": "",
                "route_confidence": "medium",
            }
        if lowered.startswith(("ms-settings:", "microsoft-edge:", "calculator:")):
            return {
                "platform": "windows",
                "platform_object_type": "shell_app",
                "platform_object_id": lowered.split(":", 1)[0],
                "launch_target_kind": "shell_app",
                "launch_target_raw": text,
                "target_path": "",
                "entry_path": text,
                "install_dir": "",
                "route_confidence": "medium",
            }
        parsed = self.protocol_parser.parse(text)
        if parsed["launch_target_kind"] in {"protocol", "web_url"}:
            parsed["target_path"] = ""
            parsed["entry_path"] = ""
            parsed["install_dir"] = ""
            return parsed
        if not text:
            parsed["target_path"] = ""
            parsed["entry_path"] = ""
            parsed["install_dir"] = ""
            return parsed
        normalized = self.normalize_path(text)
        launch_target_kind = "local_exe" if normalized.lower().endswith(".exe") else "local_file"
        return {
            "platform": parsed.get("platform", "unknown"),
            "platform_object_type": parsed.get("platform_object_type", ""),
            "platform_object_id": parsed.get("platform_object_id", ""),
            "launch_target_kind": launch_target_kind,
            "launch_target_raw": text,
            "target_path": normalized,
            "entry_path": normalized,
            "install_dir": self.install_dir_provider.guess(normalized),
            "route_confidence": "high" if normalized else "low",
        }

    def resolve_shortcut_target(self, shortcut_path: Path) -> str:
        suffix = shortcut_path.suffix.lower()
        if suffix == ".url":
            try:
                for line in shortcut_path.read_text(encoding="utf-8", errors="ignore").splitlines():
                    if line.startswith("URL="):
                        return line.partition("=")[2].strip()
            except Exception:
                return ""
            return ""

        shortcut_text = str(shortcut_path).replace("'", "''")
        command = [
            "powershell",
            "-NoProfile",
            "-Command",
            (
                "$ws = New-Object -ComObject WScript.Shell; "
                f"$sc = $ws.CreateShortcut('{shortcut_text}'); "
                "Write-Output $sc.TargetPath"
            ),
        ]
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            if completed.returncode == 0:
                return completed.stdout.strip()
        except Exception:
            return ""
        return ""
