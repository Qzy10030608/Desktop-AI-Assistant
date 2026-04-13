# 页面已刷新/已切换角色/语音生成
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel


class SystemMessageWidget(QFrame):
    """
    系统提示消息组件
    """

    def __init__(self, text: str, parent=None):
        super().__init__(parent)

        self.setObjectName("systemMessageWidget")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)

        self.label = QLabel(text)
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setWordWrap(True)

        layout.addWidget(self.label)

        self.setStyleSheet("""
        QFrame#systemMessageWidget {
            background-color: #3B0764;
            border: 1px solid #7E22CE;
            border-radius: 10px;
        }
        QLabel {
            color: #F3E8FF;
            font-size: 13px;
            font-style: italic;
            background: transparent;
        }
        """)