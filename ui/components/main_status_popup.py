from __future__ import annotations

from typing import Dict

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QGridLayout, QFrame

from ui.main_window_config import MAIN_WINDOW_SIZE, MAIN_WINDOW_COLOR  # type: ignore


class MainStatusPopup(QWidget):
    """
    系统状态弹窗
    - 使用 Qt.Popup：点击外部自动关闭
    - 只读摘要，不承担设置功能
    """

    FIELD_ORDER = [
        ("当前角色", "role"),
        ("语言模型", "model"),
        ("语音后端", "tts_backend"),
        ("语音包", "tts_package"),
        ("文本模板", "style"),
        ("表现模板", "performance"),
        ("输出模式", "output_mode"),
        ("外接TTS状态", "tts_runtime"),
        ("ASR状态", "asr_runtime"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent, Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self.setObjectName("mainStatusPopup")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        self.value_labels: Dict[str, QLabel] = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(10)

        title = QLabel("系统状态")
        title.setObjectName("popupTitle")
        root.addWidget(title)

        line = QFrame()
        line.setObjectName("popupLine")
        line.setFixedHeight(1)
        root.addWidget(line)

        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(8)

        for row, (label_text, key) in enumerate(self.FIELD_ORDER):
            left = QLabel(label_text)
            left.setObjectName("popupKeyLabel")

            right = QLabel("-")
            right.setObjectName("popupValueLabel")
            right.setWordWrap(True)
            right.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

            self.value_labels[key] = right
            grid.addWidget(left, row, 0, Qt.AlignmentFlag.AlignTop)
            grid.addWidget(right, row, 1, Qt.AlignmentFlag.AlignTop)

        root.addLayout(grid)

        self.setStyleSheet(f"""
        QWidget#mainStatusPopup {{
            background-color: {MAIN_WINDOW_COLOR["popup_bg"]};
            border: 1px solid {MAIN_WINDOW_COLOR["popup_border"]};
            border-radius: {MAIN_WINDOW_SIZE["radius_medium"]}px;
        }}

        QLabel#popupTitle {{
            color: {MAIN_WINDOW_COLOR["text_main"]};
            font-size: {MAIN_WINDOW_SIZE["font_section"]}pt;
            font-weight: bold;
            background: transparent;
        }}

        QFrame#popupLine {{
            background-color: {MAIN_WINDOW_COLOR["popup_line"]};
            border: none;
        }}

        QLabel#popupKeyLabel {{
            color: {MAIN_WINDOW_COLOR["text_soft"]};
            font-size: {MAIN_WINDOW_SIZE["font_small"]}pt;
            font-weight: bold;
            background: transparent;
        }}

        QLabel#popupValueLabel {{
            color: {MAIN_WINDOW_COLOR["text_main"]};
            font-size: {MAIN_WINDOW_SIZE["font_small"]}pt;
            background: transparent;
        }}
        """)

        self.resize(
            MAIN_WINDOW_SIZE["status_popup_width"],
            MAIN_WINDOW_SIZE["status_popup_height"],
        )

    def set_status_data(self, data: Dict[str, str]):
        data = data or {}
        for _, key in self.FIELD_ORDER:
            self.value_labels[key].setText(str(data.get(key, "-")))

    def show_at(self, global_pos):
        self.adjustSize()
        self.move(global_pos)
        self.show()
        self.raise_()