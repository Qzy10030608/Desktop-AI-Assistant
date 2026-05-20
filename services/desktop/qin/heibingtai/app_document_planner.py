from __future__ import annotations

from services.desktop.qin.heibingtai.document_adapters import (
    DefaultAppDocumentAdapter,
    NotepadDocumentAdapter,
    OfficeDocumentAdapter,
    VSCodeDocumentAdapter,
    WpsDocumentAdapter,
)
from services.desktop.qin.heibingtai.document_adapters.document_adapter_result import adapter_error


class AppDocumentPlanner:
    """
    Reserved for future file-level close adapters.

    Future targets:
    - VSCode tab close
    - WPS document close
    - Office document close
    - browser tab close
    - Arduino IDE tab/workspace close

    This class must not execute app.close.
    """

    def __init__(self, *, host_adapter=None) -> None:
        self.notepad = NotepadDocumentAdapter(host_adapter=host_adapter)
        self.vscode = VSCodeDocumentAdapter(host_adapter=host_adapter)
        self.office = OfficeDocumentAdapter()
        self.wps = WpsDocumentAdapter()
        self.default_app = DefaultAppDocumentAdapter(host_adapter=host_adapter)

    def close_registered_file(self, task, session: dict) -> dict:
        payload = session if isinstance(session, dict) else {}
        app_kind = str(payload.get("app_kind", "") or "").strip().lower()
        process_name = str(payload.get("process_name", "") or "").strip().lower()
        close_strategy = str(payload.get("close_strategy", "") or "").strip().lower()
        open_method = str(payload.get("open_method", "") or "").strip().lower()

        if app_kind == "notepad" or open_method == "notepad" or process_name == "notepad.exe":
            return self.notepad.close(task, payload)

        if app_kind == "vscode" or process_name == "code.exe":
            return self.vscode.close(task, payload)

        if app_kind.startswith("office") or process_name in {"winword.exe", "excel.exe", "powerpnt.exe"}:
            return self.office.close(task, payload)

        if app_kind.startswith("wps") or process_name in {"wps.exe", "et.exe", "wpp.exe"}:
            return self.wps.close(task, payload)

        if close_strategy == "wm_close_owned_single_document_window":
            return self.default_app.close(task, payload)

        return adapter_error(
            task,
            payload,
            adapter="app_document_planner",
            strategy="unsupported_precise_close",
            level="registered_file_precise_close_reserved",
            error="unsupported_precise_close",
            message="No safe document adapter is available for this registered file.",
        )
