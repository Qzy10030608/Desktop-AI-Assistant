from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Any

from PySide6.QtCore import QThread
from PySide6.QtWidgets import QMessageBox

from config import (  
    OLLAMA_HOST,
    OLLAMA_MODEL,
    OLLAMA_CONNECT_TIMEOUT,
    OLLAMA_READ_TIMEOUT,
    OLLAMA_NUM_CTX,
    OLLAMA_NUM_PREDICT,
    OLLAMA_TEMPERATURE,
    OLLAMA_TOP_P,
    MAX_HISTORY_MESSAGES,
    WORKSPACE_RAW_REPLY_FILE,
    WORKSPACE_VISIBLE_REPLY_FILE,
    WORKSPACE_TTS_REPLY_FILE,
)
from services.reply.stream_reply_state import StreamReplyState  # type: ignore
from ui.workers.chat_worker import ChatWorker  # type: ignore


class ChatRuntimeService:
    """
    当前承接：
    - 模型可用性检查
    - llm 参数构建
    - 流式文本轻量清洗
    - reply pipeline 文件写入
    - 启动聊天线程
    - 处理流式片段
    - 处理聊天完成
    - 处理聊天失败
    """

    def __init__(self, controller: Any):
        self.c = controller

    # =========================
    # 基础能力
    # =========================
    def build_llm_request_options(self, current_model: dict) -> dict:
        return {
            "num_ctx": int(current_model.get("num_ctx", OLLAMA_NUM_CTX)),
            "num_predict": int(current_model.get("num_predict", OLLAMA_NUM_PREDICT)),
            "temperature": float(current_model.get("temperature", OLLAMA_TEMPERATURE)),
            "top_p": float(current_model.get("top_p", OLLAMA_TOP_P)),
        }

    def build_llm_timeout(self, current_model: dict):
        connect_timeout = int(current_model.get("connect_timeout", OLLAMA_CONNECT_TIMEOUT))
        read_timeout = int(current_model.get("read_timeout", OLLAMA_READ_TIMEOUT))
        return (connect_timeout, read_timeout)

    def check_chat_model_ready(self) -> tuple[bool, str]:
        current_model = self.c.model_router_service.get_current_chat_model()
        provider = str(current_model.get("provider", "ollama")).strip().lower()
        model_name = str(current_model.get("model_name", "")).strip()
        available = bool(current_model.get("available", False))
        host = str(current_model.get("host", OLLAMA_HOST)).strip() or OLLAMA_HOST

        if provider == "ollama":
            health = self.c.llm_backend_controller.health_check(
                provider="ollama",
                model_config={"host": host},
            )
            if not health.get("ok"):
                return False, f"Ollama 未连接：{health.get('error', '')}"

            if not self.c.model_router_service.has_available_chat_model(provider="ollama"):
                return False, "当前没有可用的 Ollama 模型，请先到连接配置页刷新模型列表。"

            if not available:
                return False, f"当前模型不可用：{model_name or '-'}"

            return True, ""

        if provider == "local":
            return False, "Local provider 还未接入执行器。"

        if provider == "api":
            return False, "API provider 还未接入执行器。"

        return False, f"未知 provider：{provider}"

    def _strip_reasoning_tags(self, text: str) -> str:
        cleaned = (text or "").strip()
        if not cleaned:
            return ""

        cleaned = cleaned.replace("<think>", "").replace("</think>", "")
        cleaned = cleaned.replace("<thinking>", "").replace("</thinking>", "")
        return cleaned.strip()

    def _split_sentences(self, text: str) -> list[str]:
        text = (text or "").replace("\r", "\n").strip()
        if not text:
            return []

        parts = re.split(r"\n+|(?<=[。！？!?])\s*", text)
        return [p.strip() for p in parts if p and p.strip()]

    def _is_followup_sentence(self, text: str) -> bool:
        t = (text or "").strip()
        if not t:
            return True

        followup_patterns = [
            "需要我再解释一下吗",
            "需要我继续吗",
            "还需要我",
            "要我再",
            "要不要我",
            "如果你愿意",
            "需要的话",
            "我可以继续",
            "还想让我",
            "要不要我继续",
            "需要我帮你",
            "要我顺便",
        ]
        return len(t) <= 32 and any(p in t for p in followup_patterns)

    def _build_answer_first_text(
        self,
        text: str,
        *,
        max_sentences: int = 2,
        strip_followup_tail: bool = False,
    ) -> str:
        cleaned = self._strip_reasoning_tags(text)
        if not cleaned:
            return ""

        sentences = self._split_sentences(cleaned)
        if not sentences:
            return cleaned

        useful: list[str] = []

        for s in sentences:
            if strip_followup_tail and self._is_followup_sentence(s):
                if useful:
                    break
                continue

            useful.append(s)
            if len(useful) >= max(1, int(max_sentences)):
                break

        candidate = "\n".join(useful).strip()

        if not candidate:
            candidate = cleaned

        candidate_sentences = self._split_sentences(candidate)
        if (
            strip_followup_tail
            and len(candidate_sentences) > 1
            and self._is_followup_sentence(candidate_sentences[-1])
        ):
            candidate = "\n".join(candidate_sentences[:-1]).strip()

        return candidate.strip()

    def _get_stream_reply_policy(self, request_type: str = "chat") -> dict:
        reply_profile = self.c.model_router_service.get_reply_profile(request_type=request_type)
        policy_profile = reply_profile.get("policy_profile", {})
        return policy_profile if isinstance(policy_profile, dict) else {}

    def build_live_visible_text(self, raw_text: str, reply_policy: dict | None = None) -> str:
        raw = (raw_text or "").strip()
        if not raw:
            return ""

        cleaned = self._strip_reasoning_tags(raw)
        if not cleaned:
            return ""

        extractor = self.c.reply_pipeline_service.extractor_service
        visible = extractor.legacy_cleanup.sanitize_visible_reply(cleaned)
        visible = (visible or "").strip()

        policy = reply_policy if isinstance(reply_policy, dict) else {}
        live_mode = str(policy.get("live_visible_mode", "light_pass")).strip().lower()
        strip_followup_tail = bool(policy.get("strip_followup_tail", False))
        max_visible_sentences = int(policy.get("max_visible_sentences", 2) or 2)

        if live_mode == "strict_answer_first":
            candidate = self._build_answer_first_text(
                visible or cleaned,
                max_sentences=max_visible_sentences,
                strip_followup_tail=strip_followup_tail,
            )
            return candidate or visible or cleaned

        return visible or cleaned
    def write_reply_pipeline_files(self, envelope):
        Path(WORKSPACE_RAW_REPLY_FILE).write_text(envelope.raw_text or "", encoding="utf-8")
        Path(WORKSPACE_VISIBLE_REPLY_FILE).write_text(envelope.final_text or "", encoding="utf-8")
        Path(WORKSPACE_TTS_REPLY_FILE).write_text(
            envelope.tts_text or envelope.final_text or "",
            encoding="utf-8",
        )

    def check_before_send_or_warn(self) -> bool:
        ok, error_text = self.check_chat_model_ready()
        if not ok:
            self.c.window.set_status(error_text)
            QMessageBox.information(self.c.window, "提示", error_text)
            return False
        return True

    def log_llm_request(
        self,
        request_id: int,
        provider: str,
        model_name: str,
        host: str,
        timeout,
        request_options: dict,
        reply_profile: dict,
    ):
        print(
            f"[LLM] request_id={request_id} "
            f"provider={provider} model={model_name} host={host} "
            f"timeout={timeout} options={request_options} "
            f"reply_profile={reply_profile}"
        )

    def build_model_runtime_payload(self, request_type: str = "chat") -> dict:
        current_model = self.c.model_router_service.get_current_chat_model()
        return {
            "current_model": current_model,
            "provider": current_model.get("provider", "ollama"),
            "model_name": current_model.get("model_name", OLLAMA_MODEL),
            "host": current_model.get("host", OLLAMA_HOST),
            "timeout": self.build_llm_timeout(current_model),
            "request_options": self.build_llm_request_options(current_model),
            "reply_profile": self.c.model_router_service.get_reply_profile(
                request_type=request_type
            ),
        }

    # =========================
    # UI / stream 小工具
    # =========================
    def ensure_stream_widget(self, state: StreamReplyState):
        if state.message_widget is not None:
            return state.message_widget

        widget = self.c.window.begin_ai_stream_message(
            mode=state.output_mode,
            initial_text=state.latest_visible_text or "..."
        )
        state.set_widget(widget)
        state.mark_displayed(widget)

        if state.output_mode != "text_only":
            self.c._bind_audio_widget_actions(widget)

            set_streaming = getattr(widget, "set_streaming", None)
            if callable(set_streaming):
                set_streaming()
            else:
                self.c.window.update_ai_stream_status(widget, "回复生成中...")

        return widget

    # =========================
    # 聊天启动
    # =========================
    def start_chat_request(self, text: str, from_voice: bool = False):
        text = text.strip()
        if not text:
            self.c.window.set_status("输入文本为空")
            return

        ok, error_text = self.check_chat_model_ready()
        if not ok:
            self.c.window.set_status(error_text)
            QMessageBox.information(self.c.window, "提示", error_text)
            return

        if self.c.chat_in_progress:
            self.c.window.set_status("当前已有聊天请求正在处理中，请稍候...")
            return

        if self.c.chat_thread is not None and self.c.chat_thread.isRunning():
            self.c.window.set_status("聊天线程仍在运行，请稍候...")
            return

        self.c.chat_in_progress = True
        self.c._set_busy(True)

        if from_voice:
            self.c.window.set_status("语音识别完成，正在请求 AI 回复...")
        else:
            self.c.window.set_status("正在请求 AI 回复...")

        request_id = self.c._new_chat_request_id()
        self.c.request_start_times[request_id] = time.time()

        classify_result = self.c.request_classifier_service.classify(text)

        stream_state = StreamReplyState(
            request_id=request_id,
            user_text=text,
            output_mode=self.c.current_output_mode,
        )
        stream_state.extra["request_type"] = classify_result.request_type
        stream_state.extra["needs_search"] = classify_result.needs_search
        stream_state.extra["needs_control"] = classify_result.needs_control
        self.c.active_stream_states[request_id] = stream_state

        reply_profile = self.c.model_router_service.get_reply_profile(
            request_type=classify_result.request_type
        )
        stream_state.extra["reply_profile"] = reply_profile

        role_meta = self.c.role_service.get_current_role_meta()
        presence_plan = self.c.presence_service.build_presence_plan(
            request_type=classify_result.request_type,
            role_name=role_meta.get("name", ""),
            output_mode=self.c.current_output_mode,
            enabled=reply_profile.get("presence_enabled", True),
        )

        if presence_plan.enabled and presence_plan.text:
            widget = self.c.window.begin_ai_stream_message(
                mode=self.c.current_output_mode,
                initial_text=presence_plan.text,
            )
            stream_state.set_widget(widget)
            stream_state.mark_displayed(widget)
            if self.c.current_output_mode != "text_only":
                self.c._bind_audio_widget_actions(widget)
                set_waiting = getattr(widget, "set_waiting", None)
                if callable(set_waiting):
                    set_waiting()
                else:
                    self.c.window.update_ai_stream_status(widget, "正在思考...")

        current_model = self.c.model_router_service.get_current_chat_model()
        provider = current_model.get("provider", "ollama")
        model_name = current_model.get("model_name", OLLAMA_MODEL)
        host = current_model.get("host", OLLAMA_HOST)
        timeout = self.build_llm_timeout(current_model)
        request_options = self.build_llm_request_options(current_model)

        system_prompt = self.c.prompt_builder_service.build_system_prompt(
            user_text=text,
            prompt_mode=reply_profile.get("prompt_mode", "fast"),
            request_type=classify_result.request_type,
        )

        self.log_llm_request(
            request_id=request_id,
            provider=provider,
            model_name=model_name,
            host=host,
            timeout=timeout,
            request_options=request_options,
            reply_profile=reply_profile,
        )

        self.c.chat_thread = QThread(self.c)
        self.c.chat_worker = ChatWorker(
            request_id=request_id,
            text=text,
            history=list(self.c.chat_history),
            model_config=current_model,
            system_prompt=system_prompt,
            timeout=timeout,
            request_options=request_options,
        )
        self.c.chat_worker.moveToThread(self.c.chat_thread)

        self.c.chat_thread.started.connect(self.c.chat_worker.run)
        self.c.chat_worker.partial.connect(self.c.on_chat_partial)
        self.c.chat_worker.finished.connect(self.c.on_chat_finished)
        self.c.chat_worker.error.connect(self.c.on_chat_error)

        self.c.chat_worker.finished.connect(self.c.chat_thread.quit)
        self.c.chat_worker.error.connect(self.c.chat_thread.quit)

        self.c.chat_worker.finished.connect(self.c.chat_worker.deleteLater)
        self.c.chat_worker.error.connect(self.c.chat_worker.deleteLater)

        self.c.chat_thread.finished.connect(self.c._on_chat_thread_finished)
        self.c.chat_thread.finished.connect(self.c.chat_thread.deleteLater)

        self.c.chat_thread.start()

    # =========================
    # 聊天回调
    # =========================
    def on_chat_partial(self, request_id: int, piece: str, raw_text_so_far: str):
        state = self.c.active_stream_states.get(request_id)
        if state is None:
            return

        now = time.time()
        if state.first_chunk_at is None:
            state.first_chunk_at = now
        state.last_chunk_at = now

        state.raw_buffer = raw_text_so_far or state.raw_buffer

        reply_profile = state.extra.get("reply_profile", {})
        if not isinstance(reply_profile, dict):
            reply_profile = {}

        policy_profile = reply_profile.get("policy_profile", {})
        if not isinstance(policy_profile, dict):
            policy_profile = {}

        visible_text = self.build_live_visible_text(
            state.raw_buffer,
            reply_policy=policy_profile,
        )
        if not visible_text:
            return

        state.update_candidate(visible_text)

        widget = self.ensure_stream_widget(state)

        if state.output_mode == "voice_only":
            self.c.window.update_ai_stream_message(widget, "（仅语音模式）")
        else:
            self.c.window.update_ai_stream_message(widget, visible_text)

        if state.output_mode != "text_only":
            set_streaming = getattr(widget, "set_streaming", None)
            if callable(set_streaming):
                set_streaming()
            else:
                self.c.window.update_ai_stream_status(widget, "回复生成中...")

    def on_chat_finished(self, request_id: int, user_text: str, ai_text: str):
        self.c.chat_in_progress = False
        self.c.window.hide_loading_overlay()

        state = self.c.active_stream_states.get(request_id)
        request_type = "chat"
        reply_profile = {}
        policy_profile = {}

        if state is not None:
            request_type = str(state.extra.get("request_type", "chat")).strip() or "chat"

            reply_profile = state.extra.get("reply_profile", {})
            if not isinstance(reply_profile, dict):
                reply_profile = {}

            policy_profile = reply_profile.get("policy_profile", {})
            if not isinstance(policy_profile, dict):
                policy_profile = {}

        current_model = self.c.model_router_service.get_current_chat_model()
        provider = str(current_model.get("provider", "ollama")).strip().lower() or "ollama"
        model_name = str(current_model.get("model_name", OLLAMA_MODEL)).strip() or OLLAMA_MODEL
        host = str(current_model.get("host", OLLAMA_HOST)).strip() or OLLAMA_HOST
        timeout = self.build_llm_timeout(current_model)
        request_options = self.build_llm_request_options(current_model)

        envelope = self.c.reply_pipeline_service.build_envelope(
            backend=provider,
            model_name=model_name,
            user_text=user_text,
            raw_text=ai_text,
            host=host,
            timeout=timeout,
            request_options=request_options,
            policy_profile=policy_profile,
            request_type=request_type,
        )

        if not getattr(envelope, "final_text", ""):
            envelope.final_text = self.build_live_visible_text(
                ai_text,
                reply_policy=policy_profile,
            ) or "抱歉，当前没有成功提取到最终回复。"

        if not getattr(envelope, "tts_text", ""):
            envelope.tts_text = envelope.final_text or ""

        raw_len = len(ai_text or "")
        print(f"[RAW_REPLY_LEN] chars={raw_len}")
        print(f"[RAW_REPLY_TAIL] {(ai_text or '')[-120:]}")

        self.c.last_reply_package = envelope
        self.write_reply_pipeline_files(envelope)

        if self.c.reply_pipeline_window is not None:
            self.c.reply_pipeline_window.update_reply_package(envelope)

        self.c.chat_history.append({"role": "user", "content": user_text})
        self.c.chat_history.append({"role": "assistant", "content": envelope.final_text})
        self.c._trim_history()
        self.c.temporary_style_service.consume_once()

        self.c._set_busy(False)
        started_at = self.c.request_start_times.pop(request_id, None)
        elapsed_text = ""
        if started_at is not None:
            elapsed = time.time() - started_at
            elapsed_text = f"（耗时 {elapsed:.2f}s）"

        plan = self.c.output_mode_service.build_output_plan(
            mode=self.c.current_output_mode,
            visible_text=envelope.final_text,
            tts_text=envelope.tts_text or envelope.final_text,
            elapsed_text=elapsed_text,
        )

        self.c.window.set_status(plan.status_text)

        state = self.c.active_stream_states.pop(request_id, None)

        if state is not None and state.message_widget is not None:
            self.c.window.update_ai_stream_message(state.message_widget, plan.display_text)

            if plan.need_tts and plan.tts_text:
                tts_task_id = self.c._start_tts_request(plan.tts_text)
                self.c.pending_audio_widgets[tts_task_id] = state.message_widget
                self.c.tts_task_sessions[tts_task_id] = self.c.session_service.current_id

                if hasattr(state.message_widget, "set_tts_generating"):
                    state.message_widget.set_tts_generating()
                else:
                    self.c.window.update_ai_stream_status(state.message_widget, "语音生成中...")
            else:
                self.c.window.finish_ai_stream_message(state.message_widget)
            return

        if plan.append_text_message:
            self.c._append_ai_text_only_message(plan.display_text)
            return

        audio_widget = None
        if plan.append_audio_message:
            audio_widget = self.c._append_ai_audio_message_compat(plan.display_text)
            if audio_widget is not None:
                audio_widget.play_requested.connect(self.c.handle_play_ai_audio_for_path)
                audio_widget.favorite_requested.connect(self.c.handle_favorite_audio_for_path)
                audio_widget.download_requested.connect(self.c.handle_download_audio_for_path)

        if plan.need_tts and plan.tts_text:
            tts_task_id = self.c._start_tts_request(plan.tts_text)
            if audio_widget is not None:
                self.c.pending_audio_widgets[tts_task_id] = audio_widget
            self.c.tts_task_sessions[tts_task_id] = self.c.session_service.current_id

    def on_chat_error(self, request_id: int, msg: str):
        self.c.chat_in_progress = False
        self.c._set_busy(False)
        self.c.window.hide_loading_overlay()

        started_at = self.c.request_start_times.pop(request_id, None)
        self.c.active_stream_states.pop(request_id, None)
        if started_at is not None:
            elapsed = time.time() - started_at
            print(f"[LLM] request_id={request_id} failed in {elapsed:.2f}s: {msg}")

        self.c.window.set_status(f"聊天失败：{msg}")
        QMessageBox.critical(self.c.window, "错误", f"聊天失败：\n{msg}")

    def trim_history(self):
        if len(self.c.chat_history) > MAX_HISTORY_MESSAGES:
            self.c.chat_history = self.c.chat_history[-MAX_HISTORY_MESSAGES:]