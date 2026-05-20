from __future__ import annotations

from typing import Dict, Iterable, List, Set

from services.desktop.software_models import SoftwareRecord


class SoftwareMergeService:
    def merge_for_mode(
        self,
        *,
        mode: str,
        builtin_records: Iterable[SoftwareRecord],
        trusted_records: Iterable[SoftwareRecord],
        candidate_records: Iterable[SoftwareRecord],
        hidden_ids: Set[str] | None = None,
    ) -> List[SoftwareRecord]:
        hidden_ids = hidden_ids or set()
        builtin_map: Dict[str, SoftwareRecord] = {item.app_id: item for item in builtin_records if item.app_id}
        trusted_map: Dict[str, SoftwareRecord] = {item.app_id: item for item in trusted_records if item.app_id}
        candidate_map: Dict[str, SoftwareRecord] = {item.app_id: item for item in candidate_records if item.app_id}
        rows: Dict[str, SoftwareRecord] = {}

        for app_id, builtin in builtin_map.items():
            row = SoftwareRecord.from_dict(builtin.to_dict())
            candidate = candidate_map.get(app_id)
            trusted = trusted_map.get(app_id)
            if candidate and candidate.target_path and not row.target_path:
                row.target_path = candidate.target_path
            if trusted:
                row = SoftwareRecord.from_dict(trusted.to_dict())
                row.builtin = True
            rows[app_id] = row

        if mode == "trusted":
            for app_id, trusted in trusted_map.items():
                rows[app_id] = SoftwareRecord.from_dict(trusted.to_dict())
            for app_id, candidate in candidate_map.items():
                if app_id in rows:
                    current = rows[app_id]
                    if not current.target_path and candidate.target_path:
                        current.target_path = candidate.target_path
                    if not current.launch_target_raw and candidate.launch_target_raw:
                        current.launch_target_raw = candidate.launch_target_raw
                        current.launch_target_kind = candidate.launch_target_kind
                    continue
                rows[app_id] = SoftwareRecord.from_dict(candidate.to_dict())

        result: List[SoftwareRecord] = []
        for row in rows.values():
            row.hidden = row.app_id in hidden_ids
            result.append(row)
        return sorted(
            result,
            key=lambda item: (
                0 if item.builtin else 1,
                0 if item.source == "confirmed" else 1,
                item.title.lower(),
                item.app_id,
            ),
        )
