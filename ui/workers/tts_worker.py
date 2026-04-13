from __future__ import annotations

from PySide6.QtCore import QObject, Signal

from services.tts.tts_service import TTSRequest, generate_tts  # type: ignore


class TTSWorker(QObject):
    finished = Signal(int, str)   # tts_task_id, reply_path
    error = Signal(int, str)

    def __init__(self, tts_task_id: int, tts_request: TTSRequest):
        super().__init__()
        self.tts_task_id = tts_task_id
        self.tts_request = tts_request

    def run(self):
        try:
            reply_path = generate_tts(self.tts_request)
            self.finished.emit(self.tts_task_id, reply_path)
        except Exception as e:
            self.error.emit(self.tts_task_id, str(e))