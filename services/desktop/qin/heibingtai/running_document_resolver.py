from __future__ import annotations

import ctypes
from ctypes import wintypes
from pathlib import Path
from typing import Any

from services.desktop.qin.shaofu.open_session_service import OpenSessionService


class RunningDocumentResolver:
    """Read-only resolver for currently registered or visible file-view candidates."""

    WORD_EXTENSIONS = {".doc", ".docx", ".dot", ".dotx", ".wps", ".wpt", ".rtf"}
    SPREADSHEET_EXTENSIONS = {".xls", ".xlsx", ".xlsm", ".xlt", ".xltx", ".et", ".ett", ".csv"}
    PRESENTATION_EXTENSIONS = {".ppt", ".pptx", ".pptm", ".pps", ".ppsx", ".pot", ".potx", ".dps", ".dpt"}

    KNOWN_PROCESS_APP_KINDS = {
        "notepad.exe": "notepad",
        "code.exe": "vscode",
        "winword.exe": "office_word",
        "excel.exe": "office_excel",
        "powerpnt.exe": "office_powerpoint",
        "wps.exe": "wps_writer",
        "et.exe": "wps_spreadsheet",
        "wpp.exe": "wps_presentation",
    }

    def __init__(
        self,
        project_root: str | Path | None = None,
        *,
        open_session_service: OpenSessionService | None = None,
    ) -> None:
        self.project_root = Path(project_root or Path(__file__).resolve().parents[4]).expanduser().resolve()
        self.open_session_service = open_session_service or OpenSessionService(self.project_root)

    def resolve_candidates(self, task: dict[str, Any]) -> list[dict[str, Any]]:
        payload = task if isinstance(task, dict) else {}
        arguments = payload.get("arguments", {}) if isinstance(payload.get("arguments"), dict) else {}
        target_path = str(payload.get("target_path", arguments.get("target_path", "")) or "")
        target_name = str(
            payload.get("target_name", "")
            or payload.get("target_reference", "")
            or arguments.get("target_name", "")
            or arguments.get("target_reference", "")
            or ""
        )
        app_hint = str(payload.get("app_hint", arguments.get("app_hint", "")) or "")

        candidates: list[dict[str, Any]] = []
        candidates.extend(self.resolve_open_session_candidates(target_path, target_name, app_hint))
        candidates.extend(self.resolve_rot_document_candidates(target_path, target_name, app_hint))
        candidates.extend(self.resolve_office_candidates(target_path, target_name, app_hint))
        candidates.extend(self.resolve_wps_candidates(target_path, target_name, app_hint))
        candidates.extend(self.resolve_window_title_candidates(target_path, target_name, app_hint))
        return self._dedupe_candidates(candidates)

    def resolve_open_session_candidates(
        self,
        target_path: str = "",
        target_name: str = "",
        app_hint: str = "",
    ) -> list[dict[str, Any]]:
        terms = self._target_terms(target_path, target_name)
        strict_name = self._strict_file_name(target_path)
        normalized_target_path = self._norm_path(target_path)
        candidates: list[dict[str, Any]] = []

        try:
            items = self.open_session_service.restore_registry.read_all(include_deleted=True)
        except Exception:
            return []

        for item in reversed(items):
            if not isinstance(item, dict):
                continue
            if str(item.get("material_type", "") or "").strip() != "open_session":
                continue
            if str(item.get("status", "") or "").strip().lower() != "opened":
                continue
            item_target_type = str(item.get("target_type", "") or "").strip().lower()
            item_action = str(item.get("action", "") or "").strip().lower()
            item_close_action = str(item.get("close_action", "") or "").strip().lower()
            if item_target_type == "directory" or item_action == "folder.open" or item_close_action == "folder.close":
                continue

            item_path = str(item.get("target_path", "") or "")
            item_title = str(item.get("window_title", "") or "")
            app_kind = self._infer_document_app_kind(
                process_name=str(item.get("process_name", "") or ""),
                window_title=item_title,
                target_path=item_path,
                target_name=target_name or str(item.get("target_name", "") or ""),
                preferred_app_kind=str(item.get("app_kind", "") or ""),
            )
            if app_hint and not self._app_hint_matches(app_hint, app_kind):
                continue
            path_exact = bool(normalized_target_path and self._norm_path(item_path) == normalized_target_path)
            if normalized_target_path:
                name_matched = self._full_file_name_matches(item_path, item_title, strict_name)
            else:
                name_matched = self._path_or_title_matches(item_path, item_title, terms)
            if not path_exact and not name_matched:
                continue

            confidence = "high" if path_exact or name_matched else "medium"
            candidates.append(self.make_candidate(
                candidate_id=str(item.get("session_id", item.get("material_id", "")) or ""),
                label=self._candidate_label(app_kind, item_title, item_path),
                target_path=item_path,
                target_name=self._display_target_name(item_path, target_name),
                app_kind=app_kind,
                process_name=str(item.get("process_name", "") or ""),
                pid=str(item.get("pid", "") or ""),
                hwnd=str(item.get("hwnd", "") or ""),
                window_title=item_title,
                document_adapter=str(item.get("document_adapter", "") or "")
                or self._document_adapter_for_app_kind(app_kind),
                source="open_session",
                confidence=confidence,
                can_close=True,
                reason="registered_open_session_match",
                extra={
                    "session_id": str(item.get("session_id", item.get("material_id", "")) or ""),
                    "close_strategy": str(item.get("close_strategy", "") or ""),
                },
            ))

        return candidates

    def resolve_window_title_candidates(
        self,
        target_path: str = "",
        target_name: str = "",
        app_hint: str = "",
    ) -> list[dict[str, Any]]:
        terms = self._target_terms(target_path, target_name)
        strict_name = self._strict_file_name(target_path)
        if not terms:
            return []

        candidates: list[dict[str, Any]] = []
        for window in self._enum_windows_info():
            title = str(window.get("window_title", "") or "")
            if target_path:
                if not self._title_contains_full_file_name(title, strict_name):
                    continue
            elif not self._title_matches_terms(title, terms):
                continue
            process_name = str(window.get("process_name", "") or "").lower()
            app_kind = self._infer_document_app_kind(
                process_name=process_name,
                window_title=title,
                target_path=target_path,
                target_name=target_name,
            )
            if app_hint and not self._app_hint_matches(app_hint, app_kind):
                continue

            known_app = bool(app_kind)
            confidence = "medium" if known_app else "low"
            if known_app and app_hint and self._app_hint_matches(app_hint, app_kind):
                confidence = "high"

            candidates.append(self.make_candidate(
                candidate_id=f"window_{window.get('hwnd', '')}",
                label=self._candidate_label(app_kind, title, ""),
                target_path="",
                target_name=target_name or self._best_term(terms),
                app_kind=app_kind,
                process_name=process_name,
                pid=str(window.get("pid", "") or ""),
                hwnd=str(window.get("hwnd", "") or ""),
                window_title=title,
                document_adapter=self._document_adapter_for_app_kind(app_kind),
                source="window_title",
                confidence=confidence,
                can_close=known_app,
                reason="visible_window_title_match",
            ))

        return candidates

    def resolve_office_candidates(
        self,
        target_path: str = "",
        target_name: str = "",
        app_hint: str = "",
    ) -> list[dict[str, Any]]:
        specs = [
            {
                "app_kind": "office_word",
                "label_prefix": "Word",
                "prog_id": "Word.Application",
                "collection_name": "Documents",
                "process_name": "winword.exe",
            },
            {
                "app_kind": "office_excel",
                "label_prefix": "Excel",
                "prog_id": "Excel.Application",
                "collection_name": "Workbooks",
                "process_name": "excel.exe",
            },
            {
                "app_kind": "office_powerpoint",
                "label_prefix": "PowerPoint",
                "prog_id": "PowerPoint.Application",
                "collection_name": "Presentations",
                "process_name": "powerpnt.exe",
            },
        ]
        return self._resolve_com_document_candidates(
            specs=specs,
            target_path=target_path,
            target_name=target_name,
            app_hint=app_hint,
            source="office_com",
            reason="office_com_document_match",
            adapter="office",
        )

    def resolve_rot_document_candidates(
        self,
        target_path: str = "",
        target_name: str = "",
        app_hint: str = "",
    ) -> list[dict[str, Any]]:
        normalized_target = self._norm_path(target_path)
        terms = self._target_terms("", target_name)
        candidates: list[dict[str, Any]] = []
        for index, display_name in enumerate(self._rot_display_names()):
            if not self._is_supported_document_path(display_name):
                continue
            normalized_display = self._norm_path(display_name)
            if normalized_target:
                if normalized_display != normalized_target:
                    continue
            elif terms and not self._path_matches_terms(display_name, terms):
                continue
            elif not terms:
                continue
            app_kind, adapter = self._rot_app_kind_for_path(display_name, app_hint)
            if not app_kind or not adapter:
                continue
            if app_hint and not self._app_hint_matches(app_hint, app_kind):
                continue
            document_name = Path(display_name).name
            candidates.append(self.make_candidate(
                candidate_id=f"rot_{app_kind}_{index}",
                label=f"{self._rot_label_prefix(app_kind)}: {document_name}",
                target_path=display_name,
                target_name=document_name,
                app_kind=app_kind,
                process_name="",
                pid="",
                hwnd="",
                window_title=document_name,
                document_adapter=adapter,
                source="rot",
                confidence="high",
                can_close=True,
                reason="rot_document_match",
                extra={
                    "document_fullname": display_name,
                    "document_name": document_name,
                },
            ))
        return candidates

    def resolve_wps_candidates(
        self,
        target_path: str = "",
        target_name: str = "",
        app_hint: str = "",
    ) -> list[dict[str, Any]]:
        specs = [
            {
                "app_kind": "wps_writer",
                "label_prefix": "WPS 文字",
                "prog_id": "Kwps.Application",
                "collection_name": "Documents",
                "process_name": "wps.exe",
            },
            {
                "app_kind": "wps_spreadsheet",
                "label_prefix": "WPS 表格",
                "prog_id": "Ket.Application",
                "collection_name": "Workbooks",
                "process_name": "et.exe",
            },
            {
                "app_kind": "wps_presentation",
                "label_prefix": "WPS 演示",
                "prog_id": "Kwpp.Application",
                "collection_name": "Presentations",
                "process_name": "wpp.exe",
            },
        ]
        return self._resolve_com_document_candidates(
            specs=specs,
            target_path=target_path,
            target_name=target_name,
            app_hint=app_hint,
            source="wps_com",
            reason="wps_com_document_match",
            adapter="wps",
        )

    def _resolve_com_document_candidates(
        self,
        *,
        specs: list[dict[str, str]],
        target_path: str,
        target_name: str,
        app_hint: str,
        source: str,
        reason: str,
        adapter: str,
    ) -> list[dict[str, Any]]:
        client = self._com_client()
        if client is None:
            return []
        candidates: list[dict[str, Any]] = []
        for spec in specs:
            app_kind = str(spec.get("app_kind", "") or "")
            if app_hint and not self._app_hint_matches(app_hint, app_kind):
                continue
            app = self._get_active_com_object(client, str(spec.get("prog_id", "") or ""))
            if app is None:
                continue
            try:
                documents = list(getattr(app, str(spec.get("collection_name", "") or "")))
            except Exception:
                continue
            matches = self._matching_com_documents(documents, target_path, target_name)
            for index, document in enumerate(matches):
                full_name = self._com_document_fullname(document)
                name = self._com_document_name(document)
                candidates.append(self.make_candidate(
                    candidate_id=f"{source}_{app_kind}_{index}",
                    label=f"{spec.get('label_prefix', app_kind)}: {name or Path(full_name).name or target_name}",
                    target_path=full_name,
                    target_name=name or Path(full_name).name or target_name,
                    app_kind=app_kind,
                    process_name=str(spec.get("process_name", "") or ""),
                    pid="",
                    hwnd="",
                    window_title=name or Path(full_name).name or "",
                    document_adapter=adapter,
                    source=source,
                    confidence="high",
                    can_close=True,
                    reason=reason,
                    extra={
                        "document_fullname": full_name,
                        "document_name": name,
                    },
                ))
        return candidates

    def _com_client(self):
        try:
            import win32com.client  # type: ignore

            return win32com.client
        except Exception:
            return None

    def _get_active_com_object(self, client, prog_id: str):
        if not prog_id:
            return None
        try:
            return client.GetActiveObject(prog_id)
        except Exception:
            return None

    def _rot_display_names(self) -> list[str]:
        try:
            import pythoncom  # type: ignore
        except Exception:
            return []
        try:
            rot = pythoncom.GetRunningObjectTable()
            enum_moniker = rot.EnumRunning()
            bind_context = pythoncom.CreateBindCtx(0)
        except Exception:
            return []
        names: list[str] = []
        while True:
            try:
                monikers = enum_moniker.Next(1)
            except Exception:
                break
            if not monikers:
                break
            moniker = monikers[0]
            try:
                display_name = str(moniker.GetDisplayName(bind_context, None) or "").strip()
            except Exception:
                continue
            if display_name:
                names.append(display_name)
        return names

    def _matching_com_documents(self, documents: list[Any], target_path: str, target_name: str) -> list[Any]:
        normalized_target = self._norm_path(target_path)
        if normalized_target:
            return [
                document for document in documents
                if self._norm_path(self._com_document_fullname(document)) == normalized_target
            ]
        terms = self._target_terms("", target_name)
        if not terms:
            return []
        return [
            document for document in documents
            if self._com_document_matches_terms(document, terms)
        ]

    def _com_document_matches_terms(self, document, terms: list[str]) -> bool:
        haystack = " ".join([
            self._com_document_name(document),
            self._com_document_fullname(document),
        ]).lower()
        return any(term in haystack for term in terms)

    def _com_document_name(self, document) -> str:
        return str(getattr(document, "Name", "") or "")

    def _com_document_fullname(self, document) -> str:
        return str(getattr(document, "FullName", "") or self._com_document_name(document))

    def _is_supported_document_path(self, value: str) -> bool:
        text = str(value or "").strip()
        if not text:
            return False
        suffix = Path(text).suffix.lower()
        return suffix in (self.WORD_EXTENSIONS | self.SPREADSHEET_EXTENSIONS | self.PRESENTATION_EXTENSIONS)

    def _path_matches_terms(self, path_text: str, terms: list[str]) -> bool:
        path = Path(str(path_text or ""))
        haystack = " ".join([str(path_text or ""), path.name, path.stem]).lower()
        return any(term in haystack for term in terms)

    def _rot_app_kind_for_path(self, path_text: str, app_hint: str) -> tuple[str, str]:
        family = self._document_family_from_texts(path_text)
        hint = str(app_hint or "").strip().lower()
        if hint.startswith("wps"):
            return self._family_app_kind(family, "wps"), "wps"
        if hint.startswith("office"):
            return self._family_app_kind(family, "office"), "office"
        if hint in {"wps", "word", "doc", "excel", "sheet", "powerpoint", "ppt"}:
            if hint in {"word", "doc"}:
                return self._family_app_kind(family, "wps"), "wps"
            if hint in {"excel", "sheet"}:
                return self._family_app_kind(family, "wps"), "wps"
            if hint in {"powerpoint", "ppt"}:
                return self._family_app_kind(family, "wps"), "wps"
            return self._family_app_kind(family, "wps"), "wps"
        if hint == "office":
            return self._family_app_kind(family, "office"), "office"
        return self._family_app_kind(family, "wps"), "wps"

    def _family_app_kind(self, family: str, suite: str) -> str:
        if suite == "office":
            return {
                "word": "office_word",
                "spreadsheet": "office_excel",
                "presentation": "office_powerpoint",
            }.get(family, "")
        return {
            "word": "wps_writer",
            "spreadsheet": "wps_spreadsheet",
            "presentation": "wps_presentation",
        }.get(family, "")

    def _rot_label_prefix(self, app_kind: str) -> str:
        return {
            "office_word": "Word",
            "office_excel": "Excel",
            "office_powerpoint": "PowerPoint",
            "wps_writer": "WPS 文字",
            "wps_spreadsheet": "WPS 表格",
            "wps_presentation": "WPS 演示",
        }.get(str(app_kind or "").strip().lower(), "Document")

    def make_candidate(
        self,
        *,
        candidate_id: str,
        label: str,
        target_path: str,
        target_name: str,
        app_kind: str,
        process_name: str,
        pid: str,
        hwnd: str,
        window_title: str,
        document_adapter: str,
        source: str,
        confidence: str,
        can_close: bool,
        reason: str,
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        candidate = {
            "candidate_id": candidate_id,
            "label": label,
            "target_path": target_path,
            "target_name": target_name,
            "app_kind": app_kind,
            "process_name": process_name,
            "pid": str(pid or ""),
            "hwnd": str(hwnd or ""),
            "window_title": window_title,
            "document_adapter": document_adapter,
            "source": source,
            "confidence": confidence,
            "can_close": bool(can_close),
            "reason": reason,
        }
        if extra:
            candidate.update(extra)
        return candidate

    def _dedupe_candidates(self, candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
        path_merge_index = self._path_merge_index(candidates)
        best_by_key: dict[str, dict[str, Any]] = {}
        for candidate in candidates:
            key = self._candidate_key(candidate, path_merge_index)
            existing = best_by_key.get(key)
            if existing is None or self._candidate_rank(candidate) > self._candidate_rank(existing):
                best_by_key[key] = candidate
        return sorted(best_by_key.values(), key=self._candidate_rank, reverse=True)

    def _candidate_key(self, candidate: dict[str, Any], path_merge_index: dict[tuple[str, str], str] | None = None) -> str:
        target_path = self._norm_path(str(candidate.get("document_fullname", "") or candidate.get("target_path", "") or ""))
        if target_path:
            return f"path:{target_path}"
        merged_path = self._matching_path_candidate_key(candidate, path_merge_index or {})
        if merged_path:
            return merged_path
        hwnd = str(candidate.get("hwnd", "") or "").strip()
        app_kind = str(candidate.get("app_kind", "") or "").strip().lower()
        title = str(candidate.get("window_title", "") or "").strip().lower()
        return f"window:{app_kind}:{hwnd}:{title}"

    def _path_merge_index(self, candidates: list[dict[str, Any]]) -> dict[tuple[str, str], str]:
        pending: dict[tuple[str, str], str] = {}
        ambiguous: set[tuple[str, str]] = set()
        for candidate in candidates:
            path_text = str(candidate.get("document_fullname", "") or candidate.get("target_path", "") or "")
            normalized = self._norm_path(path_text)
            if not normalized:
                continue
            app_kind = str(candidate.get("app_kind", "") or "").strip().lower()
            doc_name = str(
                candidate.get("document_name", "")
                or Path(path_text).name
                or candidate.get("target_name", "")
                or ""
            ).strip().lower()
            if not app_kind or not doc_name:
                continue
            key = (app_kind, doc_name)
            path_key = f"path:{normalized}"
            existing = pending.get(key)
            if existing and existing != path_key:
                ambiguous.add(key)
                continue
            pending[key] = path_key
        for key in ambiguous:
            pending.pop(key, None)
        return pending

    def _matching_path_candidate_key(self, candidate: dict[str, Any], path_merge_index: dict[tuple[str, str], str]) -> str:
        title = str(candidate.get("window_title", "") or "").strip().lower()
        app_kind = str(candidate.get("app_kind", "") or "").strip().lower()
        if not title or not app_kind:
            return ""
        for (candidate_app_kind, doc_name), path_key in path_merge_index.items():
            if candidate_app_kind == app_kind and doc_name in title:
                return path_key
        return ""

    def _candidate_rank(self, candidate: dict[str, Any]) -> tuple[int, int, int]:
        confidence_rank = {"high": 3, "medium": 2, "low": 1}.get(
            str(candidate.get("confidence", "") or "").lower(),
            0,
        )
        source_rank = {
            "rot": 6,
            "office_com": 5,
            "wps_com": 5,
            "open_session": 4,
            "window_title": 2,
        }.get(str(candidate.get("source", "") or "").lower(), 0)
        path_rank = 1 if str(candidate.get("document_fullname", "") or candidate.get("target_path", "") or "").strip() else 0
        return confidence_rank, source_rank, path_rank

    def _enum_windows_info(self) -> list[dict[str, Any]]:
        try:
            user32 = ctypes.WinDLL("user32", use_last_error=True)
        except Exception:
            return []

        windows: list[dict[str, Any]] = []

        enum_proc_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        user32.EnumWindows.argtypes = [enum_proc_type, wintypes.LPARAM]
        user32.EnumWindows.restype = wintypes.BOOL
        user32.IsWindowVisible.argtypes = [wintypes.HWND]
        user32.IsWindowVisible.restype = wintypes.BOOL
        user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
        user32.GetWindowTextLengthW.restype = ctypes.c_int
        user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
        user32.GetWindowTextW.restype = ctypes.c_int
        user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
        user32.GetWindowThreadProcessId.restype = wintypes.DWORD

        def callback(hwnd: int, lparam: int) -> bool:
            try:
                if not user32.IsWindowVisible(hwnd):
                    return True
                length = user32.GetWindowTextLengthW(hwnd)
                if length <= 0:
                    return True
                buffer = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buffer, length + 1)
                title = buffer.value.strip()
                if not title:
                    return True
                pid = wintypes.DWORD()
                user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                process_name = self._process_name_for_pid(int(pid.value))
                windows.append({
                    "hwnd": str(int(hwnd)),
                    "pid": str(int(pid.value)),
                    "process_name": process_name,
                    "window_title": title,
                })
            except Exception:
                return True
            return True

        try:
            user32.EnumWindows(enum_proc_type(callback), 0)
        except Exception:
            return []
        return windows

    def _process_name_for_pid(self, pid: int) -> str:
        if not pid:
            return ""
        try:
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            process_query_limited_information = 0x1000
            kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
            kernel32.OpenProcess.restype = wintypes.HANDLE
            kernel32.QueryFullProcessImageNameW.argtypes = [
                wintypes.HANDLE,
                wintypes.DWORD,
                wintypes.LPWSTR,
                ctypes.POINTER(wintypes.DWORD),
            ]
            kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
            kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
            kernel32.CloseHandle.restype = wintypes.BOOL
            handle = kernel32.OpenProcess(process_query_limited_information, False, int(pid))
            if not handle:
                return ""
            try:
                size = wintypes.DWORD(32768)
                buffer = ctypes.create_unicode_buffer(size.value)
                if not kernel32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
                    return ""
                return Path(buffer.value).name.lower()
            finally:
                kernel32.CloseHandle(handle)
        except Exception:
            return ""

    def _target_terms(self, target_path: str, target_name: str) -> list[str]:
        terms: list[str] = []
        raw_name = str(target_name or "").strip()
        if raw_name:
            terms.append(raw_name)
        path_text = str(target_path or "").strip()
        if path_text:
            path = Path(path_text)
            if path.name:
                terms.append(path.name)
            if path.stem:
                terms.append(path.stem)
        normalized: list[str] = []
        for term in terms:
            key = term.strip().lower()
            if key and key not in normalized:
                normalized.append(key)
        return normalized

    def _path_or_title_matches(self, target_path: str, window_title: str, terms: list[str]) -> bool:
        path = Path(str(target_path or ""))
        haystack = " ".join([str(target_path or ""), path.name, path.stem, str(window_title or "")]).lower()
        return any(term in haystack for term in terms)

    def _title_matches_terms(self, window_title: str, terms: list[str]) -> bool:
        title = str(window_title or "").lower()
        return any(term in title for term in terms)

    def _strict_file_name(self, target_path: str) -> str:
        return Path(str(target_path or "")).name.strip().lower()

    def _full_file_name_matches(self, target_path: str, window_title: str, strict_name: str) -> bool:
        if not strict_name:
            return False
        path_name = Path(str(target_path or "")).name.strip().lower()
        title = str(window_title or "").strip().lower()
        return path_name == strict_name or strict_name in title

    def _title_contains_full_file_name(self, window_title: str, strict_name: str) -> bool:
        return bool(strict_name and strict_name in str(window_title or "").strip().lower())

    def _app_kind_from_item(self, item: dict[str, Any]) -> str:
        app_kind = self._infer_document_app_kind(
            process_name=str(item.get("process_name", "") or ""),
            window_title=str(item.get("window_title", "") or ""),
            target_path=str(item.get("target_path", "") or ""),
            target_name=str(item.get("target_name", "") or ""),
            preferred_app_kind=str(item.get("app_kind", "") or ""),
        )
        if app_kind:
            return app_kind
        process_name = str(item.get("process_name", "") or "").strip().lower()
        return self.KNOWN_PROCESS_APP_KINDS.get(process_name, "")

    def _infer_document_app_kind(
        self,
        *,
        process_name: str,
        window_title: str = "",
        target_path: str = "",
        target_name: str = "",
        preferred_app_kind: str = "",
    ) -> str:
        process = str(process_name or "").strip().lower()
        preferred = str(preferred_app_kind or "").strip().lower()
        ext_family = self._document_family_from_texts(window_title, target_path, target_name)
        is_wps = process in {"wps.exe", "et.exe", "wpp.exe"} or preferred.startswith("wps")
        is_office = process in {"winword.exe", "excel.exe", "powerpnt.exe"} or preferred.startswith("office")

        if is_wps and ext_family:
            return {
                "presentation": "wps_presentation",
                "spreadsheet": "wps_spreadsheet",
                "word": "wps_writer",
            }.get(ext_family, preferred)
        if is_office and ext_family:
            return {
                "presentation": "office_powerpoint",
                "spreadsheet": "office_excel",
                "word": "office_word",
            }.get(ext_family, preferred)

        if preferred:
            return preferred
        if process == "wpp.exe":
            return "wps_presentation"
        if process == "et.exe":
            return "wps_spreadsheet"
        if process == "wps.exe":
            return "wps_writer"
        if process == "powerpnt.exe":
            return "office_powerpoint"
        if process == "excel.exe":
            return "office_excel"
        if process == "winword.exe":
            return "office_word"
        return self.KNOWN_PROCESS_APP_KINDS.get(process, "")

    def _document_family_from_texts(self, *values: str) -> str:
        extensions = self._extensions_from_texts(*values)
        if extensions & self.PRESENTATION_EXTENSIONS:
            return "presentation"
        if extensions & self.SPREADSHEET_EXTENSIONS:
            return "spreadsheet"
        if extensions & self.WORD_EXTENSIONS:
            return "word"
        return ""

    def _extensions_from_texts(self, *values: str) -> set[str]:
        result: set[str] = set()
        all_extensions = self.WORD_EXTENSIONS | self.SPREADSHEET_EXTENSIONS | self.PRESENTATION_EXTENSIONS
        for value in values:
            text = str(value or "").strip().lower()
            if not text:
                continue
            suffix = Path(text).suffix.lower()
            if suffix:
                result.add(suffix)
            for extension in all_extensions:
                if extension in text:
                    result.add(extension)
        return result

    def _app_hint_matches(self, app_hint: str, app_kind: str) -> bool:
        normalized_hint = str(app_hint or "").strip().lower()
        normalized_kind = str(app_kind or "").strip().lower()
        if not normalized_hint:
            return True
        aliases = {
            "word": {"office_word", "wps_writer"},
            "doc": {"office_word", "wps_writer"},
            "excel": {"office_excel", "wps_spreadsheet"},
            "sheet": {"office_excel", "wps_spreadsheet"},
            "powerpoint": {"office_powerpoint", "wps_presentation"},
            "ppt": {"office_powerpoint", "wps_presentation"},
            "vscode": {"vscode"},
            "code": {"vscode"},
            "notepad": {"notepad"},
            "记事本": {"notepad"},
            "wps": {"wps_writer", "wps_spreadsheet", "wps_presentation"},
            "wps_writer": {"wps_writer"},
            "wps_spreadsheet": {"wps_spreadsheet"},
            "wps_presentation": {"wps_presentation"},
            "office": {"office_word", "office_excel", "office_powerpoint"},
            "office_word": {"office_word"},
            "office_excel": {"office_excel"},
            "office_powerpoint": {"office_powerpoint"},
        }
        allowed = aliases.get(normalized_hint, {normalized_hint})
        return normalized_kind in allowed

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

    def _candidate_label(self, app_kind: str, window_title: str, target_path: str) -> str:
        app_label = {
            "vscode": "VSCode",
            "office_word": "Word",
            "office_excel": "Excel",
            "office_powerpoint": "PowerPoint",
            "wps_writer": "WPS",
            "wps_spreadsheet": "WPS",
            "wps_presentation": "WPS",
            "notepad": "Notepad",
        }.get(str(app_kind or "").strip().lower(), "Window")
        name = Path(str(target_path or "")).name or str(window_title or "").strip() or "unknown"
        return f"{app_label}: {name}"

    def _display_target_name(self, target_path: str, fallback: str) -> str:
        return Path(str(target_path or "")).name or str(fallback or "")

    def _best_term(self, terms: list[str]) -> str:
        return max(terms, key=len) if terms else ""

    def _norm_path(self, value: str) -> str:
        text = str(value or "").strip()
        if not text:
            return ""
        try:
            return str(Path(text).expanduser().resolve(strict=False)).rstrip("\\/").lower()
        except Exception:
            return text.rstrip("\\/").lower()
