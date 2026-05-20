from __future__ import annotations

import json
from pathlib import Path
from typing import Any


SUPPORTED_UI_LOCALES = ("zh-CN", "en-US", "ja-JP")
DEFAULT_UI_LOCALE = "zh-CN"

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_PREF_FILE = _PROJECT_ROOT / "data" / "user_prefs" / "ui_language.json"


UI_TRANSLATIONS: dict[str, dict[str, str]] = {
    "zh-CN": {
        "app.title": "本地桌面语音 AI 原型",
        "toolbar.title": "本地桌面语音 AI",
        "toolbar.reply_text": "回复文本",
        "toolbar.system_status": "系统状态",
        "toolbar.settings": "设置",
        "main.input_label": "文本输入区，回车换行，双击回车发送",
        "main.input_placeholder": "请输入文字，或将语音识别结果发送给 AI...",
        "main.send_text": "发送文字",
        "main.start_record": "开始录音",
        "main.stop_record": "停止录音",
        "main.output_mode_hint": "当前输出模式：{mode}",
        "settings.title": "设置",
        "settings.quick_entry": "快捷入口",
        "settings.open_control_center": "打开控制中心",
        "settings.open_folder": "打开文件夹",
        "settings.restart_project": "重启项目",
        "settings.language": "界面语言",
        "settings.output_mode": "输出模式",
        "language.zh": "中文",
        "language.en": "English",
        "language.ja": "日本語",
        "output.text_only": "仅文字",
        "output.text_voice": "文字+语音",
        "output.voice_only": "仅语音",
        "control.title": "控制中心",
        "control.reply_text": "回复文本",
        "control.close": "关闭",
        "control.nav.model": "运行配置",
        "control.nav.connection": "连接配置",
        "control.nav.basic_settings": "基础设置",
        "control.nav.desktop": "桌面连接",
        "control.nav.style": "风格设计",
        "control.nav.info": "角色组合",
        "control.nav.system_group": "系统配置",
        "control.nav.voice_group": "语音配置",
        "control.nav.expand": "展开左侧栏",
        "control.nav.collapse": "缩进左侧栏",
    },
    "en-US": {
        "app.title": "Local Desktop Voice AI Prototype",
        "toolbar.title": "Local Desktop Voice AI",
        "toolbar.reply_text": "Reply Text",
        "toolbar.system_status": "System Status",
        "toolbar.settings": "Settings",
        "main.input_label": "Text input, Enter for newline, double Enter to send",
        "main.input_placeholder": "Enter text, or send speech recognition results to AI...",
        "main.send_text": "Send Text",
        "main.start_record": "Start Recording",
        "main.stop_record": "Stop Recording",
        "main.output_mode_hint": "Current output mode: {mode}",
        "settings.title": "Settings",
        "settings.quick_entry": "Quick Entry",
        "settings.open_control_center": "Open Control Center",
        "settings.open_folder": "Open Folder",
        "settings.restart_project": "Restart Project",
        "settings.language": "Interface Language",
        "settings.output_mode": "Output Mode",
        "language.zh": "中文",
        "language.en": "English",
        "language.ja": "日本語",
        "output.text_only": "Text Only",
        "output.text_voice": "Text + Voice",
        "output.voice_only": "Voice Only",
        "control.title": "Control Center",
        "control.reply_text": "Reply Text",
        "control.close": "Close",
        "control.nav.model": "Runtime Config",
        "control.nav.connection": "Connection Config",
        "control.nav.basic_settings": "Basic Settings",
        "control.nav.desktop": "Desktop Connection",
        "control.nav.style": "Style Design",
        "control.nav.info": "Role Combination",
        "control.nav.system_group": "System Config",
        "control.nav.voice_group": "Voice Config",
        "control.nav.expand": "Expand Sidebar",
        "control.nav.collapse": "Collapse Sidebar",
    },
    "ja-JP": {
        "app.title": "ローカルデスクトップ音声 AI プロトタイプ",
        "toolbar.title": "ローカルデスクトップ音声 AI",
        "toolbar.reply_text": "返信テキスト",
        "toolbar.system_status": "システム状態",
        "toolbar.settings": "設定",
        "main.input_label": "テキスト入力、Enterで改行、Enterを2回押すと送信",
        "main.input_placeholder": "文字を入力、または音声認識結果を AI に送信...",
        "main.send_text": "文字を送信",
        "main.start_record": "録音開始",
        "main.stop_record": "録音停止",
        "main.output_mode_hint": "現在の出力モード：{mode}",
        "settings.title": "設定",
        "settings.quick_entry": "クイック入口",
        "settings.open_control_center": "コントロールセンターを開く",
        "settings.open_folder": "フォルダーを開く",
        "settings.restart_project": "プロジェクトを再起動",
        "settings.language": "表示言語",
        "settings.output_mode": "出力モード",
        "language.zh": "中文",
        "language.en": "English",
        "language.ja": "日本語",
        "output.text_only": "文字のみ",
        "output.text_voice": "文字 + 音声",
        "output.voice_only": "音声のみ",
        "control.title": "コントロールセンター",
        "control.reply_text": "返信テキスト",
        "control.close": "閉じる",
        "control.nav.model": "実行設定",
        "control.nav.connection": "接続設定",
        "control.nav.basic_settings": "基本設定",
        "control.nav.desktop": "デスクトップ接続",
        "control.nav.style": "スタイル設計",
        "control.nav.info": "役割構成",
        "control.nav.system_group": "システム設定",
        "control.nav.voice_group": "音声設定",
        "control.nav.expand": "左サイドバーを展開",
        "control.nav.collapse": "左サイドバーを折りたたむ",
    },
}


class UiLanguageService:
    def __init__(self, pref_file: Path = _PREF_FILE):
        self.pref_file = pref_file
        self.locale = self._load_locale()

    def _load_locale(self) -> str:
        try:
            data = json.loads(self.pref_file.read_text(encoding="utf-8"))
            locale = str(data.get("locale", DEFAULT_UI_LOCALE))
        except Exception:
            locale = DEFAULT_UI_LOCALE

        if locale not in SUPPORTED_UI_LOCALES:
            return DEFAULT_UI_LOCALE
        return locale

    def set_locale(self, locale: str) -> str:
        if locale not in SUPPORTED_UI_LOCALES:
            locale = DEFAULT_UI_LOCALE

        self.locale = locale
        self.pref_file.parent.mkdir(parents=True, exist_ok=True)
        self.pref_file.write_text(
            json.dumps({"locale": locale}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return self.locale

    def t(self, key: str, default: str | None = None, **params: Any) -> str:
        text = UI_TRANSLATIONS.get(self.locale, {}).get(key)
        if text is None:
            text = UI_TRANSLATIONS[DEFAULT_UI_LOCALE].get(key, default or key)

        if params:
            try:
                return text.format(**params)
            except Exception:
                return text
        return text


_ui_language_service: UiLanguageService | None = None


def get_ui_language_service() -> UiLanguageService:
    global _ui_language_service
    if _ui_language_service is None:
        _ui_language_service = UiLanguageService()
    return _ui_language_service
