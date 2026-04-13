from typing import cast
from PySide6.QtGui import QMovie
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QHBoxLayout,
    QTextEdit,
)

from ui.control_center.control_center_widgets.no_wheel_combo import NoWheelComboBox # type: ignore
from ui.control_center.config import ASSET_PATHS, UI_COLOR # type: ignore

def _build_status_dot() -> QLabel:
    dot = QLabel("●")
    dot.setFixedWidth(20)
    dot.setStyleSheet(
        f"color: {UI_COLOR['status_idle']}; font-size: 18px; font-weight: bold;"
    )
    return dot

def build_model_page(window) -> QFrame:
    page = QFrame()
    page.setObjectName("pageCard")

    layout = QVBoxLayout(page)
    layout.setContentsMargins(18, 18, 18, 18)
    layout.setSpacing(window.UI_SIZE["spacing_large"] if hasattr(window, "UI_SIZE") else 14)

    # =========================
    # 页面标题
    # =========================
    title = QLabel("运行配置")
    title.setStyleSheet(
        f"font-size: {window.UI_SIZE['font_page_title']}px; font-weight: bold;"
    )
    layout.addWidget(title)

    desc = QLabel("运行层配置：语言模型、语音后端、角色方案与输出模式。")
    desc.setWordWrap(True)
    desc.setStyleSheet("color: #9FB3D9;")
    layout.addWidget(desc)

    # =========================
    # 当前配置总览
    # =========================
    summary_card = window.build_section_card("当前运行总览")
    summary_layout = cast(QVBoxLayout, summary_card.layout())

    window.summary_role_label = QLabel("组合方案：-")
    window.summary_voice_label = QLabel("语音包：-")
    window.summary_role_config_label = QLabel("当前文本模板：-")
    window.summary_voice_config_label = QLabel("当前表现模板：-")
    window.summary_output_mode_label = QLabel("输出模式：-")
    window.summary_model_label = QLabel("语言模型：-")
    window.summary_tts_model_label = QLabel("语音后端：-")

    summary_layout.addWidget(window.summary_role_label)
    summary_layout.addWidget(window.summary_voice_label)
    summary_layout.addWidget(window.summary_role_config_label)
    summary_layout.addWidget(window.summary_voice_config_label)
    summary_layout.addWidget(window.summary_output_mode_label)
    summary_layout.addWidget(window.summary_model_label)
    summary_layout.addWidget(window.summary_tts_model_label)

    # =========================
    # 模型设置
    # =========================
    model_card = window.build_section_card("模型设置")
    model_layout = cast(QVBoxLayout, model_card.layout())

    # -------- 语言模型 --------
    window.chat_model_combo = NoWheelComboBox()
    window.chat_model_combo.currentIndexChanged.connect(window.on_model_page_selection_changed)

    window.btn_refresh_models = QPushButton("刷新")
    window.btn_apply_chat_model = QPushButton("应用")

    window.apply_button_preset(window.btn_refresh_models, "refresh")
    window.apply_button_preset(window.btn_apply_chat_model, "apply")

    window.btn_refresh_models.clicked.connect(window.reload_model_list)
    window.btn_apply_chat_model.clicked.connect(window.apply_chat_model_selection)

    model_layout.addWidget(QLabel("语言模型"))
    row_chat = QHBoxLayout()
    row_chat.setSpacing(window.UI_SIZE["spacing_medium"])
    row_chat.addWidget(window.chat_model_combo, 1)
    row_chat.addWidget(window.btn_refresh_models)
    row_chat.addWidget(window.btn_apply_chat_model)
    model_layout.addLayout(row_chat)

    # -------- 语音模型 --------
    window.tts_backend_status_dot = _build_status_dot()

    window.tts_model_combo = NoWheelComboBox()
    window.tts_model_combo.addItem("GPT-SoVITS", "gpt_sovits")
    window.tts_model_combo.addItem("Edge-TTS", "edge")
    window.tts_model_combo.currentIndexChanged.connect(window.on_tts_model_changed)

    window.btn_refresh_tts_models = QPushButton("刷新")
    window.btn_apply_tts_backend = QPushButton("应用")

    window.apply_button_preset(window.btn_refresh_tts_models, "refresh")
    window.apply_button_preset(window.btn_apply_tts_backend, "apply")

    window.btn_refresh_tts_models.clicked.connect(window.refresh_tts_backend_status)
    window.btn_apply_tts_backend.clicked.connect(window.apply_tts_backend_selection)

    model_layout.addWidget(QLabel("语音模型"))
    row_tts = QHBoxLayout()
    row_tts.setSpacing(window.UI_SIZE["spacing_medium"])
    row_tts.addWidget(window.tts_backend_status_dot, 0)
    row_tts.addWidget(window.tts_model_combo, 1)
    row_tts.addWidget(window.btn_refresh_tts_models)
    row_tts.addWidget(window.btn_apply_tts_backend)
    model_layout.addLayout(row_tts)

    # ===== 行内加载区（默认隐藏）=====
    window.tts_loading_frame = QFrame()
    window.tts_loading_frame.setVisible(False)

    tts_loading_layout = QHBoxLayout(window.tts_loading_frame)
    tts_loading_layout.setContentsMargins(28, 4, 0, 0)
    tts_loading_layout.setSpacing(10)

    window.tts_loading_gif_label = QLabel()
    window.tts_loading_gif_label.setFixedSize(42, 42)
    window.tts_loading_gif_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

    window.tts_loading_movie = QMovie(ASSET_PATHS["tts.loading_gif"])
    window.tts_loading_movie.setScaledSize(window.tts_loading_gif_label.size())
    window.tts_loading_gif_label.setMovie(window.tts_loading_movie)

    text_col = QVBoxLayout()
    text_col.setContentsMargins(0, 0, 0, 0)
    text_col.setSpacing(2)

    window.tts_loading_text_label = QLabel("正在加载语音后端…")
    window.tts_loading_text_label.setStyleSheet( f"color: {UI_COLOR['loading_text']}; font-weight: bold;")

    window.tts_loading_percent_label = QLabel("0%")
    window.tts_loading_percent_label.setStyleSheet(f"color: {UI_COLOR['loading_percent']};")

    text_col.addWidget(window.tts_loading_text_label)
    text_col.addWidget(window.tts_loading_percent_label)

    tts_loading_layout.addWidget(window.tts_loading_gif_label, 0)
    tts_loading_layout.addLayout(text_col, 1)
    tts_loading_layout.addStretch()

    model_layout.addWidget(window.tts_loading_frame)

    # -------- 组合方案 --------
    window.combo_scheme_combo = NoWheelComboBox()
    window.combo_scheme_combo.currentIndexChanged.connect(window.on_model_page_selection_changed)

    window.btn_refresh_combo_schemes = QPushButton("刷新")
    window.btn_apply_combo_scheme = QPushButton("应用")

    window.apply_button_preset(window.btn_refresh_combo_schemes, "refresh")
    window.apply_button_preset(window.btn_apply_combo_scheme, "apply")

    window.btn_refresh_combo_schemes.clicked.connect(window.reload_scheme_list)
    window.btn_apply_combo_scheme.clicked.connect(window.apply_combo_scheme_selection)

    model_layout.addWidget(QLabel("组合方案"))
    row_role = QHBoxLayout()
    row_role.setSpacing(window.UI_SIZE["spacing_medium"])
    row_role.addWidget(window.combo_scheme_combo, 1)
    row_role.addWidget(window.btn_refresh_combo_schemes)
    row_role.addWidget(window.btn_apply_combo_scheme)
    model_layout.addLayout(row_role)

    # =========================
    # 运行设置
    # =========================
    scheme_card = window.build_section_card("运行设置")
    scheme_layout = cast(QVBoxLayout, scheme_card.layout())

    window.current_scheme_display = QTextEdit()
    window.current_scheme_display.setReadOnly(True)
    window.current_scheme_display.setObjectName("schemeDisplay")
    window.add_labeled_widget(scheme_layout, "当前方案", window.current_scheme_display)
    window.current_scheme_display.setFixedHeight(120)

    window.output_mode_combo = NoWheelComboBox()
    window.output_mode_combo.addItem("仅文字", "text_only")
    window.output_mode_combo.addItem("文字+语音", "text_voice")
    window.output_mode_combo.addItem("仅语音", "voice_only")
    window.output_mode_combo.currentIndexChanged.connect(window.on_output_mode_changed_in_model_page)
    window.add_labeled_widget(scheme_layout, "输出模式", window.output_mode_combo)

    window.async_voice_label = QLabel("异步语音")
    window.async_voice_label.setStyleSheet("font-weight: bold; color: #FFFFFF;")
    window.async_voice_label.setFixedHeight(window.UI_SIZE["section_title_height"])
    scheme_layout.addWidget(window.async_voice_label)

    window.async_voice_combo = NoWheelComboBox()
    window.async_voice_combo.addItem("关闭", False)
    window.async_voice_combo.addItem("开启", True)
    window.async_voice_combo.currentIndexChanged.connect(window.on_model_page_selection_changed)
    window.async_voice_combo.setFixedHeight(window.UI_SIZE["input_min_height"])
    scheme_layout.addWidget(window.async_voice_combo)

    # =========================
    # 底部按钮
    # =========================
    btn_row = QHBoxLayout()
    btn_row.setSpacing(window.UI_SIZE["spacing_medium"] if hasattr(window, "UI_SIZE") else 10)

    window.btn_refresh_runtime_files = QPushButton("刷新文件")
    window.btn_apply_model = QPushButton("应用当前配置")
    window.btn_save_model = QPushButton("保存为默认启动")

    window.apply_button_preset(window.btn_refresh_runtime_files, "refresh_long")
    window.apply_button_preset(window.btn_apply_model, "apply")
    window.apply_button_preset(window.btn_save_model, "save")

    window.btn_refresh_runtime_files.clicked.connect(window.load_current_state)
    window.btn_apply_model.clicked.connect(window.apply_model_page)
    window.btn_save_model.clicked.connect(window.save_model_page_default)

    btn_row.addWidget(window.btn_refresh_runtime_files)
    btn_row.addWidget(window.btn_apply_model)
    btn_row.addWidget(window.btn_save_model)
    btn_row.addStretch()

    layout.addWidget(summary_card)
    layout.addWidget(model_card)
    layout.addWidget(scheme_card)
    layout.addStretch()
    layout.addLayout(btn_row)

    if hasattr(window, "update_model_page_mode_visibility"):
        window.update_model_page_mode_visibility()

    return page