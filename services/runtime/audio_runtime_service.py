from __future__ import annotations

import os
import time
import uuid
from typing import Any

import numpy as np
import sounddevice as sd
import soundfile as sf
from PySide6.QtCore import QThread, QUrl
from PySide6.QtMultimedia import QMediaPlayer
from PySide6.QtWidgets import QMessageBox

from config import (  # type: ignore
    RECORD_FOLDER,
    REPLY_FOLDER,
    SAMPLE_RATE,
    CHANNELS,
    RECORD_DTYPE,
    MIN_RECORD_SECONDS,
    MAX_RECORD_SECONDS,
    RECORD_EXTENSION,
    TTS_OUTPUT_EXTENSION,
    AUTO_PLAY_AUDIO,
    RECORD_SAVE_SUBTYPE,
    RECORD_NORMALIZE_AUDIO,
    RECORD_NORMALIZE_PEAK,
    RECORD_MIN_PEAK_FOR_NORMALIZE,
)
from services.tts.tts_service import TTSRequest  # type: ignore
from ui.workers.asr_worker import ASRWorker  # type: ignore
from ui.workers.tts_worker import TTSWorker  # type: ignore


class AudioRuntimeService:
    """
    音频运行时服务（第二批）
    -------------------------
    负责：
    - 录音文件路径构造
    - 回复音频路径构造
    - TTSRequest 构造
    - 录音开始/停止
    - ASR 完成/失败
    - 录音回放控制
    - TTS 启动/完成/失败

    第二批改动：
    - 录音消息进入聊天流
    - 页面底部固定录音回放区不再承担主显示职责
    """

    def __init__(self, controller: Any):
        self.c = controller

    # =========================
    # 基础构造
    # =========================
    def build_record_file_path(self) -> str:
        record_filename = f"{uuid.uuid4().hex}{RECORD_EXTENSION}"
        return os.path.join(RECORD_FOLDER, record_filename)

    def build_reply_file_path(self, backend: str) -> str:
        reply_ext = ".wav" if backend == "gpt_sovits" else TTS_OUTPUT_EXTENSION
        reply_filename = f"{uuid.uuid4().hex}{reply_ext}"
        return os.path.join(REPLY_FOLDER, reply_filename)

    def get_record_limits(self) -> dict:
        return {
            "sample_rate": SAMPLE_RATE,
            "channels": CHANNELS,
            "dtype": RECORD_DTYPE,
            "min_seconds": MIN_RECORD_SECONDS,
            "max_seconds": MAX_RECORD_SECONDS,
        }

    def _prepare_record_audio_for_asr(self, audio) -> np.ndarray:
        """
        统一录音数据，提升 Whisper 识别稳定性：
        1. 转 float32
        2. 单声道
        3. 去 NaN / Inf
        4. clip 到 [-1, 1]
        5. 轻量归一化
        """
        arr = np.asarray(audio, dtype=np.float32)

        if arr.ndim == 2:
            # 理论上当前就是 1 声道，这里作为兜底
            arr = arr.mean(axis=1)

        arr = np.squeeze(arr)
        arr = np.nan_to_num(arr, nan=0.0, posinf=0.0, neginf=0.0)
        arr = np.clip(arr, -1.0, 1.0)

        if RECORD_NORMALIZE_AUDIO:
            peak = float(np.max(np.abs(arr))) if arr.size > 0 else 0.0
            if peak >= RECORD_MIN_PEAK_FOR_NORMALIZE:
                arr = arr / peak * float(RECORD_NORMALIZE_PEAK)
                arr = np.clip(arr, -1.0, 1.0)

        return arr.astype(np.float32)
    def build_tts_request(self, ai_text: str) -> TTSRequest:
        backend = self.c.voice_profile_service.get_current_tts_backend()
        reply_path = self.build_reply_file_path(backend)

        current_voice_profile = self.c.voice_profile_service.get_current_voice_profile() or {}
        current_style_profile = self.c.style_profile_service.get_current_style_profile() or {}
        current_voice_name = self.c.voice_profile_service.get_current_tts_voice_name()

        package = self.c.tts_package_service.get_current_package(backend) or {}
        runtime_cfg = self.c.tts_package_service.build_runtime_config(backend, package)

        performance_profile = {
            "rate": current_style_profile.get("rate", 0),
            "volume": current_style_profile.get("volume", 0),
            "pitch": current_style_profile.get("pitch", 0),
            "style_name": current_style_profile.get("name", current_style_profile.get("id", "")),
            "scene": current_voice_profile.get("scene", "daily"),
            "emotion": current_voice_profile.get("emotion", "gentle"),
            "emotion_strength": current_voice_profile.get("emotion_strength", "medium"),
            "speed": current_voice_profile.get("speed", "normal"),
            "pause": current_voice_profile.get("pause", "medium"),
            "intonation": current_voice_profile.get("intonation", "normal"),
            "emphasis": current_voice_profile.get("emphasis", "natural"),
        }

        runtime_voice_profile = {
            **current_voice_profile,
            "ref_audio_path": runtime_cfg.get("ref_audio_path", ""),
            "ref_wav": runtime_cfg.get("ref_audio_path", ""),
            "prompt_text_path": runtime_cfg.get("prompt_text_path", ""),
            "ref_txt": runtime_cfg.get("prompt_text_path", ""),
            "prompt_text": runtime_cfg.get("prompt_text", ""),
            "gpt_sovits_json": runtime_cfg.get("model_config_path", ""),
            "api_url": runtime_cfg.get("api_url", ""),
            "text_lang": runtime_cfg.get("text_lang", ""),
            "prompt_lang": runtime_cfg.get("prompt_lang", ""),
            "gpt_model_path": runtime_cfg.get("gpt_model_path", ""),
            "sovits_model_path": runtime_cfg.get("sovits_model_path", ""),
        }

        extra = {
            "role_id": self.c.role_service.get_current_role_id(),
            "style_id": self.c.style_profile_service.get_current_style_id(),
            "voice_id": self.c.voice_profile_service.get_current_voice_id(),
            "tts_package_id": runtime_cfg.get("package_id", ""),
            "tts_package_name": runtime_cfg.get("package_name", ""),
            "tts_package_path": runtime_cfg.get("package_path", ""),
            "text_lang": runtime_cfg.get("text_lang", ""),
            "prompt_lang": runtime_cfg.get("prompt_lang", ""),
            "api_url": runtime_cfg.get("api_url", ""),
            "model_config_path": runtime_cfg.get("model_config_path", ""),
        }

        request_voice = runtime_cfg.get("voice")
        if not request_voice and backend == "edge":
            request_voice = current_voice_name

        return TTSRequest(
            text=ai_text,
            output_file=reply_path,
            backend=backend,
            voice=request_voice,
            voice_profile=runtime_voice_profile,
            performance_profile=performance_profile,
            extra=extra,
        )

    # =========================
    # TTS 启动与回调
    # =========================
    def start_tts_request(self, ai_text: str) -> int:
        tts_task_id = self.c._new_tts_task_id()
        tts_request = self.build_tts_request(ai_text)

        thread = QThread(self.c)
        worker = TTSWorker(
            tts_task_id=tts_task_id,
            tts_request=tts_request,
        )
        worker.moveToThread(thread)

        thread.started.connect(worker.run)
        worker.finished.connect(self.c.on_tts_finished)
        worker.error.connect(self.c.on_tts_error)

        worker.finished.connect(thread.quit)
        worker.error.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        worker.error.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(lambda task_id=tts_task_id: self.c._on_tts_thread_finished(task_id))

        self.c.tts_threads[tts_task_id] = thread
        self.c.tts_workers[tts_task_id] = worker

        if hasattr(self.c.window, "set_tts_runtime_status"):
            self.c.window.set_tts_runtime_status("已就绪")
        thread.start()
        return tts_task_id

    def on_tts_finished(self, tts_task_id: int, reply_path: str):
        session_id = self.c.tts_task_sessions.get(tts_task_id)
        if session_id != self.c.session_service.current_id:
            return

        self.c.current_reply_audio_path = reply_path
        self.c.ai_player.setSource(QUrl.fromLocalFile(reply_path))
        self.c.ai_player.setPlaybackRate(self.c.current_speech_rate)

        self.on_reply_audio_ready(tts_task_id, reply_path)

        if AUTO_PLAY_AUDIO:
            self.c.ai_player.play()

        if hasattr(self.c.window, "set_tts_runtime_status"):
            self.c.window.set_tts_runtime_status("已连接")

        self.c.window.set_status("AI 语音已生成")

    def on_reply_audio_ready(self, tts_task_id: int, reply_path: str):
        audio_widget = self.c.pending_audio_widgets.get(tts_task_id)
        if audio_widget:
            audio_widget.set_audio_ready(reply_path)

    def on_tts_error(self, tts_task_id: int, msg: str):
        session_id = self.c.tts_task_sessions.get(tts_task_id)
        if session_id != self.c.session_service.current_id:
            return

        self.on_reply_audio_error(tts_task_id, msg)

        if hasattr(self.c.window, "set_tts_runtime_status"):
            self.c.window.set_tts_runtime_status("异常")

        self.c.window.set_status(f"AI 文字已回复，但语音生成失败：{msg}")

    def on_reply_audio_error(self, tts_task_id: int, msg: str):
        audio_widget = self.c.pending_audio_widgets.get(tts_task_id)
        if audio_widget:
            audio_widget.set_audio_error(msg)

    # =========================
    # 录音
    # =========================
    def handle_start_record(self):
        if self.c.is_recording:
            self.c.window.set_status("当前已经在录音中")
            return

        try:
            self.c.window.set_status("正在启动录音...")
            self.c.record_start_time = time.time()

            total_frames = int(MAX_RECORD_SECONDS * SAMPLE_RATE)
            self.c.record_buffer = sd.rec(
                total_frames,
                samplerate=SAMPLE_RATE,
                channels=CHANNELS,
                dtype=RECORD_DTYPE
            )

            self.c.is_recording = True
            self.c.window.set_status("录音中...")

            if hasattr(self.c.window, "set_asr_runtime_status"):
                self.c.window.set_asr_runtime_status("待识别")

            self.c.window.start_record_btn.setEnabled(False)
            self.c.window.stop_record_btn.setEnabled(True)

        except Exception as e:
            self.c.is_recording = False
            self.c.record_start_time = None
            self.c.record_buffer = None
            self.c.window.set_status(f"开始录音失败：{str(e)}")
            QMessageBox.critical(self.c.window, "错误", f"开始录音失败：\n{str(e)}")

    def handle_stop_record(self):
        if not self.c.is_recording:
            self.c.window.set_status("当前没有正在进行的录音")
            return

        try:
            sd.stop()
            start_time = self.c.record_start_time or time.time()
            elapsed = time.time() - start_time
            elapsed = max(0.0, min(elapsed, float(MAX_RECORD_SECONDS)))
            self.c.is_recording = False

            self.c.window.start_record_btn.setEnabled(True)
            self.c.window.stop_record_btn.setEnabled(False)

            if elapsed < MIN_RECORD_SECONDS:
                self.c.window.set_status(f"录音不足 {MIN_RECORD_SECONDS} 秒，请重新录音")
                self.c.current_record_path = ""
                self.c.current_recognized_text = ""
                if hasattr(self.c.window, "set_asr_runtime_status"):
                    self.c.window.set_asr_runtime_status("就绪")
                return

            if self.c.record_buffer is None:
                self.c.window.set_status("录音缓存为空，停止录音失败")
                QMessageBox.critical(self.c.window, "错误", "录音缓存为空，停止录音失败。")
                if hasattr(self.c.window, "set_asr_runtime_status"):
                    self.c.window.set_asr_runtime_status("异常")
                return

            valid_frames = int(elapsed * SAMPLE_RATE)
            valid_audio = self.c.record_buffer[:valid_frames]
            valid_audio = self._prepare_record_audio_for_asr(valid_audio)

            record_path = self.build_record_file_path()
            sf.write(
                record_path,
                valid_audio,
                SAMPLE_RATE,
                subtype=RECORD_SAVE_SUBTYPE,
            )
            self.c.current_record_path = record_path

            # 第二批：录音消息插入聊天流
            record_widget = self.c.window.append_record_message(
                record_path=record_path,
                duration_ms=int(elapsed * 1000),
            )
            if record_widget and hasattr(record_widget, "play_requested"):
                record_widget.play_requested.connect(self.handle_play_record_file)

            self.c.window.set_status("录音完成，正在后台识别语音...")
            if hasattr(self.c.window, "set_asr_runtime_status"):
                self.c.window.set_asr_runtime_status("识别中")

            self.c._set_busy(True)

            request_id = self.c.session_service.current_id

            self.c.asr_thread = QThread(self.c)
            self.c.asr_worker = ASRWorker(request_id=request_id, record_path=record_path)
            self.c.asr_worker.moveToThread(self.c.asr_thread)

            self.c.asr_thread.started.connect(self.c.asr_worker.run)
            self.c.asr_worker.finished.connect(self.c.on_asr_finished)
            self.c.asr_worker.error.connect(self.c.on_asr_error)

            self.c.asr_worker.finished.connect(self.c.asr_thread.quit)
            self.c.asr_worker.error.connect(self.c.asr_thread.quit)
            self.c.asr_worker.finished.connect(self.c.asr_worker.deleteLater)
            self.c.asr_worker.error.connect(self.c.asr_worker.deleteLater)
            self.c.asr_thread.finished.connect(self.c._on_asr_thread_finished)
            self.c.asr_thread.finished.connect(self.c.asr_thread.deleteLater)

            self.c.asr_thread.start()

        except Exception as e:
            self.c.window.set_status(f"停止录音失败：{str(e)}")
            QMessageBox.critical(self.c.window, "错误", f"停止录音失败：\n{str(e)}")

        finally:
            self.c.record_start_time = None
            self.c.record_buffer = None

    def on_asr_finished(self, request_id: int, recognized_text: str):
        if not self.c.session_service.is_current(request_id):
            return

        if hasattr(self.c.window, "set_asr_runtime_status"):
            self.c.window.set_asr_runtime_status("就绪")

        self.c.current_recognized_text = recognized_text.strip()

        if not self.c.current_recognized_text:
            self.c._set_busy(False)
            self.c.window.set_status("未识别到有效语音内容")
            QMessageBox.warning(self.c.window, "提示", "未识别到有效语音内容。")
            return

        self.c.window.set_recognized_text(self.c.current_recognized_text)
        self.c._start_chat_request(self.c.current_recognized_text, from_voice=True)

    def on_asr_error(self, request_id: int, msg: str):
        if not self.c.session_service.is_current(request_id):
            return

        self.c._set_busy(False)

        if hasattr(self.c.window, "set_asr_runtime_status"):
            self.c.window.set_asr_runtime_status("异常")

        self.c.window.set_status(f"语音识别失败：{msg}")
        QMessageBox.critical(self.c.window, "错误", f"语音识别失败：\n{msg}")

    # =========================
    # 录音回放
    # =========================
    def handle_play_record_file(self, record_path: str):
        if not record_path or not os.path.exists(record_path):
            self.c.window.set_status("录音文件不存在，无法播放")
            return

        self.c.current_record_path = record_path
        self.c.record_player.setSource(QUrl.fromLocalFile(record_path))
        self.c.record_player.setPlaybackRate(1.0)
        self.c.record_player.play()
        self.c.window.set_status("正在播放录音")

    def handle_record_play(self):
        if not self.c.current_record_path:
            self.c.window.set_status("当前没有可回放的录音")
            return

        self.c.record_player.play()
        self.c.window.set_status("正在播放录音")

    def handle_record_pause(self):
        self.c.record_player.pause()
        self.c.window.set_status("已暂停录音播放")

    def handle_record_seek(self, progress: float):
        duration = self.c.record_player.duration()
        if duration <= 0:
            return
        position = int(duration * progress)
        self.c.record_player.setPosition(position)

    def handle_record_speed_changed(self, speed: float):
        self.c.record_player.setPlaybackRate(speed)
        self.c.window.set_status(f"录音回放速度已切换为 {speed}x")

    def on_record_position_changed(self, position: int):
        self.c.window.update_record_playback_ui(position)

    def on_record_duration_changed(self, duration: int):
        self.c.window.set_record_duration(duration)

    def on_record_playback_state_changed(self, state):
        if state == QMediaPlayer.PlaybackState.PlayingState:
            self.c.window.set_record_play_state(True)
        else:
            self.c.window.set_record_play_state(False)