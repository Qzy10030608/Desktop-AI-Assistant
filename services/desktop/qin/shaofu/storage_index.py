from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


class StorageIndex:
    def __init__(self, project_root: str | Path | None = None) -> None:
        self.project_root = Path(project_root or Path(__file__).resolve().parents[4]).expanduser().resolve()
        self.base_dir = self.project_root / "data" / "runtime" / "desktop" / "shaofu"
        self.path = self.base_dir / "storage_index.json"

    def ensure_layout(self) -> None:
        self.base_dir.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.write({
                "materials": [],
                "storage": {
                    "base_dir": str(self.base_dir),
                    "retention_policy": {"default_days": 14},
                },
            })

    def read(self) -> dict[str, Any]:
        self.ensure_layout()
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return self._default_data()
        return data if isinstance(data, dict) else self._default_data()

    def write(self, data: dict[str, Any]) -> None:
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")

    def add_material(self, material: dict[str, Any]) -> None:
        data = self.read()
        items = data.get("materials", []) if isinstance(data.get("materials"), list) else []
        items.append(dict(material or {}))
        data["materials"] = items[-1000:]
        storage = data.get("storage", {}) if isinstance(data.get("storage"), dict) else {}
        storage["base_dir"] = str(self.base_dir)
        storage.setdefault("retention_policy", {"default_days": 14})
        data["storage"] = storage
        self.write(data)

    def update_material(self, material: dict[str, Any]) -> None:
        payload = dict(material or {})
        material_id = str(payload.get("material_id", "") or "").strip()
        checkpoint_id = str(payload.get("checkpoint_id", "") or "").strip()
        if not material_id and not checkpoint_id:
            self.add_material(payload)
            return
        data = self.read()
        items = data.get("materials", []) if isinstance(data.get("materials"), list) else []
        replaced = False
        next_items: list[dict[str, Any]] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            same_material = material_id and str(item.get("material_id", "") or "").strip() == material_id
            same_checkpoint = checkpoint_id and str(item.get("checkpoint_id", "") or "").strip() == checkpoint_id
            if same_material or same_checkpoint:
                merged = dict(item)
                merged.update(payload)
                next_items.append(merged)
                replaced = True
            else:
                next_items.append(item)
        if not replaced:
            next_items.append(payload)
        data["materials"] = next_items[-1000:]
        storage = data.get("storage", {}) if isinstance(data.get("storage"), dict) else {}
        storage["base_dir"] = str(self.base_dir)
        storage.setdefault("retention_policy", {"default_days": 14})
        data["storage"] = storage
        self.write(data)

    def summarize(self, *, include_deleted: bool = False, environment: str = "") -> dict[str, Any]:
        try:
            data = self.read()
            items = data.get("materials", []) if isinstance(data.get("materials"), list) else []
            summary = self._empty_summary()
            for item in items:
                if not isinstance(item, dict):
                    continue
                if not include_deleted and bool(item.get("deleted", False)):
                    continue
                env = self._environment_for(item)
                if environment and env != str(environment or "").strip().lower():
                    continue
                summary["total"] += 1
                self._increment(summary["by_environment"], env)
                if bool(item.get("deleted", False)):
                    summary["deleted"] += 1
                material_type = self._normalized(item.get("material_type"), "unknown")
                retention_class = self._normalized(item.get("retention_class"), "unknown")
                restore_status = self._normalized(item.get("restore_status"), "pending")
                verify_status = self._normalized(item.get("verify_status"), "unverified")
                self._increment(summary["by_material_type"], material_type)
                self._increment(summary["by_retention_class"], retention_class)
                self._increment(summary["by_restore_status"], restore_status)
                self._increment(summary["by_verify_status"], verify_status)
                material_status = self._normalized(item.get("material_status"), "")
                if restore_status == "pending":
                    summary["pending"] += 1
                if restore_status == "ready" or material_status == "ready":
                    summary["ready"] += 1
                if restore_status == "expired" or self._is_expired(item):
                    summary["expired"] += 1
                if verify_status == "unverified":
                    summary["unverified"] += 1
                if (
                    retention_class == "cleanup_on_exit"
                    or self._normalized(item.get("material_scope"), "") == "temp"
                    or material_type == "temp_material"
                ):
                    summary["temp"] += 1
                try:
                    summary["size_bytes"] += int(item.get("size_bytes", 0) or 0)
                except Exception:
                    continue
            return summary
        except Exception:
            return self._empty_summary()

    def summarize_by_action(self) -> dict[str, int]:
        return self._summarize_by_key("action", "unknown")

    def summarize_by_restore_status(self) -> dict[str, int]:
        return self._summarize_by_key("restore_status", "pending")

    def summarize_by_retention_class(self) -> dict[str, int]:
        return self._summarize_by_key("retention_class", "unknown")

    def update_retention_days(self, days: int) -> dict[str, Any]:
        normalized = int(days or 14)
        if normalized not in {7, 14, 30}:
            normalized = 14
        data = self.read()
        storage = data.get("storage", {}) if isinstance(data.get("storage"), dict) else {}
        storage["base_dir"] = str(self.base_dir)
        policy = storage.get("retention_policy", {}) if isinstance(storage.get("retention_policy"), dict) else {}
        policy["default_days"] = normalized
        storage["retention_policy"] = policy
        data["storage"] = storage
        self.write(data)
        return {"ok": True, "retention_days": normalized}

    def get_retention_days(self) -> int:
        data = self.read()
        storage = data.get("storage", {}) if isinstance(data.get("storage"), dict) else {}
        policy = storage.get("retention_policy", {}) if isinstance(storage.get("retention_policy"), dict) else {}
        try:
            days = int(policy.get("default_days", 14) or 14)
        except Exception:
            days = 14
        return days if days in {7, 14, 30} else 14

    def mark_record_deleted(
        self,
        *,
        material_id: str = "",
        checkpoint_id: str = "",
        reason: str = "user_deleted_record",
    ) -> dict[str, Any]:
        data = self.read()
        items = data.get("materials", []) if isinstance(data.get("materials"), list) else []
        material_key = str(material_id or "").strip()
        checkpoint_key = str(checkpoint_id or "").strip()
        if not material_key and not checkpoint_key:
            return {"ok": False, "error": "missing_record_id"}
        now = self._now_iso()
        matched = False
        for item in items:
            if not isinstance(item, dict):
                continue
            if material_key and str(item.get("material_id", "") or "").strip() == material_key:
                matched = True
            elif checkpoint_key and str(item.get("checkpoint_id", "") or "").strip() == checkpoint_key:
                matched = True
            else:
                continue
            item["deleted"] = True
            item["deleted_at"] = now
            item["delete_reason"] = str(reason or "user_deleted_record")
        if not matched:
            return {"ok": False, "error": "record_not_found"}
        data["materials"] = items
        storage = data.get("storage", {}) if isinstance(data.get("storage"), dict) else {}
        storage["base_dir"] = str(self.base_dir)
        storage.setdefault("retention_policy", {"default_days": 14})
        data["storage"] = storage
        self.write(data)
        return {"ok": True}

    def cleanup_candidates(self, *, environment: str = "", retention_days: int | None = None) -> list[dict[str, Any]]:
        days = int(retention_days or self.get_retention_days())
        items = self.read().get("materials", [])
        if not isinstance(items, list):
            return []
        result: list[dict[str, Any]] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            if environment and self._environment_for(item) != str(environment or "").strip().lower():
                continue
            if self._is_cleanup_candidate(item, days):
                result.append(dict(item))
        return result

    def _empty_summary(self) -> dict[str, Any]:
        return {
            "total": 0,
            "by_material_type": {},
            "by_retention_class": {},
            "by_restore_status": {},
            "by_verify_status": {},
            "by_environment": {},
            "pending": 0,
            "ready": 0,
            "expired": 0,
            "unverified": 0,
            "temp": 0,
            "deleted": 0,
            "size_bytes": 0,
        }

    def _default_data(self) -> dict[str, Any]:
        return {
            "materials": [],
            "storage": {
                "base_dir": str(self.base_dir),
                "retention_policy": {"default_days": 14},
            },
        }

    def _normalized(self, value: Any, default: str) -> str:
        text = str(value or "").strip().lower()
        return text or default

    def _increment(self, bucket: dict[str, int], key: str) -> None:
        bucket[key] = int(bucket.get(key, 0) or 0) + 1

    def _summarize_by_key(self, key: str, default: str) -> dict[str, int]:
        try:
            data = self.read()
            items = data.get("materials", []) if isinstance(data.get("materials"), list) else []
            result: dict[str, int] = {}
            for item in items:
                if isinstance(item, dict):
                    self._increment(result, self._normalized(item.get(key), default))
            return result
        except Exception:
            return {}

    def _environment_for(self, item: dict[str, Any]) -> str:
        execution_backend = self._normalized(item.get("execution_backend"), "")
        target_environment = self._normalized(item.get("target_environment"), "")
        path_namespace = self._normalized(item.get("path_namespace"), "")
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

    def _computed_expired(self, item: dict[str, Any], days: int) -> bool:
        created_at = str(item.get("created_at", "") or "").strip()
        if not created_at:
            return False
        try:
            parsed = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed + timedelta(days=days) < datetime.now(timezone.utc)
        except Exception:
            return False

    def _has_real_material_path(self, item: dict[str, Any]) -> bool:
        keys = (
            "backup_original_path",
            "backup_path",
            "quarantine_path",
            "registry_backup_path",
            "shortcut_backup_dir",
            "service_backup_path",
            "snapshot_id",
        )
        for key in keys:
            value = str(item.get(key, "") or "").strip()
            if value and value not in {"-", "__pending__", "__vm_agent_select__", "__vm_agent_auto__"} and not value.startswith("vm_shaofu://"):
                return True
        return False

    def _is_cleanup_candidate(self, item: dict[str, Any], days: int) -> bool:
        if self._truthy(item.get("keep", False)):
            return False
        if bool(item.get("deleted", False)) and not self._has_real_material_path(item):
            return True
        if self._normalized(item.get("verify_status"), "") == "unverified":
            return False
        if self._normalized(item.get("restore_status"), "") in {"pending", "ready"}:
            return False
        if self._normalized(item.get("cleanup_policy"), "") == "manual_only":
            return False
        retention_class = self._normalized(item.get("retention_class"), "")
        if retention_class in {"permanent_index", "manual_only"}:
            return False
        action = self._normalized(item.get("action"), "")
        if action == "app.relocate" and str(item.get("backup_original_path", "") or "").strip():
            return False
        if action == "file.delete" and str(item.get("quarantine_path", "") or "").strip():
            return False
        material_type = self._normalized(item.get("material_type"), "")
        material_status = self._normalized(item.get("material_status"), "")
        cleanup_policy = self._normalized(item.get("cleanup_policy"), "")
        if cleanup_policy == "cleanup_on_exit" or retention_class == "cleanup_on_exit" or material_type == "temp_material":
            return True
        if material_status in {"cancelled", "incomplete"}:
            return True
        if (self._is_expired(item) or self._computed_expired(item, days)) and retention_class != "critical_long":
            return not self._has_real_material_path(item)
        return False

    def _truthy(self, value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return value != 0
        return str(value or "").strip().lower() in {"1", "true", "yes", "y", "on", "是"}
