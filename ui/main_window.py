import os
import time
from typing import Optional

from PySide6.QtCore import Qt, QTimer, Signal, QUrl, QEvent, QSize, QPoint
from PySide6.QtGui import QKeyEvent, QDesktopServices, QIcon, QMovie
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPlainTextEdit,
    QPushButton, QLabel, QMessageBox, QFrame, QMenu
)

from ui.main_window_config import (
    MAIN_WINDOW_SIZE,
    MAIN_WINDOW_COLOR,
    build_main_window_qss,
    build_folder_menu_qss,
)  
from ui.chat_panel import ChatPanel 
from ui.components.main_top_toolbar import MainTopToolbar  
from ui.components.main_status_popup import MainStatusPopup  
from ui.components.main_settings_popup import MainSettingsPopup 
from config import DEFAULT_OUTPUT_MODE, APP_ICON_FILE  


class SendTextEdit(QPlainTextEdit):
    double_enter_send = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.last_enter_time = 0.0
        self.enter_interval = 0.4

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            now = time.time()

            if now - self.last_enter_time <= self.enter_interval:
                self.last_enter_time = 0.0
                self.double_enter_send.emit()
                event.accept()
                return

            self.last_enter_time = now
            super().keyPressEvent(event)
            return

        super().keyPressEvent(event)


class MainWindow(QWidget):
    send_text_requested = Signal(str)
    start_record_requested = Signal()
    stop_record_requested = Signal()
    refresh_requested = Signal()
    restart_requested = Signal()
    exit_requested = Signal()
    close_requested = Signal()
    open_control_center_requested = Signal()
    open_folder_requested = Signal(str)
    open_reply_pipeline_requested = Signal()

    record_play_requested = Signal()
    record_pause_requested = Signal()
    record_seek_requested = Signal(float)
    record_speed_changed = Signal(float)

    output_mode_changed = Signal(str)
    minimized_changed = Signal(bool)

    def __init__(self):
        super().__init__()

        self.setWindowTitle("本地桌面语音 AI 原型")
        self.setWindowIcon(QIcon(APP_ICON_FILE))
        self.resize(
            MAIN_WINDOW_SIZE["window_width"],
            MAIN_WINDOW_SIZE["window_height"]
        )
        self.setMinimumSize(
            MAIN_WINDOW_SIZE["window_min_width"],
            MAIN_WINDOW_SIZE["window_min_height"]
        )

        self.current_recognized_text = ""
        self.record_seconds = 0
        self.min_record_seconds = 2
        self.max_record_seconds = 60

        self.record_timer = QTimer(self)
        self.record_timer.timeout.connect(self.update_record_progress)

        self.record_total_ms = 0
        self.record_current_ms = 0
        self.record_is_playing = False
        self.record_speed = 1.0
        self._record_playback_enabled = False

        self.current_output_mode = DEFAULT_OUTPUT_MODE
        self.current_state_summary = ""
        self.runtime_state_data = {
            "role": "-",
            "model": "-",
            "tts_backend": "-",
            "tts_package": "-",
            "style": "-",
            "performance": "-",
            "output_mode": "文字+语音",
            "tts_runtime": "-",
            "asr_runtime": "就绪",
        }

        self._allow_direct_close = False
        self._closing_in_progress = False
        self._last_minimized_state = False

        self.loading_gif_path = os.path.join(os.path.dirname(APP_ICON_FILE), "乐乐.gif")
        self.loading_base_text = "AI 正在思考"

        self.hint_timer = QTimer(self)
        self.hint_timer.setSingleShot(True)
        self.hint_timer.timeout.connect(self.hide_hint_bar)

        self.init_ui()
        self.init_loading_overlay()
        self.init_folder_menu()
        self.folder_menu.setStyleSheet(build_folder_menu_qss())

        self.setStyleSheet(build_main_window_qss())
        self._refresh_main_action_button_skins()
        self._show_current_output_mode_hint()

    # =========================
    # UI 初始化
    # =========================
    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(
            MAIN_WINDOW_SIZE["outer_margin"],
            MAIN_WINDOW_SIZE["outer_margin"],
            MAIN_WINDOW_SIZE["outer_margin"],
            MAIN_WINDOW_SIZE["outer_margin"]
        )
        main_layout.setSpacing(MAIN_WINDOW_SIZE["outer_spacing"])

        # 顶部工具栏
        self.top_toolbar = MainTopToolbar(self)
        self.top_toolbar.reply_text_requested.connect(self.on_open_reply_pipeline_clicked)
        self.top_toolbar.status_requested.connect(self.show_status_popup)
        self.top_toolbar.settings_requested.connect(self.show_settings_popup)
        main_layout.addWidget(self.top_toolbar)

        # 极薄提示条
        self.runtime_hint_frame = QFrame()
        self.runtime_hint_frame.setObjectName("runtimeHintFrame")
        self.runtime_hint_frame.setFixedHeight(MAIN_WINDOW_SIZE["hint_bar_height"])
        hint_layout = QHBoxLayout(self.runtime_hint_frame)
        hint_layout.setContentsMargins(6, 0, 6, 0)

        self.runtime_hint_label = QLabel("")
        self.runtime_hint_label.setObjectName("runtimeHintLabel")
        hint_layout.addWidget(self.runtime_hint_label)

        self.runtime_hint_frame.hide()
        main_layout.addWidget(self.runtime_hint_frame)

        # 主卡片
        self.main_card = QFrame()
        self.main_card.setObjectName("mainCard")

        card_layout = QVBoxLayout(self.main_card)
        card_layout.setContentsMargins(
            MAIN_WINDOW_SIZE["card_margin"],
            MAIN_WINDOW_SIZE["card_margin"],
            MAIN_WINDOW_SIZE["card_margin"],
            MAIN_WINDOW_SIZE["card_margin"]
        )
        card_layout.setSpacing(MAIN_WINDOW_SIZE["card_spacing"])

        self.chat_panel = ChatPanel()
        card_layout.addWidget(self.chat_panel, stretch=1)

        input_label = QLabel("文本输入区，回车换行，双击回车发送")
        input_label.setObjectName("sectionLabel")
        card_layout.addWidget(input_label)

        self.text_input = SendTextEdit()
        self.text_input.setPlaceholderText("请输入文字，或将语音识别结果发送给 AI...")
        self.text_input.setMaximumHeight(MAIN_WINDOW_SIZE["text_input_max_height"])
        self.text_input.setObjectName("textInput")
        self.text_input.double_enter_send.connect(self.on_send_text_clicked)
        card_layout.addWidget(self.text_input)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(MAIN_WINDOW_SIZE["main_action_spacing"])

        self.send_text_btn = QPushButton("发送文字")
        self.send_text_btn.setObjectName("mainBottomActionButton")
        self.send_text_btn.clicked.connect(self.on_send_text_clicked)

        self.start_record_btn = QPushButton("开始录音")
        self.start_record_btn.setObjectName("mainBottomActionButton")
        self.start_record_btn.clicked.connect(self.on_start_record_clicked)

        self.stop_record_btn = QPushButton("停止录音")
        self.stop_record_btn.setObjectName("mainBottomActionButton")
        self.stop_record_btn.setEnabled(False)
        self.stop_record_btn.clicked.connect(self.on_stop_record_clicked)

        btn_row.addWidget(self.send_text_btn)
        btn_row.addWidget(self.start_record_btn)
        btn_row.addWidget(self.stop_record_btn)
        self._refresh_main_action_button_skins()

        card_layout.addLayout(btn_row)
        main_layout.addWidget(self.main_card)

        # 两个轻弹窗
        self.status_popup = MainStatusPopup(self)
        self.settings_popup = MainSettingsPopup(self)

        self.settings_popup.control_center_requested.connect(self.on_open_control_center_clicked)
        self.settings_popup.output_mode_selected.connect(self.on_output_mode_selected)
        self.settings_popup.folder_menu_requested.connect(self.on_folder_menu_requested)
        self.settings_popup.restart_requested.connect(self.on_restart_clicked)

        self.status_popup.set_status_data(self.runtime_state_data)
        self.settings_popup.set_current_mode(self.current_output_mode)

    # =========================
    # 顶部弹窗
    # =========================
    def show_status_popup(self):
        self.settings_popup.hide()
        self.status_popup.set_status_data(self.runtime_state_data)

        btn = self.top_toolbar.status_btn
        popup_size = self.status_popup.sizeHint()
        global_pos = btn.mapToGlobal(
            QPoint(btn.width() - popup_size.width(), btn.height() + 8)
        )
        self.status_popup.show_at(global_pos)

    def show_settings_popup(self):
        self.status_popup.hide()
        self.settings_popup.set_current_mode(self.current_output_mode)

        btn = self.top_toolbar.settings_btn
        popup_size = self.settings_popup.sizeHint()
        global_pos = btn.mapToGlobal(
            QPoint(btn.width() - popup_size.width(), btn.height() + 8)
        )
        self.settings_popup.show_at(global_pos)

    def on_open_reply_pipeline_clicked(self):
        self.open_reply_pipeline_requested.emit()

    def on_restart_clicked(self):
        self.restart_requested.emit()

    def on_folder_menu_requested(self, global_pos):
        self.folder_menu.popup(global_pos)

    # =========================
    # 提示条
    # =========================
    def show_hint_bar(self, text: str, duration_ms: int = 2200):
        self.runtime_hint_label.setText(text)
        self.runtime_hint_frame.show()
        self.hint_timer.stop()
        self.hint_timer.start(duration_ms)

    def hide_hint_bar(self):
        self.runtime_hint_frame.hide()
        self.runtime_hint_label.clear()

    def _show_current_output_mode_hint(self):
        self.show_hint_bar(
            f"当前输出模式：{self.get_output_mode_display_name(self.current_output_mode)}",
            1600
        )

    def set_status(self, text: str, temporary: bool = True):
        if not text:
            return

        if temporary:
            self.show_hint_bar(text, 2200)
        else:
            self.runtime_hint_label.setText(text)
            self.runtime_hint_frame.show()
            self.hint_timer.stop()

    def restore_runtime_state_summary(self, token: Optional[int] = None):
        self.hide_hint_bar()

    # =========================
    # runtime 摘要 / 数据
    # =========================
    def _parse_runtime_summary(self, summary: str) -> dict:
        result = dict(self.runtime_state_data)

        if not summary:
            return result

        parts = [p.strip() for p in summary.split("|") if p.strip()]
        key_map = {
            "当前角色": "role",
            "语言模型": "model",
            "语音后端": "tts_backend",
            "语音包": "tts_package",
            "文本模板": "style",
            "表现模板": "performance",
            "输出": "output_mode",
        }

        for part in parts:
            if "：" in part:
                k, v = part.split("：", 1)
            elif ":" in part:
                k, v = part.split(":", 1)
            else:
                continue

            k = k.strip()
            v = v.strip()

            real_key = key_map.get(k)
            if real_key:
                result[real_key] = v

        return result

    def set_runtime_state_summary(self, text: str):
        self.current_state_summary = text or ""
        parsed = self._parse_runtime_summary(self.current_state_summary)

        # 保留运行时状态字段
        parsed["tts_runtime"] = self.runtime_state_data.get("tts_runtime", "-")
        parsed["asr_runtime"] = self.runtime_state_data.get("asr_runtime", "就绪")

        self.runtime_state_data = parsed
        self.status_popup.set_status_data(self.runtime_state_data)

    def set_runtime_state_data(self, data: dict):
        patched = dict(self.runtime_state_data)
        patched.update(data or {})
        self.runtime_state_data = patched
        self.status_popup.set_status_data(self.runtime_state_data)

    def set_tts_runtime_status(self, text: str):
        self.runtime_state_data["tts_runtime"] = text or "-"
        self.status_popup.set_status_data(self.runtime_state_data)

    def set_asr_runtime_status(self, text: str):
        self.runtime_state_data["asr_runtime"] = text or "-"
        self.status_popup.set_status_data(self.runtime_state_data)

    # =========================
    # 聊天显示
    # =========================
    def append_user_message(self, text: str):
        self.chat_panel.append_user_message(text)

    def append_ai_message(self, text: str):
        self.chat_panel.append_ai_message(text)

    def append_recognized_message(self, text: str):
        self.chat_panel.append_recognized_message(text)

    def append_system_message(self, text: str):
        self.chat_panel.append_system_message(text)

    def append_ai_audio_message(self, text: str):
        return self.chat_panel.append_ai_audio_message(text)

    def begin_ai_stream_message(self, mode: str, initial_text: str = ""):
        if mode == "text_only":
            return self.chat_panel.begin_ai_text_stream(initial_text)
        return self.chat_panel.begin_ai_audio_stream(initial_text)

    def update_ai_stream_message(self, widget, text: str):
        self.chat_panel.update_message_text(widget, text)

    def update_ai_stream_status(self, widget, text: str):
        self.chat_panel.update_message_status(widget, text)

    def finish_ai_stream_message(self, widget):
        self.chat_panel.finish_stream_message(widget)
    
    def append_record_message(self, record_path: str, duration_ms: int = 0):
        return self.chat_panel.append_record_message(record_path, duration_ms)

    # =========================
    # 录音界面（第一批仅保留逻辑，不再显示旧录音状态栏）
    # =========================
    def reset_record_ui(self):
        self.record_seconds = 0
        self.start_record_btn.setEnabled(True)
        self.stop_record_btn.setEnabled(False)
        self._refresh_main_action_button_skins()

    def start_record_ui(self):
        self.record_seconds = 0
        self.start_record_btn.setEnabled(False)
        self.stop_record_btn.setEnabled(True)
        self._refresh_main_action_button_skins()
        self.set_status("开始录音")
        self.record_timer.start(1000)

    def stop_record_ui(self):
        self.record_timer.stop()
        self.start_record_btn.setEnabled(True)
        self.stop_record_btn.setEnabled(False)
        self._refresh_main_action_button_skins()

        if self.record_seconds < self.min_record_seconds:
            self.set_status("录音不足 2 秒，请重新录音")
        else:
            self.set_status("录音完成，正在自动识别语音...")

    def update_record_progress(self):
        self.record_seconds += 1
        if self.record_seconds >= self.max_record_seconds:
            self.record_timer.stop()
            self.set_status("已达到 60 秒上限，自动停止录音")
            self.on_stop_record_clicked()

    # =========================
    # 加载浮层（保留）
    # =========================
    def init_loading_overlay(self):
        self.chat_panel.viewport().installEventFilter(self)

        self.loading_overlay = QFrame(self.chat_panel.viewport())
        self.loading_overlay.setObjectName("chatLoadingOverlay")
        self.loading_overlay.hide()
        self.loading_overlay.setFixedSize(170, 220)
        self.loading_overlay.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

        overlay_layout = QVBoxLayout(self.loading_overlay)
        overlay_layout.setContentsMargins(10, 10, 10, 10)
        overlay_layout.setSpacing(6)

        self.loading_gif_label = QLabel(self.loading_overlay)
        self.loading_gif_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.loading_gif_label.setStyleSheet("background: transparent;")

        self.loading_text_label = QLabel(self.loading_base_text, self.loading_overlay)
        self.loading_text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.loading_text_label.setWordWrap(True)
        self.loading_text_label.setStyleSheet(
            f"""
            background: transparent;
            color: {MAIN_WINDOW_COLOR["loading_text"]};
            font-size: {MAIN_WINDOW_SIZE["loading_text_font"]}pt;
            font-weight: bold;
            """
        )

        overlay_layout.addStretch()
        overlay_layout.addWidget(self.loading_gif_label, 0, Qt.AlignmentFlag.AlignCenter)
        overlay_layout.addWidget(self.loading_text_label, 0, Qt.AlignmentFlag.AlignCenter)
        overlay_layout.addStretch()

        self.loading_overlay.setStyleSheet(
            """
            QFrame#chatLoadingOverlay {
                background-color: rgba(8, 15, 30, 170);
                border: 1px solid rgba(120, 160, 220, 120);
                border-radius: 14px;
            }
            """
        )

        self.loading_movie = QMovie(self.loading_gif_path)
        if self.loading_movie.isValid():
            self.loading_movie.setScaledSize(QSize(110, 110))
            self.loading_gif_label.setMovie(self.loading_movie)
        else:
            self.loading_gif_label.setText("加载中")

        self._update_loading_overlay_geometry()

    def _update_loading_overlay_geometry(self):
        if hasattr(self, "loading_overlay") and self.loading_overlay is not None:
            viewport = self.chat_panel.viewport()
            overlay_w = self.loading_overlay.width()
            overlay_h = self.loading_overlay.height()

            right_margin = 16
            top_margin = 18

            x = max(0, viewport.width() - overlay_w - right_margin)
            y = max(0, top_margin)

            self.loading_overlay.move(x, y)
            self.loading_overlay.raise_()

    def show_loading_overlay(self, text: str = "AI 正在思考"):
        self.loading_base_text = text
        self.loading_text_label.setText(text)
        self._update_loading_overlay_geometry()
        self.loading_overlay.show()
        self.loading_overlay.raise_()

        if hasattr(self, "loading_movie") and self.loading_movie is not None:
            if self.loading_movie.isValid():
                self.loading_movie.start()

    def hide_loading_overlay(self):
        if hasattr(self, "loading_movie") and self.loading_movie is not None:
            if self.loading_movie.isValid():
                self.loading_movie.stop()

        if hasattr(self, "loading_overlay") and self.loading_overlay is not None:
            self.loading_overlay.hide()

    def eventFilter(self, watched, event):
        if watched is self.chat_panel.viewport():
            if event.type() in (QEvent.Type.Resize, QEvent.Type.Show):
                self._update_loading_overlay_geometry()
        return super().eventFilter(watched, event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_loading_overlay_geometry()

    # =========================
    # 文件夹菜单
    # =========================
    def init_folder_menu(self):
        self.folder_menu = QMenu(self)

        action_downloads = self.folder_menu.addAction("打开下载文件夹")
        action_favorites = self.folder_menu.addAction("打开收藏文件夹")
        action_records = self.folder_menu.addAction("打开录音文件夹")
        action_replies = self.folder_menu.addAction("打开回复音频文件夹")
        action_temp = self.folder_menu.addAction("打开临时文件夹")

        action_downloads.triggered.connect(lambda: self.open_folder_requested.emit("downloads"))
        action_favorites.triggered.connect(lambda: self.open_folder_requested.emit("favorites"))
        action_records.triggered.connect(lambda: self.open_folder_requested.emit("records"))
        action_replies.triggered.connect(lambda: self.open_folder_requested.emit("replies"))
        action_temp.triggered.connect(lambda: self.open_folder_requested.emit("temp"))

    # =========================
    # 输出模式
    # =========================
    def get_output_mode_display_name(self, mode: str) -> str:
        return {
            "text_only": "仅文字",
            "text_voice": "文字+语音",
            "voice_only": "仅语音",
        }.get(mode, "文字+语音")

    def on_output_mode_selected(self, mode: str):
        self.set_output_mode(mode)
        self.output_mode_changed.emit(mode)
        self.show_hint_bar(f"当前输出模式：{self.get_output_mode_display_name(mode)}", 1600)

    def set_output_mode(self, mode: str):
        self.current_output_mode = mode
        self.settings_popup.set_current_mode(mode)
        self.runtime_state_data["output_mode"] = self.get_output_mode_display_name(mode)
        self.status_popup.set_status_data(self.runtime_state_data)

    def open_local_folder(self, folder_path: str):
        QDesktopServices.openUrl(QUrl.fromLocalFile(folder_path))

    # =========================
    # 外部可调用
    # =========================
    def set_recognized_text(self, text: str):
        self.current_recognized_text = text.strip()

        if self.current_recognized_text:
            self.append_recognized_message(self.current_recognized_text)
            self.set_status("语音识别完成")
        else:
            self.set_status("未识别到有效语音内容")

    def clear_page(self):
        self.chat_panel.clear_messages()
        self.text_input.clear()
        self.current_recognized_text = ""
        self.reset_record_ui()
        self.hide_loading_overlay()
        self.hide_hint_bar()
        self._show_current_output_mode_hint()
    def _apply_button_skin(self, button: QPushButton, skin: str):
        button.setProperty("skin", skin)
        button.style().unpolish(button)
        button.style().polish(button)
        button.update()

    def _refresh_main_action_button_skins(self):
        # 发送按钮：正常一直蓝色，禁用时自动走 disabled 样式
        self._apply_button_skin(self.send_text_btn, "blue")

        # 开始录音按钮：
        # 正常可点 = 蓝色
        # 已开始录音后 = 粉色（即使此时按钮被禁用，也保持粉色皮肤）
        if self.start_record_btn.isEnabled():
            self._apply_button_skin(self.start_record_btn, "blue")
        else:
            self._apply_button_skin(self.start_record_btn, "pink")

        # 停止录音按钮：
        # 可点击 = 红色
        # 不可点击 = 灰色按钮底图
        if self.stop_record_btn.isEnabled():
            self._apply_button_skin(self.stop_record_btn, "red")
        else:
            self._apply_button_skin(self.stop_record_btn, "disabled")
    # =========================
    # 按钮事件
    # =========================
    def on_send_text_clicked(self):
        if not self.send_text_btn.isEnabled():
            self.set_status("当前正在处理上一条请求，请稍候...")
            return

        text = self.text_input.toPlainText().strip()
        if not text:
            QMessageBox.warning(self, "提示", "请输入文本内容后再发送。")
            return

        self.send_text_requested.emit(text)

    def on_start_record_clicked(self):
        if not self.start_record_btn.isEnabled():
            self.set_status("当前暂时无法开始录音，请稍候...")
            return

        self.start_record_ui()
        self.start_record_requested.emit()

    def on_stop_record_clicked(self):
        self.stop_record_requested.emit()
        self.stop_record_ui()

    def on_refresh_clicked(self):
        self.clear_page()
        self.refresh_requested.emit()

    def on_exit_clicked(self):
        reply = QMessageBox.question(
            self,
            "确认退出",
            "退出后将结束当前系统任务，是否继续？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            self.exit_requested.emit()

    def on_open_control_center_clicked(self):
        self.open_control_center_requested.emit()

    # =========================
    # 录音回放区接口（第一批先保留方法，UI 已移除）
    # =========================
    def on_record_play_clicked(self):
        if self.record_is_playing:
            self.record_pause_requested.emit()
        else:
            self.record_play_requested.emit()

    def on_record_seek_released(self):
        if self.record_total_ms <= 0:
            return
        self.record_seek_requested.emit(0.0)

    def on_speed_menu_selected(self, speed: float):
        self.record_speed = speed
        self.record_speed_changed.emit(speed)

    def set_record_playback_enabled(self, enabled: bool):
        self._record_playback_enabled = enabled

    def set_record_play_state(self, is_playing: bool):
        self.record_is_playing = is_playing

    def set_record_duration(self, total_ms: int):
        self.record_total_ms = max(0, total_ms)

    def update_record_playback_ui(self, current_ms: int, total_ms: Optional[int] = None):
        if total_ms is not None:
            self.record_total_ms = max(0, total_ms)
        self.record_current_ms = max(0, current_ms)

    def format_ms(self, ms: int) -> str:
        seconds = max(0, int(ms / 1000))
        m = seconds // 60
        s = seconds % 60
        return f"{m}:{s:02d}"

    # =========================
    # 最小化 / 关闭
    # =========================
    def changeEvent(self, event):
        super().changeEvent(event)

        if event.type() == QEvent.Type.WindowStateChange:
            is_minimized = self.isMinimized()
            if is_minimized != self._last_minimized_state:
                self._last_minimized_state = is_minimized
                self.minimized_changed.emit(is_minimized)

    def closeEvent(self, event):
        if self._allow_direct_close:
            super().closeEvent(event)
            return

        if self._closing_in_progress:
            event.ignore()
            return

        self._closing_in_progress = True
        event.ignore()
        self.close_requested.emit()

    def allow_direct_close_once(self):
        self._allow_direct_close = True
        self._closing_in_progress = False

    def reset_close_guard(self):
        self._allow_direct_close = False
        self._closing_in_progress = False