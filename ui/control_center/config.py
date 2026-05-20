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
    "window_width": 980,
    "window_height": 1080,
    "window_min_width": 560,
    "window_min_height": 900,

    # -------------------------
    # 顶部栏 / 导航
    # -------------------------
    "top_bar_height": 56,
    "top_bar_outer_height": 66,
    "top_bar_margin_h": 14,
    "top_bar_margin_v": 10,

    "nav_width": 160,
    "nav_margin": 10,
    "nav_width_expanded": 176,
    "nav_width_collapsed": 72,
    "nav_header_height": 64,
    "nav_group_title_height": 28,
    "nav_group_icon_size": 22,
    "nav_toggle_btn_size": 28,
    "nav_item_height": 46,
    "nav_group_spacing": 8,
    "nav_section_spacing": 10,
    # -------------------------
    # 页面内容边距
    # -------------------------
    "page_inner_margin": 16,
    "page_section_margin": 12,
    "page_model_margin": 18,

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

    "scheme_display_height": 120,
    "tts_loading_gif_size": 42,

    # -------------------------
    # 标签
    # -------------------------
    "summary_line_height": 24,
    "section_title_height": 24,

    "status_dot_width": 20,
    "slider_label_width": 70,
    "slider_value_width": 36,

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

CONTROL_CENTER_STARTUP = {
    # 控制中心首次打开时的窗口宽度比例
    # 数值越大，窗口初始越宽
    "width_ratio": 0.42,

    # 控制中心首次打开时的窗口高度比例
    # 数值越大，窗口初始越高
    "height_ratio": 0.88,

    # 控制中心首次打开时的最小宽度
    # 即使屏幕很大，也不会小于这个值
    "min_width": 980,

    # 控制中心首次打开时的最小高度
    "min_height": 1080,

    # True = 默认靠屏幕右侧打开
    # False = 默认居中打开
    "prefer_right_side": True,

    # 顶部预留距离
    "top_margin": 20,
}

DESKTOP_UI_SIZE = {
    # ===== 桌面页整体边距 =====
    "desktop_page_margin": 18,

    # ===== 尺寸调试 badge =====
    "desktop_debug_badge_radius": 7,
    "desktop_debug_badge_border_width": 1,
    "desktop_debug_badge_padding_v": 1,
    "desktop_debug_badge_padding_h": 9,
    "desktop_debug_badge_font_size": 11,
    "desktop_debug_pressure_min_width": 140,

    # ===== 文件治理区外层卡片 =====
    # 只读模式边框粗细
    "file_card_border_width_readonly": 3,
    # 可编辑模式边框粗细
    "file_card_border_width_editable": 2,
    # 文件治理区外层圆角
    "file_card_border_radius": 12,

    # 文件治理区整体最大宽度
    # 0 = 不限制最大宽度
    # 如果你要固定成 722，这里要写 722
    "file_card_max_width": 0,

    # 文件治理区整体最小宽度
    # 如果你要固定成 722，这里也写 722
    "file_card_min_width": 680,

    # ===== 文件治理区顶部“只读”切换按钮 =====
    "file_toggle_border_radius": 10,
    "file_toggle_border_width": 2,
    "file_toggle_padding_v": 6,
    "file_toggle_padding_h": 14,

    # ===== 表格最小高度 =====
    "disk_table_min_height": 353,
    "file_table_min_height": 550,

    # ===== 上层磁盘表默认列宽（默认值，不一定是运行时实际值）=====
    "disk_column_width_name": 180,
    "disk_column_width_status": 200,
    "disk_column_width_bool": 140,

    # ===== 下层对象表默认列宽（默认值，不一定是运行时实际值）=====
    "file_column_width_enabled": 90,
    "file_column_width_name": 240,
    "file_column_width_path": 160,
    "file_column_width_open": 76,
    "file_column_width_manage": 150,
    "file_column_width_type": 72,
    "file_column_width_status": 96,
    "file_column_width_permission": 96,

    # ===== 软件治理区默认列宽 =====
    "software_column_width_icon": 80,
    "software_column_width_name": 200,
    "software_column_width_permission": 96,
    "software_column_width_actions": 620,
    "software_column_width_path": 380,
    "software_column_width_status": 190,
    "software_column_width_clear": 90,
    "software_column_width_locate": 72,
    "software_path_min_width": 420,
    "software_action_button_width": 48,
    "software_action_button_height": 30,
    "software_action_button_width_small": 64,
    "software_action_button_width_medium": 90,
    "software_action_button_width_large": 106,
    "software_action_button_height_small": 30,
    "software_action_button_height_medium": 36,
    "software_action_button_height_large": 40,
    "software_action_button_spacing": 8,

    # ===== 结果区最小高度 =====
    "software_table_min_height": 780,
    "software_icon_size": 26,
    "readonly_result_min_height": 280,
    "sandbox_result_min_height": 280,

    # ===== 文件治理区内部上下区域间距 =====
    "file_top_spacing": 12,
    "file_bottom_spacing": 8,
    "toolbar_spacing_top": 8,
    "toolbar_spacing_bottom": 10,

    # ===== 表格通用外观 =====
    "desktop_table_border_radius": 14,
    "desktop_table_border_width": 1,
    "desktop_table_item_separator_width": 1,
    "desktop_table_header_separator_width": 1,
    "desktop_table_padding": 6,
    "desktop_table_item_padding_v": 6,
    "desktop_table_item_padding_h": 10,

    # 表头上下 / 左右内边距
    # 左右内边距越大，表头文字可显示空间越小
    "desktop_table_header_padding_v": 15,
    "desktop_table_header_padding_h": 22,

    # ===== 表格行高 =====
    "disk_row_height": 56,
    "file_row_height": 52,
    "software_row_height": 58,

    # ===== 上层左侧盘名按钮样式 =====
    "disk_name_button_padding_v": 10,
    "disk_name_button_padding_h": 20,
    "disk_name_button_min_height": 42,
    "disk_name_button_radius": 8,
    "disk_name_button_border_width": 2,

    # ===== 状态框样式（未设定 / 允许 / 仅一次 / 禁止）=====
    "status_badge_padding_v": 6,
    "status_badge_padding_h": 12,
    "status_badge_min_height": 32,
    "status_badge_radius": 8,
    "status_badge_border_width": 1,

    # ===== 上层“是 / 否”切换按钮样式 =====
    "toggle_button_padding_v": 7,
    "toggle_button_padding_h": 14,
    "toggle_button_min_height": 28,
    "toggle_button_radius": 8,
    "toggle_button_border_width": 1,

    # ===== 桌面连接：主模式按钮（不启用 / 限制模式 / 信任模式）=====
    "desktop_mode_button_padding_v": 8,
    "desktop_mode_button_padding_h": 18,
    "desktop_mode_button_min_height": 36,
    "desktop_mode_button_radius": 10,
    "desktop_mode_button_border_width": 1,

    # ===== 桌面连接：测试模式 / 测试出口按钮 =====
    "desktop_test_button_padding_v": 8,
    "desktop_test_button_padding_h": 18,
    "desktop_test_button_min_height": 36,
    "desktop_test_button_radius": 10,
    "desktop_test_button_border_width": 1,

    # ===== 桌面连接：测试出口/少府所在行 =====
    "desktop_test_backend_row_margin_l": 0,
    "desktop_test_backend_row_margin_t": 0,
    "desktop_test_backend_row_margin_r": 0,
    "desktop_test_backend_row_margin_b": 0,

    # ===== 下层名称蓝框样式 =====
    "name_cell_padding_v": 8,
    "name_cell_padding_h": 10,
    "name_cell_radius": 7,
    "name_cell_border_width": 1,

    # ===== 下层权限按钮样式 =====
    "permission_button_padding_v": 7,
    "permission_button_padding_h": 14,
    "permission_button_min_height": 28,
    "permission_button_radius": 8,
    "permission_button_border_width": 1,

    # ===== 下层动作按钮样式（如“进入下级”）=====
    "action_button_padding_v": 7,
    "action_button_padding_h": 14,
    "action_button_min_height": 28,
    "action_button_radius": 8,
    "action_button_border_width": 1,

    # ===== 桌面页字体档位 =====
    "desktop_font_small": 10,
    "desktop_font_medium": 12,
    "desktop_font_large": 15,

    "desktop_toolbar_icon_size": 22,
    "desktop_table_button_icon_size": 20,
    "desktop_scan_loading_icon_size": 28,
    
    "desktop_icon_button_size": 44,
    "desktop_table_icon_button_size": 40,
    
    "file_action_button_font_size": 16,
    "file_action_button_font_size_large": 17,
    "file_action_button_width": 96,
    "file_action_button_height": 40,
    "file_manage_button_spacing": 6,
    "file_manage_button_width": 66,
    "file_manage_button_height": 34,
    "file_manage_icon_size": 24,

    "software_toolbar_button_icon_size": 22,
    "software_clear_button_icon_size": 22,
    "software_hide_button_icon_size": 20,
    # 软件治理区扫描按钮
    "software_scan_button_size": 44,
    "software_quick_scan_icon_size": 28,
    "software_full_scan_icon_size": 30,
    "software_scan_feedback_icon_size": 42,
    "software_scan_progress_min_width": 220,
    "software_scan_progress_height": 16,
}
DESKTOP_LAYOUT_BREAKPOINTS = {
    "compact_max": 980,
    "normal_max": 1360,
}
UI_SIZE.update({
    # ===== 左侧导航整体 =====
    "nav_width_expanded": 188,
    "nav_width_collapsed": 92,
    "nav_header_height": 76,
    "nav_header_title_gap": 6,

    # ===== 左侧导航主按钮 =====
    "nav_button_height": 62,
    "nav_button_radius": 16,
    "nav_button_border_width": 1,
    "nav_button_text_font_size": 16,
    "nav_button_icon_size": 26,

    # ===== 左侧导航按钮背景绘制 =====
    "nav_button_draw_base": False,
    "nav_button_draw_border": False,

    "nav_button_base_padding_h": 4,
    "nav_button_base_padding_v": 0,
    "nav_button_image_padding_h": 0,
    "nav_button_image_padding_v": 0,
    "nav_button_image_y_offset": 10,

    "nav_button_image_alpha_threshold": 8,
    "nav_button_image_white_threshold": 245,
    "nav_button_image_crop_extra": 8,
    # ===== 折叠态分组按钮 =====
    "nav_collapsed_button_size": 64,
    "nav_collapsed_icon_size": 28,

    # ===== 缩进 / 展开按钮 =====
    "nav_toggle_button_size": 64,
    "nav_toggle_icon_size": 46,
    "nav_toggle_radius": 16,
    "nav_toggle_border_width": 1,
    "nav_toggle_show_background": False,

    "basic_audio_label_icon_size": 22,
    "basic_audio_label_icon_gap": 6,
})
UI_SIZE.update({
    # ===== 基础设置：音频设备 =====
    "basic_audio_test_button_width": 120,
    "basic_audio_test_play_button_width": 140,
    "basic_audio_combo_min_width": 360,
    "basic_audio_level_bar_width": 360,
    "basic_audio_level_bar_height": 18,
    "basic_audio_level_block_count": 20,
    "basic_audio_test_frame_min_height": 92,
    "basic_audio_test_update_ms": 100,
    "basic_audio_test_frame_max_width": 680,
    "basic_audio_test_frame_border_width": 1,
    "basic_audio_test_frame_radius": 8,
})

DESKTOP_LAYOUT_PRESETS = {
    "compact": {
        # ===== 上层磁盘表 =====
        # 三个“允许...”列共用宽度
        "disk_column_width_bool": 92,

        # 盘名列最小宽度
        "disk_name_min": 180,

        # 状态列最小宽度
        "disk_status_min": 220,

        # ===== 下层对象表固定列 =====
        # “启用”列宽
        "file_column_width_enabled": 72,

        # “打开”列宽
        "file_column_width_open": 76,

        # “管理”列宽
        "file_column_width_manage": 142,

        # “类型”列宽
        "file_column_width_type": 66,

        # “状态”列宽
        "file_column_width_status": 74,

        # “权限”列宽
        "file_column_width_permission": 74,

        # ===== 下层对象表弹性列最小宽度 =====
        # 名称列最小宽度
        "file_name_min": 260,

        # 路径列最小宽度
        "file_path_min": 420,

        # ===== 行高 =====
        "disk_row_height": 54,
        "file_row_height": 48,

        # ===== 表头内边距 =====
        # 上下 padding
        "desktop_table_header_padding_v": 13,
        # 左右 padding，越大越挤字
        "desktop_table_header_padding_h": 14,
    },

    "normal": {
        "disk_column_width_bool": 96,
        "disk_name_min": 220,
        "disk_status_min": 300,

        "file_column_width_enabled": 82,
        "file_column_width_open": 80,
        "file_column_width_manage": 150,
        "file_column_width_type": 72,
        "file_column_width_status": 86,
        "file_column_width_permission": 86,

        "file_name_min": 220,
        "file_path_min": 320,

        "disk_row_height": 56,
        "file_row_height": 52,

        "desktop_table_header_padding_v": 15,
        "desktop_table_header_padding_h": 22,
    },

    "wide": {
        "disk_column_width_bool": 96,
        "disk_name_min": 260,
        "disk_status_min": 420,

        "file_column_width_enabled": 88,
        "file_column_width_open": 84,
        "file_column_width_manage": 164,
        "file_column_width_type": 84,
        "file_column_width_status": 96,
        "file_column_width_permission": 96,

        "file_name_min": 260,
        "file_path_min": 420,

        "disk_row_height": 60,
        "file_row_height": 56,

        "desktop_table_header_padding_v": 16,
        "desktop_table_header_padding_h": 24,
    },
}
BASE_DIR = Path(__file__).resolve().parents[1]   # 指向 ui

ASSET_PATHS = {
    # ===== 保留磁盘路径：GIF/loading 类资源 =====
    "tts.loading_gif": str(BASE_DIR / "assets" / "loading" / "tts.loading.gif"),

    # ===== 第三页播放器图标 =====
    "player.play": str(BASE_DIR / "assets" / "启动.png"),
    "player.pause": str(BASE_DIR / "assets" / "暂停.png"),
    "player.loop": str(BASE_DIR / "assets" / "循环播放.png"),

    # ===== 左侧导航图片按钮 =====
    "nav.group_system": str(BASE_DIR / "assets" / "系统.png"),
    "nav.group_voice": str(BASE_DIR / "assets" / "语音消息.png"),
    "nav.button_bg": str(BASE_DIR / "assets" / "透明蓝紫色.png"),
    "nav.toggle_crystal_bg": str(BASE_DIR / "assets" / "蓝色水晶边框.png"),
    "nav.toggle_expand_icon": str(BASE_DIR / "assets" / "右拉出.png"),
    "nav.toggle_collapse_icon": str(BASE_DIR / "assets" / "左缩进.png"),
}

ASSET_PATHS.update({
    # 桌面连接页先继续走磁盘路径
    "desktop.loading_gif": str(BASE_DIR / "assets" / "loading" / "加载.gif"),
    "desktop.clear_gif": str(BASE_DIR / "assets" / "loading" / "清理.gif"),

    "desktop.rename_icon": str(BASE_DIR / "assets" / "重命名.png"),
    "desktop.delete_icon": str(BASE_DIR / "assets" / "删除名片.png"),

    "desktop.quick_scan_gif": str(BASE_DIR / "assets" / "loading" / "目标扫描.gif"),
    "desktop.full_scan_gif": str(BASE_DIR / "assets" / "loading" / "扫描雷达.gif"),
    "desktop.scan_feedback_gif": str(BASE_DIR / "assets" / "loading" / "兔子散步.gif"),
    "desktop.hide_icon": str(BASE_DIR / "assets" / "loading" / "隐藏.png"),

    "desktop.back_icon": str(BASE_DIR / "assets" / "loading" / "返回.png"),
    "desktop.forward_icon": str(BASE_DIR / "assets" / "loading" / "向前.png"),

    "desktop.root_icon": str(BASE_DIR / "assets" / "loading" / "根目录.png"),
    "desktop.scan_icon": str(BASE_DIR / "assets" / "loading" / "扫描.png"),

    "basic.audio_output_icon": str(BASE_DIR / "assets" / "耳机.png"),
    "basic.audio_input_icon": str(BASE_DIR / "assets" / "麦克风.png"),
})
def software_scan_image_button_qss() -> str:
    """
    软件治理区扫描图片按钮样式。

    作用：
    - 去掉普通按钮蓝色底
    - 只显示图片/GIF
    - hover/pressed 保留轻微反馈
    - disabled 保持灰色状态
    """
    return """
    QPushButton {
        background: transparent;
        border: none;
        padding: 0px;
        margin: 0px;
    }
    QPushButton:hover {
        background: rgba(255, 255, 255, 0.08);
        border-radius: 8px;
    }
    QPushButton:pressed {
        background: rgba(255, 255, 255, 0.14);
        border-radius: 8px;
    }
    QPushButton:disabled {
        background: transparent;
        border: none;
    }
    """
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

    "status_idle": "#EAB308",
    "status_ready": "#22C55E",
    "status_error": "#EF4444",
    "loading_text": "#DCE8FF",
    "loading_percent": "#9FB3D9",

    "page_desc": "#9FB3D9",

    "reference_toggle_on_bg": "#1E3A2F",
    "reference_toggle_on_border": "#4ADE80",
    "reference_toggle_off_bg": "#3A1E1E",
    "reference_toggle_off_border": "#F87171",

    # ===== 左侧导航图片按钮绘制颜色 =====
    "nav_button_text": "#FFFFFF",

    # 真正的完整按钮底色
    "nav_button_base_bg": "#101820",
    "nav_button_base_bg_checked": "#142238",
    "nav_button_base_bg_hover": "#16263A",

    # 图片读取失败时的备用底色
    "nav_button_fallback_bg": "#182A3D",

    # 边框颜色
    "nav_button_border_normal": "#2E405A",
    "nav_button_border_hover": "#8BB8FF",
    "nav_button_border_active": "#3A8DFF",
    "nav_button_border_checked": "#8BB8FF",

    # ===== 缩进 / 展开按钮绘制颜色 =====
    "nav_toggle_fallback_bg": "#348DFF",
    "nav_toggle_border_hover": "#8BB8FF",
    "nav_toggle_border_active": "#3A8DFF",
}
UI_COLOR.update({
    # ===== 基础设置：麦克风测试 =====
    "basic_audio_level_idle": "#3A4150",
    "basic_audio_level_low": "#4D8DFF",
    "basic_audio_level_mid": "#31C96B",
    "basic_audio_level_high": "#FFB020",
    "basic_audio_level_clip": "#FF4D4F",
    "basic_audio_test_status_idle": "#B8C7E0",
    "basic_audio_test_status_active": "#31C96B",
    "basic_audio_test_status_silent": "#FFB020",
    "basic_audio_test_status_error": "#FF4D4F",
    "basic_audio_test_frame_bg": "#101820",
    "basic_audio_test_frame_border": "#33445F",
})

DESKTOP_UI_COLOR = {
    "file_card_readonly_border": "#EF4444",
    "file_card_readonly_bg": "rgba(42, 22, 26, 0.92)",
    "file_card_editable_border": "#22C55E",
    "file_card_editable_bg": "rgba(18, 42, 32, 0.94)",
    "software_card_readonly_border": "#EF4444",
    "software_card_readonly_bg": "rgba(42, 22, 26, 0.92)",
    "software_card_editable_border": "#22C55E",
    "software_card_editable_bg": "rgba(18, 42, 32, 0.94)",
    "file_toggle_readonly_border": "#EF4444",
    "file_toggle_readonly_bg": "rgba(54, 26, 30, 0.95)",
    "file_toggle_editable_border": "#22C55E",
    "file_toggle_editable_bg": "rgba(20, 58, 42, 0.96)",
    "software_toggle_readonly_border": "#EF4444",
    "software_toggle_readonly_bg": "rgba(54, 26, 30, 0.95)",
    "software_toggle_editable_border": "#22C55E",
    "software_toggle_editable_bg": "rgba(20, 58, 42, 0.96)",
    "bool_yes_text": "#86EFAC",
    "bool_yes_border": "#22C55E",
    "bool_no_text": "#FCA5A5",
    "bool_no_border": "#7F1D1D",
    "bool_button_bg": "rgba(13, 20, 32, 0.96)",
    "bool_button_disabled_text": "#6B7280",
    "bool_button_disabled_border": "#4B5563",
    "file_hint_readonly_text": "#A7B0C0",
    "file_hint_editable_text": "#D6F5E1",
    "file_table_readonly_bg": "rgba(8, 12, 20, 0.90)",
    "file_table_readonly_hover": "rgba(54, 26, 30, 0.45)",
    "file_table_editable_bg": "rgba(12, 24, 20, 0.92)",
    "file_table_editable_hover": "rgba(34, 197, 94, 0.16)",
    # ===== 桌面连接：总览区文字 =====
    "desktop_overview_text": "#B8C7E0",
    "desktop_overview_tip_text": "#9FB3D9",
    "desktop_test_backend_label_text": "#DCE6FA",

    # ===== 桌面连接：测试出口/少府所在行 =====
    # transparent = 继承总览区背景
    "desktop_test_backend_row_bg": "transparent",
    "desktop_test_backend_row_border": "none",

    # ===== 桌面连接：正式主模式按钮 =====
    "desktop_mode_button_bg": "#3A8DFF",
    "desktop_mode_button_bg_checked": "#4C84EC",
    "desktop_mode_button_bg_hover": "#5A96FF",
    "desktop_mode_button_border": "#3A8DFF",
    "desktop_mode_button_border_checked": "#93C5FD",
    "desktop_mode_button_text": "#FFFFFF",

    "desktop_mode_button_disabled_bg": "#4A4A4A",
    "desktop_mode_button_disabled_border": "#4A4A4A",
    "desktop_mode_button_disabled_text": "#BFBFBF",

    # ===== 桌面连接：测试模式 / 测试出口按钮 =====
    "desktop_test_button_bg": "rgba(13, 20, 32, 0.96)",
    "desktop_test_button_on_border": "#22C55E",
    "desktop_test_button_on_text": "#86EFAC",
    "desktop_test_button_off_border": "#7F1D1D",
    "desktop_test_button_off_text": "#FCA5A5",
    "desktop_test_button_disabled_border": "#4B5563",
    "desktop_test_button_disabled_text": "#6B7280",

    # ===== 桌面连接：VM 测试按钮连接中/异常 =====
    "desktop_vm_button_pending_border": "#FACC15",
    "desktop_vm_button_pending_text": "#FDE68A",
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
    }}

    QFrame#navHeaderFrame {{
        background: transparent;
        border: none;
    }}

    QFrame#navGroupFrame {{
        background: transparent;
        border: none;
    }}

    QLabel#navTitleLabel {{
        background: transparent;
        color: {c["text_main"]};
    }}

    QLabel#navGroupTitle {{
        background: transparent;
        color: #9FB3D9;
        font-weight: bold;
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

    QScrollBar:horizontal {{
        background: #182131;
        height: 16px;
        border-radius: 8px;
    }}

    QScrollBar::handle:horizontal {{
        background: {c["primary"]};
        min-width: 52px;
        border-radius: 8px;
    }}

    QScrollBar::add-page:horizontal,
    QScrollBar::sub-page:horizontal {{
        background: #24354D;
        border-radius: 8px;
    }}

    QScrollBar::add-line:horizontal,
    QScrollBar::sub-line:horizontal {{
        width: 0px;
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
