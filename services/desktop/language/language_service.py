from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from services.desktop.language.locale_detector import detect_locale


DEFAULT_LOCALE = "zh-CN"
SAFE_FALLBACK_MESSAGE = "桌面操作已处理。"


class DesktopLanguageService:
    """Unified desktop language resource service.

    Natural-language resources live under services/desktop/language/locales.
    """

    _cache: dict[str, tuple[float, dict[str, Any]]] = {}

    def __init__(
        self,
        locale_dir: str | Path | None = None,
        *,
        default_locale: str = DEFAULT_LOCALE,
    ) -> None:
        self.locale_dir = Path(locale_dir or Path(__file__).resolve().parent / "locales")
        self.default_locale = str(default_locale or DEFAULT_LOCALE).strip() or DEFAULT_LOCALE

    def detect_locale(self, text: str) -> str:
        return detect_locale(text)

    def load_profile(self, locale: str | None = None) -> dict[str, Any]:
        requested = str(locale or self.default_locale or DEFAULT_LOCALE).strip() or DEFAULT_LOCALE
        for candidate in (requested, self.default_locale, DEFAULT_LOCALE):
            profile = self._read_profile(candidate)
            if profile:
                return profile
        return self._default_profile()

    def profile_for_text(self, text: str) -> dict[str, Any]:
        return self.load_profile(self.detect_locale(text))

    def get_profile_for_text(self, text: str) -> dict[str, Any]:
        return self.profile_for_text(text)

    def get(self, profile: dict[str, Any], path: str, default: Any = None) -> Any:
        current: Any = profile if isinstance(profile, dict) else {}
        for part in str(path or "").split("."):
            if not part:
                continue
            if not isinstance(current, dict) or part not in current:
                return default
            current = current.get(part)
        return current

    def list(self, profile: dict[str, Any], path: str) -> list[str]:
        value = self.get(profile, path, [])
        if isinstance(value, list):
            return [str(item) for item in value if str(item or "").strip()]
        return []

    def words(self, profile: dict[str, Any], key: str) -> list[str]:
        return self.list(profile, f"command.{key}")

    def connection_words(self, profile: dict[str, Any], key: str) -> list[str]:
        return self.list(profile, f"command.connection_words.{key}")

    def contains_any(self, text: str, queries: list[str], locale: str | None = None) -> bool:
        compact = "".join(str(text or "").split()).lower()
        for query in queries if isinstance(queries, list) else []:
            needle = "".join(str(query or "").split()).lower()
            if needle and needle in compact:
                return True
        return False

    def render(
        self,
        profile: dict[str, Any] | None,
        key: str,
        params: dict[str, Any] | None = None,
    ) -> str:
        clean_key = str(key or "").strip()
        if not clean_key:
            return SAFE_FALLBACK_MESSAGE
        payload = profile if isinstance(profile, dict) else self.load_profile()
        reply_catalog = payload.get("reply", {}) if isinstance(payload.get("reply"), dict) else {}
        template = str(reply_catalog.get(clean_key, "") or "").strip()
        if not template:
            template = str(self.get(payload, f"reply.{clean_key}", "") or "").strip()
        if not template:
            return SAFE_FALLBACK_MESSAGE
        safe_params = {name: _safe_param(value) for name, value in (params or {}).items()}
        try:
            return template.format(**safe_params)
        except Exception:
            return template

    def _read_profile(self, locale: str) -> dict[str, Any]:
        path = self.locale_dir / f"{locale}.json"
        try:
            mtime = path.stat().st_mtime
            cache_key = str(path)
            cached = self._cache.get(cache_key)
            if cached and cached[0] == mtime:
                return dict(cached[1])
            data = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                return {}
            self._cache[cache_key] = (mtime, data)
            return dict(data)
        except Exception:
            return {}

    def _default_profile(self) -> dict[str, Any]:
        return {
            "schema_version": "desktop_language_profile_v1",
            "locale": DEFAULT_LOCALE,
            "command": {},
            "system_skill": {},
            "pending": {},
            "reply": {},
            "ui": {},
        }


def _safe_param(value: Any) -> str:
    return str(value if value is not None else "").strip()[:120]
