from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from services.desktop.desktop_whitelist_service import DesktopWhitelistService
from services.desktop.qin_runtime_service import QinRuntimeService

if TYPE_CHECKING:
    from PySide6.QtCore import QThread
    from ui.control_center.desktop.software_scan_worker import SoftwareScanWorker
    from services.desktop.tianting.vm_bridge.vm_connect_worker import VmConnectWorker


class DesktopPageRuntime:
    def __init__(self, window) -> None:
        self.window = window
        self.project_root = Path(window.machine_profile_service.project_root)
        self.service = DesktopWhitelistService(self.project_root)
        self.qin_runtime = QinRuntimeService(self.project_root)

        self.apps_editable = False
        self.file_governance_editable = False
        self.readonly_selected_root_id = "project_root"
        self.readonly_result: dict | None = None
        self.sandbox_result: dict | None = None

        # ===== 测试模式 / VM 连接状态 =====
        desktop_runtime_state = self.service.mode_store.get_runtime_state()
        self.test_mode_enabled = str(desktop_runtime_state.get("desktop_mode", "") or "") == "test"
        self.test_backend = str(desktop_runtime_state.get("test_backend", "sandbox") or "sandbox")

        self.vm_connection_state = "unchecked"
        self.vm_test_available = False
        self.vm_connection_started_at = 0.0

        self.vm_health_result: dict | None = None
        self.vm_apps_result: dict | None = None
        self.vm_file_result: dict | None = None

        # ===== VM 文件区 roots/list 状态 =====
        self.vm_file_roots_result: dict | None = None
        self.vm_selected_file_root_id: str = "vm_drive_c"
        self.vm_current_relative_path: str = ""

        self.vm_last_error: str = ""
        self.vm_status_text = "虚拟机测试代理：未检查"

        # ===== VM 文件区上层测试开关 =====
        self.vm_file_actions_enabled = False
        self.vm_allow_expand = True
        self.vm_allow_scan = True
        self.vm_allow_index = True

        # ===== VM 连接线程 =====
        self.vm_connect_thread: QThread | None = None
        self.vm_connect_worker: VmConnectWorker | None = None

        # ===== VM 文件扫描线程 =====
        self.vm_file_scan_in_progress = False
        self.vm_file_scan_message = ""
        self.vm_file_scan_total_count = 0
        self.vm_file_scan_visible_count = 0
        self.vm_file_scan_hidden_count = 0
        self.vm_file_scan_thread: QThread | None = None
        self.vm_file_scan_worker: object | None = None
        self.vm_file_scan_id = 0
        self.vm_file_scan_stage = ""
        self.vm_file_scan_error = ""
        self.vm_file_scan_progress_percent = 0
        

        self.disk_filter_key = "all"
        self.disk_font_size = "medium"
        self.object_view_mode = "roots"
        self.object_filter_key = "all"
        self.object_font_size = "medium"
        self.file_view_mode = self.object_view_mode
        self.file_filter_key = self.object_filter_key
        self.file_font_size = self.object_font_size
        self.software_font_size = "medium"
        # 这两个字段属于页面运行态，不写入 user_prefs/local 真源。
        self.selected_disk = ""
        self.current_directory = ""
        self.file_navigation_stack: list[str] = []
        # 文件对象权限覆盖仅在当前会话中生效
        self.file_permission_overrides: dict[str, str] = {}
        self.file_table_vertical_scroll_value = 0
        self.file_table_horizontal_scroll_value = 0
        self.host_file_current_root: str = ""
        self.host_file_current_path: str = ""
        self.host_file_cache_state: dict = {}
        self.host_file_scan_status: str = "idle"
        self.host_file_scan_progress: int = 0
        self.host_file_scan_message: str = ""
        self.host_file_last_error: str = ""
        self.host_file_trigger_source: str = ""
        self.host_file_request_id: str = ""
        self.host_file_scan_thread: QThread | None = None
        self.host_file_scan_worker: object | None = None
        self.host_file_table_scroll_value: int = 0
        self.host_file_table_horizontal_scroll_value: int = 0
        self.software_table_scroll_value = 0
        self.software_table_horizontal_scroll_value = 0
        self.desktop_page_scroll_value = 0
        self.cleared_app_ids: set[str] = set()
        self.last_software_app_id = ""
        self.last_software_action = ""
        self.software_scan_in_progress = False
        self.software_scan_thread: QThread | None = None
        self.software_scan_worker: object | None = None
        self.host_file_scan_id = 0
        # 当前软件扫描模式：quick / full
        self.software_scan_profile = "quick"
        self.software_scan_stage = ""
        self.software_scan_message = ""
        self.software_scan_progress_percent = 0
        self.software_scan_progress_stats: dict[str, object] = {}
        self.software_scan_log_lines: list[str] = []
        self.software_table_loaded = False
        self.software_auto_memory_load_requested = False
        self.software_last_state: dict[str, object] | None = None

        # 软件区 UI 缓存
        self.software_cache_loaded = False
        self.software_cache_source = "empty"
        self.software_cache_state: dict[str, object] | None = None

        self.file_deferred_load_requested = False
        self.desktop_load_sequence_id = 0
        self.software_table_rendering = False
        # 软件表渲染保护：避免渲染过程中重复重建表格
        self.software_refresh_pending = False
        self.software_render_generation = 0
        # Layout debug overrides are session-only and are not written to local prefs.
        self.layout_overrides: dict[str, int] = {}

        self.latest_desktop_action_result: dict | None = None
        self.latest_host_action_result: dict | None = None
        self.latest_vm_action_result: dict | None = None