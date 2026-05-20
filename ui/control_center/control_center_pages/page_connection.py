from typing import cast
import json

from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QHBoxLayout,
    QLineEdit,
)

from ui.control_center.control_center_widgets.no_wheel_combo import NoWheelComboBox  # type: ignore


def build_connection_page(window) -> QFrame:
    """
    连接配置页

    作用：
    1. 管理 LLM 连接方式与模型选择
    2. 管理 TTS 后端连接方式与 GPT-SoVITS 本地配置
    3. 管理模型回复策略识别与覆盖
    4. 汇总当前连接状态
    """
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

    desc = QLabel(
        "这一页用于统一配置语言模型连接、语音后端连接、本地 GPT-SoVITS 路径，以及当前模型的回复策略。"
    )
    desc.setWordWrap(True)
    desc.setStyleSheet("color: #9FB3D9;")
    layout.addWidget(desc)

    # =========================================================
    # 一、LLM 连接区
    # =========================================================
    llm_card = window.build_section_card("LLM 连接区")
    llm_layout = cast(QVBoxLayout, llm_card.layout())

    llm_tip = QLabel("当前默认以 Ollama 为主，Local / API 先保留为后续扩展入口。")
    llm_tip.setWordWrap(True)
    llm_tip.setStyleSheet("color: #9FB3D9;")
    llm_layout.addWidget(llm_tip)

    window.llm_provider_combo = NoWheelComboBox()
    window.llm_provider_combo.addItem("Ollama", "ollama")
    window.llm_provider_combo.addItem("Local（预留）", "local")
    window.llm_provider_combo.addItem("API（预留）", "api")
    window.llm_provider_combo.currentIndexChanged.connect(window.on_connection_page_changed)
    window.add_labeled_widget(llm_layout, "LLM Provider", window.llm_provider_combo)

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

    llm_btn_row = QHBoxLayout()
    llm_btn_row.setSpacing(window.UI_SIZE["spacing_medium"])

    window.btn_refresh_ollama_models = QPushButton("刷新模型")
    window.btn_use_connection_model = QPushButton("设为当前模型")

    llm_btn_row.addWidget(window.btn_refresh_ollama_models)
    llm_btn_row.addWidget(window.btn_use_connection_model)
    llm_btn_row.addStretch()

    window.btn_refresh_ollama_models.clicked.connect(window.refresh_ollama_model_runtime)
    window.btn_use_connection_model.clicked.connect(window.use_selected_connection_model)

    ollama_runtime_layout.addLayout(llm_btn_row)
    llm_layout.addWidget(window.ollama_runtime_frame)

    # =========================================================
    # 二、TTS 连接区
    # =========================================================
    tts_card = window.build_section_card("TTS 连接区")
    tts_layout = cast(QVBoxLayout, tts_card.layout())

    tts_tip = QLabel("当前运行语音引擎由“运行配置”页选择；本页只配置当前已选语音引擎的连接细节。")
    tts_tip.setWordWrap(True)
    tts_tip.setStyleSheet("color: #9FB3D9;")
    tts_layout.addWidget(tts_tip)
    window.current_tts_backend_label = QLabel("当前运行语音引擎：-")
    window.current_tts_backend_label.setWordWrap(True)
    window.current_tts_backend_label.setStyleSheet("color: #B8C7E0; font-weight: bold;")
    tts_layout.addWidget(window.current_tts_backend_label)

    window.tts_connection_hint_label = QLabel("")
    window.tts_connection_hint_label.setWordWrap(True)
    window.tts_connection_hint_label.setStyleSheet("color: #9FB3D9;")
    tts_layout.addWidget(window.tts_connection_hint_label)

    # 兼容旧 loader / actions 中依旧使用的状态标签
    window.gpt_sovits_status_label = QLabel("GPT-SoVITS 状态：未检测")
    window.gpt_sovits_status_label.setWordWrap(True)
    window.gpt_sovits_status_label.setStyleSheet("color: #B8C7E0;")
    tts_layout.addWidget(window.gpt_sovits_status_label)

    # GPT-SoVITS 配置容器
    window.gpt_sovits_config_frame = QFrame()
    gpt_layout = QVBoxLayout(window.gpt_sovits_config_frame)
    gpt_layout.setContentsMargins(0, 0, 0, 0)
    gpt_layout.setSpacing(window.UI_SIZE["spacing_medium"])

    gpt_desc = QLabel("当使用 GPT-SoVITS 时，需要配置本地根目录、Python、端口与 API 脚本路径。")
    gpt_desc.setWordWrap(True)
    gpt_desc.setStyleSheet("color: #B8C7E0;")
    gpt_layout.addWidget(gpt_desc)

    window.gpt_sovits_root_edit = QLineEdit()
    window.gpt_sovits_root_edit.setPlaceholderText("GPT-SoVITS 根目录")
    window.gpt_sovits_root_edit.textEdited.connect(window.on_connection_page_changed)
    window.add_labeled_widget(gpt_layout, "根目录", window.gpt_sovits_root_edit)

    window.gpt_sovits_python_edit = QLineEdit()
    window.gpt_sovits_python_edit.setPlaceholderText("python.exe 路径（可为空自动探测）")
    window.gpt_sovits_python_edit.textEdited.connect(window.on_connection_page_changed)
    window.add_labeled_widget(gpt_layout, "Python", window.gpt_sovits_python_edit)

    host_port_row = QHBoxLayout()
    host_port_row.setSpacing(window.UI_SIZE["spacing_medium"])

    host_col = QVBoxLayout()
    host_label = QLabel("Host")
    host_label.setStyleSheet("font-weight: bold; color: #FFFFFF;")
    host_label.setFixedHeight(window.UI_SIZE["section_title_height"])
    window.gpt_sovits_host_edit = QLineEdit()
    window.gpt_sovits_host_edit.setPlaceholderText("127.0.0.1")
    window.gpt_sovits_host_edit.textEdited.connect(window.on_connection_page_changed)
    host_col.addWidget(host_label)
    host_col.addWidget(window.gpt_sovits_host_edit)

    port_col = QVBoxLayout()
    port_label = QLabel("Port")
    port_label.setStyleSheet("font-weight: bold; color: #FFFFFF;")
    port_label.setFixedHeight(window.UI_SIZE["section_title_height"])
    window.gpt_sovits_port_edit = QLineEdit()
    window.gpt_sovits_port_edit.setPlaceholderText("9880")
    window.gpt_sovits_port_edit.textEdited.connect(window.on_connection_page_changed)
    port_col.addWidget(port_label)
    port_col.addWidget(window.gpt_sovits_port_edit)

    host_port_row.addLayout(host_col, 1)
    host_port_row.addLayout(port_col, 1)
    gpt_layout.addLayout(host_port_row)

    window.gpt_sovits_api_script_edit = QLineEdit()
    window.gpt_sovits_api_script_edit.setPlaceholderText("api_v2.py")
    window.gpt_sovits_api_script_edit.textEdited.connect(window.on_connection_page_changed)
    window.add_labeled_widget(gpt_layout, "API 脚本", window.gpt_sovits_api_script_edit)

    window.gpt_sovits_tts_config_edit = QLineEdit()
    window.gpt_sovits_tts_config_edit.setPlaceholderText("GPT_SoVITS/configs/tts_infer.yaml")
    window.gpt_sovits_tts_config_edit.textEdited.connect(window.on_connection_page_changed)
    window.add_labeled_widget(gpt_layout, "TTS 配置", window.gpt_sovits_tts_config_edit)

    tts_btn_row = QHBoxLayout()
    tts_btn_row.setSpacing(window.UI_SIZE["spacing_medium"])

    window.btn_test_gpt_sovits = QPushButton("检测路径")
    window.btn_run_startup_check = QPushButton("执行启动检查")
    window.btn_save_connection = QPushButton("保存连接配置")

    window.btn_test_gpt_sovits.clicked.connect(window.test_gpt_sovits_connection)
    window.btn_run_startup_check.clicked.connect(window.run_connection_startup_check)
    window.btn_save_connection.clicked.connect(window.save_connection_page)

    tts_btn_row.addWidget(window.btn_test_gpt_sovits)
    tts_btn_row.addWidget(window.btn_run_startup_check)
    tts_btn_row.addWidget(window.btn_save_connection)
    tts_btn_row.addStretch()
    gpt_layout.addLayout(tts_btn_row)

    tts_layout.addWidget(window.gpt_sovits_config_frame)

    layout.addWidget(llm_card)
    layout.addWidget(tts_card)
    layout.addStretch()

    return page
