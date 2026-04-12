import sys

from PySide6.QtCore import QObject, Qt, Signal, QThread, QTimer
from PySide6.QtWidgets import QApplication
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput

# 导入配置
from config import ( # type: ignore
    APP_TITLE,
    DEFAULT_SPEECH_RATE,
    FAVORITES_FOLDER,
    DOWNLOADS_FOLDER,
    DEFAULT_OUTPUT_MODE,
)

# 导入服务层
from services.persona.prompt_builder_service import PromptBuilderService
from services.persona.role_service import RoleService  
from services.persona.style_profile_service import StyleProfileService  
from services.persona.temporary_style_service import TemporaryStyleService  
from services.persona.voice_profile_service import VoiceProfileService  

from services.model_registry_service import ModelRegistryService  
from services.model_router_service import ModelRouterService

from services.output_mode_service import OutputModeService 

from services.reply.presence_service import PresenceService
from services.reply.request_classifier_service import RequestClassifierService
from services.reply.stream_reply_state import StreamReplyState
from services.reply.reply_engine.pipeline_service import ReplyPipelineService

from services.tts.tts_service import TTSRequest  
from services.tts.tts_package_service import TTSPackageService  
from services.tts.tts_backend_controller_service import TTSBackendControllerService 
from services.favorite_service import FavoriteService
from services.download_service import DownloadService

from services.runtime.app_bootstrap_service import AppBootstrapService 
from services.runtime.chat_runtime_service import ChatRuntimeService  
from services.runtime.audio_runtime_service import AudioRuntimeService  
from services.runtime.ui_bridge_service import UIBridgeService  
from services.runtime.media_library_runtime_service import MediaLibraryRuntimeService  
from services.runtime.app_lifecycle_runtime_service import AppLifecycleRuntimeService  
# 导入页面
from ui.main_window import MainWindow

from ui.control_center.window import ControlCenterWindow 
from ui.reply_pipeline_window import ReplyPipelineWindow 

class StartupTTSPrepareWorker(QObject):
    finished = Signal(dict)
    error = Signal(str)

    def __init__(self, voice_profile_service, tts_backend_controller, tts_package_service):
        super().__init__()
        self.voice_profile_service = voice_profile_service
        self.tts_backend_controller = tts_backend_controller
        self.tts_package_service = tts_package_service

    def run(self):
        try:
            backend = self.voice_profile_service.get_current_tts_backend()

            if backend != "gpt_sovits":
                self.finished.emit({
                    "backend": backend,
                    "healthy": True,
                    "message": "当前语音后端无需后台预连接。",
                })
                return

            package = self.tts_package_service.get_current_package(backend) or {}

            if package:
                preload = self.tts_backend_controller.preload_backend(backend, package)
                self.finished.emit({
                    "backend": backend,
                    "healthy": True,
                    "message": preload.get("status", "GPT-SoVITS 预连接完成"),
                })
                return

            status = self.tts_backend_controller.ensure_backend_ready(backend)
            self.finished.emit({
                "backend": backend,
                "healthy": bool(status.get("healthy", False)),
                "message": status.get("message", "GPT-SoVITS 已就绪"),
            })

        except Exception as e:
            self.error.emit(str(e))
# =========================
# 主控制器
# =========================
class DesktopAIController(QObject):
    """
    桌面版语音 AI 控制器
    """
    def __init__(self):
        super().__init__()
        self.app_bootstrap_service = AppBootstrapService()
        bootstrap_bundle = self.app_bootstrap_service.bootstrap()

        self.machine_profile_service = bootstrap_bundle.machine_profile_service
        self.startup_check_service = bootstrap_bundle.startup_check_service
        self.startup_report = bootstrap_bundle.startup_report
        self.llm_backend_controller = bootstrap_bundle.llm_backend_controller
        self.temp_cleanup_service = bootstrap_bundle.temp_cleanup_service
        self.session_service = bootstrap_bundle.session_service

        self.window = MainWindow()
        self.window.setWindowTitle(APP_TITLE)

        print(f"[StartupCheck] {self.startup_report}")

        if not bool(self.startup_report.get("ollama", {}).get("ok", False)):
            self.window.set_status("Ollama 未连接，请后续在连接设置页检查。")
        
        self.chat_history = []
        self.current_recognized_text = ""
        self.current_record_path = ""
        self.current_reply_audio_path = ""
        self.pending_audio_widgets = {}
        self.tts_task_sessions = {}
        self.tts_task_id = 0
        self.request_start_times = {}

        self.current_speech_rate = DEFAULT_SPEECH_RATE
        self.current_output_mode = DEFAULT_OUTPUT_MODE

        self.is_recording = False
        self.record_start_time = None
        self.record_buffer = None
        self.control_center_window = None
        self._is_exiting = False
        self.startup_tts_thread = None
        self.startup_tts_worker = None
        
        self.reply_pipeline_service = ReplyPipelineService()
        self.reply_pipeline_window = None
        self.last_reply_package = None
        self.presence_service = PresenceService()
        self.request_classifier_service = RequestClassifierService()
        self.active_stream_states: dict[int, StreamReplyState] = {}

        self.favorite_service = FavoriteService(FAVORITES_FOLDER)
        self.download_service = DownloadService(DOWNLOADS_FOLDER)
        self.output_mode_service = OutputModeService()
        # -------------------------
        # 角色引擎相关服务
        # -------------------------
        self.tts_package_service = TTSPackageService()
        self.tts_backend_controller = TTSBackendControllerService()
        self.role_service = RoleService()
        self.style_profile_service = StyleProfileService(self.role_service)
        self.temporary_style_service = TemporaryStyleService()
        self.voice_profile_service = VoiceProfileService(self.role_service)
        self.model_registry_service = ModelRegistryService(
            machine_profile_service=self.machine_profile_service
        )
        self.model_router_service = ModelRouterService(self.model_registry_service)
        self.prompt_builder_service = PromptBuilderService(
            role_service=self.role_service,
            style_service=self.style_profile_service,
            temp_style_service=self.temporary_style_service,
        )
        self.chat_runtime_service = ChatRuntimeService(self)
        self.audio_runtime_service = AudioRuntimeService(self)
        self.ui_bridge_service = UIBridgeService(self)
        self.media_library_runtime_service = MediaLibraryRuntimeService(self)
        self.app_lifecycle_runtime_service = AppLifecycleRuntimeService(self)
        # -------------------------
        # 录音回放播放器
        # -------------------------
        self.record_audio_output = QAudioOutput()
        self.record_player = QMediaPlayer()
        self.record_player.setAudioOutput(self.record_audio_output)
        self.record_player.positionChanged.connect(self.on_record_position_changed)
        self.record_player.durationChanged.connect(self.on_record_duration_changed)
        self.record_player.playbackStateChanged.connect(self.on_record_playback_state_changed)

        # -------------------------
        # AI 回复播放器
        # -------------------------
        self.ai_audio_output = QAudioOutput()
        self.ai_player = QMediaPlayer()
        self.ai_player.setAudioOutput(self.ai_audio_output)
        self.ai_player.setPlaybackRate(self.current_speech_rate)

        # 线程引用
        self.chat_thread = None
        self.chat_worker = None
        self.asr_thread = None
        self.asr_worker = None
        self.tts_threads = {}
        self.tts_workers = {}
        self.chat_request_seq = 0
        self.chat_in_progress = False

        self.bind_signals()
        self.sync_runtime_state_to_main_window()
        QTimer.singleShot(600, self.prepare_tts_backend_after_startup)
    def _on_control_center_destroyed(self):
        self.control_center_window = None

    def _on_reply_pipeline_destroyed(self):
        self.reply_pipeline_window = None
    def _new_tts_task_id(self) -> int:
        self.tts_task_id += 1
        return self.tts_task_id
    def _new_chat_request_id(self) -> int:
        self.chat_request_seq += 1
        return self.chat_request_seq
    def _build_llm_request_options(self, current_model: dict) -> dict:
        return self.chat_runtime_service.build_llm_request_options(current_model)
    def _ensure_stream_widget(self, state: StreamReplyState):
        return self.chat_runtime_service.ensure_stream_widget(state)
    def _build_live_visible_text(self, raw_text: str) -> str:
        return self.chat_runtime_service.build_live_visible_text(raw_text)
    
    def _build_llm_timeout(self, current_model: dict):
        return self.chat_runtime_service.build_llm_timeout(current_model)
    
    def _check_chat_model_ready(self) -> tuple[bool, str]:
        return self.chat_runtime_service.check_chat_model_ready()
    # =========================
    # 信号绑定
    # =========================
    def handle_output_mode_changed(self, mode: str):
        self.ui_bridge_service.handle_output_mode_changed(mode)
    def bind_signals(self):
        self.window.send_text_requested.connect(self.handle_send_text)
        self.window.start_record_requested.connect(self.handle_start_record)
        self.window.stop_record_requested.connect(self.handle_stop_record)
        self.window.output_mode_changed.connect(self.handle_output_mode_changed)

        self.window.refresh_requested.connect(self.handle_refresh)
        self.window.restart_requested.connect(self.handle_restart)
        self.window.exit_requested.connect(self.handle_exit)

        self.window.record_play_requested.connect(self.handle_record_play)
        self.window.record_pause_requested.connect(self.handle_record_pause)
        self.window.record_seek_requested.connect(self.handle_record_seek)
        self.window.record_speed_changed.connect(self.handle_record_speed_changed)

        self.window.open_control_center_requested.connect(self.handle_open_control_center)
        self.window.open_folder_requested.connect(self.handle_open_folder)
        self.window.open_reply_pipeline_requested.connect(self.open_reply_pipeline_window)
        self.window.close_requested.connect(self.handle_exit)

    def _close_secondary_windows(self):
        if self.control_center_window is not None:
            try:
                if hasattr(self.control_center_window, "force_close_once"):
                    self.control_center_window.force_close_once()
                self.control_center_window.close()
            except Exception:
                pass

        if self.reply_pipeline_window is not None:
            try:
                self.reply_pipeline_window.close()
            except Exception:
                pass
    def _ensure_reply_pipeline_window(self):
        if self.reply_pipeline_window is None:
            self.reply_pipeline_window = ReplyPipelineWindow(parent=None)
        return self.reply_pipeline_window
    
    def open_reply_pipeline_window(self):
        win = self._ensure_reply_pipeline_window()
        win.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)

        try:
            win.destroyed.disconnect()
        except Exception:
            pass
        win.destroyed.connect(self._on_reply_pipeline_destroyed)

        if self.last_reply_package is not None:
            win.update_reply_package(self.last_reply_package)

        main_geo = self.window.frameGeometry()
        win.adjustSize()

        x = main_geo.right() + 12
        y = main_geo.top() + 8

        screen = self.window.screen()
        if screen is not None:
            screen_geo = screen.availableGeometry()
            if x + win.width() > screen_geo.right():
                x = max(screen_geo.left(), main_geo.left() - win.width() - 12)
            if y + win.height() > screen_geo.bottom():
                y = max(screen_geo.top(), screen_geo.bottom() - win.height())

        win.move(x, y)
        win.show()
        win.raise_()
        win.activateWindow()

    def _write_reply_pipeline_files(self, envelope):
        self.chat_runtime_service.write_reply_pipeline_files(envelope)
    # =========================
    # 公共小工具
    # =========================
    def sync_runtime_state_to_main_window(self):
        self.ui_bridge_service.sync_runtime_state_to_main_window()
    def _trim_history(self):
        self.chat_runtime_service.trim_history()
    def _set_busy(self, busy: bool):
        """
        控制页面按钮状态，避免重复点击
        """
        self.window.send_text_btn.setEnabled(not busy)
        self.window.start_record_btn.setEnabled(not busy and not self.is_recording)
    #兼容音频控制
    def _append_ai_text_only_message(self, text: str):
        """
        兼容不同版本 MainWindow 的文本消息追加方法
        """
        if hasattr(self.window, "append_ai_text_message"):
            self.window.append_ai_text_message(text) # type: ignore
            return

        if hasattr(self.window, "append_ai_message"):
            self.window.append_ai_message(text)
            return

        if hasattr(self.window, "append_text_message"):
            try:
                self.window.append_text_message("assistant", text) # type: ignore
            except TypeError:
                self.window.append_text_message(text) # type: ignore
            return

        # 最后的兜底：至少不让程序崩
        self.window.set_status(f"AI 回复：{text}")

    def _append_ai_audio_message_compat(self, text: str):
        """
        兼容不同版本 MainWindow 的语音消息追加方法
        返回音频消息控件；如果没有可用接口则返回 None
        """
        if hasattr(self.window, "append_ai_audio_message"):
            return self.window.append_ai_audio_message(text)

        if hasattr(self.window, "append_audio_message"):
            try:
                return self.window.append_audio_message("assistant", text) # type: ignore
            except TypeError:
                return self.window.append_audio_message(text) # type: ignore

        return None
    def _bind_audio_widget_actions(self, widget):
        if widget is None:
            return

        if hasattr(widget, "play_requested"):
            try:
                widget.play_requested.disconnect()
            except Exception:
                pass
            widget.play_requested.connect(self.handle_play_ai_audio_for_path)

        if hasattr(widget, "favorite_requested"):
            try:
                widget.favorite_requested.disconnect()
            except Exception:
                pass
            widget.favorite_requested.connect(self.handle_favorite_audio_for_path)

        if hasattr(widget, "download_requested"):
            try:
                widget.download_requested.disconnect()
            except Exception:
                pass
            widget.download_requested.connect(self.handle_download_audio_for_path)

    def _start_chat_request(self, text: str, from_voice: bool = False):
        self.chat_runtime_service.start_chat_request(text, from_voice=from_voice)

    def _build_tts_request(self, ai_text: str) -> TTSRequest:
        return self.audio_runtime_service.build_tts_request(ai_text)
    
    def _start_tts_request(self, ai_text: str) -> int:
        return self.audio_runtime_service.start_tts_request(ai_text)
    # =========================
    # 文字聊天
    # =========================
    def _on_chat_thread_finished(self):
        self.chat_thread = None
        self.chat_worker = None

    def _on_asr_thread_finished(self):
        self.asr_thread = None
        self.asr_worker = None

    def _on_tts_thread_finished(self, tts_task_id: int):
        self.tts_threads.pop(tts_task_id, None)
        self.tts_workers.pop(tts_task_id, None)
        self.pending_audio_widgets.pop(tts_task_id, None)
        self.tts_task_sessions.pop(tts_task_id, None)

    def _wait_thread(self, thread, timeout: int = 3000):
        self.app_lifecycle_runtime_service.wait_thread(thread, timeout)
    def _wait_all_tts_threads(self, timeout: int = 3000):
        self.app_lifecycle_runtime_service.wait_all_tts_threads(timeout)
    def handle_send_text(self, text: str):
        text = text.strip()
        if not text:
            self.window.set_status("输入文本为空")
            return

        if self.chat_in_progress:
            self.window.set_status("当前已有聊天请求正在处理中，请稍候...")
            return

        if self.chat_thread is not None and self.chat_thread.isRunning():
            self.window.set_status("聊天线程仍在运行，请稍候...")
            return

        if not self.chat_runtime_service.check_before_send_or_warn():
            return

        self.window.append_user_message(text)
        self.window.text_input.clear()
        self.window.set_status("已发送文字给 AI")

        self._start_chat_request(text, from_voice=False)
    def on_chat_finished(self, request_id: int, user_text: str, ai_text: str):
        self.chat_runtime_service.on_chat_finished(request_id, user_text, ai_text)   
    def on_chat_error(self, request_id: int, msg: str):
        self.chat_runtime_service.on_chat_error(request_id, msg)
    # =========================
    # TTS 结果
    # =========================
    def prepare_tts_backend_after_startup(self):
        backend = self.voice_profile_service.get_current_tts_backend()

        if backend != "gpt_sovits":
            if hasattr(self.window, "set_tts_runtime_status"):
                self.window.set_tts_runtime_status("无需连接")
            return

        if self.startup_tts_thread is not None and self.startup_tts_thread.isRunning():
            return

        if hasattr(self.window, "set_tts_runtime_status"):
            self.window.set_tts_runtime_status("连接中")
        self.window.set_status("正在连接 GPT-SoVITS...", temporary=True)

        self.startup_tts_thread = QThread(self)
        self.startup_tts_worker = StartupTTSPrepareWorker(
            voice_profile_service=self.voice_profile_service,
            tts_backend_controller=self.tts_backend_controller,
            tts_package_service=self.tts_package_service,
        )
        self.startup_tts_worker.moveToThread(self.startup_tts_thread)

        self.startup_tts_thread.started.connect(self.startup_tts_worker.run)
        self.startup_tts_worker.finished.connect(self._on_startup_tts_prepare_finished)
        self.startup_tts_worker.error.connect(self._on_startup_tts_prepare_error)

        self.startup_tts_worker.finished.connect(self.startup_tts_thread.quit)
        self.startup_tts_worker.error.connect(self.startup_tts_thread.quit)
        self.startup_tts_worker.finished.connect(self.startup_tts_worker.deleteLater)
        self.startup_tts_worker.error.connect(self.startup_tts_worker.deleteLater)
        self.startup_tts_thread.finished.connect(self._on_startup_tts_thread_finished)
        self.startup_tts_thread.finished.connect(self.startup_tts_thread.deleteLater)

        self.startup_tts_thread.start()

    def _on_startup_tts_prepare_finished(self, result: dict):
        backend = result.get("backend", "")
        healthy = bool(result.get("healthy", False))
        message = result.get("message", "")

        if backend != "gpt_sovits":
            if hasattr(self.window, "set_tts_runtime_status"):
                self.window.set_tts_runtime_status("无需连接")
            return

        if healthy:
            if hasattr(self.window, "set_tts_runtime_status"):
                self.window.set_tts_runtime_status("已连接")
            self.window.set_status(message or "GPT-SoVITS 已连接", temporary=True)
        else:
            if hasattr(self.window, "set_tts_runtime_status"):
                self.window.set_tts_runtime_status("连接失败")
            self.window.set_status(message or "GPT-SoVITS 连接失败", temporary=True)

    def _on_startup_tts_prepare_error(self, message: str):
        if hasattr(self.window, "set_tts_runtime_status"):
            self.window.set_tts_runtime_status("连接失败")
        self.window.set_status(f"GPT-SoVITS 预连接失败：{message}", temporary=True)

    def _on_startup_tts_thread_finished(self):
        self.startup_tts_thread = None
        self.startup_tts_worker = None
    def on_chat_partial(self, request_id: int, piece: str, raw_text_so_far: str):
        self.chat_runtime_service.on_chat_partial(request_id, piece, raw_text_so_far)
    def on_tts_finished(self, tts_task_id: int, reply_path: str):
        self.audio_runtime_service.on_tts_finished(tts_task_id, reply_path)
    def _on_reply_audio_ready(self, tts_task_id: int, reply_path: str):
        self.audio_runtime_service.on_reply_audio_ready(tts_task_id, reply_path)
    def on_tts_error(self, tts_task_id: int, msg: str):
        self.audio_runtime_service.on_tts_error(tts_task_id, msg)
    def _on_reply_audio_error(self, tts_task_id: int, msg: str):
        self.audio_runtime_service.on_reply_audio_error(tts_task_id, msg)
    # =========================
    # 录音
    # =========================
    def handle_start_record(self):
        self.audio_runtime_service.handle_start_record()
    def handle_stop_record(self):
        self.audio_runtime_service.handle_stop_record()
    # =========================
    # ASR 完成后，直接发给 AI
    # =========================
    def on_asr_finished(self, request_id: int, recognized_text: str):
        self.audio_runtime_service.on_asr_finished(request_id, recognized_text)
    def on_asr_error(self, request_id: int, msg: str):
        self.audio_runtime_service.on_asr_error(request_id, msg)
    # =========================
    # 录音回放
    # =========================
    def handle_record_play(self):
        self.audio_runtime_service.handle_record_play()
    def handle_record_pause(self):
        self.audio_runtime_service.handle_record_pause()
    def handle_record_seek(self, progress: float):
        self.audio_runtime_service.handle_record_seek(progress)
    def handle_record_speed_changed(self, speed: float):
        self.audio_runtime_service.handle_record_speed_changed(speed)
    def on_record_position_changed(self, position: int):
        self.audio_runtime_service.on_record_position_changed(position)
    def on_record_duration_changed(self, duration: int):
        self.audio_runtime_service.on_record_duration_changed(duration)
    def on_record_playback_state_changed(self, state):
        self.audio_runtime_service.on_record_playback_state_changed(state)
    # =========================
    # 刷新 / 退出
    # =========================
    def handle_restart(self):
        self.app_lifecycle_runtime_service.handle_restart()
    def handle_refresh(self):
        self.app_lifecycle_runtime_service.handle_refresh()
    def handle_exit(self):
        self.app_lifecycle_runtime_service.handle_exit() 
    def _finish_exit_cleanup(self):
        self.app_lifecycle_runtime_service.finish_exit_cleanup()
    def show(self):
        self.window.show()
    # =========================
    # 收藏 / 下载
    # =========================        
    def handle_download_audio_for_path(self, audio_path: str):
        self.media_library_runtime_service.handle_download_audio_for_path(audio_path)
    def handle_play_ai_audio_for_path(self, audio_path: str):
        self.media_library_runtime_service.handle_play_ai_audio_for_path(audio_path)
    def handle_favorite_audio_for_path(self, audio_path: str):
        self.media_library_runtime_service.handle_favorite_audio_for_path(audio_path)
    # =========================
    # 收藏 / 下载
    # =========================   
    def handle_open_control_center(self):
        if self.control_center_window is None:
            self.control_center_window = ControlCenterWindow(
                parent=None,
                role_service=self.role_service,
                style_service=self.style_profile_service,
                voice_service=self.voice_profile_service,
                model_service=self.model_registry_service,
                tts_package_service=self.tts_package_service,
                tts_backend_controller=self.tts_backend_controller,
                machine_profile_service=self.machine_profile_service,
                startup_check_service=self.startup_check_service,
                llm_backend_controller=self.llm_backend_controller,
            )
            self.control_center_window.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
            self.control_center_window.destroyed.connect(self._on_control_center_destroyed)
            self.control_center_window.settings_applied.connect(self.on_control_center_applied)
            self.control_center_window.current_state_changed.connect(self.on_control_center_state_changed)
            self.control_center_window.open_reply_pipeline_requested.connect(self.open_reply_pipeline_window)

        self.control_center_window.current_output_mode = self.current_output_mode
        self.control_center_window.load_current_state()  # type: ignore

        main_geo = self.window.frameGeometry()
        cc = self.control_center_window

        cc_width = cc.frameGeometry().width()
        cc_height = cc.frameGeometry().height()

        x = main_geo.right() + 12
        y = main_geo.top()

        screen = self.window.screen()
        if screen is not None:
            screen_geo = screen.availableGeometry()
            if x + cc_width > screen_geo.right():
                x = max(screen_geo.left(), screen_geo.right() - cc_width)
            if y + cc_height > screen_geo.bottom():
                y = max(screen_geo.top(), screen_geo.bottom() - cc_height)
        cc.move(x, y)

        if cc.isMinimized():
            cc.showNormal()
        else:
            cc.show()

        cc.raise_()
        cc.activateWindow()
    def handle_open_folder(self, folder_type: str):
        self.media_library_runtime_service.handle_open_folder(folder_type)
    def on_control_center_applied(self):
        self.session_service.new_session()
        self.chat_history = []
        self.sync_runtime_state_to_main_window()

        ok, error_text = self._check_chat_model_ready()
        if ok:
            self.window.set_status("控制中心设置已应用，已切换到新会话")
        else:
            self.window.set_status(f"控制中心设置已应用，但当前聊天不可用：{error_text}")

        QTimer.singleShot(200, self.prepare_tts_backend_after_startup)

    def on_control_center_state_changed(self, state: dict):
        role_name = state.get("role", "-")
        model_name = state.get("model", "-")
        style_name = state.get("style", "-")
        performance_name = state.get("performance", "-")
        package_name = state.get("voice", "-")
        output_mode = state.get("output_mode", DEFAULT_OUTPUT_MODE)
        voice_model_name = state.get("voice_model", "-")

        self.current_output_mode = output_mode
        self.window.set_output_mode(output_mode)

        output_mode_map = {
            "text_only": "仅文字",
            "text_voice": "文字+语音",
            "voice_only": "仅语音",
        }
        output_mode_name = output_mode_map.get(output_mode, "文字+语音")

        summary = (
            f"当前角色：{role_name} | "
            f"语言模型：{model_name} | "
            f"语音后端：{voice_model_name} | "
            f"语音包：{package_name} | "
            f"文本模板：{style_name} | "
            f"表现模板：{performance_name} | "
            f"输出：{output_mode_name}"
        )
        self.window.set_runtime_state_summary(summary)

def main():
    app = QApplication(sys.argv)
    controller = DesktopAIController()
    controller.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()