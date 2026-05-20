from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from services.desktop.qin.shaofu.restore_registry import RestoreRegistry
from services.desktop.qin.shaofu.storage_index import StorageIndex


class FileQuarantineService:
    """Maintain Host file quarantine manifests and material status."""

    def __init__(
        self,
        project_root: str | Path | None = None,
        *,
        restore_registry: RestoreRegistry | None = None,
        storage_index: StorageIndex | None = None,
    ) -> None:
        self.project_root = Path(project_root or Path(__file__).resolve().parents[4]).expanduser().resolve()
        self.restore_registry = restore_registry or RestoreRegistry(self.project_root)
        self.storage_index = storage_index or StorageIndex(self.project_root)

    def find_material(
        self,
        *,
        restore_token: str = "",
        material_id: str = "",
        quarantine_path: str = "",
    ) -> dict[str, Any] | None:
        token = str(restore_token or "").strip()
        material_key = str(material_id or "").strip()
        quarantine = str(quarantine_path or "").strip()
        if material_key:
            found = self.restore_registry.find_by_material_id(material_key, include_deleted=True)
            if found is not None:
                return found
        for item in reversed(self.restore_registry.read_all(include_deleted=True)):
            if token and str(item.get("restore_token", "") or "").strip() == token:
                return item
            if quarantine and str(item.get("quarantine_path", "") or "").strip() == quarantine:
                return item
        return None

    def material_for_restore(self, arguments: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
        material = self.find_material(
            restore_token=str(arguments.get("restore_token", "") or ""),
            material_id=str(arguments.get("material_id", "") or ""),
            quarantine_path=str(arguments.get("quarantine_path", "") or ""),
        )
        if material is None:
            return None, "material_not_found"
        quarantine_path = str(material.get("quarantine_path", "") or "").strip()
        original_path = str(material.get("original_path", material.get("source_path", "")) or "").strip()
        if not quarantine_path:
            return None, "missing_quarantine_path"
        if not original_path:
            return None, "missing_original_path"
        return material, ""

    def mark_quarantined(self, material: dict[str, Any], result_data: dict[str, Any]) -> dict[str, Any]:
        now = self._now_iso()
        update = self._merged_material(material, result_data)
        update.update({
            "status": "quarantined",
            "material_status": "quarantined",
            "restore_status": "ready",
            "deleted_at": now,
            "updated_at": now,
        })
        self._persist(update)
        return update

    def mark_restored(self, material: dict[str, Any], result_data: dict[str, Any]) -> dict[str, Any]:
        now = self._now_iso()
        update = self._merged_material(material, result_data)
        update.update({
            "status": "restored",
            "material_status": "restored",
            "restore_status": "restored",
            "restored_at": now,
            "updated_at": now,
        })
        self._persist(update)
        return update

    def _merged_material(self, material: dict[str, Any], result_data: dict[str, Any]) -> dict[str, Any]:
        merged = dict(material or {})
        data = result_data if isinstance(result_data, dict) else {}
        original_path = str(
            data.get("original_path", merged.get("original_path", merged.get("source_path", ""))) or ""
        ).strip()
        quarantine_path = str(data.get("quarantine_path", merged.get("quarantine_path", "")) or "").strip()
        target_type = str(data.get("target_type", merged.get("target_type", "")) or "").strip()
        action = str(merged.get("action", data.get("action", "")) or "").strip()
        restore_action = str(
            merged.get("restore_action", data.get("restore_action", "folder.restore" if target_type == "directory" else "file.restore"))
            or ""
        ).strip()
        material_id = str(merged.get("material_id", data.get("material_id", "")) or "").strip()
        manifest_path = str(merged.get("manifest_path", data.get("manifest_path", "")) or "").strip()
        if not manifest_path and quarantine_path:
            manifest_path = str(Path(quarantine_path).parent / "manifest.json")
        merged.update({
            "material_id": material_id,
            "checkpoint_id": str(data.get("checkpoint_id", merged.get("checkpoint_id", "")) or ""),
            "restore_token": str(data.get("restore_token", merged.get("restore_token", "")) or ""),
            "run_id": str(data.get("run_id", merged.get("run_id", "")) or ""),
            "run_backend": str(data.get("run_backend", merged.get("run_backend", "host")) or "host"),
            "action": action,
            "target_type": target_type,
            "original_path": original_path,
            "source_path": original_path,
            "quarantine_path": quarantine_path,
            "restore_action": restore_action,
            "manifest_path": manifest_path,
        })
        return merged

    def _persist(self, material: dict[str, Any]) -> None:
        self.restore_registry.append(material)
        self.storage_index.update_material(material)
        manifest_path = str(material.get("manifest_path", "") or "").strip()
        if not manifest_path:
            quarantine_path = str(material.get("quarantine_path", "") or "").strip()
            if quarantine_path:
                manifest_path = str(Path(quarantine_path).parent / "manifest.json")
        if manifest_path:
            path = Path(manifest_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(material, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")

    def _now_iso(self) -> str:
        return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
