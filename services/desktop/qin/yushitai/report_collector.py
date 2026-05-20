from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class ReportCollector:
    """Read-only collector for Yushitai reports."""

    def __init__(self, project_root: str | Path | None = None) -> None:
        self.project_root = Path(project_root or Path(__file__).resolve().parents[4]).expanduser().resolve()
        self.audit_path = self.project_root / "data" / "logs" / "desktop" / "audit.jsonl"
        self.checkpoint_path = self.project_root / "data" / "logs" / "desktop" / "action_checkpoints.jsonl"
        self.vm_memory_path = self.project_root / "data" / "runtime" / "desktop" / "vm_connection_memory.json"
        self.runtime_path = self.project_root / "data" / "runtime" / "desktop_runtime.json"
        self.shaofu_dir = self.project_root / "data" / "runtime" / "desktop" / "shaofu"
        self.shaofu_restore_registry_path = self.shaofu_dir / "restore_registry.jsonl"
        self.shaofu_storage_index_path = self.shaofu_dir / "storage_index.json"
        self.yushitai_dir = self.project_root / "data" / "runtime" / "desktop" / "yushitai"
        self.index_path = self.yushitai_dir / "index.json"

    def collect(self, *, runtime_state: dict[str, Any] | None = None) -> dict[str, Any]:
        index = self._read_json_file(self.index_path, {"latest_run_id": "", "latest_run_backend": "", "runs": []})
        requested_backend = ""
        if isinstance(runtime_state, dict):
            try:
                from services.desktop.qin.yushitai.report_writer import _resolve_run_backend

                requested_backend = _resolve_run_backend(runtime_state)
            except Exception:
                requested_backend = ""
        run_backend = (
            requested_backend
            if requested_backend in {"host", "vm"}
            else str(index.get("latest_run_backend", "") or "").strip().lower()
        )
        run_id = self._latest_run_id_for_backend(index, run_backend) if run_backend in {"host", "vm"} else self._latest_run_id(index)
        run_dir = self._run_dir_for(run_id, run_backend, index) if run_id and run_backend != "sandbox" else None
        events_path = run_dir / "events.jsonl" if run_dir is not None else self.yushitai_dir / "events.jsonl"
        snapshot_path = run_dir / "snapshots" / "latest_state.json" if run_dir is not None else self.yushitai_dir / "snapshots" / "latest_state.json"
        vm_snapshot_path = run_dir / "snapshots" / "latest_vm_state.json" if run_dir is not None else self.yushitai_dir / "snapshots" / "latest_vm_state.json"
        software_snapshot_path = run_dir / "snapshots" / "latest_software_state.json" if run_dir is not None else self.yushitai_dir / "snapshots" / "latest_software_state.json"
        latest_snapshot = self._read_json_file(snapshot_path, {})
        latest_vm_snapshot = self._read_json_file(vm_snapshot_path, {})
        latest_software_snapshot = self._read_json_file(software_snapshot_path, {})
        snapshot_runtime = self._runtime_state_from_snapshot(latest_snapshot)
        effective_runtime_state = runtime_state if isinstance(runtime_state, dict) else snapshot_runtime or self._read_json_file(self.runtime_path, {})
        yushitai_events = self._read_jsonl_tail(events_path, 500)
        long_term_audit_events = self._read_jsonl_tail(self.audit_path, 500)
        long_term_checkpoint_events = self._read_jsonl_tail(self.checkpoint_path, 200)
        return {
            "audit_events": long_term_audit_events,
            "long_term_audit_events": long_term_audit_events,
            "yushitai_events": yushitai_events,
            "current_run_events_count": len(yushitai_events),
            "checkpoints": long_term_checkpoint_events,
            "long_term_checkpoint_events": long_term_checkpoint_events,
            "vm_connection_memory": self._read_json_file(self.vm_memory_path, {"memories": []}).get("memories", []),
            "runtime_state": effective_runtime_state,
            "latest_snapshot": latest_snapshot,
            "latest_vm_snapshot": latest_vm_snapshot,
            "latest_software_snapshot": latest_software_snapshot,
            "run_id": run_id,
            "run_backend": run_backend,
            "run_meta": self._read_json_file(run_dir / "run_meta.json", {}) if run_dir is not None else {},
            "latest_run_id": run_id,
            "latest_run_backend": run_backend,
            "latest_run_meta": self._read_json_file(run_dir / "run_meta.json", {}) if run_dir is not None else {},
            "shaofu_restore_registry": self._read_jsonl_tail(self.shaofu_restore_registry_path, 200),
            "shaofu_storage_index": self._read_json_file(self.shaofu_storage_index_path, {}),
            "paths": {
                "audit": str(self.audit_path),
                "checkpoints": str(self.checkpoint_path),
                "vm_connection_memory": str(self.vm_memory_path),
                "runtime": str(self.runtime_path),
                "yushitai_index": str(self.index_path),
                "yushitai_run_dir": str(run_dir) if run_dir is not None else "",
                "yushitai_events": str(events_path),
                "yushitai_snapshot": str(snapshot_path),
                "yushitai_vm_snapshot": str(vm_snapshot_path),
                "yushitai_software_snapshot": str(software_snapshot_path),
                "shaofu_restore_registry": str(self.shaofu_restore_registry_path),
                "shaofu_storage_index": str(self.shaofu_storage_index_path),
            },
        }

    def _read_json_file(self, path: Path, default: dict[str, Any]) -> dict[str, Any]:
        if not path.exists():
            return default
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return default
        return data if isinstance(data, dict) else default

    def _read_jsonl_tail(self, path: Path, limit: int) -> list[dict[str, Any]]:
        if not path.exists():
            return []
        lines = path.read_text(encoding="utf-8").splitlines()
        result: list[dict[str, Any]] = []
        for line in lines[-max(1, int(limit)):]:
            try:
                item = json.loads(line)
            except Exception:
                continue
            if isinstance(item, dict):
                result.append(item)
        return result

    def _latest_run_id(self, index: dict[str, Any] | None = None) -> str:
        data = index if isinstance(index, dict) else self._read_json_file(self.index_path, {"latest_run_id": ""})
        return str(data.get("latest_run_id", "") or "").strip()

    def _latest_run_id_for_backend(self, index: dict[str, Any], backend: str) -> str:
        normalized_backend = str(backend or "").strip().lower()
        if str(index.get("latest_run_backend", "") or "").strip().lower() == normalized_backend:
            return str(index.get("latest_run_id", "") or "").strip()
        runs = index.get("runs", []) if isinstance(index.get("runs"), list) else []
        for item in reversed(runs):
            if not isinstance(item, dict):
                continue
            if str(item.get("run_backend", "") or "").strip().lower() == normalized_backend:
                return str(item.get("run_id", "") or "").strip()
        return ""

    def _run_dir_for(self, run_id: str, backend: str, index: dict[str, Any]) -> Path:
        normalized_run_id = str(run_id or "").strip()
        normalized_backend = str(backend or "").strip().lower()
        runs = index.get("runs", []) if isinstance(index.get("runs"), list) else []
        for item in runs:
            if not isinstance(item, dict) or str(item.get("run_id", "") or "").strip() != normalized_run_id:
                continue
            recorded_dir = str(item.get("run_dir", "") or "").strip()
            if recorded_dir:
                return Path(recorded_dir)
            recorded_backend = str(item.get("run_backend", "") or "").strip().lower()
            if recorded_backend in {"host", "vm"}:
                return self.yushitai_dir / "runs" / recorded_backend / normalized_run_id
        if normalized_backend in {"host", "vm"}:
            return self.yushitai_dir / "runs" / normalized_backend / normalized_run_id
        for candidate_backend in ("host", "vm"):
            candidate = self.yushitai_dir / "runs" / candidate_backend / normalized_run_id
            if candidate.exists():
                return candidate
        return self.yushitai_dir / "runs" / normalized_run_id

    def _runtime_state_from_snapshot(self, snapshot: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(snapshot, dict):
            return {}
        system_state = snapshot.get("system_state", {}) if isinstance(snapshot.get("system_state"), dict) else {}
        if system_state:
            return {
                "test_backend": system_state.get("test_backend", system_state.get("current_backend", "")),
                "execution_backend": system_state.get("execution_backend", ""),
                "desktop_mode": system_state.get("desktop_mode", system_state.get("governance_mode", "")),
                "current_mode": system_state.get("desktop_mode", system_state.get("governance_mode", "")),
                "host_execution_enabled": bool(system_state.get("host_execution_enabled", False)),
                "vm_apps_count": system_state.get("vm_software_count", 0),
                "vm_software_raw_count": system_state.get("vm_software_raw_count", 0),
                "vm_software_final_count": system_state.get("vm_software_final_count", system_state.get("vm_software_count", 0)),
                "vm_software_hidden_count": system_state.get("vm_software_hidden_count", 0),
                "vm_software_merged_uninstallers": system_state.get("vm_software_merged_uninstallers", 0),
            }
        return snapshot
