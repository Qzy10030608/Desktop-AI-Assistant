from __future__ import annotations

import re
from typing import Any, Dict


class ProtocolParser:
    def parse(self, raw_value: str) -> Dict[str, Any]:
        text = str(raw_value or "").strip()
        lowered = text.lower()
        result: Dict[str, Any] = {
            "platform": "unknown",
            "platform_object_type": "",
            "platform_object_id": "",
            "launch_target_kind": "missing",
            "launch_target_raw": text,
            "route_confidence": "low",
        }
        if not text:
            return result
        if lowered.startswith("http://") or lowered.startswith("https://"):
            result["launch_target_kind"] = "web_url"
            return result
        if re.match(r"^[a-z][a-z0-9+.-]*://", lowered):
            result["launch_target_kind"] = "protocol"
            result["route_confidence"] = "medium"
            if lowered.startswith("steam://"):
                result["platform"] = "steam"
                result["platform_object_type"] = "game" if "rungameid" in lowered else "client"
                match = re.search(r"rungameid/(\d+)", lowered)
                if match:
                    result["platform_object_id"] = match.group(1)
                    result["route_confidence"] = "high"
            elif lowered.startswith("com.epicgames.launcher://") or lowered.startswith("epic://"):
                result["platform"] = "epic"
                result["platform_object_type"] = "game"
            elif lowered.startswith("battlenet://"):
                result["platform"] = "battlenet"
                result["platform_object_type"] = "game"
            elif lowered.startswith("origin://") or lowered.startswith("ea://"):
                result["platform"] = "ea"
                result["platform_object_type"] = "game"
            return result
        return result
