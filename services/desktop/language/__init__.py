from __future__ import annotations

from services.desktop.language.language_service import DesktopLanguageService
from services.desktop.language.locale_detector import detect_locale
from services.desktop.language.ui_language_service import UiLanguageService, get_ui_language_service

__all__ = ["DesktopLanguageService", "UiLanguageService", "detect_locale", "get_ui_language_service"]
