from PySide6.QtWidgets import QWidget, QVBoxLayout, QScrollArea
from PySide6.QtCore import QTimer

from ui.main_window_config import build_chat_panel_qss  # type: ignore
from ui.components.text_message_widget import TextMessageWidget  # type: ignore
from ui.components.system_message_widget import SystemMessageWidget  # type: ignore
from ui.components.audio_message_widget import AudioMessageWidget  # type: ignore
from ui.components.record_message_widget import RecordMessageWidget  # type: ignore


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

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWidgetResizable(True)
        self.setObjectName("chatPanel")

        self.container = QWidget()
        self.container.setObjectName("chatContainer")

        self.message_layout = QVBoxLayout(self.container)
        self.message_layout.setContentsMargins(10, 10, 10, 10)
        self.message_layout.setSpacing(10)
        self.message_layout.addStretch()

        self.setWidget(self.container)
        self.setStyleSheet(build_chat_panel_qss())

    def _add_widget(self, widget: QWidget):
        self.message_layout.insertWidget(self.message_layout.count() - 1, widget)
        QTimer.singleShot(0, self.scroll_to_bottom)

    def append_user_message(self, text: str):
        widget = TextMessageWidget("user", text)
        self._add_widget(widget)
        return widget

    def append_ai_message(self, text: str):
        widget = TextMessageWidget("ai", text)
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
        widget = AudioMessageWidget(text)
        self._add_widget(widget)
        return widget

    def append_record_message(self, record_path: str, duration_ms: int = 0):
        widget = RecordMessageWidget(record_path=record_path, duration_ms=duration_ms)
        self._add_widget(widget)
        return widget

    # =========================
    # 流式消息接口
    # =========================
    def begin_ai_text_stream(self, initial_text: str = ""):
        widget = TextMessageWidget("ai", initial_text or "...")
        self._add_widget(widget)
        return widget

    def begin_ai_audio_stream(self, initial_text: str = ""):
        widget = AudioMessageWidget(initial_text or "...")
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

    def scroll_to_bottom(self):
        bar = self.verticalScrollBar()
        bar.setValue(bar.maximum())