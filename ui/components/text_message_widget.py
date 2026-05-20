from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QVBoxLayout, QLabel

from ui.main_window_config import MAIN_WINDOW_SIZE, build_text_message_widget_qss  # type: ignore


class TextMessageWidget(QFrame):
    """
    普通文本消息组件
    支持：
    - user
    - ai
    - recognized
    """

    def __init__(
        self,
        role: str,
        text: str,
        parent=None,
        assistant_display_name: str | None = None,
        title: str | None = None,
    ):
        super().__init__(parent)

        self.role = role
        self.text = text
        self.assistant_display_name = self._normalize_assistant_name(assistant_display_name)
        self.custom_title = str(title or "").strip()

        self.setObjectName("textMessageWidget")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            MAIN_WINDOW_SIZE["chat_message_margin_h"],
            MAIN_WINDOW_SIZE["chat_message_margin_v"],
            MAIN_WINDOW_SIZE["chat_message_margin_h"],
            MAIN_WINDOW_SIZE["chat_message_margin_v"],
        )
        layout.setSpacing(MAIN_WINDOW_SIZE["chat_message_spacing"])

        self.title_label = QLabel(self._get_title())
        self.title_label.setObjectName("msgTitle")

        self.text_label = QLabel(text)
        self.text_label.setWordWrap(True)
        self.text_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse |
            Qt.TextInteractionFlag.TextSelectableByKeyboard
        )
        self.text_label.setObjectName("msgText")

        layout.addWidget(self.title_label)
        layout.addWidget(self.text_label)

        self._apply_style()

    def _get_title(self) -> str:
        if self.custom_title:
            return self.custom_title
        if self.role == "ai":
            return f"{self.assistant_display_name} 回复"
        title_map = {
            "user": "用户",
            "recognized": "语音识别",
        }
        return title_map.get(self.role, "消息")

    def _normalize_assistant_name(self, value: str | None) -> str:
        name = str(value or "").strip()
        return name or "AI"

    def _apply_style(self):
        self.setStyleSheet(build_text_message_widget_qss(self.role))

    def set_text(self, text: str):
        self.text = text or ""
        self.text_label.setText(self.text)

    def set_assistant_display_name(self, name: str):
        if self.role != "ai":
            return
        self.assistant_display_name = self._normalize_assistant_name(name)
        self.title_label.setText(self._get_title())
