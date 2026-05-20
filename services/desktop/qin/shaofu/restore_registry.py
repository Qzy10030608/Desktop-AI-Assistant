from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class RestoreRegistry:
    def __init__(self, project_root: str | Path | None = None) -> None:
        self.project_root = Path(project_root or Path(__file__).resolve().parents[4]).expanduser().resolve()
        self.base_dir = self.project_root / "data" / "runtime" / "desktop" / "shaofu"
        self.path = self.base_dir / "restore_registry.jsonl"

    def append(self, material: dict[str, Any]) -> dict[str, Any]:
        self.base_dir.mkdir(parents=True, exist_ok=True)
        payload = dict(material or {})
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")
        return payload

    def read_tail(self, limit: int = 100, *, include_deleted: bool = False) -> list[dict[str, Any]]:
        records = self.read_all(include_deleted=include_deleted)
        return records[-max(1, int(limit)):]

    def read_all(self, *, include_deleted: bool = False) -> list[dict[str, Any]]:
        records = self._merged_records()
        if include_deleted:
            return records
        return [item for item in records if not bool(item.get("deleted", False))]

    def find_by_material_id(self, material_id: str, *, include_deleted: bool = True) -> dict[str, Any] | None:
        normalized = str(material_id or "").strip()
        if not normalized:
            return None
        for item in reversed(self.read_all(include_deleted=include_deleted)):
            if str(item.get("material_id", "") or "").strip() == normalized:
                return item
        return None

    def mark_record_deleted(
        self,
        *,
        material_id: str = "",
        checkpoint_id: str = "",
        reason: str = "user_deleted_record",
    ) -> dict[str, Any]:
        material_key = str(material_id or "").strip()
        checkpoint_key = str(checkpoint_id or "").strip()
        if not material_key and not checkpoint_key:
            return {"ok": False, "error": "missing_record_id"}
        target: dict[str, Any] | None = None
        for item in reversed(self.read_all(include_deleted=True)):
            if material_key and str(item.get("material_id", "") or "").strip() == material_key:
                target = item
                break
            if checkpoint_key and str(item.get("checkpoint_id", "") or "").strip() == checkpoint_key:
                target = item
                break
        if target is None:
            return {"ok": False, "error": "record_not_found"}
        update = dict(target)
        update["deleted"] = True
        update["deleted_at"] = self._now_iso()
        update["delete_reason"] = str(reason or "user_deleted_record")
        update["record_event"] = "shaofu.record.deleted"
        self.append(update)
        return {"ok": True, "record": update}

    def filter_by_environment(self, environment: str, *, include_deleted: bool = False) -> list[dict[str, Any]]:
        normalized = str(environment or "").strip().lower()
        return [
            item for item in self.read_all(include_deleted=include_deleted)
            if self._environment_for(item) == normalized
        ]

    def _read_raw(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        result: list[dict[str, Any]] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            try:
                item = json.loads(line)
            except Exception:
                continue
            if isinstance(item, dict):
                result.append(item)
        return result

    def _merged_records(self) -> list[dict[str, Any]]:
        merged: dict[str, dict[str, Any]] = {}
        order: list[str] = []
        for item in self._read_raw():
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

    def _now_iso(self) -> str:
        return datetime.now(timezone.utc).isoformat()
