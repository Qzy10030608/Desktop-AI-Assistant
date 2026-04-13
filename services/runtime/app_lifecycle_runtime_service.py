from __future__ import annotations

import os
import sys
import subprocess
from typing import Any

import sounddevice as sd
from PySide6.QtCore import QTimer, QUrl
from PySide6.QtWidgets import QApplication


class AppLifecycleRuntimeService:
    """
    应用生命周期运行时服务
    -------------------------
    负责：
    - 页面刷新
    - 退出流程
    - 重启流程
    - 等待线程结束
    - 退出后的 temp 清理与窗口关闭
    """

    def __init__(self, controller: Any):
        self.c = controller

    def wait_thread(self, thread, timeout: int = 3000):
        if thread is None:
            return
        try:
            if thread.isRunning():
                thread.quit()
                thread.wait(timeout)
        except Exception:
            pass

    def wait_all_tts_threads(self, timeout: int = 3000):
        for thread in list(self.c.tts_threads.values()):
            self.wait_thread(thread, timeout)

    def handle_refresh(self):
        self.c.session_service.new_session()

        self.c.record_player.stop()
        self.c.ai_player.stop()
        self.c.window.hide_loading_overlay()

        self.c.record_player.setPlaybackRate(1.0)

        self.wait_thread(self.c.chat_thread, 800)
        self.wait_thread(self.c.asr_thread, 800)
        self.wait_all_tts_threads(800)

        self.c.current_recognized_text = ""
        self.c.current_record_path = ""
        self.c.current_reply_audio_path = ""
        self.c.chat_history = []
        self.c.pending_audio_widgets = {}
        self.c.tts_task_sessions = {}
        self.c.request_start_times = {}
        self.c.chat_in_progress = False
        self.c.tts_threads = {}
        self.c.tts_workers = {}
        self.c.active_stream_states = {}

        self.c.window.clear_page()
        self.c.window.set_record_playback_enabled(False)
        self.c.window.set_record_play_state(False)
        self.c.window.update_record_playback_ui(0, 0)
        self.c.window.set_status("页面已刷新")

        self.c._set_busy(False)
        self.c.window.stop_record_btn.setEnabled(False)

    def handle_restart(self):
        if self.c._is_exiting:
            return

        try:
            subprocess.Popen(
                [sys.executable, *sys.argv],
                cwd=os.getcwd(),
                close_fds=True,
            )
        except Exception as e:
            self.c.window.set_status(f"重启失败：{e}")
            return

        self.handle_exit()

    def handle_exit(self):
        if self.c._is_exiting:
            return

        self.c._is_exiting = True

        try:
            self.c.session_service.new_session()
            self.c.active_stream_states = {}

            if self.c.is_recording:
                sd.stop()
                self.c.is_recording = False

            self.c.record_player.stop()
            self.c.ai_player.stop()
            self.c.window.hide_loading_overlay()

            self.c.record_player.setSource(QUrl())
            self.c.ai_player.setSource(QUrl())
            self.c._close_secondary_windows()

            self.wait_thread(self.c.chat_thread)
            self.wait_thread(self.c.asr_thread)
            self.wait_all_tts_threads()

            self.c.current_record_path = ""
            self.c.current_reply_audio_path = ""
        except Exception:
            pass

        QTimer.singleShot(200, self.finish_exit_cleanup)

    def finish_exit_cleanup(self):
        try:
            self.c.temp_cleanup_service.clear_all_temp()
        except Exception as e:
            print(f"[DesktopAIController] 退出清理失败: {e}")

        try:
            self.c.window.allow_direct_close_once()
            self.c.window.hide()
            self.c.window.close()
        except Exception:
            pass

        QApplication.quit()