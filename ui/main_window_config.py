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
    "window_height": 980,
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


def build_audio_message_widget_qss() -> str:
    c = MAIN_WINDOW_COLOR
    s = MAIN_WINDOW_SIZE
    a = MAIN_WINDOW_ASSET

    return f"""
    QFrame#audioMessageWidget {{
        background-color: {c["audio_card_bg"]};
        border: 1px solid {c["audio_card_border"]};
        border-radius: 12px;
    }}
    QFrame#visualFrame {{
        background-color: rgba(255, 255, 255, 0.03);
        border: 1px solid rgba(120, 160, 220, 0.18);
        border-radius: 10px;
    }}
    QLabel#msgTitle {{
        color: #93C5FD;
        font-size: 13px;
        font-weight: bold;
        background: transparent;
    }}
    QLabel#msgText {{
        color: white;
        font-size: 14px;
        background: transparent;
    }}
    QLabel#audioStatus {{
        color: #C4B5FD;
        font-size: 13px;
        background: transparent;
    }}
    QLabel#visualText {{
        color: #D6E4FF;
        font-size: 12px;
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
        border-radius: 12px;
    }}
    QLabel#msgTitle {{
        color: #BFDBFE;
        font-size: 13pt;
        font-weight: bold;
        background: transparent;
    }}
    QLabel#recordMeta {{
        color: #E5F0FF;
        font-size: 12pt;
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