from typing import cast

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
)

from ui.control_center.control_center_widgets.no_wheel_combo import NoWheelComboBox  # type: ignore
from ui.control_center.config import UI_COLOR, ASSET_PATHS  # type: ignore


def _add_tip(layout: QVBoxLayout, text: str) -> QLabel:
    label = QLabel(text)
    label.setWordWrap(True)
    label.setStyleSheet("color: #9FB3D9;")
    layout.addWidget(label)
    return label

def _asset_icon_label(window, asset_key: str) -> QLabel:
    label = QLabel()
    size = int(window.UI_SIZE.get("basic_audio_label_icon_size", 22))
    path = str(ASSET_PATHS.get(asset_key, "") or "")
    pixmap = QPixmap(path)

    if not pixmap.isNull():
        pixmap = pixmap.scaled(
            size,
            size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        label.setPixmap(pixmap)

    label.setFixedSize(size + 4, size + 4)
    label.setStyleSheet("background: transparent;")
    return label


def _add_audio_label_row(window, layout: QVBoxLayout, text: str, asset_key: str) -> None:
    row = QHBoxLayout()
    row.setSpacing(window.UI_SIZE.get("basic_audio_label_icon_gap", 6))

    text_label = QLabel(text)
    text_label.setStyleSheet(f"color: {UI_COLOR['text_main']}; font-weight: bold;")

    row.addWidget(text_label)
    row.addWidget(_asset_icon_label(window, asset_key))
    row.addStretch()
    layout.addLayout(row)

def _build_audio_device_section(window) -> QFrame:
    card = window.build_section_card("音频设备")
    layout = cast(QVBoxLayout, card.layout())

    window.audio_output_device_combo = NoWheelComboBox()
    window.audio_output_device_combo.addItem("系统默认", None)
    window.audio_output_device_combo.addItem("暂未加载设备", None)
    window.audio_output_device_combo.setMinimumWidth(window.UI_SIZE["basic_audio_combo_min_width"])
    window.audio_output_device_combo.currentIndexChanged.connect(
        window.on_audio_output_device_selected
    )
    _add_audio_label_row(window, layout, "输出设备", "basic.audio_output_icon")
    layout.addWidget(window.audio_output_device_combo)

    window.audio_input_device_combo = NoWheelComboBox()
    window.audio_input_device_combo.addItem("系统默认", None)
    window.audio_input_device_combo.addItem("暂未加载设备", None)
    window.audio_input_device_combo.setMinimumWidth(window.UI_SIZE["basic_audio_combo_min_width"])
    window.audio_input_device_combo.currentIndexChanged.connect(
        window.on_audio_input_device_selected
    )
    window.btn_test_audio_input_device = QPushButton("测试麦克风")
    window.btn_test_audio_input_device.setMinimumWidth(
        window.UI_SIZE["basic_audio_test_button_width"]
    )
    window.btn_test_audio_input_device.clicked.connect(window.test_audio_input_device)
    _add_audio_label_row(window, layout, "输入设备", "basic.audio_input_icon")

    input_row = QHBoxLayout()
    input_row.setSpacing(window.UI_SIZE["spacing_medium"])
    input_row.addWidget(window.audio_input_device_combo, 1)
    input_row.addWidget(window.btn_test_audio_input_device)
    layout.addLayout(input_row)

    window.audio_input_test_frame = QFrame()
    window.audio_input_test_frame.setMinimumHeight(window.UI_SIZE["basic_audio_test_frame_min_height"])
    window.audio_input_test_frame.setMaximumWidth(
        window.UI_SIZE["basic_audio_test_frame_max_width"]
    )
    window.audio_input_test_frame.setStyleSheet(
        "QFrame {"
        f"background-color: {UI_COLOR['basic_audio_test_frame_bg']};"
        f"border: {window.UI_SIZE['basic_audio_test_frame_border_width']}px solid {UI_COLOR['basic_audio_test_frame_border']};"
        f"border-radius: {window.UI_SIZE['basic_audio_test_frame_radius']}px;"
        "}"
    )
    test_layout = QVBoxLayout(window.audio_input_test_frame)
    test_layout.setContentsMargins(
        window.UI_SIZE["spacing_medium"],
        window.UI_SIZE["spacing_medium"],
        window.UI_SIZE["spacing_medium"],
        window.UI_SIZE["spacing_medium"],
    )
    test_layout.setSpacing(window.UI_SIZE["spacing_small"])

    title = QLabel("麦克风输入测试")
    title.setStyleSheet(f"color: {UI_COLOR['text_main']}; font-weight: bold;")
    test_layout.addWidget(title)

    window.audio_input_level_bar = QProgressBar()
    window.audio_input_level_bar.setRange(0, 100)
    window.audio_input_level_bar.setValue(0)
    window.audio_input_level_bar.setTextVisible(False)
    window.audio_input_level_bar.setMinimumWidth(
        window.UI_SIZE["basic_audio_level_bar_width"]
    )
    window.audio_input_level_bar.setFixedHeight(window.UI_SIZE["basic_audio_level_bar_height"])
    test_layout.addWidget(window.audio_input_level_bar)

    window.audio_input_test_status_label = QLabel("当前状态：未测试")
    window.audio_input_test_status_label.setWordWrap(False)
    window.audio_input_test_status_label.setMinimumWidth(0)
    window.audio_input_test_status_label.setStyleSheet(
        f"color: {UI_COLOR['basic_audio_test_status_idle']};"
    )
    test_layout.addWidget(window.audio_input_test_status_label)

    window.audio_input_test_detail_label = QLabel("峰值：-  RMS：-")
    window.audio_input_test_detail_label.setStyleSheet(
        f"color: {UI_COLOR['basic_audio_test_status_idle']};"
    )
    test_layout.addWidget(window.audio_input_test_detail_label)

    window.audio_input_test_frame.setVisible(False)
    layout.addWidget(window.audio_input_test_frame)

    return card


def _build_cleanup_section(window) -> QFrame:
    card = window.build_section_card("项目清扫")
    layout = cast(QVBoxLayout, card.layout())

    button_row = QHBoxLayout()
    button_row.setSpacing(window.UI_SIZE["spacing_medium"])
    window.btn_basic_cleanup_scan = QPushButton("扫描")
    window.btn_basic_cleanup_delete_selected = QPushButton("删除选中")
    window.btn_basic_cleanup_open_folder = QPushButton("打开文件夹")
    window.apply_button_preset(window.btn_basic_cleanup_scan, "refresh")
    window.apply_button_preset(window.btn_basic_cleanup_delete_selected, "delete")
    window.apply_button_preset(window.btn_basic_cleanup_open_folder, "folder")
    window.btn_basic_cleanup_scan.clicked.connect(window.scan_project_cleanup)
    window.btn_basic_cleanup_delete_selected.clicked.connect(window.delete_selected_project_cleanup)
    window.btn_basic_cleanup_open_folder.clicked.connect(window.open_selected_cleanup_folder)
    button_row.addWidget(window.btn_basic_cleanup_scan)
    button_row.addWidget(window.btn_basic_cleanup_delete_selected)
    button_row.addWidget(window.btn_basic_cleanup_open_folder)
    button_row.addStretch()
    layout.addLayout(button_row)

    window.basic_cleanup_category_checks = {}
    window.basic_cleanup_count_labels = {}
    window.basic_cleanup_size_labels = {}
    cleanup_titles = (
        ("downloads", "下载文件"),
        ("favorites", "收藏文件"),
        ("operation_logs", "操作日志"),
        ("history_operations", "历史操作记录"),
        ("temporary_files", "临时文件"),
    )
    for key, label_text in cleanup_titles:
        row = QHBoxLayout()
        row.setSpacing(window.UI_SIZE["spacing_medium"])
        check = QCheckBox(label_text)
        count_label = QLabel("数量：-")
        size_label = QLabel("大小：-")
        count_label.setStyleSheet("color: #B8C7E0;")
        size_label.setStyleSheet("color: #B8C7E0;")
        window.basic_cleanup_category_checks[key] = check
        window.basic_cleanup_count_labels[key] = count_label
        window.basic_cleanup_size_labels[key] = size_label
        row.addWidget(check, 1)
        row.addWidget(count_label)
        row.addWidget(size_label)
        row.addStretch()
        layout.addLayout(row)

    return card


def _build_display_section(window) -> QFrame:
    card = window.build_section_card("显示设置")
    layout = cast(QVBoxLayout, card.layout())
    _add_tip(layout, "设置聊天区中 AI 回复消息的显示名称，不影响模型、角色、语音包或提示词。")

    row = QHBoxLayout()
    row.setSpacing(window.UI_SIZE["spacing_medium"])
    window.chat_assistant_display_name_edit = QLineEdit()
    window.chat_assistant_display_name_edit.setPlaceholderText("AI")
    service = getattr(window, "chat_display_config_service", None)
    if service is not None:
        window.chat_assistant_display_name_edit.setText(service.get_assistant_display_name())

    window.btn_save_chat_display_settings = QPushButton("保存显示设置")
    window.apply_button_preset(window.btn_save_chat_display_settings, "apply")
    window.btn_save_chat_display_settings.setMinimumWidth(150)
    window.btn_save_chat_display_settings.clicked.connect(window.save_chat_display_settings)

    row.addWidget(QLabel("AI 显示名称"))
    row.addWidget(window.chat_assistant_display_name_edit, 1)
    row.addWidget(window.btn_save_chat_display_settings)
    layout.addLayout(row)
    return card


def _build_integrity_section(window) -> QFrame:
    card = window.build_section_card("完整度检查")
    layout = cast(QVBoxLayout, card.layout())
    _add_tip(layout, "检查并创建缺失目录、默认配置和运行目录，不删除任何数据。")

    row = QHBoxLayout()
    row.setSpacing(window.UI_SIZE["spacing_medium"])
    window.btn_run_project_integrity_check = QPushButton("执行完整度检查")
    window.apply_button_preset(window.btn_run_project_integrity_check, "apply")
    window.btn_run_project_integrity_check.setMinimumWidth(150)
    window.btn_run_project_integrity_check.clicked.connect(window.run_project_integrity_check)
    row.addWidget(window.btn_run_project_integrity_check)
    row.addStretch()
    layout.addLayout(row)
    return card


def _build_developer_section(window) -> QFrame:
    card = window.build_section_card("开发者设置")
    layout = cast(QVBoxLayout, card.layout())

    window.basic_developer_mode_status_label = QLabel("当前状态：关闭")
    window.basic_developer_mode_status_label.setWordWrap(True)
    window.basic_developer_mode_status_label.setStyleSheet("color: #B8C7E0;")
    layout.addWidget(window.basic_developer_mode_status_label)
    _add_tip(layout, "开发者模式用于显示测试入口和高级配置项，开启或关闭后需要重启项目生效。")

    row = QHBoxLayout()
    row.setSpacing(window.UI_SIZE["spacing_medium"])
    window.btn_basic_toggle_developer_mode = QPushButton("开启开发者模式")
    window.apply_button_preset(window.btn_basic_toggle_developer_mode, "apply")
    window.btn_basic_toggle_developer_mode.setMinimumWidth(150)
    window.btn_basic_toggle_developer_mode.clicked.connect(window.toggle_developer_mode)
    row.addWidget(window.btn_basic_toggle_developer_mode)
    row.addStretch()
    layout.addLayout(row)
    return card


def _build_restore_section(window) -> QFrame:
    card = window.build_section_card("恢复初始环境")
    layout = cast(QVBoxLayout, card.layout())
    _add_tip(layout, "仅开发者模式：清理记录、记忆、缓存与运行材料，使项目接近首次安装状态。")

    row = QHBoxLayout()
    row.setSpacing(window.UI_SIZE["spacing_medium"])
    window.btn_restore_initial_environment = QPushButton("恢复初始环境")
    window.apply_button_preset(window.btn_restore_initial_environment, "delete")
    window.btn_restore_initial_environment.setMinimumWidth(150)
    window.btn_restore_initial_environment.clicked.connect(window.restore_initial_environment)
    row.addWidget(window.btn_restore_initial_environment)
    row.addStretch()
    layout.addLayout(row)

    window.basic_restore_initial_environment_card = card
    return card


def build_basic_settings_page(window) -> QFrame:
    page = QFrame()
    page.setObjectName("pageCard")

    layout = QVBoxLayout(page)
    layout.setContentsMargins(
        window.UI_SIZE["page_model_margin"],
        window.UI_SIZE["page_model_margin"],
        window.UI_SIZE["page_model_margin"],
        window.UI_SIZE["page_model_margin"],
    )
    layout.setSpacing(window.UI_SIZE["spacing_large"])

    title = QLabel("基础设置")
    title.setStyleSheet(
        f"font-size: {window.UI_SIZE['font_page_title']}px; font-weight: bold;"
    )
    layout.addWidget(title)
    _add_tip(layout, "系统基础设置：音频输入输出、项目清扫、完整度检查与开发者维护入口。")

    layout.addWidget(_build_audio_device_section(window))
    layout.addWidget(_build_display_section(window))
    layout.addWidget(_build_cleanup_section(window))
    layout.addWidget(_build_integrity_section(window))
    layout.addWidget(_build_developer_section(window))
    layout.addWidget(_build_restore_section(window))
    layout.addStretch()

    if hasattr(window, "refresh_developer_mode_section"):
        window.refresh_developer_mode_section()

    return page
