from __future__ import annotations

from pathlib import Path
from typing import Tuple


class CategoryClassifier:
    def classify(
        self,
        *,
        title: str,
        target_path: str,
        launch_target_kind: str,
        launch_target_raw: str,
    ) -> Tuple[str, str]:
        title = str(title or "").strip()
        target_path = str(target_path or "").strip()
        launch_target_raw = str(launch_target_raw or "").strip()

        title_lower = title.lower()
        target_lower = target_path.lower()
        raw_lower = launch_target_raw.lower()
        haystack = f"{title} {target_path} {launch_target_raw}".lower()
        target_name = Path(target_lower).name

        admin_tool_names = {
            "administrative tools",
            "component services",
            "computer management",
            "event viewer",
            "performance monitor",
            "print management",
            "registry editor",
            "resource monitor",
            "security configuration management",
            "services",
            "task scheduler",
            "windows defender firewall with advanced security",
            "磁盘管理",
        }
        admin_tool_files = {
            "compmgmt.msc",
            "comexp.msc",
            "eventvwr.msc",
            "services.msc",
            "taskschd.msc",
            "wf.msc",
            "printmanagement.msc",
            "perfmon.msc",
            "secpol.msc",
            "regedit.exe",
            "rundll32.exe",
            "dpinst.exe",
            "dpinst64.exe",
            "msiexec.exe",
        }
        if title_lower in admin_tool_names or target_lower.endswith(".msc") or target_name in admin_tool_files:
            return "admin_tool", "driver_or_runtime"

        if (
            target_name == "explorer.exe"
            or "file explorer" in title_lower
            or "文件资源管理器" in title
            or "control panel" in haystack
            or title_lower == "run"
            or title == "运行"
        ):
            return "system_core", "driver_or_runtime"

        if target_path and any(
            keyword in haystack
            for keyword in {
                "steam.exe",
                "epic games launcher",
                "battle.net launcher",
                "ea app",
                "ubisoft connect",
            }
        ):
            return "platform_app", "platform_app"

        if launch_target_kind in {"protocol", "launcher", "command"}:
            if any(keyword in raw_lower for keyword in {"steam://", "epic://", "battlenet://", "origin://", "ea://"}):
                return "platform_app", "indirect_launcher"
            return "indirect_launcher", "indirect_launcher"

        if launch_target_kind in {"appx", "shell_app"}:
            return "system_app", "system_app"

        installer_keywords = {
            "setup",
            "installshield",
            "package cache",
            "unins",
            "uninstall",
            "uninstaller",
            "installer",
            "bootstrapper",
            "updater",
            "update helper",
            "maintenance service",
            "helper service",
            "dpinst",
            "msiexec",
            "卸载器",
            "卸载",
            "安装程序",
            "更新程序",
        }
        if any(keyword in haystack for keyword in installer_keywords):
            return "installer_bundle", "installer_bundle"

        driver_keywords = {
            "driver",
            "driver package",
            "hal",
            "nvcpl",
            "realtek",
            "amd chipset",
            "display control panel",
            "container",
            "framework service",
            "service framework",
            "service",
            "驱动程序",
            "驱动程序包",
            "服务",
            "组件",
            "容器",
        }
        if any(keyword in haystack for keyword in driver_keywords):
            return "driver", "driver_or_runtime"

        runtime_keywords = {
            "runtime",
            "sdk",
            "development",
            ".net host",
            "fx resolver",
            "cuda",
            "cupti",
            "nvrtc",
            "nvtx",
            "redistributable",
            "运行库",
            "toolkit",
            "python",
            "conda",
            "miniconda",
            "anaconda",
            "node",
            "npm",
            "jdk",
            "jre",
            "java",
            "ffmpeg",
            "cublas",
            "cufft",
            "cuobjdump",
            "curand",
            "cusolver",
            "cusparse",
            "cuxxfilt",
            "compute sanitizer",
            "visual profiler",
            "occupancy calculator",
        }
        if any(keyword in haystack for keyword in runtime_keywords):
            return "runtime_env", "driver_or_runtime"

        if target_path:
            return "normal_app", "normal_app"

        return "unknown", "weak_missing_path"
