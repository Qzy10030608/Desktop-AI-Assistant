from __future__ import annotations

from typing import Any, Dict


class SecondaryRouteGuard:
    def analyze(self, item: Dict[str, Any]) -> Dict[str, Any]:
        launch_target_kind = str(item.get("launch_target_kind", "missing")).strip().lower()
        candidate_kind = str(item.get("candidate_kind", "weak_missing_path")).strip().lower()
        platform = str(item.get("platform", "unknown")).strip() or "unknown"
        launch_target_raw = str(item.get("launch_target_raw", "")).strip()
        is_secondary = launch_target_kind in {"protocol", "launcher", "command"} or candidate_kind == "indirect_launcher"
        confidence = str(item.get("route_confidence", "")).strip().lower() or ("high" if launch_target_kind == "protocol" else "low")
        return {
            "is_secondary_route": is_secondary,
            "route_confidence": confidence,
            "platform": platform,
            "launch_target_raw": launch_target_raw,
            "launch_target_kind": launch_target_kind,
        }
