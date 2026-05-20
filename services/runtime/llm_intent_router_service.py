from __future__ import annotations

import json
import re
import urllib.request
from dataclasses import dataclass
from typing import Any


DEFAULT_OLLAMA_HOST = "http://localhost:11434"


@dataclass
class LLMIntentRouterConfig:
    enabled: bool = True
    timeout_seconds: float = 20.0
    max_tokens: int = 256
    temperature: float = 0.1
    top_p: float = 0.8


class LLMIntentRouterService:
    """
    LLM 意图路由层。

    只负责把自然语言转成结构化 route。
    不负责执行，不直接回答时间/天气，不打开软件，不读取文件。
    模型名不写死，优先从当前聊天模型 model_config 读取。
    """

    def __init__(self, config: LLMIntentRouterConfig | None = None) -> None:
        self.config = config or LLMIntentRouterConfig()

    def route(
        self,
        user_text: str,
        *,
        locale: str = "zh-CN",
        model_config: dict[str, Any] | None = None,
        router_profile: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        text = str(user_text or "").strip()
        if not text:
            return self._empty("empty_text")

        fast = self._fast_route(text)
        fast_confidence = float(fast.get("confidence", 0.0) or 0.0)

        if fast.get("ok") and (
            fast_confidence >= 0.95
            or (
                fast.get("route") == "system_skill"
                and fast.get("skill") == "weather.open_display"
                and fast_confidence >= 0.88
            )
        ):
            return fast

        if not self.config.enabled:
            return self._chat_reply("router_disabled")

        model = model_config if isinstance(model_config, dict) else {}
        provider = str(model.get("provider", "ollama") or "ollama").strip().lower()
        model_name = str(model.get("model_name", "") or "").strip()
        host = str(model.get("host", DEFAULT_OLLAMA_HOST) or DEFAULT_OLLAMA_HOST).strip()

        if provider != "ollama":
            return self._chat_reply("unsupported_router_provider")

        if not model_name:
            return self._chat_reply("missing_current_model_name")

        prompt = self._build_prompt(
            text=text,
            locale=locale,
            router_profile=router_profile if isinstance(router_profile, dict) else {},
        )

        response_text = ""
        try:
            response_text = self._ollama_generate(
                prompt=prompt,
                host=host,
                model_name=model_name,
            )
            parsed = self._parse_json(response_text)
            return self._normalize(parsed, raw_response=response_text)
        except Exception as exc:
            return {
                "schema_version": "llm_intent_route_v1",
                "ok": False,
                "source": "ollama_intent_router",
                "route": "chat_reply",
                "skill": "",
                "action_hint": "",
                "target_normalized": "",
                "arguments": {},
                "confidence": 0.0,
                "reason": "llm_intent_router_failed",
                "error_kind": exc.__class__.__name__,
                "error": str(exc),
                "raw_response_head": response_text[:240],
            }

    def _fast_route(self, text: str) -> dict[str, Any]:
        compact = self._compact(text)

        # 这里只保留极少数明确请求。复杂说法交给 LLM。
        if compact in {"现在几点", "几点了", "当前时间"}:
            return self._system_skill(
                skill="datetime.read",
                arguments={
                    "need_time": True,
                    "need_date": False,
                    "need_weekday": False,
                },
                confidence=0.98,
                reason="fast_exact_time_query",
            )

        if compact in {"今天几号", "今天日期", "现在日期"}:
            return self._system_skill(
                skill="datetime.read",
                arguments={
                    "need_time": False,
                    "need_date": True,
                    "need_weekday": False,
                },
                confidence=0.98,
                reason="fast_exact_date_query",
            )

        if compact in {"星期几", "今天星期几", "周几", "今天周几", "礼拜几", "今天礼拜几"}:
            return self._system_skill(
                skill="datetime.read",
                arguments={
                    "need_time": False,
                    "need_date": False,
                    "need_weekday": True,
                },
                confidence=0.98,
                reason="fast_exact_weekday_query",
            )
        
        if self._looks_like_weather_request(compact):
            return self._system_skill(
                skill="weather.open_display",
                arguments={
                    "location": "current",
                    "date": "today",
                    "need": ["weather_display"],
                },
                confidence=0.90,
                reason="fast_weather_display_fallback",
            )

        return self._empty("no_fast_route")
    
    def _looks_like_weather_request(self, compact: str) -> bool:
        value = str(compact or "")
        if not value:
            return False

        weather_marks = (
            "天气",
            "下雨",
            "雨",
            "带伞",
            "伞",
            "冷不冷",
            "热不热",
            "温度",
            "气温",
            "风大",
            "出门",
        )

        return any(mark in value for mark in weather_marks)

    def _build_prompt(
        self,
        *,
        text: str,
        locale: str,
        router_profile: dict[str, Any],
    ) -> str:
        allowed_routes = router_profile.get("allowed_routes") or [
            "system_skill",
            "desktop_command",
            "chat_reply",
        ]
        allowed_system_skills = router_profile.get("allowed_system_skills") or [
            "datetime.read",
            "weather.open_display",
            "weather.query",
            "calendar.read",
        ]
        allowed_desktop_actions = router_profile.get("allowed_desktop_actions") or [
            "app.launch",
            "app.close",
            "folder.open",
            "file.open",
            "desktop.resolve",
        ]
        prompt_rules = router_profile.get("prompt_rules") or [
            "你是意图路由器，不是执行器。",
            "你只能判断用户意图，并输出 JSON。",
            "你不能直接回答当前时间、日期、天气、文件路径或软件路径。",
            "当前时间必须由系统读取。",
            "天气必须由天气页面或天气数据源读取。",
            "软件、文件、文件夹必须由记忆、治理区和证据层确认。",
            "如果用户说法不规范，也要尽量理解其意图。",
            "如果无法确定目标类型，使用 desktop.resolve。",
            "如果只是聊天、计算、写作或解释，使用 chat_reply。",
            "不要输出 Markdown，不要输出解释，只输出 JSON。",
        ]

        return f"""
你是桌面 AI 的意图路由器。你不是聊天助手，也不是执行器。

允许 route:
{json.dumps(allowed_routes, ensure_ascii=False)}

允许 system_skill:
{json.dumps(allowed_system_skills, ensure_ascii=False)}

允许 desktop action_hint:
{json.dumps(allowed_desktop_actions, ensure_ascii=False)}

规则:
{json.dumps(prompt_rules, ensure_ascii=False, indent=2)}

判断原则:
- 用户询问当前时间、日期、星期：route=system_skill, skill=datetime.read。
- 用户询问天气、下雨、冷不冷、热不热、要不要带伞：route=system_skill。
- 当前天气数据源未配置时，优先 skill=weather.open_display。
- 用户要求打开软件、关闭软件、打开文件、打开文件夹：route=desktop_command。
- 用户只是聊天、解释、计算、写作、讨论：route=chat_reply。
- target_normalized 只保留用户真正想操作的目标名，例如“微信”“英雄联盟”“个人AI设计”。
- 不要输出 exe_path、process_name、backend、permission_state、os_command。
- 不要直接回答事实，只输出 JSON。

输出 JSON 格式:
{{
  "schema_version": "llm_intent_route_v1",
  "route": "system_skill | desktop_command | chat_reply",
  "skill": "",
  "action_hint": "",
  "target_normalized": "",
  "arguments": {{}},
  "confidence": 0.0,
  "reason": ""
}}

用户语言: {locale}
用户输入: {text}
""".strip()

    def _ollama_generate(self, *, prompt: str, host: str, model_name: str) -> str:
        url = host.rstrip("/") + "/api/generate"
        payload = {
            "model": model_name,
            "prompt": prompt,
            "stream": False,
            "format": "json",
            "options": {
                "temperature": self.config.temperature,
                "top_p": self.config.top_p,
                "num_predict": self.config.max_tokens,
            },
        }

        req = urllib.request.Request(
            url,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        with urllib.request.urlopen(req, timeout=self.config.timeout_seconds) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="ignore"))
            return str(data.get("response", "") or "")

    def _parse_json(self, raw: str) -> dict[str, Any]:
        text = str(raw or "").strip()
        if not text:
            return {}

        try:
            data = json.loads(text)
            return data if isinstance(data, dict) else {}
        except Exception:
            pass

        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if not match:
            return {}

        data = json.loads(match.group(0))
        return data if isinstance(data, dict) else {}

    def _normalize(self, parsed: dict[str, Any], *, raw_response: str) -> dict[str, Any]:
        route = str(parsed.get("route", "") or "").strip()
        skill = str(parsed.get("skill", "") or "").strip()
        action_hint = str(parsed.get("action_hint", "") or "").strip()
        target_normalized = str(parsed.get("target_normalized", "") or "").strip()
        reason = str(parsed.get("reason", "") or "").strip()

        arguments = parsed.get("arguments", {})
        if not isinstance(arguments, dict):
            arguments = {}

        confidence = self._safe_float(parsed.get("confidence", 0.0), default=0.0)
        confidence = max(0.0, min(1.0, confidence))

        allowed_routes = {"system_skill", "desktop_command", "chat_reply"}
        allowed_skills = {
            "datetime.read",
            "weather.open_display",
            "weather.query",
            "calendar.read",
        }
        allowed_actions = {
            "app.launch",
            "app.close",
            "folder.open",
            "file.open",
            "desktop.resolve",
        }

        if route not in allowed_routes:
            route = "chat_reply"
            skill = ""
            action_hint = ""
            target_normalized = ""
            confidence = min(confidence, 0.3)
            reason = reason or "invalid_route_fallback"

        if route == "system_skill":
            action_hint = ""
            target_normalized = ""

            if skill not in allowed_skills:
                route = "chat_reply"
                skill = ""
                confidence = min(confidence, 0.3)
                reason = reason or "invalid_skill_fallback"

            # 当前还没有真实天气 API，LLM 即使识别成 weather.query，
            # 也先降级为打开天气页面，避免系统假装能读取真实天气。
            elif skill == "weather.query":
                skill = "weather.open_display"
                arguments.setdefault("location", "current")
                arguments.setdefault("need", ["weather_display"])
                reason = reason or "weather_query_downgraded_to_open_display"

        elif route == "desktop_command":
            skill = ""
            if action_hint not in allowed_actions:
                action_hint = "desktop.resolve"

        elif route == "chat_reply":
            skill = ""
            action_hint = ""
            target_normalized = ""

        return {
            "schema_version": "llm_intent_route_v1",
            "ok": True,
            "source": "ollama_intent_router",
            "route": route,
            "skill": skill,
            "action_hint": action_hint,
            "target_normalized": target_normalized,
            "arguments": arguments,
            "confidence": confidence,
            "reason": reason or "llm_intent_route",
            "raw_response_head": raw_response[:240],
        }

    def _system_skill(
        self,
        *,
        skill: str,
        arguments: dict[str, Any],
        confidence: float,
        reason: str,
    ) -> dict[str, Any]:
        return {
            "schema_version": "llm_intent_route_v1",
            "ok": True,
            "source": "fast_intent_router",
            "route": "system_skill",
            "skill": skill,
            "action_hint": "",
            "target_normalized": "",
            "arguments": arguments,
            "confidence": confidence,
            "reason": reason,
        }

    def _chat_reply(self, reason: str) -> dict[str, Any]:
        return {
            "schema_version": "llm_intent_route_v1",
            "ok": True,
            "source": "intent_router",
            "route": "chat_reply",
            "skill": "",
            "action_hint": "",
            "target_normalized": "",
            "arguments": {},
            "confidence": 0.0,
            "reason": reason,
        }

    def _empty(self, reason: str) -> dict[str, Any]:
        return {
            "schema_version": "llm_intent_route_v1",
            "ok": False,
            "source": "intent_router",
            "route": "",
            "skill": "",
            "action_hint": "",
            "target_normalized": "",
            "arguments": {},
            "confidence": 0.0,
            "reason": reason,
        }

    def _compact(self, text: str) -> str:
        return re.sub(r"[\s　，,。.!！?？：:；;、]+", "", str(text or "").strip().lower())

    def _safe_float(self, value: Any, *, default: float = 0.0) -> float:
        try:
            return float(value)
        except Exception:
            return default


def route_user_intent(
    user_text: str,
    *,
    locale: str = "zh-CN",
    model_config: dict[str, Any] | None = None,
    router_profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return LLMIntentRouterService().route(
        user_text,
        locale=locale,
        model_config=model_config,
        router_profile=router_profile,
    )