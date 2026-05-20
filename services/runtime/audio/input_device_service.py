from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any

import sounddevice as sd

from config import AUDIO_DEVICE_LOCAL_FILE  # type: ignore


class InputDeviceService:
    def __init__(self, config_path: str | Path | None = None):
        self.config_path = Path(config_path or AUDIO_DEVICE_LOCAL_FILE)

    def list_input_devices(self) -> list[dict[str, Any]]:
        return [
            self._device_payload(index, device, "input")
            for index, device in self._query_devices()
            if int(device.get("max_input_channels", 0) or 0) > 0
        ]

    def list_output_devices(self) -> list[dict[str, Any]]:
        return [
            self._device_payload(index, device, "output")
            for index, device in self._query_devices()
            if int(device.get("max_output_channels", 0) or 0) > 0
        ]

    def load_config(self) -> dict[str, Any]:
        data = self._read_json(self.config_path, {})
        return self._normalize_config(data)

    def save_config(self, config: dict[str, Any]) -> dict[str, Any]:
        normalized = self._normalize_config(config)
        normalized["updated_at"] = self._now_iso()
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self.config_path.write_text(
            json.dumps(normalized, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return normalized

    def set_input_device(self, device_index: int | None, device_name: str = "") -> dict[str, Any]:
        config = self.load_config()
        config["input"] = self._selected_device_config(device_index, device_name, "input")
        return self.save_config(config)

    def set_output_device(self, device_index: int | None, device_name: str = "") -> dict[str, Any]:
        config = self.load_config()
        config["output"] = self._selected_device_config(device_index, device_name, "output")
        return self.save_config(config)

    def resolve_input_device(self) -> dict[str, Any]:
        config = self.load_config().get("input", {})
        return self._resolve_device(config, "input")

    def resolve_output_device(self) -> dict[str, Any]:
        config = self.load_config().get("output", {})
        return self._resolve_device(config, "output")

    def reset_input_to_default(self) -> dict[str, Any]:
        config = self.load_config()
        config["input"] = self._default_device_config()
        return self.save_config(config)

    def reset_output_to_default(self) -> dict[str, Any]:
        config = self.load_config()
        config["output"] = self._default_device_config()
        return self.save_config(config)

    def _resolve_device(self, config: dict[str, Any], direction: str) -> dict[str, Any]:
        use_default = bool(config.get("use_system_default", True))
        if use_default:
            return {
                "resolved": True,
                "fallback": False,
                "use_system_default": True,
                "device_index": None,
                "device_name": "",
                "reason": "system_default",
            }

        saved_index = self._coerce_optional_int(config.get("device_index"))
        saved_name = str(config.get("device_name", "") or "").strip()
        devices = self.list_input_devices() if direction == "input" else self.list_output_devices()

        if saved_index is not None:
            for device in devices:
                if int(device.get("index", -1)) == saved_index:
                    return {
                        "resolved": True,
                        "fallback": False,
                        "use_system_default": False,
                        "device_index": saved_index,
                        "device_name": str(device.get("name", "") or saved_name),
                        "reason": "configured_index",
                    }

        if saved_name:
            matched = self._match_device_by_name(devices, saved_name)
            if matched:
                return {
                    "resolved": True,
                    "fallback": saved_index is not None,
                    "use_system_default": False,
                    "device_index": int(matched.get("index")),
                    "device_name": str(matched.get("name", "") or saved_name),
                    "reason": "configured_name_match",
                }

        return {
            "resolved": False,
            "fallback": True,
            "use_system_default": True,
            "device_index": None,
            "device_name": saved_name,
            "reason": "configured_device_missing_fallback_system_default",
        }

    def _query_devices(self) -> list[tuple[int, dict[str, Any]]]:
        try:
            devices = sd.query_devices()
        except Exception:
            return []

        result: list[tuple[int, dict[str, Any]]] = []
        for index, device in enumerate(devices):
            if isinstance(device, dict):
                result.append((index, device))
        return result

    def _device_payload(self, index: int, device: dict[str, Any], direction: str) -> dict[str, Any]:
        name = str(device.get("name", "") or f"Device {index}").strip()
        key = "max_input_channels" if direction == "input" else "max_output_channels"
        return {
            "index": int(index),
            "name": name,
            "display_name": name,
            key: int(device.get(key, 0) or 0),
            "default_samplerate": float(device.get("default_samplerate", 0.0) or 0.0),
        }

    def _selected_device_config(
        self,
        device_index: int | None,
        device_name: str,
        direction: str,
    ) -> dict[str, Any]:
        index = self._coerce_optional_int(device_index)
        if index is None:
            return self._default_device_config()

        name = str(device_name or "").strip()
        devices = self.list_input_devices() if direction == "input" else self.list_output_devices()
        for device in devices:
            if int(device.get("index", -1)) == index:
                name = name or str(device.get("name", "") or "")
                break

        return {
            "use_system_default": False,
            "device_index": index,
            "device_name": name,
        }

    def _match_device_by_name(
        self,
        devices: list[dict[str, Any]],
        device_name: str,
    ) -> dict[str, Any] | None:
        needle = self._normalize_device_name(device_name)
        if not needle:
            return None

        for device in devices:
            if self._normalize_device_name(str(device.get("name", "") or "")) == needle:
                return device

        for device in devices:
            haystack = self._normalize_device_name(str(device.get("name", "") or ""))
            if needle in haystack or haystack in needle:
                return device

        return None

    def _normalize_config(self, config: dict[str, Any] | None) -> dict[str, Any]:
        base = self._default_config()
        if isinstance(config, dict):
            merged = deepcopy(base)
            if isinstance(config.get("input"), dict):
                merged["input"].update(config.get("input", {}))
            if isinstance(config.get("output"), dict):
                merged["output"].update(config.get("output", {}))
            merged["schema_version"] = "audio_device_config_v1"
            merged["updated_at"] = str(config.get("updated_at", "") or "")
            return {
                "schema_version": merged["schema_version"],
                "input": self._normalize_device_config(merged.get("input")),
                "output": self._normalize_device_config(merged.get("output")),
                "updated_at": merged["updated_at"],
            }
        return base

    def _normalize_device_config(self, value: Any) -> dict[str, Any]:
        if not isinstance(value, dict):
            return self._default_device_config()
        use_default = bool(value.get("use_system_default", True))
        index = self._coerce_optional_int(value.get("device_index"))
        name = str(value.get("device_name", "") or "").strip()
        return {
            "use_system_default": use_default,
            "device_index": None if use_default else index,
            "device_name": "" if use_default else name,
        }

    def _default_config(self) -> dict[str, Any]:
        return {
            "schema_version": "audio_device_config_v1",
            "input": self._default_device_config(),
            "output": self._default_device_config(),
            "updated_at": "",
        }

    def _default_device_config(self) -> dict[str, Any]:
        return {
            "use_system_default": True,
            "device_index": None,
            "device_name": "",
        }

    def _read_json(self, path: Path, default: dict[str, Any]) -> dict[str, Any]:
        if not path.exists():
            return default
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else default
        except Exception:
            return default

    def _coerce_optional_int(self, value: Any) -> int | None:
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def _normalize_device_name(self, value: str) -> str:
        return "".join(str(value or "").lower().split())

    def _now_iso(self) -> str:
        return datetime.now().astimezone().isoformat(timespec="seconds")
