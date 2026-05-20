import os

# =========================
# 主页面资源路径
# =========================
ASSET_DIR = os.path.join(os.path.dirname(__file__), "assets")

def _qss_url(path: str) -> str:
    return os.path.abspath(path).replace("\\", "/")

MAIN_WINDOW_ASSET = {
    "settings_icon": _qss_url(os.path.join(ASSET_DIR, "设置.png")),
    "status_icon": _qss_url(os.path.join(ASSET_DIR, "系统状态.png")),
    "reply_icon": _qss_url(os.path.join(ASSET_DIR, "已回复.png")),

    "glass_blue": _qss_url(os.path.join(ASSET_DIR, "蓝色玻璃.png")),
    "glass_pink": _qss_url(os.path.join(ASSET_DIR, "粉色玻璃.png")),
    "glass_red": _qss_url(os.path.join(ASSET_DIR, "静止按钮.png")),
    "glass_disabled": _qss_url(os.path.join(ASSET_DIR, "红色玻璃.png")),

    "play_icon": _qss_url(os.path.join(ASSET_DIR, "播放.png")),
    "download_icon": _qss_url(os.path.join(ASSET_DIR, "下载.png")),
    "favorite_off_icon": _qss_url(os.path.join(ASSET_DIR, "收藏 -未收藏.png")),
    "favorite_on_icon": _qss_url(os.path.join(ASSET_DIR, "收藏 -已收藏.png")),
}

# =========================
# 尺寸配置
# =========================
MAIN_WINDOW_SIZE = {
    "window_width": 950,
    "window_height": 1080,
    "window_min_width": 720,
    "window_min_height": 760,

    "outer_margin": 18,
    "outer_spacing": 12,

    "card_margin": 18,
    "card_spacing": 12,
    "main_card_padding": 6,

    "radius_large": 18,
    "radius_medium": 12,
    "radius_small": 8,

    "font_title": 20,
    "font_section": 14,
    "font_body": 12,
    "font_input": 14,
    "font_small": 11,

    "chat_message_margin_h": 12,
    "chat_message_margin_v": 10,
    "chat_message_spacing": 8,
    "chat_message_radius": 12,
    "chat_message_border_width": 1,
    "chat_title_font": 13,
    "chat_body_font": 14,
    "chat_meta_font": 12,
    "chat_system_font": 12,
    "chat_pending_padding_h": 14,
    "chat_pending_padding_v": 12,
    "chat_pending_spacing": 10,
    "chat_pending_candidate_padding_h": 10,
    "chat_pending_candidate_padding_v": 8,
    "chat_pending_button_min_height": 30,
    "chat_pending_button_padding_h": 12,
    "chat_pending_button_padding_v": 4,
    "chat_pending_button_radius": 8,

    "toolbar_height": 46,
    "toolbar_spacing": 10,
    "toolbar_button_size": 38,
    "toolbar_icon_size": 20,

    "hint_bar_height": 26,
    "hint_bar_font": 11,

    "text_input_max_height": 118,

    # 主页面底部三按钮
    "main_action_spacing": 10,
    "main_action_min_height": 42,
    "main_action_font": 14,
    "main_action_text_h_padding": 18,

    # 聊天气泡里的图标按钮
    "chat_action_button_w": 56,
    "chat_action_button_h": 40,
    "chat_action_icon_size": 22,
    "chat_action_spacing": 8,

    # 用户录音消息里的播放按钮
    "record_action_button_w": 56,
    "record_action_button_h": 40,
    "record_action_icon_size": 22,

    "status_popup_width": 420,
    "status_popup_height": 260,
    "settings_popup_width": 360,
    "settings_popup_height": 220,

    "loading_text_font": 12,
}

# =========================
# 颜色配置
# =========================
MAIN_WINDOW_COLOR = {
    "bg_main": "#1E5AA8",
    "bg_card": "#0B1835",
    "bg_input": "#6B7686",

    "border_card": "#24324F",
    "border_input": "#7D8796",
    "border_icon": "#4B5B76",

    "primary": "#2F6FE4",
    "primary_hover": "#4A82EC",
    "primary_disabled": "#5E6A7C",

    "toolbar_button_bg": "#13284D",
    "toolbar_button_hover": "#1C3B6E",

    "toolbar_button_bg_bright": "#4DA3FF",
    "toolbar_button_hover_bright": "#74B9FF",
    "toolbar_button_border_bright": "#A8D6FF",

    "hint_bg": "#071224",
    "hint_border": "#23375A",

    "popup_bg": "#0D172C",
    "popup_border": "#334155",
    "popup_line": "#22304A",
    "popup_action_bg": "#13284D",
    "popup_action_hover": "#1E3A68",
    "popup_action_border": "#334A73",
    "popup_mode_bg": "#1A2740",
    "popup_mode_hover": "#22375A",

    "text_main": "#FFFFFF",
    "text_soft": "#DCE6F8",
    "text_muted": "#A9B8D0",

    "audio_card_bg": "#111827",
    "audio_card_border": "#334155",
    "record_card_bg": "#1E3A8A",
    "record_card_border": "#3B82F6",
    "user_message_bg": "#1E3A8A",
    "user_message_border": "#3B82F6",
    "ai_message_bg": "#111827",
    "ai_message_border": "#334155",
    "recognized_message_bg": "#3F3F46",
    "recognized_message_border": "#71717A",
    "error_message_bg": "#451A03",
    "error_message_border": "#F97316",
    "system_message_bg": "#1F2937",
    "system_message_border": "#475569",
    "system_message_text": "#D8E4F8",
    "chat_title": "#93C5FD",
    "chat_user_title": "#BFDBFE",
    "chat_record_title": "#BFDBFE",
    "chat_text": "#FFFFFF",
    "chat_meta": "#E5F0FF",
    "chat_audio_status": "#C4B5FD",
    "chat_pending_bg": "rgba(3, 18, 24, 235)",
    "chat_pending_border": "#2DD4BF",
    "chat_pending_border_resolved": "#22C55E",
    "chat_pending_border_cancelled": "#64748B",
    "chat_pending_title": "#67E8F9",
    "chat_pending_text": "#F8FAFC",
    "chat_pending_status": "#A7F3D0",
    "chat_pending_candidate_bg": "rgba(20, 184, 166, 28)",
    "chat_pending_candidate_border": "rgba(94, 234, 212, 120)",
    "chat_pending_candidate_label": "#ECFEFF",
    "chat_pending_candidate_subtitle": "#A7F3D0",
    "chat_pending_button_bg": "rgba(13, 148, 136, 70)",
    "chat_pending_button_hover": "rgba(20, 184, 166, 120)",
    "chat_pending_button_disabled_bg": "rgba(51, 65, 85, 90)",
    "chat_pending_button_disabled_text": "#94A3B8",
    "chat_pending_button_disabled_border": "#475569",

    "loading_overlay_bg": "rgba(2, 6, 23, 215)",
    "loading_text": "#FFFFFF",

    "folder_menu_bg": "#2D6BC2",
    "folder_menu_hover": "#3E86E6",
    "folder_menu_border": "#8EC5FF",
    "folder_menu_text": "#FFFFFF",
}


def build_main_window_qss() -> str:
    c = MAIN_WINDOW_COLOR
    s = MAIN_WINDOW_SIZE
    a = MAIN_WINDOW_ASSET

    return f"""
    QWidget {{
        background-color: {c["bg_main"]};
        color: {c["text_main"]};
        font-family: "Microsoft YaHei";
        font-size: {s["font_body"]}pt;
    }}

    QFrame#mainCard {{
        background-color: {c["bg_card"]};
        border-radius: {s["radius_large"]}px;
        padding: {s["main_card_padding"]}px;
    }}

    QFrame#runtimeHintFrame {{
        background-color: {c["hint_bg"]};
        border: 1px solid {c["hint_border"]};
        border-radius: {s["radius_small"]}px;
    }}

    QLabel#runtimeHintLabel {{
        color: {c["text_soft"]};
        font-size: {s["hint_bar_font"]}pt;
        font-weight: bold;
        background: transparent;
        padding-left: 10px;
        padding-right: 10px;
    }}

    QLabel#sectionLabel {{
        font-size: {s["font_section"]}pt;
        font-weight: bold;
        color: {c["text_main"]};
        background: transparent;
    }}

    QPlainTextEdit#textInput {{
        background-color: {c["bg_input"]};
        color: {c["text_main"]};
        border: 1px solid {c["border_input"]};
        border-radius: {s["radius_medium"]}px;
        padding: 12px;
        font-size: {s["font_input"]}pt;
    }}

    /* =========================
       主页面底部三按钮
       ========================= */
    QPushButton#mainBottomActionButton {{
        min-height: {s["main_action_min_height"]}px;
        font-size: {s["main_action_font"]}pt;
        font-weight: bold;
        color: {c["text_main"]};
        border: none;
        background: transparent;
        padding-left: {s["main_action_text_h_padding"]}px;
        padding-right: {s["main_action_text_h_padding"]}px;
    }}

    QPushButton#mainBottomActionButton[skin="blue"] {{
       
        border-image: url("{a["glass_blue"]}") 18 18 18 18 stretch stretch;
    }}

    QPushButton#mainBottomActionButton[skin="pink"] {{
       
        border-image: url("{a["glass_pink"]}") 18 18 18 18 stretch stretch;
    }}

    QPushButton#mainBottomActionButton[skin="red"] {{
       
        border-image: url("{a["glass_red"]}") 18 18 18 18 stretch stretch;
    }}

    QPushButton#mainBottomActionButton[skin="disabled"] {{
      
        border-image: url("{a["glass_disabled"]}") 18 18 18 18 stretch stretch;
        color: {c["text_muted"]};
    }}

    QPushButton#mainBottomActionButton[skin="blue"]:disabled {{
        border-image: url("{a["glass_disabled"]}") 18 18 18 18 stretch stretch;
        color: {c["text_muted"]};
    }}

    QPushButton#mainBottomActionButton[skin="pink"]:disabled {{
        border-image: url("{a["glass_pink"]}") 18 18 18 18 stretch stretch;
        color: {c["text_main"]};
    }}

    QPushButton#mainBottomActionButton[skin="red"]:disabled {{
        border-image: url("{a["glass_disabled"]}") 18 18 18 18 stretch stretch;
        color: {c["text_muted"]};
    }}
    """


def build_chat_panel_qss() -> str:
    s = MAIN_WINDOW_SIZE
    return f"""
    QScrollArea#chatPanel {{
        background-color: #000000;
        border: 1px solid #16284D;
        border-radius: {s["radius_medium"]}px;
    }}

    QWidget#chatContainer {{
        background-color: #000000;
    }}
    """


def build_text_message_widget_qss(role: str) -> str:
    c = MAIN_WINDOW_COLOR
    s = MAIN_WINDOW_SIZE
    palette = {
        "user": (c["user_message_bg"], c["user_message_border"], c["chat_user_title"]),
        "ai": (c["ai_message_bg"], c["ai_message_border"], c["chat_title"]),
        "recognized": (c["recognized_message_bg"], c["recognized_message_border"], c["chat_title"]),
        "error": (c["error_message_bg"], c["error_message_border"], c["chat_title"]),
    }
    bg, border, title = palette.get(role, (c["system_message_bg"], c["system_message_border"], c["chat_title"]))
    return f"""
    QFrame#textMessageWidget {{
        background-color: {bg};
        border: {s["chat_message_border_width"]}px solid {border};
        border-radius: {s["chat_message_radius"]}px;
    }}
    QLabel#msgTitle {{
        color: {title};
        font-size: {s["chat_title_font"]}pt;
        font-weight: bold;
        background: transparent;
    }}
    QLabel#msgText {{
        color: {c["chat_text"]};
        font-size: {s["chat_body_font"]}pt;
        background: transparent;
    }}
    """


def build_system_message_widget_qss(kind: str = "system") -> str:
    c = MAIN_WINDOW_COLOR
    s = MAIN_WINDOW_SIZE
    is_error = kind == "error"
    bg = c["error_message_bg"] if is_error else c["system_message_bg"]
    border = c["error_message_border"] if is_error else c["system_message_border"]
    text = c["chat_meta"] if is_error else c["system_message_text"]
    return f"""
    QFrame#systemMessageWidget {{
        background-color: {bg};
        border: {s["chat_message_border_width"]}px solid {border};
        border-radius: {s["chat_message_radius"]}px;
    }}
    QLabel {{
        color: {text};
        font-size: {s["chat_system_font"]}px;
        font-style: italic;
        background: transparent;
    }}
    """


def build_audio_message_widget_qss() -> str:
    c = MAIN_WINDOW_COLOR
    s = MAIN_WINDOW_SIZE
    a = MAIN_WINDOW_ASSET

    return f"""
    QFrame#audioMessageWidget {{
        background-color: {c["audio_card_bg"]};
        border: 1px solid {c["audio_card_border"]};
        border-radius: {s["chat_message_radius"]}px;
    }}
    QFrame#visualFrame {{
        background-color: rgba(255, 255, 255, 0.03);
        border: 1px solid rgba(120, 160, 220, 0.18);
        border-radius: {s["radius_small"]}px;
    }}
    QLabel#msgTitle {{
        color: {c["chat_title"]};
        font-size: {s["chat_title_font"]}px;
        font-weight: bold;
        background: transparent;
    }}
    QLabel#msgText {{
        color: {c["chat_text"]};
        font-size: {s["chat_body_font"]}px;
        background: transparent;
    }}
    QLabel#audioStatus {{
        color: {c["chat_audio_status"]};
        font-size: {s["chat_meta_font"]}px;
        background: transparent;
    }}
    QLabel#visualText {{
        color: {c["text_soft"]};
        font-size: {s["chat_meta_font"]}px;
        font-weight: bold;
        background: transparent;
    }}

    QPushButton#chatActionIconButton {{
        min-width: {s["chat_action_button_w"]}px;
        max-width: {s["chat_action_button_w"]}px;
        min-height: {s["chat_action_button_h"]}px;
        max-height: {s["chat_action_button_h"]}px;
        border: none;
        background: transparent;
        padding: 0;
    }}

    QPushButton#chatActionIconButton {{
        border-image: url("{a["glass_blue"]}") 18 18 18 18 stretch stretch;
    }}

    QPushButton#chatActionIconButton:disabled {{
        border-image: url("{a["glass_disabled"]}") 18 18 18 18 stretch stretch;
    }}
    """


def build_record_message_widget_qss() -> str:
    c = MAIN_WINDOW_COLOR
    s = MAIN_WINDOW_SIZE
    a = MAIN_WINDOW_ASSET

    return f"""
    QFrame#recordMessageWidget {{
        background-color: {c["record_card_bg"]};
        border: 1px solid {c["record_card_border"]};
        border-radius: {s["chat_message_radius"]}px;
    }}
    QLabel#msgTitle {{
        color: {c["chat_record_title"]};
        font-size: {s["chat_title_font"]}pt;
        font-weight: bold;
        background: transparent;
    }}
    QLabel#recordMeta {{
        color: {c["chat_meta"]};
        font-size: {s["chat_meta_font"]}pt;
        background: transparent;
    }}

    QPushButton#recordPlayIconButton {{
        min-width: {s["record_action_button_w"]}px;
        max-width: {s["record_action_button_w"]}px;
        min-height: {s["record_action_button_h"]}px;
        max-height: {s["record_action_button_h"]}px;
        border: none;
        background: transparent;
        padding: 0;
        border-image: url("{a["glass_blue"]}") 18 18 18 18 stretch stretch;
    }}

    QPushButton#recordPlayIconButton:disabled {{
        border-image: url("{a["glass_disabled"]}") 18 18 18 18 stretch stretch;
    }}
    """
def build_folder_menu_qss() -> str:
    c = MAIN_WINDOW_COLOR
    s = MAIN_WINDOW_SIZE
    return f"""
    QMenu {{
        background-color: {c["folder_menu_bg"]};
        color: {c["folder_menu_text"]};
        border: 1px solid {c["folder_menu_border"]};
        border-radius: {s["radius_small"]}px;
        padding: 6px;
    }}

    QMenu::item {{
        padding: 8px 18px;
        border-radius: 6px;
        background: transparent;
    }}

    QMenu::item:selected {{
        background-color: {c["folder_menu_hover"]};
    }}
    """


def build_main_settings_popup_qss() -> str:
    c = MAIN_WINDOW_COLOR
    s = MAIN_WINDOW_SIZE
    return f"""
    QWidget#mainSettingsPopup {{
        background-color: {c["popup_bg"]};
        border: 1px solid {c["popup_border"]};
        border-radius: {s["radius_medium"]}px;
    }}

    QLabel#popupTitle {{
        color: {c["text_main"]};
        font-size: {s["font_section"]}pt;
        font-weight: bold;
        background: transparent;
    }}

    QLabel#sectionLabel {{
        color: {c["text_soft"]};
        font-size: {s["font_small"]}pt;
        font-weight: bold;
        background: transparent;
        padding-top: 4px;
    }}

    QFrame#popupLine {{
        background-color: {c["popup_line"]};
        border: none;
    }}

    QPushButton#popupActionButton {{
        min-height: 38px;
        padding: 0 12px;
        border-radius: {s["radius_small"]}px;
        border: 1px solid {c["popup_action_border"]};
        background-color: {c["popup_action_bg"]};
        color: {c["text_main"]};
        font-size: {s["font_small"]}pt;
        font-weight: bold;
        text-align: left;
    }}

    QPushButton#popupActionButton:hover {{
        background-color: {c["popup_action_hover"]};
    }}

    QComboBox#languageComboBox {{
        min-height: 34px;
        padding: 0 10px;
        border-radius: {s["radius_small"]}px;
        border: 1px solid {c["popup_action_border"]};
        background-color: {c["popup_mode_bg"]};
        color: {c["text_main"]};
        font-size: {s["font_small"]}pt;
        font-weight: bold;
    }}

    QComboBox#languageComboBox:hover {{
        background-color: {c["popup_mode_hover"]};
    }}

    QComboBox#languageComboBox QAbstractItemView {{
        background-color: {c["popup_bg"]};
        color: {c["text_main"]};
        selection-background-color: {c["primary"]};
        selection-color: {c["text_main"]};
        border: 1px solid {c["popup_border"]};
    }}

    QPushButton#modeChipButton {{
        min-height: 34px;
        padding: 0 10px;
        border-radius: {s["radius_small"]}px;
        border: 1px solid {c["popup_action_border"]};
        background-color: {c["popup_mode_bg"]};
        color: {c["text_main"]};
        font-size: {s["font_small"]}pt;
        font-weight: bold;
    }}

    QPushButton#modeChipButton[active="true"] {{
        background-color: {c["primary"]};
        border: 1px solid {c["primary_hover"]};
    }}

    QPushButton#modeChipButton:hover {{
        background-color: {c["popup_mode_hover"]};
    }}
    """


def build_pending_interaction_card_qss() -> str:
    c = MAIN_WINDOW_COLOR
    s = MAIN_WINDOW_SIZE
    return f"""
    QFrame#pendingInteractionCard {{
        background-color: {c["chat_pending_bg"]};
        border: {s["chat_message_border_width"]}px solid {c["chat_pending_border"]};
        border-radius: {s["chat_message_radius"]}px;
    }}
    QFrame#pendingInteractionCard[state="resolved"] {{
        border: {s["chat_message_border_width"]}px solid {c["chat_pending_border_resolved"]};
    }}
    QFrame#pendingInteractionCard[state="cancelled"] {{
        border: {s["chat_message_border_width"]}px solid {c["chat_pending_border_cancelled"]};
    }}
    QLabel#pendingTitle {{
        color: {c["chat_pending_title"]};
        font-size: {s["chat_meta_font"]}px;
        font-weight: bold;
        background: transparent;
    }}
    QLabel#pendingText {{
        color: {c["chat_pending_text"]};
        font-size: {s["chat_body_font"]}px;
        background: transparent;
    }}
    QLabel#pendingStatus {{
        color: {c["chat_pending_status"]};
        font-size: {s["chat_meta_font"]}px;
        background: transparent;
    }}
    QFrame#pendingCandidateRow {{
        background-color: {c["chat_pending_candidate_bg"]};
        border: {s["chat_message_border_width"]}px solid {c["chat_pending_candidate_border"]};
        border-radius: {s["chat_pending_button_radius"]}px;
    }}
    QLabel#pendingCandidateLabel {{
        color: {c["chat_pending_candidate_label"]};
        font-size: {s["chat_meta_font"]}px;
        font-weight: bold;
        background: transparent;
    }}
    QLabel#pendingCandidateSubtitle {{
        color: {c["chat_pending_candidate_subtitle"]};
        font-size: {s["font_small"]}px;
        background: transparent;
    }}
    QPushButton#pendingActionButton,
    QPushButton#pendingCandidateButton {{
        color: {c["chat_pending_candidate_label"]};
        background-color: {c["chat_pending_button_bg"]};
        border: {s["chat_message_border_width"]}px solid {c["chat_pending_border"]};
        border-radius: {s["chat_pending_button_radius"]}px;
        min-height: {s["chat_pending_button_min_height"]}px;
        padding: {s["chat_pending_button_padding_v"]}px {s["chat_pending_button_padding_h"]}px;
        font-weight: bold;
    }}
    QPushButton#pendingActionButton:hover,
    QPushButton#pendingCandidateButton:hover {{
        background-color: {c["chat_pending_button_hover"]};
    }}
    QPushButton#pendingActionButton:disabled,
    QPushButton#pendingCandidateButton:disabled {{
        color: {c["chat_pending_button_disabled_text"]};
        background-color: {c["chat_pending_button_disabled_bg"]};
        border: {s["chat_message_border_width"]}px solid {c["chat_pending_button_disabled_border"]};
    }}
    """
