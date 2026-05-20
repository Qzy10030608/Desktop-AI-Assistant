from __future__ import annotations

import string
import time
from pathlib import Path
from typing import Any
import json
import re

EVIDENCE_SCHEMA_VERSION = "jiuchasi_evidence_packet_v1"


class EvidenceBroker:
    """
    天庭·纠察司：证据查询中介。

    原则：
    - 只查询，不执行。
    - 不授予权限。
    - 不直接调用 HostAdapter。
    - 返回给 LLM/决策层的是 evidence packet。
    """

    def __init__(self, project_root: str | Path | None = None) -> None:
        self.project_root = Path(project_root or Path(__file__).resolve().parents[4]).expanduser().resolve()

    def collect(
        self,
        *,
        user_text: str,
        action_hint: str = "",
        target_normalized: str = "",
        needs: list[str] | None = None,
    ) -> dict[str, Any]:
        need_set = set(needs or [])
        if not need_set:
            need_set = self._infer_needs(
                user_text=user_text,
                action_hint=action_hint,
                target_normalized=target_normalized,
            )

        packet = {
            "schema_version": EVIDENCE_SCHEMA_VERSION,
            "created_at_ts": int(time.time()),
            "user_text": str(user_text or ""),
            "action_hint": str(action_hint or ""),
            "target_normalized": str(target_normalized or ""),
            "needs": sorted(need_set),
            "providers": {},
        }

        if "software_governance" in need_set:
            packet["providers"]["software_governance"] = self._software_governance()

        if "file_roots" in need_set:
            packet["providers"]["file_roots"] = self._file_roots()

        if "file_candidates" in need_set:
            packet["providers"]["file_candidates"] = self._file_candidates(
                user_text=user_text,
                action_hint=action_hint,
                target_normalized=target_normalized,
            )

        if "running_apps" in need_set:
            packet["providers"]["running_apps"] = self._running_apps()

        if "memory" in need_set:
            packet["providers"]["memory"] = self._memory_terms(user_text=user_text)

        if "system_skill" in need_set:
            packet["providers"]["system_skill"] = self._system_skill(user_text=user_text)

        return packet

    def _infer_needs(
        self,
        *,
        user_text: str,
        action_hint: str,
        target_normalized: str,
    ) -> set[str]:
        text = f"{user_text} {action_hint} {target_normalized}".lower()
        needs: set[str] = set()

        if "app." in action_hint or "软件" in text or "程序" in text or "应用" in text:
            needs.add("software_governance")

        if "folder." in action_hint or "file." in action_hint or "盘" in text or "目录" in text or "文件夹" in text:
            needs.add("file_roots")
            needs.add("file_candidates")
        if "close" in action_hint or "关闭" in text or "关掉" in text:
            needs.add("running_apps")

        if "记得" in text or "上次" in text or "是不是" in text:
            needs.add("memory")

        if "几点" in text or "几号" in text or "星期" in text or "天气" in text or "日程" in text:
            needs.add("system_skill")

        if not needs:
            needs.add("software_governance")

        return needs

    def _software_governance(self) -> dict[str, Any]:
        labels: list[str] = []
        rows: list[dict[str, Any]] = []
        sources: list[str] = []
        errors: list[dict[str, str]] = []

        # 第一来源：软件治理区视图缓存。
        # 这是 UI 当前看到的软件列表，优先级最高。
        try:
            from services.desktop.software_view_cache_service import SoftwareViewCacheService

            state = SoftwareViewCacheService(self.project_root).read()
            raw_rows = state.get("rows", []) if isinstance(state, dict) else []

            if isinstance(raw_rows, list):
                for row in raw_rows[:300]:
                    if not isinstance(row, dict):
                        continue

                    safe_row = self._safe_software_row(
                        row,
                        source="software_view_cache",
                    )
                    rows.append(safe_row)

                    for key in ("title", "name", "app_id", "canonical_app_id"):
                        value = safe_row.get(key, "").strip()
                        if value:
                            labels.append(value)

            if labels:
                sources.append("software_view_cache")

        except Exception as exc:
            errors.append(
                {
                    "source": "software_view_cache",
                    "error_kind": exc.__class__.__name__,
                    "error": str(exc),
                }
            )

        # 第二来源：吏部软件账本。
        # 当软件治理区视图缓存为空时，仍然允许纠察司读取候选/可信账本作为 evidence。
        # 注意：这里只读 label，不返回 exe/process/backend，不授予权限，不执行。
        if not labels:
            try:
                from services.desktop.qin.libu.software_ledger import SoftwareCandidateBook, SoftwareTrustedBook

                for source_name, book in (
                    ("software_trusted_book", SoftwareTrustedBook(self.project_root)),
                    ("software_candidate_book", SoftwareCandidateBook(self.project_root)),
                ):
                    for record in book.read():
                        if hasattr(record, "to_dict"):
                            item = record.to_dict()
                        elif isinstance(record, dict):
                            item = record
                        else:
                            continue

                        safe_row = self._safe_software_row(
                            item,
                            source=source_name,
                        )
                        rows.append(safe_row)

                        for key in ("title", "name", "app_id", "canonical_app_id"):
                            value = safe_row.get(key, "").strip()
                            if value:
                                labels.append(value)

                    sources.append(source_name)

            except Exception as exc:
                errors.append(
                    {
                        "source": "software_ledger",
                        "error_kind": exc.__class__.__name__,
                        "error": str(exc),
                    }
                )

        deduped_labels = _dedupe(labels)

        return {
            "ok": True,
            "label_count": len(deduped_labels),
            "labels": deduped_labels[:300],
            "rows": rows[:300],
            "sources": sources,
            "errors": errors,
        }

    def _safe_software_row(
        self,
        row: dict[str, Any],
        *,
        source: str = "",
    ) -> dict[str, Any]:
        item = row if isinstance(row, dict) else {}

        return {
            "title": str(item.get("title", "") or ""),
            "name": str(item.get("name", "") or ""),
            "app_id": str(item.get("app_id", "") or ""),
            "canonical_app_id": str(item.get("canonical_app_id", "") or ""),
            "permission_state": str(item.get("permission_state", "") or ""),
            "visible": bool(item.get("visible", True)),
            "source": str(source or ""),
        }
    
    def _file_roots(self) -> dict[str, Any]:
        roots: list[dict[str, Any]] = []

        for letter in string.ascii_uppercase:
            path = Path(f"{letter}:\\")
            try:
                exists = path.exists()
            except Exception:
                exists = False

            if exists:
                roots.append(
                    {
                        "root_id": f"{letter.lower()}_drive",
                        "label": f"{letter}盘",
                        "path": f"{letter}:\\",
                        "exists": True,
                    }
                )

        return {
            "ok": True,
            "roots": roots,
            "root_count": len(roots),
        }

    def _file_candidates(
        self,
        *,
        user_text: str,
        action_hint: str,
        target_normalized: str,
    ) -> dict[str, Any]:
        query = self._file_query_text(user_text=user_text, target_normalized=target_normalized)
        root_scope = self._extract_drive_root(f"{user_text} {target_normalized}")
        want_folder = str(action_hint or "").startswith("folder.")
        want_file = str(action_hint or "").startswith("file.")

        if not query:
            return {
                "ok": True,
                "query": "",
                "root_scope": root_scope,
                "candidate_count": 0,
                "candidates": [],
                "source": "host_file_view_cache",
                "reason": "empty_query",
            }

        cache_dir = self.project_root / "data" / "runtime" / "desktop" / "file_view_cache" / "host"
        candidates: list[dict[str, Any]] = []
        scanned_cache_files = 0

        try:
            cache_files = sorted(cache_dir.glob("cache_*.json")) if cache_dir.exists() else []
        except Exception:
            cache_files = []

        query_key = self._norm_text(query)
        root_key = root_scope.casefold() if root_scope else ""

        for cache_path in cache_files[:300]:
            try:
                data = json.loads(cache_path.read_text(encoding="utf-8"))
            except Exception:
                continue

            if not isinstance(data, dict):
                continue

            scanned_cache_files += 1
            current_path = str(data.get("current_path", "") or data.get("root_path", "") or "")
            if root_key and current_path and not current_path.casefold().startswith(root_key):
                continue

            rows = data.get("rows", [])
            if not isinstance(rows, list):
                continue

            for row in rows:
                if not isinstance(row, dict):
                    continue

                name = str(row.get("name", "") or "").strip()
                path = str(row.get("path", "") or "").strip()
                object_type = str(row.get("object_type", "") or row.get("type", "") or "").strip().lower()
                is_dir = bool(row.get("is_dir", object_type in {"directory", "folder"}))

                if want_folder and not is_dir:
                    continue
                if want_file and is_dir:
                    continue

                name_key = self._norm_text(name)
                path_key = self._norm_text(path)

                if not name_key and not path_key:
                    continue

                score = 0.0
                reason = ""

                if query_key == name_key:
                    score = 0.96
                    reason = "exact_name_match"
                elif query_key and query_key in name_key:
                    score = 0.88
                    reason = "contains_name_match"
                elif query_key and query_key in path_key:
                    score = 0.78
                    reason = "contains_path_match"

                if score <= 0:
                    continue

                if root_scope:
                    score = min(0.99, score + 0.03)

                candidates.append(
                    {
                        "candidate_id": f"file_{len(candidates) + 1:03d}",
                        "display_index": len(candidates) + 1,
                        "label": name or path,
                        "name": name,
                        "target_path": path,
                        "path": path,
                        "kind": "folder" if is_dir else "file",
                        "object_type": "directory" if is_dir else "file",
                        "source": "host_file_view_cache",
                        "confidence": round(score, 3),
                        "match_reason": reason,
                        "root_scope": root_scope,
                    }
                )

        candidates.sort(key=lambda item: float(item.get("confidence", 0.0)), reverse=True)

        return {
            "ok": True,
            "query": query,
            "root_scope": root_scope,
            "candidate_count": len(candidates),
            "candidates": candidates[:20],
            "source": "host_file_view_cache",
            "scanned_cache_files": scanned_cache_files,
        }


    def _file_query_text(self, *, user_text: str, target_normalized: str) -> str:
        text = str(target_normalized or user_text or "").strip()
        if not text:
            return ""

        compact = text.replace(" ", "").replace("　", "")

        # 去掉 “G盘的 / G盘 / G:\” 这种范围词，保留真正目标名
        compact = re.sub(r"(?i)^[a-z][:：]?[\\/]+", "", compact)
        compact = re.sub(r"(?i)^[a-z]盘的?", "", compact)

        for suffix in ("文件夹", "目录", "根目录", "根路径", "路径"):
            if compact.endswith(suffix):
                compact = compact[: -len(suffix)]

        for prefix in ("打开", "开启", "进入", "显示", "定位到", "请", "帮我", "给我"):
            if compact.startswith(prefix):
                compact = compact[len(prefix):]

        return compact.strip()


    def _extract_drive_root(self, text: str) -> str:
        raw = str(text or "").strip()
        if not raw:
            return ""

        compact = raw.replace(" ", "").replace("　", "")

        match = re.search(r"(?i)([a-z])[:：]?盘", compact)
        if match:
            return f"{match.group(1).upper()}:\\"

        match = re.search(r"(?i)\b([a-z])[:：][\\/]", compact)
        if match:
            return f"{match.group(1).upper()}:\\"

        return ""


    def _norm_text(self, text: str) -> str:
        value = str(text or "").casefold()
        keep: list[str] = []
        for char in value:
            if char.isalnum() or "\u4e00" <= char <= "\u9fff":
                keep.append(char)
        return "".join(keep)

    def _running_apps(self) -> dict[str, Any]:
        # 第一版先不做真实进程扫描，避免绕过治理链。
        # 后续可以接 running_apps provider 或黑冰台 running document resolver。
        return {
            "ok": False,
            "reason": "running_apps_provider_not_connected",
            "items": [],
        }

    def _memory_terms(self, *, user_text: str) -> dict[str, Any]:
        # 第一版只保留接口。长期记忆晋升必须由确认 + 执行成功后再做。
        return {
            "ok": False,
            "reason": "memory_provider_not_connected",
            "query": str(user_text or ""),
            "terms": [],
        }

    def _system_skill(self, *, user_text: str) -> dict[str, Any]:
        return {
            "ok": True,
            "query": str(user_text or ""),
            "available_skills": [
                "system_info.read_datetime",
                "weather.read_current",
                "calendar.read_events",
            ],
        }


def _dedupe(items: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()

    for item in items:
        text = str(item or "").strip()
        key = text.casefold()
        if not text or key in seen:
            continue
        seen.add(key)
        result.append(text)

    return result
