# 页面已刷新/已切换角色/语音生成
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel

from ui.main_window_config import MAIN_WINDOW_SIZE, build_system_message_widget_qss  # type: ignore


class SystemMessageWidget(QFrame):
    """
    系统提示消息组件
    """

    def __init__(self, text: str, parent=None, kind: str = "system"):
        super().__init__(parent)
        self.kind = str(kind or "system")

        self.setObjectName("systemMessageWidget")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(
            MAIN_WINDOW_SIZE["chat_message_margin_h"],
            MAIN_WINDOW_SIZE["chat_message_margin_v"],
            MAIN_WINDOW_SIZE["chat_message_margin_h"],
            MAIN_WINDOW_SIZE["chat_message_margin_v"],
        )

        self.label = QLabel(text)
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setWordWrap(True)

        layout.addWidget(self.label)

        self.setStyleSheet(build_system_message_widget_qss(self.kind))
