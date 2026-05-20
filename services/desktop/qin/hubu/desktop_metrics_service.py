from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class DesktopMetricsService:
    """Read-only metrics aggregator for desktop governance."""

    def __init__(self, project_root: str | Path | None = None) -> None:
        self.project_root = Path(project_root or Path(__file__).resolve().parents[4]).expanduser().resolve()
        self.audit_path = self.project_root / "data" / "logs" / "desktop" / "audit.jsonl"
        self.checkpoint_path = self.project_root / "data" / "logs" / "desktop" / "action_checkpoints.jsonl"
        self.vm_memory_path = self.project_root / "data" / "runtime" / "desktop" / "vm_connection_memory.json"
        self.shaofu_restore_registry_path = self.project_root / "data" / "runtime" / "desktop" / "shaofu" / "restore_registry.jsonl"

    def collect_metrics(self, *, runtime_state: dict[str, Any] | None = None) -> dict[str, Any]:
        audit_events = self._read_jsonl(self.audit_path)
        checkpoints = self._read_jsonl(self.checkpoint_path)
        memories = self._read_json(self.vm_memory_path, {"memories": []}).get("memories", [])
        materials = self._read_jsonl(self.shaofu_restore_registry_path)
        memories = memories if isinstance(memories, list) else []

        vm_attempts = len(memories)
        vm_success = len([item for item in memories if isinstance(item, dict) and bool(item.get("ok", False))])
        latest_memory = memories[-1] if memories and isinstance(memories[-1], dict) else {}
        runtime = runtime_state if isinstance(runtime_state, dict) else {}
        vm_software_count = self._safe_int(runtime.get("vm_apps_count", latest_memory.get("apps_count", 0)))
        vm_software_raw_count = self._safe_int(runtime.get("vm_software_raw_count", vm_software_count))
        vm_software_final_count = self._safe_int(runtime.get("vm_software_final_count", vm_software_count))
        vm_software_hidden_count = self._safe_int(runtime.get("vm_software_hidden_count", 0))
        vm_software_merged_uninstallers = self._safe_int(runtime.get("vm_software_merged_uninstallers", 0))
        durations = [
            float(item.get("duration_ms", 0) or 0)
            for item in memories
            if isinstance(item, dict) and float(item.get("duration_ms", 0) or 0) > 0
        ]
        return {
            "total_actions": len(audit_events),
            "sandbox_actions": self._count_adapter(audit_events, "sandbox"),
            "vm_actions": self._count_adapter(audit_events, "vm"),
            "host_blocked_actions": len([
                item for item in audit_events
                if str(item.get("route_result", "")).strip().lower().startswith("host.")
            ]),
            "failed_actions": len([
                item for item in audit_events
                if str(item.get("decision", "")).strip().lower() in {"deny", "confirm_required"}
            ]),
            "dangerous_actions": len([
                item for item in audit_events
                if str(item.get("action", "")).strip().lower() in {"app.uninstall", "app.move", "app.relocate", "app.update"}
            ]),
            "vm_connect_attempts": vm_attempts,
            "vm_connect_success": vm_success,
            "vm_connect_failed": max(0, vm_attempts - vm_success),
            "avg_vm_connect_duration_ms": round(sum(durations) / len(durations), 2) if durations else 0.0,
            "checkpoint_count": len(checkpoints),
            "shaofu_material_count": len(materials),
            "shaofu_material_failed": len([
                item for item in materials
                if str(item.get("material_status", "")).strip().lower() in {"failed", "missing_strategy"}
            ]),
            "vm_software_count": vm_software_count,
            "vm_software_raw_count": vm_software_raw_count,
            "vm_software_final_count": vm_software_final_count,
            "vm_software_hidden_count": vm_software_hidden_count,
            "vm_software_merged_uninstallers": vm_software_merged_uninstallers,
            "runtime_state": runtime,
        }

    def _count_adapter(self, events: list[dict[str, Any]], adapter_id: str) -> int:
        normalized = str(adapter_id or "").strip().lower()
        return len([item for item in events if str(item.get("adapter_id", "")).strip().lower() == normalized])

    def _read_jsonl(self, path: Path) -> list[dict[str, Any]]:
        if not path.exists():
            return []
        result: list[dict[str, Any]] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                item = json.loads(line)
            except Exception:
                continue
            if isinstance(item, dict):
                result.append(item)
        return result

    def _read_json(self, path: Path, default: dict[str, Any]) -> dict[str, Any]:
        if not path.exists():
            return default
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return default
        return data if isinstance(data, dict) else default

    def _safe_int(self, value: Any) -> int:
        try:
            return int(value or 0)
        except Exception:
            return 0
