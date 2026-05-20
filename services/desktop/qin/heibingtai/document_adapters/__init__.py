from __future__ import annotations

from services.desktop.qin.heibingtai.document_adapters.default_app_document_adapter import DefaultAppDocumentAdapter
from services.desktop.qin.heibingtai.document_adapters.notepad_document_adapter import NotepadDocumentAdapter
from services.desktop.qin.heibingtai.document_adapters.office_document_adapter import OfficeDocumentAdapter
from services.desktop.qin.heibingtai.document_adapters.vscode_document_adapter import VSCodeDocumentAdapter
from services.desktop.qin.heibingtai.document_adapters.wps_document_adapter import WpsDocumentAdapter

__all__ = [
    "DefaultAppDocumentAdapter",
    "NotepadDocumentAdapter",
    "OfficeDocumentAdapter",
    "VSCodeDocumentAdapter",
    "WpsDocumentAdapter",
]
