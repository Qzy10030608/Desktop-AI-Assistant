from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QVBoxLayout, QLabel


class TextMessageWidget(QFrame):
    """
    普通文本消息组件
    支持：
    - user
    - ai
    - recognized
    """

    def __init__(self, role: str, text: str, parent=None):
        super().__init__(parent)

        self.role = role
        self.text = text

        self.setObjectName("textMessageWidget")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)

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
        title_map = {
            "user": "用户",
            "ai": "AI",
            "recognized": "语音识别",
        }
        return title_map.get(self.role, "消息")

    def _apply_style(self):
        if self.role == "user":
            bg = "#1E3A8A"
            border = "#3B82F6"
        elif self.role == "ai":
            bg = "#111827"
            border = "#334155"
        elif self.role == "recognized":
            bg = "#3F3F46"
            border = "#71717A"
        else:
            bg = "#1F2937"
            border = "#4B5563"

        self.setStyleSheet(f"""
        QFrame#textMessageWidget {{
            background-color: {bg};
            border: 1px solid {border};
            border-radius: 12px;
        }}
        QLabel#msgTitle {{
            color: #93C5FD;
            font-size: 13pt;
            font-weight: bold;
            background: transparent;
        }}
        QLabel#msgText {{
            color: white;
            font-size: 14pt;
            background: transparent;
        }}
        """)

    def set_text(self, text: str):
        self.text = text or ""
        self.text_label.setText(self.text)