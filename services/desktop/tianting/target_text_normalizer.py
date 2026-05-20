from __future__ import annotations

import re
from typing import Any

from services.desktop.language.language_service import DesktopLanguageService


def normalize_target_text(
    raw_text: str,
    *,
    action_hint: str = "",
    locale: str = "",
    profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    统一目标清洗。

    例：
    - 请打开绘画 -> 绘画
    - 请帮我打开记事本 -> 记事本
    - Open Stardew Valley please -> Stardew Valley
    - スターデューバレーを開いて -> スターデューバレー

    这里只清洗，不判断具体软件，不决定权限，不执行。
    """
    raw = str(raw_text or "").strip()
    service = DesktopLanguageService()

    used_profile = profile if isinstance(profile, dict) else (
        service.load_profile(locale) if locale else service.profile_for_text(raw)
    )

    used_locale = str(used_profile.get("locale", locale or service.detect_locale(raw)) or "zh-CN")

    action = str(action_hint or "").strip().lower()

    tokens: list[str] = []
    generic_tokens: set[str] = set()

    if action in {"app.launch", "file.open", "folder.open"} or action.endswith(".open") or action.endswith(".launch"):
        tokens.extend(service.list(used_profile, "command.open_verbs"))
    elif action in {"app.close", "file.close", "folder.close"} or action.endswith(".close"):
        tokens.extend(service.list(used_profile, "command.close_verbs"))
    else:
        tokens.extend(service.list(used_profile, "command.open_verbs"))
        tokens.extend(service.list(used_profile, "command.close_verbs"))

    tokens.extend(service.list(used_profile, "command.polite_fillers"))

    if action.startswith("app."):
        app_generic = service.list(used_profile, "command.generic_app_words")
        tokens.extend(app_generic)
        generic_tokens.update(app_generic)
    elif action.startswith("file.") or action.startswith("folder."):
        file_generic = service.list(used_profile, "command.generic_file_words")
        tokens.extend(file_generic)
        generic_tokens.update(file_generic)
    else:
        app_generic = service.list(used_profile, "command.generic_app_words")
        file_generic = service.list(used_profile, "command.generic_file_words")
        tokens.extend(app_generic)
        tokens.extend(file_generic)
        generic_tokens.update(app_generic)
        generic_tokens.update(file_generic)

    cleaned = raw

    # 长词优先，避免“请帮我打开”先被“请”拆掉
    tokens = sorted(set(tokens), key=len, reverse=True)

    removed: list[str] = []
    for token in tokens:
        before = cleaned
        next_text = _remove_token(cleaned, token)

        # 防御：generic token 不允许把最后一个目标词删空。
        # 例如语言包误把“微信”放进 generic_app_words 时，不能把目标清成空。
        if token in generic_tokens:
            before_clean = _cleanup_text(before, locale=used_locale)
            next_clean = _cleanup_text(next_text, locale=used_locale)
            if before_clean and not next_clean:
                continue

        cleaned = next_text
        if cleaned != before:
            removed.append(token)

    cleaned = _cleanup_text(cleaned, locale=used_locale)

    return {
        "schema_version": "target_text_normalization_v1",
        "raw_text": raw,
        "normalized_target": cleaned,
        "locale": used_locale,
        "action_hint": action_hint,
        "removed_tokens": removed,
        "profile_locale": used_locale,
    }


def _remove_token(text: str, token: str) -> str:
    source = str(text or "")
    clean_token = str(token or "").strip()
    if not clean_token:
        return source

    # 英文用词边界，避免 open 误删 stopen 之类
    if clean_token.isascii():
        pattern = r"(?i)\b" + re.escape(clean_token) + r"\b"
        return re.sub(pattern, " ", source)

    # 中文/日文直接替换
    return source.replace(clean_token, " ")


def _cleanup_text(text: str, *, locale: str = "") -> str:
    result = str(text or "")

    # 常见标点
    result = re.sub(r"[，。！？、,.!?;；:：]+", " ", result)

    # 日语残留助词，轻量处理，不做复杂形态分析
    if str(locale or "").lower().startswith("ja"):
        result = result.strip()
        result = re.sub(r"(を|に|で|へ)$", "", result)

    result = " ".join(result.split()).strip()
    return result
