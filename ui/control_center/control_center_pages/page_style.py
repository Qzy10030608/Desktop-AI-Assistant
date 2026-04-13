from typing import cast

from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QHBoxLayout,
    QLineEdit,
    QTextEdit,
)

from ui.control_center.control_center_widgets.no_wheel_combo import NoWheelComboBox  # type: ignore


def build_style_page(window) -> QFrame:
    page = QFrame()
    page.setObjectName("pageCard")

    layout = QVBoxLayout(page)
    layout.setContentsMargins(18, 18, 18, 18)
    layout.setSpacing(window.UI_SIZE["spacing_large"])

    # =========================
    # 页面标题
    # =========================
    title = QLabel("风格设计")
    title.setStyleSheet(
        f"font-size: {window.UI_SIZE['font_page_title']}px; font-weight: bold;"
    )
    layout.addWidget(title)

    desc = QLabel("模板层配置：文本风格模板 + 语音表现模板。第二页只编辑模板，不直接组成最终角色，也不在这里做语音测试。")
    desc.setWordWrap(True)
    desc.setStyleSheet("color: #9FB3D9;")
    layout.addWidget(desc)

    # =========================================================
    # 一、文本模板区（上）
    # =========================================================
    text_card = window.build_section_card("文本风格模板")
    text_layout = cast(QVBoxLayout, text_card.layout())

    window.current_style_config_combo = NoWheelComboBox()
    window.current_style_config_combo.currentIndexChanged.connect(
        lambda: window.on_style_profile_selected()
    )
    window.add_labeled_widget(text_layout, "文本模板列表", window.current_style_config_combo)

    window.role_config_name_edit = QLineEdit()
    window.role_config_name_edit.setPlaceholderText("请输入文本模板名称")
    window.role_config_name_edit.textChanged.connect(window.on_style_page_changed)
    window.add_labeled_widget(text_layout, "配置名称", window.role_config_name_edit)

    window.text_scene_combo = NoWheelComboBox()
    window.text_scene_combo.addItem("日常聊天", "daily")
    window.text_scene_combo.addItem("安慰陪伴", "comfort")
    window.text_scene_combo.addItem("解释说明", "explain")
    window.text_scene_combo.addItem("轻互动", "light")
    window.text_scene_combo.currentIndexChanged.connect(window.on_text_scene_changed)
    window.add_labeled_widget(text_layout, "场景类型", window.text_scene_combo)

    text_row_1 = QHBoxLayout()
    text_row_1.setSpacing(window.UI_SIZE["spacing_medium"])

    window.reply_mode_combo = NoWheelComboBox()
    window.reply_mode_combo.addItem("直接", "direct")
    window.reply_mode_combo.addItem("温和", "gentle")
    window.reply_mode_combo.addItem("陪伴", "companion")
    window.reply_mode_combo.addItem("教学", "teaching")
    window.reply_mode_combo.currentIndexChanged.connect(window.on_style_page_changed)

    window.explain_tendency_combo = NoWheelComboBox()
    window.explain_tendency_combo.addItem("低", "low")
    window.explain_tendency_combo.addItem("中", "medium")
    window.explain_tendency_combo.addItem("高", "high")
    window.explain_tendency_combo.currentIndexChanged.connect(lambda: window.set_dirty("style", True))

    window.comfort_tendency_combo = NoWheelComboBox()
    window.comfort_tendency_combo.addItem("低", "low")
    window.comfort_tendency_combo.addItem("中", "medium")
    window.comfort_tendency_combo.addItem("高", "high")
    window.comfort_tendency_combo.currentIndexChanged.connect(lambda: window.set_dirty("style", True))

    window.tone_strength_combo = NoWheelComboBox()
    window.tone_strength_combo.addItem("弱", "low")
    window.tone_strength_combo.addItem("中", "medium")
    window.tone_strength_combo.addItem("强", "high")
    window.tone_strength_combo.currentIndexChanged.connect(lambda: window.set_dirty("style", True))

    for label_text, widget in [
        ("回答方式", window.reply_mode_combo),
        ("解释倾向", window.explain_tendency_combo),
        ("安慰倾向", window.comfort_tendency_combo),
        ("语气强度", window.tone_strength_combo),
    ]:
        col = QVBoxLayout()
        label = QLabel(label_text)
        label.setStyleSheet("font-weight: bold; color: #FFFFFF;")
        label.setFixedHeight(window.UI_SIZE["section_title_height"])
        widget.setFixedHeight(window.UI_SIZE["input_min_height"])
        col.addWidget(label)
        col.addWidget(widget)
        text_row_1.addLayout(col, 1)

    text_layout.addLayout(text_row_1)

    window.catchphrase_edit = QTextEdit()
    window.catchphrase_edit.setPlaceholderText("请输入常用口头禅（可多行）")
    window.catchphrase_edit.textChanged.connect(lambda: window.set_dirty("style", True))
    window.add_labeled_widget(text_layout, "常用口头禅", window.catchphrase_edit)

    window.opening_style_edit = QTextEdit()
    window.opening_style_edit.setPlaceholderText("请输入开头习惯（可多行）")
    window.opening_style_edit.textChanged.connect(lambda: window.set_dirty("style", True))
    window.add_labeled_widget(text_layout, "开头习惯", window.opening_style_edit)

    window.forbidden_edit = QTextEdit()
    window.forbidden_edit.setPlaceholderText("请输入限制词（可多行）")
    window.forbidden_edit.textChanged.connect(lambda: window.set_dirty("style", True))
    window.add_labeled_widget(text_layout, "限制词", window.forbidden_edit)

    text_btn_row = QHBoxLayout()
    text_btn_row.setSpacing(window.UI_SIZE["spacing_medium"])

    window.btn_preview_role_config = QPushButton("文本预览")
    window.btn_load_role_config = QPushButton("刷新列表")
    window.btn_save_role_config = QPushButton("保存文本模板")
    window.btn_reset_role_config = QPushButton("恢复默认")

    window.apply_button_preset(window.btn_preview_role_config, "preview")
    window.apply_button_preset(window.btn_load_role_config, "load")
    window.apply_button_preset(window.btn_save_role_config, "save")
    window.apply_button_preset(window.btn_reset_role_config, "action")

    window.btn_preview_role_config.clicked.connect(window.preview_role_config_text)
    window.btn_load_role_config.clicked.connect(window.reload_style_list)
    window.btn_save_role_config.clicked.connect(window.save_style_page)
    window.btn_reset_role_config.clicked.connect(window.reset_style_page)

    text_btn_row.addWidget(window.btn_preview_role_config)
    text_btn_row.addWidget(window.btn_load_role_config)
    text_btn_row.addWidget(window.btn_save_role_config)
    text_btn_row.addWidget(window.btn_reset_role_config)
    text_btn_row.addStretch()
    text_layout.addLayout(text_btn_row)

    # =========================================================
    # 二、语音表现模板区（下）
    # =========================================================
    voice_card = window.build_section_card("语音表现模板")
    voice_layout = cast(QVBoxLayout, voice_card.layout())

    window.current_voice_config_combo = NoWheelComboBox()
    window.current_voice_config_combo.currentIndexChanged.connect(
        lambda: window.on_voice_profile_selected()
    )
    window.add_labeled_widget(voice_layout, "语音模板列表", window.current_voice_config_combo)

    window.voice_config_name_edit = QLineEdit()
    window.voice_config_name_edit.setPlaceholderText("请输入表现模板名称")
    window.voice_config_name_edit.textChanged.connect(lambda: window.set_dirty("style", True))
    window.add_labeled_widget(voice_layout, "配置名称", window.voice_config_name_edit)

    window.scene_combo = NoWheelComboBox()
    window.scene_combo.addItem("日常聊天", "daily")
    window.scene_combo.addItem("安慰陪伴", "comfort")
    window.scene_combo.addItem("解释说明", "explain")
    window.scene_combo.addItem("轻互动", "light")
    window.scene_combo.currentIndexChanged.connect(window.on_voice_scene_changed)
    window.add_labeled_widget(voice_layout, "场景类型", window.scene_combo)

    voice_row_1 = QHBoxLayout()
    voice_row_1.setSpacing(window.UI_SIZE["spacing_medium"])

    window.emotion_combo = NoWheelComboBox()
    window.emotion_combo.addItem("冷静", "calm")
    window.emotion_combo.addItem("温和", "gentle")
    window.emotion_combo.addItem("活泼", "lively")
    window.emotion_combo.addItem("沉稳", "steady")
    window.emotion_combo.currentIndexChanged.connect(lambda: window.set_dirty("style", True))

    window.emotion_strength_combo = NoWheelComboBox()
    window.emotion_strength_combo.addItem("弱", "low")
    window.emotion_strength_combo.addItem("中", "medium")
    window.emotion_strength_combo.addItem("强", "high")
    window.emotion_strength_combo.currentIndexChanged.connect(lambda: window.set_dirty("style", True))

    window.speed_combo = NoWheelComboBox()
    window.speed_combo.addItem("慢", "slow")
    window.speed_combo.addItem("中", "normal")
    window.speed_combo.addItem("快", "fast")
    window.speed_combo.currentIndexChanged.connect(lambda: window.set_dirty("style", True))

    window.pause_combo = NoWheelComboBox()
    window.pause_combo.addItem("少", "low")
    window.pause_combo.addItem("中", "medium")
    window.pause_combo.addItem("多", "high")
    window.pause_combo.currentIndexChanged.connect(lambda: window.set_dirty("style", True))

    for label_text, widget in [
        ("情绪预设", window.emotion_combo),
        ("情绪强度", window.emotion_strength_combo),
        ("语速", window.speed_combo),
        ("停顿", window.pause_combo),
    ]:
        col = QVBoxLayout()
        label = QLabel(label_text)
        label.setStyleSheet("font-weight: bold; color: #FFFFFF;")
        label.setFixedHeight(window.UI_SIZE["section_title_height"])
        widget.setFixedHeight(window.UI_SIZE["input_min_height"])
        col.addWidget(label)
        col.addWidget(widget)
        voice_row_1.addLayout(col, 1)

    voice_layout.addLayout(voice_row_1)

    voice_row_2 = QHBoxLayout()
    voice_row_2.setSpacing(window.UI_SIZE["spacing_medium"])

    window.intonation_combo = NoWheelComboBox()
    window.intonation_combo.addItem("弱", "weak")
    window.intonation_combo.addItem("中", "normal")
    window.intonation_combo.addItem("强", "strong")
    window.intonation_combo.currentIndexChanged.connect(lambda: window.set_dirty("style", True))

    window.emphasis_combo = NoWheelComboBox()
    window.emphasis_combo.addItem("自然", "natural")
    window.emphasis_combo.addItem("关键词", "keyword")
    window.emphasis_combo.addItem("句首", "start")
    window.emphasis_combo.currentIndexChanged.connect(lambda: window.set_dirty("style", True))

    for label_text, widget in [
        ("起伏感", window.intonation_combo),
        ("重音方式", window.emphasis_combo),
    ]:
        col = QVBoxLayout()
        label = QLabel(label_text)
        label.setStyleSheet("font-weight: bold; color: #FFFFFF;")
        label.setFixedHeight(window.UI_SIZE["section_title_height"])
        widget.setFixedHeight(window.UI_SIZE["input_min_height"])
        col.addWidget(label)
        col.addWidget(widget)
        voice_row_2.addLayout(col, 1)

    voice_row_2.addStretch()
    voice_layout.addLayout(voice_row_2)

    # 模板说明
    tip = QLabel("第二页只保存语音表现模板。试听语音、纯 TTS 测试、再次播放等操作统一放到第三页进行。")
    tip.setWordWrap(True)
    tip.setStyleSheet("color: #9FB3D9;")
    voice_layout.addWidget(tip)

    voice_btn_row = QHBoxLayout()
    voice_btn_row.setSpacing(window.UI_SIZE["spacing_medium"])

    window.btn_load_voice_config = QPushButton("刷新列表")
    window.btn_save_voice_config = QPushButton("保存表现模板")

    window.apply_button_preset(window.btn_load_voice_config, "load")
    window.apply_button_preset(window.btn_save_voice_config, "save")

    window.btn_load_voice_config.clicked.connect(window.reload_voice_list)
    window.btn_save_voice_config.clicked.connect(window.save_style_page)

    voice_btn_row.addWidget(window.btn_load_voice_config)
    voice_btn_row.addWidget(window.btn_save_voice_config)
    voice_btn_row.addStretch()
    voice_layout.addLayout(voice_btn_row)

    bottom_btn_row = QHBoxLayout()
    bottom_btn_row.setSpacing(window.UI_SIZE["spacing_medium"])

    window.btn_apply_style = QPushButton("应用当前页")
    window.btn_open_role_config_folder = QPushButton("打开文本模板文件夹")
    window.btn_open_voice_config_folder = QPushButton("打开表现模板文件夹")

    window.apply_button_preset(window.btn_apply_style, "apply")
    window.apply_button_preset(window.btn_open_role_config_folder, "folder")
    window.apply_button_preset(window.btn_open_voice_config_folder, "folder")

    window.btn_apply_style.clicked.connect(window.apply_style_page)
    window.btn_open_role_config_folder.clicked.connect(window.open_role_config_folder)
    window.btn_open_voice_config_folder.clicked.connect(window.open_voice_config_folder)

    bottom_btn_row.addWidget(window.btn_apply_style)
    bottom_btn_row.addWidget(window.btn_open_role_config_folder)
    bottom_btn_row.addWidget(window.btn_open_voice_config_folder)
    bottom_btn_row.addStretch()

    layout.addWidget(text_card)
    layout.addWidget(voice_card)
    layout.addStretch()
    layout.addLayout(bottom_btn_row)

    return page