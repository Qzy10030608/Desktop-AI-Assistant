from __future__ import annotations

import re


def detect_locale(text: str) -> str:
    raw = str(text or "")
    if any(phrase in raw for phrase in ("今何時", "現在時刻", "今日は何日", "今日の日付")):
        return "ja-JP"
    if re.search(r"[\u3040-\u30ff]", raw):
        return "ja-JP"

    letters = re.findall(r"[A-Za-z]", raw)
    cjk = re.findall(r"[\u4e00-\u9fff]", raw)
    if letters and (not cjk or (len(cjk) <= 1 and len(letters) >= 4)):
        return "en-US"

    return "zh-CN"
