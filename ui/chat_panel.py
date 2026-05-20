from PySide6.QtWidgets import QWidget, QVBoxLayout, QScrollArea
from PySide6.QtCore import QTimer

from ui.main_window_config import build_chat_panel_qss  # type: ignore
from ui.components.text_message_widget import TextMessageWidget  # type: ignore
from ui.components.system_message_widget import SystemMessageWidget  # type: ignore
from ui.components.audio_message_widget import AudioMessageWidget  # type: ignore
from ui.components.record_message_widget import RecordMessageWidget  # type: ignore
from ui.components.pending_interaction_card_widget import PendingInteractionCardWidget  # type: ignore


class ChatPanel(QScrollArea):
    """
    独立聊天面板
    负责：
    - 显示消息流
    - 添加不同类型消息
    - 清空消息
    - 自动滚动到底部
    - 流式消息创建 / 更新
    """

    def __init__(self, parent=None, assistant_display_name: str = "AI"):
        super().__init__(parent)
        self.assistant_display_name = self._normalize_assistant_name(assistant_display_name)

        self.setWidgetResizable(True)
        self.setObjectName("chatPanel")

        self.container = QWidget()
        self.container.setObjectName("chatContainer")

        self.message_layout = QVBoxLayout(self.container)
        self.message_layout.setContentsMargins(10, 10, 10, 10)
        self.message_layout.setSpacing(10)
        self.message_layout.addStretch()
        self.pending_interaction_cards: dict[str, QWidget] = {}
        self.latest_record_message_widget: QWidget | None = None

        self.setWidget(self.container)
        self.setStyleSheet(build_chat_panel_qss())

    def _add_widget(self, widget: QWidget):
        self.message_layout.insertWidget(self.message_layout.count() - 1, widget)
        QTimer.singleShot(0, self.scroll_to_bottom)

    def _remove_widget(self, widget: QWidget):
        if widget is None:
            return
        self.message_layout.removeWidget(widget)
        widget.setParent(None)
        widget.deleteLater()
        QTimer.singleShot(0, self.scroll_to_bottom)

    def append_user_message(self, text: str):
        widget = TextMessageWidget("user", text)
        self._add_widget(widget)
        return widget

    def append_ai_message(self, text: str):
        widget = TextMessageWidget("ai", text, assistant_display_name=self.assistant_display_name)
        self._add_widget(widget)
        return widget

    def append_recognized_message(self, text: str):
        widget = TextMessageWidget("recognized", text)
        self._add_widget(widget)
        return widget

    def append_system_message(self, text: str):
        widget = SystemMessageWidget(text)
        self._add_widget(widget)
        return widget

    def append_ai_audio_message(self, text: str):
        widget = AudioMessageWidget(text, assistant_display_name=self.assistant_display_name)
        self._add_widget(widget)
        return widget

    def append_record_message(self, record_path: str, duration_ms: int = 0):
        widget = RecordMessageWidget(record_path=record_path, duration_ms=duration_ms)
        self.latest_record_message_widget = widget
        self._add_widget(widget)
        return widget

    def update_latest_record_recognized_text(self, text: str) -> bool:
        widget = self.latest_record_message_widget
        if widget is None or not hasattr(widget, "set_recognized_text"):
            return False
        widget.set_recognized_text(text)  # type: ignore
        QTimer.singleShot(0, self.scroll_to_bottom)
        return True

    def update_latest_record_recognized_status(self, text: str) -> bool:
        widget = self.latest_record_message_widget
        if widget is None or not hasattr(widget, "set_recognized_status"):
            return False
        widget.set_recognized_status(text)  # type: ignore
        QTimer.singleShot(0, self.scroll_to_bottom)
        return True

    def append_pending_interaction_card(self, ui_prompt: dict):
        widget = PendingInteractionCardWidget(ui_prompt if isinstance(ui_prompt, dict) else {})
        pending_task_id = str((ui_prompt or {}).get("pending_task_id", "") or "")
        if pending_task_id:
            old_widget = self.pending_interaction_cards.pop(pending_task_id, None)
            if old_widget is not None:
                self._remove_widget(old_widget)
            self.pending_interaction_cards[pending_task_id] = widget
        self._add_widget(widget)
        return widget

    def remove_pending_interaction_card(self, pending_task_id: str) -> None:
        pending_id = str(pending_task_id or "").strip()
        if not pending_id:
            return
        widget = self.pending_interaction_cards.pop(pending_id, None)
        if widget is None:
            return
        self._remove_widget(widget)

    def mark_pending_interaction_resolved(self, pending_task_id: str, text: str = "") -> None:
        widget = self.pending_interaction_cards.get(str(pending_task_id or "").strip())
        if widget is not None and hasattr(widget, "mark_resolved"):
            widget.mark_resolved(text)  # type: ignore

    def mark_pending_interaction_cancelled(self, pending_task_id: str, text: str = "") -> None:
        widget = self.pending_interaction_cards.get(str(pending_task_id or "").strip())
        if widget is not None and hasattr(widget, "mark_cancelled"):
            widget.mark_cancelled(text)  # type: ignore

    # =========================
    # 流式消息接口
    # =========================
    def begin_ai_text_stream(self, initial_text: str = ""):
        widget = TextMessageWidget(
            "ai",
            initial_text or "...",
            assistant_display_name=self.assistant_display_name,
        )
        self._add_widget(widget)
        return widget

    def begin_ai_audio_stream(self, initial_text: str = ""):
        widget = AudioMessageWidget(
            initial_text or "...",
            assistant_display_name=self.assistant_display_name,
        )
        widget.set_waiting()
        self._add_widget(widget)
        return widget

    def update_message_text(self, widget: QWidget, text: str):
        if widget is None:
            return

        if hasattr(widget, "set_text"):
            widget.set_text(text)  # type: ignore

        QTimer.singleShot(0, self.scroll_to_bottom)

    def update_message_status(self, widget: QWidget, text: str):
        if widget is None:
            return

        if hasattr(widget, "set_status_text"):
            widget.set_status_text(text)  # type: ignore

        QTimer.singleShot(0, self.scroll_to_bottom)

    def finish_stream_message(self, widget: QWidget):
        if widget is None:
            return

        if hasattr(widget, "finish_stream"):
            widget.finish_stream()  # type: ignore

        QTimer.singleShot(0, self.scroll_to_bottom)

    def clear_messages(self):
        while self.message_layout.count() > 1:
            item = self.message_layout.takeAt(0)
            if item is None:
                continue

            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self.latest_record_message_widget = None
        self.pending_interaction_cards.clear()

    def set_assistant_display_name(self, name: str):
        self.assistant_display_name = self._normalize_assistant_name(name)
        for index in range(self.message_layout.count()):
            item = self.message_layout.itemAt(index)
            widget = item.widget() if item is not None else None
            setter = getattr(widget, "set_assistant_display_name", None)
            if callable(setter):
                setter(self.assistant_display_name)

    def _normalize_assistant_name(self, value: str | None) -> str:
        name = str(value or "").strip()
        return name or "AI"

    def scroll_to_bottom(self):
        bar = self.verticalScrollBar()
        bar.setValue(bar.maximum())
