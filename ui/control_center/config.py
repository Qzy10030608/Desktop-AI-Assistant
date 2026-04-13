# =========================
# 控制中心 UI 配置中心
# 作用：
# 1. 统一窗口尺寸、间距、圆角、字体
# 2. 统一页面标题、导航名、说明文案
# 3. 统一按钮尺寸预设
# 4. 区分页级按钮 与 区块级按钮
# 5. 统一 QSS 样式
# =========================
from pathlib import Path

# =========================
# 一、尺寸（布局参数）
# =========================
UI_SIZE = {
    # -------------------------
    # 窗口
    # -------------------------
    "window_width": 950,
    "window_height": 1080,
    "window_min_width": 680,
    "window_min_height": 900,

    # -------------------------
    # 顶部栏 / 导航
    # -------------------------
    "top_bar_height": 56,
    "nav_width": 190,

    # -------------------------
    # 页面内容边距
    # -------------------------
    "page_inner_margin": 18,
    "page_section_margin": 12,

    # -------------------------
    # 间距
    # -------------------------
    "spacing_large": 14,
    "spacing_medium": 10,
    "spacing_small": 6,

    # -------------------------
    # 圆角
    # -------------------------
    "radius_large": 16,
    "radius_medium": 12,
    "radius_small": 8,

    # -------------------------
    # 按钮高度
    # -------------------------
    "btn_height_main": 42,
    "btn_height_small": 34,
    "btn_height_bookmark": 52,

    # 兼容旧写法
    "button_height": 42,
    "bookmark_height": 52,

    # -------------------------
    # 基础按钮宽度
    # -------------------------
    "btn_w_xs": 72,
    "btn_w_sm": 90,
    "btn_w_md": 110,
    "btn_w_lg": 130,
    "btn_w_xl": 150,

    # -------------------------
    # 功能按钮宽度
    # -------------------------
    "btn_w_refresh": 96,
    "btn_w_apply": 110,
    "btn_w_save": 120,
    "btn_w_save_as": 140,
    "btn_w_folder": 150,
    "btn_w_preview": 100,
    "btn_w_test": 100,
    "btn_w_clear": 80,
    "btn_w_send": 90,
    "btn_w_play": 90,
    "btn_w_delete": 100,
    "btn_w_close": 84,
    "btn_w_choice": 100,

    # -------------------------
    # 字体
    # -------------------------
    "font_title": 24,
    "font_page_title": 22,
    "font_section_title": 15,
    "font_body": 14,
    "font_tip": 12,

    # -------------------------
    # 输入控件
    # -------------------------
    "input_min_height": 38,
    "textedit_min_height": 68,
    "textedit_max_height": 88,
    "textedit_large_min_height": 120,

    # -------------------------
    # 标签
    # -------------------------
    "summary_line_height": 24,
    "section_title_height": 24,

    "info_left_stretch": 5,
    "info_right_stretch": 2,

    "audio_bar_height": 8,
    "audio_icon_btn": 34,
    "audio_time_width": 86,
    "audio_loop_btn": 54,

    "side_top_min_height": 150,
    "side_mid_min_height": 150,
    "side_bottom_min_height": 185,

}
BASE_DIR = Path(__file__).resolve().parents[1]   # 指向 ui
ASSET_PATHS = {
    "tts.loading_gif": str(BASE_DIR / "assets" / "loading" / "tts.loading.gif"),

    "player.play": str(BASE_DIR / "assets" / "启动.png"),
    "player.pause": str(BASE_DIR / "assets" / "暂停.png"),
    "player.loop": str(BASE_DIR / "assets" / "循环播放.png"),
}

# =========================
# 二、页面元信息
# 作用：
# - 左侧导航文字
# - 页面标题
# - 页面说明
# =========================
PAGE_META = {
    "model": {
        "title": "运行配置",
        "nav_text": "运行配置",
        "description": "运行层配置：语言模型、语音后端、角色方案与输出模式。",
    },
    "style": {
        "title": "风格设计",
        "nav_text": "风格设计",
        "description": "模板层配置：文本风格模板与语音表现模板。",
    },
    "info": {
        "title": "角色组合与测试",
        "nav_text": "角色组合",
        "description": "角色组合、方案保存、测试模拟与右侧方案信息显示。",
    },
}

# =========================
# 三、区块渲染预设
# 作用：
# - 页面卡片
# - 区块卡片
# - 标题字号
# =========================
SECTION_RENDER = {
    "page_card": {
        "object_name": "pageCard",
        "margin": "page_inner_margin",
        "spacing": "spacing_large",
    },
    "section_card": {
        "object_name": "sectionCard",
        "margin": "page_section_margin",
        "spacing": "spacing_medium",
    },
    "title_block": {
        "font_size": "font_page_title",
        "font_weight": "bold",
    },
    "section_title_block": {
        "font_size": "font_section_title",
        "font_weight": "bold",
    },
}

# =========================
# 四、按钮尺寸预设
# 作用：
# - 所有按钮统一走这里
# - 页面文件里只写 preset 名称
# =========================
BUTTON_PRESETS = {
    "xs": {"width": "btn_w_xs", "height": "btn_height_main"},
    "sm": {"width": "btn_w_sm", "height": "btn_height_main"},
    "md": {"width": "btn_w_md", "height": "btn_height_main"},
    "lg": {"width": "btn_w_lg", "height": "btn_height_main"},
    "xl": {"width": "btn_w_xl", "height": "btn_height_main"},

    "top": {"width": "btn_w_apply", "height": "btn_height_main"},

    "refresh": {"width": "btn_w_refresh", "height": "btn_height_main"},
    "refresh_long": {"width": "btn_w_md", "height": "btn_height_main"},
    "apply": {"width": "btn_w_apply", "height": "btn_height_main"},
    "save": {"width": "btn_w_save", "height": "btn_height_main"},
    "save_as": {"width": "btn_w_save_as", "height": "btn_height_main"},
    "folder": {"width": "btn_w_folder", "height": "btn_height_main"},

    "preview": {"width": "btn_w_preview", "height": "btn_height_main"},
    "test": {"width": "btn_w_test", "height": "btn_height_main"},
    "clear": {"width": "btn_w_clear", "height": "btn_height_main"},
    "send": {"width": "btn_w_send", "height": "btn_height_main"},
    "play": {"width": "btn_w_play", "height": "btn_height_main"},

    "delete": {"width": "btn_w_delete", "height": "btn_height_main"},
    "close": {"width": "btn_w_close", "height": "btn_height_main"},
    "load": {"width": "btn_w_md", "height": "btn_height_main"},
    "action": {"width": "btn_w_md", "height": "btn_height_main"},

    "bookmark": {"width": None, "height": "btn_height_bookmark"},

    "load_preset": {"width": "btn_w_save", "height": "btn_height_main"},
    "loop": {"width": "btn_w_md", "height": "btn_height_main"},
}

# =========================
# 五、旧版页面按钮组（兼容层）
# 说明：
# - 保留给你现在已有代码继续使用
# - 后面新结构优先走 PAGE_ACTION_AREAS
# =========================
PAGE_BUTTON_GROUPS = {
    "model": {
        "model_rows": [
            ("btn_refresh_models", "refresh"),
            ("btn_refresh_tts_models", "refresh"),
            ("btn_refresh_role_models", "refresh"),
        ],
        "bottom_row": [
            ("btn_refresh_runtime_files", "refresh_long"),
            ("btn_apply_model", "apply"),
            ("btn_save_model", "save"),
        ],
    },
    "style": {
        "role_row": [
            ("btn_preview_role_config", "preview"),
            ("btn_load_role_config", "load"),
            ("btn_save_role_config", "save"),
            ("btn_save_as_role_config", "save_as"),
            ("btn_reset_role_config", "action"),
        ],
        "voice_test_row": [
            ("btn_preview_voice_config", "preview"),
            ("btn_run_voice_test", "test"),
            ("btn_clear_voice_test", "clear"),
        ],
        "voice_save_row": [
            ("btn_load_voice_config", "load"),
            ("btn_save_voice_config", "save"),
            ("btn_save_as_voice_config", "save_as"),
        ],
        "bottom_row": [
            ("btn_apply_style", "apply"),
            ("btn_open_role_config_folder", "folder"),
            ("btn_open_voice_config_folder", "folder"),
        ],
    },
    "info": {
        "top_row": [
            ("btn_combo_save", "save"),
            ("btn_combo_load", "load_preset"),
            ("btn_combo_delete", "delete"),
        ],
        "sim_row": [
            ("btn_combo_run", "send"),
            ("btn_combo_play_pause", "play"),
            ("btn_combo_loop", "loop"),
        ],
    },
    "connection": {
        "llm_row": [
            ("btn_refresh_ollama_models", "refresh_long"),
            ("btn_use_connection_model", "apply"),
        ],
        "gpt_row": [
            ("btn_test_gpt_sovits", "refresh"),
            ("btn_run_startup_check", "refresh_long"),
            ("btn_save_connection", "save"),
        ],
    },
}

# =========================
# 六、新版按钮区域设计
# 核心思想：
# 1. page_actions = 页面总按钮
# 2. section_actions = 各区块自己的按钮
# 这样后面你要调按钮设计会更清晰
# =========================
PAGE_ACTION_AREAS = {
    "model": {
        "page_actions": [
            ("btn_refresh_runtime_files", "refresh_long"),
            ("btn_apply_model", "apply"),
            ("btn_save_model", "save"),
        ],
        "section_actions": {
            "model_card": [
                ("btn_refresh_models", "refresh"),
                ("btn_refresh_tts_models", "refresh"),
                ("btn_refresh_role_models", "refresh"),
            ],
            "runtime_card": [],
        },
    },

    "style": {
        "page_actions": [
            ("btn_apply_style", "apply"),
            ("btn_open_role_config_folder", "folder"),
            ("btn_open_voice_config_folder", "folder"),
        ],
        "section_actions": {
            "text_template_card": [
                ("btn_preview_role_config", "preview"),
                ("btn_load_role_config", "load"),
                ("btn_save_role_config", "save"),
                ("btn_save_as_role_config", "save_as"),
                ("btn_reset_role_config", "action"),
            ],
            "voice_template_card": [
                ("btn_preview_voice_config", "preview"),
                ("btn_run_voice_test", "test"),
                ("btn_clear_voice_test", "clear"),
                ("btn_load_voice_config", "load"),
                ("btn_save_voice_config", "save"),
                ("btn_save_as_voice_config", "save_as"),
            ],
        },
    },

    "info": {
        "page_actions": [],
        "section_actions": {
            "combo_card": [
                ("btn_combo_save", "save"),
                ("btn_combo_test", "test"),
                ("btn_combo_delete", "action"),
            ],
            "sim_card": [
                ("btn_combo_run", "send"),
                ("btn_combo_replay", "play"),
            ],
            "info_side_card": [],
        },
    },
}


# =========================
# 七、读取函数
# =========================
def get_button_preset(name: str) -> dict:
    return BUTTON_PRESETS.get(name, BUTTON_PRESETS["md"])


def get_page_meta(page_key: str) -> dict:
    return PAGE_META.get(page_key, PAGE_META["model"])


def get_page_button_groups(page_key: str) -> dict:
    return PAGE_BUTTON_GROUPS.get(page_key, {})


def get_page_action_areas(page_key: str) -> dict:
    return PAGE_ACTION_AREAS.get(page_key, {"page_actions": [], "section_actions": {}})


# =========================
# 八、颜色（主题）
# =========================
UI_COLOR = {
    "bg_main": "#121212",
    "bg_card": "#1A1A1A",
    "bg_section": "#202020",
    "bg_topbar": "#121212",

    "bg_input": "#8F5105",
    "bg_input_active": "#DCEBFF",
    "bg_input_readonly": "#232A35",

    "border": "#3D3C3C",
    "border_active": "#3A8DFF",
    "border_soft": "#8BB8FF",

    "primary": "#3A8DFF",
    "primary_hover": "#4C84EC",
    "primary_pressed": "#255DC4",

    "text_main": "#FFFFFF",
    "text_secondary": "#DCE8FF",
    "text_dark": "#17345E",
    "text_muted": "#9FB3D9",

    "disabled": "#4A4A4A",
    "disabled_text": "#BFBFBF",

    "status_idle": "#EAB308",     # 黄色：未加载
    "status_ready": "#22C55E",    # 绿色：加载完成
    "status_error": "#EF4444",    # 红色：加载失败
    "loading_text": "#DCE8FF",
    "loading_percent": "#9FB3D9",

    "page_desc": "#9FB3D9",
    "loading_text": "#DCE8FF",
    "loading_percent": "#9FB3D9",

    "reference_toggle_on_bg": "#1E3A2F",
    "reference_toggle_on_border": "#4ADE80",
    "reference_toggle_off_bg": "#3A1E1E",
    "reference_toggle_off_border": "#F87171",
}


# =========================
# 九、QSS
# =========================
def build_qss() -> str:
    c = UI_COLOR
    s = UI_SIZE

    return f"""
    QWidget {{
        background-color: {c["bg_main"]};
        color: {c["text_main"]};
        font-size: {s["font_body"]}px;
        font-family: "Microsoft YaHei";
    }}

    QLabel {{
        background: transparent;
    }}

    QFrame#topBar {{
        background-color: {c["bg_main"]};
        border: 1px solid {c["border"]};
        border-radius: {s["radius_large"]}px;
    }}

    QFrame#navFrame {{
        background-color: {c["bg_card"]};
        border: 1px solid {c["border"]};
        border-radius: {s["radius_large"]}px;
        min-width: {s["nav_width"]}px;
        max-width: {s["nav_width"]}px;
    }}

    QFrame#pageCard {{
        background-color: {c["bg_card"]};
        border-radius: {s["radius_large"]}px;
        border: 1px solid {c["border"]};
    }}

    QFrame#sectionCard {{
        background-color: {c["bg_section"]};
        border-radius: {s["radius_medium"]}px;
        border: 1px solid {c["border"]};
    }}

    QPushButton {{
        background-color: {c["primary"]};
        color: {c["text_main"]};
        border: none;
        border-radius: {s["radius_medium"]}px;
        min-height: {s["button_height"]}px;
        padding: 6px 12px;
        font-weight: bold;
    }}

    QPushButton:hover {{
        background-color: {c["primary_hover"]};
    }}

    QPushButton:pressed {{
        background-color: {c["primary_pressed"]};
    }}

    QPushButton:disabled {{
        background-color: {c["disabled"]};
        color: {c["disabled_text"]};
    }}

    QPushButton[checked="true"] {{
        background-color: {c["primary"]};
        border: 1px solid {c["border_soft"]};
        text-align: center;
        padding-left: 12px;
    }}

    QComboBox, QLineEdit, QTextEdit {{
        background-color: {c["bg_input"]};
        color: {c["text_main"]};
        border: 1px solid {c["border_active"]};
        border-radius: {s["radius_medium"]}px;
        padding: 6px;
        selection-background-color: {c["primary"]};
    }}

    QComboBox:focus, QLineEdit:focus, QTextEdit:focus {{
        background-color: {c["bg_input_active"]};
        color: {c["text_dark"]};
        border: 1px solid {c["border_soft"]};
    }}

    QTextEdit[readOnly="true"] {{
        background-color: {c["bg_input_readonly"]};
        color: {c["text_secondary"]};
        border: 1px solid {c["border"]};
    }}

    QComboBox::drop-down {{
        border: none;
        width: 20px;
        background: transparent;
    }}

    QScrollArea {{
        border: none;
        background: transparent;
    }}

    QScrollArea > QWidget > QWidget {{
        background: transparent;
    }}

    QScrollBar:vertical {{
        background: #182131;
        width: 12px;
        border-radius: 6px;
    }}

    QScrollBar::handle:vertical {{
        background: {c["primary"]};
        min-height: 24px;
        border-radius: 6px;
    }}

    QScrollBar::add-page:vertical,
    QScrollBar::sub-page:vertical {{
        background: #24354D;
        border-radius: 6px;
    }}

    QScrollBar::add-line:vertical,
    QScrollBar::sub-line:vertical {{
        height: 0px;
    }}

    QSlider::groove:horizontal {{
        height: 8px;
        background: #24354D;
        border-radius: 4px;
    }}

    QSlider::sub-page:horizontal {{
        background: {c["primary"]};
        border-radius: 4px;
    }}

    QSlider::add-page:horizontal {{
        background: #182131;
        border-radius: 4px;
    }}

    QSlider::handle:horizontal {{
        background: {c["bg_input_active"]};
        border: 1px solid {c["border_active"]};
        width: 14px;
        border-radius: 7px;
        margin: -4px 0;
    }}

    QFrame#audioDropFrame {{
        background-color: #1A2638;
        border: 1px solid {c["border_active"]};
        border-radius: {s["radius_medium"]}px;
    }}

    QFrame#audioDropInner {{
        background-color: #20314A;
        border: 1px dashed {c["border_soft"]};
        border-radius: {s["radius_medium"]}px;
    }}

    QLabel#audioDropHeader {{
        font-weight: bold;
        color: {c["text_main"]};
        background: transparent;
    }}

    QLabel#audioDropTip {{
        background-color: #162033;
        color: {c["text_secondary"]};
        border: 1px solid {c["border_soft"]};
        border-radius: 8px;
        padding: 4px 8px;
    }}

    QLabel#audioDropIcon {{
        font-size: 28px;
        font-weight: bold;
        color: {c["text_secondary"]};
        background: transparent;
    }}

    QLabel#audioDropMain {{
        font-size: 20px;
        font-weight: bold;
        color: {c["text_main"]};
        background: transparent;
    }}

    QLabel#audioDropSub, QLabel#audioDropPath {{
        color: {c["text_secondary"]};
        background: transparent;
    }}

    QMessageBox {{
        background-color: {c["bg_card"]};
        color: {c["text_main"]};
    }}

    QPushButton#audioIconButton {{
    background-color: transparent;
    border: 1px solid {c["border"]};
    border-radius: {s["radius_medium"]}px;
    padding: 0px;
    }}

    QPushButton#audioIconButton:hover {{
        background-color: #1B2432;
        border: 1px solid {c["border_soft"]};
    }}

    QPushButton#audioIconButton:pressed {{
        background-color: #162033;
        border: 1px solid {c["border_active"]};
    }}

    QPushButton#audioLoopButtonOn {{
        background-color: #1B2432;
        border: 1px solid {c["border_soft"]};
        border-radius: {s["radius_medium"]}px;
        padding: 0px;
    }}

    QPushButton#audioLoopButtonOff {{
        background-color: transparent;
        border: 1px solid {c["border"]};
        border-radius: {s["radius_medium"]}px;
        padding: 0px;
    }}

    QPushButton#audioLoopButtonOn:hover,
    QPushButton#audioLoopButtonOff:hover {{
        background-color: #1B2432;
    }}

    QLineEdit#editorInput {{
        background-color: #DCEBFF;
        color: #17345E;
        border: 1px solid #EF4444;
        border-radius: 12px;
        padding: 6px;
    }}

    QTextEdit#editorTextArea {{
        background-color: #DCEBFF;
        color: #17345E;
        border: 1px solid #EF4444;
        border-radius: 12px;
        padding: 6px;
    }}
    """