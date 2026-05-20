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
from services.reply.reply_engine.envelope import ReplyEnvelope
from services.runtime.interaction import (
    build_interaction_result_from_receipt,
    build_receipt_material,
)
from services.runtime.interaction.language_interaction_center import LanguageInteractionCenter
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
        self.interaction_center = LanguageInteractionCenter(controller)

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
        total_started = time.perf_counter()
        step_started = time.perf_counter()
        current_model = self.c.model_router_service.get_current_chat_model()
        print(f"[ChatPerf] model_ready_get_current_model_ms={(time.perf_counter() - step_started) * 1000.0:.2f}")

        provider = str(current_model.get("provider", "ollama")).strip().lower()
        model_name = str(current_model.get("model_name", "")).strip()
        available = bool(current_model.get("available", False))
        host = str(current_model.get("host", OLLAMA_HOST)).strip() or OLLAMA_HOST

        if provider == "ollama":
            step_started = time.perf_counter()
            health = self.c.llm_backend_controller.health_check(
                provider="ollama",
                model_config={"host": host},
            )
            print(f"[ChatPerf] model_ready_health_check_ms={(time.perf_counter() - step_started) * 1000.0:.2f}")

            if not health.get("ok"):
                print(f"[ChatPerf] model_ready_total_ms={(time.perf_counter() - total_started) * 1000.0:.2f}")
                error_text = str(health.get("error", "") or "")
                return False, self._desktop_text(
                    "chat.model.ollama_not_connected",
                    {"error": error_text},
                    fallback=f"Ollama 未连接：{error_text}",
                )

            step_started = time.perf_counter()
            if not self.c.model_router_service.has_available_chat_model(provider="ollama"):
                print(f"[ChatPerf] model_ready_has_available_ms={(time.perf_counter() - step_started) * 1000.0:.2f}")
                print(f"[ChatPerf] model_ready_total_ms={(time.perf_counter() - total_started) * 1000.0:.2f}")
                return False, self._desktop_text(
                    "chat.model.no_available_ollama_model",
                    fallback="当前没有可用的 Ollama 模型，请先到连接配置页刷新模型列表。",
                )

            print(f"[ChatPerf] model_ready_has_available_ms={(time.perf_counter() - step_started) * 1000.0:.2f}")

            if not available:
                print(f"[ChatPerf] model_ready_total_ms={(time.perf_counter() - total_started) * 1000.0:.2f}")
                return False, self._desktop_text(
                    "chat.model.current_model_unavailable",
                    {"model": model_name or "-"},
                    fallback=f"当前模型不可用：{model_name or '-'}",
                )

            print(f"[ChatPerf] model_ready_total_ms={(time.perf_counter() - total_started) * 1000.0:.2f}")
            return True, ""

        if provider == "local":
            print(f"[ChatPerf] model_ready_total_ms={(time.perf_counter() - total_started) * 1000.0:.2f}")
            return False, self._desktop_text(
                "chat.model.local_provider_not_ready",
                fallback="Local provider 还未接入执行器。",
            )

        if provider == "api":
            print(f"[ChatPerf] model_ready_total_ms={(time.perf_counter() - total_started) * 1000.0:.2f}")
            return False, self._desktop_text(
                "chat.model.api_provider_not_ready",
                fallback="API provider 还未接入执行器。",
            )

        print(f"[ChatPerf] model_ready_total_ms={(time.perf_counter() - total_started) * 1000.0:.2f}")
        return False, self._desktop_text(
            "chat.model.unknown_provider",
            {"provider": provider},
            fallback=f"未知 provider：{provider}",
        )
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
            QMessageBox.information(
                self.c.window,
                self._desktop_text("ui.messagebox.info_title", fallback="提示"),
                error_text,
            )
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
                self.c.window.update_ai_stream_status(
                    widget,
                    self._desktop_text(
                        "chat.stream.generating",
                        fallback="回复生成中...",
                    ),
                )

        return widget

    def _get_desktop_actor_role(self) -> str:
        try:
            role_meta = self.c.role_service.get_current_role_meta()
        except Exception:
            role_meta = {}

        if not isinstance(role_meta, dict):
            return "normal_user"

        haystack = " ".join(
            str(role_meta.get(key, "") or "")
            for key in ("id", "role", "name", "display_name", "code")
        ).lower()
        if any(token in haystack for token in ("developer", "dev", "admin", "开发", "调试")):
            return "developer"
        return "normal_user"

    def _desktop_text(
        self,
        key: str,
        params: dict[str, Any] | None = None,
        *,
        user_text: str = "",
        locale: str = "",
        fallback: str = "",
    ) -> str:
        message_key = str(key or "").strip()
        message_params = params if isinstance(params, dict) else {}
        fallback_text = str(fallback or "").strip()

        if not message_key:
            return fallback_text

        try:
            from services.desktop.language.language_service import DesktopLanguageService

            language_service = DesktopLanguageService()
            if locale:
                profile = language_service.load_profile(locale)
            else:
                profile = language_service.profile_for_text(user_text)

            rendered = str(language_service.render(profile, message_key, message_params) or "").strip()
            return rendered or fallback_text or message_key
        except Exception:
            return fallback_text or message_key

    def _desktop_safe_payload(
        self,
        *,
        status: str,
        message_key: str,
        message_params: dict[str, Any] | None = None,
        user_text: str = "",
        locale: str = "",
        fallback: str = "",
        ok: bool = True,
        executed: bool = False,
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        params = message_params if isinstance(message_params, dict) else {}
        payload = {
            "ok": bool(ok),
            "status": str(status or ""),
            "message_key": str(message_key or ""),
            "message_params": params,
            "safe_user_message": self._desktop_text(
                message_key,
                params,
                user_text=user_text,
                locale=locale,
                fallback=fallback,
            ),
            "executed": bool(executed),
        }

        if isinstance(extra, dict):
            payload.update(extra)

        return payload

    def _jiuchasi_enabled(self) -> bool:
        # 当前开发阶段先打开纠察司接入。
        # 后续可以改成读取 config / ModeStore / 控制中心设置。
        return True

    def _jiuchasi_dry_run_only(self) -> bool:
        # V4 trusted host 执行链测试开关：
        # ready_for_qin 不再被纠察司 dry-run 截断，仍会进入 QinRuntimeService /
        # ReviewGate / 工部适配器链路，不在聊天入口直接执行。
        return False

    def _jiuchasi_allow_llm_thinking(self) -> bool:
        # 允许 LLMTargetHintService 做模糊目标提示。
        # 例如“星露谷”→ 从软件治理区 labels 中提示 Stardew Valley。
        return True

    def _jiuchasi_allow_llm_reply(self) -> bool:
        # 第一轮先关闭 LLM 改写回复，使用语言中心 fallback。
        # 这样测试结果更稳定。
        return False

    # [FallbackOnly]
    # 主路径已迁入 LanguageInteractionCenter，本函数仅作为异常回退保留。
    # 禁止在这里新增业务补丁。新增逻辑应进入 LanguageInteractionCenter 或对应 tianting 服务。
    def _detect_desktop_route(
        self,
        text: str,
        *,
        from_voice: bool,
        classifier_result: Any,
    ) -> dict[str, Any]:
        actor_role = self._get_desktop_actor_role()
        try:
            from services.desktop.tianting.desktop_command_detector import DesktopCommandDetector

            detector = DesktopCommandDetector()
            return detector.detect(
                text,
                input_channel="voice" if from_voice else "text",
                actor_role=actor_role,
                classifier_result=classifier_result,
            )
        except Exception as exc:
            return {
                "schema_version": "desktop_route_decision_v1",
                "raw_user_text": text,
                "input_channel": "voice" if from_voice else "text",
                "actor_role": actor_role,
                "route": "chat_reply",
                "confidence": 0.0,
                "matched_rules": [],
                "action_hint": "",
                "target_hint": {},
                "pending_task_id": "",
                "safe_user_message": "",
                "allow_direct_execution": False,
                "requires_qin_review": True,
                "debug_summary": {"detector_error": str(exc)},
            }

    # [FallbackOnly]
    # 主路径已迁入 LanguageInteractionCenter，本函数仅作为异常回退保留。
    # 禁止在这里新增业务补丁。新增逻辑应进入 LanguageInteractionCenter 或对应 tianting 服务。
    def _maybe_pending_followup_route(
        self,
        text: str,
        desktop_route: dict[str, Any],
        *,
        from_voice: bool,
    ) -> dict[str, Any]:
        route = str((desktop_route or {}).get("route", "") or "")
        if route != "chat_reply":
            return desktop_route
        compact = str(text or "").strip().lower().replace(" ", "")
        try:
            from services.desktop.language.language_service import DesktopLanguageService

            language_service = DesktopLanguageService()
            profile = language_service.profile_for_text(text)
            pending_words: list[str] = []
            for path in ("pending.confirm_words", "pending.cancel_words", "pending.choice_words"):
                pending_words.extend(language_service.list(profile, path))
        except Exception:
            pending_words = []
        normalized_pending_words = {
            str(word or "").strip().lower().replace(" ", "")
            for word in pending_words
            if str(word or "").strip()
        }
        if compact not in normalized_pending_words:
            return desktop_route
        try:
            from services.desktop.tianting.pending_task_service import get_latest_pending_task

            pending = get_latest_pending_task()
        except Exception:
            pending = None
        if not isinstance(pending, dict):
            return desktop_route
        actor_role = str((desktop_route or {}).get("actor_role", "") or "") or self._get_desktop_actor_role()
        next_route = dict(desktop_route or {})
        next_route.update({
            "route": "pending_followup",
            "input_channel": "voice" if from_voice else "text",
            "actor_role": actor_role,
            "confidence": 0.94,
            "matched_rules": [*list(next_route.get("matched_rules", []) or []), "chat_runtime_pending_followup_override"],
            "pending_task_id": str(pending.get("pending_task_id", "") or ""),
            "allow_direct_execution": False,
            "requires_qin_review": True,
        })
        return next_route

    # [FallbackOnly]
    # 主路径已迁入 LanguageInteractionCenter，本函数仅作为异常回退保留。
    # 禁止在这里新增业务补丁。新增逻辑应进入 LanguageInteractionCenter 或对应 tianting 服务。
    def _detect_basic_system_skill_route(self, text: str, *, from_voice: bool) -> dict[str, Any]:
        try:
            from services.desktop.tianting.basic_system_skill_router import detect_basic_system_skill

            system_route = detect_basic_system_skill(
                text,
                input_channel="voice" if from_voice else "text",
            )
        except Exception as exc:
            return {
                "schema_version": "basic_system_skill_route_v1",
                "route": "chat_reply",
                "matched": False,
                "debug_summary": {"system_skill_error": str(exc)},
            }
        if str((system_route or {}).get("route", "") or "") == "system_skill":
            print(
                "[BasicSystemSkill] "
                f"route=system_skill action={str(system_route.get('action', '') or '')} "
                f"locale={str(system_route.get('locale', '') or '')}"
            )
        return system_route if isinstance(system_route, dict) else {"route": "chat_reply", "matched": False}

    def _append_command_observation_card(self, text: str, desktop_route: dict[str, Any], *, from_voice: bool) -> None:
        try:
            from services.desktop.tianting.command_memory_card_service import append_observation_card

            append_observation_card(
                raw_text=text,
                input_channel="voice" if from_voice else "text",
                locale="zh-CN",
                route=str((desktop_route or {}).get("route", "") or ""),
                action_hint=str((desktop_route or {}).get("action_hint", "") or ""),
                confidence=float((desktop_route or {}).get("confidence", 0.0) or 0.0),
                matched_rules=list((desktop_route or {}).get("matched_rules", []) or []),
                target_hint=(desktop_route or {}).get("target_hint", {})
                if isinstance((desktop_route or {}).get("target_hint", {}), dict)
                else {},
            )
        except Exception:
            return

    def _handle_desktop_route(
        self,
        request_id: int,
        text: str,
        desktop_route: dict[str, Any],
        *,
        from_voice: bool,
    ) -> bool:
        route = str((desktop_route or {}).get("route", "") or "").strip()
        if route == "chat_reply":
            return False

        actor_role = str((desktop_route or {}).get("actor_role", "") or "").strip()
        if not actor_role:
            actor_role = self._get_desktop_actor_role()

        try:
            if route == "pending_followup":
                from services.desktop.tianting.result_bridge_service import (
                    resolve_pending_choice_from_user_text,
                    to_safe_chat_message,
                )

                payload = resolve_pending_choice_from_user_text(
                    text,
                    pending_task_id=str((desktop_route or {}).get("pending_task_id", "") or "") or None,
                )
                if str(payload.get("next_step", "") or "") == "submit_selected_candidate_to_qin":
                    resolution_payload = payload
                    original = payload.get("original_task_draft", {}) if isinstance(payload.get("original_task_draft"), dict) else {}
                    if str(original.get("action", "") or "") == "app.launch":
                        payload = self._execute_pending_app_launch_selection_through_qin(payload)
                    else:
                        payload = self._execute_pending_app_close_selection_through_qin(payload)
                    try:
                        payload = self.interaction_center.complete_pending_resolution_memory(
                            project_root=self._project_root(),
                            resolution=resolution_payload,
                            result_payload=payload,
                        )
                    except Exception as exc:
                        print(f"[PendingMemory] text_followup_failed error={exc!r}")
                elif str(payload.get("status", "") or "") == "choice_resolved":
                    payload["message_key"] = "desktop.generic.choice_resolved_need_confirm"
                    payload["message_params"] = {}
                    payload["safe_user_message"] = self._desktop_text(
                        "desktop.generic.choice_resolved_need_confirm",
                        user_text=text,
                        fallback="已选择候选，请再次确认执行。",
                    )
                safe = to_safe_chat_message(payload)
            elif route == "desktop_command":
                from services.desktop.tianting.result_bridge_service import to_safe_chat_message

                print("[DirectRoute] executing desktop_command through QinRuntimeService")
                payload = self._execute_desktop_command_through_qin(
                    text,
                    actor_role=actor_role,
                    input_channel="voice" if from_voice else "text",
                    desktop_route=desktop_route,
                )
                safe = to_safe_chat_message(payload)
                if isinstance(payload, dict) and isinstance(payload.get("ui_prompt"), dict):
                    safe["ui_prompt"] = payload["ui_prompt"]
            elif route == "system_skill":
                from services.desktop.tianting.result_bridge_service import to_safe_chat_message

                payload = self._execute_system_skill_through_qin(
                    text,
                    actor_role=actor_role,
                    input_channel="voice" if from_voice else "text",
                    system_route=desktop_route,
                )
                safe = to_safe_chat_message(payload, locale=str((desktop_route or {}).get("locale", "") or "zh-CN"))
            else:
                from services.desktop.tianting.result_bridge_service import to_safe_chat_message

                safe = to_safe_chat_message(desktop_route)
        except Exception as exc:
            from services.desktop.tianting.result_bridge_service import to_safe_chat_message

            safe = to_safe_chat_message(
                self._desktop_safe_payload(
                    ok=False,
                    status="failed",
                    message_key="desktop.error.parse_failed",
                    user_text=text,
                    fallback="桌面指令解析失败，请重新描述。",
                    extra={
                        "debug_summary": {"error": str(exc), "route": route},
                    },
                )
            )

        self._finish_direct_safe_reply(request_id, text, safe, desktop_route)
        return True

    def _jiuchasi_target_from_task_draft(
        self,
        task_draft: dict[str, Any],
        understanding_packet: dict[str, Any] | None = None,
    ) -> str:
        draft = task_draft if isinstance(task_draft, dict) else {}
        target = draft.get("target", {}) if isinstance(draft.get("target"), dict) else {}
        action = str(draft.get("action", "") or "").strip()

        # 文件 / 文件夹动作：优先使用编译后的 path_hint。
        # 例如 “请打开G盘根目录” 应该传给 Jiuchasi 的是 G:\，
        # 而不是 normalization 后的 “G盘根目录 / G盘 夹”。
        if action.startswith("folder.") or action.startswith("file."):
            path_hint = str(target.get("path_hint", "") or "").strip()
            name_hint = str(target.get("name_hint", "") or "").strip()
            identity = str(target.get("identity", "") or "").strip()

            # 纯盘符根目录：打开E盘 / 打开G盘根目录
            if path_hint and not name_hint:
                print(
                    "[JiuchasiTarget] "
                    f"action={action!r} target_normalized={path_hint!r} source='task_path_hint'"
                )
                return path_hint

            # name_hint 只是“E盘/G盘”时，也可以走根目录
            if path_hint and name_hint:
                compact_name = name_hint.replace(" ", "").replace("　", "")
                compact_path = path_hint.replace("\\", "").replace(":", "").casefold()
                if compact_name.casefold() in {
                    f"{compact_path}盘",
                    f"{compact_path}盘根目录",
                    f"{compact_path}根目录",
                }:
                    print(
                        "[JiuchasiTarget] "
                        f"action={action!r} target_normalized={path_hint!r} source='task_path_hint'"
                    )
                    return path_hint

            # 具体文件夹 / 文件名：优先传 name_hint，让 EvidenceBroker 去查候选
            if name_hint:
                print(
                    "[JiuchasiTarget] "
                    f"action={action!r} target_normalized={name_hint!r} source='task_name_hint'"
                )
                return name_hint

            if identity:
                print(
                    "[JiuchasiTarget] "
                    f"action={action!r} target_normalized={identity!r} source='task_identity'"
                )
                return identity

            if path_hint:
                print(
                    "[JiuchasiTarget] "
                    f"action={action!r} target_normalized={path_hint!r} source='task_path_hint_fallback'"
                )
                return path_hint

        understanding = understanding_packet if isinstance(understanding_packet, dict) else {}
        target_from_understanding = str(understanding.get("target_normalized", "") or "").strip()

        # desktop.resolve 是“待判断目标类型”，这里必须优先使用 puzzle/compiler 清洗后的 target。
        # 否则会把“你真棒，那么可以帮我打开英雄联盟吗”这种整句脏文本传给 Jiuchasi。
        if action == "desktop.resolve":
            for key in ("app_hint", "name_hint", "path_hint", "identity"):
                value = str(target.get(key, "") or "").strip()
                if value:
                    print(
                        "[JiuchasiTarget] "
                        f"action={action!r} target_normalized={value!r} source='task_{key}'"
                    )
                    return value

            if target_from_understanding:
                print(
                    "[JiuchasiTarget] "
                    f"action={action!r} target_normalized={target_from_understanding!r} "
                    "source='understanding_packet_fallback'"
                )
                return target_from_understanding

        if action.startswith("app."):
            # app 动作可以继续优先使用 understanding，因为“打开steam / 请打开微信”这类通常更干净。
            if target_from_understanding:
                print(
                    "[JiuchasiTarget] "
                    f"action={action!r} target_normalized={target_from_understanding!r} "
                    "source='understanding_packet'"
                )
                return target_from_understanding

            for key in ("app_hint", "name_hint", "identity"):
                value = str(target.get(key, "") or "").strip()
                if value:
                    print(
                        "[JiuchasiTarget] "
                        f"action={action!r} target_normalized={value!r} source='task_{key}'"
                    )
                    return value

        for key in ("app_hint", "name_hint", "path_hint", "identity"):
            value = str(target.get(key, "") or "").strip()
            if value:
                print(
                    "[JiuchasiTarget] "
                    f"action={action!r} target_normalized={value!r} source='task_{key}'"
                )
                return value

        if target_from_understanding:
            print(
                "[JiuchasiTarget] "
                f"action={action!r} target_normalized={target_from_understanding!r} "
                "source='understanding_packet_fallback'"
            )
            return target_from_understanding

        print(f"[JiuchasiTarget] action={action!r} target_normalized='' source='missing'")
        return ""

    def _execute_desktop_command_through_qin(
        self,
        text: str,
        *,
        actor_role: str,
        input_channel: str,
        desktop_route: dict[str, Any],
    ) -> dict[str, Any]:
        started = time.perf_counter()
        try:
            from services.desktop.tianting.llm_command_bridge_service import build_puzzle_from_user_text
            from services.desktop.qin.zhongshu.desktop_task_compiler import compile_desktop_task_draft

            action_hint = str((desktop_route or {}).get("action_hint", "") or "").strip()
            bridge_result = build_puzzle_from_user_text(
                text,
                llm_hint={"selected_action_hint": action_hint} if action_hint else None,
                actor_role=actor_role,
                input_channel=input_channel,
            )
            puzzle = bridge_result.get("puzzle", {}) if isinstance(bridge_result, dict) else {}

            understanding_packet = (
                bridge_result.get("understanding_packet", {})
                if isinstance(bridge_result, dict) and isinstance(bridge_result.get("understanding_packet"), dict)
                else puzzle.get("understanding_packet", {})
                if isinstance(puzzle, dict) and isinstance(puzzle.get("understanding_packet"), dict)
                else {}
            )

            if understanding_packet:
                decision = understanding_packet.get("decision", {}) if isinstance(understanding_packet.get("decision"), dict) else {}
                print(
                    "[DirectRouteUnderstanding] "
                    f"target={understanding_packet.get('target_normalized', '')!r} "
                    f"decision={decision.get('status', '')!r} "
                    f"need_llm={decision.get('need_llm_hint', False)} "
                    f"reason={decision.get('reason', '')!r}"
                )
            else:
                print("[DirectRouteUnderstanding] missing_understanding_packet")

            if not self._jiuchasi_enabled():
                puzzle = self._maybe_apply_llm_target_hint(
                    puzzle,
                    raw_user_text=text,
                    action_hint=action_hint,
                )
            else:
                print("[JiuchasiBridge] skip legacy _maybe_apply_llm_target_hint")

            task_draft = compile_desktop_task_draft(puzzle)

            jiuchasi_payload = self._maybe_route_through_jiuchasi(
                text=text,
                actor_role=actor_role,
                input_channel=input_channel,
                desktop_route=desktop_route,
                puzzle=puzzle,
                task_draft=task_draft,
                understanding_packet=understanding_packet,
            )

            if isinstance(jiuchasi_payload, dict):
                if not bool(jiuchasi_payload.get("__continue_to_qin__", False)):
                    return jiuchasi_payload

                qin_patch = (
                    jiuchasi_payload.get("qin_task_patch", {})
                    if isinstance(jiuchasi_payload.get("qin_task_patch"), dict)
                    else {}
                )
                session_id = str(
                    (
                        jiuchasi_payload.get("jiuchasi_result", {})
                        if isinstance(jiuchasi_payload.get("jiuchasi_result"), dict)
                        else {}
                    ).get("session_id", "")
                    or ""
                )
                task_draft = self._apply_jiuchasi_qin_task_patch(
                    task_draft,
                    qin_patch,
                    jiuchasi_session_id=session_id,
                )

            mode_allowed, blocked = self._desktop_real_execution_allowed()
            if not mode_allowed:
                return blocked

            task = self._qin_task_from_draft(task_draft)
            result = self._qin_runtime().execute_desktop_task(task)
            action = str(task.get("action", "") or "")
            self._log_qin_exec_result(action, result, task=task)
            return self._safe_qin_payload(result, task=task)

        except Exception as exc:
            return self._desktop_execution_fallback(
                text,
                actor_role=actor_role,
                input_channel=input_channel,
                error=str(exc),
            )
        finally:
    
            print(f"[ChatPerf] direct_route_total_ms={(time.perf_counter() - started) * 1000.0:.2f}")
  
    def _execute_system_skill_through_qin(
        self,
        text: str,
        *,
        actor_role: str,
        input_channel: str,
        system_route: dict[str, Any],
    ) -> dict[str, Any]:
        action = str((system_route or {}).get("action", "") or "").strip()
        arguments = (
            dict(system_route.get("arguments", {}))
            if isinstance(system_route.get("arguments"), dict)
            else {}
        )
        arguments.update({
            "actor_role": actor_role,
            "input_channel": input_channel,
            "source": "basic_system_skill_router",
            "locale": str(system_route.get("locale", arguments.get("locale", "zh-CN")) or "zh-CN"),
        })
        task = {
            "action": action,
            "target_name": "系统信息",
            "target_type": "system_skill",
            "target_id": action,
            "arguments": arguments,
            "source": "chat_runtime_basic_system_skill",
            "task_id": f"system_skill_{int(time.time() * 1000)}",
        }
        result = self._qin_runtime().execute_desktop_task(task)
        status = str(result.get("status", result.get("data", {}).get("status", "")) or "")
        print(f"[SystemSkillExec] action={action} result={bool(result.get('ok', False))} status={status}")
        return self._safe_qin_payload(result, task=task)

    def _maybe_apply_llm_target_hint(
        self,
        puzzle: dict[str, Any],
        *,
        raw_user_text: str,
        action_hint: str,
    ) -> dict[str, Any]:
        payload = dict(puzzle or {})
        understanding = (
            payload.get("understanding_packet", {})
            if isinstance(payload.get("understanding_packet"), dict)
            else {}
        )
        decision = (
            understanding.get("decision", {})
            if isinstance(understanding.get("decision"), dict)
            else {}
        )
        if not understanding or not bool(decision.get("need_llm_hint", False)):
            return payload
        normalized_action = str(action_hint or payload.get("selected_action_hint", "") or "").strip()
        if not normalized_action.startswith("app."):
            print(f"[LLMTargetHint] skipped action={normalized_action!r} reason=non_app_action")
            return payload

        try:
            from services.desktop.tianting.llm_target_hint_service import LLMTargetHintService

            hint = LLMTargetHintService(project_root=self._project_root()).build_hint(
                raw_user_text=raw_user_text,
                action_hint=normalized_action,
                target_normalized=str(understanding.get("target_normalized", "") or ""),
                understanding_packet=understanding,
            )
        except Exception as exc:
            hint = {
                "schema_version": "llm_target_hint_v1",
                "ok": False,
                "trusted": False,
                "target_label_hint": "",
                "requires_confirmation": True,
                "allow_direct_execution": False,
                "reason": f"llm_target_hint_exception:{exc}",
            }

        evidence = understanding.get("evidence", {}) if isinstance(understanding.get("evidence"), dict) else {}
        evidence = dict(evidence)
        evidence["llm_hint"] = hint
        understanding = dict(understanding)
        understanding["evidence"] = evidence
        payload["understanding_packet"] = understanding
        label = str(hint.get("target_label_hint", "") or "") if isinstance(hint, dict) else ""
        print(
            "[LLMTargetHint] "
            f"ok={bool((hint or {}).get('ok', False))} "
            f"target_label_hint={label!r} "
            f"requires_confirmation={bool((hint or {}).get('requires_confirmation', True))} "
            f"reason={str((hint or {}).get('reason', '') or '')!r}"
        )
        return payload

    def _execute_pending_app_close_selection_through_qin(self, resolution: dict[str, Any]) -> dict[str, Any]:
        started = time.perf_counter()
        try:
            mode_allowed, blocked = self._desktop_real_execution_allowed()
            if not mode_allowed:
                return blocked

            task_draft = (
                resolution.get("original_task_draft", {})
                if isinstance(resolution.get("original_task_draft"), dict)
                else {}
            )
            selected_candidate = (
                resolution.get("selected_candidate", {})
                if isinstance(resolution.get("selected_candidate"), dict)
                else {}
            )
            if str(task_draft.get("action", "") or "") != "app.close" or not selected_candidate:
                return self._desktop_safe_payload(
                    ok=False,
                    status="choice_resolved",
                    message_key="desktop.generic.choice_resolved_need_confirm",
                    user_text=str(resolution.get("original_user_text", "") or ""),
                    fallback="已选择候选，请再次确认执行。",
                    executed=False,
                )

            task = self._qin_task_from_draft(task_draft)
            arguments = task.get("arguments", {}) if isinstance(task.get("arguments"), dict) else {}
            arguments = dict(arguments)
            arguments["app_close_selected_candidate"] = selected_candidate
            arguments["selected_candidate"] = selected_candidate
            task["arguments"] = arguments

            result = self._qin_runtime().execute_desktop_task(task)
            self._log_qin_exec_result("app.close", result, task=task)
            return self._safe_qin_payload(result, task=task)
        except Exception as exc:
            return self._desktop_safe_payload(
                ok=False,
                status="failed",
                message_key="desktop.qin.pending_submit_failed",
                message_params={"error": str(exc)},
                fallback=f"候选已选择，但提交秦链失败：{exc}",
                executed=False,
                extra={"error": str(exc)},
            )
        finally:
            print(f"[ChatPerf] direct_route_total_ms={(time.perf_counter() - started) * 1000.0:.2f}")

    def _execute_pending_app_launch_selection_through_qin(self, resolution: dict[str, Any]) -> dict[str, Any]:
        started = time.perf_counter()
        try:
            mode_allowed, blocked = self._desktop_real_execution_allowed()
            if not mode_allowed:
                return blocked

            task_draft = (
                resolution.get("original_task_draft", {})
                if isinstance(resolution.get("original_task_draft"), dict)
                else {}
            )
            selected_candidate = (
                resolution.get("selected_candidate", {})
                if isinstance(resolution.get("selected_candidate"), dict)
                else {}
            )
            if str(task_draft.get("action", "") or "") != "app.launch" or not selected_candidate:
                return {
                    "ok": False,
                    "status": "choice_resolved",
                    "message_key": "desktop.app.launch.need_confirmation",
                    "message_params": {"target": str(selected_candidate.get("label", "") or "")},
                    "executed": False,
                }

            task = self._qin_task_from_draft(task_draft)
            arguments = task.get("arguments", {}) if isinstance(task.get("arguments"), dict) else {}
            arguments = dict(arguments)
            arguments["app_launch_selected_candidate"] = selected_candidate
            arguments["selected_candidate"] = selected_candidate
            arguments["confirmed_from_pending"] = True
            arguments["pending_task_id"] = str(resolution.get("pending_task_id", "") or "")
            task["arguments"] = arguments

            result = self._qin_runtime().execute_desktop_task(task)
            self._log_qin_exec_result("app.launch", result, task=task)
            return self._safe_qin_payload(result, task=task)
        except Exception as exc:
            return {
                "ok": False,
                "status": "failed",
                "message_key": "desktop.app.launch.failed",
                "message_params": {"target": ""},
                "executed": False,
                "error": str(exc),
            }
        finally:
            print(f"[ChatPerf] direct_route_total_ms={(time.perf_counter() - started) * 1000.0:.2f}")

    def handle_pending_ui_action(self, event: dict[str, Any]) -> dict[str, Any]:
        try:
            return self.interaction_center.handle_pending_ui_action(
                event,
                project_root=self._project_root(),
                selected_candidate_fn=self._pending_ui_selected_candidate,
                execute_app_close_fn=self._execute_pending_app_close_selection_through_qin,
                execute_app_launch_fn=self._execute_pending_app_launch_selection_through_qin,
                desktop_safe_payload_fn=self._desktop_safe_payload,
            )
        except Exception as exc:
            print(f"[PendingUI] interaction_center_failed error={exc!r}")

        # [FallbackOnly]
        # 主路径已迁入 LanguageInteractionCenter，本段仅作为异常回退保留。
        # 禁止在这里新增业务补丁。新增逻辑应进入 LanguageInteractionCenter 或对应 tianting 服务。
        payload = event if isinstance(event, dict) else {}
        print(f"[PendingUI] event={payload!r}")
        pending_task_id = str(payload.get("pending_task_id", "") or "").strip()
        action = str(payload.get("action", "") or "").strip()
        if not pending_task_id:
            return self._desktop_safe_payload(
                ok=False,
                status="failed",
                message_key="desktop.exec.failed_generic",
                fallback="桌面操作未能完成。",
                executed=False,
            )

        try:
            from services.desktop.tianting.pending_task_service import PendingTaskService

            pending_service = PendingTaskService(self._project_root())
            pending = pending_service.get_pending_task(pending_task_id)
            if not isinstance(pending, dict):
                return self._desktop_safe_payload(
                    ok=False,
                    status="failed",
                    message_key="desktop.exec.failed_generic",
                    message_params={"target": ""},
                    fallback="桌面操作未能完成。",
                    executed=False,
                )

            choice_type = str(pending.get("choice_type", "") or "")
            print(f"[PendingUI] choice_type={choice_type!r}")

            if action == "cancel":
                pending_service.cancel_pending_task(pending_task_id)
                return self._desktop_safe_payload(
                    ok=True,
                    status="choice_cancelled",
                    message_key="desktop.exec.cancelled",
                    fallback="已取消本次操作。",
                    executed=False,
                    extra={"pending_task_id": pending_task_id, "cancelled": True},
                )

            if action not in {"confirm", "select_candidate"}:
                return self._desktop_safe_payload(
                    ok=False,
                    status="failed",
                    message_key="desktop.exec.failed_generic",
                    fallback="桌面操作未能完成。",
                    executed=False,
                )

            selected_candidate = self._pending_ui_selected_candidate(pending, payload)
            if not selected_candidate:
                return self._desktop_safe_payload(
                    ok=False,
                    status="choice_invalid",
                    message_key="desktop.generic.choice_invalid",
                    fallback="选择无效，请重新选择。",
                    executed=False,
                    extra={"pending_task_id": pending_task_id},
                )

            pending_service.complete_pending_task(pending_task_id, selected_candidate)
            resolution = {
                "ok": True,
                "status": "choice_resolved",
                "pending_task_id": pending_task_id,
                "selected_candidate": selected_candidate,
                "original_task_draft": pending.get("original_task_draft", {})
                if isinstance(pending.get("original_task_draft"), dict)
                else {},
                "original_user_text": str(pending.get("original_user_text", "") or ""),
                "choice_type": choice_type,
                "executed": False,
                "allow_direct_execution": False,
            }

            if choice_type == "app_close_candidate":
                print("[PendingUI] executing app_close via Qin ...")
                result = self._execute_pending_app_close_selection_through_qin(resolution)
            elif choice_type in {"app_launch_candidate", "app_launch_confirmation"}:
                print("[PendingUI] executing app_launch via Qin ...")
                result = self._execute_pending_app_launch_selection_through_qin(resolution)
            else:
                result = self._desktop_safe_payload(
                    ok=False,
                    status="failed",
                    message_key="desktop.exec.failed_generic",
                    fallback="桌面操作未能完成。",
                    executed=False,
                    extra={"pending_task_id": pending_task_id, "choice_type": choice_type},
                )

            result_payload = result if isinstance(result, dict) else {}
            result_data = result_payload.get("data", {}) if isinstance(result_payload.get("data"), dict) else {}
            print(
                "[PendingUI] result "
                f"ok={bool(result_payload.get('ok', False))!r} "
                f"executed={bool(result_payload.get('executed', result_data.get('executed', False)))!r} "
                f"status={str(result_payload.get('status', result_data.get('status', '')) or '')!r}"
            )
            result_payload["pending_task_id"] = pending_task_id
            return result_payload
        except Exception as exc:
            print(f"[PendingUI] failed error={exc!r}")
            return self._desktop_safe_payload(
                ok=False,
                status="failed",
                message_key="desktop.exec.failed_generic",
                message_params={"target": ""},
                fallback=f"桌面操作未能完成：{exc}",
                executed=False,
                extra={"error": str(exc), "pending_task_id": pending_task_id},
            )

    def _pending_ui_selected_candidate(self, pending: dict[str, Any], event: dict[str, Any]) -> dict[str, Any]:
        action = str(event.get("action", "") or "").strip()
        candidates = pending.get("candidates", []) if isinstance(pending.get("candidates"), list) else []
        selected = pending.get("selected_candidate", {}) if isinstance(pending.get("selected_candidate"), dict) else {}
        if action == "confirm":
            if selected:
                return selected
            if len(candidates) == 1 and isinstance(candidates[0], dict):
                return candidates[0]

        candidate_id = str(event.get("candidate_id", "") or "").strip()
        display_index = str(event.get("display_index", "") or "").strip()
        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue
            if candidate_id and str(candidate.get("candidate_id", "") or "").strip() == candidate_id:
                return candidate
            if display_index and str(candidate.get("display_index", "") or "").strip() == display_index:
                return candidate
        return selected if action == "select_candidate" and selected else {}

    def _desktop_real_execution_allowed(self) -> tuple[bool, dict[str, Any]]:
        try:
            from services.desktop.tiandi.mode_store import ModeStore

            state = ModeStore(self._project_root()).get_runtime_state()
        except Exception as exc:
            return False, self._desktop_safe_payload(
                ok=False,
                status="desktop_mode_unavailable",
                message_key="desktop.connection.mode_unavailable",
                message_params={"error": str(exc)},
                fallback=f"无法读取桌面连接状态，已阻止真实桌面动作：{exc}",
                executed=False,
            )

        mode = str(state.get("desktop_mode", state.get("current_mode", "disabled")) or "disabled").strip().lower()
        host_enabled = bool(state.get("host_execution_enabled", False))
        if mode == "disabled":
            return False, self._desktop_safe_payload(
                ok=True,
                status="desktop_connection_disabled",
                message_key="desktop.connection.not_enabled_test_only",
                fallback="桌面连接尚未开启，当前只生成测试结果。",
                executed=False,
            )
        if mode != "trusted" or not host_enabled:
            return False, self._desktop_safe_payload(
                ok=True,
                status="desktop_not_execution_mode",
                message_key="desktop.connection.not_execution_mode",
                fallback="当前不是执行模式，已阻止真实桌面动作。",
                executed=False,
            )
        return True, {}

    def _qin_task_from_draft(self, task_draft: dict[str, Any]) -> dict[str, Any]:
        draft = task_draft if isinstance(task_draft, dict) else {}
        target = draft.get("target", {}) if isinstance(draft.get("target"), dict) else {}
        arguments = draft.get("arguments", {}) if isinstance(draft.get("arguments"), dict) else {}
        arguments = dict(arguments)
        arguments.pop("draft_only", None)
        arguments.pop("do_not_execute", None)

        target_name = (
            str(target.get("name_hint", "") or "")
            or str(target.get("app_hint", "") or "")
            or str(target.get("path_hint", "") or "")
        ).strip()
        target_type = str(target.get("kind", "") or "").strip()
        target_path = str(target.get("path_hint", "") or "").strip()

        if target_name:
            arguments.setdefault("target_name", target_name)
        if target_type:
            arguments.setdefault("target_type", target_type)
        if target_path:
            arguments.setdefault("target_path", target_path)
            arguments.setdefault("path_hint", target_path)

        task = {
            "action": str(draft.get("action", "") or "").strip(),
            "target": target,
            "target_path": target_path,
            "target_name": target_name,
            "target_type": target_type,
            "target_id": str(target.get("identity", "") or target_name or target_path),
            "arguments": arguments,
            "source": "chat_runtime_tianting_puzzle",
            "task_id": str(draft.get("task_id", "") or ""),
        }
        root_id = str(draft.get("root_id", arguments.get("root_id", "")) or "").strip()
        if root_id:
            task["root_id"] = root_id
        if "request_allowed" in draft:
            task["request_allowed"] = bool(draft.get("request_allowed", False))
        return task

    def _file_permission_bridge_for_open(self, target_path: str) -> dict[str, Any]:
        path_text = str(target_path or "").strip()
        disk_id = self._drive_key_for_path(path_text)
        root_id = self._drive_root_id_for_path(path_text)
        if not path_text or not disk_id:
            print(
                "[FilePermissionBridge] permission_missing "
                f"target={path_text!r} root_id={root_id!r}"
            )
            return {}

        try:
            from services.desktop.desktop_whitelist_service import DesktopWhitelistService
            from services.desktop.tiandi.mode_store import ModeStore

            mode = ModeStore(self._project_root()).get_mode_state().current_mode
            service = DesktopWhitelistService(self._project_root())
            disk_rows = service.build_disk_rows(str(mode or "trusted"))
            disk_row = next(
                (
                    item for item in disk_rows
                    if str(item.get("disk_id", "") or "").strip().upper() == disk_id
                ),
                None,
            )
            is_drive_root = self._is_drive_root_path(path_text)
            if disk_row and is_drive_root:
                permission = self._normalize_file_permission(disk_row.get("permission_state", "unset"))
                return {
                    "root_id": root_id,
                    "permission_state": permission,
                    "effective_permission_state": permission,
                    "permission_source_type": "disk",
                    "permission_source_key": str(disk_row.get("disk_id", disk_id) or disk_id).strip(),
                    "file_actions_enabled": bool(disk_row.get("file_actions_enabled", False)),
                }

            file_state = service.get_file_governance_state(
                mode=str(mode or "trusted"),
                editable=False,
                selected_disk=disk_id,
                current_path=path_text,
                object_view_mode="roots",
            )
            rows = file_state.get("rows", []) if isinstance(file_state.get("rows", []), list) else []
            normalized_target = Path(path_text).expanduser().resolve(strict=False)
            matched: dict[str, Any] = {}
            matched_depth = -1
            for row in rows:
                if not isinstance(row, dict):
                    continue
                row_path_text = str(row.get("target_path", row.get("path", "")) or "").strip()
                if not row_path_text:
                    continue
                try:
                    row_path = Path(row_path_text).expanduser().resolve(strict=False)
                    normalized_target.relative_to(row_path)
                except Exception:
                    continue
                depth = len(row_path.parts)
                if depth > matched_depth:
                    matched = row
                    matched_depth = depth

            if matched:
                permission = self._normalize_file_permission(
                    matched.get("effective_permission_state", matched.get("permission_state", "unset"))
                )
                source_type = str(matched.get("permission_source_type", "root") or "root").strip().lower()
                source_key = str(matched.get("permission_source_key", matched.get("root_id", "")) or "").strip()
                return {
                    "root_id": str(matched.get("root_id", root_id) or root_id).strip(),
                    "permission_state": permission,
                    "effective_permission_state": permission,
                    "permission_source_type": source_type,
                    "permission_source_key": source_key,
                    "file_actions_enabled": bool(file_state.get("file_actions_enabled", False)),
                }
        except Exception as exc:
            print(
                "[FilePermissionBridge] permission_missing "
                f"target={path_text!r} root_id={root_id!r} error={exc!r}"
            )
            return {}

        print(
            "[FilePermissionBridge] permission_missing "
            f"target={path_text!r} root_id={root_id!r}"
        )
        return {}

    def _drive_key_for_path(self, target_path: str) -> str:
        text = str(target_path or "").strip()
        match = re.match(r"^([A-Za-z]):", text)
        return f"{match.group(1).upper()}:" if match else ""

    def _drive_root_id_for_path(self, target_path: str) -> str:
        disk_id = self._drive_key_for_path(target_path)
        if not disk_id:
            return ""
        return f"{disk_id[:1].lower()}_drive"

    def _is_drive_root_path(self, target_path: str) -> bool:
        text = str(target_path or "").strip().replace("/", "\\")
        return bool(re.match(r"^([A-Za-z]):\\*$", text))

    def _normalize_file_permission(self, value: Any) -> str:
        text = str(value or "unset").strip().lower() or "unset"
        if text in {"allow", "once", "deny", "unset"}:
            return text
        if text in {"restricted", "\u53d7\u9650"}:
            return "once"
        if text in {"\u662f", "\u5141\u8bb8"}:
            return "allow"
        if text in {"\u5426", "\u62d2\u7edd"}:
            return "deny"
        return "unset"

    # [MigrationRiskHigh]
    # 当前仍是主链关键逻辑，暂不能删除或迁移。
    # 后续应通过 ReceiptMapper / ResultBridge 收口。
    def _apply_jiuchasi_qin_task_patch(
        self,
        task_draft: dict[str, Any],
        qin_task_patch: dict[str, Any],
        *,
        jiuchasi_session_id: str = "",
    ) -> dict[str, Any]:
        draft = dict(task_draft or {})
        patch = qin_task_patch if isinstance(qin_task_patch, dict) else {}

        action = str(patch.get("action", draft.get("action", "")) or "").strip()
        if action:
            draft["action"] = action

        target = draft.get("target", {}) if isinstance(draft.get("target"), dict) else {}
        target = dict(target)

        target_value = str(patch.get("target", "") or "").strip()
        path_hint = str(patch.get("path_hint", "") or "").strip()
        target_label_hint = str(
            patch.get("target_label_hint", patch.get("target_label", ""))
            or ""
        ).strip()
        app_target_label = target_label_hint or target_value
        filesystem_target = path_hint or target_value

        if action.startswith("folder."):
            target["kind"] = "folder"
            if filesystem_target:
                target["path_hint"] = filesystem_target
                target["name_hint"] = target_value or filesystem_target
                target["identity"] = filesystem_target

        elif action.startswith("file."):
            target["kind"] = "file"
            if filesystem_target:
                target["path_hint"] = filesystem_target
            if target_value:
                target["name_hint"] = target_value
                target["identity"] = target_value

        elif action.startswith("app."):
            target["kind"] = "app"
            if app_target_label:
                target["app_hint"] = app_target_label
                target["name_hint"] = app_target_label
                target["label_hint"] = app_target_label
                target["identity"] = app_target_label

        else:
            if target_value:
                target["name_hint"] = target_value
                target["identity"] = target_value

        draft["target"] = target

        arguments = draft.get("arguments", {}) if isinstance(draft.get("arguments"), dict) else {}
        arguments = dict(arguments)
        arguments["jiuchasi_enabled"] = True
        arguments["jiuchasi_session_id"] = str(jiuchasi_session_id or "")
        arguments["jiuchasi_qin_task_patch"] = patch
        arguments["source"] = "jiuchasi_chat_runtime_bridge"
        
        if isinstance(patch.get("needs"), dict):
            needs = draft.get("needs", {}) if isinstance(draft.get("needs"), dict) else {}
            patched_needs = dict(needs)
            patched_needs.update(patch.get("needs", {}))
            draft["needs"] = patched_needs
        elif isinstance(patch.get("needs"), list):
            needs = draft.get("needs", {}) if isinstance(draft.get("needs"), dict) else {}
            patched_needs = dict(needs)
            patched_needs["items"] = list(patch.get("needs", []))
            draft["needs"] = patched_needs

        if "candidate_search" in patch:
            needs = draft.get("needs", {}) if isinstance(draft.get("needs"), dict) else {}
            patched_needs = dict(needs)
            patched_needs["candidate_search"] = bool(patch.get("candidate_search"))
            draft["needs"] = patched_needs

        if "requires_confirmation" in patch:
            needs = draft.get("needs", {}) if isinstance(draft.get("needs"), dict) else {}
            patched_needs = dict(needs)
            patched_needs["requires_confirmation"] = bool(patch.get("requires_confirmation"))
            draft["needs"] = patched_needs

        for key in (
            "target_label_hint",
            "candidate_search",
            "requires_confirmation",
            "path_hint",
        ):
            if key in patch:
                arguments[key] = patch.get(key)

        if action.startswith("app.") and app_target_label:
            arguments["target_name"] = app_target_label
            arguments["target_label"] = app_target_label
            arguments["app_name"] = app_target_label
            arguments["app_hint"] = app_target_label
            arguments["target_label_hint"] = app_target_label
            arguments["llm_target_hint"] = app_target_label
            arguments["normalized_target"] = app_target_label

        if action.startswith(("folder.", "file.")) and filesystem_target:
            arguments["target_path"] = filesystem_target
            arguments["path_hint"] = filesystem_target
            arguments["target_name"] = target_value or filesystem_target

        if action == "folder.open" and filesystem_target:
            target["kind"] = "folder"
            target["path_hint"] = filesystem_target
            target["name_hint"] = target_value or filesystem_target
            target["identity"] = filesystem_target
            arguments["request_allowed"] = True
            arguments["target_path"] = filesystem_target
            arguments["path_hint"] = filesystem_target
            arguments["target_type"] = "directory"
            draft["request_allowed"] = True
            permission = self._file_permission_bridge_for_open(filesystem_target)
            if permission:
                root_id = str(permission.get("root_id", "") or "").strip()
                if root_id:
                    draft["root_id"] = root_id
                    arguments["root_id"] = root_id
                for key in (
                    "permission_state",
                    "effective_permission_state",
                    "permission_source_type",
                    "permission_source_key",
                    "file_actions_enabled",
                ):
                    if key in permission:
                        arguments[key] = permission.get(key)
                print(
                    "[FilePermissionBridge] "
                    f"target={filesystem_target!r} "
                    f"root_id={str(permission.get('root_id', '') or '')!r} "
                    f"permission={str(permission.get('effective_permission_state', '') or '')!r} "
                    f"request_allowed={bool(arguments.get('request_allowed', False))}"
                )

        if action == "file.open" and filesystem_target:
            target["kind"] = "file"
            target["path_hint"] = filesystem_target
            target["name_hint"] = target_value or filesystem_target
            target["identity"] = filesystem_target
            arguments["request_allowed"] = True
            arguments["target_path"] = filesystem_target
            arguments["path_hint"] = filesystem_target
            arguments["target_type"] = "file"
            draft["request_allowed"] = True
            permission = self._file_permission_bridge_for_open(filesystem_target)
            if permission:
                root_id = str(permission.get("root_id", "") or "").strip()
                if root_id:
                    draft["root_id"] = root_id
                    arguments["root_id"] = root_id
                for key in (
                    "permission_state",
                    "effective_permission_state",
                    "permission_source_type",
                    "permission_source_key",
                    "file_actions_enabled",
                ):
                    if key in permission:
                        arguments[key] = permission.get(key)
                print(
                    "[FilePermissionBridge] "
                    f"target={filesystem_target!r} "
                    f"root_id={str(permission.get('root_id', '') or '')!r} "
                    f"permission={str(permission.get('effective_permission_state', '') or '')!r} "
                    f"request_allowed={bool(arguments.get('request_allowed', False))}"
                )

        draft["arguments"] = arguments
        print(
            "[JiuchasiBridge] patched_task "
            f"action={str(draft.get('action', '') or '')!r} "
            f"target={str(target.get('name_hint', '') or target.get('path_hint', '') or target.get('app_hint', '') or '')!r} "
            f"path_hint={str(target.get('path_hint', '') or arguments.get('path_hint', '') or '')!r} "
            f"target_label_hint={str(arguments.get('target_label_hint', '') or '')!r} "
            f"candidate_search={arguments.get('candidate_search', '')!r} "
            f"requires_confirmation={arguments.get('requires_confirmation', '')!r}"
        )
        return draft
        
    def _create_jiuchasi_pending_task(
        self,
        *,
        user_text: str,
        jiuchasi_result: dict[str, Any],
        patched_task_draft: dict[str, Any],
    ) -> str:
        try:
            from services.desktop.tianting.pending_task_service import create_pending_task

            result = jiuchasi_result if isinstance(jiuchasi_result, dict) else {}
            decision = result.get("decision", {}) if isinstance(result.get("decision"), dict) else {}
            qin_task_patch = result.get("qin_task_patch", {}) if isinstance(result.get("qin_task_patch"), dict) else {}
            pending_question = result.get("pending_question", {}) if isinstance(result.get("pending_question"), dict) else {}
            candidates = result.get("candidates", []) if isinstance(result.get("candidates"), list) else []

            action = str(qin_task_patch.get("action", patched_task_draft.get("action", "")) or "").strip()
            target = str(qin_task_patch.get("target", "") or "").strip()

            selected_candidate: dict[str, Any] = {}
            if target:
                selected_candidate = {
                    "candidate_id": "jiuchasi_confirmed_target",
                    "display_index": 1,
                    "label": target,
                    "name": target,
                    "target_name": target,
                    "target_label": target,
                    "source": "jiuchasi",
                    "recommended": True,
                }

            if not candidates and selected_candidate:
                candidates = [selected_candidate]

            status = str(result.get("status", decision.get("status", "")) or "")
            if status == "need_confirmation" and action == "app.launch":
                choice_type = "app_launch_confirmation"
            elif action == "app.close":
                choice_type = "app_close_candidate"
            elif action == "file.open":
                choice_type = "file_candidate"
            else:
                choice_type = "jiuchasi_candidate"

            message = decision.get("message", {}) if isinstance(decision.get("message"), dict) else {}
            message_key = str(message.get("key", result.get("message_key", "")) or "")
            message_params = message.get("slots", {}) if isinstance(message.get("slots"), dict) else {}

            if status == "need_confirmation":
                ui_prompt_type = "confirm_or_choose"
            elif status == "need_deep_search":
                ui_prompt_type = "deep_search"
            else:
                ui_prompt_type = "choose_one"

            pending = create_pending_task(
                original_action=action or "jiuchasi.decision",
                original_user_text=user_text,
                candidates=candidates,
                original_task_draft=patched_task_draft,
                original_puzzle_summary={
                    "raw_user_text": user_text,
                    "source": "jiuchasi_chat_runtime_bridge",
                    "jiuchasi_session_id": str(result.get("session_id", "") or ""),
                    "jiuchasi_status": status,
                    "pending_question": pending_question,
                },
                choice_type=choice_type,
                selected_candidate=selected_candidate,
                ui_prompt_type=ui_prompt_type,
                message_key=message_key,
                message_params=message_params,
            )

            return str(pending.get("pending_task_id", "") or "")
        except Exception as exc:
            print(f"[JiuchasiBridge] create_pending_failed error={exc}")
            return ""

    def _jiuchasi_ui_prompt(
        self,
        *,
        status: str,
        pending_task_id: str,
        message_key: str,
        message_params: dict[str, Any],
        display_text: str,
        candidates: list[Any],
    ) -> dict[str, Any]:
        clean_candidates = self._jiuchasi_ui_candidates(
            candidates,
            pending_task_id=pending_task_id,
        )
        if status == "need_deep_search":
            return {
                "schema_version": "desktop_ui_prompt_v1",
                "prompt_type": "deep_search_card",
                "style_key": "pending_neon_green",
                "transient": True,
                "record_as_assistant_message": False,
                "tts_enabled": False,
                "pending_task_id": pending_task_id,
                "message_key": message_key or "desktop.pending.deep_search.body",
                "message_params": message_params if isinstance(message_params, dict) else {},
                "display_text": display_text,
                "allow_background_llm": True,
                "background_task_type": "target_deep_search",
                "actions": [
                    {
                        "action": "deep_search",
                        "label_key": "desktop.ui.action.deep_search",
                        "label": self._desktop_text(
                            "desktop.ui.action.deep_search",
                            fallback="Deep search",
                        ),
                        "payload": {
                            "pending_task_id": pending_task_id,
                        },
                    },
                    {
                        "action": "refresh_software",
                        "label_key": "desktop.ui.action.refresh_software",
                        "label": self._desktop_text(
                            "desktop.ui.action.refresh_software",
                            fallback="Refresh software",
                        ),
                        "payload": {
                            "pending_task_id": pending_task_id,
                        },
                    },
                    {
                        "action": "manual_select",
                        "label_key": "desktop.ui.action.manual_select",
                        "label": self._desktop_text(
                            "desktop.ui.action.manual_select",
                            fallback="Manual select",
                        ),
                        "payload": {
                            "pending_task_id": pending_task_id,
                        },
                    },
                    {
                        "action": "cancel",
                        "label_key": "desktop.ui.action.cancel",
                        "label": self._desktop_text(
                            "desktop.ui.action.cancel",
                            fallback="Cancel",
                        ),
                        "payload": {
                            "pending_task_id": pending_task_id,
                        },
                    },
                ],
                "candidates": clean_candidates,
            }

        if status == "multiple_candidates":
            return {
                "schema_version": "desktop_ui_prompt_v1",
                "prompt_type": "candidate_card",
                "style_key": "pending_neon_green",
                "transient": True,
                "record_as_assistant_message": False,
                "tts_enabled": False,
                "pending_task_id": pending_task_id,
                "message_key": message_key,
                "message_params": message_params if isinstance(message_params, dict) else {},
                "display_text": display_text,
                "actions": [
                    {
                        "action": "cancel",
                        "label_key": "desktop.ui.action.cancel",
                        "label": self._desktop_text(
                            "desktop.ui.action.cancel",
                            fallback="Cancel",
                        ),
                        "payload": {
                            "pending_task_id": pending_task_id,
                        },
                    }
                ],
                "candidates": clean_candidates,
            }

        return {
            "schema_version": "desktop_ui_prompt_v1",
            "prompt_type": "confirmation_card",
            "style_key": "pending_neon_green",
            "transient": True,
            "record_as_assistant_message": False,
            "tts_enabled": False,
            "pending_task_id": pending_task_id,
            "message_key": message_key,
            "message_params": message_params if isinstance(message_params, dict) else {},
            "display_text": display_text,
            "actions": [
                {
                    "action": "confirm",
                    "label_key": "desktop.ui.action.confirm_open",
                    "label": self._desktop_text(
                        "desktop.ui.action.confirm_open",
                        fallback="Confirm open",
                    ),
                    "payload": {
                        "pending_task_id": pending_task_id,
                    },
                },
                {
                    "action": "cancel",
                    "label_key": "desktop.ui.action.cancel",
                    "label": self._desktop_text(
                        "desktop.ui.action.cancel",
                        fallback="Cancel",
                    ),
                    "payload": {
                        "pending_task_id": pending_task_id,
                    },
                },
            ],
            "candidates": clean_candidates,
        }

    def _jiuchasi_ui_candidates(
        self,
        candidates: list[Any],
        *,
        pending_task_id: str,
    ) -> list[dict[str, Any]]:
        clean: list[dict[str, Any]] = []
        for index, item in enumerate(candidates if isinstance(candidates, list) else [], start=1):
            candidate = item if isinstance(item, dict) else {}
            candidate_id = str(candidate.get("candidate_id", "") or "").strip() or f"candidate_{index:03d}"
            display_index = int(candidate.get("display_index", index) or index)
            label = str(
                candidate.get("label")
                or candidate.get("target_label")
                or candidate.get("name")
                or candidate.get("target_name")
                or ""
            ).strip()
            subtitle = str(
                candidate.get("subtitle")
                or candidate.get("safe_location")
                or candidate.get("window_title")
                or candidate.get("reason")
                or ""
            ).strip()
            kind = str(
                candidate.get("kind")
                or candidate.get("target_type")
                or candidate.get("target_kind")
                or ""
            ).strip()
            source = candidate.get("source", "")
            if isinstance(source, list):
                source_text = ", ".join(str(value) for value in source if value)
            else:
                source_text = str(source or "").strip()
            clean.append(
                {
                    "candidate_id": candidate_id,
                    "display_index": display_index,
                    "label": label,
                    "subtitle": subtitle,
                    "kind": kind,
                    "source": source_text,
                    "target_path": str(
                        candidate.get("target_path")
                        or candidate.get("path")
                        or candidate.get("safe_path")
                        or ""
                    ).strip(),
                    "app_label": str(
                        candidate.get("app_label")
                        or candidate.get("target_label")
                        or label
                        or ""
                    ).strip(),
                    "action": "select_candidate",
                    "payload": {
                        "pending_task_id": pending_task_id,
                        "candidate_id": candidate_id,
                        "display_index": display_index,
                    },
                }
            )
        return clean

    def _jiuchasi_result_to_safe_payload(
        self,
        *,
        user_text: str,
        jiuchasi_result: dict[str, Any],
        patched_task_draft: dict[str, Any],
    ) -> dict[str, Any]:
        result = jiuchasi_result if isinstance(jiuchasi_result, dict) else {}
        status = str(result.get("status", "") or "").strip()

        visible_text = str(result.get("visible_text", "") or "").strip()

        qin_task_patch = (
            result.get("qin_task_patch", {})
            if isinstance(result.get("qin_task_patch"), dict)
            else {}
        )

        decision = (
            result.get("decision", {})
            if isinstance(result.get("decision"), dict)
            else {}
        )

        response = (
            result.get("response", {})
            if isinstance(result.get("response"), dict)
            else {}
        )

        message_key = str(
            response.get("message_key", decision.get("message_key", ""))
            or ""
        ).strip()

        message_params = (
            decision.get("message_slots", {})
            if isinstance(decision.get("message_slots"), dict)
            else {}
        )

        if status in {"chat_reply", "need_clarification"}:
            return {
                "ok": True,
                "status": status,
                "message_key": message_key,
                "message_params": message_params,
                "safe_user_message": visible_text or self._desktop_text(
                    "desktop.generic.need_clarification",
                    user_text=user_text,
                    fallback="我需要再确认一个细节后才能继续。",
                ),
                "executed": False,
                "jiuchasi_result": result,
            }

        if status in {"need_confirmation", "multiple_candidates", "need_deep_search"}:
            pending_task_id = self._create_jiuchasi_pending_task(
                user_text=user_text,
                jiuchasi_result=result,
                patched_task_draft=patched_task_draft,
            )

            return {
                "ok": True,
                "status": status,
                "message_key": message_key,
                "message_params": message_params,
                "safe_user_message": visible_text or self._desktop_text(
                    "desktop.pending.deep_search.body" if status == "need_deep_search" else "desktop.generic.need_confirmation",
                    user_text=user_text,
                    fallback="我需要你确认后才能继续。",
                ),
                "executed": False,
                "pending_task_id": pending_task_id,
                "requires_user_choice": True,
                "needs_user_choice": True,
                "candidates": result.get("candidates", [])
                if isinstance(result.get("candidates"), list)
                else [],
                "qin_task_patch": qin_task_patch,
                "jiuchasi_result": result,
                "ui_prompt": self._jiuchasi_ui_prompt(
                    status=status,
                    pending_task_id=pending_task_id,
                    message_key=message_key,
                    message_params=message_params,
                    display_text=visible_text or self._desktop_text(
                        "desktop.pending.deep_search.body" if status == "need_deep_search" else "desktop.generic.need_confirmation",
                        user_text=user_text,
                        fallback="请确认后继续。",
                    ),
                    candidates=result.get("candidates", [])
                    if isinstance(result.get("candidates"), list)
                    else [],
                ),
            }

        if status == "ready_for_qin":
            if self._jiuchasi_dry_run_only():
                suffix = self._desktop_text(
                    "desktop.jiuchasi.dry_run_suffix",
                    user_text=user_text,
                    fallback="（当前为纠察司接入测试，未执行真实动作。）",
                )

                return {
                    "ok": True,
                    "status": "jiuchasi_ready_for_qin_dry_run",
                    "message_key": message_key or "desktop.jiuchasi.ready_for_qin_dry_run",
                    "message_params": message_params,
                    "safe_user_message": (visible_text + suffix).strip() if visible_text else suffix,
                    "executed": False,
                    "qin_task_patch": qin_task_patch,
                    "jiuchasi_result": result,
                }

            return {
                "ok": True,
                "status": "jiuchasi_ready_for_qin_continue",
                "message_key": message_key,
                "message_params": message_params,
                "safe_user_message": visible_text,
                "executed": False,
                "qin_task_patch": qin_task_patch,
                "jiuchasi_result": result,
                "__continue_to_qin__": True,
            }

        return {
            "ok": False,
            "status": status or "jiuchasi_unknown_status",
            "message_key": message_key,
            "message_params": message_params,
            "safe_user_message": visible_text or self._desktop_text(
                "desktop.generic.failed",
                user_text=user_text,
                fallback="桌面操作未能完成。",
            ),
            "executed": False,
            "jiuchasi_result": result,
        }

    def _infer_desktop_target_label(self, result: dict[str, Any], task: dict[str, Any]) -> str:
        payload = result if isinstance(result, dict) else {}
        data = payload.get("data", {}) if isinstance(payload.get("data"), dict) else {}
        receipt = data.get("receipt_packet", {}) if isinstance(data.get("receipt_packet"), dict) else {}

        arguments = task.get("arguments", {}) if isinstance(task.get("arguments"), dict) else {}

        def first_text(*values: Any) -> str:
            for value in values:
                text = str(value or "").strip()
                if text and text not in {"-", "None", "null"}:
                    return text
            return ""

        def label_from_candidate(candidate: Any) -> str:
            if not isinstance(candidate, dict):
                return ""
            return first_text(
                candidate.get("label"),
                candidate.get("title"),
                candidate.get("target_name"),
                candidate.get("app_name"),
                candidate.get("name"),
                candidate.get("app_id"),
            )

        # 1. 优先从 pending/候选对象里取用户能看懂的名字
        for key in (
            "selected_candidate",
            "app_launch_selected_candidate",
            "app_close_selected_candidate",
            "candidate",
        ):
            label = label_from_candidate(arguments.get(key))
            if label:
                return label

        for source in (payload, data, receipt):
            if not isinstance(source, dict):
                continue
            for key in ("selected_candidate", "candidate"):
                label = label_from_candidate(source.get(key))
                if label:
                    return label

        # 2. 再从 task / arguments / data / receipt 的常规字段取
        for source in (arguments, task, data, receipt, payload):
            if not isinstance(source, dict):
                continue
            target = first_text(
                source.get("target_label"),
                source.get("target_name"),
                source.get("current_target"),
                source.get("app_name"),
                source.get("label"),
                source.get("launch_target_raw"),
                source.get("target_path"),
            )
            if target:
                return target

        return ""

    # [MigrationRiskHigh]
    # 当前仍是主链关键逻辑，暂不能删除或迁移。
    # 后续应通过 ReceiptMapper / ResultBridge 收口。
    def _desktop_execution_message_from_qin_result(
        self,
        action: str,
        target: str,
        result: dict[str, Any],
    ) -> dict[str, Any]:
        payload = result if isinstance(result, dict) else {}
        data = payload.get("data", {}) if isinstance(payload.get("data"), dict) else {}
        receipt = data.get("receipt_packet", {}) if isinstance(data.get("receipt_packet"), dict) else {}
        target_text = str(target or "").strip()

        def first_text(*values: Any) -> str:
            for value in values:
                text = str(value or "").strip()
                if text:
                    return text
            return ""

        def any_bool(*values: Any) -> bool:
            return any(isinstance(value, bool) and value for value in values)

        status = first_text(payload.get("status"), data.get("status"), receipt.get("status"))
        message = first_text(
            payload.get("message"),
            payload.get("safe_user_message"),
            payload.get("reason"),
            payload.get("error"),
            data.get("message"),
            data.get("safe_user_message"),
            data.get("reason"),
            data.get("error"),
            receipt.get("message"),
            receipt.get("safe_user_message"),
            receipt.get("reason"),
            receipt.get("error"),
        )
        material_status = first_text(data.get("material_status"), receipt.get("material_status"))
        haystack = " ".join([status, message, material_status]).lower()
        has_open_session = any(
            key in source and source.get(key)
            for source in (payload, data, receipt)
            if isinstance(source, dict)
            for key in ("open_session", "open_session_id", "session_id")
        )

        permission_markers = (
            "unsupported host permission state",
            "need_permission",
            "not allowed",
            "deny",
            "permission state is deny",
            "permission state is unset",
        )
        if any(marker in haystack for marker in permission_markers):
            return {
                "ok": False,
                "executed": False,
                "status": "permission_denied",
                "message_key": "desktop.exec.permission.denied",
                "message_params": {"target": target_text},
                "fallback_text": f"我找到了「{target_text}」，但当前权限不允许执行。请先在对应治理区设置为允许或受限。",
            }

        if "winerror 5" in haystack or "拒绝访问" in haystack:
            return {
                "ok": False,
                "executed": False,
                "status": "windows_access_denied",
                "message_key": "desktop.exec.windows.access_denied",
                "message_params": {"target": target_text},
                "fallback_text": f"我找到了「{target_text}」，但 Windows 拒绝直接启动它。可能需要管理员权限、正确工作目录，或改用启动器入口。",
            }

        if status in {"pending_user_choice", "app_launch_pending_user_choice"}:
            return {
                "ok": False,
                "executed": False,
                "status": status,
                "message_key": "desktop.exec.multiple_candidates",
                "message_params": {"target": target_text},
                "fallback_text": "我找到了多个可能的对象，请选择要操作哪一个。",
            }

        if status in {"choice_cancelled", "app_close_choice_cancelled"} or "cancelled" in haystack or "canceled" in haystack:
            return {
                "ok": True,
                "executed": False,
                "status": "choice_cancelled",
                "message_key": "desktop.exec.cancelled",
                "message_params": {"target": target_text},
                "fallback_text": "已取消本次操作。",
            }

        action_text = str(action or payload.get("action", "") or "").strip()
        if action_text in {"folder.open", "file.open"}:
            opened = (
                bool(payload.get("ok", False))
                or any_bool(payload.get("executed"), data.get("executed"), receipt.get("executed"))
                or any(marker in haystack for marker in ("opened", "open_session", "sent open request", "host sent"))
                or material_status == "opened"
                or has_open_session
            )
            if opened:
                return {
                    "ok": True,
                    "executed": True,
                    "status": "open_done",
                    "message_key": "desktop.exec.open.success",
                    "message_params": {"target": target_text},
                    "fallback_text": f"已打开 {target_text}。",
                }

        if action_text == "app.launch":
            launch_sent = bool(payload.get("ok", False)) or "host sent launch request" in haystack
            if launch_sent:
                return {
                    "ok": True,
                    "executed": True,
                    "status": "app_launch_done",
                    "message_key": "desktop.exec.app.launch.sent",
                    "message_params": {"target": target_text},
                    "fallback_text": f"已发送软件启动请求：{target_text}。",
                }
            
        raw_message = " ".join([
            str(result.get("message", "") or ""),
            str(data.get("safe_user_message", "") or ""),
            str(data.get("error", "") or ""),
            str(data.get("resolution_status", "") or ""),
            str(data.get("close_strategy", "") or ""),
        ]).lower()

        if action == "app.close" and (
            "soft-close material" in raw_message
            or "not_enough_material" in raw_message
            or "selected app candidate does not contain enough" in raw_message
        ):
            target_name = target or "目标软件"
            return {
                "ok": False,
                "executed": False,
                "message_key": "desktop.app.close.not_enough_material",
                "message_params": {"target": target_name},
                "fallback_text": f"我找到了“{target_name}”，但当前缺少可安全关闭它的窗口或进程材料。",
                "status": "app_close_not_enough_material",
            }

        return {}

    # [MigrationRiskHigh]
    # 当前仍是主链关键逻辑，暂不能删除或迁移。
    # 后续应通过 ReceiptMapper / ResultBridge 收口。
    def _safe_qin_payload(self, result: dict[str, Any], *, task: dict[str, Any]) -> dict[str, Any]:
        payload = result if isinstance(result, dict) else {}
        message = str(payload.get("message", "") or "").strip()
        data = payload.get("data", {}) if isinstance(payload.get("data"), dict) else {}

        if not message:
            message = str(data.get("safe_user_message", data.get("error", "")) or "").strip()
        if not message:
            message = self._desktop_text(
                "desktop.qin.submitted",
                fallback="桌面操作已提交秦链处理。",
            )

        receipt = data.get("receipt_packet", {}) if isinstance(data.get("receipt_packet"), dict) else {}

        raw_params = payload.get(
            "message_params",
            data.get("message_params", receipt.get("message_params", {})),
        )
        message_params = dict(raw_params) if isinstance(raw_params, dict) else {}

        target_label = self._infer_desktop_target_label(payload, task)
        if target_label and not str(message_params.get("target", "") or "").strip():
            message_params["target"] = target_label

        status = str(payload.get("status", data.get("status", "")) or "")
        action = str(payload.get("action", task.get("action", "")) or "")
        execution_message = self._desktop_execution_message_from_qin_result(action, target_label, payload)
        if execution_message:
            execution_params = execution_message.get("message_params", {})
            if isinstance(execution_params, dict):
                message_params.update({key: value for key, value in execution_params.items() if value not in (None, "")})
            message_key_for_exec = str(execution_message.get("message_key", "") or "")
            fallback_text = str(execution_message.get("fallback_text", "") or "")
            if message_key_for_exec:
                message = self._desktop_text(message_key_for_exec, message_params, fallback=fallback_text)
            status = str(execution_message.get("status", status) or status)
            print(
                "[QinExecMessage] "
                f"action={action!r} target={target_label!r} "
                f"message_key={message_key_for_exec!r} status={status!r}"
            )

        # 有些 Host 执行结果只返回 ok/message，不给 status，这里做最小状态补齐
        if not status:
            if action == "app.launch":
                status = "app_launch_done" if bool(payload.get("ok", False)) else "app_launch_failed"
            elif action == "app.close":
                status = "app_close_done" if bool(payload.get("ok", False)) else "app_close_failed"

        output = {
            "ok": bool(execution_message.get("ok", payload.get("ok", False))) if execution_message else bool(payload.get("ok", False)),
            "status": status,
            "action": action,
            "target": target_label,
            "target_name": target_label,
            "message_key": str(
                execution_message.get("message_key", "") if execution_message else payload.get(
                    "message_key",
                    data.get("message_key", receipt.get("message_key", "")),
                )
                or ""
            ),
            "message_params": message_params,
            "choice_request": receipt.get("choice_request", {}) if isinstance(receipt.get("choice_request"), dict) else {},
            "ui_prompt_type": str(data.get("ui_prompt_type", receipt.get("ui_prompt_type", "")) or ""),
            "ui_actions": data.get("ui_actions", receipt.get("ui_actions", []))
            if isinstance(data.get("ui_actions", receipt.get("ui_actions", [])), list)
            else [],
            "safe_user_message": message,
            "executed": bool(execution_message.get("executed", payload.get("ok", False))) if execution_message else bool(payload.get("ok", False)),
            "qin_result": payload,
        }
        try:
            from services.runtime.interaction.receipt_mapper import ReceiptMapper

            output["_receipt_mapper_preview"] = ReceiptMapper().map_qin_result(
                result=payload,
                task=task,
            )
        except Exception as exc:
            print(f"[ReceiptMapperPreview] failed error={exc!r}")
        return output

    def _log_qin_exec_result(self, action: str, result: dict[str, Any], *, task: dict[str, Any]) -> None:
        payload = result if isinstance(result, dict) else {}
        data = payload.get("data", {}) if isinstance(payload.get("data"), dict) else {}
        receipt = data.get("receipt_packet", {}) if isinstance(data.get("receipt_packet"), dict) else {}
        choice_request = receipt.get("choice_request", {}) if isinstance(receipt.get("choice_request"), dict) else {}

        def first_text(*values: Any) -> str:
            for value in values:
                text = str(value or "").strip()
                if text:
                    return text
            return ""

        def first_bool(*values: Any) -> bool:
            for value in values:
                if isinstance(value, bool):
                    return value
            return False

        candidates: list[Any] = []
        for value in (
            payload.get("candidates"),
            data.get("candidates"),
            choice_request.get("candidates"),
            receipt.get("candidates"),
        ):
            if isinstance(value, list):
                candidates = value
                break

        candidate_labels: list[str] = []
        for candidate in candidates[:3]:
            if not isinstance(candidate, dict):
                continue
            label = first_text(
                candidate.get("label"),
                candidate.get("title"),
                candidate.get("target_name"),
                candidate.get("app_name"),
                candidate.get("name"),
                candidate.get("app_id"),
            )
            if label:
                candidate_labels.append(label)

        status = first_text(payload.get("status"), data.get("status"), receipt.get("status"))
        message = first_text(
            payload.get("message"),
            payload.get("safe_user_message"),
            data.get("safe_user_message"),
            receipt.get("safe_user_message"),
        )
        print(
            "[QinExec] "
            f"ok={bool(payload.get('ok', False))!r} "
            f"executed={first_bool(payload.get('executed'), data.get('executed'))!r} "
            f"status={status!r} "
            f"action={first_text(action, payload.get('action'), data.get('current_action'), task.get('action'))!r} "
            f"error={first_text(payload.get('error'), data.get('error'), receipt.get('error'))!r} "
            f"reason={first_text(payload.get('reason'), data.get('reason'), receipt.get('reason'), data.get('resolution_status'))!r} "
            f"message={self._short_log_text(message)!r} "
            f"visible_text={self._short_log_text(first_text(payload.get('visible_text'), data.get('visible_text')))!r} "
            f"adapter_id={first_text(payload.get('adapter_id'), data.get('adapter_id'))!r} "
            f"backend={first_text(payload.get('backend'), data.get('backend'), data.get('test_backend'))!r} "
            f"decision={first_text(payload.get('decision'), data.get('decision'), data.get('resolution_status'))!r} "
            f"candidate_count={len(candidates)} "
            f"candidates={candidate_labels!r}"
        )

    def _short_log_text(self, value: Any, limit: int = 180) -> str:
        text = str(value or "").strip()
        if len(text) <= limit:
            return text
        return text[: limit - 1] + "…"

    def _desktop_execution_fallback(
        self,
        text: str,
        *,
        actor_role: str,
        input_channel: str,
        error: str,
    ) -> dict[str, Any]:
        try:
            from services.desktop.xingjun.llm_bridge_dry_run import dry_run_user_text

            dry_run = dry_run_user_text(text, actor_role=actor_role, input_channel=input_channel)
            return self._desktop_safe_payload(
                ok=False,
                status="qin_execution_failed_dry_run_fallback",
                message_key="desktop.qin.failed_dry_run_fallback",
                message_params={"error": error},
                user_text=text,
                fallback="真实桌面执行链发生错误，已改为生成安全测试结果。",
                executed=False,
                extra={
                    "error": error,
                    "dry_run": dry_run,
                },
            )
        except Exception:
            return self._desktop_safe_payload(
                ok=False,
                status="qin_execution_failed",
                message_key="desktop.qin.failed_blocked",
                message_params={"error": error},
                user_text=text,
                fallback="真实桌面执行链发生错误，已阻止桌面动作。",
                executed=False,
                extra={
                    "error": error,
                },
            )

    def _qin_runtime(self):
        runtime = getattr(self, "_chat_qin_runtime", None)
        if runtime is None:
            from services.desktop.qin_runtime_service import QinRuntimeService

            runtime = QinRuntimeService(self._project_root())
            self._chat_qin_runtime = runtime
        return runtime

    def _project_root(self):
        machine_profile = getattr(self.c, "machine_profile_service", None)
        project_root = getattr(machine_profile, "project_root", None)
        return project_root or Path(__file__).resolve().parents[2]

    def _build_interaction_result_from_safe_payload(
        self,
        *,
        request_id: int,
        user_text: str,
        safe_payload: dict[str, Any],
        desktop_route: dict[str, Any],
    ) -> dict[str, Any]:
        payload = safe_payload if isinstance(safe_payload, dict) else {}
        route_data = desktop_route if isinstance(desktop_route, dict) else {}
        route = str(route_data.get("route", "") or "")
        confidence = route_data.get("confidence", 0.0)
        target = str(payload.get("target", payload.get("target_name", "")) or "")
        display_text = str(payload.get("display_text", "") or payload.get("safe_user_message", "") or "")
        tts_text = str(payload.get("tts_text", "") or display_text)

        receipt = build_receipt_material(
            source="chat_runtime.safe_payload",
            route=route,
            status=payload.get("status", ""),
            ok=payload.get("ok", True),
            executed=payload.get("executed", False),
            action=payload.get("action", ""),
            target=target,
            message_key=payload.get("message_key", ""),
            message_params=payload.get("message_params", {}),
            safe_user_message=payload.get("safe_user_message", ""),
            display_text=display_text,
            tts_text=tts_text,
            ui_prompt=payload.get("ui_prompt", {}),
            qin_result=payload.get("qin_result", {}),
            jiuchasi_result=payload.get("jiuchasi_result", {}),
            pending_result=payload.get("pending_result", {}),
            system_result=payload.get("system_result", {}),
            raw_payload=payload,
            debug_refs={
                "request_id": request_id,
                "desktop_route": route,
                "route_confidence": confidence,
                "schema_stage": "phase4_sidecar_only",
            },
            extra={
                "raw_user_text": user_text,
                "pending_task_id": payload.get("pending_task_id", ""),
                "memory_update_plan": payload.get("memory_update_plan", {}),
                "action_hint": route_data.get("action_hint", ""),
            },
        )
        context = self.interaction_center.build_context(
            request_id=request_id,
            raw_user_text=user_text,
            input_channel=route_data.get("input_channel", ""),
            from_voice=str(route_data.get("input_channel", "") or "") == "voice",
            actor_role=route_data.get("actor_role", ""),
            pending_task_id=payload.get("pending_task_id", route_data.get("pending_task_id", "")),
            extra={
                "debug": {
                    "schema_stage": "phase4_sidecar_only",
                    "desktop_route": route,
                    "route_confidence": confidence,
                }
            },
        )
        return build_interaction_result_from_receipt(context, receipt)

    def _append_ai_command_summary(
        self,
        *,
        request_id: int,
        user_text: str,
        desktop_route: dict[str, Any],
        payload: dict[str, Any],
        interaction_result: dict[str, Any],
        display_text: str,
        tts_text: str = "",
    ) -> None:
        try:
            from services.desktop.qin.yushitai.report_writer import ReportWriter
            from services.desktop.qin.yushitai.runtime_material_writer import RuntimeMaterialWriter

            route_data = desktop_route if isinstance(desktop_route, dict) else {}
            payload_data = payload if isinstance(payload, dict) else {}
            result_data = interaction_result if isinstance(interaction_result, dict) else {}
            qin_result = payload_data.get("qin_result", {}) if isinstance(payload_data.get("qin_result"), dict) else {}
            qin_data = qin_result.get("data", {}) if isinstance(qin_result.get("data"), dict) else {}
            memory_result = (
                payload_data.get("memory_update_result", {})
                if isinstance(payload_data.get("memory_update_result"), dict)
                else {}
            )
            jiuchasi_result = (
                result_data.get("jiuchasi_result", {})
                if isinstance(result_data.get("jiuchasi_result"), dict)
                else payload_data.get("jiuchasi_result", {})
                if isinstance(payload_data.get("jiuchasi_result"), dict)
                else {}
            )

            def first_text(*values: Any) -> str:
                for value in values:
                    text = str(value or "").strip()
                    if text:
                        return text
                return ""

            backend = first_text(
                qin_result.get("backend"),
                qin_data.get("backend"),
                qin_data.get("test_backend"),
                route_data.get("execution_backend"),
                "host",
            ).lower()
            if backend not in {"host", "vm"}:
                backend = "host"

            record = {
                "schema_version": "ai_command_record_v1",
                "request_id": str(request_id),
                "user_text": str(user_text or ""),
                "route": first_text(result_data.get("route"), route_data.get("route")),
                "action": first_text(result_data.get("action"), payload_data.get("action"), route_data.get("action_hint")),
                "target": first_text(result_data.get("target"), payload_data.get("target"), payload_data.get("target_name")),
                "status": first_text(result_data.get("status"), payload_data.get("status"), "done"),
                "ok": bool(result_data.get("ok", payload_data.get("ok", True))),
                "executed": bool(result_data.get("executed", payload_data.get("executed", False))),
                "display_text": str(display_text or ""),
                "tts_text": str(tts_text or ""),
                "pending_task_id": first_text(result_data.get("pending_task_id"), payload_data.get("pending_task_id")),
                "jiuchasi_session_id": first_text(
                    jiuchasi_result.get("session_id"),
                    jiuchasi_result.get("jiuchasi_session_id"),
                    payload_data.get("jiuchasi_session_id"),
                ),
                "memory_update_status": first_text(memory_result.get("status")),
                "source": "language_interaction_center",
                "event_type": "command_finished",
            }

            report_writer = getattr(self.c, "yushitai_report_writer", None)
            if report_writer is None:
                report_writer = ReportWriter(self._project_root())
            RuntimeMaterialWriter(report_writer).append_ai_command(record, backend=backend)
        except Exception as exc:
            print(f"[AICommandSummary] append_failed error={exc!r}")

    def _finish_direct_safe_reply(
        self,
        request_id: int,
        user_text: str,
        safe_payload: dict[str, Any],
        desktop_route: dict[str, Any],
    ) -> None:
        self.c.chat_in_progress = False
        self.c._set_busy(False)
        self.c.window.hide_loading_overlay()

        payload = safe_payload if isinstance(safe_payload, dict) else {}
        interaction_result: dict[str, Any] = {}
        try:
            interaction_result = self._build_interaction_result_from_safe_payload(
                request_id=request_id,
                user_text=user_text,
                safe_payload=payload,
                desktop_route=desktop_route,
            )
            payload["_interaction_result_preview"] = interaction_result
            print(
                "[InteractionResultPreview] "
                f"route={interaction_result.get('route', '')!r} "
                f"status={interaction_result.get('status', '')!r} "
                f"handled={interaction_result.get('handled', False)!r} "
                f"executed={interaction_result.get('executed', False)!r}"
            )
        except Exception as exc:
            print(f"[InteractionResultPreview] failed error={exc!r}")

        try:
            interaction_result = self.interaction_center.polish_interaction_reply(interaction_result)
        except Exception as exc:
            print(f"[ReplyPolisher] failed error={exc!r}")

        ui_prompt = (
            interaction_result.get("ui_prompt", {})
            if isinstance(interaction_result.get("ui_prompt"), dict)
            else payload.get("ui_prompt", {})
            if isinstance(payload.get("ui_prompt"), dict)
            else {}
        )
        prompt_is_transient = bool(ui_prompt.get("transient"))
        record_as_assistant = not (
            prompt_is_transient and ui_prompt.get("record_as_assistant_message") is False
        )
        tts_enabled = not (prompt_is_transient and ui_prompt.get("tts_enabled") is False)

        display_text = (
            str(ui_prompt.get("display_text", "") or "").strip()
            or str(interaction_result.get("display_text", "") or "").strip()
            or str(interaction_result.get("safe_user_message", "") or "").strip()
            or str(payload.get("display_text", "") or "").strip()
            or str(payload.get("safe_user_message", "") or "").strip()
        )
        if not display_text:
            display_text = self._desktop_text(
                "desktop.generic.unknown",
                user_text=user_text,
                fallback="桌面操作已处理。",
            )

        self._append_ai_command_summary(
            request_id=request_id,
            user_text=user_text,
            desktop_route=desktop_route,
            payload=payload,
            interaction_result=interaction_result,
            display_text=display_text,
            tts_text=str(interaction_result.get("tts_text", "") or payload.get("tts_text", "") or "").strip(),
        )

        if prompt_is_transient:
            envelope = ReplyEnvelope(
                raw_text=display_text,
                final_text=display_text,
                display_text=display_text,
                tts_text="",
                source_type="desktop_pending_prompt",
                model_key="tianting",
                strategy_used=str((desktop_route or {}).get("route", "") or "desktop_route"),
                confidence=float((desktop_route or {}).get("confidence", 0.0) or 0.0),
            )
            self.c.last_reply_package = envelope
            self.write_reply_pipeline_files(envelope)

            if self.c.reply_pipeline_window is not None:
                self.c.reply_pipeline_window.update_reply_package(envelope)

            self.c.chat_history.append({"role": "user", "content": user_text})
            self.c._trim_history()

            started_at = self.c.request_start_times.pop(request_id, None)
            perf_started_at = None
            if hasattr(self.c, "request_perf_start_times"):
                perf_started_at = self.c.request_perf_start_times.pop(request_id, None)
            if perf_started_at is not None:
                print(f"[ChatPerf] total_ms={(time.perf_counter() - perf_started_at) * 1000.0:.2f}")

            widget = None
            append_card = getattr(self.c, "_append_pending_interaction_card_compat", None)
            if callable(append_card):
                try:
                    widget = append_card(ui_prompt)
                except Exception as exc:
                    print(f"[PendingInteractionCard] append_failed error={exc}")
                    widget = None

            if widget is not None:
                self.c.window.set_status(
                    self._desktop_text(
                        "desktop.pending.card_ready",
                        user_text=user_text,
                        fallback="需要你确认后继续。",
                    )
                )
                return

            self.c._append_ai_text_only_message(display_text)
            self.c.window.set_status(
                self._desktop_text(
                    "desktop.pending.card_fallback",
                    user_text=user_text,
                    fallback="需要你确认后继续。",
                )
            )
            return

        tts_text = (
            str(interaction_result.get("tts_text", "") or "").strip()
            or str(payload.get("tts_text", "") or "").strip()
            or display_text
        )
        if not tts_text:
            tts_text = display_text
        if not tts_enabled:
            tts_text = ""

        envelope = ReplyEnvelope(
            raw_text=display_text,
            final_text=display_text,
            display_text=display_text,
            tts_text=tts_text,
            source_type="desktop_route",
            model_key="tianting",
            strategy_used=str((desktop_route or {}).get("route", "") or "desktop_route"),
            confidence=float((desktop_route or {}).get("confidence", 0.0) or 0.0),
        )
        self.c.last_reply_package = envelope
        self.write_reply_pipeline_files(envelope)

        if self.c.reply_pipeline_window is not None:
            self.c.reply_pipeline_window.update_reply_package(envelope)

        self.c.chat_history.append({"role": "user", "content": user_text})
        if record_as_assistant:
            self.c.chat_history.append({"role": "assistant", "content": envelope.final_text})
        self.c._trim_history()

        started_at = self.c.request_start_times.pop(request_id, None)
        perf_started_at = None
        if hasattr(self.c, "request_perf_start_times"):
            perf_started_at = self.c.request_perf_start_times.pop(request_id, None)
        if perf_started_at is not None:
            print(f"[ChatPerf] total_ms={(time.perf_counter() - perf_started_at) * 1000.0:.2f}")
        elapsed_text = ""
        if started_at is not None:
            elapsed_text = f"（耗时 {time.time() - started_at:.2f}s）"

        plan = self.c.output_mode_service.build_output_plan(
            mode=self.c.current_output_mode,
            visible_text=envelope.final_text,
            tts_text=envelope.tts_text,
            elapsed_text=elapsed_text,
        )

        self.c.window.set_status(plan.status_text)

        if not tts_enabled:
            self.c._append_ai_text_only_message(plan.display_text or envelope.final_text)
            return

        if plan.append_text_message:
            self.c._append_ai_text_only_message(plan.display_text)
            return

        audio_widget = None
        if plan.append_audio_message:
            audio_widget = self.c._append_ai_audio_message_compat(plan.display_text)
            if audio_widget is not None:
                self.c._bind_audio_widget_actions(audio_widget)

        if plan.need_tts and plan.tts_text:
            tts_task_id = self.c._start_tts_request(plan.tts_text)
            if audio_widget is not None:
                self.c.pending_audio_widgets[tts_task_id] = audio_widget
            self.c.tts_task_sessions[tts_task_id] = self.c.session_service.current_id

    def _maybe_route_through_jiuchasi(
        self,
        *,
        text: str,
        actor_role: str,
        input_channel: str,
        desktop_route: dict[str, Any],
        puzzle: dict[str, Any],
        task_draft: dict[str, Any],
        understanding_packet: dict[str, Any],
    ) -> dict[str, Any] | None:
        try:
            return self.interaction_center.route_through_jiuchasi(
                text=text,
                actor_role=actor_role,
                input_channel=input_channel,
                desktop_route=desktop_route,
                task_draft=task_draft,
                understanding_packet=understanding_packet,
                project_root=self._project_root(),
                jiuchasi_enabled_fn=self._jiuchasi_enabled,
                allow_llm_reply_fn=self._jiuchasi_allow_llm_reply,
                allow_llm_thinking_fn=self._jiuchasi_allow_llm_thinking,
                dry_run_only_fn=self._jiuchasi_dry_run_only,
                target_from_task_draft_fn=self._jiuchasi_target_from_task_draft,
                apply_qin_task_patch_fn=self._apply_jiuchasi_qin_task_patch,
                result_to_safe_payload_fn=self._jiuchasi_result_to_safe_payload,
            )
        except Exception as exc:
            print(f"[JiuchasiBridge] interaction_center_failed error={exc!r}")

        # [FallbackOnly]
        # 主路径已迁入 LanguageInteractionCenter，本段仅作为异常回退保留。
        # 禁止在这里新增业务补丁。新增逻辑应进入 LanguageInteractionCenter 或对应 tianting 服务。
        if not self._jiuchasi_enabled():
            return None

        action = str(task_draft.get("action", "") or desktop_route.get("action_hint", "") or "").strip()

        # 桌面连接开关类动作先不交给纠察司，避免影响连接状态控制。
        if action.startswith("desktop.connection."):
            return None

        try:
            from services.desktop.tianting.jiuchasi.jiuchasi_service import JiuchasiService
            from services.desktop.qin.yushitai.report_writer import ReportWriter
            from services.desktop.qin.yushitai.runtime_material_writer import RuntimeMaterialWriter

            target_normalized = self._jiuchasi_target_from_task_draft(
                task_draft,
                understanding_packet=understanding_packet,
            )
            report_writer = ReportWriter(self._project_root())
            material_writer = RuntimeMaterialWriter(report_writer)

            service = JiuchasiService(
                project_root=self._project_root(),
                allow_llm_reply=self._jiuchasi_allow_llm_reply(),
                allow_llm_thinking=self._jiuchasi_allow_llm_thinking(),
                material_writer=material_writer,
                backend="host",
            )
            jiuchasi_needs: list[str] = []

            if action.startswith("folder.") or action.startswith("file."):
                jiuchasi_needs.append("file_roots")
                jiuchasi_needs.append("file_candidates")
            if action.startswith("app.") or action == "desktop.resolve":
                jiuchasi_needs.append("software_governance")

            if action == "desktop.resolve":
                jiuchasi_needs.append("file_roots")

            jiuchasi_needs = list(dict.fromkeys(jiuchasi_needs))
            result = service.handle(
                user_text=text,
                action_hint=action,
                target_normalized=target_normalized,
                route_hint={
                    **dict(desktop_route or {}),
                    "actor_role": actor_role,
                    "input_channel": input_channel,
                },
                understanding_packet=understanding_packet,
                original_task_draft=task_draft,
                needs=jiuchasi_needs,
            )

            patched_task_draft = self._apply_jiuchasi_qin_task_patch(
                task_draft,
                result.get("qin_task_patch", {}) if isinstance(result, dict) else {},
                jiuchasi_session_id=str((result or {}).get("session_id", "") or ""),
            )

            safe_payload = self._jiuchasi_result_to_safe_payload(
                user_text=text,
                jiuchasi_result=result,
                patched_task_draft=patched_task_draft,
            )

            print(
                "[JiuchasiBridge] "
                f"status={safe_payload.get('status', '')!r} "
                f"dry_run={self._jiuchasi_dry_run_only()} "
                f"session_id={str((result or {}).get('session_id', '') or '')!r}"
            )
            return safe_payload

        except Exception as exc:
            print(f"[JiuchasiBridge] failed error={exc}")
            return None

    # =========================
    # 聊天启动
    # =========================
    def start_chat_request(self, text: str, from_voice: bool = False):
        perf_start = time.perf_counter()
        text = text.strip()
        print(f"[ChatPerf] start text={text[:40]!r}")
        if not text:
            self.c.window.set_status(
                self._desktop_text(
                    "chat.input.empty",
                    user_text=text,
                    fallback="输入文本为空",
                )
            )
            return

        if self.c.chat_in_progress:
            self.c.window.set_status(
                self._desktop_text(
                    "chat.busy.in_progress",
                    user_text=text,
                    fallback="当前已有聊天请求正在处理中，请稍候...",
                )
            )
            return

        if self.c.chat_thread is not None and self.c.chat_thread.isRunning():
            self.c.window.set_status(
                self._desktop_text(
                    "chat.busy.thread_running",
                    user_text=text,
                    fallback="聊天线程仍在运行，请稍候...",
                )
            )
            return

        request_id = self.c._new_chat_request_id()
        self.c.request_start_times[request_id] = time.time()
        if not hasattr(self.c, "request_perf_start_times"):
            self.c.request_perf_start_times = {}
        self.c.request_perf_start_times[request_id] = perf_start

        t0 = time.perf_counter()
        classify_result = self.c.request_classifier_service.classify(text)
        print(f"[ChatPerf] request_classifier_ms={(time.perf_counter() - t0) * 1000.0:.2f}")

        t0 = time.perf_counter()
        try:
            desktop_route = self.interaction_center.route_desktop_command(
                text=text,
                from_voice=from_voice,
                classifier_result=classify_result,
                actor_role=self._get_desktop_actor_role(),
            )
        except Exception as exc:
            print(f"[DesktopRoute] interaction_center_failed error={exc!r}")
            desktop_route = self._detect_desktop_route(text, from_voice=from_voice, classifier_result=classify_result)
        try:
            desktop_route = self.interaction_center.route_pending_followup(
                text=text,
                desktop_route=desktop_route,
                from_voice=from_voice,
                actor_role=self._get_desktop_actor_role(),
            )
        except Exception as exc:
            print(f"[PendingFollowup] interaction_center_failed error={exc!r}")
            desktop_route = self._maybe_pending_followup_route(text, desktop_route, from_voice=from_voice)
        if str(desktop_route.get("route", "") or "") == "chat_reply":
            try:
                system_route = self.interaction_center.route_basic_system_skill(
                    text=text,
                    from_voice=from_voice,
                )
            except Exception as exc:
                print(f"[BasicSystemSkill] interaction_center_failed error={exc!r}")
                system_route = self._detect_basic_system_skill_route(text, from_voice=from_voice)
            if str((system_route or {}).get("route", "") or "") == "system_skill":
                desktop_route = system_route
        self._append_command_observation_card(text, desktop_route, from_voice=from_voice)
        detector_ms = (time.perf_counter() - t0) * 1000.0
        route = str(desktop_route.get("route", "") or "")
        print(f"[ChatPerf] desktop_detector_ms={detector_ms:.2f}")
        print(f"[ChatPerf] route={route}")

        if str(desktop_route.get("route", "") or "") != "chat_reply":
            print("[ChatPerf] check_model_ready_ms=skipped")
            print("[ChatRoute] direct route handled before ChatWorker")
            self.c.chat_in_progress = True
            self.c._set_busy(True)
            self.c.window.set_status(
                self._desktop_text(
                    "desktop.request.processing",
                    user_text=text,
                    fallback="正在处理桌面请求...",
                )
            )
            self._handle_desktop_route(request_id, text, desktop_route, from_voice=from_voice)
            return

        self.c.chat_in_progress = True
        t0 = time.perf_counter()
        ok, error_text = self.check_chat_model_ready()
        print(f"[ChatPerf] check_model_ready_ms={(time.perf_counter() - t0) * 1000.0:.2f}")
        if not ok:
            self.c.chat_in_progress = False
            self.c.request_start_times.pop(request_id, None)
            if hasattr(self.c, "request_perf_start_times"):
                self.c.request_perf_start_times.pop(request_id, None)
            self.c.window.set_status(error_text)
            QMessageBox.information(
                self.c.window,
                self._desktop_text("ui.messagebox.info_title", fallback="提示"),
                error_text,
            )
            return

        self.c._set_busy(True)

        if from_voice:
            self.c.window.set_status(
                self._desktop_text(
                    "chat.requesting_ai_after_voice",
                    user_text=text,
                    fallback="语音识别完成，正在请求 AI 回复...",
                )
            )
        else:
            self.c.window.set_status(
                self._desktop_text(
                    "chat.requesting_ai",
                    user_text=text,
                    fallback="正在请求 AI 回复...",
                )
            )

        stream_state = StreamReplyState(
            request_id=request_id,
            user_text=text,
            output_mode=self.c.current_output_mode,
        )
        stream_state.extra["perf_start"] = perf_start
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
                    self.c.window.update_ai_stream_status(
                        widget,
                        self._desktop_text(
                            "chat.stream.thinking",
                            user_text=text,
                            fallback="正在思考...",
                        ),
                    )

        current_model = self.c.model_router_service.get_current_chat_model()
        provider = current_model.get("provider", "ollama")
        model_name = current_model.get("model_name", OLLAMA_MODEL)
        host = current_model.get("host", OLLAMA_HOST)
        timeout = self.build_llm_timeout(current_model)
        request_options = self.build_llm_request_options(current_model)

        t0 = time.perf_counter()
        system_prompt = self.c.prompt_builder_service.build_system_prompt(
            user_text=text,
            prompt_mode=reply_profile.get("prompt_mode", "fast"),
            request_type=classify_result.request_type,
        )
        print(f"[ChatPerf] prompt_builder_ms={(time.perf_counter() - t0) * 1000.0:.2f}")

        self.log_llm_request(
            request_id=request_id,
            provider=provider,
            model_name=model_name,
            host=host,
            timeout=timeout,
            request_options=request_options,
            reply_profile=reply_profile,
        )

        t0 = time.perf_counter()
        print(f"[ChatRoute] request_id={request_id} creating ChatWorker")
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
        print(f"[ChatPerf] create_worker_ms={(time.perf_counter() - t0) * 1000.0:.2f}")

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

        t0 = time.perf_counter()
        self.c.chat_thread.start()
        print(f"[ChatPerf] chat_thread_start_ms={(time.perf_counter() - t0) * 1000.0:.2f}")

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
            perf_start = state.extra.get("perf_start")
            if perf_start is not None:
                print(f"[ChatPerf] first_chunk_ms={(time.perf_counter() - float(perf_start)) * 1000.0:.2f}")
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
            self.c.window.update_ai_stream_message(
                widget,
                self._desktop_text(
                    "chat.output.voice_only",
                    user_text=state.user_text,
                    fallback="（仅语音模式）",
                ),
            )
        else:
            self.c.window.update_ai_stream_message(widget, visible_text)

        if state.output_mode != "text_only":
            set_streaming = getattr(widget, "set_streaming", None)
            if callable(set_streaming):
                set_streaming()
            else:
                self.c.window.update_ai_stream_status(
                    widget,
                    self._desktop_text(
                        "chat.stream.generating",
                        user_text=state.user_text,
                        fallback="回复生成中...",
                    ),
                )

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

        reply_pipeline_started = time.perf_counter()
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
            ) or self._desktop_text(
                "chat.reply.extract_failed",
                user_text=user_text,
                fallback="抱歉，当前没有成功提取到最终回复。",
            )

        if not getattr(envelope, "tts_text", ""):
            envelope.tts_text = envelope.final_text or ""
        print(f"[ChatPerf] reply_pipeline_ms={(time.perf_counter() - reply_pipeline_started) * 1000.0:.2f}")
        print(f"[ChatPerf] final_text_len={len(envelope.final_text or '')}")
        print(f"[ChatPerf] tts_text_len={len(envelope.tts_text or '')}")

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
        perf_started_at = None
        if hasattr(self.c, "request_perf_start_times"):
            perf_started_at = self.c.request_perf_start_times.pop(request_id, None)
        if perf_started_at is not None:
            print(f"[ChatPerf] total_ms={(time.perf_counter() - perf_started_at) * 1000.0:.2f}")
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
                    self.c.window.update_ai_stream_status(
                        state.message_widget,
                        self._desktop_text(
                            "chat.tts.generating",
                            user_text=user_text,
                            fallback="语音生成中...",
                        ),
                    )
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
        if hasattr(self.c, "request_perf_start_times"):
            self.c.request_perf_start_times.pop(request_id, None)
        self.c.active_stream_states.pop(request_id, None)
        if started_at is not None:
            elapsed = time.time() - started_at
            print(f"[LLM] request_id={request_id} failed in {elapsed:.2f}s: {msg}")

        error_text = self._desktop_text(
            "chat.error.failed",
            {"error": msg},
            fallback=f"聊天失败：{msg}",
        )
        self.c.window.set_status(error_text)
        QMessageBox.critical(
            self.c.window,
            self._desktop_text("ui.messagebox.error_title", fallback="错误"),
            self._desktop_text(
                "chat.error.failed_multiline",
                {"error": msg},
                fallback=f"聊天失败：\n{msg}",
            ),
        )

    def trim_history(self):
        if len(self.c.chat_history) > MAX_HISTORY_MESSAGES:
            self.c.chat_history = self.c.chat_history[-MAX_HISTORY_MESSAGES:]



    
