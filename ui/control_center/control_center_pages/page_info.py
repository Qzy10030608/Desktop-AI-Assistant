from typing import cast

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QHBoxLayout,
    QLineEdit,
    QTextEdit,
    QSlider,
    QListWidget,
    QListWidgetItem,
)

from ui.control_center.control_center_widgets.no_wheel_combo import NoWheelComboBox  # type: ignore
    

def build_info_page(window) -> QFrame:
    page = QFrame()
    page.setObjectName("pageCard")

    layout = QHBoxLayout(page)
    layout.setContentsMargins(18, 18, 18, 18)
    layout.setSpacing(window.UI_SIZE["spacing_large"])

    # =========================================================
    # 左侧主区域
    # =========================================================
    left_wrap = QVBoxLayout()
    left_wrap.setSpacing(window.UI_SIZE["spacing_large"])

    title = QLabel("方案编排与测试")
    title.setStyleSheet(
        f"font-size: {window.UI_SIZE['font_page_title']}px; font-weight: bold;"
    )
    left_wrap.addWidget(title)

    desc = QLabel("第三页用于创建方案名称，并将文本模板、表现模板与语音包组合后进行模拟测试。")
    desc.setWordWrap(True)
    desc.setStyleSheet("color: #9FB3D9;")
    left_wrap.addWidget(desc)

    # =========================
    # 一、组合配置
    # =========================
    combo_card = window.build_section_card("组合配置")
    combo_layout = cast(QVBoxLayout, combo_card.layout())

    window.combo_name_edit = QLineEdit()
    window.combo_name_edit.setObjectName("editorInput")
    window.combo_name_edit.setPlaceholderText("请输入创建方案名称")
    window.combo_name_edit.textChanged.connect(lambda: window.set_dirty("info", True))
    window.add_labeled_widget(combo_layout, "创建方案名称", window.combo_name_edit)

    window.combo_persona_edit = QTextEdit()
    window.combo_persona_edit.setObjectName("editorTextArea")
    window.combo_persona_edit.setPlaceholderText("请输入该方案的人设说明")
    window.combo_persona_edit.textChanged.connect(lambda: window.set_dirty("info", True))
    window.combo_persona_edit.setMinimumHeight(window.UI_SIZE["textedit_large_min_height"])
    window.add_labeled_widget(combo_layout, "人设说明", window.combo_persona_edit)

    row_1 = QHBoxLayout()
    row_1.setSpacing(window.UI_SIZE["spacing_medium"])

    window.combo_scheme_name_combo = NoWheelComboBox()
    window.combo_scheme_name_combo.currentIndexChanged.connect(window.on_scheme_name_selected_in_info_page)

    window.combo_role_config_combo = NoWheelComboBox()
    window.combo_role_config_combo.currentIndexChanged.connect(lambda: window.set_dirty("info", True))

    for label_text, widget in [
        ("方案名称", window.combo_scheme_name_combo),
        ("文本模板", window.combo_role_config_combo),
    ]:
        col = QVBoxLayout()
        label = QLabel(label_text)
        label.setStyleSheet("font-weight: bold; color: #FFFFFF;")
        label.setFixedHeight(window.UI_SIZE["section_title_height"])
        widget.setFixedHeight(window.UI_SIZE["input_min_height"])
        col.addWidget(label)
        col.addWidget(widget)
        row_1.addLayout(col, 1)

    combo_layout.addLayout(row_1)

    row_2 = QHBoxLayout()
    row_2.setSpacing(window.UI_SIZE["spacing_medium"])

    window.combo_voice_config_combo = NoWheelComboBox()
    window.combo_voice_config_combo.currentIndexChanged.connect(lambda: window.set_dirty("info", True))

    window.combo_voice_combo = NoWheelComboBox()
    window.combo_voice_combo.currentIndexChanged.connect(window.on_info_page_changed)

    for label_text, widget in [
        ("表现模板", window.combo_voice_config_combo),
        ("语音包", window.combo_voice_combo),
    ]:
        col = QVBoxLayout()
        label = QLabel(label_text)
        label.setStyleSheet("font-weight: bold; color: #FFFFFF;")
        label.setFixedHeight(window.UI_SIZE["section_title_height"])
        widget.setFixedHeight(window.UI_SIZE["input_min_height"])
        col.addWidget(label)
        col.addWidget(widget)
        row_2.addLayout(col, 1)

    combo_layout.addLayout(row_2)

    combo_btn_row = QHBoxLayout()
    combo_btn_row.setSpacing(window.UI_SIZE["spacing_medium"])

    window.btn_combo_save = QPushButton("保存方案")
    window.btn_combo_load = QPushButton("应用方案")
    window.btn_combo_delete = QPushButton("删除方案")

    window.apply_button_preset(window.btn_combo_save, "save")
    window.apply_button_preset(window.btn_combo_load, "load_preset")
    window.apply_button_preset(window.btn_combo_delete, "delete")

    window.btn_combo_save.clicked.connect(window.save_combo_preset)
    window.btn_combo_load.clicked.connect(window.load_combo_preset)
    window.btn_combo_delete.clicked.connect(window.delete_combo_preset)

    combo_btn_row.addWidget(window.btn_combo_save)
    combo_btn_row.addWidget(window.btn_combo_load)
    combo_btn_row.addWidget(window.btn_combo_delete)
    combo_btn_row.addStretch()

    combo_layout.addLayout(combo_btn_row)
    left_wrap.addWidget(combo_card)

    # =========================
    # 二、模拟测试区
    # =========================
    sim_card = window.build_section_card("模拟测试区")
    sim_layout = cast(QVBoxLayout, sim_card.layout())

    window.combo_input_text = QTextEdit()
    window.combo_input_text.setObjectName("editorTextArea")
    window.combo_input_text.setPlaceholderText("输入测试文本，使用当前组合方案进行纯 TTS 测试")
    window.combo_input_text.textChanged.connect(lambda: window.set_dirty("info", True))
    window.combo_input_text.setMinimumHeight(84)
    window.combo_input_text.setMaximumHeight(110)
    window.add_labeled_widget(sim_layout, "输入文本", window.combo_input_text)

    window.combo_waiting_label = QLabel("预计等待：-")
    window.combo_waiting_label.setStyleSheet("color: #DCE8FF;")
    sim_layout.addWidget(window.combo_waiting_label)

    audio_label = QLabel("音频控制")
    audio_label.setStyleSheet("font-weight: bold; color: #FFFFFF;")
    audio_label.setFixedHeight(window.UI_SIZE["section_title_height"])
    sim_layout.addWidget(audio_label)

    audio_row = QHBoxLayout()
    audio_row.setSpacing(window.UI_SIZE["spacing_medium"])

    window.btn_combo_play_pause = QPushButton()
    window.btn_combo_play_pause.setObjectName("audioIconButton")

    window.btn_combo_loop = QPushButton()
    window.btn_combo_loop.setObjectName("audioLoopButtonOff")

    window.combo_time_label = QLabel("0:00 / 0:00")
    window.combo_time_label.setFixedWidth(window.UI_SIZE["audio_time_width"])
    window.combo_time_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

    window.btn_combo_play_pause.setFixedSize(
        window.UI_SIZE["audio_icon_btn"],
        window.UI_SIZE["audio_icon_btn"],
    )
    window.btn_combo_loop.setFixedSize(
        window.UI_SIZE["audio_loop_btn"],
        window.UI_SIZE["audio_icon_btn"],
    )

    window.btn_combo_play_pause.clicked.connect(window.mock_audio_play)
    window.btn_combo_loop.clicked.connect(window.cc_actions.toggle_combo_loop)

    window.combo_progress_slider = QSlider(Qt.Orientation.Horizontal)
    window.combo_progress_slider.setRange(0, 1000)
    window.combo_progress_slider.setFixedHeight(window.UI_SIZE["audio_bar_height"] + 14)
    window.combo_progress_slider.sliderMoved.connect(window.cc_actions.seek_combo_audio)
    
    audio_row.addWidget(window.btn_combo_play_pause)
    audio_row.addWidget(window.combo_progress_slider, 1)
    audio_row.addWidget(window.combo_time_label)
    audio_row.addWidget(window.btn_combo_loop)

    sim_layout.addLayout(audio_row)

    bottom_row = QHBoxLayout()
    bottom_row.setSpacing(window.UI_SIZE["spacing_medium"])

    window.btn_combo_run = QPushButton("发送")
    window.apply_button_preset(window.btn_combo_run, "send")
    window.btn_combo_run.clicked.connect(window.run_combo_preview)

    window.combo_speed_combo = NoWheelComboBox()
    window.apply_combo_width(window.combo_speed_combo, "btn_w_choice")
    window.combo_speed_combo.setFixedHeight(window.UI_SIZE["input_min_height"])
    window.combo_speed_combo.addItem("0.8x", 0.8)
    window.combo_speed_combo.addItem("1.0x", 1.0)
    window.combo_speed_combo.addItem("1.2x", 1.2)
    window.combo_speed_combo.addItem("1.5x", 1.5)
    window.combo_speed_combo.setCurrentIndex(1)

    bottom_row.addWidget(window.btn_combo_run)
    bottom_row.addWidget(window.combo_speed_combo)
    bottom_row.addStretch()

    sim_layout.addLayout(bottom_row)
    left_wrap.addWidget(sim_card, 1)

    # =========================================================
    # 右侧信息栏
    # =========================================================
    right_card = window.build_section_card("简略信息栏")
    right_layout = cast(QVBoxLayout, right_card.layout())

    right_tip = QLabel("这里集中显示当前方案信息、已保存方案以及当前选中项的摘要。")
    right_tip.setWordWrap(True)
    right_tip.setStyleSheet("color: #9FB3D9;")
    right_layout.addWidget(right_tip)

    # 已保存方案：改成长列表
    saved_label = QLabel("已保存方案")
    saved_label.setStyleSheet("font-weight: bold; color: #FFFFFF;")
    saved_label.setFixedHeight(window.UI_SIZE["section_title_height"])
    right_layout.addWidget(saved_label)

    window.saved_combo_combo = QListWidget()
    window.saved_combo_combo.setObjectName("savedComboList")
    window.saved_combo_combo.setMinimumHeight(180)
    window.saved_combo_combo.itemClicked.connect(lambda _: window.on_saved_combo_selected())
    right_layout.addWidget(window.saved_combo_combo)

    # 方案列表摘要：用于看列表中当前选中方案的信息
    window.combo_scheme_list = QTextEdit()
    window.combo_scheme_list.setReadOnly(True)
    window.combo_scheme_list.setPlaceholderText("这里显示当前选中保存方案的摘要")
    window.combo_scheme_list.setMinimumHeight(150)
    right_layout.addWidget(QLabel("方案列表摘要"))
    right_layout.addWidget(window.combo_scheme_list)

    # 测试选中方案详情：与模拟测试区平行
    window.combo_voice_preview = QTextEdit()
    window.combo_voice_preview.setReadOnly(True)
    window.combo_voice_preview.setPlaceholderText("这里显示测试选中方案的详细摘要")
    window.combo_voice_preview.setMinimumHeight(220)
    right_layout.addWidget(QLabel("测试选中方案详情"))
    right_layout.addWidget(window.combo_voice_preview, 1)

    layout.addLayout(left_wrap, window.UI_SIZE["info_left_stretch"])
    layout.addWidget(right_card, window.UI_SIZE["info_right_stretch"])

    return page