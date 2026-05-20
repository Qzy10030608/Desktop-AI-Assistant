from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List

from bootstrap.hundun.bind import bind_tokens
from bootstrap.hundun.load import ensure_local_data_files
from bootstrap.hundun.path import collect_machine_paths
from bootstrap.hundun.seed import load_defaults
from services.desktop.desktop_models import now_iso
from services.desktop.software_discovery_service import SoftwareDiscoveryService
from services.desktop.software_models import SoftwareRecord
from services.desktop.software_view_cache_service import SoftwareVisibilityPolicy
from services.desktop.software_view_model_service import SoftwareViewModelService
from services.desktop.tianting.providers.protocol_parser import ProtocolParser
from services.desktop.qin.liyi.permission_rules import (
    PERMISSION_COLORS as QIN_PERMISSION_COLORS,
    PERMISSION_LABELS as QIN_PERMISSION_LABELS,
    PERMISSION_ORDER as QIN_PERMISSION_ORDER,
    PermissionState,
    next_permission_state,
    normalize_permission_state,
)
from services.desktop.qin.libu.software_ledger import (
    SoftwareCandidateBook,
    SoftwareHiddenBook,
    SoftwareMergeService,
    SoftwareTrustedBook,
)
from services.desktop.qin.menxia.review_policy import get_review_policy
from services.desktop.tiandi.mode_store import ModeStore

PERMISSION_ORDER = QIN_PERMISSION_ORDER
PERMISSION_LABELS = QIN_PERMISSION_LABELS
PERMISSION_COLORS = QIN_PERMISSION_COLORS

FILTER_TO_PERMISSION = {
    "all": None,
    "allow": "allow",
    "deny": "deny",
    "unset": "unset",
    "once": "once",
}


class DesktopWhitelistService:
    def __init__(self, project_root: str | Path | None = None) -> None:
        self.project_root = Path(project_root or Path(__file__).resolve().parents[2])
        self.user_prefs_dir = self.project_root / "data" / "user_prefs"
        self.user_prefs_dir.mkdir(parents=True, exist_ok=True)
        self.mode_store = ModeStore(self.project_root)
        self.software_discovery_service = SoftwareDiscoveryService(self.project_root)
        self.software_candidate_book = SoftwareCandidateBook(self.project_root)
        self.software_trusted_book = SoftwareTrustedBook(self.project_root)
        self.software_hidden_book = SoftwareHiddenBook(self.project_root)
        self.software_merge_service = SoftwareMergeService()
        self.software_view_model_service = SoftwareViewModelService()
        self.software_visibility_policy = SoftwareVisibilityPolicy()
        self.protocol_parser = ProtocolParser()

    def _path(self, name: str) -> Path:
        mapping = {
            "mode": self.user_prefs_dir / "desktop_mode.local.json",
            "roots": self.user_prefs_dir / "roots.local.json",
            "disks": self.user_prefs_dir / "disks.local.json",
            "apps": self.user_prefs_dir / "apps.local.json",
            "apps_candidates": self.user_prefs_dir / "apps.candidates.local.json",
            "install": self.user_prefs_dir / "install.local.json",
            "file_actions": self.user_prefs_dir / "file_actions.local.json",
        }
        return mapping[name]

    def _read_json(self, path: Path, default: Dict[str, Any]) -> Dict[str, Any]:
        if not path.exists():
            return default
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else default
        except Exception:
            return default

    def _write_json(self, path: Path, data: Dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def _normalize_path(self, raw_path: str) -> str:
        if raw_path is None:
            return ""
        text = str(raw_path or "").strip()
        if text.lower() == "none":
            return ""
        if not text:
            return ""
        lower = text.lower()
        if lower.startswith(
            (
                "shell:",
                "steam://",
                "http://",
                "https://",
                "ms-settings:",
                "microsoft-edge:",
                "calculator:",
                "appx:",
            )
        ):
            return ""
        try:
            return str(Path(text).expanduser().resolve(strict=False))
        except Exception:
            return text

    def _normalize_text(self, raw_value: Any, default: str = "") -> str:
        if raw_value is None:
            return default
        text = str(raw_value or "").strip()
        if text.lower() == "none":
            return default
        return text or default

    def _permission_state_from_item(self, item: Dict[str, Any]) -> str:
        raw = str(item.get("permission_state", "")).strip().lower()
        if raw in PERMISSION_ORDER:
            return raw

        enabled = item.get("enabled")
        allow_launch = item.get("allow_launch")
        if enabled is True and allow_launch is True:
            return "allow"
        if enabled is False and allow_launch is False:
            return "deny"
        return "unset"

    def _disk_permission_state_from_item(self, item: Dict[str, Any]) -> PermissionState:
        return self._typed_permission_state(str(item.get("permission_state", "unset")).strip().lower() or "unset")

    def _typed_permission_state(self, value: str | None) -> PermissionState:
        return normalize_permission_state(value)

    def _apply_permission_state(self, item: Dict[str, Any], permission_state: str) -> Dict[str, Any]:
        normalized = dict(item)
        normalized["permission_state"] = permission_state
        if permission_state == "allow":
            normalized["enabled"] = True
            normalized["allow_launch"] = True
        elif permission_state == "deny":
            normalized["enabled"] = False
            normalized["allow_launch"] = False
        elif permission_state == "once":
            normalized["enabled"] = True
            normalized["allow_launch"] = True
        else:
            normalized["enabled"] = False
            normalized["allow_launch"] = False
        return normalized

    def _normalize_root(self, item: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "root_id": str(item.get("root_id", "")).strip(),
            "title": str(item.get("title", item.get("root_id", ""))).strip(),
            "path": self._normalize_path(str(item.get("path", ""))),
            "enabled": bool(item.get("enabled", True)),
            "index_enabled": bool(item.get("index_enabled", True)),
            "allow_search": bool(item.get("allow_search", True)),
            "allow_open_file": bool(item.get("allow_open_file", True)),
            "allow_open_folder": bool(item.get("allow_open_folder", True)),
            "allow_read_meta": bool(item.get("allow_read_meta", True)),
        }

    def _normalize_disk(self, item: Dict[str, Any]) -> Dict[str, Any]:
        permission_state = self._disk_permission_state_from_item(item)
        disk_id = str(item.get("disk_id", item.get("title", ""))).strip().upper()
        return {
            "disk_id": disk_id,
            "title": str(item.get("title", disk_id)).strip() or disk_id,
            "permission_state": permission_state,
            "allow_expand": bool(item.get("allow_expand", False)),
            "allow_scan": bool(item.get("allow_scan", False)),
            "allow_index": bool(item.get("allow_index", False)),
            "updated_at": str(item.get("updated_at", now_iso())).strip() or now_iso(),
        }

    def _normalize_app(self, item: Dict[str, Any], *, source: str, builtin: bool = False) -> Dict[str, Any]:
        normalized = {
            "app_id": str(item.get("app_id", "")).strip(),
            "canonical_app_id": self._normalize_text(item.get("canonical_app_id", "")),
            "title": str(item.get("title", item.get("app_id", ""))).strip(),
            "target_path": self._normalize_path(str(item.get("target_path", ""))),
            "launch_target_kind": self._normalize_text(item.get("launch_target_kind", "missing"), "missing"),
            "launch_target_raw": self._normalize_text(item.get("launch_target_raw", "")),
            "launch_args": list(item.get("launch_args", []) or []),
            "enabled": bool(item.get("enabled", False)),
            "allow_launch": bool(item.get("allow_launch", False)),
            "allow_attach": bool(item.get("allow_attach", False)),
            "allow_close": bool(item.get("allow_close", False)),
            "connector_id": self._normalize_text(item.get("connector_id", "windows_shell"), "windows_shell"),
            "permission_state": self._permission_state_from_item(item),
            "source": source,
            "builtin": builtin,
            "discover_source": self._normalize_text(item.get("discover_source", "unknown"), "unknown"),
            "category": self._normalize_text(item.get("category", "unknown"), "unknown"),
            "discovered": bool(item.get("discovered", bool(item.get("target_path", "") or item.get("manual_target_path", "") or item.get("manual_launch_target_raw", "")))),
            "candidate_kind": self._normalize_text(item.get("candidate_kind", "normal_app" if item.get("target_path") else "weak_missing_path"), "weak_missing_path"),
            "candidate_strength": self._normalize_text(item.get("candidate_strength", "strong" if item.get("target_path") else "weak"), "weak"),
            "path_status": self._normalize_text(item.get("path_status", "resolved" if item.get("target_path") else "missing"), "missing"),
            "visibility_reason": self._normalize_text(item.get("visibility_reason", "")),
            "risk_hint": self._normalize_text(item.get("risk_hint", "")),
            "sensitivity": self._normalize_text(item.get("sensitivity", "")),
            "publisher": self._normalize_text(item.get("publisher", "")),
            "version": self._normalize_text(item.get("version", "")),
            "uninstall_string": self._normalize_text(item.get("uninstall_string", "")),
            "registry_key": self._normalize_text(item.get("registry_key", "")),
            "source_detail": self._normalize_text(item.get("source_detail", "")),
            "identity_source": self._normalize_text(item.get("identity_source", "")),
            "launch_source": self._normalize_text(item.get("launch_source", "")),
            "registry_entry_status": self._normalize_text(item.get("registry_entry_status", "")),
            "platform": self._normalize_text(item.get("platform", "unknown"), "unknown"),
            "platform_object_type": self._normalize_text(item.get("platform_object_type", "")),
            "platform_object_id": self._normalize_text(item.get("platform_object_id", "")),
            "install_dir": self._normalize_path(str(item.get("install_dir", ""))),
            "entry_path": self._normalize_path(str(item.get("entry_path", ""))),
            "icon_source_path": self._normalize_path(str(item.get("icon_source_path", ""))),
            "icon_kind": self._normalize_text(item.get("icon_kind", "missing"), "missing"),
            "route_confidence": self._normalize_text(item.get("route_confidence", "low"), "low"),
            "manual_bound": bool(item.get("manual_bound", False)),
            "manual_target_path": self._normalize_path(str(item.get("manual_target_path", ""))),
            "manual_launch_target_kind": self._normalize_text(item.get("manual_launch_target_kind", "missing"), "missing"),
            "manual_launch_target_raw": self._normalize_text(item.get("manual_launch_target_raw", "")),
            "manual_entry_path": self._normalize_path(str(item.get("manual_entry_path", ""))),
            "bind_source": self._normalize_text(item.get("bind_source", "")),
            "bound_at": self._normalize_text(item.get("bound_at", "")),
        }
        return normalized

    def _serialize_app(self, item: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "app_id": item["app_id"],
            "canonical_app_id": item.get("canonical_app_id", ""),
            "title": item["title"],
            "target_path": item.get("target_path", ""),
            "launch_target_kind": item.get("launch_target_kind", "missing"),
            "launch_target_raw": item.get("launch_target_raw", ""),
            "launch_args": list(item.get("launch_args", []) or []),
            "enabled": bool(item.get("enabled", False)),
            "allow_launch": bool(item.get("allow_launch", False)),
            "allow_attach": bool(item.get("allow_attach", False)),
            "allow_close": bool(item.get("allow_close", False)),
            "connector_id": item.get("connector_id", "windows_shell"),
            "permission_state": item.get("permission_state", "unset"),
            "category": item.get("category", "unknown"),
            "candidate_kind": item.get("candidate_kind", "normal_app" if item.get("target_path") else "weak_missing_path"),
            "candidate_strength": item.get("candidate_strength", "strong" if item.get("target_path") else "weak"),
            "path_status": item.get("path_status", "resolved" if item.get("target_path") else "missing"),
            "platform": item.get("platform", "unknown"),
            "platform_object_type": item.get("platform_object_type", ""),
            "platform_object_id": item.get("platform_object_id", ""),
            "install_dir": item.get("install_dir", ""),
            "entry_path": item.get("entry_path", ""),
            "icon_source_path": item.get("icon_source_path", ""),
            "icon_kind": item.get("icon_kind", "missing"),
            "route_confidence": item.get("route_confidence", "low"),
            "visibility_reason": item.get("visibility_reason", ""),
            "risk_hint": item.get("risk_hint", ""),
            "sensitivity": item.get("sensitivity", ""),
            "publisher": item.get("publisher", ""),
            "version": item.get("version", ""),
            "uninstall_string": item.get("uninstall_string", ""),
            "registry_key": item.get("registry_key", ""),
            "source_detail": item.get("source_detail", ""),
            "identity_source": item.get("identity_source", ""),
            "launch_source": item.get("launch_source", ""),
            "registry_entry_status": item.get("registry_entry_status", ""),
            "manual_bound": bool(item.get("manual_bound", False)),
            "manual_target_path": item.get("manual_target_path", ""),
            "manual_launch_target_kind": item.get("manual_launch_target_kind", "missing"),
            "manual_launch_target_raw": item.get("manual_launch_target_raw", ""),
            "manual_entry_path": item.get("manual_entry_path", ""),
            "bind_source": item.get("bind_source", ""),
            "bound_at": item.get("bound_at", ""),
        }

    def _serialize_candidate(self, item: Dict[str, Any]) -> Dict[str, Any]:
        data = self._serialize_app(item)
        data["discovered"] = bool(item.get("target_path") or item.get("manual_target_path") or item.get("manual_launch_target_raw"))
        data["discover_source"] = item.get("discover_source", "filesystem_scan" if item.get("target_path") else "not_found")
        data["category"] = item.get("category", "unknown")
        data["launch_target_kind"] = item.get("launch_target_kind", "missing")
        data["launch_target_raw"] = item.get("launch_target_raw", "")
        data["candidate_kind"] = item.get("candidate_kind", "normal_app" if item.get("target_path") else "weak_missing_path")
        data["candidate_strength"] = item.get("candidate_strength", "strong" if item.get("target_path") else "weak")
        data["path_status"] = item.get("path_status", "resolved" if item.get("target_path") else "missing")
        data["visibility_reason"] = item.get("visibility_reason", "")
        return data

    def _apply_manual_binding(self, item: Dict[str, Any], selected_path: str) -> Dict[str, Any]:
        normalized_path = self._normalize_path(selected_path)
        suffix = Path(normalized_path).suffix.lower()
        updated = dict(item)
        updated["manual_bound"] = True
        updated["bind_source"] = "manual_pick"
        updated["bound_at"] = now_iso()
        updated["manual_target_path"] = ""
        updated["manual_launch_target_kind"] = "missing"
        updated["manual_launch_target_raw"] = ""
        updated["manual_entry_path"] = ""

        if suffix == ".exe":
            updated["manual_target_path"] = normalized_path
            updated["manual_entry_path"] = normalized_path
            updated["manual_launch_target_kind"] = "local_exe"
            updated["candidate_kind"] = "normal_app"
            updated["candidate_strength"] = "strong"
            updated["path_status"] = "resolved"
            updated["icon_source_path"] = normalized_path
            updated["icon_kind"] = "exe"
            updated["visibility_reason"] = "手动补充了本地可执行路径。"
            return updated

        if suffix == ".lnk":
            updated["manual_target_path"] = normalized_path
            updated["manual_entry_path"] = normalized_path
            updated["manual_launch_target_kind"] = "launcher"
            updated["candidate_kind"] = "indirect_launcher"
            updated["candidate_strength"] = "strong"
            updated["path_status"] = "indirect"
            updated["icon_source_path"] = normalized_path
            updated["icon_kind"] = "launcher"
            updated["visibility_reason"] = "手动补充了本地启动器入口。"
            return updated

        if suffix == ".url":
            url_value = ""
            try:
                for line in Path(normalized_path).read_text(encoding="utf-8", errors="ignore").splitlines():
                    if line.strip().lower().startswith("url="):
                        url_value = line.split("=", 1)[1].strip()
                        break
            except Exception:
                url_value = ""
            parsed = self.protocol_parser.parse(url_value) if url_value else None
            updated["manual_entry_path"] = normalized_path
            updated["manual_launch_target_raw"] = url_value
            updated["manual_launch_target_kind"] = str((parsed or {}).get("launch_target_kind", "missing"))
            if parsed and str(parsed.get("launch_target_kind", "")).strip().lower() == "protocol":
                updated["candidate_kind"] = "indirect_launcher"
                updated["candidate_strength"] = "strong"
                updated["path_status"] = "indirect"
                updated["platform"] = str(parsed.get("platform", updated.get("platform", "unknown"))).strip() or "unknown"
                updated["platform_object_id"] = str(parsed.get("platform_object_id", updated.get("platform_object_id", ""))).strip()
                updated["route_confidence"] = "medium"
                updated["visibility_reason"] = "手动补充了平台协议入口。"
            else:
                updated["candidate_kind"] = "weak_missing_path"
                updated["candidate_strength"] = "weak"
                updated["path_status"] = "missing"
                updated["visibility_reason"] = "已记录手动绑定尝试，但当前入口仍不可用于软件动作。"
            return updated

        updated["visibility_reason"] = "暂不支持该类型的手动绑定。"
        return updated

    def _load_defaults(self) -> Dict[str, Dict[str, Any]]:
        return load_defaults(self.project_root)

    def _builtin_apps(self) -> List[Dict[str, Any]]:
        defaults = self._load_defaults()
        result: List[Dict[str, Any]] = []
        for item in defaults.get("app_map", {}).get("apps", []) or []:
            if not isinstance(item, dict):
                continue
            result.append(self._normalize_app(item, source="builtin", builtin=True))
        return result

    def _builtin_app_ids(self) -> set[str]:
        return {item["app_id"] for item in self._builtin_apps() if item.get("app_id")}

    def _read_roots(self) -> List[Dict[str, Any]]:
        roots = self._read_json(self._path("roots"), {"roots": []}).get("roots", []) or []
        return [self._normalize_root(item) for item in roots if isinstance(item, dict)]

    def _write_roots(self, roots: Iterable[Dict[str, Any]]) -> None:
        self._write_json(self._path("roots"), {"roots": [self._normalize_root(item) for item in roots]})

    def _default_disks(self) -> List[Dict[str, Any]]:
        return [
            self._normalize_disk(
                {
                    "disk_id": self._drive_key(drive),
                    "title": self._drive_key(drive) or str(drive),
                    "permission_state": "unset",
                    "allow_expand": False,
                    "allow_scan": False,
                    "allow_index": False,
                    "updated_at": now_iso(),
                }
            )
            for drive in self._list_windows_drives()
        ]

    def _read_disks(self) -> List[Dict[str, Any]]:
        disks = self._read_json(self._path("disks"), {"disks": []}).get("disks", []) or []
        existing = {
            str(item.get("disk_id", "")).strip().upper(): self._normalize_disk(item)
            for item in disks
            if isinstance(item, dict) and str(item.get("disk_id", "")).strip()
        }
        merged: List[Dict[str, Any]] = []
        for default_item in self._default_disks():
            disk_id = default_item["disk_id"]
            merged.append(existing.get(disk_id, default_item))
        return merged

    def _write_disks(self, disks: Iterable[Dict[str, Any]]) -> None:
        self._write_json(self._path("disks"), {"disks": [self._normalize_disk(item) for item in disks]})

    def _read_confirmed_apps(self) -> List[Dict[str, Any]]:
        return [self._normalize_app(item.to_dict(), source="confirmed", builtin=False) for item in self.software_trusted_book.read()]

    def _write_confirmed_apps(self, apps: Iterable[Dict[str, Any]]) -> None:
        records: List[SoftwareRecord] = []
        for item in apps:
            if not item.get("app_id"):
                continue
            records.append(SoftwareRecord.from_dict(self._serialize_app(item)))
        self.software_trusted_book.write(records)

    def _read_candidate_apps(self) -> List[Dict[str, Any]]:
        return [self._normalize_app(item.to_dict(), source="candidate", builtin=False) for item in self.software_candidate_book.read()]

    def _write_candidate_apps(self, apps: Iterable[Dict[str, Any]]) -> None:
        records: List[SoftwareRecord] = []
        for item in apps:
            if not item.get("app_id"):
                continue
            records.append(SoftwareRecord.from_dict(self._serialize_candidate(item)))
        self.software_candidate_book.write(records)

    def _write_software_scan_diagnostics(self, diagnostics: Dict[str, Any]) -> None:
        path = self.project_root / "data" / "runtime" / "desktop" / "software_scan_diagnostics.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(diagnostics, ensure_ascii=False, indent=2), encoding="utf-8")

    def _software_scan_diagnostics_path(self) -> Path:
        return self.project_root / "data" / "runtime" / "desktop" / "software_scan_diagnostics.json"

    def _print_software_scan_summary(self, diagnostics: Dict[str, Any], candidates: List[Dict[str, Any]]) -> None:
        candidate_path = self._path("apps_candidates")
        diagnostics_path = self._software_scan_diagnostics_path()
        source_stats = diagnostics.get("sources", {}) if isinstance(diagnostics, dict) else {}
        pipeline = diagnostics.get("pipeline", {}) if isinstance(diagnostics, dict) else {}
        counts = diagnostics.get("candidates", {}) if isinstance(diagnostics, dict) else {}

        print("", flush=True)
        print("[desktop software scan] completed", flush=True)
        print(f"[desktop software scan] candidates file: {candidate_path}", flush=True)
        print(f"[desktop software scan] diagnostics file: {diagnostics_path}", flush=True)
        print(
            "[desktop software scan] totals: "
            f"raw={pipeline.get('raw_total', 0)} "
            f"filtered={pipeline.get('filter_after_total', 0)} "
            f"deduped={pipeline.get('dedupe_after_total', 0)} "
            f"strong={counts.get('strong_candidate_count', 0)} "
            f"weak={counts.get('weak_candidate_count', 0)} "
            f"written={counts.get('final_written_count', 0)} "
            f"duration_ms={diagnostics.get('duration_ms', '-')}",
            flush=True,
        )
        for source_name, stats in source_stats.items():
            print(
                "[desktop software scan] source "
                f"{source_name}: total={stats.get('total', 0)} "
                f"duration_ms={stats.get('duration_ms', '-')} "
                f"with_path={stats.get('with_path', 0)} "
                f"no_path={stats.get('no_path', 0)}",
                flush=True,
            )

        sample = candidates[:12]
        if sample:
            print("[desktop software scan] sample candidates:", flush=True)
            for index, item in enumerate(sample, start=1):
                title = str(item.get("title", "-")).strip() or "-"
                strength = str(item.get("candidate_strength", "-")).strip() or "-"
                source = str(item.get("discover_source", "-")).strip() or "-"
                path_text = str(item.get("target_path", "")).strip() or "路径缺失"
                print(
                    f"  {index:02d}. [{strength}] {title} | {source} | {path_text}",
                    flush=True,
                )
        else:
            print("[desktop software scan] sample candidates: none", flush=True)
        print("", flush=True)

    def _emit_scan_progress(
        self,
        callback: Callable[[dict[str, Any]], None] | None,
        *,
        stage: str,
        message: str,
        stats: dict[str, Any] | None = None,
        percent: int | None = None,
    ) -> None:
        print(f"[desktop software scan] {message}", flush=True)
        if callback is None:
            return
        callback(
            {
                "stage": stage,
                "message": message,
                "stats": dict(stats or {}),
                "percent": percent,
            }
        )

    def _read_install(self) -> Dict[str, Any]:
        defaults = self._load_defaults()
        return self._read_json(
            self._path("install"),
            {
                "initialized": False,
                "init_version": int(defaults.get("init_seed", {}).get("init_version", 1) or 1),
            },
        )

    def _write_install(self, install: Dict[str, Any]) -> None:
        defaults = self._load_defaults()
        normalized = {
            "initialized": bool(install.get("initialized", False)),
            "init_version": int(install.get("init_version", defaults.get("init_seed", {}).get("init_version", 1)) or 1),
            "generated_at": str(install.get("generated_at", now_iso())).strip() or now_iso(),
        }
        self._write_json(self._path("install"), normalized)

    def _read_file_actions(self) -> Dict[str, Any]:
        return self._read_json(self._path("file_actions"), {"disks": {}})

    def _write_file_actions(self, disks: Dict[str, bool]) -> None:
        normalized = {
            str(key).strip().upper(): bool(value)
            for key, value in disks.items()
            if str(key).strip()
        }
        self._write_json(
            self._path("file_actions"),
            {
                "disks": normalized,
                "updated_at": now_iso(),
            },
        )

    def get_disk_file_actions_enabled(self, disk_id: str) -> bool:
        normalized = str(disk_id or "").strip().upper()
        if not normalized:
            return False
        data = self._read_file_actions()
        disks = data.get("disks", {}) if isinstance(data.get("disks", {}), dict) else {}
        return bool(disks.get(normalized, False))

    def set_disk_file_actions_enabled(self, disk_id: str, value: bool) -> bool:
        normalized = str(disk_id or "").strip().upper()
        if not normalized:
            raise ValueError("缺少 disk_id")
        enabled = bool(value)
        data = self._read_file_actions()
        disks = data.get("disks", {}) if isinstance(data.get("disks", {}), dict) else {}
        next_disks = {
            str(key).strip().upper(): bool(item)
            for key, item in disks.items()
            if str(key).strip()
        }
        next_disks[normalized] = enabled
        self._write_file_actions(next_disks)
        return enabled

    def toggle_disk_file_actions_enabled(self, disk_id: str) -> bool:
        return self.set_disk_file_actions_enabled(
            disk_id,
            not self.get_disk_file_actions_enabled(disk_id),
        )

    def _mark_initialized(self) -> None:
        install = self._read_install()
        install["initialized"] = True
        install["generated_at"] = now_iso()
        self._write_install(install)

    def _mode_ui_summary(self, mode: str) -> str:
        if mode == "disabled":
            return "当前为不启用模式：不允许初始化，也不显示桌面白名单。"
        if mode == "restricted":
            return "当前为限制模式：根目录和基础对象只读展示，不扫描第三方软件。"
        return "当前为信任模式：可调整根目录白名单、软件白名单，并可重新扫描候选软件。"

    def _root_permission_text(self, item: Dict[str, Any]) -> str:
        parts: List[str] = []
        if item.get("allow_search", False):
            parts.append("查询")
        if item.get("allow_open_file", False):
            parts.append("打开文件")
        if item.get("allow_open_folder", False):
            parts.append("打开目录")
        if item.get("allow_read_meta", False):
            parts.append("读取信息")
        return " / ".join(parts) if parts else "无额外权限"

    def _software_display_permission_state(self, permission_state: str | None) -> PermissionState:
        normalized = self._typed_permission_state(str(permission_state or "unset").strip().lower() or "unset")
        return "deny" if normalized == "unset" else normalized

    def _software_permission_label(self, permission_state: str | None) -> str:
        return {
            "allow": "是",
            "deny": "否",
            "once": "受限",
        }.get(self._software_display_permission_state(permission_state), "否")

    def _software_filter_matches(self, permission_state: str | None, filter_key: str) -> bool:
        matched_permission = FILTER_TO_PERMISSION.get(filter_key)
        if matched_permission is None:
            return True
        if matched_permission == "deny":
            return self._software_display_permission_state(permission_state) == "deny"
        return self._typed_permission_state(str(permission_state or "unset").strip().lower() or "unset") == matched_permission

    def _software_status_profile(self, item: Dict[str, Any]) -> tuple[str, str]:
        candidate_kind = str(item.get("candidate_kind", "")).strip().lower()
        path_status = str(item.get("path_status", "")).strip().lower()
        launch_target_kind = str(item.get("launch_target_kind", "")).strip().lower()
        if candidate_kind == "indirect_launcher" or path_status == "indirect" or launch_target_kind in {"protocol", "launcher"}:
            return "平台入口", "#A78BFA"
        if path_status == "missing" or candidate_kind == "weak_missing_path":
            return "路径缺失", "#F97316"
        if bool(item.get("builtin", False)):
            return "内置", "#60A5FA"
        source = str(item.get("source", "")).strip().lower()
        if source == "confirmed":
            return "已确认", "#22C55E"
        if source == "candidate":
            return "候选", "#FACC15"
        return "发现", "#94A3B8"

    def _software_capability_summary(self, *, mode: str, permission_state: str, has_path: bool) -> str:
        display_state = self._software_display_permission_state(permission_state)
        if mode not in {"trusted", "test"}:
            return "当前模式不执行软件动作。"
        if not has_path:
            return "当前对象缺少路径或入口信息，执行结果会提示缺少信息。"
        if display_state == "allow":
            return "当前权限说明：允许定位、启动、关闭、卸载、迁移、更新操作。"
        if display_state == "once":
            return "当前权限说明：允许定位、启动、关闭操作；卸载、迁移、更新不可执行。"
        return "当前权限说明：所有软件动作禁用。"

    def _is_indirect_launcher(self, item: Dict[str, Any]) -> bool:
        return (
            str(item.get("candidate_kind", "")).strip().lower() == "indirect_launcher"
            or str(item.get("path_status", "")).strip().lower() == "indirect"
            or str(item.get("launch_target_kind", "")).strip().lower() in {"protocol", "launcher"}
        )

    def _is_hidden_software_category(self, item: Dict[str, Any]) -> bool:
        policy_hidden, _reason = self.software_visibility_policy.should_hide(item if isinstance(item, dict) else {})
        if policy_hidden:
            return True

        candidate_kind = str(item.get("candidate_kind", "")).strip().lower()
        category = str(item.get("category", "")).strip().lower()
        launch_target_kind = str(item.get("launch_target_kind", "")).strip().lower()
        path_status = str(item.get("path_status", "")).strip().lower()

        if launch_target_kind == "web_url":
            return True

        if path_status == "registry_residual":
            return True

        return candidate_kind in {"installer_bundle", "driver_or_runtime"} or category in {
            "admin_tool",
            "installer_bundle",
            "driver",
            "driver_or_runtime",
            "runtime_env",
            "system_core",
            "diagnostics_only",
        }

    def _software_path_display(self, item: Dict[str, Any]) -> tuple[str, str]:
        target_path = str(item.get("target_path", "")).strip()
        if target_path:
            return self._truncate_path(target_path), target_path
        if self._is_indirect_launcher(item):
            launch_target_raw = str(item.get("launch_target_raw", "")).strip()
            launch_target_kind = str(item.get("launch_target_kind", "")).strip().lower()
            label = "协议入口" if launch_target_kind == "protocol" else "平台入口"
            return label, launch_target_raw or label
        return "路径缺失", ""

    def _software_icon_source_path(self, item: Dict[str, Any]) -> str:
        target_path = str(item.get("target_path", "")).strip()
        if target_path and target_path.lower().endswith(".exe"):
            return target_path
        return ""

    def _software_icon_kind(self, item: Dict[str, Any]) -> str:
        if bool(item.get("builtin", False)) or str(item.get("category", "")).strip().lower() == "system_core":
            return "system"
        if self._is_indirect_launcher(item):
            return "launcher"
        if self._software_icon_source_path(item):
            return "exe"
        if str(item.get("path_status", "")).strip().lower() == "missing":
            return "missing"
        return "app"

    def _merge_apps_for_mode(self, mode: str) -> List[Dict[str, Any]]:
        builtin_records = [
            SoftwareRecord.from_dict(item)
            for item in self._builtin_apps()
            if item.get("app_id") and not self._is_file_shell_app(item)
        ]
        trusted_records = [
            SoftwareRecord.from_dict(item)
            for item in self._read_confirmed_apps()
            if item.get("app_id") and not self._is_file_shell_app(item)
        ]
        candidate_records = [
            SoftwareRecord.from_dict(item)
            for item in self._read_candidate_apps()
            if item.get("app_id") and not self._is_file_shell_app(item)
        ]

        merged = self.software_merge_service.merge_for_mode(
            mode=mode,
            builtin_records=builtin_records,
            trusted_records=trusted_records,
            candidate_records=candidate_records,
            hidden_ids=self.software_hidden_book.read_ids(),
        )
        merged = self._dedupe_final_software_records(merged)

        result: List[Dict[str, Any]] = []
        for item in merged:
            payload = item.to_dict()
            permission_state = self._typed_permission_state(self._permission_state_from_item(payload))
            payload["permission_state"] = permission_state
            payload["status_text"] = PERMISSION_LABELS[permission_state]
            payload["status_color"] = PERMISSION_COLORS[permission_state]
            result.append(payload)

        return sorted(
            result,
            key=lambda item: (
                str(item.get("title", "")).casefold(),
                str(item.get("app_id", "")).casefold(),
            ),
        )

    def _dedupe_final_software_records(self, records: Iterable[SoftwareRecord]) -> List[SoftwareRecord]:
        items = [item for item in records if item and str(getattr(item, "app_id", "") or "").strip()]
        steam_title_map: Dict[str, str] = {}
        for item in items:
            steam_id = self._final_steam_app_id(item)
            title_key = self._final_title_key(getattr(item, "title", ""))
            if steam_id and title_key:
                steam_title_map.setdefault(title_key, f"steam::{steam_id}")

        buckets: Dict[str, SoftwareRecord] = {}
        for item in items:
            key = self._final_software_identity_key(item, steam_title_map)
            if key in buckets:
                buckets[key] = self._merge_final_software_record(buckets[key], item)
            else:
                buckets[key] = SoftwareRecord.from_dict(item.to_dict())
        return list(buckets.values())

    def _final_software_identity_key(self, item: SoftwareRecord, steam_title_map: Dict[str, str]) -> str:
        canonical_app_id = str(getattr(item, "canonical_app_id", "") or "").strip().casefold()
        if canonical_app_id:
            return f"canonical::{canonical_app_id}"

        steam_id = self._final_steam_app_id(item)
        if steam_id:
            return f"steam::{steam_id}"

        title_key = self._final_title_key(getattr(item, "title", ""))
        if title_key in steam_title_map and self._final_is_steam_common_record(item):
            return steam_title_map[title_key]

        path_key = self._final_path_key(
            getattr(item, "manual_target_path", "")
            or getattr(item, "target_path", "")
            or getattr(item, "entry_path", "")
            or getattr(item, "manual_entry_path", "")
        )
        if path_key:
            return f"path::{path_key}"

        install_dir_key = self._final_path_key(getattr(item, "install_dir", ""))
        if install_dir_key and title_key:
            return f"install::{install_dir_key}::{title_key}"

        publisher_key = self._final_text_key(getattr(item, "publisher", ""))
        if title_key:
            return f"title::{title_key}::{publisher_key}"

        return f"app::{str(getattr(item, 'app_id', '') or '').strip().casefold()}"

    def _merge_final_software_record(self, current: SoftwareRecord, incoming: SoftwareRecord) -> SoftwareRecord:
        primary, secondary = (
            (current, incoming)
            if self._final_record_rank(current) >= self._final_record_rank(incoming)
            else (incoming, current)
        )
        merged = SoftwareRecord.from_dict(primary.to_dict())
        secondary_payload = secondary.to_dict()

        for field in (
            "target_path",
            "manual_target_path",
            "entry_path",
            "manual_entry_path",
            "install_dir",
            "icon_source_path",
            "uninstall_string",
            "registry_key",
            "source_detail",
            "identity_source",
            "launch_source",
            "registry_entry_status",
            "publisher",
            "version",
        ):
            if not str(getattr(merged, field, "") or "").strip() and str(secondary_payload.get(field, "") or "").strip():
                setattr(merged, field, secondary_payload.get(field, ""))

        steam_source = primary if self._final_steam_app_id(primary) else (secondary if self._final_steam_app_id(secondary) else None)
        if steam_source is not None:
            for field in (
                "platform",
                "platform_object_type",
                "platform_object_id",
                "launch_target_kind",
                "launch_target_raw",
                "manual_launch_target_kind",
                "manual_launch_target_raw",
                "route_confidence",
            ):
                value = str(getattr(steam_source, field, "") or "").strip()
                if value:
                    setattr(merged, field, getattr(steam_source, field))

        current_permission = str(getattr(current, "permission_state", "unset") or "unset").strip().lower()
        incoming_permission = str(getattr(incoming, "permission_state", "unset") or "unset").strip().lower()
        permission = current_permission
        if self._final_permission_rank(incoming_permission) > self._final_permission_rank(current_permission):
            permission = incoming_permission
        merged.permission_state = self._typed_permission_state(permission)
        merged.enabled = merged.permission_state in {"allow", "once"}
        merged.allow_launch = merged.permission_state in {"allow", "once"}
        merged.discovered = bool(getattr(current, "discovered", False) or getattr(incoming, "discovered", False))
        merged.hidden = bool(getattr(current, "hidden", False) and getattr(incoming, "hidden", False))
        merged.manual_bound = bool(getattr(current, "manual_bound", False) or getattr(incoming, "manual_bound", False))
        if str(getattr(current, "source", "") or "").strip().lower() in {"trusted", "confirmed"}:
            merged.source = getattr(current, "source")
        if str(getattr(incoming, "source", "") or "").strip().lower() in {"trusted", "confirmed"}:
            merged.source = getattr(incoming, "source")
        return merged

    def _final_record_rank(self, item: SoftwareRecord) -> tuple[int, int, int, int, int]:
        source = str(getattr(item, "source", "") or "").strip().lower()
        source_rank = {"trusted": 4, "confirmed": 4, "builtin": 3, "candidate": 1}.get(source, 0)
        permission_rank = self._final_permission_rank(getattr(item, "permission_state", "unset"))
        protocol_rank = 1 if self._final_steam_app_id(item) else 0
        path_rank = 1 if self._final_path_key(getattr(item, "target_path", "") or getattr(item, "manual_target_path", "")) else 0
        strength = str(getattr(item, "candidate_strength", "") or "").strip().lower()
        strength_rank = {"strong": 2, "medium": 1, "weak": 0}.get(strength, 0)
        return permission_rank, source_rank, protocol_rank, path_rank, strength_rank

    def _final_permission_rank(self, permission_state: str | None) -> int:
        return {"allow": 4, "once": 3, "unset": 2, "deny": 1}.get(
            str(permission_state or "unset").strip().lower(),
            0,
        )

    def _final_steam_app_id(self, item: SoftwareRecord) -> str:
        platform = str(getattr(item, "platform", "") or "").strip().lower()
        object_id = str(getattr(item, "platform_object_id", "") or "").strip().lower()
        if platform == "steam" and object_id:
            return object_id
        for field in ("launch_target_raw", "manual_launch_target_raw"):
            value = str(getattr(item, field, "") or "").strip().lower()
            match = re.search(r"steam://rungameid/(\d+)", value)
            if match:
                return match.group(1)
        return ""

    def _final_is_steam_common_record(self, item: SoftwareRecord) -> bool:
        for field in ("target_path", "manual_target_path", "entry_path", "manual_entry_path", "install_dir", "icon_source_path"):
            value = self._final_path_key(getattr(item, field, ""))
            if "steamapps\\common\\" in value:
                return True
        return False

    def _final_path_key(self, value: Any) -> str:
        text = str(value or "").strip()
        if not text:
            return ""
        normalized = self._normalize_path(text) or text
        return normalized.replace("/", "\\").strip().casefold()

    def _final_title_key(self, value: Any) -> str:
        text = str(value or "").strip().casefold()
        if not text:
            return ""
        text = re.sub(r"[\s\-_：:（）()\[\]【】]+", "", text)
        return text

    def _final_text_key(self, value: Any) -> str:
        text = str(value or "").strip().casefold()
        return re.sub(r"\s+", " ", text)

    def _core_local_ready(self) -> bool:
        required = (
            self._path("roots"),
            self._path("disks"),
            self._path("apps"),
            self._path("apps_candidates"),
            self._path("install"),
        )
        return all(path.exists() for path in required)

    def _truncate_path(self, path_text: str, *, limit: int = 68) -> str:
        text = str(path_text or "").strip()
        if len(text) <= limit:
            return text or "-"
        return f"...{text[-(limit - 3):]}"

    def _detect_object_type(self, path: Path) -> str:
        if path.is_dir():
            return "目录"
        suffix = path.suffix.lower()
        if suffix in {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp"}:
            return "图片"
        if suffix in {".mp4", ".mkv", ".avi", ".mov", ".wmv"}:
            return "视频"
        if suffix in {".md", ".txt", ".pdf", ".doc", ".docx", ".ppt", ".pptx", ".xls", ".xlsx"}:
            return "文档"
        if suffix in {".py", ".js", ".ts", ".tsx", ".json", ".yaml", ".yml", ".toml"}:
            return "项目对象"
        return "文件"

    def _resolve_app_icon_text(self, item: Dict[str, Any]) -> str:
        icon_kind = self._software_icon_kind(item)
        if icon_kind == "system":
            return "SYS"
        if icon_kind in {"missing", "launcher"}:
            return "?"
        return "APP"

    def _is_file_shell_app(self, item: Dict[str, Any]) -> bool:
        app_id = str(item.get("app_id", "")).strip().lower()
        title = str(item.get("title", "")).strip().lower()
        category = str(item.get("category", "")).strip().lower()
        if app_id == "explorer":
            return True
        if title in {"文件资源管理器", "explorer", "file explorer"}:
            return True
        return category == "system_core" and (
            "explorer" in app_id
            or "资源管理器" in title
            or "file explorer" in title
        )

    def _ability_summary(self, mode: str, *, software: bool = False) -> str:
        if mode == "disabled":
            return "桌面连接关闭，不执行文件或软件动作。"
        if software:
            if mode == "restricted":
                return "限制模式不执行软件动作。"
            if mode == "test":
                return "测试模式根据选择进入沙盒回执或虚拟机测试。"
            return "信任模式进入 Host 真实执行，软件动作按权限、确认、审议和记录执行。"
        if mode == "restricted":
            return "只允许部分文件查询与只读浏览，不执行软件动作和文件写入动作。"
        if mode == "test":
            return "测试模式根据选择进入沙盒回执或虚拟机测试。"
        return "信任模式进入 Host 真实执行，文件动作按权限、确认、审议和记录执行。"

    def _enabled_roots(self) -> List[Dict[str, Any]]:
        return [item for item in self._read_roots() if bool(item.get("enabled", False))]

    def _is_path_under_enabled_root(self, target_path: Path) -> bool:
        for item in self._enabled_roots():
            try:
                target_path.relative_to(Path(str(item.get("path", "")).strip()).expanduser().resolve(strict=False))
                return True
            except Exception:
                continue
        return False

    def _root_permission_state(self, root_item: Dict[str, Any], permission_overrides: Dict[str, str]) -> PermissionState:
        root_id = str(root_item.get("root_id", "")).strip()
        return self._typed_permission_state(permission_overrides.get(root_id, "unset"))

    def _find_enabled_root_for_path(self, target_path: Path, roots: Iterable[Dict[str, Any]]) -> Dict[str, Any] | None:
        matches: List[tuple[int, Dict[str, Any]]] = []
        for item in roots:
            if not bool(item.get("enabled", False)):
                continue
            root_path_text = str(item.get("path", "")).strip()
            if not root_path_text:
                continue
            try:
                root_path = Path(root_path_text).expanduser().resolve(strict=False)
                target_path.relative_to(root_path)
            except Exception:
                continue
            matches.append((len(root_path.parts), item))
        if not matches:
            return None
        return max(matches, key=lambda pair: pair[0])[1]

    def _list_windows_drives(self) -> List[Path]:
        result: List[Path] = []
        for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
            drive = Path(f"{letter}:/")
            if drive.exists():
                result.append(drive)
        return result

    def _drive_key(self, path: Path) -> str:
        drive = str(path.drive or path.anchor or "").strip()
        return drive.upper() if drive else str(path).strip()

    def _disk_allows_traversal(self, permission_state: PermissionState) -> bool:
        return permission_state in {"allow", "once"}

    def _resolve_disk_status_text(self, permission_state: PermissionState, mode: str) -> str:
        if mode == "disabled":
            return "未启用"
        return PERMISSION_LABELS[permission_state]

    def _file_permission_summary(self, permission_state: str | None) -> str:
        normalized = self._typed_permission_state(str(permission_state or "deny").strip().lower() or "deny")
        if normalized in {"unset", "deny"}:
            return "不展开、不扫描、不查询，也不显示内部内容。"
        if normalized == "once":
            return "允许按开关展开、扫描、查询；允许基础文件动作。"
        if normalized == "allow":
            return "允许按开关展开、扫描、查询；允许完整文件动作。"
        return "按当前模式和对象权限判断可用动作。"

    def build_disk_rows(self, mode: str) -> List[Dict[str, Any]]:
        return self._build_disk_rows_v2(mode)

    def _build_disk_rows_v2(self, mode: str) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        for disk in self._read_disks():
            permission_state = self._disk_permission_state_from_item(disk)
            disk_id = str(disk.get("disk_id", "")).strip().upper()
            trusted = mode in {"restricted", "trusted", "test"} and self._disk_allows_traversal(permission_state)
            rows.append({
                "disk_id": disk_id,
                "title": str(disk.get("title", "")).strip() or str(disk.get("disk_id", "")).strip(),
                "path": f"{str(disk.get('disk_id', '')).strip()}\\",
                "status_text": self._resolve_disk_status_text(permission_state, mode),
                "status_color": PERMISSION_COLORS[permission_state],
                "allow_expand": bool(disk.get("allow_expand", False)),
                "allow_scan": bool(disk.get("allow_scan", False)),
                "allow_index": bool(disk.get("allow_index", False)),
                "file_actions_enabled": self.get_disk_file_actions_enabled(disk_id),
                "trusted": trusted,
                "permission_state": permission_state,
                "can_adjust": mode in {"trusted", "test"},
                "tooltip": (
                    f"完整路径：{str(disk.get('disk_id', '')).strip()}\\\n"
                    "对象类型：磁盘\n"
                    f"当前状态：{self._resolve_disk_status_text(permission_state, mode)}\n"
                    f"当前权限说明：{self._file_permission_summary(permission_state)}\n"
                    f"当前模式下允许的能力摘要：{self._ability_summary(mode)}"
                ),
            })
        return rows

    def cycle_file_permission(self, current_state: str | None) -> str:
        return next_permission_state(current_state)

    def get_file_governance_state(
        self,
        *,
        mode: str,
        disk_filter_key: str = "all",
        object_view_mode: str = "roots",
        object_filter_key: str = "all",
        view_mode: str | None = None,
        filter_key: str | None = None,
        editable: bool,
        selected_disk: str,
        current_path: str,
        permission_overrides: Dict[str, str] | None = None,
        host_file_cache_state: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        permission_overrides = permission_overrides or {}
        cache_state = host_file_cache_state if isinstance(host_file_cache_state, dict) else {}
        cache_rows = cache_state.get("rows", [])
        if not isinstance(cache_rows, list):
            cache_rows = []
        all_disk_rows = self._build_disk_rows_v2(mode)
        disk_matched_permission = FILTER_TO_PERMISSION.get(disk_filter_key)
        disk_rows = [
            item for item in all_disk_rows
            if disk_matched_permission is None or item.get("permission_state") == disk_matched_permission
        ]
        roots = self._read_roots()
        selected_disk = str(selected_disk or "").strip().upper()
        if not selected_disk and disk_rows:
            root_drive_keys = {
                self._drive_key(Path(str(item.get("path", "")).strip()))
                for item in roots
                if bool(item.get("enabled", False)) and str(item.get("path", "")).strip()
            }
            preferred_disk = next(
                (
                    item for item in disk_rows
                    if bool(item.get("trusted", False))
                ),
                next(
                    (
                        item for item in disk_rows
                        if str(item.get("disk_id", "")).strip().upper() in root_drive_keys
                    ),
                    disk_rows[0],
                ),
            )
            selected_disk = str(preferred_disk.get("disk_id", "")).strip().upper()

        selected_disk_row = next((item for item in disk_rows if item["disk_id"] == selected_disk), None)
        if selected_disk and selected_disk_row is None and disk_rows:
            selected_disk = str(disk_rows[0].get("disk_id", "")).strip().upper()
            selected_disk_row = next((item for item in disk_rows if item["disk_id"] == selected_disk), None)
        roots_view = str(object_view_mode or view_mode or "roots").strip().lower() or "roots"
        matched_permission = FILTER_TO_PERMISSION.get(object_filter_key if object_filter_key is not None else filter_key)
        allow_adjust = mode in {"trusted", "test"} and editable
        for item in all_disk_rows:
            item["can_adjust"] = allow_adjust
        selected_disk_permission_state = self._disk_permission_state_from_item(selected_disk_row or {})
        selected_disk_allows_open = bool(
            selected_disk_row
            and mode in {"restricted", "trusted", "test"}
            and selected_disk_permission_state in {"allow", "once"}
            and bool(selected_disk_row.get("allow_expand", False))
        )

        rows: List[Dict[str, Any]] = []
        current_target_path = "-"

        if roots_view == "roots":
            for item in roots:
                path_text = str(item.get("path", "")).strip()
                path_obj = Path(path_text) if path_text else None
                drive_key = self._drive_key(path_obj) if path_obj is not None else ""
                if selected_disk and drive_key != selected_disk:
                    continue

                object_key = str(item.get("root_id", "")).strip()
                permission_state = self._root_permission_state(item, permission_overrides)
                effective_permission_state = permission_state
                path_exists = bool(path_text) and Path(path_text).expanduser().exists()
                request_allowed = bool(
                    mode in {"restricted", "trusted", "test"}
                    and bool(item.get("enabled", False))
                    and path_exists
                    and selected_disk_allows_open
                    and effective_permission_state in {"allow", "once"}
                )
                apply_ui_allowed = request_allowed
                if matched_permission is not None:
                    if matched_permission == "deny":
                        if effective_permission_state not in {"deny", "unset"}:
                            continue
                    elif effective_permission_state != matched_permission:
                        continue

                rows.append({
                    "object_key": object_key,
                    "root_id": object_key,
                    "enabled": bool(item.get("enabled", False)),
                    "name": str(item.get("title", object_key)).strip() or "-",
                    "path": path_text or "-",
                    "path_short": self._truncate_path(path_text),
                    "open_label": "进入下级" if bool(item.get("enabled", False)) else "查看信息",
                    "target_path": path_text,
                    "target_name": str(item.get("title", object_key)).strip() or "-",
                    "target_type": "目录",
                    "object_type": "directory",
                    "is_dir": True,
                    "status_text": PERMISSION_LABELS[effective_permission_state],
                    "status_color": PERMISSION_COLORS[effective_permission_state],
                    "permission_state": permission_state,
                    "permission_text": PERMISSION_LABELS[permission_state],
                    "effective_permission_state": effective_permission_state,
                    "permission_source_type": "root",
                    "permission_source_key": object_key,
                    "request_allowed": request_allowed,
                    "apply_ui_allowed": apply_ui_allowed,
                    "can_open": request_allowed,
                    "can_adjust": allow_adjust,
                    "open_action": "navigate",
                    "open_disabled_reason": (
                        "当前模式不允许进入下级。"
                        if mode not in {"restricted", "trusted", "test"}
                        else "当前根目录未启用。"
                        if not bool(item.get("enabled", False))
                        else "当前根目录路径无效。"
                        if not path_exists
                        else "当前磁盘未允许展开。"
                        if not selected_disk_row or not bool(selected_disk_row.get("allow_expand", False))
                        else "当前磁盘未被允许访问。"
                        if selected_disk_permission_state not in {"allow", "once"}
                        else "当前根目录权限未允许进入。"
                        if effective_permission_state not in {"allow", "once"}
                        else ""
                    ),
                    "tooltip": (
                        f"完整路径：{path_text or '-'}\n"
                        "对象类型：目录\n"
                        f"纳入治理：{'是' if bool(item.get('enabled', False)) else '否'}\n"
                        f"当前状态：{PERMISSION_LABELS[effective_permission_state]}\n"
                        f"当前权限说明：{self._file_permission_summary(permission_state)}\n"
                        f"当前模式能力：{self._ability_summary(mode)}"
                    ),
                })
            current_target_path = "当前视图：根目录表"
        else:
            current_target = str(current_path or "").strip()
            cache_current_path = str(cache_state.get("current_path") or cache_state.get("root_path") or "").strip()
            if not current_target and cache_current_path:
                current_target = cache_current_path
            if not current_target and selected_disk_row and bool(selected_disk_row.get("trusted", False)) and bool(selected_disk_row.get("allow_expand", False)):
                candidate_root = next(
                    (
                        item for item in roots
                        if bool(item.get("enabled", False))
                        and self._drive_key(Path(str(item.get("path", "")).strip())) == selected_disk
                        and self._root_permission_state(item, permission_overrides) in {"allow", "once"}
                    ),
                    None,
                )
                if candidate_root is not None:
                    current_target = str(candidate_root.get("path", "")).strip()

            current_target_path = current_target or "-"
            if (
                current_target
                and selected_disk_row
                and selected_disk_allows_open
            ):
                base_path = Path(current_target).expanduser().resolve(strict=False)
                current_drive_key = self._drive_key(base_path)
                current_root = self._find_enabled_root_for_path(base_path, roots)
                if (
                    (not selected_disk or current_drive_key == selected_disk)
                    and (current_root is not None or selected_disk_permission_state in {"allow", "once"})
                ):
                    root_id = (
                        str(current_root.get("root_id", "")).strip()
                        if current_root is not None
                        else selected_disk
                    )
                    root_permission_state = (
                        self._root_permission_state(current_root, permission_overrides)
                        if current_root is not None
                        else selected_disk_permission_state
                    )
                    normalized_cache_path = str(Path(cache_current_path).expanduser().resolve(strict=False)) if cache_current_path else ""
                    normalized_current = str(base_path)
                    cached_entries = cache_rows if normalized_cache_path == normalized_current else []

                    for entry in cached_entries:
                        if not isinstance(entry, dict):
                            continue
                        child_path_text = str(entry.get("path", "") or "").strip()
                        if not child_path_text:
                            continue
                        child_path = Path(child_path_text)
                        child_name = str(entry.get("name", "") or "").strip() or child_path.name or "-"
                        is_dir = bool(entry.get("is_dir", False)) or str(entry.get("type", "")).strip().lower() in {"directory", "folder"}
                        object_key = child_path_text
                        has_object_override = object_key in permission_overrides
                        permission_state = self._typed_permission_state(permission_overrides.get(object_key, "unset"))
                        effective_permission_state = permission_state if has_object_override else root_permission_state
                        permission_source_type = "object" if has_object_override else "root"
                        permission_source_key = object_key if has_object_override else root_id
                        if matched_permission is not None:
                            if matched_permission == "deny":
                                if effective_permission_state not in {"deny", "unset"}:
                                    continue
                            elif effective_permission_state != matched_permission:
                                continue
                        object_type = "目录" if is_dir else "文件"
                        request_allowed = effective_permission_state in {"allow", "once"}
                        apply_ui_allowed = bool(request_allowed and is_dir)
                        can_open = request_allowed
                        open_disabled_reason = ""
                        if mode not in {"restricted", "trusted", "test"}:
                            can_open = False
                            request_allowed = False
                            apply_ui_allowed = False
                            open_disabled_reason = "当前模式不允许执行对象操作。"
                        elif not bool(selected_disk_row.get("trusted", False)):
                            can_open = False
                            request_allowed = False
                            apply_ui_allowed = False
                            open_disabled_reason = "当前磁盘未被允许访问。"
                        elif not bool(selected_disk_row.get("allow_expand", False)):
                            can_open = False
                            request_allowed = False
                            apply_ui_allowed = False
                            open_disabled_reason = "当前磁盘未允许展开。"
                        elif effective_permission_state not in {"allow", "once"}:
                            can_open = False
                            request_allowed = False
                            apply_ui_allowed = False
                            open_disabled_reason = "当前对象权限未允许操作。"
                        rows.append({
                            "object_key": object_key,
                            "root_id": root_id,
                            "enabled": True,
                            "name": child_name,
                            "path": child_path_text,
                            "path_short": self._truncate_path(child_path_text),
                            "open_label": "进入下级" if is_dir else "打开",
                            "target_path": child_path_text,
                            "target_name": child_name,
                            "target_type": object_type,
                            "is_dir": is_dir,
                            "source": str(entry.get("source") or "host_cache"),
                            "backend": "host",
                            "status_text": PERMISSION_LABELS[effective_permission_state],
                            "status_color": PERMISSION_COLORS[effective_permission_state],
                            "permission_state": effective_permission_state,
                            "permission_text": PERMISSION_LABELS[effective_permission_state],
                            "effective_permission_state": effective_permission_state,
                            "permission_source_type": permission_source_type,
                            "permission_source_key": permission_source_key,
                            "request_allowed": request_allowed,
                            "apply_ui_allowed": apply_ui_allowed,
                            "can_open": can_open,
                            "can_adjust": allow_adjust,
                            "open_action": "navigate" if is_dir else "inspect",
                            "open_disabled_reason": open_disabled_reason,
                            "tooltip": (
                                f"完整路径：{child_path_text}\n"
                                f"对象类型：{object_type}\n"
                                f"当前状态：{PERMISSION_LABELS[effective_permission_state]}\n"
                                f"当前权限说明：{self._file_permission_summary(effective_permission_state)}\n"
                                f"当前模式能力：{self._ability_summary(mode)}"
                            ),
                        })

        return {
            "mode": mode,
            "view_mode": roots_view,
            "disk_filter_key": disk_filter_key,
            "object_filter_key": object_filter_key,
            "file_actions_enabled": self.get_disk_file_actions_enabled(selected_disk),
            "read_only": not allow_adjust,
            "disk_rows": disk_rows,
            "trusted_disk_rows": [
                item for item in all_disk_rows
                if item.get("permission_state") in {"allow", "once"}
            ],
            "selected_disk": selected_disk,
            "selected_disk_trusted": bool(selected_disk_row and selected_disk_row.get("trusted", False)),
            "selected_disk_permission_state": str((selected_disk_row or {}).get("permission_state", "unset")),
            "can_rescan_disk": bool(
                mode in {"restricted", "trusted"}
                and selected_disk_row
                and selected_disk_permission_state in {"allow", "once"}
                and bool(selected_disk_row.get("allow_scan", False))
            ),
            "current_path": current_target_path,
            "rows": rows,
        }

    def get_software_governance_state(
        self,
        *,
        mode: str,
        filter_key: str,
        editable: bool,
    ) -> Dict[str, Any]:
        hidden_ids = self.software_hidden_book.read_ids()
        all_apps = [
            item
            for item in self._merge_apps_for_mode(mode)
            if not self._is_file_shell_app(item)
        ]
        visibility_hidden_count = len([
            item for item in all_apps
            if self._is_hidden_software_category(item)
        ])
        merged_apps = [
            SoftwareRecord.from_dict(item)
            for item in all_apps
            if not self._is_hidden_software_category(item)
        ]
        state = self.software_view_model_service.build_state(
            mode=mode,
            filter_key=filter_key,
            editable=editable,
            merged_apps=merged_apps,
            hidden_ids=hidden_ids,
        )
        state["hidden_count"] = int(state.get("hidden_count", 0) or 0) + visibility_hidden_count
        diagnostics = state.get("diagnostics", {}) if isinstance(state.get("diagnostics", {}), dict) else {}
        diagnostics = dict(diagnostics)
        diagnostics["visibility_policy_hidden_count"] = visibility_hidden_count
        state["diagnostics"] = diagnostics
        return state

    def get_page_shell_state(self, *, apps_editable: bool = False) -> Dict[str, Any]:
        """
        桌面连接页轻量状态。

        只给页面首次显示使用：
        - 不合并完整软件 rows
        - 不构建 filtered_apps
        - 不读取/渲染完整软件表
        """
        mode_state = self.mode_store.get_mode_state()
        current_mode = mode_state.current_mode
        mode_policy = get_review_policy(current_mode)

        roots = self._read_roots()
        install = self._read_install()

        try:
            confirmed_count = len([
                item for item in self._read_confirmed_apps()
                if not self._is_file_shell_app(item)
            ])
        except Exception:
            confirmed_count = 0

        roots_read_only = bool(mode_policy["roots_read_only"])
        apps_visible = bool(mode_policy["show_apps"])
        apps_read_only = not bool(mode_policy["allow_app_adjust"]) or not apps_editable

        return {
            "mode": current_mode,
            "mode_updated_at": mode_state.updated_at,
            "mode_summary": self._mode_ui_summary(current_mode),
            "local_ready": self._core_local_ready(),
            "initialized": bool(install.get("initialized", False)),
            "root_count": len(roots),
            "confirmed_app_count": confirmed_count,
            "show_roots": bool(mode_policy["show_roots"]),
            "show_apps": apps_visible,
            "roots_read_only": roots_read_only,
            "apps_read_only": apps_read_only,
            "can_init": current_mode != "disabled",
            "can_scan": bool(mode_policy["allow_candidate_rescan"]),
            "can_adjust_apps": bool(mode_policy["allow_app_adjust"]),
            "can_toggle_apps_editable": bool(mode_policy["allow_app_adjust"]),
            "filter_key": "all",
            "roots": [],
            "apps": [],
            "shell_only": True,
        }

    def get_page_state(self, *, filter_key: str = "all", apps_editable: bool = False) -> Dict[str, Any]:
        mode_state = self.mode_store.get_mode_state()
        current_mode = mode_state.current_mode
        mode_policy = get_review_policy(current_mode)
        roots = self._read_roots()
        confirmed_apps = [item for item in self._read_confirmed_apps() if not self._is_file_shell_app(item)]
        merged_apps = self._merge_apps_for_mode(current_mode)

        matched_permission = FILTER_TO_PERMISSION.get(filter_key)
        filtered_apps = [
            item for item in merged_apps
            if matched_permission is None or self._software_filter_matches(str(item.get("permission_state", "unset")), filter_key)
        ]

        roots_rows = []
        for item in roots:
            row = dict(item)
            row["permission_text"] = self._root_permission_text(item)
            roots_rows.append(row)

        install = self._read_install()
        roots_read_only = bool(mode_policy["roots_read_only"])
        apps_visible = bool(mode_policy["show_apps"])
        apps_read_only = not bool(mode_policy["allow_app_adjust"]) or not apps_editable

        return {
            "mode": current_mode,
            "mode_updated_at": mode_state.updated_at,
            "mode_summary": self._mode_ui_summary(current_mode),
            "local_ready": self._core_local_ready(),
            "initialized": bool(install.get("initialized", False)),
            "root_count": len(roots_rows),
            "confirmed_app_count": len(confirmed_apps),
            "show_roots": bool(mode_policy["show_roots"]),
            "show_apps": apps_visible,
            "roots_read_only": roots_read_only,
            "apps_read_only": apps_read_only,
            "can_init": current_mode != "disabled",
            "can_scan": bool(mode_policy["allow_candidate_rescan"]),
            "can_adjust_apps": bool(mode_policy["allow_app_adjust"]),
            "can_toggle_apps_editable": bool(mode_policy["allow_app_adjust"]),
            "filter_key": filter_key,
            "roots": roots_rows,
            "apps": filtered_apps,
        }

    def set_mode(self, mode: str) -> Dict[str, Any]:
        state = self.mode_store.set_mode(mode)
        return state.to_dict()

    def initialize_local_connection(self) -> Dict[str, Any]:
        ensure_local_data_files(self.project_root)
        self.format_local_files(mark_initialized=True)
        return self.get_page_state()

    def format_local_files(self, *, mark_initialized: bool = False) -> None:
        defaults = self._load_defaults()
        machine = collect_machine_paths(self.project_root)

        mode_file = self._path("mode")
        current_mode = self.mode_store.get_mode_state().current_mode
        self._write_json(
            mode_file,
            {
                "current_mode": current_mode,
                "updated_at": now_iso(),
            },
        )

        roots = self._read_roots()
        if not roots:
            bound = bind_tokens(defaults.get("root_seed", {}), machine)
            roots = [
                self._normalize_root(item)
                for item in bound.get("roots", []) or []
                if isinstance(item, dict)
            ]
        self._write_roots(roots)

        disks = self._read_disks()
        if not disks:
            disks = self._default_disks()
        self._write_disks(disks)

        apps = self._read_confirmed_apps()
        self._write_confirmed_apps(apps)

        candidates = self._read_candidate_apps()
        self._write_candidate_apps(candidates)

        install = self._read_install()
        if mark_initialized:
            install["initialized"] = True
        self._write_install(install)

    def rescan_candidates(self,*,progress_callback: Callable[[dict[str, Any]], None] | None = None,scan_profile: str = "quick",) -> int:
        started_at = time.perf_counter()
        profile = str(scan_profile or "quick").strip().lower()
        if profile not in {"quick", "full"}:
            profile = "quick"
        label = "快速扫描" if profile == "quick" else "完整扫描"
        self._emit_scan_progress(
            progress_callback,
            stage="preparing",
            message=f"{label}准备中",
            stats={"scan_profile": profile},
            percent=1,
        )
        confirmed_ids = [
            item["app_id"] for item in self._read_confirmed_apps()
            if item.get("app_id") and not self._is_file_shell_app(item)
        ]
        existing_candidates = {
            item["app_id"]: item for item in self._read_candidate_apps() if item.get("app_id")
        }
        discovered, diagnostics = self.software_discovery_service.discover_candidates_with_diagnostics(
            app_map=self._load_defaults().get("app_map", {}),
            existing_app_ids=confirmed_ids,
            progress_callback=progress_callback,
            scan_profile=profile,
        )

        refreshed: List[Dict[str, Any]] = []
        dropped_no_target_path = 0
        file_shell_removed = 0
        self._emit_scan_progress(
            progress_callback,
            stage="writing",
            message="writing candidates",
            stats={
                "scan_profile": profile,
                "raw_total": int((diagnostics.get("pipeline", {}) or {}).get("raw_total", 0)),
                "filter_after_total": int((diagnostics.get("pipeline", {}) or {}).get("filter_after_total", 0)),
                "dedupe_after_total": int((diagnostics.get("pipeline", {}) or {}).get("dedupe_after_total", 0)),
            },
            percent=92,
        )
        for item in discovered:
            if not isinstance(item, dict):
                continue
            if self._is_file_shell_app(item):
                file_shell_removed += 1
                continue
            previous = existing_candidates.get(str(item.get("app_id", "")).strip(), {})
            merged = dict(item)
            if not str(merged.get("target_path", "")).strip():
                dropped_no_target_path += 1
            if previous:
                merged["permission_state"] = previous.get("permission_state", "unset")
            else:
                merged["permission_state"] = "deny"
            refreshed.append(self._normalize_app(merged, source="candidate"))

        self._write_candidate_apps(refreshed)
        strong_count = len([item for item in refreshed if str(item.get("candidate_strength", "")).strip().lower() == "strong"])
        weak_count = len([item for item in refreshed if str(item.get("candidate_strength", "")).strip().lower() == "weak"])
        diagnostics = dict(diagnostics)
        diagnostics["scan_profile"] = profile
        diagnostics["generated_at"] = now_iso()
        diagnostics["ok"] = True
        diagnostics["duration_ms"] = int((time.perf_counter() - started_at) * 1000)
        diagnostics["candidates"] = {
            "strong_candidate_count": strong_count,
            "weak_candidate_count": weak_count,
            "service_no_target_path_count": dropped_no_target_path,
            "service_dropped_no_target_path": 0,
            "file_shell_app_removed_count": file_shell_removed,
            "final_written_count": len(refreshed),
        }
        diagnostics["error"] = None
        self._write_software_scan_diagnostics(diagnostics)
        self._print_software_scan_summary(diagnostics, refreshed)
        self._emit_scan_progress(
            progress_callback,
            stage="completed",
            message=f"{label}完成",
            stats={
                "scan_profile": profile,
                "raw_total": int((diagnostics.get("pipeline", {}) or {}).get("raw_total", 0)),
                "filter_after_total": int((diagnostics.get("pipeline", {}) or {}).get("filter_after_total", 0)),
                "dedupe_after_total": int((diagnostics.get("pipeline", {}) or {}).get("dedupe_after_total", 0)),
                "strong_candidate_count": strong_count,
                "weak_candidate_count": weak_count,
                "final_written_count": len(refreshed),
            },
            percent=100,
        )
        return len(refreshed)

    def clear_third_party_connections(self) -> None:
        builtin_ids = self._builtin_app_ids()
        keep_confirmed = [
            item for item in self._read_confirmed_apps()
            if item.get("app_id") in builtin_ids
        ]
        keep_candidates = [
            item for item in self._read_candidate_apps()
            if item.get("app_id") in builtin_ids
        ]
        self._write_confirmed_apps(keep_confirmed)
        self._write_candidate_apps(keep_candidates)
        self._mark_initialized()

    def _update_disk(self, disk_id: str, updater) -> Dict[str, Any]:
        normalized_disk_id = str(disk_id or "").strip().upper()
        if not normalized_disk_id:
            raise ValueError("缺少 disk_id")

        disks = self._read_disks()
        for index, item in enumerate(disks):
            if str(item.get("disk_id", "")).strip().upper() != normalized_disk_id:
                continue
            updated = dict(item)
            updater(updated)
            updated["updated_at"] = now_iso()
            disks[index] = self._normalize_disk(updated)
            self._write_disks(disks)
            self._mark_initialized()
            return disks[index]
        raise ValueError(f"未找到磁盘对象：{normalized_disk_id}")

    def cycle_disk_status(self, disk_id: str) -> str:
        updated = self._update_disk(
            disk_id,
            lambda item: item.__setitem__(
                "permission_state",
                next_permission_state(str(item.get("permission_state", "unset")).strip().lower() or "unset"),
            ),
        )
        return str(updated.get("permission_state", "unset"))

    def toggle_disk_expand(self, disk_id: str, value: bool) -> bool:
        updated = self._update_disk(disk_id, lambda item: item.__setitem__("allow_expand", bool(value)))
        return bool(updated.get("allow_expand", False))

    def toggle_disk_scan(self, disk_id: str, value: bool) -> bool:
        updated = self._update_disk(disk_id, lambda item: item.__setitem__("allow_scan", bool(value)))
        return bool(updated.get("allow_scan", False))

    def toggle_disk_index(self, disk_id: str, value: bool) -> bool:
        updated = self._update_disk(disk_id, lambda item: item.__setitem__("allow_index", bool(value)))
        return bool(updated.get("allow_index", False))

    def update_root_flag(self, root_id: str, field: str, value: bool) -> None:
        roots = self._read_roots()
        for item in roots:
            if item.get("root_id") == root_id and field in item:
                item[field] = bool(value)
                break
        self._write_roots(roots)
        self._mark_initialized()

    def cycle_app_permission(self, app_id: str) -> str:
        if not app_id:
            raise ValueError("缺少 app_id")

        builtin_map = {item["app_id"]: item for item in self._builtin_apps() if item.get("app_id")}
        confirmed_map = {item["app_id"]: item for item in self._read_confirmed_apps() if item.get("app_id")}
        candidate_map = {item["app_id"]: item for item in self._read_candidate_apps() if item.get("app_id")}

        source_item = confirmed_map.get(app_id) or candidate_map.get(app_id) or builtin_map.get(app_id)
        if source_item is None:
            raise ValueError(f"未找到对应的软件对象：{app_id}")
        effective_target_path = str(source_item.get("manual_target_path", "") or source_item.get("target_path", "")).strip()
        effective_launch_target_raw = str(source_item.get("manual_launch_target_raw", "") or source_item.get("launch_target_raw", "")).strip()
        candidate_kind = str(source_item.get("candidate_kind", "")).strip().lower()
        if app_id in candidate_map and not effective_target_path and not effective_launch_target_raw:
            if candidate_kind == "indirect_launcher":
                raise ValueError("该候选软件缺少稳定的平台入口，暂不能确认权限。")
            raise ValueError("该候选软件缺少可执行路径，暂不能确认权限。")

        current_state = self._software_display_permission_state(self._permission_state_from_item(source_item))
        next_state = {
            "deny": "once",
            "once": "allow",
            "allow": "deny",
        }.get(current_state, "once")

        if next_state == "unset":
            confirmed_map.pop(app_id, None)
        else:
            new_item = self._apply_permission_state(dict(source_item), next_state)
            confirmed_map[app_id] = self._normalize_app(new_item, source="confirmed", builtin=app_id in builtin_map)
            candidate_map.pop(app_id, None)

        self._write_confirmed_apps(confirmed_map.values())
        self._write_candidate_apps(candidate_map.values())
        self._mark_initialized()
        return next_state

    def bind_app_path(self, app_id: str, selected_path: str) -> Dict[str, Any]:
        normalized_app_id = str(app_id or "").strip()
        normalized_selected_path = str(selected_path or "").strip()
        if not normalized_app_id:
            raise ValueError("缺少 app_id")
        if not normalized_selected_path:
            raise ValueError("缺少绑定路径")

        builtin_map = {item["app_id"]: item for item in self._builtin_apps() if item.get("app_id")}
        confirmed_map = {item["app_id"]: item for item in self._read_confirmed_apps() if item.get("app_id")}
        candidate_map = {item["app_id"]: item for item in self._read_candidate_apps() if item.get("app_id")}

        source_item = confirmed_map.get(normalized_app_id) or candidate_map.get(normalized_app_id) or builtin_map.get(normalized_app_id)
        if source_item is None:
            raise ValueError(f"未找到对应的软件对象：{normalized_app_id}")

        updated = self._normalize_app(
            self._apply_manual_binding(source_item, normalized_selected_path),
            source="confirmed" if normalized_app_id in confirmed_map else "candidate",
            builtin=bool(source_item.get("builtin", False)),
        )

        if normalized_app_id in confirmed_map:
            confirmed_map[normalized_app_id] = updated
            self._write_confirmed_apps(confirmed_map.values())
        else:
            candidate_map[normalized_app_id] = updated
            self._write_candidate_apps(candidate_map.values())
        self._mark_initialized()
        return updated

    def consume_app_once_permission(self, app_id: str) -> None:
        """
        兼容旧权限消费接口。

        once 当前已作为“受限”长期权限使用，不再执行后自动回退。
        """
        return
