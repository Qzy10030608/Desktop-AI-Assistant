from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from services.desktop.qin.shaofu.storage_index import StorageIndex


class StorageMetricsService:
    """Read-only storage metrics for Shaofu restore materials."""

    def __init__(self, project_root: str | Path | None = None) -> None:
        self.project_root = Path(project_root or Path(__file__).resolve().parents[4]).expanduser().resolve()
        self.shaofu_dir = self.project_root / "data" / "runtime" / "desktop" / "shaofu"
        self.restore_registry_path = self.shaofu_dir / "restore_registry.jsonl"
        self.storage_index_path = self.shaofu_dir / "storage_index.json"

    def collect_metrics(self) -> dict[str, Any]:
        materials = self._merged_materials(self._read_jsonl(self.restore_registry_path))
        active_materials = [item for item in materials if not bool(item.get("deleted", False))]
        storage_index = self._read_json(self.storage_index_path, {})
        shaofu_storage = self._collect_shaofu_storage()
        shaofu_size_bytes = sum(
            int(item.get("size_bytes", 0) or 0)
            for item in shaofu_storage.values()
            if isinstance(item, dict)
        )
        cleanup_candidate_count = 0
        try:
            cleanup_candidate_count = len(StorageIndex(self.project_root).cleanup_candidates())
        except Exception:
            cleanup_candidate_count = 0
        return {
            "shaofu_dir": str(self.shaofu_dir),
            "materials_count": len(active_materials),
            "ready_materials": len([item for item in active_materials if str(item.get("material_status", "")).lower() == "ready"]),
            "failed_materials": len([item for item in active_materials if str(item.get("material_status", "")).lower() in {"failed", "missing_strategy"}]),
            "vm_material_count": len([item for item in active_materials if self._environment_for(item) == "vm"]),
            "host_material_count": len([item for item in active_materials if self._environment_for(item) == "host"]),
            "sandbox_ignored_count": len([item for item in materials if self._environment_for(item) == "sandbox"]),
            "deleted_count": len([item for item in materials if bool(item.get("deleted", False))]),
            "expired_count": len([item for item in active_materials if self._is_expired(item)]),
            "cleanup_candidate_count": cleanup_candidate_count,
            "storage_index": storage_index,
            "shaofu_size_bytes": shaofu_size_bytes,
            "shaofu_storage": shaofu_storage,
        }

    def _collect_shaofu_storage(self) -> dict[str, dict[str, Any]]:
        result: dict[str, dict[str, Any]] = {}
        for name in ("backups", "quarantine", "snapshots", "materials"):
            path = self.shaofu_dir / name
            result[name] = {
                "path": str(path),
                "size_bytes": self._dir_size(path),
            }
        return result

    def _dir_size(self, path: Path) -> int:
        if not path.exists():
            return 0
        total = 0
        try:
            for root, _dirs, files in os.walk(path, followlinks=False):
                root_path = Path(root)
                for name in files:
                    try:
                        total += (root_path / name).stat().st_size
                    except Exception:
                        continue
        except Exception:
            return 0
        return total

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

    def _merged_materials(self, materials: list[dict[str, Any]]) -> list[dict[str, Any]]:
        merged: dict[str, dict[str, Any]] = {}
        order: list[str] = []
        for item in materials:
            key = self._record_key(item)
            if not key:
                key = f"line:{len(order)}"
            if key not in merged:
                order.append(key)
                merged[key] = dict(item)
            else:
                merged[key].update(dict(item))
        return [merged[key] for key in order]

    def _record_key(self, item: dict[str, Any]) -> str:
        material_id = str(item.get("material_id", "") or "").strip()
        if material_id:
            return f"material:{material_id}"
        checkpoint_id = str(item.get("checkpoint_id", "") or "").strip()
        if checkpoint_id:
            return f"checkpoint:{checkpoint_id}"
        return ""

    def _environment_for(self, item: dict[str, Any]) -> str:
        execution_backend = str(item.get("execution_backend", "") or "").strip().lower()
        target_environment = str(item.get("target_environment", "") or "").strip().lower()
        path_namespace = str(item.get("path_namespace", "") or "").strip().lower()
        if execution_backend == "vm" or target_environment == "virtual_machine" or path_namespace == "vm_windows":
            return "vm"
        if execution_backend == "host" or target_environment in {"local_host", "host_machine"} or path_namespace == "host_windows":
            return "host"
        if execution_backend == "sandbox" or target_environment == "sandbox_simulation" or path_namespace == "sandbox":
            return "sandbox"
        return "unknown"

    def _is_expired(self, item: dict[str, Any]) -> bool:
        expire_at = str(item.get("expire_at", "") or "").strip()
        if not expire_at:
            return False
        try:
            parsed = datetime.fromisoformat(expire_at.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed < datetime.now(timezone.utc)
        except Exception:
            return False
