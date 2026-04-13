from pathlib import Path
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtCore import Qt, Signal, QSize, QUrl
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtWidgets import (
    QWidget,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QHBoxLayout,
    QFrame,
    QStackedWidget,
    QSlider,
    QScrollArea,
    QComboBox,
    QLineEdit,
    QTextEdit,
    QInputDialog,
)
from bootstrap.machine_profile_service import MachineProfileService  # type: ignore
from bootstrap.startup_check_service import StartupCheckService  # type: ignore
from services.reply.llm_backend_controller_service import LLMBackendControllerService  # type: ignore
from ui.control_center.control_center_pages.page_connection import build_connection_page  # type: ignore

from config import (  
    DEFAULT_OUTPUT_MODE, # type: ignore
    PRESETS_DIR, # type: ignore
    WORKSPACE_DRAFT_IDENTITY_FILE,# type: ignore
    WORKSPACE_STYLE_SELECTION_FILE,# type: ignore
    WORKSPACE_VOICE_SELECTION_FILE,# type: ignore
    WORKSPACE_PERSONA_DRAFT_FILE,# type: ignore
    WORKSPACE_PREVIEW_TEXT_FILE,# type: ignore
    APP_ICON_FILE,# type: ignore
)

from services.tts.tts_backend_controller_service import TTSBackendControllerService  # type: ignore
from services.tts.tts_package_service import TTSPackageService  # type: ignore
from services.download_service import DownloadService  # type: ignore
from services.persona.role_service import RoleService  # type: ignore
from services.persona.style_profile_service import StyleProfileService  # type: ignore
from services.persona.voice_profile_service import VoiceProfileService  # type: ignore  # type: ignore
from services.model_registry_service import ModelRegistryService  # type: ignore

from ui.control_center.config import (  # type: ignore
    UI_SIZE,
    ASSET_PATHS,
    build_qss,
    get_button_preset,
    get_page_meta,
    get_page_button_groups,
)
from ui.control_center.loader import ControlCenterLoader  # type: ignore
from ui.control_center.logic import ControlCenterLogic  # type: ignore
from ui.control_center.forms import ControlCenterForms  # type: ignore
from ui.control_center.state import ControlCenterState  # type: ignore
from ui.control_center.actions import ControlCenterActions  # type: ignore

from ui.control_center.control_center_widgets.bookmark_button import BookmarkButton  # type: ignore
from ui.control_center.control_center_pages.page_model import build_model_page  # type: ignore
from ui.control_center.control_center_pages.page_style import build_style_page  # type: ignore
from ui.control_center.control_center_pages.page_info import build_info_page  # type: ignore


class ControlCenterWindow(QWidget):
    settings_applied = Signal()
    current_state_changed = Signal(dict)
    open_reply_pipeline_requested = Signal()

    def __init__(
        self,
        parent=None,
        *,
        role_service=None,
        style_service=None,
        voice_service=None,
        model_service=None,
        tts_package_service=None,
        tts_backend_controller=None,
        download_service=None,
        machine_profile_service=None,
        startup_check_service=None,
        llm_backend_controller=None,
    ):
        super().__init__(parent)
        self.setWindowFlag(Qt.Window, True)  # type: ignore
        self.setWindowFlag(Qt.WindowMinMaxButtonsHint, True)  # type: ignore
        self.setWindowFlag(Qt.WindowCloseButtonHint, True)  # type: ignore
        self.setWindowModality(Qt.NonModal)  # type: ignore

        self.UI_SIZE = UI_SIZE
        self.setWindowTitle("控制中心")
        self.setWindowIcon(QIcon(APP_ICON_FILE))
        self.resize(UI_SIZE["window_width"], UI_SIZE["window_height"])
        self.setMinimumSize(UI_SIZE["window_min_width"], UI_SIZE["window_min_height"])

        # -------------------------
        # 配置 / 路径
        # -------------------------
        self.current_output_mode = DEFAULT_OUTPUT_MODE
        self.combo_presets_dir = Path(PRESETS_DIR) / "combos"
        self.combo_presets_dir.mkdir(parents=True, exist_ok=True)

        self.WORKSPACE_DRAFT_IDENTITY_FILE = WORKSPACE_DRAFT_IDENTITY_FILE
        self.WORKSPACE_STYLE_SELECTION_FILE = WORKSPACE_STYLE_SELECTION_FILE
        self.WORKSPACE_VOICE_SELECTION_FILE = WORKSPACE_VOICE_SELECTION_FILE
        self.WORKSPACE_PERSONA_DRAFT_FILE = WORKSPACE_PERSONA_DRAFT_FILE
        self.WORKSPACE_PREVIEW_TEXT_FILE = WORKSPACE_PREVIEW_TEXT_FILE

        # -------------------------
        # 服务层（优先复用主程序传入的共享实例）
        # -------------------------
        self.role_service = role_service or RoleService()
        self.style_service = style_service or StyleProfileService(self.role_service)
        self.voice_service = voice_service or VoiceProfileService(self.role_service)
        self.model_service = model_service or ModelRegistryService()
        self.tts_package_service = tts_package_service or TTSPackageService()
        self.tts_backend_controller = tts_backend_controller or TTSBackendControllerService()
        self.download_service = download_service or DownloadService(str(Path(PRESETS_DIR).parent / "downloads"))

        self.temp_test_audio_dir = Path(PRESETS_DIR).parent / "temp" / "test_voice"
        self.temp_test_audio_dir.mkdir(parents=True, exist_ok=True)
        self.current_test_audio_path = ""

        self.machine_profile_service = (
            machine_profile_service
            or getattr(model_service, "machine_profile_service", None)
            or MachineProfileService()
        )
        self.startup_check_service = (
            startup_check_service
            or StartupCheckService(self.machine_profile_service)
        )
        self.llm_backend_controller = llm_backend_controller or LLMBackendControllerService()

        # 第三页测试语音播放器
        self.preview_audio_output = QAudioOutput(self)
        self.preview_audio_player = QMediaPlayer(self)
        self.preview_audio_player.setAudioOutput(self.preview_audio_output)
        self.preview_audio_player.positionChanged.connect(self._on_preview_position_changed)
        self.preview_audio_player.durationChanged.connect(self._on_preview_duration_changed)
        self.preview_audio_player.playbackStateChanged.connect(self._on_preview_playback_state_changed)
        
        # -------------------------
        # 运行状态
        # -------------------------
        self._loading = False
        self._force_close = False
        self.page_dirty = {
            "model": False,
            "style": False,
            "info": False,
        }

        # 先声明页面控件引用，减少静态检查报错
        self._init_page_refs()

        # -------------------------
        # 分层对象
        # -------------------------
        self.loader = ControlCenterLoader(self)
        self.logic = ControlCenterLogic(self)
        self.forms = ControlCenterForms(self)
        self.state = ControlCenterState(self)
        self.cc_actions = ControlCenterActions(self)
        
        # -------------------------
        # UI
        # -------------------------
        self.init_ui()
        self.setStyleSheet(build_qss())
        self._apply_preview_button_icons()
        self.refresh_combo_loop_button()

        # 首次加载
        self.load_current_state()
        self.logic.initialize_style_scene_defaults()
        self.logic.update_model_page_mode_visibility()
        self.capture_all_snapshots()
    # =========================================================
    # 页面控件占位声明
    # =========================================================
    def _init_page_refs(self):
        # 第1页
        self.chat_model_combo = None
        self.tts_model_combo = None

        self.combo_scheme_combo = None
        self.btn_refresh_combo_schemes = None
        self.btn_apply_combo_scheme = None
        self.current_scheme_display = None

        self.output_mode_combo = None
        self.async_voice_label = None
        self.async_voice_combo = None

        self.summary_role_label = None
        self.summary_voice_label = None
        self.summary_role_config_label = None
        self.summary_voice_config_label = None
        self.summary_output_mode_label = None
        self.summary_model_label = None
        self.summary_tts_model_label = None

        self.btn_apply_chat_model = None
        self.btn_apply_tts_backend = None
        self.btn_refresh_models = None
        self.btn_refresh_tts_models = None

        self.tts_backend_status_dot = None
        self.tts_loading_frame = None
        self.tts_loading_gif_label = None
        self.tts_loading_movie = None
        self.tts_loading_text_label = None
        self.tts_loading_percent_label = None
        # 第2页
        self.current_style_config_combo = None
        self.role_config_name_edit = None
        self.text_scene_combo = None
        self.reply_mode_combo = None
        self.explain_tendency_combo = None
        self.comfort_tendency_combo = None
        self.tone_strength_combo = None
        self.catchphrase_edit = None
        self.opening_style_edit = None
        self.forbidden_edit = None

        self.current_voice_config_combo = None
        self.voice_config_name_edit = None
        self.scene_combo = None
        self.emotion_combo = None
        self.emotion_strength_combo = None
        self.speed_combo = None
        self.pause_combo = None
        self.intonation_combo = None
        self.emphasis_combo = None

        # 第3页
        self.combo_name_edit = None
        self.combo_persona_edit = None
        self.combo_scheme_name_combo = None
        self.combo_role_config_combo = None
        self.combo_voice_config_combo = None
        self.combo_voice_combo = None
        self.combo_test_config_preview = None
        self.combo_input_text = None
        self.combo_waiting_label = None
        self.combo_speed_combo = None
        self.combo_role_preview = None
        self.saved_combo_combo = None
        self.combo_scheme_list = None
        self.combo_voice_preview = None

        self.btn_combo_save = None
        self.btn_combo_load = None
        self.btn_combo_delete = None
        self.btn_combo_run = None
        self.btn_combo_play_pause = None
        self.btn_combo_loop = None

        self.combo_progress_slider = None
        self.combo_time_label = None
        self.combo_loop_enabled = False
        self.combo_is_playing = False

        # 第4页：连接配置
        self.llm_provider_combo = None
        self.ollama_host_edit = None
        self.ollama_status_label = None
        self.ollama_runtime_frame = None
        self.ollama_download_model_combo = None

        self.gpt_sovits_root_edit = None
        self.gpt_sovits_python_edit = None
        self.gpt_sovits_host_edit = None
        self.gpt_sovits_port_edit = None
        self.gpt_sovits_api_script_edit = None
        self.gpt_sovits_tts_config_edit = None
        self.gpt_sovits_status_label = None

        self.connection_model_combo = None
        self.connection_summary_display = None

        self.btn_test_ollama = None
        self.btn_refresh_ollama_models = None
        self.btn_use_connection_model = None
        self.btn_test_gpt_sovits = None
        self.btn_run_startup_check = None
        self.btn_save_connection = None
        self.btn_clear_policy_override = None
        self.btn_apply_policy_override = None
        self.btn_connection = None

        self.policy_detected_family_label = None
        self.policy_detected_size_tier_label = None
        self.policy_detected_template_label = None
        self.policy_family_override_combo = None
        self.policy_size_tier_override_combo = None
        self.policy_template_override_combo = None
        self.policy_override_json_edit = None
        
        self.connection_policy_preview_display = None
    # =========================================================
    # 通用尺寸控制
    # =========================================================
    def apply_button_preset(self, button: QPushButton, preset_name: str):
        preset = get_button_preset(preset_name)
        width_key = preset.get("width")
        height_key = preset.get("height")

        if width_key:
            button.setFixedWidth(UI_SIZE[width_key])
        else:
            button.setMinimumWidth(0)
            button.setMaximumWidth(16777215)

        if height_key:
            button.setFixedHeight(UI_SIZE[height_key])

    def apply_combo_width(self, combo: QComboBox, width_key: str):
        combo.setFixedWidth(UI_SIZE[width_key])

    def apply_page_button_group(self, page_key: str):
        groups = get_page_button_groups(page_key)
        if not groups:
            return

        for _, items in groups.items():
            for widget_name, preset_name in items:
                widget = getattr(self, widget_name, None)
                if isinstance(widget, QPushButton):
                    self.apply_button_preset(widget, preset_name)

    # =========================================================
    # UI 初始化
    # =========================================================
    def init_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(
            UI_SIZE["page_inner_margin"],
            UI_SIZE["page_inner_margin"],
            UI_SIZE["page_inner_margin"],
            UI_SIZE["page_inner_margin"],
        )
        root.setSpacing(UI_SIZE["spacing_large"])

        self.top_bar = self.build_top_bar()
        root.addWidget(self.top_bar)

        body_layout = QHBoxLayout()
        body_layout.setSpacing(UI_SIZE["spacing_large"])

        self.nav_frame = self.build_nav_bar()
        body_layout.addWidget(self.nav_frame, 0)

        self.stack = QStackedWidget()
        self.page_model = self.build_scroll_page(build_model_page(self))
        self.page_style = self.build_scroll_page(build_style_page(self))
        self.page_info = self.build_scroll_page(build_info_page(self))
        self.page_connection = self.build_scroll_page(build_connection_page(self))

        self.stack.addWidget(self.page_model)
        self.stack.addWidget(self.page_style)
        self.stack.addWidget(self.page_info)
        self.stack.addWidget(self.page_connection)
        body_layout.addWidget(self.stack, 1)

        root.addLayout(body_layout)

        self.stack.setCurrentIndex(0)
        self.btn_model.setChecked(True)

        self.finalize_page_setup()

    def finalize_page_setup(self):
        self.apply_page_button_group("model")
        self.apply_page_button_group("style")
        self.apply_page_button_group("info")
        self.apply_page_button_group("connection")
        self.sync_nav_buttons()
        self.logic.update_model_page_mode_visibility()

    def build_top_bar(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("topBar")
        frame.setFixedHeight(UI_SIZE["top_bar_height"] + 10)

        layout = QHBoxLayout(frame)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(UI_SIZE["spacing_medium"])

        title = QLabel("控制中心")
        title.setStyleSheet(f"font-size: {UI_SIZE['font_title']}px; font-weight: bold;")
        layout.addWidget(title)
        layout.addStretch()

        self.btn_reply_pipeline = QPushButton("回复文本")
        self.btn_close = QPushButton("关闭")

        self.apply_button_preset(self.btn_reply_pipeline, "top")
        self.apply_button_preset(self.btn_close, "top")

        self.btn_reply_pipeline.clicked.connect(self.open_reply_pipeline_requested.emit)
        self.btn_close.clicked.connect(self.close)

        layout.addWidget(self.btn_reply_pipeline)
        layout.addWidget(self.btn_close)

        return frame

    def build_nav_bar(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("navFrame")

        layout = QVBoxLayout(frame)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(UI_SIZE["spacing_medium"])

        model_meta = get_page_meta("model")
        style_meta = get_page_meta("style")
        info_meta = get_page_meta("info")

        self.btn_model = BookmarkButton(model_meta["nav_text"])
        self.btn_style = BookmarkButton(style_meta["nav_text"])
        self.btn_info = BookmarkButton(info_meta["nav_text"])

        self.apply_button_preset(self.btn_model, "bookmark")
        self.apply_button_preset(self.btn_style, "bookmark")
        self.apply_button_preset(self.btn_info, "bookmark")

        self.btn_model.clicked.connect(lambda: self.try_switch_page(0, "model"))
        self.btn_style.clicked.connect(lambda: self.try_switch_page(1, "style"))
        self.btn_info.clicked.connect(lambda: self.try_switch_page(2, "info"))
        self.btn_connection = BookmarkButton("连接配置")
        self.apply_button_preset(self.btn_connection, "bookmark")
        self.btn_connection.clicked.connect(self.switch_to_connection_page)

        layout.addWidget(self.btn_connection)
        layout.addWidget(self.btn_model)
        layout.addWidget(self.btn_style)
        layout.addWidget(self.btn_info)
        layout.addStretch()
        return frame

    # =========================================================
    # 通用小区块
    # =========================================================
    def build_section_card(self, title_text: str) -> QFrame:
        frame = QFrame()
        frame.setObjectName("sectionCard")

        layout = QVBoxLayout(frame)
        layout.setContentsMargins(
            UI_SIZE["page_section_margin"],
            UI_SIZE["page_section_margin"],
            UI_SIZE["page_section_margin"],
            UI_SIZE["page_section_margin"],
        )
        layout.setSpacing(UI_SIZE["spacing_medium"])

        title = QLabel(title_text)
        title.setStyleSheet(
            f"font-size: {UI_SIZE['font_section_title']}px; font-weight: bold;"
        )
        layout.addWidget(title)
        return frame

    def build_scroll_page(self, inner_page: QWidget) -> QScrollArea:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)  # type: ignore
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(inner_page)
        return scroll

    def add_labeled_widget(self, parent_layout: QVBoxLayout, label_text: str, widget: QWidget):
        label = QLabel(label_text)
        label.setStyleSheet("font-weight: bold; color: #FFFFFF;")
        label.setFixedHeight(UI_SIZE["section_title_height"])
        parent_layout.addWidget(label)

        if isinstance(widget, (QLineEdit, QComboBox)):
            widget.setFixedHeight(UI_SIZE["input_min_height"])
        elif isinstance(widget, QTextEdit):
            widget.setMinimumHeight(UI_SIZE["textedit_min_height"])
            widget.setMaximumHeight(UI_SIZE["textedit_max_height"])

        parent_layout.addWidget(widget)

    def add_labeled_row(self, parent_layout: QVBoxLayout, label_text: str, widget: QWidget, button: QWidget | None = None):
        label = QLabel(label_text)
        label.setStyleSheet("font-weight: bold; color: #FFFFFF;")
        label.setFixedHeight(UI_SIZE["section_title_height"])

        row = QHBoxLayout()
        row.setSpacing(UI_SIZE["spacing_medium"])

        if isinstance(widget, (QLineEdit, QComboBox)):
            widget.setFixedHeight(UI_SIZE["input_min_height"])

        row.addWidget(widget, 1)

        if button is not None:
            button.setFixedHeight(button.height() if button.height() > 0 else UI_SIZE["input_min_height"])
            row.addWidget(button)

        parent_layout.addWidget(label)
        parent_layout.addLayout(row)

    def make_labeled_slider(self, parent_layout, title: str) -> QSlider:
        wrap = QFrame()
        row = QHBoxLayout(wrap)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(UI_SIZE["spacing_medium"])

        label = QLabel(title)
        label.setFixedWidth(70)

        value_label = QLabel("50")
        value_label.setFixedWidth(36)
        value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setMinimum(0)
        slider.setMaximum(100)
        slider.setValue(50)

        slider.valueChanged.connect(lambda v: value_label.setText(str(v)))
        slider.valueChanged.connect(lambda _: self.refresh_dirty("style"))

        row.addWidget(label)
        row.addWidget(slider, 1)
        row.addWidget(value_label)

        parent_layout.addWidget(wrap)
        return slider
    def force_close_once(self):
        self._force_close = True
    # =========================================================
    # loader / logic / forms 转发
    # =========================================================
    def load_current_state(self):
        self.loader.load_current_state()
        self.refresh_tts_backend_status()
        self._set_nav_checked_manual(self.stack.currentIndex())
        
    def reload_role_list(self):
        self.loader.reload_role_list()

    def reload_model_list(self):
        self.loader.reload_model_list()

    def reload_voice_list(self):
        self.loader.reload_voice_list()

    def reload_style_list(self):
        self.loader.reload_style_list()

    def refresh_top_bar(self):
        self.loader.refresh_top_bar()

    def refresh_info_page(self):
        self.loader.refresh_info_page()

    def reload_scheme_list(self):
        self.loader.reload_scheme_list()

    def reload_saved_combo_list(self):
        self.loader.reload_saved_combo_list()

    def load_workspace_draft(self):
        self.loader.load_workspace_draft()

    def update_model_page_mode_visibility(self):
        self.logic.update_model_page_mode_visibility()

    def on_text_scene_changed(self):
        self.logic.on_text_scene_changed()

    def on_voice_scene_changed(self):
        self.logic.on_voice_scene_changed()

    def collect_style_form_data(self) -> dict:
        return self.forms.collect_style_form_data()

    def collect_voice_form_data(self) -> dict:
        return self.forms.collect_voice_form_data()

    def collect_info_form_data(self) -> dict:
        return self.forms.collect_info_form_data()

    def fill_voice_editor_from_current_profile(self):
        self.forms.fill_voice_editor_from_current_profile()

    def fill_style_editor_from_current_profile(self):
        self.forms.fill_style_editor_from_current_profile()

    def on_connection_model_changed(self):
        self.cc_actions.on_connection_model_changed()

    def clear_connection_policy_override(self):
        self.cc_actions.clear_connection_policy_override()

    def apply_connection_policy_override(self):
        self.cc_actions.apply_connection_policy_override()

    # =========================================================
    # state 转发
    # =========================================================
    def set_dirty(self, page_key: str, dirty: bool):
        self.state.set_dirty(page_key, dirty)

    def refresh_dirty(self, page_key: str):
        self.state.refresh_dirty(page_key)

    def refresh_all_dirty(self):
        self.state.refresh_all_dirty()

    def capture_snapshot(self, page_key: str):
        self.state.capture_snapshot(page_key)

    def capture_all_snapshots(self):
        self.state.capture_all_snapshots()

    def discard_page_changes(self, page_key: str):
        self.state.discard_page_changes(page_key)

    def update_window_title(self):
        self.state.update_window_title()

    def page_key_from_index(self, index: int) -> str:
        return self.state.page_key_from_index(index)

    def sync_nav_buttons(self):
        self.state.sync_nav_buttons()

    def ask_apply_changes(self, page_key: str) -> str:
        return self.state.ask_apply_changes(page_key)

    def is_model_page_changed(self) -> bool:
        return self.state.is_model_page_changed()

    def is_style_page_changed(self) -> bool:
        return self.state.is_style_page_changed()

    def is_info_page_changed(self) -> bool:
        return self.state.is_info_page_changed()

    # =========================================================
    # actions 转发
    # =========================================================
    def apply_page(self, page_key: str):
        self.cc_actions.apply_page(page_key) # type: ignore

    def apply_model_page(self):
        self.cc_actions.apply_model_page() # type: ignore

    def save_model_page_default(self):
        self.cc_actions.save_model_page_default() # type: ignore

    def apply_style_page(self):
        self.cc_actions.apply_style_page() # type: ignore

    def save_style_page(self):
        self.cc_actions.save_style_page() # type: ignore

    def reset_style_page(self):
        self.cc_actions.reset_style_page() # type: ignore

    def apply_info_page(self):
        self.cc_actions.apply_info_page() # type: ignore

    def on_role_changed_in_model_page(self):
        self.cc_actions.on_role_changed_in_model_page() # type: ignore

    def on_voice_profile_selected(self):
        self.cc_actions.on_voice_profile_selected() # type: ignore

    def on_style_profile_selected(self):
        self.cc_actions.on_style_profile_selected() # type: ignore

    def on_saved_combo_selected(self):
        self.cc_actions.on_saved_combo_selected() # type: ignore

    def on_scheme_name_selected_in_info_page(self):
        self.cc_actions.on_scheme_name_selected_in_info_page()  # type: ignore

    def on_tts_model_changed(self):
        self.cc_actions.on_tts_model_changed() # type: ignore

    def on_model_page_selection_changed(self):
        self.cc_actions.on_model_page_selection_changed() # type: ignore

    def on_output_mode_changed_in_model_page(self):
        self.cc_actions.on_output_mode_changed_in_model_page() # type: ignore

    def _get_selected_tts_backend(self) -> str:
        return self.cc_actions._get_selected_tts_backend() # type: ignore

    def _get_selected_tts_package(self) -> dict:
        return self.cc_actions._get_selected_tts_package() # type: ignore

    def update_tts_backend_indicator(self, status: dict):
        self.cc_actions.update_tts_backend_indicator(status) # type: ignore

    def refresh_tts_backend_status(self):
        self.cc_actions.refresh_tts_backend_status() # type: ignore

    def apply_chat_model_selection(self):
        self.cc_actions.apply_chat_model_selection() # type: ignore

    def apply_tts_backend_selection(self):
        self.cc_actions.apply_tts_backend_selection() # type: ignore

    def show_tts_loading_inline(self, text: str = "正在加载语音后端…", percent: int = 0):
        self.cc_actions.show_tts_loading_inline(text, percent) # type: ignore

    def update_tts_loading_inline(self, text: str, percent: int):
        self.cc_actions.update_tts_loading_inline(text, percent) # type: ignore

    def hide_tts_loading_inline(self):
        self.cc_actions.hide_tts_loading_inline() # type: ignore

    def open_role_config_folder(self):
        self.cc_actions.open_role_config_folder() # type: ignore

    def open_voice_config_folder(self):
        self.cc_actions.open_voice_config_folder() # type: ignore

    def preview_role_config_text(self):
        self.cc_actions.preview_role_config_text()# type: ignore

    def run_combo_preview(self):
        self.cc_actions.run_combo_preview()# type: ignore

    def mock_audio_play(self):
        self.cc_actions.mock_audio_play()# type: ignore

    def get_selected_style_id_for_save(self) -> str:
        return self.cc_actions.get_selected_style_id_for_save()# type: ignore

    def get_selected_voice_id_for_save(self) -> str:
        return self.cc_actions.get_selected_voice_id_for_save()# type: ignore

    def save_combo_preset(self):
        self.cc_actions.save_combo_preset()# type: ignore

    def load_combo_preset(self):
        self.cc_actions.load_combo_preset()# type: ignore

    def delete_combo_preset(self):
        self.cc_actions.delete_combo_preset()# type: ignore

    def save_workspace_draft(self):
        self.cc_actions.save_workspace_draft()# type: ignore

    def apply_combo_scheme_selection(self):
        self.cc_actions.apply_combo_scheme_selection()  # type: ignore

    def on_ollama_download_model_selected(self):
        self.cc_actions.on_ollama_download_model_selected()

    def update_connection_page_provider_visibility(self):
        self.cc_actions.update_connection_page_provider_visibility()
    # =========================================================
    # 第二页补充回调
    # =========================================================
    def on_style_page_changed(self):
        self.refresh_dirty("style")

    def on_info_page_changed(self):
        self.refresh_dirty("info")
        self.refresh_info_page()
        
    def _apply_preview_button_icons(self):
        if not hasattr(self, "btn_combo_play_pause") or not hasattr(self, "btn_combo_loop"):
            return

        play_path = ASSET_PATHS.get("player.play", "")
        pause_path = ASSET_PATHS.get("player.pause", "")
        loop_path = ASSET_PATHS.get("player.loop", "")

        self._preview_play_icon = QIcon(play_path) if play_path and Path(play_path).exists() else QIcon()
        self._preview_pause_icon = QIcon(pause_path) if pause_path and Path(pause_path).exists() else QIcon()
        self._preview_loop_icon = QIcon(loop_path) if loop_path and Path(loop_path).exists() else QIcon()

        play_icon_size = QSize(22, 22)
        loop_icon_size = QSize(24, 24)

        if self.btn_combo_play_pause is not None:
            self.btn_combo_play_pause.setIcon(self._preview_play_icon)
            self.btn_combo_play_pause.setIconSize(play_icon_size)
            self.btn_combo_play_pause.setText("")
            self.btn_combo_play_pause.setToolTip("播放 / 暂停")

        if self.btn_combo_loop is not None:
            self.btn_combo_loop.setIcon(self._preview_loop_icon)
            self.btn_combo_loop.setIconSize(loop_icon_size)
            self.btn_combo_loop.setText("")
            self.btn_combo_loop.setToolTip("循环播放开关")

    def _format_preview_ms(self, ms: int) -> str:
        total_sec = max(0, int(ms / 1000))
        m = total_sec // 60
        s = total_sec % 60
        return f"{m}:{s:02d}"
    # =========================================================
    # 第三页补充回调
    # =========================================================
    def _on_preview_position_changed(self, position: int):
        if self.combo_progress_slider is not None:
            duration = max(1, self.preview_audio_player.duration())
            self.combo_progress_slider.blockSignals(True)
            self.combo_progress_slider.setValue(int(position * 1000 / duration))
            self.combo_progress_slider.blockSignals(False)

        if self.combo_time_label is not None:
            self.combo_time_label.setText(
                f"{self._format_preview_ms(position)} / {self._format_preview_ms(self.preview_audio_player.duration())}"
            )

    def _on_preview_duration_changed(self, duration: int):
        if self.combo_time_label is not None:
            self.combo_time_label.setText(
                f"{self._format_preview_ms(0)} / {self._format_preview_ms(duration)}"
            )

    def _on_preview_playback_state_changed(self, state):
        is_playing = state == QMediaPlayer.PlaybackState.PlayingState
        self.combo_is_playing = is_playing

        if self.btn_combo_play_pause is not None:
            self.btn_combo_play_pause.setText("")
            self.btn_combo_play_pause.setIcon(self._preview_pause_icon if is_playing else self._preview_play_icon)
            self.btn_combo_play_pause.setIconSize(QSize(22, 22))
            self.btn_combo_play_pause.setToolTip("暂停" if is_playing else "播放")

        if (
            state == QMediaPlayer.PlaybackState.StoppedState
            and self.combo_loop_enabled
            and self.current_test_audio_path
        ):
            self.preview_audio_player.setPosition(0)
            self.preview_audio_player.play()

    def refresh_combo_loop_button(self):
        if self.btn_combo_loop is None:
            return

        self.btn_combo_loop.setText("")
        self.btn_combo_loop.setIcon(self._preview_loop_icon)
        self.btn_combo_loop.setIconSize(QSize(24, 24))
        self.btn_combo_loop.setToolTip("循环播放已开启" if self.combo_loop_enabled else "循环播放已关闭")
        self.btn_combo_loop.setObjectName("audioLoopButtonOn" if self.combo_loop_enabled else "audioLoopButtonOff")
        self.btn_combo_loop.style().unpolish(self.btn_combo_loop)
        self.btn_combo_loop.style().polish(self.btn_combo_loop)
        self.btn_combo_loop.update()


    def _set_nav_checked_manual(self, page_index: int):
        buttons = [
            getattr(self, "btn_model", None),
            getattr(self, "btn_style", None),
            getattr(self, "btn_info", None),
            getattr(self, "btn_connection", None),
        ]
        for idx, btn in enumerate(buttons):
            if btn is not None:
                btn.setChecked(idx == page_index)

    def switch_to_connection_page(self):
        current_index = self.stack.currentIndex()

        # 离开前 3 页时，仍然保留原来的“未应用提醒”
        if current_index in (0, 1, 2):
            current_key = self.page_key_from_index(current_index)
            if self.page_dirty.get(current_key, False):
                decision = self.ask_apply_changes(current_key)
                if decision == "cancel":
                    return
                if decision == "apply":
                    self.apply_page(current_key)
                elif decision == "discard":
                    self.discard_page_changes(current_key)

        self.stack.setCurrentIndex(3)
        self._set_nav_checked_manual(3)

    def try_switch_page(self, page_index: int, target_key: str):
        # 如果当前正处于连接页，返回前三页时不走旧 state 的索引映射
        if self.stack.currentIndex() == 3:
            self.stack.setCurrentIndex(page_index)
            self._set_nav_checked_manual(page_index)
            return

        self.state.try_switch_page(page_index, target_key)
        self._set_nav_checked_manual(self.stack.currentIndex())

    def reload_connection_page(self):
        self.loader.load_connection_page()

    def on_connection_page_changed(self):
        self.cc_actions.on_connection_page_changed()

    def test_ollama_connection(self):
        self.cc_actions.test_ollama_connection()

    def refresh_ollama_model_runtime(self):
        self.cc_actions.refresh_ollama_model_runtime()

    def use_selected_connection_model(self):
        self.cc_actions.use_selected_connection_model()

    def download_ollama_model(self, model_name: str):
        self.cc_actions.download_ollama_model(model_name)

    def test_gpt_sovits_connection(self):
        self.cc_actions.test_gpt_sovits_connection()

    def run_connection_startup_check(self):
        self.cc_actions.run_connection_startup_check()

    def save_connection_page(self):
        self.cc_actions.save_connection_page()
    # =========================================================
    # 关闭事件
    # =========================================================
    def closeEvent(self, event):
        if not getattr(self, "_force_close", False):
            self.state.close_event(event)
            if not event.isAccepted():
                return
        else:
            event.accept()
            self._force_close = False

        try:
            if self.preview_audio_player is not None:
                self.preview_audio_player.stop()
                self.preview_audio_player.setSource(QUrl())
        except Exception:
            pass

        try:
            if self.preview_audio_output is not None:
                self.preview_audio_output.setVolume(1.0)
        except Exception:
            pass

        try:
            load_thread = getattr(self.cc_actions, "_tts_load_thread", None)
            if load_thread is not None and load_thread.isRunning():
                load_thread.quit()
                load_thread.wait(1000)
        except Exception:
            pass

        self.current_test_audio_path = ""
        super().closeEvent(event)