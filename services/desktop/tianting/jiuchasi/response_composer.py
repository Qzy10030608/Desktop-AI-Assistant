from __future__ import annotations

import json
import urllib.request
from pathlib import Path
from typing import Any

from config import OLLAMA_HOST, OLLAMA_MODEL
from services.desktop.language.language_service import DesktopLanguageService


def _profile_locale(profile: Any) -> str:
    """
    兼容 DesktopLanguageService.profile_for_text() 返回对象或 dict 两种情况。

    注意：
    - 这个函数必须放在 class ResponseComposer 外面。
    - 不要缩进到类里面。
    - 否则 Pylance 会把它当成实例方法，提示缺少 self。
    """
    if isinstance(profile, dict):
        for key in ("locale", "locale_name", "language", "name"):
            value = str(profile.get(key, "") or "").strip()
            if value:
                return value
        return ""

    for key in ("locale", "locale_name", "language", "name"):
        value = str(getattr(profile, key, "") or "").strip()
        if value:
            return value

    return ""


class ResponseComposer:
    """
    天庭·纠察司：自然语言回复生成器。

    设计原则：
    - DecisionPolicy 只负责结构化判断。
    - ResponseComposer 才负责把 decision 转成人类可读文本。
    - 优先使用 LLM 进行自然、多语言表达。
    - LLM 失败时使用 DesktopLanguageService 的 reply 模板兜底。
    - 这里不执行桌面动作，不授予权限，不生成可执行参数。
    """

    def __init__(
        self,
        *,
        project_root: str | Path | None = None,
        ollama_host: str = "",
        model_name: str = "",
        timeout_seconds: float = 3.0,
        allow_llm: bool = True,
    ) -> None:
        self.project_root = Path(project_root or Path(__file__).resolve().parents[4]).expanduser().resolve()
        self.ollama_host = str(ollama_host or OLLAMA_HOST).rstrip("/")
        self.model_name = str(model_name or OLLAMA_MODEL).strip()
        self.timeout_seconds = max(1.0, float(timeout_seconds or 3.0))
        self.allow_llm = bool(allow_llm)
        self.language_service = DesktopLanguageService()

    def compose(
        self,
        *,
        decision: dict[str, Any],
        user_text: str = "",
        locale: str = "",
    ) -> dict[str, Any]:
        if not isinstance(decision, dict):
            decision = {}

        profile = self.language_service.profile_for_text(user_text or decision.get("user_text", "") or "")
        locale_name = str(locale or _profile_locale(profile) or "zh-CN")

        message = decision.get("message", {})
        if not isinstance(message, dict):
            message = {}

        message_key = str(message.get("key", "") or decision.get("message_key", "") or "")
        message_intent = str(message.get("intent", "") or decision.get("message_intent", "") or "")

        slots = message.get("slots", {})
        if not isinstance(slots, dict):
            slots = {}

        allow_llm_rewrite = bool(message.get("allow_llm_rewrite", True))

        fallback_text = self._fallback_text(
            profile=profile,
            message_key=message_key,
            slots=slots,
            decision=decision,
        )

        if self.allow_llm and allow_llm_rewrite:
            llm_text = self._compose_by_llm(
                locale=locale_name,
                user_text=user_text,
                decision=decision,
                message_intent=message_intent,
                message_key=message_key,
                slots=slots,
                fallback_text=fallback_text,
            )
            if llm_text:
                return {
                    "ok": True,
                    "source": "llm_composed",
                    "locale": locale_name,
                    "visible_text": llm_text,
                    "fallback_text": fallback_text,
                    "message_key": message_key,
                    "message_intent": message_intent,
                }

        last_resort_text = self._last_resort_text(locale_name)

        return {
            "ok": bool(fallback_text or last_resort_text),
            "source": "language_template_fallback",
            "locale": locale_name,
            "visible_text": fallback_text or last_resort_text,
            "fallback_text": fallback_text,
            "message_key": message_key,
            "message_intent": message_intent,
        }

    def _fallback_text(
        self,
        *,
        profile: Any,
        message_key: str,
        slots: dict[str, Any],
        decision: dict[str, Any],
    ) -> str:
        if message_key:
            try:
                return str(self.language_service.render(profile, message_key, slots) or "").strip()
            except Exception:
                pass

        status = str(decision.get("status", "") or "")
        generic_key = {
            "need_confirmation": "desktop.generic.need_confirmation",
            "need_clarification": "desktop.generic.need_clarification",
            "multiple_candidates": "desktop.generic.pending_choice",
            "chat_reply": "desktop.generic.unknown",
            "ready_for_qin": "desktop.generic.candidate_ready",
            "deny": "desktop.generic.blocked",
        }.get(status, "desktop.generic.unknown")

        try:
            return str(self.language_service.render(profile, generic_key, slots) or "").strip()
        except Exception:
            return ""

    def _last_resort_text(self, locale: str) -> str:
        normalized = str(locale or "").strip().lower()

        if normalized.startswith("ja"):
            return "続行する前に、もう少し確認が必要です。"

        if normalized.startswith("en"):
            return "I need one more detail before continuing."

        return "我需要再确认一下才能继续。"

    def _compose_by_llm(
        self,
        *,
        locale: str,
        user_text: str,
        decision: dict[str, Any],
        message_intent: str,
        message_key: str,
        slots: dict[str, Any],
        fallback_text: str,
    ) -> str:
        try:
            prompt = self._prompt(
                locale=locale,
                user_text=user_text,
                decision=decision,
                message_intent=message_intent,
                message_key=message_key,
                slots=slots,
                fallback_text=fallback_text,
            )
            raw = self._ollama_generate(prompt)
            parsed = self._parse_response(raw)
            text = str(parsed.get("visible_text", "") or "").strip()
            return self._sanitize_visible_text(text)
        except Exception:
            return ""

    def _prompt(
        self,
        *,
        locale: str,
        user_text: str,
        decision: dict[str, Any],
        message_intent: str,
        message_key: str,
        slots: dict[str, Any],
        fallback_text: str,
    ) -> str:
        safe_decision = {
            "status": decision.get("status", ""),
            "reason": decision.get("reason", ""),
            "message_intent": message_intent,
            "message_key": message_key,
            "slots": slots,
            "candidates": decision.get("candidates", []),
            "direct_execution_allowed": False,
        }

        return (
            "You are a desktop assistant response composer.\n"
            "Generate one short natural user-facing sentence.\n"
            "Do not claim the action has been executed unless the decision status says it is done.\n"
            "Do not mention internal modules such as Qin, Jiuchasi, ReviewGate, adapter, backend, evidence broker.\n"
            "Do not invent paths, permissions, process names, or software names.\n"
            "Use the same language as locale.\n"
            "Return compact JSON only: {\"visible_text\":\"...\"}\n\n"
            f"locale: {locale}\n"
            f"user_text: {user_text}\n"
            f"decision: {json.dumps(safe_decision, ensure_ascii=False)}\n"
            f"fallback_text: {fallback_text}\n"
        )

    def _ollama_generate(self, prompt: str) -> str:
        url = f"{self.ollama_host}/api/generate"
        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.2,
                "num_predict": 80,
            },
        }

        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
            body = response.read().decode("utf-8", errors="replace")

        result = json.loads(body)
        return str(result.get("response", "") or "")

    def _parse_response(self, text: str) -> dict[str, Any]:
        raw = str(text or "").strip()
        if not raw:
            return {}

        start = raw.find("{")
        end = raw.rfind("}")
        if start >= 0 and end > start:
            raw = raw[start:end + 1]

        data = json.loads(raw)
        return data if isinstance(data, dict) else {}

    def _sanitize_visible_text(self, text: str) -> str:
        value = str(text or "").strip()
        if not value:
            return ""

        forbidden = [
            "Qin",
            "ReviewGate",
            "Jiuchasi",
            "EvidenceBroker",
            "adapter",
            "backend",
            "HostAdapter",
            "纠察司",
            "秦链",
            "证据中介",
        ]

        for word in forbidden:
            value = value.replace(word, "")

        value = " ".join(value.split())
        return value[:240]