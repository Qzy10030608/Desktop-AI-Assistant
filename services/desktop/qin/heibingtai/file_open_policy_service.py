from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class FileOpenPolicyService:
    """Read-only file open policy resolver for Heibingtai v3 planning."""

    def __init__(self, project_root: str | Path | None = None) -> None:
        self.project_root = Path(project_root or Path(__file__).resolve().parents[4]).expanduser().resolve()
        self.default_path = self.project_root / "data" / "defaults" / "desktop" / "file_open_policy.json"
        self.user_path = self.project_root / "data" / "user_prefs" / "desktop" / "file_open_policy.json"

    def get_policy_for_path(self, target_path: str) -> dict[str, Any]:
        return self.get_policy_for_key(self._suffix_key(target_path))

    def get_policy_for_key(self, key: str) -> dict[str, Any]:
        normalized_key = str(key or "").strip().lower() or "no_extension"
        defaults = self._read_json(self.default_path)
        user = self._read_json(self.user_path)

        default_rules = defaults.get("rules", {}) if isinstance(defaults.get("rules", {}), dict) else {}
        user_rules = user.get("rules", {}) if isinstance(user.get("rules", {}), dict) else {}

        base = default_rules.get(normalized_key, {})
        override = user_rules.get(normalized_key, {})
        if not isinstance(base, dict):
            base = {}
        if not isinstance(override, dict):
            override = {}

        merged: dict[str, Any] = {
            "extension_key": normalized_key,
            "preferred_app_kind": "",
            "fallback_app_kinds": [],
            "open_mode": "windows_default_allowed",
            "close_adapter": "default_app",
            "allow_windows_default": True,
            "requires_user_choice": False,
        }
        merged.update(base)
        merged.update(override)

        merged["extension_key"] = normalized_key
        merged["preferred_app_kind"] = str(merged.get("preferred_app_kind", "") or "").strip().lower()
        merged["fallback_app_kinds"] = [
            str(item or "").strip().lower()
            for item in (merged.get("fallback_app_kinds", []) or [])
            if str(item or "").strip()
        ]
        merged["open_mode"] = str(merged.get("open_mode", "") or "").strip().lower()
        merged["close_adapter"] = str(merged.get("close_adapter", "") or "").strip().lower()
        merged["allow_windows_default"] = bool(merged.get("allow_windows_default", False))
        merged["requires_user_choice"] = bool(merged.get("requires_user_choice", False))
        return merged

    def list_rules(self) -> dict[str, dict[str, Any]]:
        defaults = self._read_json(self.default_path)
        user = self._read_json(self.user_path)
        default_rules = defaults.get("rules", {}) if isinstance(defaults.get("rules", {}), dict) else {}
        user_rules = user.get("rules", {}) if isinstance(user.get("rules", {}), dict) else {}

        result: dict[str, dict[str, Any]] = {}
        for key in sorted(set(default_rules.keys()) | set(user_rules.keys())):
            result[str(key)] = self.get_policy_for_key(str(key))
        return result

    def has_user_rule_for_key(self, key: str) -> bool:
        normalized_key = str(key or "").strip().lower() or "no_extension"
        user = self._read_json(self.user_path)
        user_rules = user.get("rules", {}) if isinstance(user.get("rules", {}), dict) else {}
        return normalized_key in user_rules and isinstance(user_rules.get(normalized_key), dict)

    def _suffix_key(self, target_path: str) -> str:
        name = Path(str(target_path or "")).name
        suffix = Path(name).suffix.lower()
        return suffix if suffix else "no_extension"

    def _read_json(self, path: Path) -> dict[str, Any]:
        if not path.exists():
            return {}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}
        return data if isinstance(data, dict) else {}
