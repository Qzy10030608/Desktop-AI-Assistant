from typing import cast
import json

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


def build_connection_page(window) -> QFrame:
    page = QFrame()
    page.setObjectName("pageCard")

    layout = QVBoxLayout(page)
    layout.setContentsMargins(18, 18, 18, 18)
    layout.setSpacing(window.UI_SIZE["spacing_large"] if hasattr(window, "UI_SIZE") else 14)

    # =========================
    # 页面标题
    # =========================
    title = QLabel("连接配置")
    title.setStyleSheet(
        f"font-size: {window.UI_SIZE['font_page_title']}px; font-weight: bold;"
    )
    layout.addWidget(title)

    desc = QLabel("用于选择 LLM 提供方、查看本机已发现模型，并在使用 Ollama 时直接选择下载模型。")
    desc.setWordWrap(True)
    desc.setStyleSheet("color: #9FB3D9;")
    layout.addWidget(desc)

    # =========================
    # LLM 连接
    # =========================
    llm_card = window.build_section_card("LLM 连接")
    llm_layout = cast(QVBoxLayout, llm_card.layout())

    window.llm_provider_combo = NoWheelComboBox()
    window.llm_provider_combo.addItem("Ollama", "ollama")
    window.llm_provider_combo.addItem("Local（预留）", "local")
    window.llm_provider_combo.addItem("API（预留）", "api")
    window.llm_provider_combo.currentIndexChanged.connect(window.on_connection_page_changed)
    window.add_labeled_widget(llm_layout, "LLM Provider", window.llm_provider_combo)

    # Ollama 专属区域
    window.ollama_runtime_frame = QFrame()
    ollama_runtime_layout = QVBoxLayout(window.ollama_runtime_frame)
    ollama_runtime_layout.setContentsMargins(0, 0, 0, 0)
    ollama_runtime_layout.setSpacing(window.UI_SIZE["spacing_medium"])

    window.ollama_status_label = QLabel("Ollama 状态：未检测")
    window.ollama_status_label.setWordWrap(True)
    window.ollama_status_label.setStyleSheet("color: #B8C7E0;")
    ollama_runtime_layout.addWidget(window.ollama_status_label)

    window.connection_model_combo = NoWheelComboBox()
    window.connection_model_combo.currentIndexChanged.connect(window.on_connection_model_changed)
    window.add_labeled_widget(ollama_runtime_layout, "已发现模型", window.connection_model_combo)

    window.ollama_download_model_combo = NoWheelComboBox()
    window.ollama_download_model_combo.addItem("请选择要下载的模型…", "")
    window.ollama_download_model_combo.addItem("qwen3:4b", "qwen3:4b")
    window.ollama_download_model_combo.addItem("qwen3:8b", "qwen3:8b")
    window.ollama_download_model_combo.addItem("qwen3:30b", "qwen3:30b")
    window.ollama_download_model_combo.addItem("qwen3-coder:30b", "qwen3-coder:30b")
    window.ollama_download_model_combo.addItem("qwen3-vl:4b", "qwen3-vl:4b")
    window.ollama_download_model_combo.addItem("qwen3-vl:8b", "qwen3-vl:8b")
    window.ollama_download_model_combo.addItem("qwen3-vl:30b", "qwen3-vl:30b")
    window.ollama_download_model_combo.addItem("deepseek-r1:8b", "deepseek-r1:8b")
    window.ollama_download_model_combo.addItem("手动输入其他模型名…", "__custom__")
    window.ollama_download_model_combo.currentIndexChanged.connect(window.on_ollama_download_model_selected)
    window.add_labeled_widget(ollama_runtime_layout, "下载模型", window.ollama_download_model_combo)

    row_llm_btn = QHBoxLayout()
    row_llm_btn.setSpacing(window.UI_SIZE["spacing_medium"])

    window.btn_refresh_ollama_models = QPushButton("刷新模型")
    window.btn_use_connection_model = QPushButton("设为当前模型")

    row_llm_btn.addWidget(window.btn_refresh_ollama_models)
    row_llm_btn.addWidget(window.btn_use_connection_model)
    row_llm_btn.addStretch()

    window.btn_refresh_ollama_models.clicked.connect(window.refresh_ollama_model_runtime)
    window.btn_use_connection_model.clicked.connect(window.use_selected_connection_model)

    ollama_runtime_layout.addLayout(row_llm_btn)
    llm_layout.addWidget(window.ollama_runtime_frame)

    # =========================
    # 模型回复策略
    # =========================
    policy_card = window.build_section_card("模型回复策略")
    policy_layout = cast(QVBoxLayout, policy_card.layout())

    tip = QLabel("用于查看当前模型自动识别出的 family / size_tier / 策略模板，并支持手动覆盖。")
    tip.setWordWrap(True)
    tip.setStyleSheet("color: #9FB3D9;")
    policy_layout.addWidget(tip)

    # 自动识别结果
    window.policy_detected_family_label = QLabel("自动识别 Family：-")
    window.policy_detected_size_tier_label = QLabel("自动识别 Size Tier：-")
    window.policy_detected_template_label = QLabel("自动识别策略模板：-")
    for lab in [
        window.policy_detected_family_label,
        window.policy_detected_size_tier_label,
        window.policy_detected_template_label,
    ]:
        lab.setWordWrap(True)
        lab.setStyleSheet("color: #B8C7E0;")
        policy_layout.addWidget(lab)

    # 手动覆盖
    window.policy_family_override_combo = NoWheelComboBox()
    window.policy_family_override_combo.addItem("自动", "")
    window.policy_family_override_combo.addItem("qwen", "qwen")
    window.policy_family_override_combo.addItem("deepseek", "deepseek")
    window.policy_family_override_combo.addItem("llama", "llama")
    window.policy_family_override_combo.addItem("gpt", "gpt")
    window.policy_family_override_combo.addItem("gemini", "gemini")
    window.policy_family_override_combo.addItem("claude", "claude")
    window.policy_family_override_combo.addItem("mistral", "mistral")
    window.policy_family_override_combo.addItem("unknown", "unknown")
    window.policy_family_override_combo.currentIndexChanged.connect(window.on_connection_page_changed)
    window.add_labeled_widget(policy_layout, "Family 手动覆盖", window.policy_family_override_combo)

    window.policy_size_tier_override_combo = NoWheelComboBox()
    window.policy_size_tier_override_combo.addItem("自动", "")
    window.policy_size_tier_override_combo.addItem("small", "small")
    window.policy_size_tier_override_combo.addItem("medium", "medium")
    window.policy_size_tier_override_combo.addItem("large", "large")
    window.policy_size_tier_override_combo.currentIndexChanged.connect(window.on_connection_page_changed)
    window.add_labeled_widget(policy_layout, "Size Tier 手动覆盖", window.policy_size_tier_override_combo)

    window.policy_template_override_combo = NoWheelComboBox()
    window.policy_template_override_combo.addItem("自动", "")
    window.policy_template_override_combo.addItem("small_local_strict", "small_local_strict")
    window.policy_template_override_combo.addItem("medium_local_balanced", "medium_local_balanced")
    window.policy_template_override_combo.addItem("large_local_light", "large_local_light")
    window.policy_template_override_combo.addItem("api_high_trust", "api_high_trust")
    window.policy_template_override_combo.currentIndexChanged.connect(window.on_connection_page_changed)
    window.add_labeled_widget(policy_layout, "策略模板手动覆盖", window.policy_template_override_combo)

    window.policy_override_json_edit = QTextEdit()
    window.policy_override_json_edit.setPlaceholderText(
        json.dumps(
            {
                "strip_followup_tail": True,
                "max_visible_sentences": 2
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    window.policy_override_json_edit.textChanged.connect(window.on_connection_page_changed)
    window.add_labeled_widget(policy_layout, "策略补丁 JSON（可选）", window.policy_override_json_edit)

    row_policy_btn = QHBoxLayout()
    row_policy_btn.setSpacing(window.UI_SIZE["spacing_medium"])

    window.btn_clear_policy_override = QPushButton("清空覆盖")
    window.btn_apply_policy_override = QPushButton("应用当前覆盖")

    window.btn_clear_policy_override.clicked.connect(window.clear_connection_policy_override)
    window.btn_apply_policy_override.clicked.connect(window.apply_connection_policy_override)

    row_policy_btn.addWidget(window.btn_clear_policy_override)
    row_policy_btn.addWidget(window.btn_apply_policy_override)
    row_policy_btn.addStretch()
    policy_layout.addLayout(row_policy_btn)

    window.connection_policy_preview_display = QTextEdit()
    window.connection_policy_preview_display.setReadOnly(True)
    window.connection_policy_preview_display.setObjectName("schemeDisplay")
    window.connection_policy_preview_display.setFixedHeight(180)
    policy_layout.addWidget(window.connection_policy_preview_display)

    # =========================
    # GPT-SoVITS 连接
    # =========================
    gpt_card = window.build_section_card("GPT-SoVITS 连接")
    gpt_layout = cast(QVBoxLayout, gpt_card.layout())

    window.gpt_sovits_root_edit = QLineEdit()
    window.gpt_sovits_root_edit.setPlaceholderText("GPT-SoVITS 根目录")
    window.gpt_sovits_root_edit.textEdited.connect(window.on_connection_page_changed)
    window.add_labeled_widget(gpt_layout, "根目录", window.gpt_sovits_root_edit)

    window.gpt_sovits_python_edit = QLineEdit()
    window.gpt_sovits_python_edit.setPlaceholderText("python.exe 路径（可为空自动探测）")
    window.gpt_sovits_python_edit.textEdited.connect(window.on_connection_page_changed)
    window.add_labeled_widget(gpt_layout, "Python", window.gpt_sovits_python_edit)

    window.gpt_sovits_host_edit = QLineEdit()
    window.gpt_sovits_host_edit.setPlaceholderText("127.0.0.1")
    window.gpt_sovits_host_edit.textEdited.connect(window.on_connection_page_changed)
    window.add_labeled_widget(gpt_layout, "Host", window.gpt_sovits_host_edit)

    window.gpt_sovits_port_edit = QLineEdit()
    window.gpt_sovits_port_edit.setPlaceholderText("9880")
    window.gpt_sovits_port_edit.textEdited.connect(window.on_connection_page_changed)
    window.add_labeled_widget(gpt_layout, "Port", window.gpt_sovits_port_edit)

    window.gpt_sovits_api_script_edit = QLineEdit()
    window.gpt_sovits_api_script_edit.setPlaceholderText("api_v2.py")
    window.gpt_sovits_api_script_edit.textEdited.connect(window.on_connection_page_changed)
    window.add_labeled_widget(gpt_layout, "API 脚本", window.gpt_sovits_api_script_edit)

    window.gpt_sovits_tts_config_edit = QLineEdit()
    window.gpt_sovits_tts_config_edit.setPlaceholderText("GPT_SoVITS/configs/tts_infer.yaml")
    window.gpt_sovits_tts_config_edit.textEdited.connect(window.on_connection_page_changed)
    window.add_labeled_widget(gpt_layout, "TTS 配置", window.gpt_sovits_tts_config_edit)

    window.gpt_sovits_status_label = QLabel("GPT-SoVITS 状态：未检测")
    window.gpt_sovits_status_label.setWordWrap(True)
    window.gpt_sovits_status_label.setStyleSheet("color: #B8C7E0;")
    gpt_layout.addWidget(window.gpt_sovits_status_label)

    row_gpt_btn = QHBoxLayout()
    row_gpt_btn.setSpacing(window.UI_SIZE["spacing_medium"])

    window.btn_test_gpt_sovits = QPushButton("检测路径")
    window.btn_run_startup_check = QPushButton("执行启动检查")
    window.btn_save_connection = QPushButton("保存连接配置")

    window.btn_test_gpt_sovits.clicked.connect(window.test_gpt_sovits_connection)
    window.btn_run_startup_check.clicked.connect(window.run_connection_startup_check)
    window.btn_save_connection.clicked.connect(window.save_connection_page)

    row_gpt_btn.addWidget(window.btn_test_gpt_sovits)
    row_gpt_btn.addWidget(window.btn_run_startup_check)
    row_gpt_btn.addWidget(window.btn_save_connection)
    row_gpt_btn.addStretch()
    gpt_layout.addLayout(row_gpt_btn)

    # =========================
    # 当前连接摘要
    # =========================
    summary_card = window.build_section_card("当前连接摘要")
    summary_layout = cast(QVBoxLayout, summary_card.layout())

    window.connection_summary_display = QTextEdit()
    window.connection_summary_display.setReadOnly(True)
    window.connection_summary_display.setObjectName("schemeDisplay")
    window.connection_summary_display.setFixedHeight(150)
    summary_layout.addWidget(window.connection_summary_display)

    layout.addWidget(llm_card)
    layout.addWidget(policy_card)
    layout.addWidget(gpt_card)
    layout.addWidget(summary_card)
    layout.addStretch()

    return page