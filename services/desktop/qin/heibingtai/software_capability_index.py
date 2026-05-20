from __future__ import annotations

from pathlib import Path
from typing import Any

from services.desktop.qin.libu.software_ledger import SoftwareCandidateBook, SoftwareTrustedBook
from services.desktop.software_view_cache_service import SoftwareViewCacheService


class SoftwareCapabilityIndex:
    """Build a read-only app_kind capability map from existing software governance data."""

    MULTI_DOCUMENT_APP_KINDS = {
        "vscode",
        "office_word",
        "office_excel",
        "office_powerpoint",
        "wps_writer",
        "wps_spreadsheet",
        "wps_presentation",
    }

    def __init__(self, project_root: str | Path | None = None) -> None:
        self.project_root = Path(project_root or Path(__file__).resolve().parents[4]).expanduser().resolve()
        self.candidate_book = SoftwareCandidateBook(self.project_root)
        self.trusted_book = SoftwareTrustedBook(self.project_root)
        self.view_cache = SoftwareViewCacheService(self.project_root)

    def build_index(self) -> dict[str, dict[str, Any]]:
        rows = self._collect_rows()
        index: dict[str, dict[str, Any]] = {}

        for row in rows:
            if not isinstance(row, dict):
                continue
            capability = self._capability_from_row(row)
            app_kind = str(capability.get("app_kind", "") or "").strip().lower()
            if not app_kind:
                continue

            existing = index.get(app_kind)
            if existing is None or self._rank(capability) > self._rank(existing):
                index[app_kind] = capability

        self._ensure_builtin_fallbacks(index)
        return index

    def get(self, app_kind: str) -> dict[str, Any] | None:
        return self.build_index().get(str(app_kind or "").strip().lower())

    def resolve_first_available(self, app_kinds: list[str]) -> dict[str, Any] | None:
        index = self.build_index()
        for app_kind in app_kinds:
            key = str(app_kind or "").strip().lower()
            item = index.get(key)
            if item and bool(item.get("available", False)):
                return item
        return None

    def _collect_rows(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []

        try:
            for item in self.trusted_book.read():
                payload = item.to_dict()
                payload["source"] = "trusted"
                rows.append(payload)
        except Exception:
            pass

        try:
            for item in self.candidate_book.read():
                payload = item.to_dict()
                payload["source"] = payload.get("source") or "candidate"
                rows.append(payload)
        except Exception:
            pass

        try:
            cache = self.view_cache.read()
            cache_rows = cache.get("rows", [])
            if isinstance(cache_rows, list):
                for item in cache_rows:
                    if isinstance(item, dict):
                        payload = dict(item)
                        payload["source"] = payload.get("source") or "cache"
                        rows.append(payload)
        except Exception:
            pass

        return rows

    def _capability_from_row(self, row: dict[str, Any]) -> dict[str, Any]:
        title = str(row.get("title", row.get("name", "")) or "")
        target_path = str(
            row.get("manual_target_path", "")
            or row.get("effective_target_path", "")
            or row.get("target_path", "")
            or row.get("entry_path", "")
            or ""
        )
        launch_raw = str(
            row.get("manual_launch_target_raw", "")
            or row.get("effective_launch_target_raw", "")
            or row.get("launch_target_raw", "")
            or ""
        )
        app_id = str(row.get("app_id", "") or "")
        permission_state = str(
            row.get("effective_permission_state", "")
            or row.get("permission_state", "")
            or row.get("permission_state_raw", "")
            or ""
        ).strip().lower()
        app_kind = self._infer_app_kind(title=title, path=target_path, launch_raw=launch_raw, app_id=app_id)

        return {
            "app_kind": app_kind,
            "app_id": app_id,
            "title": title,
            "exe_path": target_path,
            "launch_target_raw": launch_raw,
            "permission_state": permission_state,
            "available": bool(target_path or launch_raw or app_kind == "notepad"),
            "can_open": permission_state in {"", "allow", "once", "unset"},
            "document_adapter": self._document_adapter_for_app_kind(app_kind),
            "multi_document": app_kind in self.MULTI_DOCUMENT_APP_KINDS,
            "source": str(row.get("source", "") or ""),
        }

    def _infer_app_kind(self, *, title: str, path: str, launch_raw: str, app_id: str) -> str:
        haystack = " ".join([title, path, launch_raw, app_id]).lower().replace("\\", "/")
        app_id_key = str(app_id or "").strip().lower()

        if "code.exe" in haystack or "visual studio code" in haystack or "vscode" in haystack:
            return "vscode"

        if "winword.exe" in haystack or "microsoft word" in haystack or app_id_key in {"word", "office_word"}:
            return "office_word"
        if "excel.exe" in haystack or "microsoft excel" in haystack or app_id_key in {"excel", "office_excel"}:
            return "office_excel"
        if "powerpnt.exe" in haystack or "powerpoint" in haystack or app_id_key in {
            "powerpoint",
            "office_powerpoint",
        }:
            return "office_powerpoint"

        if "wps.exe" in haystack or "wps writer" in haystack:
            return "wps_writer"
        if "/et.exe" in haystack or "wps spreadsheet" in haystack:
            return "wps_spreadsheet"
        if "/wpp.exe" in haystack or "wps presentation" in haystack:
            return "wps_presentation"

        if "notepad.exe" in haystack or app_id_key == "notepad" or title.strip().lower() in {"notepad"}:
            return "notepad"

        return ""

    def _document_adapter_for_app_kind(self, app_kind: str) -> str:
        if app_kind == "vscode":
            return "vscode"
        if app_kind.startswith("office"):
            return "office"
        if app_kind.startswith("wps"):
            return "wps"
        if app_kind == "notepad":
            return "notepad"
        return "default_app"

    def _rank(self, item: dict[str, Any]) -> tuple[int, int]:
        source = str(item.get("source", "") or "").strip().lower()
        source_rank = {
            "trusted": 4,
            "confirmed": 4,
            "cache": 3,
            "candidate": 2,
            "builtin_fallback": 1,
            "builtin": 1,
        }.get(source, 0)
        path_rank = 1 if str(item.get("exe_path", "") or "").strip() else 0
        return source_rank, path_rank

    def _ensure_builtin_fallbacks(self, index: dict[str, dict[str, Any]]) -> None:
        if "notepad" in index:
            return
        index["notepad"] = {
            "app_kind": "notepad",
            "app_id": "notepad",
            "title": "Notepad",
            "exe_path": "notepad.exe",
            "launch_target_raw": "notepad.exe",
            "permission_state": "allow",
            "available": True,
            "can_open": True,
            "document_adapter": "notepad",
            "multi_document": False,
            "source": "builtin_fallback",
        }
