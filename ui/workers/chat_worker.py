from __future__ import annotations

from PySide6.QtCore import QObject, Signal

from services.reply.llm_service import chat_stream  # type: ignore


class ChatWorker(QObject):
    partial = Signal(int, str, str)   # request_id, piece, raw_text_so_far
    finished = Signal(int, str, str)  # request_id, user_text, ai_text
    error = Signal(int, str)

    def __init__(
        self,
        request_id: int,
        text: str,
        history: list,
        model_config: dict,
        system_prompt: str,
        timeout,
        request_options: dict | None = None,
    ):
        super().__init__()
        self.request_id = request_id
        self.text = text
        self.history = history
        self.model_config = dict(model_config or {})
        self.system_prompt = system_prompt
        self.timeout = timeout
        self.request_options = request_options or {}

    def run(self):
        try:
            def _on_chunk(piece: str, raw_text_so_far: str):
                self.partial.emit(self.request_id, piece, raw_text_so_far)

            ai_text = chat_stream(
                self.text,
                history=self.history,
                model_config=self.model_config,
                system_prompt=self.system_prompt,
                timeout=self.timeout,
                request_options=self.request_options,
                on_chunk=_on_chunk,
                should_stop=None,
            )
            self.finished.emit(self.request_id, self.text, ai_text)
        except Exception as e:
            self.error.emit(self.request_id, str(e))