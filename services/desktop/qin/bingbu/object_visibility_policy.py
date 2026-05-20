from __future__ import annotations

from typing import Tuple


class ObjectVisibilityPolicy:
    def decide(self, *, category: str, candidate_kind: str, launch_target_kind: str) -> Tuple[str, str]:
        if launch_target_kind == "web_url":
            return "diagnostics_only", "普通网页链接默认不进入软件治理主显示区。"
        if candidate_kind in {"installer_bundle", "driver_or_runtime"} or category in {
            "admin_tool",
            "installer_bundle",
            "driver",
            "runtime_env",
            "system_core",
        }:
            return "diagnostics_only", "安装器、驱动或运行时对象默认不进入软件治理主显示区。"
        return "main", "对象进入软件治理主显示区。"

    def actionability(self, *, candidate_kind: str, launch_target_kind: str, target_path: str) -> str:
        if launch_target_kind == "web_url":
            return "blocked"
        if candidate_kind == "indirect_launcher":
            return "display_only"
        if target_path:
            return "sandboxable"
        return "display_only"
