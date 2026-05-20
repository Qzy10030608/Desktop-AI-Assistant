from __future__ import annotations

from pathlib import Path
from typing import Any

from services.desktop.qin.heibingtai.document_adapters.document_adapter_result import (
    adapter_error,
    adapter_ok,
    normalize_path,
)


class OfficeDocumentAdapter:
    strategy = "office_com_close_by_fullname"
    level = "registered_file_office_com"

    def close(self, task, session: dict) -> dict:
        rot_result = self._close_rot_document(task, session)
        if rot_result is not None:
            return rot_result

        app_kind = str(session.get("app_kind", "") or "").strip().lower()
        process_name = str(session.get("process_name", "") or "").strip().lower()
        if "word" in app_kind or process_name == "winword.exe":
            return self._close_office_collection(
                task,
                session,
                prog_id="Word.Application",
                collection_name="Documents",
                app_label="word",
            )
        if "excel" in app_kind or process_name == "excel.exe":
            return self._close_office_collection(
                task,
                session,
                prog_id="Excel.Application",
                collection_name="Workbooks",
                app_label="excel",
            )
        if "powerpoint" in app_kind or process_name == "powerpnt.exe":
            return self._close_office_collection(
                task,
                session,
                prog_id="PowerPoint.Application",
                collection_name="Presentations",
                app_label="powerpoint",
            )
        return adapter_error(
            task,
            session,
            adapter="office",
            strategy=self.strategy,
            level=self.level,
            error="office_document_adapter_required",
            message="Unsupported Office document kind.",
        )

    def _com_client(self):
        try:
            import win32com.client  # type: ignore

            return win32com.client
        except Exception:
            return None

    def _active_object(self, prog_id: str):
        client = self._com_client()
        if client is None:
            return None, "office_com_not_available"
        try:
            return client.GetActiveObject(prog_id), ""
        except Exception:
            try:
                return client.GetObject(None, prog_id), ""
            except Exception:
                return None, "office_com_not_available"

    def _close_rot_document(self, task, session: dict) -> dict | None:
        target_path = self._target_path(task, session)
        if not target_path:
            return None
        if not self._rot_contains_path(target_path):
            return None
        client = self._com_client()
        if client is None:
            return None
        try:
            document = client.GetObject(target_path)
        except Exception:
            return None
        try:
            saved = self._document_saved(document)
            full_name = self._document_fullname(document) or target_path
            if normalize_path(full_name) != normalize_path(target_path):
                return self._error(task, session, "office_document_not_found", {"document_fullname": full_name})
            self._close_document(document)
            return self._ok(
                task,
                session,
                strategy="office_rot_getobject_close_by_fullname",
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
            return self._error(task, session, "office_com_close_failed", {
                "com_error": str(exc),
                "close_strategy": "office_rot_getobject_close_by_fullname",
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

    def _close_office_collection(
        self,
        task,
        session: dict,
        *,
        prog_id: str,
        collection_name: str,
        app_label: str,
    ) -> dict:
        app, error = self._active_object(prog_id)
        if error:
            return self._error(task, session, error)
        try:
            documents = list(getattr(app, collection_name))
            matches, strategy = self._matching_documents(task, session, documents)
            if not matches:
                return self._error(task, session, "office_document_not_found", {"office_app": app_label})
            if len(matches) > 1:
                return self._error(
                    task,
                    session,
                    "requires_user_choice",
                    {"office_app": app_label, "candidate_count": len(matches), "candidates": self._candidate_summary(matches)},
                )
            document = matches[0]
            saved = self._document_saved(document)
            full_name = self._document_fullname(document)
            self._close_document(document)
            return self._ok(
                task,
                session,
                strategy=strategy,
                extra={
                    "office_app": app_label,
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
            return self._error(task, session, "office_com_close_failed", {"com_error": str(exc), "office_app": app_label})

    def _matching_documents(self, task, session: dict, documents: list[Any]) -> tuple[list[Any], str]:
        target_path = normalize_path(str(session.get("target_path", getattr(task, "target_path", "")) or ""))
        if target_path:
            matches = [
                document for document in documents
                if normalize_path(self._document_fullname(document)) == target_path
            ]
            if matches:
                return matches, "office_com_close_by_fullname"

        terms = self._target_terms(task, session)
        matches = [
            document for document in documents
            if self._document_matches_terms(document, terms)
        ]
        return matches, "office_com_close_by_name"

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
        # Do not pass SaveChanges=False or Application.Quit. Let Office show its own save prompt.
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

    def _ok(self, task, session: dict, *, strategy: str, extra: dict | None = None) -> dict:
        return adapter_ok(
            task,
            session,
            adapter="office",
            strategy=strategy,
            level=self.level,
            message="Office document close requested by COM.",
            extra=extra,
        )

    def _error(self, task, session: dict, error: str, extra: dict | None = None) -> dict:
        return adapter_error(
            task,
            session,
            adapter="office",
            strategy=self.strategy,
            level=self.level,
            error=error,
            message="Office document could not be closed safely.",
            extra=extra,
        )
