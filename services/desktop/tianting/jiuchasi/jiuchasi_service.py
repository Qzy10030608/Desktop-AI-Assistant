from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from services.desktop.tianting.jiuchasi.thinking_session_cache import ThinkingSessionCache
from services.desktop.tianting.jiuchasi.evidence_broker import EvidenceBroker
from services.desktop.tianting.jiuchasi.llm_thinking_orchestrator import LLMThinkingOrchestrator
from services.desktop.tianting.jiuchasi.desktop_decision_policy import DesktopDecisionPolicy
from services.desktop.tianting.jiuchasi.response_composer import ResponseComposer
from services.desktop.qin.yushitai.report_writer import ReportWriter
from services.desktop.qin.yushitai.runtime_material_writer import RuntimeMaterialWriter


JIUCHASI_SERVICE_SCHEMA_VERSION = "jiuchasi_service_result_v1"


class JiuchasiService:
    """
    天庭·纠察司：总入口服务。

    职责：
    1. 创建 thinking session
    2. 查询 evidence
    3. 调用 LLMThinkingOrchestrator
    4. 调用 DesktopDecisionPolicy
    5. 调用 ResponseComposer
    6. 写回 thinking session
    7. 返回统一结果

    重要原则：
    - 不执行真实桌面动作。
    - 不授予权限。
    - 不绕过 QinRuntimeService / ReviewGate。
    - ready_for_qin 也只是“准备交给秦链”，不是执行。
    """

    def __init__(
        self,
        project_root: str | Path | None = None,
        *,
        ttl_seconds: int = 120,
        allow_llm_reply: bool = True,
        allow_llm_thinking: bool = True,
        material_writer: Any | None = None,
        backend: str = "host",
    ) -> None:
        self.project_root = Path(project_root or Path(__file__).resolve().parents[4]).expanduser().resolve()
        self.allow_llm_reply = bool(allow_llm_reply)
        self.allow_llm_thinking = bool(allow_llm_thinking)
        self.backend = str(backend or "host").strip().lower() or "host"
        self.material_writer = material_writer
        if self.material_writer is None:
            try:
                self.material_writer = RuntimeMaterialWriter(ReportWriter(self.project_root))
            except Exception:
                self.material_writer = None

        self.session_cache = ThinkingSessionCache(
            project_root=self.project_root,
            ttl_seconds=ttl_seconds,
            material_writer=self.material_writer,
            backend=self.backend,
        )
        self.evidence_broker = EvidenceBroker(project_root=self.project_root)
        self.llm_orchestrator = LLMThinkingOrchestrator(project_root=self.project_root)
        self.decision_policy = DesktopDecisionPolicy(project_root=self.project_root)

    def handle(
        self,
        *,
        user_text: str,
        action_hint: str = "",
        target_normalized: str = "",
        route_hint: dict[str, Any] | None = None,
        understanding_packet: dict[str, Any] | None = None,
        original_task_draft: dict[str, Any] | None = None,
        needs: list[str] | None = None,
        locale: str = "",
        llm_thinking_override: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        处理一次桌面理解请求。

        参数说明：
        - user_text：用户原始输入
        - action_hint：旧链路或初判给出的动作，例如 app.launch / folder.open
        - target_normalized：旧链路或初判提取出的目标文本
        - route_hint：路由层信息，可为空
        - understanding_packet：已有理解材料，可为空
        - original_task_draft：已有 task 草案，可为空
        - needs：指定要查询哪些 evidence provider；为空则 EvidenceBroker 自行推断
        - locale：指定语言；为空则 ResponseComposer 自行判断
        - llm_thinking_override：测试用，可以绕过真实 LLMThinking
        """
        user_text = str(user_text or "").strip()
        action_hint = str(action_hint or "").strip()
        target_normalized = str(target_normalized or "").strip()

        route_hint = route_hint if isinstance(route_hint, dict) else {}
        understanding_packet = understanding_packet if isinstance(understanding_packet, dict) else {}
        original_task_draft = original_task_draft if isinstance(original_task_draft, dict) else {}

        session = self.session_cache.create_session(
            user_text=user_text,
            route_hint=route_hint,
            understanding_packet=understanding_packet,
            metadata={
                "source": "jiuchasi_service",
                "action_hint": action_hint,
                "target_normalized": target_normalized,
            },
        )
        session_id = str(session.get("session_id", "") or "")

        self.session_cache.append_step(
            session_id,
            stage="session_created",
            payload={
                "action_hint": action_hint,
                "target_normalized": target_normalized,
            },
        )

        try:
            evidence_packet = self.evidence_broker.collect(
                user_text=user_text,
                action_hint=action_hint,
                target_normalized=target_normalized,
                needs=needs,
            )
            self.session_cache.append_step(
                session_id,
                stage="evidence_collected",
                payload={
                    "needs": evidence_packet.get("needs", []),
                    "provider_keys": list((evidence_packet.get("providers", {}) or {}).keys()),
                },
            )

            if isinstance(llm_thinking_override, dict):
                llm_thinking = llm_thinking_override
                self.session_cache.append_step(
                    session_id,
                    stage="llm_thinking_overridden",
                    payload={
                        "reason": "test_override",
                    },
                )
            elif self.allow_llm_thinking:
                llm_thinking = self.llm_orchestrator.think(
                    user_text=user_text,
                    action_hint=action_hint,
                    target_normalized=target_normalized,
                    understanding_packet=understanding_packet,
                    evidence_packet=evidence_packet,
                )
                self.session_cache.append_step(
                    session_id,
                    stage="llm_thinking_done",
                    payload={
                        "ok": llm_thinking.get("ok", False),
                        "has_target_hint": bool(
                            isinstance(llm_thinking.get("llm_target_hint", {}), dict)
                            and llm_thinking.get("llm_target_hint", {}).get("target_label_hint")
                        ),
                    },
                )
            else:
                llm_thinking = {
                    "schema_version": "jiuchasi_llm_thinking_v1",
                    "created_at_ts": int(time.time()),
                    "ok": True,
                    "user_text": user_text,
                    "action_hint": action_hint,
                    "target_normalized": target_normalized,
                    "llm_target_hint": {},
                    "notes": ["llm_thinking_disabled"],
                }
                self.session_cache.append_step(
                    session_id,
                    stage="llm_thinking_skipped",
                    payload={
                        "reason": "allow_llm_thinking_false",
                    },
                )

            decision = self.decision_policy.decide(
                user_text=user_text,
                action_hint=action_hint,
                target_normalized=target_normalized,
                evidence_packet=evidence_packet,
                llm_thinking=llm_thinking,
                original_task_draft=original_task_draft,
            )
            self.session_cache.append_step(
                session_id,
                stage="decision_done",
                payload={
                    "status": decision.get("status", ""),
                    "reason": decision.get("reason", ""),
                    "message_key": decision.get("message_key", ""),
                    "direct_execution_allowed": decision.get("direct_execution_allowed", False),
                },
            )

            response = ResponseComposer(
                project_root=self.project_root,
                allow_llm=self.allow_llm_reply,
            ).compose(
                decision=decision,
                user_text=user_text,
                locale=locale,
            )
            self.session_cache.append_step(
                session_id,
                stage="response_composed",
                payload={
                    "source": response.get("source", ""),
                    "message_key": response.get("message_key", ""),
                    "locale": response.get("locale", ""),
                },
            )

            self.session_cache.update_session(
                session_id,
                evidence=evidence_packet,
                llm_thinking=llm_thinking,
                decision=decision,
                pending_question=decision.get("pending_question", {}),
                response=response,
            )
            self._append_decision_summary(
                session_id=session_id,
                user_text=user_text,
                action_hint=action_hint,
                target_normalized=target_normalized,
                decision=decision,
                response=response,
            )

            return {
                "schema_version": JIUCHASI_SERVICE_SCHEMA_VERSION,
                "ok": True,
                "session_id": session_id,
                "user_text": user_text,
                "action_hint": action_hint,
                "target_normalized": target_normalized,
                "evidence": evidence_packet,
                "llm_thinking": llm_thinking,
                "decision": decision,
                "response": response,
                "visible_text": str(response.get("visible_text", "") or ""),
                "status": str(decision.get("status", "") or ""),
                "qin_task_patch": decision.get("qin_task_patch", {}),
                "pending_question": decision.get("pending_question", {}),
                "candidates": decision.get("candidates", []),
                "direct_execution_allowed": False,
            }

        except Exception as exc:
            error_decision = {
                "schema_version": "jiuchasi_desktop_decision_v2",
                "created_at_ts": int(time.time()),
                "status": "need_clarification",
                "reason": "jiuchasi_service_failed",
                "message": {
                    "intent": "jiuchasi_service_failed",
                    "key": "desktop.generic.need_clarification",
                    "slots": {},
                    "allow_llm_rewrite": False,
                },
                "message_intent": "jiuchasi_service_failed",
                "message_key": "desktop.generic.need_clarification",
                "message_slots": {},
                "qin_task_patch": {},
                "pending_question": {},
                "candidates": [],
                "evidence_refs": {},
                "direct_execution_allowed": False,
                "safe_user_message": "",
            }

            response = ResponseComposer(
                project_root=self.project_root,
                allow_llm=False,
            ).compose(
                decision=error_decision,
                user_text=user_text,
                locale=locale,
            )

            self.session_cache.update_session(
                session_id,
                status="error",
                decision=error_decision,
                response=response,
                metadata={
                    "source": "jiuchasi_service",
                    "error_kind": exc.__class__.__name__,
                    "error": str(exc),
                },
            )
            self._append_decision_summary(
                session_id=session_id,
                user_text=user_text,
                action_hint=action_hint,
                target_normalized=target_normalized,
                decision=error_decision,
                response=response,
                status="error",
            )

            return {
                "schema_version": JIUCHASI_SERVICE_SCHEMA_VERSION,
                "ok": False,
                "session_id": session_id,
                "user_text": user_text,
                "action_hint": action_hint,
                "target_normalized": target_normalized,
                "status": "need_clarification",
                "decision": error_decision,
                "response": response,
                "visible_text": str(response.get("visible_text", "") or ""),
                "qin_task_patch": {},
                "pending_question": {},
                "candidates": [],
                "direct_execution_allowed": False,
                "error_kind": exc.__class__.__name__,
                "error": str(exc),
            }

    def _append_decision_summary(
        self,
        *,
        session_id: str,
        user_text: str,
        action_hint: str,
        target_normalized: str,
        decision: dict[str, Any],
        response: dict[str, Any] | None = None,
        status: str = "",
    ) -> None:
        if self.material_writer is None or not session_id:
            return
        if not isinstance(decision, dict):
            return

        qin_patch = decision.get("qin_task_patch", {})
        qin_patch = qin_patch if isinstance(qin_patch, dict) else {}
        target = qin_patch.get("target")
        target = target if isinstance(target, dict) else {}
        message = decision.get("message")
        message = message if isinstance(message, dict) else {}
        response = response if isinstance(response, dict) else {}

        target_label_hint = (
            qin_patch.get("target_label_hint")
            or target.get("label_hint")
            or target.get("name_hint")
            or target.get("app_hint")
            or qin_patch.get("target")
            or target_normalized
        )

        summary = {
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "session_id": session_id,
            "user_text": user_text,
            "action_hint": action_hint,
            "action": qin_patch.get("action") or action_hint,
            "target_normalized": target_normalized,
            "target_label_hint": str(target_label_hint or ""),
            "status": status or str(decision.get("status", "") or ""),
            "reason": str(decision.get("reason", "") or ""),
            "message_key": str(decision.get("message_key") or message.get("key") or response.get("message_key") or ""),
            "message_intent": str(decision.get("message_intent") or message.get("intent") or ""),
            "session_path": self.session_cache.session_path_for(session_id),
        }

        try:
            self.material_writer.append_jiuchasi_decision(summary, backend=self.backend)
        except Exception:
            return


def handle_by_jiuchasi(**kwargs: Any) -> dict[str, Any]:
    return JiuchasiService(
        project_root=kwargs.pop("project_root", None),
        allow_llm_reply=kwargs.pop("allow_llm_reply", True),
        allow_llm_thinking=kwargs.pop("allow_llm_thinking", True),
        backend=kwargs.pop("backend", "host"),
    ).handle(**kwargs)
