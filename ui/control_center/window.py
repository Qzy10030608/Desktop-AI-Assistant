from pathlib import Path

from PySide6.QtGui import QIcon, QPainter, QPixmap, QColor, QPen
from PySide6.QtCore import QSize
from PySide6.QtCore import Qt, Signal, QSize, QUrl
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtWidgets import QPushButton, QLabel, QFrame, QHBoxLayout, QVBoxLayout
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
)

from bootstrap.machine_profile_service import MachineProfileService  # type: ignore
from bootstrap.startup_check_service import StartupCheckService  # type: ignore
from services.reply.llm_backend_controller_service import LLMBackendControllerService  # type: ignore

from ui.control_center.control_center_pages.page_connection import build_connection_page  # type: ignore

from config import (  # type: ignore
    DEFAULT_OUTPUT_MODE,
    PRESETS_DIR,
    WORKSPACE_DRAFT_IDENTITY_FILE,
    WORKSPACE_STYLE_SELECTION_FILE,
    WORKSPACE_VOICE_SELECTION_FILE,
    WORKSPACE_PERSONA_DRAFT_FILE,
    WORKSPACE_PREVIEW_TEXT_FILE,
    APP_ICON_FILE,
)

from services.tts.tts_backend_controller_service import TTSBackendControllerService
from services.tts.tts_package_service import TTSPackageService
from services.download_service import DownloadService
from services.persona.role_service import RoleService
from services.persona.style_profile_service import StyleProfileService
from services.persona.voice_profile_service import VoiceProfileService
from services.model_registry_service import ModelRegistryService
from services.developer.developer_mode_service import DeveloperModeService
from services.maintenance.cleanup_service import CleanupService
from services.runtime.chat_display_config_service import ChatDisplayConfigService
from services.desktop.language.ui_language_service import get_ui_language_service

from ui.control_center.config import (
    UI_SIZE,
    UI_COLOR,
    CONTROL_CENTER_STARTUP,
    DESKTOP_UI_SIZE,
    DESKTOP_UI_COLOR,
    DESKTOP_LAYOUT_BREAKPOINTS,
    DESKTOP_LAYOUT_PRESETS,
    ASSET_PATHS,
    build_qss,
    get_button_preset,
    get_page_meta,
    get_page_button_groups,
)

from ui.control_center.loader import ControlCenterLoader
from ui.control_center.logic import ControlCenterLogic
from ui.control_center.forms import ControlCenterForms
from ui.control_center.state import ControlCenterState
from ui.control_center.actions import ControlCenterActions  # type: ignore
from ui.control_center.desktop import (  # type: ignore
    DesktopController,
    DesktopPageLoader,
    DesktopPageRuntime,
    build_desktop_page,
)

from ui.control_center.control_center_widgets.bookmark_button import BookmarkButton  # type: ignore
from ui.control_center.control_center_pages.page_model import build_model_page  # type: ignore
from ui.control_center.control_center_pages.page_basic_settings import build_basic_settings_page  # type: ignore
from ui.control_center.control_center_pages.page_style import build_style_page  # type: ignore
from ui.control_center.control_center_pages.page_info import build_info_page  # type: ignore
class NavImageButton(BookmarkButton):
    """
    左侧导航图片按钮。
    """

    _trim_cache = {}

    def __init__(self, text: str = "", bg_path: str = "", icon_path: str = "", parent=None):
        super().__init__(text, parent)

        self._bg_path = bg_path
        self._icon_path = icon_path

        self._bg_pixmap = self._load_trimmed_pixmap(bg_path)
        self._icon_pixmap = QPixmap(icon_path) if icon_path else QPixmap()

        self._hovered = False

        self.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                color: transparent;
                padding: 0px;
                margin: 0px;
            }
        """)

    @classmethod
    def _load_trimmed_pixmap(cls, path: str) -> QPixmap:
        
        if not path:
            return QPixmap()

        if path in cls._trim_cache:
            return cls._trim_cache[path]

        pixmap = QPixmap(path)
        if pixmap.isNull():
            cls._trim_cache[path] = QPixmap()
            return cls._trim_cache[path]

        image = pixmap.toImage()
        w = image.width()
        h = image.height()

        # 可在 config.py 控制：
        # alpha 小于该值视为透明
        alpha_threshold = int(UI_SIZE.get("nav_button_image_alpha_threshold", 8))

        # 接近白色的像素视为空白背景
        white_threshold = int(UI_SIZE.get("nav_button_image_white_threshold", 245))

        left = w
        right = -1
        top = h
        bottom = -1

        for y in range(h):
            for x in range(w):
                color = image.pixelColor(x, y)

                is_transparent = color.alpha() <= alpha_threshold
                is_white = (
                    color.red() >= white_threshold
                    and color.green() >= white_threshold
                    and color.blue() >= white_threshold
                )

                if not is_transparent and not is_white:
                    if x < left:
                        left = x
                    if x > right:
                        right = x
                    if y < top:
                        top = y
                    if y > bottom:
                        bottom = y

        # 如果没有找到有效区域，就退回原图
        if right < left or bottom < top:
            cls._trim_cache[path] = pixmap
            return pixmap

        extra = int(UI_SIZE.get("nav_button_image_crop_extra", 0))
        left = max(0, left - extra)
        top = max(0, top - extra)
        right = min(w - 1, right + extra)
        bottom = min(h - 1, bottom + extra)

        cropped = image.copy(
            left,
            top,
            right - left + 1,
            bottom - top + 1,
        )

        cls._trim_cache[path] = QPixmap.fromImage(cropped)
        return cls._trim_cache[path]

    def set_bg_path(self, bg_path: str):
        self._bg_path = bg_path
        self._bg_pixmap = self._load_trimmed_pixmap(bg_path)
        self.update()

    def set_icon_path(self, icon_path: str):
        self._icon_path = icon_path
        self._icon_pixmap = QPixmap(icon_path) if icon_path else QPixmap()
        self.update()

    def enterEvent(self, event):
        self._hovered = True
        super().enterEvent(event)
        self.update()

    def leaveEvent(self, event):
        self._hovered = False
        super().leaveEvent(event)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        rect = self.rect()

        radius = int(UI_SIZE.get("nav_button_radius", 16))
        border_width = int(UI_SIZE.get("nav_button_border_width", 1))

        # =====================================================
        # 1. 按钮绘制区域
        # =====================================================
        base_pad_h = int(UI_SIZE.get("nav_button_base_padding_h", 0))
        base_pad_v = int(UI_SIZE.get("nav_button_base_padding_v", 0))

        base_rect = rect.adjusted(
            base_pad_h,
            base_pad_v,
            -base_pad_h,
            -base_pad_v,
        )

        # =====================================================
        # 2. 先画备用底色
        # 图片透明区域后面需要有一层底，否则边缘可能太暗
        # =====================================================
        if self.isDown():
            base_color = QColor(
                UI_COLOR.get(
                    "nav_button_base_bg_pressed",
                    UI_COLOR.get("nav_button_base_bg_checked", "#142238"),
                )
            )
        elif self.isChecked():
            base_color = QColor(UI_COLOR.get("nav_button_base_bg_checked", "#142238"))
        elif self._hovered:
            base_color = QColor(UI_COLOR.get("nav_button_base_bg_hover", "#16263A"))
        else:
            base_color = QColor(UI_COLOR.get("nav_button_base_bg", "#101820"))

        if bool(UI_SIZE.get("nav_button_draw_base", True)):
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(base_color)
            painter.drawRoundedRect(base_rect, radius, radius)

        # =====================================================
        # 3. 画裁剪后的按钮图片
        # 这一步才会让 透明蓝紫色.png 像主页面一样包住文字
        # =====================================================
        if not self._bg_pixmap.isNull():
            image_pad_h = int(UI_SIZE.get("nav_button_image_padding_h", 0))
            image_pad_v = int(UI_SIZE.get("nav_button_image_padding_v", 0))
            image_y_offset = int(UI_SIZE.get("nav_button_image_y_offset", 0))

            image_rect = base_rect.adjusted(
                image_pad_h,
                image_pad_v + image_y_offset,
                -image_pad_h,
                -image_pad_v + image_y_offset,
            )

            painter.drawPixmap(image_rect, self._bg_pixmap)
        else:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(UI_COLOR.get("nav_button_fallback_bg", "#182A3D")))
            painter.drawRoundedRect(base_rect, radius, radius)

        # =====================================================
        # 4. 边框，可通过 config.py 关闭
        # =====================================================
        if bool(UI_SIZE.get("nav_button_draw_border", False)):
            if self.isDown():
                border_color = QColor(UI_COLOR.get("nav_button_border_active", "#3A8DFF"))
            elif self.isChecked():
                border_color = QColor(UI_COLOR.get("nav_button_border_checked", "#8BB8FF"))
            elif self._hovered:
                border_color = QColor(UI_COLOR.get("nav_button_border_hover", "#8BB8FF"))
            else:
                border_color = QColor(UI_COLOR.get("nav_button_border_normal", "#2E405A"))

            pen = QPen(border_color)
            pen.setWidth(border_width)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(
                base_rect.adjusted(1, 1, -1, -1),
                radius,
                radius,
            )

        # =====================================================
        # 5. 折叠态图标模式：系统 / 语音
        # =====================================================
        if not self._icon_pixmap.isNull() and not self.text():
            icon_size = int(UI_SIZE.get("nav_collapsed_icon_size", 28))
            icon = self._icon_pixmap.scaled(
                icon_size,
                icon_size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )

            x = rect.center().x() - icon.width() // 2
            y = rect.center().y() - icon.height() // 2
            painter.drawPixmap(x, y, icon)
            return

        # =====================================================
        # 6. 文字
        # =====================================================
        painter.setPen(QColor(UI_COLOR.get("nav_button_text", "#FFFFFF")))

        font = self.font()
        font.setBold(True)
        font.setPointSize(int(UI_SIZE.get("nav_button_text_font_size", 14)))
        painter.setFont(font)

        painter.drawText(
            rect,
            Qt.AlignmentFlag.AlignCenter,
            self.text(),
        )
class NavToggleImageButton(QPushButton):
    """
    左侧导航缩进 / 展开按钮。

    设计目标：
    1. 不使用 ui/resources / qrc；
    2. 图标从 ui/assets 的 左缩进.png / 右拉出.png 读取；
    3. 默认不画蓝色水晶背景；
    4. 尺寸、颜色全部从 config.py 的 UI_SIZE / UI_COLOR 读取。
    """

    def __init__(self, parent=None):
        super().__init__("", parent)

        self._bg_path = ""
        self._icon_path = ""
        self._bg_pixmap = QPixmap()
        self._icon_pixmap = QPixmap()
        self._hovered = False

        self.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                padding: 0px;
                margin: 0px;
            }
        """)

    def set_bg_path(self, bg_path: str):
        self._bg_path = bg_path
        self._bg_pixmap = QPixmap(bg_path) if bg_path else QPixmap()
        self.update()

    def set_icon_path(self, icon_path: str):
        self._icon_path = icon_path
        self._icon_pixmap = QPixmap(icon_path) if icon_path else QPixmap()
        self.update()

    def enterEvent(self, event):
        self._hovered = True
        super().enterEvent(event)
        self.update()

    def leaveEvent(self, event):
        self._hovered = False
        super().leaveEvent(event)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        rect = self.rect()

        radius = int(UI_SIZE.get("nav_toggle_radius", 16))
        border_width = int(UI_SIZE.get("nav_toggle_border_width", 1))

        # =====================================================
        # 1. 可选背景
        # 默认 False：不画蓝色底，只显示缩进 / 展开图标
        # =====================================================
        if bool(UI_SIZE.get("nav_toggle_show_background", False)):
            if not self._bg_pixmap.isNull():
                painter.drawPixmap(rect, self._bg_pixmap)
            else:
                fallback_color = QColor(UI_COLOR.get("nav_toggle_fallback_bg", "#348DFF"))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(fallback_color)
                painter.drawRoundedRect(rect, radius, radius)

        # =====================================================
        # 2. 中间图标：左缩进 / 右拉出
        # =====================================================
        if not self._icon_pixmap.isNull():
            icon_size = int(UI_SIZE.get("nav_toggle_icon_size", 46))
            icon = self._icon_pixmap.scaled(
                icon_size,
                icon_size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )

            x = rect.center().x() - icon.width() // 2
            y = rect.center().y() - icon.height() // 2
            painter.drawPixmap(x, y, icon)

        # =====================================================
        # 3. hover / pressed 边框
        # =====================================================
        if self.isDown():
            border_color = QColor(UI_COLOR.get("nav_toggle_border_active", "#3A8DFF"))
        elif self._hovered:
            border_color = QColor(UI_COLOR.get("nav_toggle_border_hover", "#8BB8FF"))
        else:
            border_color = None

        if border_color is not None:
            pen = QPen(border_color)
            pen.setWidth(border_width)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(
                rect.adjusted(1, 1, -2, -2),
                radius,
                radius,
            )
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

        self.nav_collapsed = False
        self.UI_SIZE = UI_SIZE
        self.DESKTOP_UI_SIZE = DESKTOP_UI_SIZE
        self.DESKTOP_UI_COLOR = DESKTOP_UI_COLOR
        self.DESKTOP_LAYOUT_BREAKPOINTS = DESKTOP_LAYOUT_BREAKPOINTS
        self.DESKTOP_LAYOUT_PRESETS = DESKTOP_LAYOUT_PRESETS
        self.CONTROL_CENTER_STARTUP = CONTROL_CENTER_STARTUP
        self._startup_geometry_applied = False
        self.ui_language_service = get_ui_language_service()

        self.setWindowTitle(self.tr_ui("control.title"))
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
        # 服务层
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
        self.developer_mode_service = DeveloperModeService()
        self.developer_mode_enabled_at_startup = bool(self.developer_mode_service.is_enabled())
        self.cleanup_service = CleanupService()
        self.chat_display_config_service = ChatDisplayConfigService()

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

        # 只保留风格设计和角色组合脏状态
        self.page_dirty = {
            "style": False,
            "info": False,
        }

        self._init_page_refs()

        # -------------------------
        # 分层对象
        # -------------------------
        self.loader = ControlCenterLoader(self)
        self.logic = ControlCenterLogic(self)
        self.forms = ControlCenterForms(self)
        self.state = ControlCenterState(self)
        self.cc_actions = ControlCenterActions(self)
        self.desktop_runtime = DesktopPageRuntime(self)
        self.desktop_page_loader = DesktopPageLoader(self)
        self.desktop_controller = DesktopController(self, runtime=self.desktop_runtime)
        self._initial_state_loaded = False

        # -------------------------
        # UI
        # -------------------------
        self.init_ui()
        self.setStyleSheet(build_qss())
        self._apply_preview_button_icons()
        self.refresh_combo_loop_button()

        # 初次加载
        self.load_current_state()
        self._initial_state_loaded = True
        self.logic.initialize_style_scene_defaults()
        self.logic.update_model_page_mode_visibility()
        self.capture_all_snapshots()

    # =========================================================
    # 页面控件占位声明
    # =========================================================
    def _init_page_refs(self):
        #左侧显示
        self.nav_header_frame = None
        self.nav_title_label = None
        self.btn_nav_toggle = None

        self.nav_system_group_frame = None
        self.nav_voice_group_frame = None

        self.nav_system_group_title = None
        self.nav_voice_group_title = None

        self.btn_nav_system_group = None
        self.btn_nav_voice_group = None
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
        self.summary_desktop_mode_label = None
        self.summary_developer_mode_label = None
        self.summary_execution_backend_label = None
        self.cleanup_category_checks = {}
        self.cleanup_count_labels = {}
        self.cleanup_size_labels = {}
        self.btn_cleanup_scan = None
        self.btn_cleanup_delete_selected = None
        self.btn_cleanup_open_folder = None
        self.audio_output_device_combo = None
        self.audio_input_device_combo = None
        self.btn_test_audio_output_device = None
        self.btn_test_audio_input_device = None
        self.audio_input_test_frame = None
        self.audio_input_level_bar = None
        self.audio_input_test_status_label = None
        self.audio_input_test_detail_label = None
        self.basic_cleanup_category_checks = {}
        self.basic_cleanup_count_labels = {}
        self.basic_cleanup_size_labels = {}
        self.btn_basic_cleanup_scan = None
        self.btn_basic_cleanup_delete_selected = None
        self.btn_basic_cleanup_open_folder = None
        self.btn_run_project_integrity_check = None
        self.chat_assistant_display_name_edit = None
        self.btn_save_chat_display_settings = None
        self.basic_developer_mode_status_label = None
        self.btn_basic_toggle_developer_mode = None
        self.basic_restore_initial_environment_card = None
        self.btn_restore_initial_environment = None
        self.developer_mode_status_label = None
        self.btn_toggle_developer_mode = None
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
        self.current_tts_backend_label = None
        self.tts_connection_hint_label = None

        # 桌面页
        self.desktop_mode_status_label = None
        self.desktop_mode_card = None
        self.desktop_roots_card = None
        self.desktop_apps_card = None
        self.desktop_readonly_card = None
        self.desktop_overview_card = None
        self.desktop_file_card = None
        self.desktop_software_card = None
        self.desktop_sandbox_card = None
        self.desktop_status_mode_value = None
        self.desktop_status_local_value = None
        self.desktop_status_confirmed_value = None
        self.desktop_status_root_count_value = None
        self.desktop_status_app_count_value = None
        self.desktop_mode_summary_label = None
        self.desktop_apps_hint_label = None
        self.desktop_readonly_hint_label = None
        self.desktop_file_hint_label = None
        self.desktop_disk_hint_label = None
        self.desktop_file_path_label = None
        self.desktop_sandbox_hint_label = None
        self.desktop_sandbox_summary_label = None
        self.desktop_readonly_summary_label = None
        self.desktop_runtime_root_combo = None
        self.desktop_runtime_target_path_label = None
        self.desktop_readonly_result_display = None
        self.desktop_sandbox_result_display = None
        self.desktop_disk_table = None
        self.desktop_file_table = None
        self.desktop_apps_table = None
        self.desktop_app_filter_combo = None
        self.desktop_apps_edit_toggle = None
        self.desktop_file_edit_toggle = None
        self.desktop_file_view_combo = None
        self.desktop_file_filter_combo = None
        self.desktop_file_font_combo = None
        self.desktop_software_font_combo = None
        self.desktop_software_discovered_label = None
        self.desktop_software_confirmed_label = None
        self.desktop_software_hidden_label = None

        # 按钮
        self.btn_test_ollama = None
        self.btn_refresh_ollama_models = None
        self.btn_run_local_init = None
        self.btn_refresh_init_preview = None
        self.btn_use_connection_model = None
        self.btn_test_gpt_sovits = None
        self.btn_run_startup_check = None
        self.btn_save_connection = None
        self.btn_clear_policy_override = None
        self.btn_apply_policy_override = None
        self.btn_connection = None
        self.btn_basic_settings = None
        self.btn_desktop = None
        self.btn_desktop_mode_disabled = None
        self.btn_desktop_mode_restricted = None
        self.btn_desktop_mode_trusted = None
        self.btn_desktop_mode_test = None
        self.desktop_record_widget = None
        self.desktop_test_backend_widget = None
        self.desktop_test_backend_label = None
        self.btn_desktop_shaofu = None
        self.btn_desktop_format_bottom = None
        self.btn_desktop_load_apps_memory = None
        self.btn_desktop_rescan = None
        self.btn_desktop_clear_apps = None
        self.btn_desktop_read_datetime = None
        self.btn_desktop_list_root = None
        self.btn_desktop_root_meta = None
        self.btn_desktop_open_root = None
        self.btn_desktop_clear_result = None
        self.btn_desktop_clear_sandbox_result = None

        # 策略区
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
    def showEvent(self, event):
        super().showEvent(event)
        self._apply_startup_geometry_once()

    def _apply_startup_geometry_once(self):
        if getattr(self, "_startup_geometry_applied", False):
            return

        cfg = getattr(self, "CONTROL_CENTER_STARTUP", {}) or {}
        screen = self.screen()
        if screen is None:
            return

        available = screen.availableGeometry()
        available_width = max(1, available.width())
        available_height = max(1, available.height())

        width_ratio = float(cfg.get("width_ratio", 0.42))
        height_ratio = float(cfg.get("height_ratio", 0.88))
        min_width = int(cfg.get("min_width", self.UI_SIZE.get("window_min_width", 760)))
        min_height = int(cfg.get("min_height", self.UI_SIZE.get("window_min_height", 820)))
        top_margin = int(cfg.get("top_margin", 20))

        startup_width = min(available_width, max(min_width, int(available_width * width_ratio)))
        startup_height = min(available_height, max(min_height, int(available_height * height_ratio)))

        if bool(cfg.get("prefer_right_side", True)):
            x = available.x() + available_width - startup_width
        else:
            x = available.x() + max(0, (available_width - startup_width) // 2)

        y = min(
            available.y() + top_margin,
            available.y() + max(0, available_height - startup_height),
        )

        self.resize(startup_width, startup_height)
        self.move(x, y)
        self._startup_geometry_applied = True

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
    def apply_nav_image_button_style(self, button: QPushButton):
        """
        兼容旧调用。

        现在导航按钮背景由 NavImageButton.paintEvent 负责绘制，
        这里不再写 QSS background-image，避免中文路径乱码。
        """
        button.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                color: white;
                font-weight: bold;
            }
        """)

    def update_nav_toggle_icon(self) -> None:
        """
        折叠按钮图标。
        """
        if self.btn_nav_toggle is None:
            return

        if self.nav_collapsed:
            icon_path = ASSET_PATHS.get("nav.toggle_expand_icon", "")
            tooltip = self.tr_ui("control.nav.expand")
        else:
            icon_path = ASSET_PATHS.get("nav.toggle_collapse_icon", "")
            tooltip = self.tr_ui("control.nav.collapse")

        self.btn_nav_toggle.setText("")
        self.btn_nav_toggle.setIcon(QIcon())

        if isinstance(self.btn_nav_toggle, NavToggleImageButton):
            self.btn_nav_toggle.set_icon_path(icon_path)

        self.btn_nav_toggle.setToolTip(tooltip)

    def apply_nav_toggle_crystal_style(self) -> None:
        """
        折叠按钮背景图。
        """
        if self.btn_nav_toggle is None:
            return

        if isinstance(self.btn_nav_toggle, NavToggleImageButton):
            if bool(UI_SIZE.get("nav_toggle_show_background", False)):
                self.btn_nav_toggle.set_bg_path(
                    ASSET_PATHS.get("nav.toggle_crystal_bg", "")
                )
            else:
                self.btn_nav_toggle.set_bg_path("")

        self.btn_nav_toggle.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
            }
        """)
    
    def resizeEvent(self, event):
        super().resizeEvent(event)

        try:
            if self.stack.currentWidget() is self.page_desktop:
                self.desktop_page_loader.apply_responsive_layout()
        except Exception:
            pass

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

        body_layout = QHBoxLayout()
        body_layout.setSpacing(UI_SIZE["spacing_large"])

        self.nav_frame = self.build_nav_bar()
        body_layout.addWidget(self.nav_frame, 0)

        self.stack = QStackedWidget()
        self.page_model = self.build_scroll_page(build_model_page(self))
        self.page_style = self.build_scroll_page(build_style_page(self))
        self.page_info = self.build_scroll_page(build_info_page(self))
        self.page_connection = self.build_scroll_page(build_connection_page(self))
        self.page_desktop = self.build_scroll_page(build_desktop_page(self))
        self.page_basic_settings = self.build_scroll_page(build_basic_settings_page(self))
        self.desktop_scroll_area = self.page_desktop

        self.stack.addWidget(self.page_model)       # 0
        self.stack.addWidget(self.page_style)       # 1
        self.stack.addWidget(self.page_info)        # 2
        self.stack.addWidget(self.page_connection)  # 3
        self.stack.addWidget(self.page_desktop)     # 4
        self.stack.addWidget(self.page_basic_settings)  # 5

        body_layout.addWidget(self.stack, 1)
        root.addLayout(body_layout)

        self.stack.setCurrentIndex(0)
        self.btn_model.setChecked(True)

        self.finalize_page_setup()
        self.retranslate_ui()

    def finalize_page_setup(self):
        self.apply_page_button_group("model")
        self.apply_page_button_group("style")
        self.apply_page_button_group("info")
        self.apply_page_button_group("connection")
        self.apply_page_button_group("desktop")
        self.sync_nav_buttons()
        self.refresh_developer_mode_section()
        self.refresh_basic_audio_devices()
        self.logic.update_model_page_mode_visibility()

    def tr_ui(self, key: str, default: str | None = None, **params) -> str:
        return self.ui_language_service.t(key, default=default, **params)

    def retranslate_ui(self):
        self.setWindowTitle(self.tr_ui("control.title"))
        if getattr(self, "top_title_label", None) is not None:
            self.top_title_label.setText(self.tr_ui("control.title"))
        if self.nav_title_label is not None:
            self.nav_title_label.setText(self.tr_ui("control.title"))
        if getattr(self, "btn_model", None) is not None:
            self.btn_model.setText(self.tr_ui("control.nav.model"))
        if getattr(self, "btn_connection", None) is not None:
            self.btn_connection.setText(self.tr_ui("control.nav.connection"))
        if getattr(self, "btn_basic_settings", None) is not None:
            self.btn_basic_settings.setText(self.tr_ui("control.nav.basic_settings"))
        if getattr(self, "btn_desktop", None) is not None:
            self.btn_desktop.setText(self.tr_ui("control.nav.desktop"))
        if getattr(self, "btn_style", None) is not None:
            self.btn_style.setText(self.tr_ui("control.nav.style"))
        if getattr(self, "btn_info", None) is not None:
            self.btn_info.setText(self.tr_ui("control.nav.info"))
        if self.nav_system_group_title is not None:
            self.nav_system_group_title.setText(self.tr_ui("control.nav.system_group"))
        if self.nav_voice_group_title is not None:
            self.nav_voice_group_title.setText(self.tr_ui("control.nav.voice_group"))
        if getattr(self, "btn_nav_system_group", None) is not None:
            self.btn_nav_system_group.setToolTip(self.tr_ui("control.nav.system_group"))
        if getattr(self, "btn_nav_voice_group", None) is not None:
            self.btn_nav_voice_group.setToolTip(self.tr_ui("control.nav.voice_group"))
        if getattr(self, "btn_reply_pipeline", None) is not None:
            self.btn_reply_pipeline.setText(self.tr_ui("control.reply_text"))
        if getattr(self, "btn_close", None) is not None:
            self.btn_close.setText(self.tr_ui("control.close"))
        self.update_nav_toggle_icon()

    def build_top_bar(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("topBar")
        frame.setFixedHeight(UI_SIZE["top_bar_outer_height"])

        layout = QHBoxLayout(frame)
        layout.setContentsMargins(
            UI_SIZE["top_bar_margin_h"],
            UI_SIZE["top_bar_margin_v"],
            UI_SIZE["top_bar_margin_h"],
            UI_SIZE["top_bar_margin_v"],
        )
        layout.setSpacing(UI_SIZE["spacing_medium"])

        self.top_title_label = QLabel(self.tr_ui("control.title"))
        self.top_title_label.setStyleSheet(f"font-size: {UI_SIZE['font_title']}px; font-weight: bold;")
        layout.addWidget(self.top_title_label)
        layout.addStretch()

        self.btn_reply_pipeline = QPushButton(self.tr_ui("control.reply_text"))
        self.btn_close = QPushButton(self.tr_ui("control.close"))

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
        frame.setMinimumWidth(UI_SIZE["nav_width_expanded"])
        frame.setMaximumWidth(UI_SIZE["nav_width_expanded"])

        layout = QVBoxLayout(frame)
        layout.setContentsMargins(
            UI_SIZE["nav_margin"],
            UI_SIZE["nav_margin"],
            UI_SIZE["nav_margin"],
            UI_SIZE["nav_margin"],
        )
        layout.setSpacing(UI_SIZE["nav_section_spacing"])

        # =========================
        # 顶部标题区
        # =========================
        self.nav_header_frame = QFrame()
        self.nav_header_frame.setObjectName("navHeaderFrame")
        self.nav_header_frame.setFixedHeight(UI_SIZE["nav_header_height"])

        header_layout = QHBoxLayout(self.nav_header_frame)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(UI_SIZE["spacing_small"])

        self.nav_title_label = QLabel("控制中心")
        self.nav_title_label.setObjectName("navTitleLabel")
        self.nav_title_label.setStyleSheet(
            f"font-size: {UI_SIZE['font_title']}px; font-weight: bold;"
        )

        self.btn_nav_toggle = NavToggleImageButton()
        self.btn_nav_toggle.setFixedSize(
            UI_SIZE.get("nav_toggle_button_size", 64),
            UI_SIZE.get("nav_toggle_button_size", 64),
        )
        self.btn_nav_toggle.clicked.connect(self.toggle_nav_collapsed)
        self.apply_nav_toggle_crystal_style()
        self.update_nav_toggle_icon()

        header_layout.addWidget(self.nav_title_label, 1)
        header_layout.addWidget(self.btn_nav_toggle, 0)

        layout.addWidget(self.nav_header_frame)

        # =========================
        # 页面按钮
        # =========================
        nav_button_bg = ASSET_PATHS.get("nav.button_bg", "")

        self.btn_connection = NavImageButton("连接配置", nav_button_bg)
        self.btn_model = NavImageButton("运行配置", nav_button_bg)
        self.btn_basic_settings = NavImageButton("基础设置", nav_button_bg)
        self.btn_desktop = NavImageButton("桌面连接", nav_button_bg)
        self.btn_style = NavImageButton("风格设计", nav_button_bg)
        self.btn_info = NavImageButton("角色组合", nav_button_bg)

        for btn in [self.btn_model, self.btn_connection, self.btn_basic_settings, self.btn_desktop, self.btn_style, self.btn_info]:
            btn.setFixedHeight(UI_SIZE.get("nav_button_height", UI_SIZE["nav_item_height"]))
            self.apply_nav_image_button_style(btn)

        self.btn_model.clicked.connect(lambda: self.try_switch_page(0, "model"))
        self.btn_style.clicked.connect(lambda: self.try_switch_page(1, "style"))
        self.btn_info.clicked.connect(lambda: self.try_switch_page(2, "info"))
        self.btn_connection.clicked.connect(self.switch_to_connection_page)
        self.btn_basic_settings.clicked.connect(lambda: self.try_switch_page(5, "basic_settings"))
        self.btn_desktop.clicked.connect(self.switch_to_desktop_page)

        # =========================
        # 系统配置分组
        # =========================
        self.nav_system_group_title = QLabel("系统配置")
        self.nav_system_group_title.setObjectName("navGroupTitle")
        self.nav_system_group_title.setFixedHeight(UI_SIZE["nav_group_title_height"])
        self.nav_system_group_title.setStyleSheet("color: #9FB3D9; font-weight: bold;")
        layout.addWidget(self.nav_system_group_title)

        self.nav_system_group_frame = QFrame()
        self.nav_system_group_frame.setObjectName("navGroupFrame")
        system_layout = QVBoxLayout(self.nav_system_group_frame)
        system_layout.setContentsMargins(0, 0, 0, 0)
        system_layout.setSpacing(UI_SIZE["nav_group_spacing"])

        system_layout.addWidget(self.btn_model)
        system_layout.addWidget(self.btn_connection)
        system_layout.addWidget(self.btn_basic_settings)
        system_layout.addWidget(self.btn_desktop)

        layout.addWidget(self.nav_system_group_frame)

        # =========================
        # 语音配置分组
        # =========================
        self.nav_voice_group_title = QLabel("语音配置")
        self.nav_voice_group_title.setObjectName("navGroupTitle")
        self.nav_voice_group_title.setFixedHeight(UI_SIZE["nav_group_title_height"])
        self.nav_voice_group_title.setStyleSheet("color: #9FB3D9; font-weight: bold;")
        layout.addWidget(self.nav_voice_group_title)

        self.nav_voice_group_frame = QFrame()
        self.nav_voice_group_frame.setObjectName("navGroupFrame")
        voice_layout = QVBoxLayout(self.nav_voice_group_frame)
        voice_layout.setContentsMargins(0, 0, 0, 0)
        voice_layout.setSpacing(UI_SIZE["nav_group_spacing"])

        voice_layout.addWidget(self.btn_style)
        voice_layout.addWidget(self.btn_info)

        layout.addWidget(self.nav_voice_group_frame)

        # =========================
        # 折叠态分组图标
        # =========================
        self.btn_nav_system_group = QPushButton("")
        self.btn_nav_system_group.setToolTip("系统配置")
        self.btn_nav_system_group.setIcon(QIcon(ASSET_PATHS["nav.group_system"]))
        self.btn_nav_system_group.setIconSize(QSize(
            UI_SIZE["nav_group_icon_size"],
            UI_SIZE["nav_group_icon_size"],
        ))
        self.btn_nav_system_group.setFixedHeight(UI_SIZE["nav_item_height"])
        self.btn_nav_system_group.setVisible(False)
        self.btn_nav_system_group.clicked.connect(lambda: self.try_switch_page(0, "model"))

        self.btn_nav_voice_group = QPushButton("")
        self.btn_nav_voice_group.setToolTip("语音配置")
        self.btn_nav_voice_group.setIcon(QIcon(ASSET_PATHS["nav.group_voice"]))
        self.btn_nav_voice_group.setIconSize(QSize(
            UI_SIZE["nav_group_icon_size"],
            UI_SIZE["nav_group_icon_size"],
        ))
        self.btn_nav_voice_group.setFixedHeight(UI_SIZE["nav_item_height"])
        self.btn_nav_voice_group.setVisible(False)
        self.btn_nav_voice_group.clicked.connect(lambda: self.try_switch_page(1, "style"))

        self.apply_nav_image_button_style(self.btn_nav_system_group)
        self.apply_nav_image_button_style(self.btn_nav_voice_group)

        layout.addWidget(self.btn_nav_system_group)
        layout.addWidget(self.btn_nav_voice_group)

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
        label.setFixedWidth(UI_SIZE["slider_label_width"])

        value_label = QLabel("50")
        value_label.setFixedWidth(UI_SIZE["slider_value_width"])
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
        self._initial_state_loaded = True

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
        self.cc_actions.apply_page(page_key)  # type: ignore

    def apply_model_page(self):
        self.cc_actions.apply_model_page()  # type: ignore

    def save_model_page_default(self):
        self.cc_actions.save_model_page_default()  # type: ignore

    def apply_style_page(self):
        self.cc_actions.apply_style_page()  # type: ignore

    def save_style_page(self):
        self.cc_actions.save_style_page()  # type: ignore

    def reset_style_page(self):
        self.cc_actions.reset_style_page()  # type: ignore

    def apply_info_page(self):
        self.cc_actions.apply_info_page()  # type: ignore

    def on_role_changed_in_model_page(self):
        self.cc_actions.on_role_changed_in_model_page()  # type: ignore

    def on_voice_profile_selected(self):
        self.cc_actions.on_voice_profile_selected()  # type: ignore

    def on_style_profile_selected(self):
        self.cc_actions.on_style_profile_selected()  # type: ignore

    def on_saved_combo_selected(self):
        self.cc_actions.on_saved_combo_selected()  # type: ignore

    def on_scheme_name_selected_in_info_page(self):
        self.cc_actions.on_scheme_name_selected_in_info_page()  # type: ignore

    def on_tts_model_changed(self):
        self.cc_actions.on_tts_model_changed()  # type: ignore

    def on_model_page_selection_changed(self):
        self.cc_actions.on_model_page_selection_changed()  # type: ignore

    def on_output_mode_changed_in_model_page(self):
        self.cc_actions.on_output_mode_changed_in_model_page()  # type: ignore

    def _get_selected_tts_backend(self) -> str:
        return self.cc_actions._get_selected_tts_backend()  # type: ignore

    def _get_selected_tts_package(self) -> dict:
        return self.cc_actions._get_selected_tts_package()  # type: ignore

    def update_tts_backend_indicator(self, status: dict):
        self.cc_actions.update_tts_backend_indicator(status)  # type: ignore

    def refresh_tts_backend_status(self):
        self.cc_actions.refresh_tts_backend_status()  # type: ignore

    def apply_chat_model_selection(self):
        self.cc_actions.apply_chat_model_selection()  # type: ignore

    def apply_tts_backend_selection(self):
        self.cc_actions.apply_tts_backend_selection()  # type: ignore

    def show_tts_loading_inline(self, text: str = "正在加载语音后端…", percent: int = 0):
        self.cc_actions.show_tts_loading_inline(text, percent)  # type: ignore

    def update_tts_loading_inline(self, text: str, percent: int):
        self.cc_actions.update_tts_loading_inline(text, percent)  # type: ignore

    def hide_tts_loading_inline(self):
        self.cc_actions.hide_tts_loading_inline()  # type: ignore

    def open_role_config_folder(self):
        self.cc_actions.open_role_config_folder()  # type: ignore

    def open_voice_config_folder(self):
        self.cc_actions.open_voice_config_folder()  # type: ignore

    def preview_role_config_text(self):
        self.cc_actions.preview_role_config_text()  # type: ignore

    def run_combo_preview(self):
        self.cc_actions.run_combo_preview()  # type: ignore

    def mock_audio_play(self):
        self.cc_actions.mock_audio_play()  # type: ignore

    def get_selected_style_id_for_save(self) -> str:
        return self.cc_actions.get_selected_style_id_for_save()  # type: ignore

    def get_selected_voice_id_for_save(self) -> str:
        return self.cc_actions.get_selected_voice_id_for_save()  # type: ignore

    def save_combo_preset(self):
        self.cc_actions.save_combo_preset()  # type: ignore

    def load_combo_preset(self):
        self.cc_actions.load_combo_preset()  # type: ignore

    def delete_combo_preset(self):
        self.cc_actions.delete_combo_preset()  # type: ignore

    def save_workspace_draft(self):
        self.cc_actions.save_workspace_draft()  # type: ignore

    def apply_combo_scheme_selection(self):
        self.cc_actions.apply_combo_scheme_selection()  # type: ignore

    def on_ollama_download_model_selected(self):
        self.cc_actions.on_ollama_download_model_selected()

    def update_connection_page_provider_visibility(self):
        self.cc_actions.update_connection_page_provider_visibility()

    def toggle_developer_mode(self):
        self.cc_actions.toggle_developer_mode()

    def refresh_developer_mode_section(self):
        self.cc_actions.refresh_developer_mode_section()

    def test_audio_output_device(self):
        self.cc_actions.test_audio_output_device()

    def test_audio_input_device(self):
        self.cc_actions.test_audio_input_device()

    def stop_audio_input_live_test(self):
        self.cc_actions.stop_audio_input_live_test()

    def refresh_basic_audio_devices(self):
        self.cc_actions.refresh_basic_audio_devices()

    def on_audio_output_device_selected(self):
        self.cc_actions.on_audio_output_device_selected()

    def on_audio_input_device_selected(self):
        self.cc_actions.on_audio_input_device_selected()

    def run_project_integrity_check(self):
        self.cc_actions.run_project_integrity_check()

    def restore_initial_environment(self):
        self.cc_actions.restore_initial_environment()

    def save_chat_display_settings(self):
        self.cc_actions.save_chat_display_settings()

    def scan_project_cleanup(self):
        self.cc_actions.scan_project_cleanup()

    def delete_selected_project_cleanup(self):
        self.cc_actions.delete_selected_project_cleanup()

    def open_selected_cleanup_folder(self):
        self.cc_actions.open_selected_cleanup_folder()

    # =========================================================
    # 页面回调
    # =========================================================
    def on_style_page_changed(self):
        self.refresh_dirty("style")

    def on_info_page_changed(self):
        self.refresh_dirty("info")
        self.refresh_info_page()

    # =========================================================
    # 第三页图标
    # =========================================================
    def _apply_preview_button_icons(self):
        if not hasattr(self, "btn_combo_play_pause") or not hasattr(self, "btn_combo_loop"):
            return

        play_path = ASSET_PATHS.get("player.play", "")
        pause_path = ASSET_PATHS.get("player.pause", "")
        loop_path = ASSET_PATHS.get("player.loop", "")

        self._preview_play_icon = QIcon(play_path) if play_path else QIcon()
        self._preview_pause_icon = QIcon(pause_path) if pause_path else QIcon()
        self._preview_loop_icon = QIcon(loop_path) if loop_path else QIcon()

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
    # 第三页播放回调
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

    def toggle_nav_collapsed(self):
        self.nav_collapsed = not self.nav_collapsed

        if self.nav_collapsed:
            self.nav_frame.setMinimumWidth(UI_SIZE["nav_width_collapsed"])
            self.nav_frame.setMaximumWidth(UI_SIZE["nav_width_collapsed"])

            if self.nav_title_label is not None:
                self.nav_title_label.setVisible(False)

            if self.nav_system_group_title is not None:
                self.nav_system_group_title.setVisible(False)
            if self.nav_voice_group_title is not None:
                self.nav_voice_group_title.setVisible(False)

            if self.nav_system_group_frame is not None:
                self.nav_system_group_frame.setVisible(False)
            if self.nav_voice_group_frame is not None:
                self.nav_voice_group_frame.setVisible(False)

            if self.btn_nav_system_group is not None:
                self.btn_nav_system_group.setVisible(True)
            if self.btn_nav_voice_group is not None:
                self.btn_nav_voice_group.setVisible(True)

        else:
            self.nav_frame.setMinimumWidth(UI_SIZE["nav_width_expanded"])
            self.nav_frame.setMaximumWidth(UI_SIZE["nav_width_expanded"])

            if self.nav_title_label is not None:
                self.nav_title_label.setVisible(True)

            if self.nav_system_group_title is not None:
                self.nav_system_group_title.setVisible(True)
            if self.nav_voice_group_title is not None:
                self.nav_voice_group_title.setVisible(True)

            if self.nav_system_group_frame is not None:
                self.nav_system_group_frame.setVisible(True)
            if self.nav_voice_group_frame is not None:
                self.nav_voice_group_frame.setVisible(True)

            if self.btn_nav_system_group is not None:
                self.btn_nav_system_group.setVisible(False)
            if self.btn_nav_voice_group is not None:
                self.btn_nav_voice_group.setVisible(False)

        self.update_nav_toggle_icon()
    # =========================================================
    # 导航辅助
    # =========================================================
    def _set_nav_checked_manual(self, page_index: int):
        mapping = {
            0: getattr(self, "btn_model", None),
            1: getattr(self, "btn_style", None),
            2: getattr(self, "btn_info", None),
            3: getattr(self, "btn_connection", None),
            4: getattr(self, "btn_desktop", None),
            5: getattr(self, "btn_basic_settings", None),
        }
        for idx, btn in mapping.items():
            if btn is not None:
                btn.setChecked(idx == page_index)

    def _page_uses_dirty_guard(self, page_key: str) -> bool:
        return page_key in ("style", "info")

    def switch_to_connection_page(self):
        current_index = self.stack.currentIndex()
        current_key = self.page_key_from_index(current_index)

        if self._page_uses_dirty_guard(current_key) and self.page_dirty.get(current_key, False):
            decision = self.ask_apply_changes(current_key)
            if decision == "cancel":
                return
            if decision == "apply":
                self.apply_page(current_key)
            elif decision == "discard":
                self.discard_page_changes(current_key)

        self.stack.setCurrentIndex(3)
        self._set_nav_checked_manual(3)

    def switch_to_desktop_page(self):
        current_index = self.stack.currentIndex()
        current_key = self.page_key_from_index(current_index)

        if self._page_uses_dirty_guard(current_key) and self.page_dirty.get(current_key, False):
            decision = self.ask_apply_changes(current_key)
            if decision == "cancel":
                return
            if decision == "apply":
                self.apply_page(current_key)
            elif decision == "discard":
                self.discard_page_changes(current_key)

        self.stack.setCurrentIndex(4)
        self._set_nav_checked_manual(4)
        self.loader.load_desktop_page_on_demand()

    def try_switch_page(self, page_index: int, target_key: str):
        current_index = self.stack.currentIndex()
        current_key = self.page_key_from_index(current_index)

        if self._page_uses_dirty_guard(current_key) and self.page_dirty.get(current_key, False):
            decision = self.ask_apply_changes(current_key)
            if decision == "cancel":
                self._set_nav_checked_manual(current_index)
                return
            if decision == "apply":
                self.apply_page(current_key)
            elif decision == "discard":
                self.discard_page_changes(current_key)

        self.stack.setCurrentIndex(page_index)
        self._set_nav_checked_manual(page_index)

    # =========================================================
    # 连接页 / 桌面页
    # =========================================================
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

    def run_local_init(self):
        self.desktop_controller.run_initialization()

    def refresh_init_preview(self):
        self.loader.load_desktop_page_on_demand(force=True)

    def reload_desktop_page(self):
        self.loader.load_desktop_page_on_demand(force=True)

    def on_desktop_mode_changed(self):
        self.desktop_controller.reload_page()

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
            self.stop_audio_input_live_test()
        except Exception:
            pass

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
