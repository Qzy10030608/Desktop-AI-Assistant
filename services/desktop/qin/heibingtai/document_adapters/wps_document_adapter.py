from __future__ import annotations

from pathlib import Path
from typing import Any

from services.desktop.qin.heibingtai.document_adapters.document_adapter_result import (
    adapter_error,
    adapter_ok,
    normalize_path,
)


class WpsDocumentAdapter:
    strategy = "wps_com_probe_close_by_fullname"
    level = "registered_file_wps_com_probe"
    WORD_EXTENSIONS = {".doc", ".docx", ".dot", ".dotx", ".wps", ".wpt", ".rtf"}
    SPREADSHEET_EXTENSIONS = {".xls", ".xlsx", ".xlsm", ".xlt", ".xltx", ".et", ".ett", ".csv"}
    PRESENTATION_EXTENSIONS = {".ppt", ".pptx", ".pptm", ".pps", ".ppsx", ".pot", ".potx", ".dps", ".dpt"}

    def close(self, task, session: dict) -> dict:
        rot_result = self._close_rot_document(task, session)
        if rot_result is not None:
            return rot_result

        app, collection_name, prog_ids = self._resolve_wps_target(session)
        if not prog_ids:
            return self._error(task, session, "wps_document_adapter_required")
        com_app = None
        last_error = "wps_com_not_available"
        for prog_id in prog_ids:
            com_app, last_error = self._active_object(prog_id)
            if com_app is not None:
                break
        if com_app is None:
            return self._error(task, session, "wps_document_adapter_required", {"probe_error": last_error})
        try:
            collection = list(getattr(com_app, collection_name))
            matches, strategy = self._matching_documents(task, session, collection)
            if not matches:
                return self._error(task, session, "wps_document_not_found", {"wps_app": app})
            if len(matches) > 1:
                return self._error(
                    task,
                    session,
                    "requires_user_choice",
                    {"wps_app": app, "candidate_count": len(matches), "candidates": self._candidate_summary(matches)},
                )
            document = matches[0]
            saved = self._document_saved(document)
            full_name = self._document_fullname(document)
            self._close_document(document)
            return adapter_ok(
                task,
                session,
                adapter="wps",
                strategy=strategy,
                level=self.level,
                message="WPS document close requested by COM probe.",
                extra={
                    "wps_app": app,
                    "document_fullname": full_name,
                    "document_saved": saved,
                    "save_state": "saved" if saved else "maybe_dirty",
                    "requires_user_save_confirmation": not saved,
                    "user_action_required": "handle_save_prompt" if not saved else "",
                    "close_requested": True,
                    "close_dispatched": True,
                },
            )
        except Exception as exc:
            return self._error(task, session, "wps_com_close_failed", {"com_error": str(exc), "wps_app": app})

    def _active_object(self, prog_id: str):
        try:
            import win32com.client  # type: ignore
        except Exception:
            return None, "wps_com_not_available"
        try:
            return win32com.client.GetActiveObject(prog_id), ""
        except Exception:
            return None, "wps_com_not_available"

    def _close_rot_document(self, task, session: dict) -> dict | None:
        target_path = self._target_path(task, session)
        if not target_path:
            return None
        if not self._rot_contains_path(target_path):
            return None
        try:
            import win32com.client  # type: ignore
        except Exception:
            return None
        try:
            document = win32com.client.GetObject(target_path)
        except Exception:
            return None
        try:
            saved = self._document_saved(document)
            full_name = self._document_fullname(document) or target_path
            if normalize_path(full_name) != normalize_path(target_path):
                return self._error(task, session, "wps_document_not_found", {"document_fullname": full_name})
            self._close_document(document)
            return adapter_ok(
                task,
                session,
                adapter="wps",
                strategy="wps_rot_getobject_close_by_fullname",
                level=self.level,
                message="WPS document close requested by ROT GetObject.",
                extra={
                    "document_fullname": full_name,
                    "document_saved": saved,
                    "save_state": "saved" if saved else "maybe_dirty",
                    "requires_user_save_confirmation": not saved,
                    "user_action_required": "handle_save_prompt" if not saved else "",
                    "close_requested": True,
                    "close_dispatched": True,
                    "rot_matched": True,
                },
            )
        except Exception as exc:
            return self._error(task, session, "wps_com_close_failed", {
                "com_error": str(exc),
                "close_strategy": "wps_rot_getobject_close_by_fullname",
                "rot_matched": True,
            })

    def _target_path(self, task, session: dict) -> str:
        return str(
            session.get("document_fullname", "")
            or session.get("target_path", "")
            or getattr(task, "target_path", "")
            or ""
        ).strip()

    def _rot_contains_path(self, target_path: str) -> bool:
        normalized_target = normalize_path(target_path)
        if not normalized_target:
            return False
        for display_name in self._rot_display_names():
            if normalize_path(display_name) == normalized_target:
                return True
        return False

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

    def _resolve_wps_target(self, session: dict) -> tuple[str, str, list[str]]:
        app_kind = str(session.get("app_kind", "") or "").strip().lower()
        process_name = str(session.get("process_name", "") or "").strip().lower()
        family = self._document_family_from_session(session)
        if app_kind == "wps_presentation" or family == "presentation":
            return "wps_presentation", "Presentations", ["Kwpp.Application"]
        if app_kind == "wps_spreadsheet" or family == "spreadsheet":
            return "wps_spreadsheet", "Workbooks", ["Ket.Application"]
        if app_kind == "wps_writer" or family == "word":
            return "wps_writer", "Documents", ["Kwps.Application"]
        if process_name == "wpp.exe" or "presentation" in app_kind or "powerpoint" in app_kind:
            return "wps_presentation", "Presentations", ["Kwpp.Application"]
        if process_name == "et.exe" or "spreadsheet" in app_kind or "excel" in app_kind:
            return "wps_spreadsheet", "Workbooks", ["Ket.Application"]
        if process_name == "wps.exe" or app_kind.startswith("wps"):
            return "wps_writer", "Documents", ["Kwps.Application"]
        return "", "", []

    def _document_family_from_session(self, session: dict) -> str:
        extensions = self._extensions_from_texts(
            str(session.get("window_title", "") or ""),
            str(session.get("target_path", "") or ""),
            str(session.get("target_name", "") or ""),
        )
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

    def _matching_documents(self, task, session: dict, documents: list[Any]) -> tuple[list[Any], str]:
        target_path = normalize_path(str(session.get("target_path", getattr(task, "target_path", "")) or ""))
        if target_path:
            matches = [
                document for document in documents
                if normalize_path(self._document_fullname(document)) == target_path
            ]
            if matches:
                return matches, "wps_com_probe_close_by_fullname"

        terms = self._target_terms(task, session)
        matches = [
            document for document in documents
            if self._document_matches_terms(document, terms)
        ]
        return matches, "wps_com_probe_close_by_name"

    def _target_terms(self, task, session: dict) -> list[str]:
        terms: list[str] = []
        target_name = str(session.get("target_name", getattr(task, "target_name", "")) or "").strip()
        target_path = str(session.get("target_path", getattr(task, "target_path", "")) or "").strip()
        window_title = str(session.get("window_title", "") or "").strip()
        if target_name:
            terms.append(target_name)
        if target_path:
            path = Path(target_path)
            terms.extend([path.name, path.stem])
        if window_title:
            terms.append(window_title)
        normalized: list[str] = []
        for term in terms:
            value = str(term or "").strip().lower()
            if value and value not in normalized:
                normalized.append(value)
        return normalized

    def _document_matches_terms(self, document, terms: list[str]) -> bool:
        if not terms:
            return False
        haystack = " ".join([
            self._document_name(document),
            self._document_fullname(document),
        ]).lower()
        return any(term in haystack for term in terms)

    def _close_document(self, document) -> None:
        # Do not pass SaveChanges=False and do not close the WPS application.
        document.Close()

    def _document_name(self, document) -> str:
        return str(getattr(document, "Name", "") or "")

    def _document_fullname(self, document) -> str:
        return str(getattr(document, "FullName", "") or self._document_name(document))

    def _document_saved(self, document) -> bool:
        try:
            return bool(getattr(document, "Saved", True))
        except Exception:
            return True

    def _candidate_summary(self, documents: list[Any]) -> list[dict[str, str]]:
        return [
            {
                "label": self._document_name(document) or self._document_fullname(document),
                "target_path": self._document_fullname(document),
                "document_fullname": self._document_fullname(document),
            }
            for document in documents[:10]
        ]

    def _error(self, task, session: dict, error: str, extra: dict | None = None) -> dict:
        return adapter_error(
            task,
            session,
            adapter="wps",
            strategy=self.strategy,
            level=self.level,
            error=error,
            message="WPS document adapter could not safely close the target document.",
            extra=extra,
        )
