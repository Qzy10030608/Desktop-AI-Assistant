"""LLM semantic fallback for read-only system skill routing.

The router only asks the model to produce a structured route. It must never
return factual answers such as the current date, time, or weather result.
"""

from __future__ import annotations

import json
import urllib.request
from typing import Any

from config import OLLAMA_HOST, OLLAMA_MODEL


ALLOWED_ACTIONS = {
    "system_info.read_datetime",
    "weather.read_current",
    "calendar.read_events",
    "chat_reply",
}
FORBIDDEN_KEYS = {
    "current_date",
    "current_time",
    "date_result",
    "time_result",
    "weekday_result",
    "weather_result",
    "weather",
    "temperature",
    "forecast",
    "file_path",
    "software_path",
    "backend",
    "permission",
    "executed",
}


class SystemSkillSemanticRouter:
    """Constrained semantic router for system skills."""

    def __init__(
        self,
        *,
        model_config: dict[str, Any] | None = None,
        timeout_seconds: float = 2.5,
        min_confidence: float = 0.72,
    ) -> None:
        self.model_config = dict(model_config or {})
        self.timeout_seconds = float(timeout_seconds)
        self.min_confidence = float(min_confidence)

    def route(self, text: str, *, from_voice: bool = False, locale: str = "zh-CN") -> dict[str, Any]:
        raw = str(text or "").strip()
        if not raw:
            return self._chat_reply("empty_text")
        local_route = self._local_semantic_route(raw, from_voice=from_voice, locale=locale)
        if local_route:
            return local_route
        if not self._could_be_system_skill(raw):
            return self._chat_reply("not_system_skill_candidate")

        model = self.model_config
        provider = str(model.get("provider", "ollama") or "ollama").strip().lower()
        if provider != "ollama":
            return self._chat_reply("unsupported_provider")

        model_name = str(model.get("model_name", OLLAMA_MODEL) or OLLAMA_MODEL).strip()
        host = str(model.get("host", OLLAMA_HOST) or OLLAMA_HOST).strip()
        if not model_name or not host:
            return self._chat_reply("missing_model_config")

        response_text = ""
        try:
            response_text = self._ollama_generate(
                prompt=self._build_prompt(raw),
                host=host,
                model_name=model_name,
            )
            parsed = self._parse_json(response_text)
            return self._normalize(parsed, raw_text=raw, from_voice=from_voice, locale=locale)
        except Exception as exc:
            return {
                "route": "chat_reply",
                "matched": False,
                "source": "system_skill_semantic_router",
                "reason": "semantic_router_failed",
                "error_kind": exc.__class__.__name__,
                "error": str(exc),
                "raw_response_head": response_text[:240],
                "model_name": model_name,
                "host": host,
                "timeout_seconds": self.timeout_seconds,
            }

    def _build_prompt(self, text: str) -> str:
        return f"""你是“系统能力路由器”，只能输出一个 JSON 对象。
你不能回答用户问题，不能输出当前日期、当前时间、天气结果。
你的任务只是判断用户是否需要调用系统能力。

允许的 route：
- system_skill
- chat_reply

允许的 action：
- system_info.read_datetime
- weather.read_current
- calendar.read_events
- chat_reply

如果用户在问：
- 现在几点、当前时间、几点了 → action=system_info.read_datetime, include_time=true
- 今天几号、今天是几号、今天几月几日、今天是什么日期 → action=system_info.read_datetime, include_date=true
- 今天星期几、今天周几、今天礼拜几 → action=system_info.read_datetime, include_weekday=true
- 天气怎么样、今天天气 → action=weather.read_current
- 日程、日历、今天安排 → action=calendar.read_events
如果是设计讨论、闲聊、普通问答 → route=chat_reply, action=chat_reply

只能输出以下 JSON 字段：
{{
  "route": "system_skill 或 chat_reply",
  "action": "system_info.read_datetime / weather.read_current / calendar.read_events / chat_reply",
  "confidence": 0.0到1.0,
  "arguments": {{
    "include_time": true/false,
    "include_date": true/false,
    "include_weekday": true/false
  }},
  "reason": "简短原因"
}}

用户输入：
{text}"""

    def _ollama_generate(self, *, prompt: str, host: str, model_name: str) -> str:
        url = host.rstrip("/") + "/api/generate"
        payload = {
            "model": model_name,
            "prompt": prompt,
            "stream": False,
            "format": "json",
            "options": {
                "temperature": 0.0,
                "top_p": 0.5,
                "num_predict": 96,
            },
        }
        data = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
            body = response.read().decode("utf-8", errors="replace")
        parsed = json.loads(body)
        return str(parsed.get("response", "") or "")

    def _parse_json(self, text: str) -> dict[str, Any]:
        raw = str(text or "").strip()
        if not raw:
            raise ValueError("empty_llm_response")
        try:
            value = json.loads(raw)
        except json.JSONDecodeError:
            start = raw.find("{")
            end = raw.rfind("}")
            if start < 0 or end <= start:
                raise
            value = json.loads(raw[start : end + 1])
        if not isinstance(value, dict):
            raise ValueError("llm_response_not_object")
        return value

    def _normalize(
        self,
        payload: dict[str, Any],
        *,
        raw_text: str,
        from_voice: bool,
        locale: str,
    ) -> dict[str, Any]:
        if self._contains_forbidden_key(payload):
            return self._chat_reply("forbidden_fact_field")

        route = str(payload.get("route", "") or "").strip()
        action = self._normalize_action(str(payload.get("action", "") or "").strip())
        confidence = self._float(payload.get("confidence"))
        arguments = payload.get("arguments", {}) if isinstance(payload.get("arguments"), dict) else {}
        reason = str(payload.get("reason", "") or "").strip()

        if route != "system_skill" or action == "chat_reply":
            return self._chat_reply(reason or "semantic_chat_reply")
        if action not in ALLOWED_ACTIONS or confidence < self.min_confidence:
            return self._chat_reply(reason or "semantic_low_confidence")

        safe_arguments = self._safe_arguments(action, arguments, locale=locale)
        return {
            "schema_version": "basic_system_skill_route_v1",
            "route": "system_skill",
            "matched": True,
            "raw_user_text": raw_text,
            "input_channel": "voice" if from_voice else "text",
            "locale": locale or "zh-CN",
            "skill": self._skill_for_action(action),
            "action": action,
            "reserved": action != "system_info.read_datetime",
            "matched_rules": ["system_skill.semantic_llm_fallback"],
            "message_key": self._message_key_for_action(action),
            "arguments": safe_arguments,
            "allow_direct_execution": False,
            "requires_qin_review": True,
            "confidence": confidence,
            "source": "system_skill_semantic_router",
            "reason": reason,
        }

    def _safe_arguments(self, action: str, arguments: dict[str, Any], *, locale: str) -> dict[str, Any]:
        used_locale = str(locale or "zh-CN")
        if action == "system_info.read_datetime":
            include_time = bool(arguments.get("include_time", False))
            include_date = bool(arguments.get("include_date", False))
            include_weekday = bool(arguments.get("include_weekday", False))
            if not (include_time or include_date or include_weekday):
                include_time = True
            return {
                "locale": used_locale,
                "include_time": include_time,
                "include_date": include_date,
                "include_weekday": include_weekday,
                "read_only": True,
                "risk_level": "low",
                "capability_group": "system_info",
            }
        return {
            "locale": used_locale,
            "read_only": True,
            "risk_level": "low_network" if action == "weather.read_current" else "personal_read",
            "capability_group": "system_info",
        }

    def _contains_forbidden_key(self, value: Any) -> bool:
        if isinstance(value, dict):
            for key, item in value.items():
                if str(key).strip().lower() in FORBIDDEN_KEYS:
                    return True
                if self._contains_forbidden_key(item):
                    return True
        elif isinstance(value, list):
            return any(self._contains_forbidden_key(item) for item in value)
        return False

    def _local_semantic_route(self, text: str, *, from_voice: bool, locale: str) -> dict[str, Any]:
        compact = self._compact(text)
        if not compact:
            return {}

        if self._has_any(compact, ("天气", "气温", "下雨", "降雨")):
            return self._system_skill(
                action="weather.read_current",
                raw_text=text,
                from_voice=from_voice,
                locale=locale,
                confidence=0.88,
                reason="local_semantic_weather",
                arguments={},
            )
        if self._has_any(compact, ("日程", "日历", "安排", "行程")):
            return self._system_skill(
                action="calendar.read_events",
                raw_text=text,
                from_voice=from_voice,
                locale=locale,
                confidence=0.86,
                reason="local_semantic_calendar",
                arguments={},
            )
        if self._has_any(compact, ("星期", "周几", "礼拜")):
            return self._system_skill(
                action="system_info.read_datetime",
                raw_text=text,
                from_voice=from_voice,
                locale=locale,
                confidence=0.92,
                reason="local_semantic_weekday",
                arguments={"include_weekday": True},
            )
        if self._has_any(compact, ("几号", "几月几日", "日期", "什么日子")):
            return self._system_skill(
                action="system_info.read_datetime",
                raw_text=text,
                from_voice=from_voice,
                locale=locale,
                confidence=0.92,
                reason="local_semantic_date",
                arguments={"include_date": True},
            )
        if self._has_any(compact, ("几点", "时间", "钟")) and self._has_any(compact, ("现在", "当前", "此刻", "几点")):
            return self._system_skill(
                action="system_info.read_datetime",
                raw_text=text,
                from_voice=from_voice,
                locale=locale,
                confidence=0.92,
                reason="local_semantic_time",
                arguments={"include_time": True},
            )
        return {}

    def _system_skill(
        self,
        *,
        action: str,
        raw_text: str,
        from_voice: bool,
        locale: str,
        confidence: float,
        reason: str,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "schema_version": "basic_system_skill_route_v1",
            "route": "system_skill",
            "matched": True,
            "raw_user_text": raw_text,
            "input_channel": "voice" if from_voice else "text",
            "locale": locale or "zh-CN",
            "skill": self._skill_for_action(action),
            "action": action,
            "reserved": action != "system_info.read_datetime",
            "matched_rules": ["system_skill.semantic_local_fallback"],
            "message_key": self._message_key_for_action(action),
            "arguments": self._safe_arguments(action, arguments, locale=locale),
            "allow_direct_execution": False,
            "requires_qin_review": True,
            "confidence": confidence,
            "source": "system_skill_semantic_router",
            "reason": reason,
        }

    def _could_be_system_skill(self, text: str) -> bool:
        compact = self._compact(text)
        if not compact:
            return False
        markers = (
            "现在",
            "当前",
            "几点",
            "时间",
            "今天",
            "几天",
            "几号",
            "几月",
            "日期",
            "星期",
            "周几",
            "礼拜",
            "天气",
            "日程",
            "日历",
            "安排",
        )
        return any(marker in compact for marker in markers)

    def _compact(self, text: str) -> str:
        return (
            str(text or "")
            .strip()
            .lower()
            .replace(" ", "")
            .replace("？", "")
            .replace("?", "")
            .replace("呀", "")
            .replace("啊", "")
            .replace("！", "")
            .replace("!", "")
            .replace("，", "")
            .replace(",", "")
        )

    def _has_any(self, text: str, markers: tuple[str, ...]) -> bool:
        return any(marker in text for marker in markers)

    def _skill_for_action(self, action: str) -> str:
        if action == "system_info.read_datetime":
            return "datetime"
        if action == "weather.read_current":
            return "weather"
        if action == "calendar.read_events":
            return "calendar"
        return ""

    def _message_key_for_action(self, action: str) -> str:
        if action == "system_info.read_datetime":
            return "desktop.system.datetime.done"
        if action == "weather.read_current":
            return "desktop.system.weather.not_configured"
        if action == "calendar.read_events":
            return "desktop.system.calendar.need_permission"
        return ""

    def _normalize_action(self, action: str) -> str:
        if action == "weather.open_display":
            return "weather.read_current"
        if action == "calendar.read":
            return "calendar.read_events"
        return action

    def _float(self, value: Any) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    def _chat_reply(self, reason: str) -> dict[str, Any]:
        return {
            "route": "chat_reply",
            "matched": False,
            "source": "system_skill_semantic_router",
            "reason": str(reason or ""),
        }
