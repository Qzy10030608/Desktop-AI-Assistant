from __future__ import annotations

from PySide6.QtCore import Qt, QSize, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel, QToolButton

from ui.main_window_config import MAIN_WINDOW_SIZE, MAIN_WINDOW_COLOR, MAIN_WINDOW_ASSET  # type: ignore


class MainTopToolbar(QWidget):
    reply_text_requested = Signal()
    status_requested = Signal()
    settings_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("mainTopToolbar")

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(MAIN_WINDOW_SIZE["toolbar_spacing"])

        self.title_label = QLabel("本地桌面语音 AI")
        self.title_label.setObjectName("toolbarTitleLabel")

        root.addWidget(self.title_label)
        root.addStretch()

        self.reply_btn = QToolButton()
        self.reply_btn.setObjectName("replyToolbarButton")
        self.reply_btn.setToolTip("回复文本")
        self.reply_btn.setIconSize(QSize(
            MAIN_WINDOW_SIZE["toolbar_icon_size"],
            MAIN_WINDOW_SIZE["toolbar_icon_size"],
        ))
        self.reply_btn.setFixedSize(
            MAIN_WINDOW_SIZE["toolbar_button_size"],
            MAIN_WINDOW_SIZE["toolbar_button_size"],
        )
        self.reply_btn.clicked.connect(self.reply_text_requested.emit)

        self.status_btn = QToolButton()
        self.status_btn.setObjectName("statusToolbarButton")
        self.status_btn.setToolTip("系统状态")
        self.status_btn.setIconSize(QSize(
            MAIN_WINDOW_SIZE["toolbar_icon_size"],
            MAIN_WINDOW_SIZE["toolbar_icon_size"],
        ))
        self.status_btn.setFixedSize(
            MAIN_WINDOW_SIZE["toolbar_button_size"],
            MAIN_WINDOW_SIZE["toolbar_button_size"],
        )
        self.status_btn.clicked.connect(self.status_requested.emit)

        self.settings_btn = QToolButton()
        self.settings_btn.setObjectName("settingsToolbarButton")
        self.settings_btn.setToolTip("设置")
        self.settings_btn.setIconSize(QSize(
            MAIN_WINDOW_SIZE["toolbar_icon_size"],
            MAIN_WINDOW_SIZE["toolbar_icon_size"],
        ))
        self.settings_btn.setFixedSize(
            MAIN_WINDOW_SIZE["toolbar_button_size"],
            MAIN_WINDOW_SIZE["toolbar_button_size"],
        )
        self.settings_btn.clicked.connect(self.settings_requested.emit)

        self._apply_icon(self.reply_btn, MAIN_WINDOW_ASSET["reply_icon"])
        self._apply_icon(self.status_btn, MAIN_WINDOW_ASSET["status_icon"])
        self._apply_icon(self.settings_btn, MAIN_WINDOW_ASSET["settings_icon"])

        root.addWidget(self.reply_btn, 0, Qt.AlignmentFlag.AlignVCenter)
        root.addWidget(self.status_btn, 0, Qt.AlignmentFlag.AlignVCenter)
        root.addWidget(self.settings_btn, 0, Qt.AlignmentFlag.AlignVCenter)

        self.setStyleSheet(f"""
        QWidget#mainTopToolbar {{
            background: transparent;
        }}

        QLabel#toolbarTitleLabel {{
            color: {MAIN_WINDOW_COLOR["text_main"]};
            font-size: {MAIN_WINDOW_SIZE["font_title"]}pt;
            font-weight: bold;
            background: transparent;
            padding: 2px 0 2px 2px;
        }}

        QToolButton#replyToolbarButton,
        QToolButton#statusToolbarButton,
        QToolButton#settingsToolbarButton {{
            border: 1px solid {MAIN_WINDOW_COLOR["toolbar_button_border_bright"]};
            border-radius: {MAIN_WINDOW_SIZE["radius_small"]}px;
            background-color: {MAIN_WINDOW_COLOR["toolbar_button_bg_bright"]};
        }}

        QToolButton#replyToolbarButton:hover,
        QToolButton#statusToolbarButton:hover,
        QToolButton#settingsToolbarButton:hover {{
            background-color: {MAIN_WINDOW_COLOR["toolbar_button_hover_bright"]};
        }}
        """)

    def _apply_icon(self, button: QToolButton, icon_path: str):
        icon = QIcon(icon_path)
        if not icon.isNull():
            button.setIcon(icon)
        else:
            button.setText("•")