from __future__ import annotations

from PySide6.QtCore import QObject, Signal

from services.asr_service import transcribe_audio  # type: ignore


class ASRWorker(QObject):
    finished = Signal(int, str)   # request_id, recognized_text
    error = Signal(int, str)

    def __init__(self, request_id: int, record_path: str):
        super().__init__()
        self.request_id = request_id
        self.record_path = record_path

    def run(self):
        try:
            recognized_text = transcribe_audio(self.record_path).strip()
            self.finished.emit(self.request_id, recognized_text)
        except Exception as e:
            self.error.emit(self.request_id, str(e))