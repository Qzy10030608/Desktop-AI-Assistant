from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QFrame,
)

from config import (  # type: ignore
    WORKSPACE_RAW_REPLY_FILE,
    WORKSPACE_VISIBLE_REPLY_FILE,
    WORKSPACE_TTS_REPLY_FILE,
    APP_ICON_FILE,
)
from PySide6.QtGui import QIcon


class ReplyPipelineWindow(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("回复文本")
        self.setWindowIcon(QIcon(APP_ICON_FILE))
        self.resize(980, 760)
        self.setMinimumSize(760, 560)

        self._build_ui()
        self.load_workspace_files()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        # 顶部栏：只保留“回复文本”和“关闭”
        top_bar = QFrame()
        top_layout = QHBoxLayout(top_bar)
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(10)

        title = QLabel("回复文本")
        title.setStyleSheet("font-size: 22px; font-weight: bold; color: #FFFFFF;")

        self.btn_close = QPushButton("关闭")
        self.btn_close.setFixedHeight(38)
        self.btn_close.setFixedWidth(90)
        self.btn_close.clicked.connect(self.close)

        top_layout.addWidget(title)
        top_layout.addStretch()
        top_layout.addWidget(self.btn_close)

        root.addWidget(top_bar)

        # 提示
        tip = QLabel("下方显示当前工作区中的三类文本：原始回复、可见回复、TTS文本。")
        tip.setWordWrap(True)
        tip.setStyleSheet("color: #9FB3D9;")
        root.addWidget(tip)

        # 三块只读文本框
        self.raw_edit = self._build_block(root, "原始回复文本（raw）")
        self.visible_edit = self._build_block(root, "可见回复文本（visible）")
        self.tts_edit = self._build_block(root, "TTS 文本（tts）")

        self.setStyleSheet("""
        QWidget {
            background-color: #121212;
            color: #FFFFFF;
            font-size: 14px;
            font-family: "Microsoft YaHei";
        }
        QFrame {
            background: transparent;
        }
        QPushButton {
            background-color: #3A8DFF;
            color: #FFFFFF;
            border: none;
            border-radius: 10px;
            padding: 6px 12px;
            font-weight: bold;
        }
        QPushButton:hover {
            background-color: #4C84EC;
        }
        QPushButton:pressed {
            background-color: #255DC4;
        }
        QTextEdit {
            background-color: #232A35;
            color: #DCE8FF;
            border: 1px solid #3D3C3C;
            border-radius: 12px;
            padding: 8px;
        }
        QLabel {
            background: transparent;
        }
        """)

    def _build_block(self, parent_layout: QVBoxLayout, title_text: str) -> QTextEdit:
        title = QLabel(title_text)
        title.setStyleSheet("font-weight: bold; color: #FFFFFF;")
        parent_layout.addWidget(title)

        edit = QTextEdit()
        edit.setReadOnly(True)
        edit.setMinimumHeight(180)
        parent_layout.addWidget(edit, 1)
        return edit

    def _read_text(self, path_str: str) -> str:
        path = Path(path_str)
        if not path.exists():
            return f"文件不存在：\n{path}"
        try:
            return path.read_text(encoding="utf-8")
        except Exception as e:
            return f"读取失败：\n{path}\n\n{e}"

    def load_workspace_files(self):
        self.raw_edit.setPlainText(self._read_text(WORKSPACE_RAW_REPLY_FILE))
        self.visible_edit.setPlainText(self._read_text(WORKSPACE_VISIBLE_REPLY_FILE))
        self.tts_edit.setPlainText(self._read_text(WORKSPACE_TTS_REPLY_FILE))

    def update_reply_package(self, envelope):
        raw_text = getattr(envelope, "raw_text", "") or ""
        final_text = getattr(envelope, "final_text", "") or ""
        tts_text = getattr(envelope, "tts_text", "") or final_text

        self.raw_edit.setPlainText(raw_text)
        self.visible_edit.setPlainText(final_text)
        self.tts_edit.setPlainText(tts_text)

    def showEvent(self, event):
        self.load_workspace_files()
        super().showEvent(event)