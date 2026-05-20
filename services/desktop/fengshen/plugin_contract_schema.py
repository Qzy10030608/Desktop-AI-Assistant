from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class PluginManifest:
    plugin_id: str
    name: str
    capability_type: str
    enabled: bool
    requires_network: bool
    requires_qin_review: bool
    entry_point: str
    generation: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def manifest_from_dict(data: dict[str, Any]) -> PluginManifest:
    payload = data if isinstance(data, dict) else {}
    return PluginManifest(
        plugin_id=str(payload.get("plugin_id", "") or ""),
        name=str(payload.get("name", "") or ""),
        capability_type=str(payload.get("capability_type", "") or ""),
        enabled=bool(payload.get("enabled", False)),
        requires_network=bool(payload.get("requires_network", False)),
        requires_qin_review=bool(payload.get("requires_qin_review", True)),
        entry_point=str(payload.get("entry_point", "") or ""),
        generation=str(payload.get("generation", "") or ""),
    )
