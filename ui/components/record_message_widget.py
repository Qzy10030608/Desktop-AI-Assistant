from __future__ import annotations

from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton

from ui.main_window_config import (  # type: ignore
    MAIN_WINDOW_ASSET,
    MAIN_WINDOW_SIZE,
    build_record_message_widget_qss,
)


class RecordMessageWidget(QFrame):
    play_requested = Signal(str)

    def __init__(self, record_path: str, duration_ms: int = 0, parent=None):
        super().__init__(parent)

        self.record_path = record_path
        self.duration_ms = max(0, int(duration_ms))

        self.setObjectName("recordMessageWidget")

        root = QVBoxLayout(self)
        root.setContentsMargins(
            MAIN_WINDOW_SIZE["chat_message_margin_h"],
            MAIN_WINDOW_SIZE["chat_message_margin_v"],
            MAIN_WINDOW_SIZE["chat_message_margin_h"],
            MAIN_WINDOW_SIZE["chat_message_margin_v"],
        )
        root.setSpacing(MAIN_WINDOW_SIZE["chat_message_spacing"])

        self.title_label = QLabel("用户录音")
        self.title_label.setObjectName("msgTitle")

        self.duration_label = QLabel(self._format_duration(self.duration_ms))
        self.duration_label.setObjectName("recordMeta")

        self.recognized_label = QLabel("识别文字：识别中...")
        self.recognized_label.setObjectName("recordMeta")
        self.recognized_label.setWordWrap(True)

        meta_row = QHBoxLayout()
        meta_row.setSpacing(MAIN_WINDOW_SIZE["chat_action_spacing"])
        meta_row.addWidget(self.duration_label)
        meta_row.addStretch()

        btn_row = QHBoxLayout()
        btn_row.setSpacing(MAIN_WINDOW_SIZE["chat_action_spacing"])

        self.play_btn = QPushButton("")
        self.play_btn.setObjectName("recordPlayIconButton")
        self.play_btn.setToolTip("播放录音")
        self.play_btn.setIcon(QIcon(MAIN_WINDOW_ASSET["play_icon"]))
        self.play_btn.setIconSize(QSize(
            MAIN_WINDOW_SIZE["record_action_icon_size"],
            MAIN_WINDOW_SIZE["record_action_icon_size"],
        ))
        self.play_btn.clicked.connect(self._on_play_clicked)

        btn_row.addWidget(self.play_btn)
        btn_row.addStretch()

        root.addWidget(self.title_label)
        root.addLayout(meta_row)
        root.addWidget(self.recognized_label)
        root.addLayout(btn_row)

        self.setStyleSheet(build_record_message_widget_qss())

    def _format_duration(self, ms: int) -> str:
        seconds = max(0, int(ms / 1000))
        m = seconds // 60
        s = seconds % 60
        return f"录音时长：{m}:{s:02d}"

    def _on_play_clicked(self):
        if self.record_path:
            self.play_requested.emit(self.record_path)

    def set_recognized_text(self, text: str):
        normalized = str(text or "").strip()
        self.recognized_label.setText(
            f"识别文字：{normalized}" if normalized else "识别文字：未识别到有效语音"
        )
        self.recognized_label.show()

    def set_recognized_status(self, text: str):
        status = str(text or "").strip() or "识别中..."
        self.recognized_label.setText(f"识别文字：{status}")
        self.recognized_label.show()
