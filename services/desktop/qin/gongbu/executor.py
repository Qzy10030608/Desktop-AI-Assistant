from __future__ import annotations

from pathlib import Path

from services.desktop.qin.gongbu.registry import AdapterRegistry
from services.desktop.qin.shangshu.router import DesktopRouter


class DesktopExecutor:
    """Minimal synchronous executor for Qin desktop readonly V1."""

    def __init__(
        self,
        registry: AdapterRegistry | None = None,
        router: DesktopRouter | None = None,
        *,
        project_root: str | Path | None = None,
    ) -> None:
        self.registry = registry or AdapterRegistry(project_root=project_root)
        self.router = router or DesktopRouter()
        self.emergency_stopped = False

    def set_emergency_stop(self, stopped: bool) -> None:
        self.emergency_stopped = bool(stopped)

    def execute(self, task: dict) -> dict:
        action = str((task or {}).get("action", "")).strip()
        if self.emergency_stopped:
            return {
                "ok": False,
                "action": action,
                "adapter_id": "",
                "message": "桌面连接已暂停",
                "data": {},
            }

        adapter_id = ""
        try:
            requested_adapter = str((task or {}).get("adapter_id", "") or "").strip().lower()
            execution_backend = str((task or {}).get("execution_backend", "") or "").strip().lower()

            if requested_adapter in {"host", "host_windows"} or execution_backend == "host":
                from services.desktop.qin.gongbu.adapters.host_windows_adapter import HostWindowsAdapter

                adapter_id = "host_windows"
                adapter = HostWindowsAdapter()
            else:
                adapter_id = self.router.resolve_adapter_id(task)
                adapter = self.registry.get(adapter_id)

            result = adapter.execute(task)
            if not isinstance(result, dict):
                raise ValueError("adapter.execute(task) 返回结果不是 dict")

            data = result.get("data", {})
            return {
                "ok": bool(result.get("ok", False)),
                "action": action,
                "adapter_id": str(result.get("adapter_id", adapter_id)).strip() or adapter_id,
                "message": str(result.get("message", "")).strip(),
                "data": data if isinstance(data, dict) else {},
            }
        except Exception as exc:
            return {
                "ok": False,
                "action": action,
                "adapter_id": adapter_id,
                "message": str(exc).strip() or "执行失败",
                "data": {},
            }
