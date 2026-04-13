import os

from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QMovie, QIcon
from PySide6.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton

from config import APP_ICON_FILE  # type: ignore
from ui.main_window_config import (  # type: ignore
    MAIN_WINDOW_ASSET,
    MAIN_WINDOW_SIZE,
    build_audio_message_widget_qss,
)


class AudioMessageWidget(QFrame):
    play_requested = Signal(str)
    favorite_requested = Signal(str)
    download_requested = Signal(str)

    def __init__(self, text: str, parent=None):
        super().__init__(parent)

        self.text = text
        self.audio_path = ""
        self.audio_ready = False
        self.is_favorite = False

        self.setObjectName("audioMessageWidget")

        root = QHBoxLayout(self)
        root.setContentsMargins(12, 10, 12, 10)
        root.setSpacing(12)

        # 左侧
        left_col = QVBoxLayout()
        left_col.setContentsMargins(0, 0, 0, 0)
        left_col.setSpacing(8)

        self.title_label = QLabel("AI")
        self.title_label.setObjectName("msgTitle")

        self.text_label = QLabel(text)
        self.text_label.setWordWrap(True)
        self.text_label.setTextInteractionFlags(Qt.TextSelectableByMouse)  # type: ignore
        self.text_label.setObjectName("msgText")

        self.status_label = QLabel("等待中...")
        self.status_label.setObjectName("audioStatus")
        self.status_label.setWordWrap(True)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(MAIN_WINDOW_SIZE["chat_action_spacing"])

        self.play_btn = QPushButton("")
        self.play_btn.setObjectName("chatActionIconButton")
        self.play_btn.setToolTip("播放语音")

        self.favorite_btn = QPushButton("")
        self.favorite_btn.setObjectName("chatActionIconButton")
        self.favorite_btn.setToolTip("收藏")

        self.download_btn = QPushButton("")
        self.download_btn.setObjectName("chatActionIconButton")
        self.download_btn.setToolTip("下载")

        for btn in [self.play_btn, self.favorite_btn, self.download_btn]:
            btn.setIconSize(QSize(
                MAIN_WINDOW_SIZE["chat_action_icon_size"],
                MAIN_WINDOW_SIZE["chat_action_icon_size"],
            ))

        self.play_btn.setEnabled(False)
        self.favorite_btn.setEnabled(False)
        self.download_btn.setEnabled(False)

        self.play_btn.clicked.connect(self._on_play_clicked)
        self.favorite_btn.clicked.connect(self._on_favorite_clicked)
        self.download_btn.clicked.connect(self._on_download_clicked)

        btn_row.addWidget(self.play_btn)
        btn_row.addWidget(self.favorite_btn)
        btn_row.addWidget(self.download_btn)
        btn_row.addStretch()

        left_col.addWidget(self.title_label)
        left_col.addWidget(self.text_label)
        left_col.addWidget(self.status_label)
        left_col.addLayout(btn_row)

        # 右侧
        self.visual_frame = QFrame()
        self.visual_frame.setObjectName("visualFrame")
        self.visual_frame.setFixedWidth(120)

        visual_layout = QVBoxLayout(self.visual_frame)
        visual_layout.setContentsMargins(4, 4, 4, 4)
        visual_layout.setSpacing(4)

        self.gif_label = QLabel()
        self.gif_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.gif_label.setFixedSize(104, 104)
        self.gif_label.setStyleSheet("background: transparent;")

        self.visual_text_label = QLabel("思考中")
        self.visual_text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.visual_text_label.setWordWrap(True)
        self.visual_text_label.setObjectName("visualText")

        visual_layout.addStretch()
        visual_layout.addWidget(self.gif_label, 0, Qt.AlignmentFlag.AlignCenter)
        visual_layout.addWidget(self.visual_text_label, 0, Qt.AlignmentFlag.AlignCenter)
        visual_layout.addStretch()

        root.addLayout(left_col, 1)
        root.addWidget(self.visual_frame, 0)

        self.setStyleSheet(build_audio_message_widget_qss())

        self._init_movie()
        self._refresh_action_icons()
        self.set_loading_visible(False)

    def _init_movie(self):
        gif_path = os.path.join(os.path.dirname(APP_ICON_FILE), "乐乐.gif")
        self.loading_movie = QMovie(gif_path)
        if self.loading_movie.isValid():
            self.loading_movie.setScaledSize(QSize(96, 96))
            self.gif_label.setMovie(self.loading_movie)
        else:
            self.gif_label.setText("...")
            self.gif_label.setStyleSheet("color: white; font-size: 24px; background: transparent;")

    def _refresh_action_icons(self):
        self.play_btn.setIcon(QIcon(MAIN_WINDOW_ASSET["play_icon"]))
        self.download_btn.setIcon(QIcon(MAIN_WINDOW_ASSET["download_icon"]))

        fav_icon = (
            MAIN_WINDOW_ASSET["favorite_on_icon"]
            if self.is_favorite
            else MAIN_WINDOW_ASSET["favorite_off_icon"]
        )
        self.favorite_btn.setIcon(QIcon(fav_icon))
        self.favorite_btn.setToolTip("取消收藏" if self.is_favorite else "收藏")

    def set_favorite_state(self, is_favorite: bool):
        self.is_favorite = bool(is_favorite)
        self._refresh_action_icons()

    def set_text(self, text: str):
        self.text = text or ""
        self.text_label.setText(self.text)

    def set_status_text(self, text: str):
        self.status_label.setText(text or "")

    def set_visual_text(self, text: str):
        self.visual_text_label.setText(text or "")

    def set_loading_visible(self, visible: bool, visual_text: str = "思考中"):
        self.visual_frame.setVisible(visible)
        self.visual_text_label.setText(visual_text)

        if hasattr(self, "loading_movie") and self.loading_movie is not None and self.loading_movie.isValid():
            if visible:
                self.loading_movie.start()
            else:
                self.loading_movie.stop()

    def set_waiting(self):
        self.audio_ready = False
        self.audio_path = ""
        self.status_label.setText("等待中...")
        self.play_btn.setEnabled(False)
        self.favorite_btn.setEnabled(False)
        self.download_btn.setEnabled(False)
        self.set_loading_visible(True, "思考中")
        self._refresh_action_icons()

    def set_streaming(self):
        self.audio_ready = False
        self.audio_path = ""
        self.status_label.setText("回复生成中...")
        self.play_btn.setEnabled(False)
        self.favorite_btn.setEnabled(False)
        self.download_btn.setEnabled(False)
        self.set_loading_visible(True, "生成回复")
        self._refresh_action_icons()

    def set_tts_generating(self):
        self.audio_ready = False
        self.audio_path = ""
        self.status_label.setText("语音生成中...")
        self.play_btn.setEnabled(False)
        self.favorite_btn.setEnabled(False)
        self.download_btn.setEnabled(False)
        self.set_loading_visible(True, "生成语音")
        self._refresh_action_icons()

    def finish_stream(self):
        self.set_loading_visible(False)

    def set_audio_ready(self, audio_path: str):
        self.audio_path = audio_path
        self.audio_ready = True
        self.status_label.setText("语音已生成")
        self.play_btn.setEnabled(True)
        self.favorite_btn.setEnabled(True)
        self.download_btn.setEnabled(True)
        self.set_loading_visible(False)
        self._refresh_action_icons()

    def set_audio_error(self, message: str):
        self.audio_path = ""
        self.audio_ready = False
        self.status_label.setText(f"语音生成失败：{message}")
        self.play_btn.setEnabled(False)
        self.favorite_btn.setEnabled(False)
        self.download_btn.setEnabled(False)
        self.set_loading_visible(False)
        self._refresh_action_icons()

    def _on_play_clicked(self):
        if self.audio_ready and self.audio_path:
            self.play_requested.emit(self.audio_path)

    def _on_favorite_clicked(self):
        if self.audio_ready and self.audio_path:
            self.favorite_requested.emit(self.audio_path)
            self.is_favorite = not self.is_favorite
            self._refresh_action_icons()

    def _on_download_clicked(self):
        if self.audio_ready and self.audio_path:
            self.download_requested.emit(self.audio_path)