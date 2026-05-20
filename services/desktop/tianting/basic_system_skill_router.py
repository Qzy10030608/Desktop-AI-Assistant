from __future__ import annotations

from typing import Any
import re
from services.desktop.language.language_service import DesktopLanguageService

SYSTEM_SKILL_ROUTE_SCHEMA = "basic_system_skill_route_v1"


class BasicSystemSkillRouter:
    """Lightweight router for read-only system skill intents.

    This module only emits structured intent. It does not answer directly,
    call providers, or bypass Qin review.
    """

    def __init__(self, language_service: DesktopLanguageService | None = None) -> None:
        self.language_service = language_service or DesktopLanguageService()

    def route(self, text: str, *, locale: str = "", input_channel: str = "text") -> dict[str, Any]:
        raw = str(text or "").strip()
        profile = self.language_service.load_profile(locale) if locale else self.language_service.profile_for_text(raw)
        used_locale = str(profile.get("locale", locale or "zh-CN") or "zh-CN")

        datetime_match = self._match_datetime(raw, profile)
        if datetime_match:
            include_time = "system_skill.datetime.time_queries" in datetime_match
            include_date = "system_skill.datetime.date_queries" in datetime_match
            include_weekday = "system_skill.datetime.weekday_queries" in datetime_match
            return self._decision(
                raw,
                used_locale,
                input_channel,
                "system_info.read_datetime",
                "datetime",
                matched_rules=datetime_match,
                message_key="desktop.system.datetime.done",
                arguments={
                    "locale": used_locale,
                    "include_time": include_time or not (include_date or include_weekday),
                    "include_date": include_date,
                    "include_weekday": include_weekday,
                    "read_only": True,
                    "risk_level": "low",
                    "capability_group": "system_info",
                },
            )

        if self._contains_any(raw, profile, "system_skill.weather.queries"):
            return self._decision(
                raw,
                used_locale,
                input_channel,
                "weather.read_current",
                "weather",
                matched_rules=["system_skill.weather.queries"],
                reserved=True,
                message_key="desktop.system.weather.not_configured",
                arguments={
                    "locale": used_locale,
                    "read_only": True,
                    "risk_level": "low_network",
                    "capability_group": "system_info",
                },
            )

        if self._contains_any(raw, profile, "system_skill.calendar.queries"):
            return self._decision(
                raw,
                used_locale,
                input_channel,
                "calendar.read_events",
                "calendar",
                matched_rules=["system_skill.calendar.queries"],
                reserved=True,
                message_key="desktop.system.calendar.need_permission",
                arguments={
                    "locale": used_locale,
                    "read_only": True,
                    "risk_level": "personal_read",
                    "capability_group": "system_info",
                },
            )

        return {
            "schema_version": SYSTEM_SKILL_ROUTE_SCHEMA,
            "route": "chat_reply",
            "matched": False,
            "locale": used_locale,
            "raw_user_text": raw,
        }

    def _match_datetime(self, raw: str, profile: dict[str, Any]) -> list[str]:
        matches: list[str] = []

        compact = self._compact_text(raw)

        if self._contains_any(raw, profile, "system_skill.datetime.time_queries"):
            matches.append("system_skill.datetime.time_queries")
        elif (
            any(word in compact for word in ("几点", "几点钟", "什么时间", "当前时间", "现在时间"))
            and any(word in compact for word in ("现在", "当前", "此刻", "告诉我", "请问", "请告诉我"))
        ):
            matches.append("system_skill.datetime.time_queries")

        if self._contains_any(raw, profile, "system_skill.datetime.date_queries"):
            matches.append("system_skill.datetime.date_queries")
        elif any(word in compact for word in ("今天几号", "今天日期", "现在日期", "当前日期")):
            matches.append("system_skill.datetime.date_queries")

        if self._contains_any(raw, profile, "system_skill.datetime.weekday_queries"):
            matches.append("system_skill.datetime.weekday_queries")
        elif any(word in compact for word in ("星期几", "周几", "礼拜几")):
            matches.append("system_skill.datetime.weekday_queries")

        return matches


    def _contains_any(self, raw: str, profile: dict[str, Any], path: str) -> bool:
        words = self.language_service.list(profile, path)

        try:
            if self.language_service.contains_any(raw, words):
                return True
        except Exception:
            pass

        compact_raw = self._compact_text(raw)
        for word in words:
            compact_word = self._compact_text(str(word or ""))
            if compact_word and compact_word in compact_raw:
                return True

        return False


    def _compact_text(self, text: str) -> str:
        value = str(text or "").strip().lower()
        return re.sub(r"[\s　，,。.!！?？：:；;、]+", "", value)

    def _decision(
        self,
        raw: str,
        locale: str,
        input_channel: str,
        action: str,
        skill: str,
        *,
        matched_rules: list[str],
        reserved: bool = False,
        message_key: str = "",
        arguments: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {
            "schema_version": SYSTEM_SKILL_ROUTE_SCHEMA,
            "route": "system_skill",
            "matched": True,
            "raw_user_text": raw,
            "input_channel": "voice" if str(input_channel or "").lower() == "voice" else "text",
            "locale": locale,
            "skill": skill,
            "action": action,
            "reserved": bool(reserved),
            "matched_rules": matched_rules,
            "message_key": message_key,
            "arguments": arguments if isinstance(arguments, dict) else {},
            "allow_direct_execution": False,
            "requires_qin_review": True,
        }


def route_basic_system_skill(text: str, *, locale: str = "", input_channel: str = "text") -> dict[str, Any]:
    return BasicSystemSkillRouter().route(text, locale=locale, input_channel=input_channel)


def detect_basic_system_skill(text: str, *, locale: str = "", input_channel: str = "text") -> dict[str, Any]:
    return route_basic_system_skill(text, locale=locale, input_channel=input_channel)
