from __future__ import annotations

from typing import Any, Dict, Iterable, List

from bootstrap.hundun.scan import discover_apps as discover_apps_from_app_map
from services.desktop.tianting.providers.launch_target_provider import LaunchTargetProvider
from services.desktop.tianting.sources.base_source import SoftwareSourceBase


class AppMapSource(SoftwareSourceBase):
    source_id = "app_map_fallback"

    def __init__(self) -> None:
        self.launch_target_provider = LaunchTargetProvider()

    def collect(self, *, existing_app_ids: Iterable[str] | None = None, app_map: Dict[str, Any] | None = None) -> List[Dict[str, Any]]:
        discovered = discover_apps_from_app_map(app_map or {}, list(existing_app_ids or []))
        results: List[Dict[str, Any]] = []
        for item in discovered:
            if not isinstance(item, dict):
                continue
            target_info = self.launch_target_provider.classify_target(
                str(item.get("launch_target_raw", item.get("target_path", ""))).strip()
            )
            row = dict(item)
            row.update(target_info)
            row["discover_source"] = self.source_id
            results.append(row)
        return results
