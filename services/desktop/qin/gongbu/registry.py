from __future__ import annotations

from pathlib import Path
from typing import Any

from services.desktop.qin.gongbu.adapters.explorer_adapter import ExplorerAdapter
from services.desktop.qin.gongbu.adapters.filesystem_readonly_adapter import FilesystemReadonlyAdapter
from services.desktop.qin.gongbu.adapters.host_windows_adapter import HostWindowsAdapter
from services.desktop.qin.gongbu.adapters.sandbox_adapter import SandboxAdapter
from services.desktop.qin.gongbu.adapters.system_info_adapter import SystemInfoAdapter
from services.desktop.qin.gongbu.adapters.vm_adapter import VmAdapter


class AdapterRegistry:
    """Minimal adapter registry for Qin desktop readonly V1."""

    def __init__(self, project_root: str | Path | None = None) -> None:
        self.project_root = project_root
        self._adapters: dict[str, Any] = {}
        self._register_defaults()

    def _register_defaults(self) -> None:
        self._adapters["sandbox"] = SandboxAdapter()
        self._adapters["vm"] = VmAdapter()
        self._adapters["host_windows"] = HostWindowsAdapter()
        self._adapters["system_info"] = SystemInfoAdapter(project_root=self.project_root)
        self._adapters["filesystem_readonly"] = FilesystemReadonlyAdapter()
        self._adapters["explorer"] = ExplorerAdapter()

    def get(self, adapter_id: str) -> Any:
        normalized = str(adapter_id or "").strip()
        if normalized not in self._adapters:
            raise ValueError(f"未注册的 adapter: {normalized}")
        return self._adapters[normalized]

    def has(self, adapter_id: str) -> bool:
        normalized = str(adapter_id or "").strip()
        return normalized in self._adapters

    def list_ids(self) -> list[str]:
        return sorted(self._adapters.keys())
