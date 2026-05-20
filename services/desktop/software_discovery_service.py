from __future__ import annotations

import re
import hashlib
import time
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List
from collections import Counter

from services.desktop.qin.bingbu.software_detection_gate import SoftwareDetectionGate
from services.desktop.tianting.sources.platform_source_registry import PlatformSourceRegistry


def _slugify(value: str) -> str:
    text = str(value or "").strip().lower()
    if not text:
        return ""
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return text.strip("_")

def _normalize_title_key(value: str) -> str:
    text = str(value or "").strip().lower()
    if not text:
        return ""
    text = re.sub(r"[™®©]", "", text)
    text = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()

def _is_steam_common_path(value: str) -> bool:
    text = str(value or "").strip().replace("/", "\\").lower()
    return "\\steamapps\\common\\" in text

def _steam_app_id_from_raw(value: str) -> str:
    """
    从 Steam 协议入口中提取 AppID。

    支持：
    - steam://rungameid/880940
    - steam://run/880940
    - 其他包含数字 AppID 的 steam:// 链接
    """
    text = str(value or "").strip().lower()
    if not text.startswith("steam://"):
        return ""

    match = re.search(r"rungameid/(\d+)", text)
    if match:
        return match.group(1)

    match = re.search(r"run/(\d+)", text)
    if match:
        return match.group(1)

    match = re.search(r"steam://.*?(\d+)", text)
    if match:
        return match.group(1)

    return ""

def _stable_app_id(title: str) -> str:
    slug = _slugify(title)
    if slug:
        return slug
    digest = hashlib.sha1(str(title or "").encode("utf-8", errors="ignore")).hexdigest()[:12]
    return f"app_{digest}" if digest else ""

def _canonical_app_id(item: Dict[str, Any]) -> str:
    explicit = str(item.get("canonical_app_id", "")).strip().lower()
    if explicit:
        return explicit
    title = str(item.get("title", item.get("app_id", ""))).strip().lower()
    app_id = str(item.get("app_id", "")).strip().lower()
    target = str(item.get("target_path", "")).strip().lower()
    raw = str(item.get("launch_target_raw", "")).strip().lower()
    platform_object_id = str(item.get("platform_object_id", "")).strip().lower()
    haystack = f"{title} {app_id} {target} {raw} {platform_object_id}"
    rules = [
        ("microsoft_edge", ("microsoft edge", "msedge.exe", "microsoft-edge:")),
        ("windows_notepad", ("记事本", "notepad", "windowsnotepad", "microsoft.windowsnotepad")),
        ("windows_calculator", ("计算器", "calculator", "windowscalculator", "microsoft.windowscalculator")),
        ("windows_paint", ("画图", "mspaint", "microsoft.paint")),
        ("windows_snipping_tool", ("截图工具", "snipping tool", "screensketch", "microsoft.screensketch")),
        ("windows_sound_recorder", ("录音机", "sound recorder", "windowssoundrecorder", "microsoft.windowssoundrecorder")),
        ("windows_powershell", ("windows powershell", "powershell.exe")),
        ("windows_explorer", ("windows explorer", "explorer.exe", "文件资源管理器")),
    ]
    for canonical, needles in rules:
        if any(needle in haystack for needle in needles):
            return canonical
    return ""


class SoftwareDiscoveryService:
    def __init__(self, project_root: str | Path | None = None) -> None:
        self.project_root = Path(project_root or Path(__file__).resolve().parents[2]).expanduser().resolve()
        self.source_registry = PlatformSourceRegistry()
        self.detection_gate = SoftwareDetectionGate()

    def _emit_progress(
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

    def _sources(self, *, scan_profile: str = "quick") -> list:
        return self.source_registry.build_sources(scan_profile=scan_profile)

    def discover_from_installed_apps(self) -> List[Dict[str, Any]]:
        return self._collect_single_source("uninstall_registry")

    def discover_from_uninstall_registry(self) -> List[Dict[str, Any]]:
        return self._collect_single_source("uninstall_registry")

    def discover_from_start_menu_shortcuts(self) -> List[Dict[str, Any]]:
        return self._collect_single_source("start_menu_shortcut")

    def discover_from_desktop_shortcuts(self) -> List[Dict[str, Any]]:
        return self._collect_single_source("desktop_shortcut")

    def discover_from_app_map(
        self,
        app_map: Dict[str, Any],
        existing_app_ids: Iterable[str] | None = None,
    ) -> List[Dict[str, Any]]:
        return self._collect_single_source("app_map_fallback", existing_app_ids=existing_app_ids, app_map=app_map)

    def _collect_single_source(
        self,
        source_id: str,
        *,
        existing_app_ids: Iterable[str] | None = None,
        app_map: Dict[str, Any] | None = None,
    ) -> List[Dict[str, Any]]:
        for source in self._sources(scan_profile="full"):
            if getattr(source, "source_id", "") == source_id:
                return [self._normalize_candidate(item, source_override=source_id) for item in source.collect(
                    existing_app_ids=existing_app_ids,
                    app_map=app_map,
                )]
        return []

    def _source_stats(self, items: Iterable[Dict[str, Any]]) -> Dict[str, int]:
        rows = list(items)
        with_path = len([item for item in rows if str(item.get("target_path", "")).strip()])
        result = {
            "total": len(rows),
            "with_path": with_path,
            "no_path": len(rows) - with_path,
        }
        if any(str(item.get("shortcut_kind", "")).strip() for item in rows):
            result.update(
                {
                    "lnk_total": len([item for item in rows if item.get("shortcut_kind") == "lnk"]),
                    "url_total": len([item for item in rows if item.get("shortcut_kind") == "url"]),
                    "lnk_resolved": len([
                        item for item in rows
                        if item.get("shortcut_kind") == "lnk"
                        and item.get("shortcut_parse_status") == "resolved"
                    ]),
                    "lnk_failed": len([
                        item for item in rows
                        if item.get("shortcut_kind") == "lnk"
                        and item.get("shortcut_parse_status") == "failed"
                    ]),
                    "lnk_timeout": len([
                        item for item in rows
                        if item.get("shortcut_kind") == "lnk"
                        and item.get("shortcut_parse_status") == "timeout"
                    ]),
                }
            )
        return result

    def _category_counts(self, items: Iterable[Dict[str, Any]]) -> Dict[str, int]:
        counts = Counter(str(item.get("category", "unknown")).strip().lower() or "unknown" for item in items)
        visibility_counts = Counter(str(item.get("visibility", "main")).strip().lower() or "main" for item in items)
        result = {
            "normal_app": counts.get("normal_app", 0),
            "platform_app": counts.get("platform_app", 0),
            "system_app": counts.get("system_app", 0),
            "admin_tool": counts.get("admin_tool", 0),
            "runtime_env": counts.get("runtime_env", 0),
            "driver_or_runtime": counts.get("driver", 0),
            "installer_bundle": counts.get("installer_bundle", 0),
            "system_core": counts.get("system_core", 0),
            "diagnostics_only": visibility_counts.get("diagnostics_only", 0),
        }
        for name, value in counts.items():
            result.setdefault(name, value)
        return result

    def filter_candidates(self, candidates: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
        filtered, _diagnostics = self.filter_candidates_with_diagnostics(candidates)
        return filtered

    def filter_candidates_with_diagnostics(self, candidates: Iterable[Dict[str, Any]]) -> tuple[List[Dict[str, Any]], Dict[str, int]]:
        blocked_title_keywords = {
            "help",
            "website",
            "readme",
            "documentation",
            "manual",
        }
        filtered: List[Dict[str, Any]] = []
        rows = list(candidates)
        diagnostics = {
            "filter_before_total": len(rows),
            "filter_after_total": 0,
            "filter_removed_by_category": 0,
            "filter_removed_by_keyword": 0,
            "filter_removed_by_registry_residual": 0,
            "filter_removed_by_title_keyword": 0,
            "filter_removed_by_windows_path": 0,
            "filter_removed_by_missing_title": 0,
            "filter_removed_by_installer_bundle": 0,
            "filter_removed_by_driver_or_runtime": 0,
            "filter_removed_by_admin_tool": 0,
            "filter_removed_by_missing_launch_target": 0,
            "filter_removed_by_unsafe_registry_entry": 0,
            "filter_removed_by_web_url": 0,
            "filter_removed_by_placeholder_title": 0,
            "path_missing_after_normalize": 0,
        }

        for item in rows:
            normalized = self._normalize_candidate(item)
            title = str(normalized.get("title", "")).strip()
            title_lower = title.lower()
            category = str(normalized.get("category", "unknown")).strip().lower()
            candidate_kind = str(normalized.get("candidate_kind", "weak_missing_path")).strip().lower()
            launch_target_kind = str(normalized.get("launch_target_kind", "missing")).strip().lower()
            visibility = str(normalized.get("visibility", "main")).strip().lower()
            path_status = str(normalized.get("path_status", "")).strip().lower()
            registry_entry_status = str(normalized.get("registry_entry_status", "")).strip().lower()
            if not title:
                diagnostics["filter_removed_by_missing_title"] += 1
                continue
            if "${{" in title or "}}" in title:
                diagnostics["filter_removed_by_placeholder_title"] += 1
                continue
            if any(keyword in title_lower for keyword in blocked_title_keywords):
                diagnostics["filter_removed_by_title_keyword"] += 1
                continue
            if registry_entry_status == "unsafe_registry_entry":
                diagnostics["filter_removed_by_unsafe_registry_entry"] = diagnostics.get("filter_removed_by_unsafe_registry_entry", 0) + 1
                continue
            if path_status == "registry_residual":
                diagnostics["filter_removed_by_registry_residual"] += 1
                continue
            if visibility == "diagnostics_only":
                if launch_target_kind == "web_url":
                    diagnostics["filter_removed_by_web_url"] += 1
                elif candidate_kind == "installer_bundle" or category == "installer_bundle":
                    diagnostics["filter_removed_by_installer_bundle"] += 1
                elif category == "admin_tool":
                    diagnostics["filter_removed_by_admin_tool"] = diagnostics.get("filter_removed_by_admin_tool", 0) + 1
                elif candidate_kind == "driver_or_runtime" or category in {"runtime_env", "driver", "system_core"}:
                    diagnostics["filter_removed_by_driver_or_runtime"] += 1
                else:
                    diagnostics["filter_removed_by_category"] += 1
                continue
            if normalized.get("target_path") and launch_target_kind in {"local_exe", "local_file"}:
                target_path = Path(str(normalized.get("target_path", "")).strip())
                if not target_path.exists():
                    normalized["target_path"] = ""
                    normalized["candidate_kind"] = "weak_missing_path"
                    normalized["path_status"] = "missing"
                    normalized["candidate_strength"] = "weak"
                    diagnostics["path_missing_after_normalize"] += 1
                    diagnostics["filter_removed_by_missing_launch_target"] += 1
                    continue
            filtered.append(normalized)

        diagnostics["filter_after_total"] = len(filtered)
        return filtered, diagnostics

    def dedupe_candidates(self, candidates: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
        deduped, _diagnostics = self.dedupe_candidates_with_diagnostics(candidates)
        return deduped

    def dedupe_candidates_with_diagnostics(self, candidates: Iterable[Dict[str, Any]]) -> tuple[List[Dict[str, Any]], Dict[str, int]]:
        source_priority = {
            # Confirmed apps are merged outside this candidate dedupe step, so they remain above every source here.
            "app_map": 0,
            "app_map_fallback": 0,
            "system_app_seed": 1,
            "start_menu_shortcut": 2,
            "desktop_shortcut": 3,
            "appx_installed_apps": 4,
            "uninstall_registry": 5,
            "steam_client_probe": 6,
            "unknown": 9,
        }

        deduped: Dict[str, Dict[str, Any]] = {}

        diagnostics = {
            "duplicate_lower_priority": 0,
            "duplicate_replaced_by_higher_priority": 0,
            "duplicate_merged_target_path": 0,
            "duplicate_merged_launch_target": 0,
            "duplicate_merged_steam_local": 0,
        }

        primary_fields = {
            "title",
            "target_path",
            "launch_target_kind",
            "launch_target_raw",
            "launch_args",
            "category",
            "candidate_kind",
            "visibility",
            "icon_source_path",
            "icon_kind",
            "path_status",
            "platform",
            "platform_object_type",
            "platform_object_id",
            "route_confidence",
            "risk_hint",
            "sensitivity",
            "canonical_app_id",
            "discover_source",
        }

        supplemental_fields = {
            "publisher",
            "version",
            "install_dir",
            "uninstall_string",
            "registry_key",
            "source_detail",
            "identity_source",
            "launch_source",
            "registry_entry_status",
        }

        def merge_candidates(current: Dict[str, Any], incoming: Dict[str, Any]) -> Dict[str, Any]:
            current_priority = source_priority.get(str(current.get("discover_source", "unknown")), 9)
            incoming_priority = source_priority.get(str(incoming.get("discover_source", "unknown")), 9)

            primary = incoming if incoming_priority < current_priority else current
            secondary = current if primary is incoming else incoming

            merged = dict(primary)

            for key in supplemental_fields:
                if not merged.get(key) and secondary.get(key):
                    merged[key] = secondary.get(key)

            for key, value in secondary.items():
                if key in primary_fields or key in supplemental_fields:
                    continue
                if not merged.get(key) and value:
                    merged[key] = value

            return merged

        def title_keys(value: str) -> list[str]:
            """
            为标题生成多个匹配 key。

            例如：
            - "Pummel Party" -> ["pummel party", "pummelparty"]
            - "Black Myth: Wukong" -> ["black myth wukong", "blackmythwukong"]

            这样可以处理 Steam 标题和本地 exe / 文件夹名之间的空格差异。
            """
            normal = _normalize_title_key(value)
            if not normal:
                return []

            compact = normal.replace(" ", "")
            if compact and compact != normal:
                return [normal, compact]

            return [normal]

        normalized_items: list[Dict[str, Any]] = []
        steam_key_by_title: dict[str, str] = {}

        # ===== 第一轮：只做预扫描 =====
        # 目标：找到所有 Steam 协议入口，并建立：
        # title_key -> steam::<appid>
        #
        # 例如：
        # Pummel Party + steam://rungameid/880940
        # 会得到：
        # "pummel party" -> "steam::880940"
        # "pummelparty" -> "steam::880940"
        for item in candidates:
            normalized = self._normalize_candidate(item)
            normalized_items.append(normalized)

            title = str(normalized.get("title", ""))
            platform = str(normalized.get("platform", "")).strip().lower()
            platform_object_id = str(normalized.get("platform_object_id", "")).strip().lower()
            launch_raw = str(normalized.get("launch_target_raw", "")).strip().lower()

            steam_app_id = platform_object_id or _steam_app_id_from_raw(launch_raw)

            if not steam_app_id:
                continue

            if platform == "steam" or launch_raw.startswith("steam://"):
                for key in title_keys(title):
                    steam_key_by_title[key] = f"steam::{steam_app_id}"

        # ===== 第二轮：正式去重 =====
        # 目标：
        # - 普通软件仍按原来的 _candidate_dedupe_key 去重；
        # - 如果是 steamapps/common 下的本地 exe，并且标题能匹配 Steam 协议入口，
        #   则强制使用同一个 steam::<appid> 作为 dedupe_key。
        for normalized in normalized_items:
            dedupe_key = self._candidate_dedupe_key(normalized)

            title = str(normalized.get("title", ""))
            target_path = str(normalized.get("target_path", "")).strip()
            install_dir = str(normalized.get("install_dir", "")).strip()

            is_local_steam_game = _is_steam_common_path(target_path) or _is_steam_common_path(install_dir)

            if is_local_steam_game:
                for key in title_keys(title):
                    steam_key = steam_key_by_title.get(key)
                    if steam_key:
                        dedupe_key = steam_key
                        diagnostics["duplicate_merged_steam_local"] += 1
                        break

            current = deduped.get(dedupe_key)

            if current is None:
                deduped[dedupe_key] = normalized
                continue

            current_priority = source_priority.get(
                str(current.get("discover_source", "unknown")),
                9,
            )
            next_priority = source_priority.get(
                str(normalized.get("discover_source", "unknown")),
                9,
            )

            # 数字越小，来源优先级越高。
            # 例如 system_app_seed 优先于 uninstall_registry。
            if next_priority < current_priority:
                deduped[dedupe_key] = merge_candidates(current, normalized)
                diagnostics["duplicate_replaced_by_higher_priority"] += 1
                continue

            # 当前对象优先级更高或相同：
            # 保留 current 作为主对象，同时用 normalized 补充 publisher/version/install_dir 等信息。
            deduped[dedupe_key] = merge_candidates(current, normalized)
            diagnostics["duplicate_lower_priority"] += 1

        return (
            sorted(
                deduped.values(),
                key=lambda item: (item.get("title", "").lower(), item.get("app_id", "")),
            ),
            diagnostics,
        )

    def discover_candidates(
        self,
        *,
        app_map: Dict[str, Any],
        existing_app_ids: Iterable[str] | None = None,
    ) -> List[Dict[str, Any]]:
        items, _diagnostics = self.discover_candidates_with_diagnostics(
            app_map=app_map,
            existing_app_ids=existing_app_ids,
        )
        return items

    def discover_candidates_with_diagnostics(
        self,
        *,
        app_map: Dict[str, Any],
        existing_app_ids: Iterable[str] | None = None,
        progress_callback: Callable[[dict[str, Any]], None] | None = None,
        scan_profile: str = "quick",
    ) -> tuple[List[Dict[str, Any]], Dict[str, Any]]:
        profile = str(scan_profile or "quick").strip().lower()
        if profile not in {"quick", "full"}:
            profile = "quick"
        existing_ids = {str(item).strip() for item in (existing_app_ids or []) if str(item).strip()}
        source_items: Dict[str, List[Dict[str, Any]]] = {}
        source_raw_counts: Dict[str, int] = {}
        source_durations_ms: Dict[str, int] = {}
        raw_candidates: List[Dict[str, Any]] = []
        self._emit_progress(progress_callback, stage="scan_started", message="scan started", stats={"raw_total": 0}, percent=2)
        for source in self._sources(scan_profile=profile):
            self._emit_progress(
                progress_callback,
                stage=f"source.{source.source_id}.started",
                message=f"source {source.source_id} started",
                stats={"raw_total": len(raw_candidates)},
            )
            source_started_at = time.perf_counter()
            collected = source.collect(existing_app_ids=existing_ids, app_map=app_map)
            source_duration_ms = int((time.perf_counter() - source_started_at) * 1000)
            source_durations_ms[source.source_id] = source_duration_ms
            source_raw_counts[source.source_id] = len(collected)
            normalized = [self._normalize_candidate(item, source_override=source.source_id) for item in collected]
            source_items[source.source_id] = normalized
            raw_candidates.extend(normalized)
            self._emit_progress(
                progress_callback,
                stage=f"source.{source.source_id}.done",
                message=f"source {source.source_id} done",
                stats={
                    "raw_total": len(raw_candidates),
                    f"{source.source_id}_total": len(normalized),
                    f"{source.source_id}_duration_ms": source_duration_ms,
                },
            )
        if profile == "full":
            steam_started_at = time.perf_counter()
            steam_client_items = [
                self._normalize_candidate(item, source_override="steam_client_probe")
                for item in self._steam_client_candidates()
            ]
            steam_duration_ms = int((time.perf_counter() - steam_started_at) * 1000)
            if steam_client_items:
                source_durations_ms["steam_client_probe"] = steam_duration_ms
                source_raw_counts["steam_client_probe"] = len(steam_client_items)
                source_items["steam_client_probe"] = steam_client_items
                raw_candidates.extend(steam_client_items)
                self._emit_progress(
                    progress_callback,
                    stage="source.steam_client_probe.done",
                    message="source steam_client_probe done",
                    stats={
                        "raw_total": len(raw_candidates),
                        "steam_client_probe_total": len(steam_client_items),
                        "steam_client_probe_duration_ms": steam_duration_ms,
                    },
                )
        self._emit_progress(progress_callback, stage="filtering", message="filtering", stats={"raw_total": len(raw_candidates)}, percent=60)
        filtered, filter_diagnostics = self.filter_candidates_with_diagnostics(raw_candidates)
        self._emit_progress(
            progress_callback,
            stage="dedupe",
            message="dedupe",
            stats={
                "raw_total": len(raw_candidates),
                "filter_after_total": len(filtered),
            },
            percent=78,
        )
        deduped, dedupe_diagnostics = self.dedupe_candidates_with_diagnostics(filtered)
        result = [item for item in deduped if item.get("app_id") not in existing_ids]
        kept_by_source = Counter(str(item.get("discover_source", "unknown")) for item in filtered)
        final_by_source = Counter(str(item.get("discover_source", "unknown")) for item in deduped)
        sources_diagnostics: Dict[str, Dict[str, int]] = {}
        for name, items in source_items.items():
            normalized_count = len(items)
            kept_count = int(kept_by_source.get(name, 0))
            final_count = int(final_by_source.get(name, 0))
            sources_diagnostics[name] = {
                "raw": int(source_raw_counts.get(name, normalized_count)),
                "after_normalize": normalized_count,
                "removed": max(normalized_count - kept_count, 0),
                "kept": kept_count,
                "final": final_count,
                "duration_ms": int(source_durations_ms.get(name, 0)),
                **self._source_stats(items),
            }
        diagnostics = {
            "scan_profile": profile,
            "sources": sources_diagnostics,
            "pipeline": {
                "raw_total": len(raw_candidates),
                **filter_diagnostics,
                "dedupe_before_total": len(filtered),
                "dedupe_after_total": len(deduped),
                "dedupe_with_path": len([item for item in deduped if str(item.get("target_path", "")).strip()]),
                **dedupe_diagnostics,
            },
            "categories": {
                "raw": self._category_counts(raw_candidates),
                "filtered": self._category_counts(filtered),
                "deduped": self._category_counts(deduped),
            },
        }
        self._emit_progress(
            progress_callback,
            stage="discover_completed",
            message="discovery completed",
            stats={
                "raw_total": len(raw_candidates),
                "filter_after_total": len(filtered),
                "dedupe_after_total": len(deduped),
            },
            percent=88,
        )
        return result, diagnostics

    def _candidate_dedupe_key(self, item: Dict[str, Any]) -> str:
        """
        候选软件去重 key。
        优先级：
        1. canonical_app_id：同一个软件的多来源统一身份
        2. steam platform_object_id：Steam 同一个 AppID 统一
        3. target_path：真实本地路径
        4. launch_target_raw：协议/AppX/Shell 启动入口
        5. app_id/title：最后兜底
        """
        canonical_app_id = str(item.get("canonical_app_id", "")).strip().lower()
        if canonical_app_id:
            return f"canonical::{canonical_app_id}"

        platform = str(item.get("platform", "")).strip().lower()
        platform_object_id = str(item.get("platform_object_id", "")).strip().lower()
        if platform == "steam" and platform_object_id:
            return f"steam::{platform_object_id}"

        target_path = (
            str(item.get("target_path", ""))
            .strip()
            .strip('"')
            .replace("/", "\\")
            .lower()
        )
        if target_path:
            return f"path::{target_path}"

        launch_target_raw = (
            str(item.get("launch_target_raw", ""))
            .strip()
            .strip('"')
            .lower()
        )
        if launch_target_raw:
            return f"launch::{launch_target_raw}"

        app_id = str(item.get("app_id", "")).strip().lower()
        title = str(item.get("title", "")).strip().lower()
        return f"name::{app_id or title}"

    def _normalize_candidate(self, item: Dict[str, Any], *, source_override: str | None = None) -> Dict[str, Any]:
        payload = dict(item or {})
        title = str(payload.get("title", payload.get("app_id", ""))).strip()
        app_id = str(payload.get("app_id", "")).strip() or _stable_app_id(title)
        canonical_app_id = _canonical_app_id({**payload, "title": title, "app_id": app_id})
        detect_input = dict(payload)
        detect_input["title"] = title
        detect_input["app_id"] = app_id
        detect_input["canonical_app_id"] = canonical_app_id
        if source_override:
            detect_input["discover_source"] = source_override
        detection = self.detection_gate.detect(detect_input)
        normalized = {
            "app_id": app_id,
            "canonical_app_id": canonical_app_id,
            "title": title or app_id or "-",
            "target_path": str(payload.get("target_path", "")).strip(),
            "launch_args": list(payload.get("launch_args", []) or []),
            "enabled": bool(payload.get("enabled", False)),
            "allow_launch": bool(payload.get("allow_launch", False)),
            "allow_attach": bool(payload.get("allow_attach", False)),
            "allow_close": bool(payload.get("allow_close", False)),
            "connector_id": str(payload.get("connector_id", "windows_shell")).strip() or "windows_shell",
            "discovered": bool(payload.get("discovered", bool(payload.get("target_path", "")))),
            "discover_source": str(source_override or payload.get("discover_source", "unknown")).strip() or "unknown",
            "category": detection.category,
            "candidate_kind": detection.candidate_kind,
            "visibility": detection.visibility,
            "actionability": detection.actionability,
            "route_confidence": detection.route_confidence,
            "risk_tags": list(detection.risk_tags),
            "launch_target_kind": detection.launch_target_kind,
            "launch_target_raw": detection.launch_target_raw,
            "platform": detection.platform,
            "platform_object_type": detection.platform_object_type,
            "platform_object_id": detection.platform_object_id,
            "install_dir": detection.install_dir,
            "entry_path": detection.entry_path,
            "icon_source_path": detection.icon_source_path,
            "icon_kind": detection.icon_kind,
            "candidate_strength": detection.candidate_strength,
            "path_status": detection.path_status,
            "visibility_reason": detection.visibility_reason,
            "identity_source": str(payload.get("identity_source", "")).strip(),
            "launch_source": str(payload.get("launch_source", "")).strip(),
            "registry_entry_status": str(payload.get("registry_entry_status", "")).strip(),
            "risk_hint": str(payload.get("risk_hint", "")).strip(),
            "sensitivity": str(payload.get("sensitivity", "")).strip(),
            "publisher": str(payload.get("publisher", "")).strip(),
            "version": str(payload.get("version", "")).strip(),
            "uninstall_string": str(payload.get("uninstall_string", "")).strip(),
            "registry_key": str(payload.get("registry_key", "")).strip(),
            "source_detail": str(payload.get("source_detail", "")).strip(),
            "canonical_app_id": canonical_app_id,
            "risk_hint": str(payload.get("risk_hint", "")).strip(),
            "sensitivity": str(payload.get("sensitivity", "")).strip(),
            "publisher": str(payload.get("publisher", "")).strip(),
            "version": str(payload.get("version", "")).strip(),
            "uninstall_string": str(payload.get("uninstall_string", "")).strip(),
            "registry_key": str(payload.get("registry_key", "")).strip(),
            "source_detail": str(payload.get("source_detail", "")).strip(),
            "identity_source": str(payload.get("identity_source", "")).strip(),
            "launch_source": str(payload.get("launch_source", "")).strip(),
            "registry_entry_status": str(payload.get("registry_entry_status", "")).strip(),
            "shortcut_kind": str(payload.get("shortcut_kind", "")).strip(),
            "shortcut_parse_status": str(payload.get("shortcut_parse_status", "")).strip(),
        }
        return normalized
    def _steam_root_candidates(self) -> list[Path]:
        result: list[Path] = []

        for raw in (
            r"C:\Program Files (x86)\Steam",
            r"C:\Program Files\Steam",
            r"D:\Steam",
            r"E:\Steam",
            r"F:\Steam",
            r"D:\steam",
            r"E:\steam",
            r"F:\steam",
        ):
            path = Path(raw)
            if path.exists():
                result.append(path)

        try:
            import winreg  # type: ignore

            registry_keys = [
                (winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam", "SteamPath"),
                (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam", "InstallPath"),
                (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Valve\Steam", "InstallPath"),
            ]

            for hive, subkey, value_name in registry_keys:
                try:
                    with winreg.OpenKey(hive, subkey) as key:
                        value, _value_type = winreg.QueryValueEx(key, value_name)
                    path = Path(str(value))
                    if path.exists():
                        result.append(path)
                except Exception:
                    continue
        except Exception:
            pass

        unique: list[Path] = []
        seen: set[str] = set()
        for path in result:
            normalized = str(path).lower()
            if normalized in seen:
                continue
            seen.add(normalized)
            unique.append(path)
        return unique


    def _steam_client_candidates(self) -> list[Dict[str, Any]]:
        result: list[Dict[str, Any]] = []

        for steam_root in self._steam_root_candidates():
            steam_exe = steam_root / "steam.exe"
            if not steam_exe.exists():
                continue

            result.append(
                {
                    "app_id": "steam_client",
                    "title": "Steam",
                    "target_path": str(steam_exe),
                    "entry_path": str(steam_exe),
                    "install_dir": str(steam_root),
                    "launch_target_kind": "local_exe",
                    "launch_target_raw": str(steam_exe),
                    "platform": "steam",
                    "platform_object_type": "client",
                    "platform_object_id": "steam",
                    "discover_source": "steam_client_probe",
                    "connector_id": "windows_shell",
                }
            )

        return result
