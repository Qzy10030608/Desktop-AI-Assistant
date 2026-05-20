from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class SoftwareVisibilityPolicy:
    """Keep system and diagnostic entries out of the main software UI."""

    HIDDEN_CATEGORIES = {
        "admin_tool",
        "runtime_env",
        "driver_or_runtime",
        "installer_bundle",
        "system_core",
        "diagnostics_only",
        "driver",
    }
    HIDDEN_CANDIDATE_KINDS = {
        "admin_tool",
        "runtime_env",
        "driver_or_runtime",
        "installer_bundle",
        "system_core",
        "diagnostics_only",
    }
    HIDDEN_PATH_STATUSES = {
        "driver_or_runtime",
        "installer_bundle",
        "registry_residual",
        "system_core",
        "diagnostics_only",
    }
    SYSTEM_TOOL_NAMES = {
        "odbc",
        "odbc data sources",
        "iscsi",
        "iscsi initiator",
        "disk cleanup",
        "cleanmgr",
        "system configuration",
        "msconfig",
        "system information",
        "msinfo32",
        "steps recorder",
        "psr",
        "character map",
        "charmap",
        "magnify",
        "magnifier",
        "livecaptions",
        "live captions",
    }

    def should_hide(self, item: dict[str, Any]) -> tuple[bool, str]:
        if not isinstance(item, dict):
            return False, ""

        category = self._value(item, "category")
        candidate_kind = self._value(item, "candidate_kind")
        path_status = self._value(item, "path_status")
        title = self._value(item, "title", "name", "app_id")
        publisher = self._value(item, "publisher")
        platform = self._value(item, "platform")
        platform_type = self._value(item, "platform_object_type")
        launch_kind = self._value(item, "launch_target_kind", "effective_launch_target_kind")

        if category in self.HIDDEN_CATEGORIES:
            return True, f"category:{category}"
        if candidate_kind in self.HIDDEN_CANDIDATE_KINDS:
            return True, f"candidate_kind:{candidate_kind}"
        if path_status in self.HIDDEN_PATH_STATUSES:
            return True, f"path_status:{path_status}"

        path_text = self._combined_paths(item)
        normalized_path = path_text.replace("/", "\\").lower()
        if "\\windows\\system32\\" in normalized_path or "\\windows\\syswow64\\" in normalized_path:
            return True, "windows_system_path"

        haystack = " ".join([title, publisher, path_text]).lower()
        if any(token in haystack for token in self.SYSTEM_TOOL_NAMES):
            return True, "known_system_tool"

        if "nvidia" in haystack and any(token in haystack for token in ("nsight", "sdk", "monitor", "runtime")):
            return True, "nvidia_tooling_or_runtime"

        if (
            platform in {"steam", "epic", "battle_net", "battlenet", "ea", "ubisoft"}
            or platform_type in {"steam_app", "game", "platform_game"}
            or launch_kind in {"protocol", "launcher"}
        ):
            return False, ""

        return False, ""

    def filter_rows(self, rows: list[Any]) -> tuple[list[Any], list[dict[str, str]]]:
        visible: list[Any] = []
        hidden: list[dict[str, str]] = []
        for row in rows:
            if not isinstance(row, dict):
                visible.append(row)
                continue
            should_hide, reason = self.should_hide(row)
            if should_hide:
                hidden.append({
                    "app_id": str(row.get("app_id", "") or ""),
                    "title": str(row.get("title", row.get("name", "")) or ""),
                    "reason": reason,
                })
                continue
            visible.append(row)
        return visible, hidden

    def _value(self, item: dict[str, Any], *keys: str) -> str:
        for key in keys:
            value = str(item.get(key, "") or "").strip().lower()
            if value:
                return value
        return ""

    def _combined_paths(self, item: dict[str, Any]) -> str:
        keys = (
            "target_path",
            "effective_target_path",
            "launch_target_raw",
            "effective_launch_target_raw",
            "entry_path",
            "install_dir",
            "icon_source_path",
        )
        return " ".join(str(item.get(key, "") or "").strip() for key in keys if str(item.get(key, "") or "").strip())


class SoftwareViewCacheService:
    """
    软件治理区 UI 缓存。

    这个缓存保存的是已经适合 UI 显示的最终 state：
    - 不是原始扫描结果
    - 不是 candidates 原始数据
    - 是 get_software_governance_state() 生成后的 rows / counts / source

    目的：
    - 下次打开桌面连接页时直接显示上次软件表
    - 不需要重新扫描
    - 不需要重新 merge candidates
    """

    def __init__(self, project_root: str | Path | None = None) -> None:
        self.project_root = Path(project_root or Path.cwd())
        self.cache_path = self.project_root / "data" / "runtime" / "desktop" / "software_view_cache.json"
        self.visibility_policy = SoftwareVisibilityPolicy()

    def exists(self) -> bool:
        return self.cache_path.exists()

    def read(self) -> dict[str, Any]:
        if not self.cache_path.exists():
            return self.empty_state()

        try:
            data = json.loads(self.cache_path.read_text(encoding="utf-8"))
        except Exception:
            return self.empty_state()

        if not isinstance(data, dict):
            return self.empty_state()

        rows = data.get("rows", [])
        if not isinstance(rows, list):
            rows = []

        visible_rows, hidden_by_policy = self.visibility_policy.filter_rows(rows)
        hidden_count = int(data.get("hidden_count", 0) or 0) + len(hidden_by_policy)
        diagnostics = data.get("diagnostics", {}) if isinstance(data.get("diagnostics", {}), dict) else {}
        if hidden_by_policy:
            diagnostics = dict(diagnostics)
            diagnostics["visibility_policy_hidden_count"] = int(
                diagnostics.get("visibility_policy_hidden_count", 0) or 0
            ) + len(hidden_by_policy)
            diagnostics["visibility_policy_hidden"] = hidden_by_policy[:50]

        return {
            "ok": bool(data.get("ok", True)),
            "source": str(data.get("source", "cache") or "cache"),
            "generated_at": str(data.get("generated_at", "") or ""),
            "scan_profile": str(data.get("scan_profile", "") or ""),
            "discovered_count": int(data.get("discovered_count", len(visible_rows)) or 0),
            "trusted_count": int(data.get("trusted_count", data.get("confirmed_count", 0)) or 0),
            "confirmed_count": int(data.get("confirmed_count", data.get("trusted_count", 0)) or 0),
            "hidden_count": hidden_count,
            "read_only": bool(data.get("read_only", True)),
            "rows": visible_rows,
            "diagnostics": diagnostics,
        }

    def write(self, state: dict[str, Any], *, scan_profile: str = "", source: str = "cache") -> dict[str, Any]:
        rows = state.get("rows", []) if isinstance(state.get("rows", []), list) else []
        visible_rows, hidden_by_policy = self.visibility_policy.filter_rows(rows)
        diagnostics = state.get("diagnostics", {}) if isinstance(state.get("diagnostics", {}), dict) else {}
        if hidden_by_policy:
            diagnostics = dict(diagnostics)
            diagnostics["visibility_policy_hidden_count"] = int(
                diagnostics.get("visibility_policy_hidden_count", 0) or 0
            ) + len(hidden_by_policy)
            diagnostics["visibility_policy_hidden"] = hidden_by_policy[:50]

        payload = {
            "ok": True,
            "source": source or "cache",
            "generated_at": str(state.get("generated_at", "") or ""),
            "scan_profile": scan_profile,
            "discovered_count": int(state.get("discovered_count", len(visible_rows)) or len(visible_rows)),
            "trusted_count": int(state.get("trusted_count", state.get("confirmed_count", 0)) or 0),
            "confirmed_count": int(state.get("confirmed_count", state.get("trusted_count", 0)) or 0),
            "hidden_count": int(state.get("hidden_count", 0) or 0) + len(hidden_by_policy),
            "read_only": bool(state.get("read_only", True)),
            "rows": visible_rows,
            "diagnostics": diagnostics,
        }

        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.cache_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return payload

    def update_row_permission(self, app_id: str, patch: dict[str, Any]) -> dict[str, Any]:
        """
        只更新 software_view_cache.json 中某一个软件行的权限显示和能力字段。

        注意：
        - 不重新扫描
        - 不重新 merge
        - 不改变 rows 顺序
        - 不清空 cache
        """
        normalized_app_id = str(app_id or "").strip()
        if not normalized_app_id:
            return self.read()

        state = self.read()
        rows = state.get("rows", [])
        if not isinstance(rows, list):
            rows = []

        updated_rows: list[Any] = []
        matched = False

        for row in rows:
            if not isinstance(row, dict):
                updated_rows.append(row)
                continue

            if str(row.get("app_id", "") or "").strip() != normalized_app_id:
                updated_rows.append(row)
                continue

            next_row = dict(row)
            next_row.update(dict(patch or {}))
            updated_rows.append(next_row)
            matched = True

        if not matched:
            return state

        state["rows"] = updated_rows
        return self.write(
            state,
            scan_profile=str(state.get("scan_profile", "") or ""),
            source=str(state.get("source", "cache") or "cache"),
        )

    def empty_state(self) -> dict[str, Any]:
        return {
            "ok": False,
            "source": "empty",
            "generated_at": "",
            "scan_profile": "",
            "discovered_count": 0,
            "trusted_count": 0,
            "confirmed_count": 0,
            "hidden_count": 0,
            "read_only": True,
            "rows": [],
            "diagnostics": {},
        }

    def clear(self) -> None:
        try:
            self.cache_path.unlink()
        except FileNotFoundError:
            return
