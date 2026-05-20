from __future__ import annotations

import json
import re
import shiboken6
from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtGui import QIcon, QMovie
from PySide6.QtWidgets import QCheckBox, QHBoxLayout, QLabel, QPushButton, QLayout, QTableWidgetItem, QWidget
from pathlib import Path
from ui.control_center.config import ASSET_PATHS, software_scan_image_button_qss
from services.desktop.qin.liyi.message_presenter import MessagePresenter
from ui.control_center.desktop.debug_tools import refresh_size_badges
from ui.control_center.desktop.software_icon_presenter import SoftwareIconPresenter
from ui.control_center.desktop.software_panel_loader import SoftwarePanelLoader
from ui.control_center.desktop.software_scan_status_presenter import SoftwareScanStatusPresenter


class DesktopPageLoader:
    def __init__(self, window) -> None:
        self.w = window
        self._scan_button_movies = {}
        self.software_icon_presenter = SoftwareIconPresenter(self)
        self.software_panel_loader = SoftwarePanelLoader(self)
        self.software_scan_status_presenter = SoftwareScanStatusPresenter()

    def load_page(self) -> None:
        controller = getattr(self.w, "desktop_controller", None)
        if controller is None:
            return

        state = controller.service.get_page_state(
            filter_key=controller.current_filter_key(),
            apps_editable=controller.runtime.apps_editable,
        )
        readonly_state = controller.get_readonly_panel_state()
        file_state = controller.get_file_governance_state()
        software_state = None
        sandbox_state = controller.get_sandbox_panel_state()

        display_mode = self._display_mode_for_user(state["mode"])
        developer_enabled = self._developer_mode_enabled()
        mode_text = self._mode_label(display_mode)
        self._set_text("desktop_status_mode_value", mode_text)
        self._set_text("desktop_status_local_value", "已生成" if state["local_ready"] else "未生成")
        self._set_text("desktop_status_confirmed_value", "已确认" if state["initialized"] else "未确认")
        self._set_text("desktop_status_root_count_value", str(state["root_count"]))
        self._set_text("desktop_status_app_count_value", str(state["confirmed_app_count"]))
        self._set_text("desktop_mode_summary_label", self._mode_summary_for_user(state))
        self._set_text("desktop_readonly_summary_label", readonly_state["summary"])
        self._set_text("desktop_runtime_target_path_label", readonly_state["selected_root_path"])
        scan_message = str(getattr(controller.runtime, "vm_file_scan_message", "") or "").strip()
        if not scan_message:
            scan_message = str(getattr(controller.runtime, "host_file_scan_message", "") or "").strip()

        if (
            state["mode"] == "test"
            and not scan_message
            and str(getattr(controller.runtime, "test_backend", "sandbox") or "").strip().lower() == "vm"
        ):
            root_count = len(file_state.get("disk_rows", []))
            total_count = int(getattr(controller.runtime, "vm_file_scan_total_count", 0) or 0)
            visible_count = int(getattr(controller.runtime, "vm_file_scan_visible_count", 0) or 0)
            hidden_count = int(getattr(controller.runtime, "vm_file_scan_hidden_count", 0) or 0)

            if root_count or total_count or visible_count or hidden_count:
                scan_message = (
                    f"磁盘根目录 {root_count} 个；当前目录回传 {total_count} 个，"
                    f"显示 {visible_count} 个，屏蔽 {hidden_count} 个"
                )

        if scan_message:
            self._set_text("desktop_file_path_label", f"当前目标：{file_state['current_path']}    {scan_message}")
        else:
            self._set_text("desktop_file_path_label", f"当前目标：{file_state['current_path']}")
        self._set_text("desktop_sandbox_summary_label", sandbox_state["summary"])
        self._set_visible("desktop_file_card", display_mode in {"restricted", "trusted", "test"})
        self._set_visible("desktop_readonly_card", developer_enabled and state["mode"] == "test")
        self._set_visible("desktop_sandbox_card", developer_enabled and bool(sandbox_state["visible"]))

        self._set_mode_buttons(display_mode)
        self._set_test_backend_buttons(state["mode"])
        self._set_shaofu_button_state()
        self._set_file_toolbar_state(file_state, state["mode"])
        self._apply_file_visual_state(file_state)
        self._set_readonly_state(readonly_state)
        self._set_sandbox_state(sandbox_state)
        self._populate_disk_table(file_state["disk_rows"], selected_disk=file_state["selected_disk"])
        self._populate_file_table(
            file_state["rows"],
            read_only=file_state["read_only"],
            file_actions_enabled=bool(file_state.get("file_actions_enabled", False)),
        )
        self._set_visible("desktop_file_table", developer_enabled)
        self._set_visible("desktop_file_path_label", developer_enabled)
        if bool(getattr(controller.runtime, "software_table_loaded", False)) and self._software_table_rendered():
            software_summary = self._software_summary_from_page_state(state)
            self.software_panel_loader.refresh_panel_chrome(software_summary, self._software_page_state_for_runtime(state))
        else:
            software_summary = self._software_summary_from_page_state(state)
            self.load_software_panel(page_state=state, software_state=software_summary, force_full=False)
            
        self.apply_responsive_layout()
        self._apply_table_font("desktop_disk_table", controller.runtime.disk_font_size)
        self._apply_table_font("desktop_file_table", controller.runtime.object_font_size)
        self._apply_table_font("desktop_apps_table", controller.runtime.software_font_size)
        self._apply_result_font("desktop_readonly_result_display", controller.runtime.object_font_size)
        self._apply_result_font("desktop_sandbox_result_display", controller.runtime.software_font_size)
        self._apply_desktop_label_fonts()
        self._apply_desktop_static_button_icons()
        refresh_size_badges(self.w)
        self._restore_desktop_table_scrolls()
        self._restore_desktop_page_scroll()

    def load_page_light(self) -> None:
        controller = getattr(self.w, "desktop_controller", None)
        if controller is None:
            return

        if hasattr(controller.service, "get_page_shell_state"):
            state = controller.service.get_page_shell_state(
                apps_editable=controller.runtime.apps_editable,
            )
        else:
            state = controller.service.get_page_state(
                filter_key=controller.current_filter_key(),
                apps_editable=controller.runtime.apps_editable,
            )

        display_mode = self._display_mode_for_user(state["mode"])
        developer_enabled = self._developer_mode_enabled()
        self._set_text("desktop_status_mode_value", self._mode_label(display_mode))
        self._set_text("desktop_status_local_value", "已生成" if state["local_ready"] else "未生成")
        self._set_text("desktop_status_confirmed_value", "已确认" if state["initialized"] else "未确认")
        self._set_text("desktop_status_root_count_value", str(state["root_count"]))
        self._set_text("desktop_status_app_count_value", str(state["confirmed_app_count"]))
        self._set_text("desktop_mode_summary_label", self._mode_summary_for_user(state))
        self._set_text("desktop_readonly_summary_label", "基础只读验证详情尚未加载。")
        self._set_text("desktop_runtime_target_path_label", "尚未加载")
        self._set_text("desktop_file_path_label", "当前目标：文件治理列表尚未加载。")
        self._set_text("desktop_sandbox_summary_label", "测试结果详情尚未加载。")

        governed_visible = display_mode in {"restricted", "trusted", "test"}
        sandbox_state = controller.get_sandbox_panel_state()
        self._set_visible("desktop_file_card", governed_visible)
        self._set_visible("desktop_readonly_card", developer_enabled and state["mode"] == "test")
        self._set_visible("desktop_sandbox_card", developer_enabled and bool(sandbox_state.get("visible", False)))
        self._set_mode_buttons(display_mode)
        self._set_test_backend_buttons(state["mode"])
        self._set_shaofu_button_state()
        runtime = getattr(controller, "runtime", None)
        runtime_editable = bool(getattr(runtime, "file_governance_editable", False)) if runtime is not None else False
        self._apply_file_visual_state({"read_only": not runtime_editable})

        software_summary = self._software_summary_from_page_state(state)
        self.load_software_panel(page_state=state, software_state=software_summary, force_full=False)

        # 首屏先显示页面壳，100ms 后读取软件视图缓存。
        # 读取缓存不是扫描，也不是重新合并软件数据。
        QTimer.singleShot(100, controller.load_software_view_cache)
        self.apply_responsive_layout()
        self._apply_desktop_label_fonts()
        self._apply_desktop_static_button_icons()
        refresh_size_badges(self.w)

        if runtime is not None:
            runtime.desktop_load_sequence_id = int(getattr(runtime, "desktop_load_sequence_id", 0) or 0) + 1
            runtime.file_deferred_load_requested = True
            sequence_id = int(runtime.desktop_load_sequence_id)
        else:
            sequence_id = 0
        QTimer.singleShot(100, lambda sequence_id=sequence_id: self.load_file_governance_deferred(sequence_id))

    def load_file_governance_deferred(self, sequence_id: int | None = None) -> None:
        """
        文件治理区延迟加载。
        避免首次点击桌面连接页时同步读取磁盘/文件列表造成卡顿。
        """
        controller = getattr(self.w, "desktop_controller", None)
        if controller is None:
            return
        runtime = getattr(controller, "runtime", None)
        if runtime is not None and sequence_id is not None:
            if int(getattr(runtime, "desktop_load_sequence_id", 0) or 0) != int(sequence_id):
                return

        try:
            state = controller.service.get_page_shell_state(
                apps_editable=controller.runtime.apps_editable,
            ) if hasattr(controller.service, "get_page_shell_state") else controller.service.get_page_state(
                filter_key=controller.current_filter_key(),
                apps_editable=controller.runtime.apps_editable,
            )
        except Exception:
            if runtime is not None:
                runtime.file_deferred_load_requested = False
            return

        mode = str(state.get("mode", "disabled") or "disabled").strip().lower()
        developer_enabled = self._developer_mode_enabled()
        if mode not in {"restricted", "trusted", "test"}:
            if runtime is not None:
                runtime.file_deferred_load_requested = False
            return

        try:
            file_state = controller.get_file_governance_state()
        except Exception as exc:
            self._set_text("desktop_file_path_label", f"当前目标：文件治理加载失败：{exc}")
            if runtime is not None:
                runtime.file_deferred_load_requested = False
            return

        scan_message = str(getattr(controller.runtime, "vm_file_scan_message", "") or "").strip()
        if not scan_message:
            scan_message = str(getattr(controller.runtime, "host_file_scan_message", "") or "").strip()
        if scan_message:
            self._set_text("desktop_file_path_label", f"当前目标：{file_state['current_path']}    {scan_message}")
        else:
            self._set_text("desktop_file_path_label", f"当前目标：{file_state['current_path']}")

        self._set_file_toolbar_state(file_state, mode)
        self._apply_file_visual_state(file_state)

        self._populate_disk_table(file_state["disk_rows"], selected_disk=file_state["selected_disk"])
        self._populate_file_table(
            file_state["rows"],
            read_only=file_state["read_only"],
            file_actions_enabled=bool(file_state.get("file_actions_enabled", False)),
        )

        self._set_visible("desktop_file_table", developer_enabled)
        self._set_visible("desktop_file_path_label", developer_enabled)
        self._apply_table_font("desktop_disk_table", controller.runtime.disk_font_size)
        self._apply_table_font("desktop_file_table", controller.runtime.object_font_size)
        self._apply_desktop_static_button_icons()

        self._restore_table_scroll(
            "desktop_file_table",
            vertical_attr="file_table_vertical_scroll_value",
            horizontal_attr="file_table_horizontal_scroll_value",
        )
        if runtime is not None:
            runtime.file_deferred_load_requested = False

    def refresh_mode_controls(self) -> None:
        controller = getattr(self.w, "desktop_controller", None)
        if controller is None:
            return

        runtime_state = {}
        try:
            runtime_state = controller.service.mode_store.get_runtime_state()
        except Exception:
            runtime_state = {}

        mode = str(
            runtime_state.get("desktop_mode")
            or runtime_state.get("current_mode")
            or runtime_state.get("governance_mode")
            or "disabled"
        ).strip().lower()
        if mode not in {"disabled", "restricted", "trusted", "test"}:
            mode = "disabled"
        display_mode = self._display_mode_for_user(mode)
        developer_enabled = self._developer_mode_enabled()

        summary = {
            "disabled": "桌面连接关闭，不执行文件或软件动作。",
            "restricted": "只允许部分文件查询与只读浏览，不执行软件动作和文件写入动作。",
            "trusted": "Host 真实执行已开启。文件和软件动作按权限、确认、审议和记录执行。",
            "test": "根据选择进入沙盒回执或虚拟机测试。沙盒不真实执行，VM 执行虚拟机动作。",
        }.get(mode, "-")

        self._set_text("desktop_status_mode_value", self._mode_label(display_mode))
        self._set_text("desktop_mode_summary_label", summary)
        self._set_mode_buttons(display_mode)
        self._set_test_backend_buttons(mode)
        self._set_shaofu_button_state()
        

        governed_visible = display_mode in {"restricted", "trusted", "test"}
        self._set_visible("desktop_file_card", governed_visible)
        self._set_visible("desktop_readonly_card", developer_enabled and mode == "test")
        self._set_visible("desktop_software_card", display_mode in {"trusted", "test"})
        sandbox_state = self.w.desktop_controller.get_sandbox_panel_state()
        self._set_visible("desktop_sandbox_card", developer_enabled and bool(sandbox_state.get("visible", False)))

    def load_software_panel(
        self,
        *,
        page_state: dict | None = None,
        software_state: dict | None = None,
        force_full: bool | None = None,
    ) -> None:
        controller = getattr(self.w, "desktop_controller", None)
        if controller is None:
            return
        if page_state is not None:
            state = page_state
        elif hasattr(controller.service, "get_page_shell_state"):
            state = controller.service.get_page_shell_state(
                apps_editable=controller.runtime.apps_editable,
            )
        else:
            state = controller.service.get_page_state(
                filter_key=controller.current_filter_key(),
                apps_editable=controller.runtime.apps_editable,
            )
        state = self._software_page_state_for_runtime(state)
        should_load_full = bool(getattr(controller.runtime, "software_table_loaded", False))
        if force_full is not None:
            should_load_full = bool(force_full)
        if should_load_full:
            software = software_state

            if software is None and isinstance(getattr(controller.runtime, "software_last_state", None), dict):
                software = controller.runtime.software_last_state

            if software is None and hasattr(controller, "software_view_cache"):
                software = controller.software_view_cache.read()

            if not isinstance(software, dict):
                software = self._software_summary_from_page_state(state)
                self.software_panel_loader.load_panel_summary(software, state)
                return

            rows = software.get("rows", [])
            if not isinstance(rows, list) or not rows:
                controller.runtime.software_last_state = dict(software)
                self.software_panel_loader.load_panel_summary(software, state)
                return

            controller.runtime.software_last_state = dict(software)
            self.software_panel_loader.load_panel(software, state)
        else:
            software = software_state or self._software_summary_from_page_state(state)
            self.software_panel_loader.load_panel_summary(software, state)
        self.apply_responsive_layout()
        self._apply_table_font("desktop_apps_table", controller.runtime.software_font_size)
        self._apply_desktop_label_fonts()
        self._restore_table_scroll(
            "desktop_apps_table",
            vertical_attr="software_table_scroll_value",
            horizontal_attr="software_table_horizontal_scroll_value",
        )
        table = getattr(self.w, "desktop_apps_table", None)
        if table is not None:
            table.setColumnHidden(3, not self._developer_mode_enabled())

    def _asset_icon(self, relative_path: str) -> QIcon:
        try:
            project_root = Path(getattr(self.w, "project_root", Path.cwd()))
        except Exception:
            project_root = Path.cwd()

        path = project_root / "ui" / "assets" / relative_path
        return QIcon(str(path))
    
    def refresh_software_editable_state(self, *, page_state: dict | None = None) -> None:
        """
        只刷新软件区可交互状态。

        用于：
        - 软件区 只读 / 可调整 切换

        禁止：
        - 不重新渲染 rows
        - 不重新读取缓存
        - 不重新扫描
        - 不重新 merge
        """
        controller = getattr(self.w, "desktop_controller", None)
        if controller is None:
            return

        if page_state is not None:
            state = page_state
        elif hasattr(controller.service, "get_page_shell_state"):
            state = controller.service.get_page_shell_state(
                apps_editable=controller.runtime.apps_editable,
            )
        else:
            state = controller.service.get_page_state(
                filter_key=controller.current_filter_key(),
                apps_editable=controller.runtime.apps_editable,
            )

        state = self._software_page_state_for_runtime(state)

        software_state = (
            controller.runtime.software_last_state
            if isinstance(getattr(controller.runtime, "software_last_state", None), dict)
            else None
        )

        if isinstance(software_state, dict):
            software_state["read_only"] = bool(state.get("apps_read_only", True))

        # 只刷新软件区顶部按钮/文字，不碰表格 rows
        self._set_visible("desktop_software_card", state["mode"] in {"trusted", "test"})
        self._set_software_toolbar_state(state)
        self._apply_software_visual_state(state)
        self._set_software_scan_status()
        self._apply_software_scan_label_fonts()
        self._apply_software_scan_button_visual()

        # 只刷新当前表格中已有按钮的 enabled 状态
        self.software_panel_loader.refresh_apps_table_interactive_state(
            software_state=software_state,
            page_state=state,
        )
        table = getattr(self.w, "desktop_apps_table", None)
        if table is not None:
            table.setColumnHidden(3, not self._developer_mode_enabled())
            
    def refresh_file_scan_status(self) -> None:
        controller = getattr(self.w, "desktop_controller", None)
        if controller is None:
            return

        runtime = getattr(controller, "runtime", None)
        if runtime is None:
            return

        current_path = (
            str(getattr(runtime, "host_file_current_path", "") or "")
            or str(getattr(runtime, "current_directory", "") or "")
            or "-"
        )

        scan_message = str(getattr(runtime, "host_file_scan_message", "") or "").strip()
        if not scan_message:
            scan_message = str(getattr(runtime, "vm_file_scan_message", "") or "").strip()

        if scan_message:
            self._set_text("desktop_file_path_label", f"当前目标：{current_path}    {scan_message}")
        else:
            self._set_text("desktop_file_path_label", f"当前目标：{current_path}")

        # 只刷新扫描按钮图标/可点击状态，不重建 disk table / file table。
        try:
            file_state = controller.get_file_governance_state()
            self._set_file_toolbar_state(file_state, controller._current_mode())
            self._apply_desktop_static_button_icons()
        except Exception:
            self._apply_desktop_static_button_icons()
    def _developer_mode_enabled(self) -> bool:
        try:
            return bool(getattr(self.w, "developer_mode_enabled_at_startup", False))
        except Exception:
            return False

    def _display_mode_for_user(self, mode: str) -> str:
        normalized = str(mode or "").strip().lower()
        if normalized == "test" and not self._developer_mode_enabled():
            return "trusted"
        return normalized if normalized in {"disabled", "restricted", "trusted", "test"} else "disabled"

    def _mode_summary_for_user(self, state: dict) -> str:
        mode = str((state or {}).get("mode", "") or "").strip().lower()
        summary = {
            "disabled": "桌面连接关闭，不执行文件或软件动作。",
            "restricted": "只允许部分文件查询与只读浏览，不执行软件动作和文件写入动作。",
            "trusted": "Host 真实执行已开启。文件和软件动作按权限、确认、审议和记录执行。",
            "test": "根据选择进入沙盒回执或虚拟机测试。沙盒不真实执行，VM 执行虚拟机动作。",
        }
        return summary.get(mode, str((state or {}).get("mode_summary", "") or ""))

    def _software_table_rendered(self) -> bool:
        controller = getattr(self.w, "desktop_controller", None)
        runtime = getattr(controller, "runtime", None)
        last_state = getattr(runtime, "software_last_state", None)
        if not isinstance(last_state, dict) or not last_state.get("rows"):
            return False
        table = getattr(self.w, "desktop_apps_table", None)
        if table is None:
            return False
        try:
            return table.rowCount() > 0
        except Exception:
            return False

    def _software_page_state_for_runtime(self, state: dict) -> dict:
        controller = getattr(self.w, "desktop_controller", None)
        runtime = getattr(controller, "runtime", None)
        if state.get("mode") != "test" or str(getattr(runtime, "test_backend", "sandbox") or "sandbox").strip().lower() != "vm":
            return state
        vm_connected = (
            str(getattr(runtime, "vm_connection_state", "unchecked") or "unchecked").strip().lower() == "connected"
            and bool(getattr(runtime, "vm_test_available", False))
        )
        if vm_connected:
            return state
        vm_state = dict(state or {})
        vm_state["apps_read_only"] = True
        vm_state["can_toggle_apps_editable"] = False
        vm_state["can_scan"] = False
        return vm_state

    def _software_summary_from_page_state(self, state: dict) -> dict:
        controller = getattr(self.w, "desktop_controller", None)
        runtime = getattr(controller, "runtime", None)
        rows = state.get("apps", []) if isinstance(state.get("apps"), list) else []
        hidden_count = 0
        try:
            hidden_count = len(controller.service.software_hidden_book.read_ids()) if controller is not None else 0
        except Exception:
            hidden_count = 0
        scanning = bool(getattr(runtime, "software_scan_in_progress", False))
        source = "scanning" if scanning else ("memory" if rows or int(state.get("confirmed_app_count", 0) or 0) else "empty")
        return {
            "discovered_count": len(rows),
            "trusted_count": int(state.get("confirmed_app_count", 0) or 0),
            "confirmed_count": int(state.get("confirmed_app_count", 0) or 0),
            "hidden_count": hidden_count,
            "read_only": bool(state.get("apps_read_only", True)),
            "rows": [],
            "source": source,
        }

    def refresh_software_scan_status(self, *, page_state: dict | None = None) -> None:
        controller = getattr(self.w, "desktop_controller", None)
        if controller is None:
            return
        if page_state is not None:
            state = page_state
        elif hasattr(controller.service, "get_page_shell_state"):
            state = controller.service.get_page_shell_state(
                apps_editable=controller.runtime.apps_editable,
            )
        else:
            state = controller.service.get_page_state(
                filter_key=controller.current_filter_key(),
                apps_editable=controller.runtime.apps_editable,
            )
        self._set_visible("desktop_software_card", state["mode"] in {"trusted", "test"})
        self._set_software_scan_button_state(state)
        self._set_software_scan_status()
        self._apply_software_scan_label_fonts()
        self._apply_software_scan_button_visual()

    def _mode_label(self, mode: str) -> str:
        return {
            "disabled": "不启用",
            "restricted": "限制模式",
            "trusted": "信任模式",
            "test": "测试模式",
        }.get(mode, mode or "-")

    def _set_text(self, attr_name: str, text: str) -> None:
        label = getattr(self.w, attr_name, None)
        if label is not None:
            label.setText(text)

    def _set_visible(self, attr_name: str, visible: bool) -> None:
        widget = getattr(self.w, attr_name, None)
        if widget is not None:
            widget.setVisible(bool(visible))

    def _asset_path(self, asset_key: str) -> str:
        return str(ASSET_PATHS.get(asset_key, ""))
    
    def _stop_button_movie(self, button) -> None:
        if button is None:
            return

        movie = getattr(button, "_desktop_icon_movie", None)
        if movie is not None:
            try:
                movie.stop()
                movie.deleteLater()
            except Exception:
                pass

        button._desktop_icon_movie = None
        button._desktop_icon_movie_path = ""

    def _set_button_icon(self, button, asset_key: str, size_key: str) -> None:
        self._stop_button_movie(button)

        path = self._asset_path(asset_key)
        if not path:
            return

        size = self._size_int(size_key)
        button.setIcon(QIcon(path))
        button.setIconSize(QSize(size, size))

    def _set_button_movie_icon(self, button, asset_key: str, size_key: str) -> None:
        path = self._asset_path(asset_key)
        if not path:
            return

        icon_size = self._size_int(size_key)
        movie = getattr(button, "_desktop_icon_movie", None)

        if movie is None or getattr(button, "_desktop_icon_movie_path", "") != path:
            movie = QMovie(path)
            movie.setScaledSize(QSize(icon_size, icon_size))
            def _safe_update_button_icon(_frame: int, b=button, m=movie) -> None:
                if b is None or not shiboken6.isValid(b):
                    if m is not None:
                        m.stop()
                    return

                pixmap = m.currentPixmap()
                if not pixmap.isNull():
                    b.setIcon(QIcon(pixmap))

            movie.frameChanged.connect(_safe_update_button_icon)
            button._desktop_icon_movie = movie
            button._desktop_icon_movie_path = path

        if movie.state() != QMovie.MovieState.Running:
            movie.start()

        button.setIconSize(QSize(icon_size, icon_size))


    def _make_icon_only_button(
        self,
        button,
        asset_key: str,
        icon_size_key: str,
        tooltip: str = "",
        *,
        button_size_key: str = "desktop_icon_button_size",
        animated: bool = False,
    ) -> None:
        if button is None:
            return

        button.setText("")
        if tooltip:
            button.setToolTip(tooltip)

        button_size = self._size_int(button_size_key)
        button.setFixedSize(button_size, button_size)

        if animated:
            self._set_button_movie_icon(button, asset_key, icon_size_key)
        else:
            self._set_button_icon(button, asset_key, icon_size_key)

    def _set_button_gif_first_frame(
        self,
        button,
        asset_key: str,
        icon_size_key: str,
        tooltip: str,
        *,
        button_size_key: str = "software_scan_button_size",
    ) -> None:
        if button is None:
            return

        movie = getattr(button, "_desktop_icon_movie", None)
        if movie is not None:
            movie.stop()
        button._desktop_icon_movie = None
        button._desktop_icon_movie_path = ""

        button.setText("")
        if tooltip:
            button.setToolTip(tooltip)

        button_size = self._size_int(button_size_key)
        button.setFixedSize(button_size, button_size)

        icon_size = self._size_int(icon_size_key)
        path = self._asset_path(asset_key)
        if path:
            frame_movie = QMovie(path)
            frame_movie.setScaledSize(QSize(icon_size, icon_size))
            if frame_movie.jumpToFrame(0):
                pixmap = frame_movie.currentPixmap()
                if not pixmap.isNull():
                    button.setIcon(QIcon(pixmap))
                    button.setIconSize(QSize(icon_size, icon_size))
                    return

        self._set_button_icon(button, asset_key, icon_size_key)

    def _apply_desktop_static_button_icons(self) -> None:
        controller = getattr(self.w, "desktop_controller", None)
        runtime = getattr(controller, "runtime", None)
        host_scanning = (
            str(getattr(runtime, "host_file_scan_status", "") or "").strip().lower()
            == "scanning"
        )
        vm_scanning = bool(getattr(runtime, "vm_file_scan_in_progress", False))
        file_scanning = host_scanning or vm_scanning

        self._make_icon_only_button(
            getattr(self.w, "btn_desktop_rescan_disk", None),
            "desktop.loading_gif" if file_scanning else "desktop.scan_icon",
            "desktop_toolbar_icon_size",
            "扫描中" if file_scanning else "扫描当前磁盘",
            animated=file_scanning,
        )

        self._make_icon_only_button(
            getattr(self.w, "btn_desktop_parent_dir", None),
            "desktop.back_icon",
            "desktop_toolbar_icon_size",
            "返回上级",
        )

        self._make_icon_only_button(
            getattr(self.w, "btn_desktop_roots_view", None),
            "desktop.root_icon",
            "desktop_toolbar_icon_size",
            "返回根目录",
        )

        self._make_icon_only_button(
            getattr(self.w, "btn_desktop_clear_apps", None),
            "desktop.clear_gif",
            "software_clear_button_icon_size",
            "清理连接",
            animated=True,
        )

    def _apply_software_scan_button_visual(self) -> None:
        """
        软件治理区扫描按钮显示规则：

        空闲：
        - 快速扫描按钮播放 desktop.quick_scan_gif
        - 完整扫描按钮播放 desktop.full_scan_gif

        扫描中：
        - 当前扫描按钮切换为 desktop.loading_gif
        - 另一个扫描按钮保留自己的扫描 gif
        - 按钮样式来自 config.py，不在这里写死
        """
        runtime = getattr(getattr(self.w, "desktop_controller", None), "runtime", None)
        is_scanning = bool(getattr(runtime, "software_scan_in_progress", False)) if runtime is not None else False

        profile = (
            str(getattr(runtime, "software_scan_profile", "quick") or "quick").strip().lower()
            if runtime is not None
            else "quick"
        )
        if profile not in {"quick", "full"}:
            profile = "quick"

        quick_button = getattr(self.w, "btn_desktop_rescan", None)
        full_button = getattr(self.w, "btn_desktop_full_scan", None)

        if quick_button is not None:
            asset_key = "desktop.loading_gif" if is_scanning and profile == "quick" else "desktop.quick_scan_gif"
            tooltip = "快速扫描中" if is_scanning and profile == "quick" else "快速扫描软件"
            self._set_scan_image_button(
                quick_button,
                asset_key=asset_key,
                icon_size_key="software_quick_scan_icon_size",
                tooltip=tooltip,
            )

        if full_button is not None:
            asset_key = "desktop.loading_gif" if is_scanning and profile == "full" else "desktop.full_scan_gif"
            tooltip = "完整扫描中" if is_scanning and profile == "full" else "完整扫描软件"
            self._set_scan_image_button(
                full_button,
                asset_key=asset_key,
                icon_size_key="software_full_scan_icon_size",
                tooltip=tooltip,
            )

    def _set_scan_image_button(
        self,
        button: QPushButton,
        *,
        asset_key: str,
        icon_size_key: str,
        tooltip: str,
    ) -> None:
        """
        软件治理区扫描图片按钮。
        样式从 config.py 读取，不在 QPushButton 上挂自定义属性。
        QMovie 更新前会检查 QPushButton 是否仍然有效，避免页面重建后后台疯狂报错。
        """
        path = self._asset_path(asset_key)
        icon_size = self._size_int(icon_size_key)
        button_size = self._size_int("software_scan_button_size")

        button.setToolTip(tooltip)
        button.setFixedSize(button_size, button_size)
        button.setIconSize(QSize(icon_size, icon_size))
        button.setText("")
        button.setFlat(True)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setStyleSheet(software_scan_image_button_qss())

        cache_key = id(button)
        cache = getattr(self, "_scan_button_movies", None)
        if cache is None:
            self._scan_button_movies = {}
            cache = self._scan_button_movies

        cached = cache.get(cache_key)
        old_movie = cached.get("movie") if isinstance(cached, dict) else None
        old_path = cached.get("path") if isinstance(cached, dict) else ""

        if old_movie is not None and old_path == path:
            if old_movie.state() != QMovie.MovieState.Running:
                old_movie.start()
            return

        if old_movie is not None:
            try:
                old_movie.stop()
                old_movie.deleteLater()
            except Exception:
                pass

        movie = QMovie(path)
        movie.setScaledSize(QSize(icon_size, icon_size))

        def _safe_update_icon(_frame: int = 0, b=button, m=movie, key=cache_key) -> None:
            if b is None or not shiboken6.isValid(b):
                try:
                    m.stop()
                    m.deleteLater()
                except Exception:
                    pass

                current_cache = getattr(self, "_scan_button_movies", {})
                if isinstance(current_cache, dict):
                    current_cache.pop(key, None)
                return

            pixmap = m.currentPixmap()
            if not pixmap.isNull():
                b.setIcon(QIcon(pixmap))

        movie.frameChanged.connect(_safe_update_icon)

        cache[cache_key] = {
            "movie": movie,
            "path": path,
        }

        movie.start()
        _safe_update_icon()

    def _set_mode_buttons(self, current_mode: str) -> None:
        mapping = {
            "disabled": getattr(self.w, "btn_desktop_mode_disabled", None),
            "restricted": getattr(self.w, "btn_desktop_mode_restricted", None),
            "trusted": getattr(self.w, "btn_desktop_mode_trusted", None),
            "test": getattr(self.w, "btn_desktop_mode_test", None),
        }

        in_test_mode = str(current_mode or "").strip().lower() == "test"
        developer_enabled = self._developer_mode_enabled()

        for mode, button in mapping.items():
            if button is None:
                continue
            if mode == "test":
                button.setVisible(developer_enabled)

            checked = mode == current_mode

            button.blockSignals(True)
            button.setChecked(checked)

            if mode in {"disabled", "restricted", "trusted"}:
                button.setEnabled(not in_test_mode)
                button.setStyleSheet(
                    self._mode_blue_button_style(
                        checked=checked,
                        interactive=not in_test_mode,
                    )
                )
            else:
                button.setEnabled(True)
                button.setStyleSheet(self._toggle_button_style(in_test_mode))

            button.blockSignals(False)

    def _set_test_backend_buttons(self, current_mode: str | None = None) -> None:
        controller = getattr(self.w, "desktop_controller", None)
        runtime = getattr(controller, "runtime", None)
        if runtime is None:
            return

        current_backend = str(getattr(runtime, "test_backend", "sandbox") or "sandbox").strip().lower()
        if current_mode is None:
            current_mode = self.w.desktop_controller._current_mode()
        current_mode = str(current_mode or "").strip().lower()
        developer_enabled = self._developer_mode_enabled()
        in_test_mode = current_mode == "test" and developer_enabled
        test_backend_widget = getattr(self.w, "desktop_test_backend_widget", None)
        if test_backend_widget is not None:
            test_backend_widget.setVisible(in_test_mode)
        test_mode_label = getattr(self.w, "desktop_test_mode_label", None)
        if test_mode_label is not None:
            test_mode_label.setVisible(in_test_mode)
        test_backend_label = getattr(self.w, "desktop_test_backend_label", None)
        if test_backend_label is not None:
            test_backend_label.setVisible(in_test_mode)
        vm_available = bool(getattr(runtime, "vm_test_available", False))
        vm_connection_state = str(getattr(runtime, "vm_connection_state", "unchecked") or "unchecked").strip().lower()
        test_mode_label = getattr(self.w, "desktop_test_mode_label", None)
        if test_mode_label is not None:
            if current_backend == "vm":
                if vm_connection_state == "connecting":
                    backend_text = "虚拟机测试（连接中）"
                else:
                    backend_text = "虚拟机测试" if vm_available else "虚拟机测试（VM 未连接）"
            else:
                backend_text = "沙盒测试"
            vm_state_text = str(getattr(runtime, "vm_status_text", "") or "").strip()
            if not vm_state_text:
                vm_state_text = "虚拟机状态：已连接" if vm_available else "虚拟机状态：未连接"
            test_mode_label.setText(
                "测试模式：开启中\n"
                f"测试出口：{backend_text}\n"
                f"{vm_state_text}"
            )

        mapping = {
            "sandbox": getattr(self.w, "btn_desktop_test_backend_sandbox", None),
            "vm": getattr(self.w, "btn_desktop_test_backend_vm", None),
        }
        for backend, button in mapping.items():
            if button is None:
                continue
            button.setVisible(in_test_mode)
            if not in_test_mode:
                button.blockSignals(True)
                button.setChecked(False)
                button.blockSignals(False)
                button.setStyleSheet(self._toggle_button_style(False))
                continue
            interactive = True
            if backend == "vm" and vm_connection_state == "connecting":
                interactive = False
            button.blockSignals(True)
            button.setChecked(backend == current_backend)
            button.setEnabled(interactive)
            button.blockSignals(False)
            if backend == "sandbox":
                button.setToolTip("沙盒测试：只返回审议和回执，不真实执行。")
            else:
                button.setToolTip(
                    "虚拟机测试：请先启动虚拟机测试代理。"
                    if not vm_available
                    else "虚拟机测试：在 VM 中执行测试动作，结果回传显示。"
                )
            if backend == "vm" and current_backend == "vm":
                button.setStyleSheet(self._vm_backend_button_style(vm_connection_state, interactive=interactive))
            else:
                button.setStyleSheet(
                    self._toggle_button_style(backend == current_backend, interactive=interactive)
                )

    def _set_shaofu_button_state(self) -> None:
        record_widget = getattr(self.w, "desktop_record_widget", None)
        if record_widget is not None:
            record_widget.setVisible(True)
        button = getattr(self.w, "btn_desktop_shaofu", None)
        if button is None:
            return
        button.setVisible(True)
        button.setText("记录")
        button.setEnabled(True)
        button.setToolTip("查看材料、备份、隔离、快照与可撤销记录。")

    def refresh_file_governance_visual_state(self, mode: str | None = None) -> None:
        controller = getattr(self.w, "desktop_controller", None)
        runtime = getattr(controller, "runtime", None)
        normalized_mode = str(mode or "").strip().lower()
        if not normalized_mode and controller is not None:
            try:
                normalized_mode = controller._current_mode()
            except Exception:
                normalized_mode = "disabled"
        editable = normalized_mode in {"trusted", "test"}
        if runtime is not None:
            editable = editable or bool(getattr(runtime, "file_governance_editable", False))
        self._apply_file_visual_state({"read_only": not editable})

        toggle = getattr(self.w, "desktop_file_edit_toggle", None)
        if toggle is not None:
            toggle.blockSignals(True)
            toggle.setChecked(bool(editable))
            toggle.setText("可调整" if editable else "只读")
            toggle.setEnabled(normalized_mode in {"trusted", "test"})
            toggle.blockSignals(False)

    def _find_layout_containing_widget(self, layout: QLayout | None, target: QWidget) -> QLayout | None:
        if layout is None:
            return None
        for index in range(layout.count()):
            item = layout.itemAt(index)
            if item is None:
                continue
            if item.widget() is target:
                return layout
            child_layout = item.layout()
            found = self._find_layout_containing_widget(child_layout, target)
            if found is not None:
                return found
        return None

    def _ensure_host_file_create_buttons(self) -> None:
        for attr_name in ("btn_desktop_create_file", "btn_desktop_create_folder"):
            button = getattr(self.w, attr_name, None)
            if button is not None:
                button.setVisible(False)
                button.setEnabled(False)
        return

    def _set_file_toolbar_state(self, state: dict, mode: str) -> None:
        controller = self.w.desktop_controller
        runtime = getattr(controller, "runtime", None)
        self._ensure_host_file_create_buttons()
        vm_backend = mode == "test" and str(getattr(runtime, "test_backend", "sandbox") or "sandbox").strip().lower() == "vm"
        vm_connected = (
            str(getattr(runtime, "vm_connection_state", "unchecked") or "unchecked").strip().lower() == "connected"
            and bool(getattr(runtime, "vm_test_available", False))
        )
        toggle = getattr(self.w, "desktop_file_edit_toggle", None)
        if toggle is not None:
            toggle.blockSignals(True)
            editable = not state["read_only"]
            toggle.setChecked(editable)
            toggle.setText("可调整" if editable else "只读")
            toggle.setEnabled(mode in {"trusted", "test"} and (not vm_backend or vm_connected))
            toggle.blockSignals(False)

        self._refresh_trusted_disk_combo(state)

        for attr_name, value in (
            ("desktop_disk_filter_combo", controller.runtime.disk_filter_key),
            ("desktop_disk_font_combo", controller.runtime.disk_font_size),
            ("desktop_object_view_combo", state["view_mode"]),
            ("desktop_object_filter_combo", controller.runtime.object_filter_key),
            ("desktop_object_font_combo", controller.runtime.object_font_size),
        ):
            combo = getattr(self.w, attr_name, None)
            if combo is None:
                continue
            combo.blockSignals(True)
            index = combo.findData(value)
            if index >= 0:
                combo.setCurrentIndex(index)
            combo.blockSignals(False)

        rescan_button = getattr(self.w, "btn_desktop_rescan_disk", None)
        if rescan_button is not None:
            scanning = bool(getattr(runtime, "vm_file_scan_in_progress", False)) or (
                str(getattr(runtime, "host_file_scan_status", "") or "").strip().lower() == "scanning"
            )
            can_scan = bool(state.get("can_rescan_disk", False))
            rescan_button.setEnabled(can_scan and not scanning)
            rescan_button.setToolTip("扫描中" if scanning else "扫描当前磁盘")

        can_create = bool(
            mode == "trusted"
            and state.get("view_mode") == "objects"
            and str(state.get("selected_disk_permission_state", "unset")).strip().lower() == "allow"
            and bool(state.get("file_actions_enabled", False))
            and str(state.get("current_path", "") or "").strip() not in {"", "-", "当前视图：根目录表"}
        )
        for attr_name in ("btn_desktop_create_file", "btn_desktop_create_folder"):
            button = getattr(self.w, attr_name, None)
            if button is not None:
                button.setVisible(False)
                button.setEnabled(False)

        parent_button = getattr(self.w, "btn_desktop_parent_dir", None)
        if parent_button is not None:
            parent_button.setEnabled(state.get("view_mode") == "objects" and bool(controller.runtime.current_directory))

        roots_button = getattr(self.w, "btn_desktop_roots_view", None)
        if roots_button is not None:
            roots_button.setEnabled(state.get("view_mode") != "roots")

    def _refresh_trusted_disk_combo(self, state: dict) -> None:
        combo = getattr(self.w, "desktop_trusted_disk_combo", None)
        if combo is None:
            return

        selected_disk = str(state.get("selected_disk", "")).strip().upper()
        controller = getattr(self.w, "desktop_controller", None)
        runtime = getattr(controller, "runtime", None)
        vm_backend = str(state.get("mode", "") or "").strip().lower() == "test" and str(getattr(runtime, "test_backend", "sandbox") or "sandbox").strip().lower() == "vm"

        allowed_states = {"allow", "once"}
        if vm_backend:
            allowed_states.add("test")

        trusted_rows = [
            row for row in state.get("trusted_disk_rows", [])
            if str(row.get("permission_state", "")).strip().lower() in allowed_states
        ]

        combo.blockSignals(True)
        combo.clear()
        if trusted_rows:
            for row in trusted_rows:
                disk_id = str(row.get("disk_id", "")).strip().upper()
                title = str(row.get("title", disk_id)).strip() or disk_id
                combo.addItem(title, disk_id)
            index = combo.findData(selected_disk)
            combo.setCurrentIndex(index if index >= 0 else 0)
            combo.setEnabled(True)
        else:
            combo.addItem("无可信磁盘", "")
            combo.setEnabled(False)
        combo.blockSignals(False) 

    def stop_scan_button_movies(self) -> None:
        cache = getattr(self, "_scan_button_movies", None)
        if not isinstance(cache, dict):
            return

        for item in list(cache.values()):
            movie = item.get("movie") if isinstance(item, dict) else None
            if movie is not None:
                try:
                    movie.stop()
                    movie.deleteLater()
                except Exception:
                    pass

        cache.clear()
        
    def _set_software_toolbar_state(self, state: dict) -> None:
        runtime = self.w.desktop_controller.runtime
        scanning = bool(getattr(runtime, "software_scan_in_progress", False))
        toggle = getattr(self.w, "desktop_apps_edit_toggle", None)
        if toggle is not None:
            toggle.blockSignals(True)
            editable = not state["apps_read_only"]
            toggle.setChecked(editable)
            toggle.setText("可调整" if editable else "只读")
            toggle.setEnabled(state["can_toggle_apps_editable"])
            toggle.blockSignals(False)

        for attr_name, value in (
            ("desktop_app_filter_combo", self.w.desktop_controller.current_filter_key()),
            ("desktop_software_font_combo", self.w.desktop_controller.runtime.software_font_size),
        ):
            combo = getattr(self.w, attr_name, None)
            if combo is None:
                continue
            combo.blockSignals(True)
            index = combo.findData(value)
            if index >= 0:
                combo.setCurrentIndex(index)
            combo.blockSignals(False)

        for attr_name, enabled in (
            ("btn_desktop_load_apps_memory", state["show_apps"] and not scanning),
            ("btn_desktop_rescan", state["can_scan"] and not scanning),
            ("btn_desktop_full_scan", state["can_scan"] and not scanning),
            ("btn_desktop_clear_apps", state["show_apps"] and not scanning),
        ):
            button = getattr(self.w, attr_name, None)
            if button is not None:
                button.setEnabled(bool(enabled))
        load_memory_button = getattr(self.w, "btn_desktop_load_apps_memory", None)
        if load_memory_button is not None:
            loaded = bool(getattr(runtime, "software_table_loaded", False))
            load_memory_button.setText("刷新列表" if loaded else "加载上次记录")
            load_memory_button.setToolTip("扫描中" if scanning else "加载上次保存的软件记录")
        rescan_button = getattr(self.w, "btn_desktop_rescan", None)
        if rescan_button is not None:
            rescan_button.setToolTip("扫描中" if scanning else "快速扫描软件")
        full_scan_button = getattr(self.w, "btn_desktop_full_scan", None)
        if full_scan_button is not None:
            full_scan_button.setToolTip("扫描中" if scanning else "完整扫描软件")
        self._apply_software_scan_button_visual()

    def _set_software_scan_button_state(self, state: dict) -> None:
        runtime = self.w.desktop_controller.runtime
        scanning = bool(getattr(runtime, "software_scan_in_progress", False))
        for attr_name, enabled in (
            ("btn_desktop_load_apps_memory", state["show_apps"] and not scanning),
            ("btn_desktop_rescan", state["can_scan"] and not scanning),
            ("btn_desktop_full_scan", state["can_scan"] and not scanning),
            ("btn_desktop_clear_apps", state["show_apps"] and not scanning),
        ):
            button = getattr(self.w, attr_name, None)
            if button is not None:
                button.setEnabled(bool(enabled))
        rescan_button = getattr(self.w, "btn_desktop_rescan", None)
        if rescan_button is not None:
            rescan_button.setToolTip("扫描中" if scanning else "快速扫描软件")
        full_scan_button = getattr(self.w, "btn_desktop_full_scan", None)
        if full_scan_button is not None:
            full_scan_button.setToolTip("扫描中" if scanning else "完整扫描软件")
        self._apply_software_scan_button_visual()

    def _set_readonly_state(self, state: dict) -> None:
        combo = getattr(self.w, "desktop_runtime_root_combo", None)
        if combo is not None:
            combo.blockSignals(True)
            combo.clear()
            for item in state.get("root_options", []):
                combo.addItem(str(item.get("title", "-")), str(item.get("root_id", "")))
            if combo.count() == 0:
                combo.addItem("暂无可用根目录", "")
            selected_root_id = str(state.get("selected_root_id", "")).strip()
            if selected_root_id:
                index = combo.findData(selected_root_id)
                if index >= 0:
                    combo.setCurrentIndex(index)
            combo.setEnabled(bool(state.get("root_options")))
            combo.blockSignals(False)

        for attr_name, enabled in (
            ("btn_desktop_read_datetime", state.get("can_read_datetime", False)),
            ("btn_desktop_list_root", state.get("can_use_root_actions", False)),
            ("btn_desktop_root_meta", state.get("can_use_root_actions", False)),
            ("btn_desktop_open_root", state.get("can_use_root_actions", False)),
            ("btn_desktop_clear_result", bool(state.get("result"))),
        ):
            button = getattr(self.w, attr_name, None)
            if button is not None:
                button.setEnabled(bool(enabled))

        result_display = getattr(self.w, "desktop_readonly_result_display", None)
        if result_display is not None:
            result_display.setPlainText(self._format_readonly_result(state.get("result")))

    def _set_sandbox_state(self, state: dict) -> None:
        clear_button = getattr(self.w, "btn_desktop_clear_sandbox_result", None)
        if clear_button is not None:
            clear_button.setEnabled(bool(state.get("result")))

        result_display = getattr(self.w, "desktop_sandbox_result_display", None)
        if result_display is not None:
            result_display.setPlainText(self._format_sandbox_result(state.get("result")))

    def _format_readonly_result(self, result: dict | None) -> str:
        if not result:
            return "尚未执行基础只读验证。"

        action = str(result.get("action", "")).strip() or "-"
        adapter_id = str(result.get("adapter_id", "")).strip() or "-"
        message = str(result.get("message", "")).strip() or "-"
        data = result.get("data", {})
        parts = [
            f"结果：{'成功' if result.get('ok') else '失败'}",
            f"动作：{action}",
            f"适配器：{adapter_id}",
            f"说明：{message}",
        ]
        if data:
            parts.extend(["", "数据：", self._pretty_json_text(data) or "{}"])
        return "\n".join(parts)

    def _format_sandbox_result(self, result: dict | None) -> str:
        if not result:
            return "尚未执行沙盒测试。"

        data = result.get("data", {}) or {}
        presenter = MessagePresenter()
        if (
            str(result.get("adapter_id", "")).strip().lower() == "vm"
            or str(data.get("adapter_stage", "")).strip().lower() == "vm"
            or str(data.get("executed_in", "")).strip().lower() == "vm"
        ):
            return self._format_vm_sandbox_result(result, data)

        target_object = data.get("target_object", {}) or {}
        action = str(data.get("current_action", result.get("action", "-")) or "-")
        parts = [
            f"结果：{presenter.receipt_outcome(backend='sandbox', action=action, ok=bool(result.get('ok', False)))}",
            f"动作：{action}",
            f"对象：{data.get('current_target', '-')}",
            f"模式：{data.get('current_mode', '-')}",
            f"审议：{data.get('review_result', '-')}",
            f"路由：{data.get('route_result', '-')}",
            f"目标对象：{target_object.get('path', '-')}",
            f"说明：{data.get('sandbox_text', result.get('message', '-'))}",
        ]
        reason = str(data.get("review_reason", "")).strip()
        if reason:
            parts.append(f"审议说明：{reason}")
        return "\n".join(parts)

    def _format_vm_sandbox_result(self, result: dict, data: dict) -> str:
        presenter = MessagePresenter()
        message = str(data.get("vm_agent_message", data.get("message", result.get("message", "-"))) or "-")
        action = str(data.get("current_action", result.get("action", "-")) or "-")
        parts = [
            f"结果：{presenter.receipt_outcome(backend='vm', action=action, ok=bool(result.get('ok', False)))}",
            f"动作：{action}",
            f"App ID：{data.get('app_id', data.get('current_target', '-'))}",
            f"主机：{data.get('hostname', '-') or '-'}",
            f"说明：{message}",
        ]
        for label, key in (
            ("Root ID", "root_id"),
            ("Relative path", "relative_path"),
            ("Total count", "total_count"),
            ("Visible count", "visible_count"),
            ("Hidden count", "hidden_count"),
        ):
            value = data.get(key, "")
            if value != "" and value is not None:
                parts.append(f"{label}: {value}")
        for label, key in (
            ("审议阶段", "review_stage"),
            ("决策", "decision"),
            ("风险", "risk_level"),
            ("路由", "route_result"),
            ("恢复点", "checkpoint_id"),
            ("请求 ID", "request_id"),
            ("VM 动作", "vm_agent_action"),
            ("HTTP 状态", "http_status"),
        ):
            value = str(data.get(key, "") or "").strip()
            if value:
                parts.append(f"{label}：{value}")
        for label, key in (
            ("Shell 入口", "shell_entry"),
            ("定位入口", "locate_entry"),
            ("启动类型", "launch_target_kind"),
            ("路径", "path"),
            ("文件夹", "folder"),
            ("进程", "process_name"),
            ("进程列表", "process_names"),
        ):
            raw_value = data.get(key, "")
            value = ", ".join(str(item) for item in raw_value) if isinstance(raw_value, list) else str(raw_value or "").strip()
            if value:
                parts.append(f"{label}：{value}")
        error = str(data.get("error", "") or "").strip()
        if error:
            parts.append(f"错误：{error}")
        return "\n".join(parts)

    def _make_item(self, text: str, *, align_center: bool = False) -> QTableWidgetItem:
        item = QTableWidgetItem(text)
        item.setFlags(Qt.ItemFlag.ItemIsEnabled)
        if align_center:
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        return item

    def _status_badge_style(self, color: str, size_key: str | None = None) -> str:
        normalized = str(color or "").strip().lower() or "#f5f5f5"
        dark_text_colors = {"#f5f5f5", "#facc15"}
        text_color = "#1F2937" if normalized in dark_text_colors else "#FFFFFF"
        border_color = "#D1D5DB" if normalized == "#f5f5f5" else normalized
        radius = self._size_int("status_badge_radius")
        padding_v = self._size_int("status_badge_padding_v")
        padding_h = self._size_int("status_badge_padding_h")
        min_height = self._size_int("status_badge_min_height")
        border_width = self._size_int("status_badge_border_width")
        return (
            "QLabel, QPushButton {"
            f"background-color: {normalized};"
            f"color: {text_color};"
            f"border: {border_width}px solid {border_color};"
            f"border-radius: {radius}px;"
            f"padding: {padding_v}px {padding_h}px;"
            "font-weight: 700;"
            f"min-height: {min_height}px;"
            "}"
        ) + self._font_style_block("QLabel, QPushButton", size_key)

    def _permission_button_style(self, size_key: str | None = None) -> str:
        radius = self._size_int("permission_button_radius")
        padding_v = self._size_int("permission_button_padding_v")
        padding_h = self._size_int("permission_button_padding_h")
        min_height = self._size_int("permission_button_min_height")
        border_width = self._size_int("permission_button_border_width")
        return (
            "QPushButton {"
            "background-color: rgba(17, 27, 41, 0.94);"
            "color: #E8F0FF;"
            f"border: {border_width}px solid rgba(148, 163, 184, 0.56);"
            f"border-radius: {radius}px;"
            f"padding: {padding_v}px {padding_h}px;"
            "font-weight: 700;"
            f"min-height: {min_height}px;"
            "}"
            "QPushButton:hover {"
            "background-color: rgba(45, 68, 102, 0.96);"
            "border-color: rgba(191, 219, 254, 0.72);"
            "}"
        ) + self._font_style_block("QPushButton", size_key)

    def _desktop_color(self) -> dict:
        return getattr(self.w, "DESKTOP_UI_COLOR", {})

    def _desktop_size(self) -> dict:
        return getattr(self.w, "DESKTOP_UI_SIZE", {})

    def _size_int(self, key: str) -> int:
        controller = getattr(self.w, "desktop_controller", None)
        runtime = getattr(controller, "runtime", None)
        overrides = getattr(runtime, "layout_overrides", {}) if runtime is not None else {}
        if key in overrides:
            return int(overrides[key])
        return int(self._desktop_size()[key])

    def _toggle_button_style(self, value: bool, *, interactive: bool = True, size_key: str | None = None) -> str:
        """
        桌面连接页：测试模式 / 测试出口按钮样式。

        只用于：
        - 测试模式按钮
        - 沙盒测试按钮
        - 虚拟机测试按钮

        正式主模式按钮不要使用这个函数。
        """
        color = self._desktop_color()

        background = color.get("desktop_test_button_bg", "rgba(13, 20, 32, 0.96)")
        radius = self._size_int("desktop_test_button_radius")
        padding_v = self._size_int("desktop_test_button_padding_v")
        padding_h = self._size_int("desktop_test_button_padding_h")
        min_height = self._size_int("desktop_test_button_min_height")
        border_width = self._size_int("desktop_test_button_border_width")

        if not interactive:
            border = color.get("desktop_test_button_disabled_border", "#4B5563")
            text = color.get("desktop_test_button_disabled_text", "#6B7280")
        elif value:
            border = color.get("desktop_test_button_on_border", "#22C55E")
            text = color.get("desktop_test_button_on_text", "#86EFAC")
        else:
            border = color.get("desktop_test_button_off_border", "#7F1D1D")
            text = color.get("desktop_test_button_off_text", "#FCA5A5")

        return (
            "QPushButton {"
            f"background-color: {background};"
            f"color: {text};"
            f"border: {border_width}px solid {border};"
            f"border-radius: {radius}px;"
            f"padding: {padding_v}px {padding_h}px;"
            "font-weight: 700;"
            f"min-height: {min_height}px;"
            "}"
        ) + self._font_style_block("QPushButton", size_key)
    
    def _mode_blue_button_style(
        self,
        *,
        checked: bool = False,
        interactive: bool = True,
        size_key: str | None = None,
    ) -> str:
        """
        桌面连接页：正式主模式按钮样式。

        用于：
        - 不启用
        - 限制模式
        - 信任模式

        测试模式按钮不使用这个函数。
        """
        color = self._desktop_color()

        radius = self._size_int("desktop_mode_button_radius")
        padding_v = self._size_int("desktop_mode_button_padding_v")
        padding_h = self._size_int("desktop_mode_button_padding_h")
        min_height = self._size_int("desktop_mode_button_min_height")
        border_width = self._size_int("desktop_mode_button_border_width")

        if not interactive:
            bg = color.get("desktop_mode_button_disabled_bg", "#4A4A4A")
            border = color.get("desktop_mode_button_disabled_border", "#4A4A4A")
            text = color.get("desktop_mode_button_disabled_text", "#BFBFBF")
        elif checked:
            bg = color.get("desktop_mode_button_bg_checked", "#4C84EC")
            border = color.get("desktop_mode_button_border_checked", "#93C5FD")
            text = color.get("desktop_mode_button_text", "#FFFFFF")
        else:
            bg = color.get("desktop_mode_button_bg", "#3A8DFF")
            border = color.get("desktop_mode_button_border", "#3A8DFF")
            text = color.get("desktop_mode_button_text", "#FFFFFF")

        hover_bg = color.get("desktop_mode_button_bg_hover", bg)

        return (
            "QPushButton {"
            f"background-color: {bg};"
            f"color: {text};"
            f"border: {border_width}px solid {border};"
            f"border-radius: {radius}px;"
            f"padding: {padding_v}px {padding_h}px;"
            "font-weight: 700;"
            f"min-height: {min_height}px;"
            "}"
            "QPushButton:hover {"
            f"background-color: {hover_bg};"
            "}"
        ) + self._font_style_block("QPushButton", size_key)

    def _vm_backend_button_style(self, state: str, *, interactive: bool = True, size_key: str | None = None) -> str:
        """
        桌面连接页：虚拟机测试按钮的连接状态样式。

        VM 按钮在被选中时会额外参考 VM 连接状态：
        - connected：绿色
        - connecting / unchecked / failed：提示色
        """
        color = self._desktop_color()

        background = color.get("desktop_test_button_bg", "rgba(13, 20, 32, 0.96)")
        radius = self._size_int("desktop_test_button_radius")
        padding_v = self._size_int("desktop_test_button_padding_v")
        padding_h = self._size_int("desktop_test_button_padding_h")
        min_height = self._size_int("desktop_test_button_min_height")
        border_width = self._size_int("desktop_test_button_border_width")

        normalized = str(state or "").strip().lower()
        if not interactive or normalized == "connecting":
            border = color.get("desktop_vm_button_pending_border", "#FACC15")
            text = color.get("desktop_vm_button_pending_text", "#FDE68A")
        elif normalized == "connected":
            border = color.get("desktop_test_button_on_border", "#22C55E")
            text = color.get("desktop_test_button_on_text", "#86EFAC")
        else:
            border = color.get("desktop_vm_button_pending_border", "#FACC15")
            text = color.get("desktop_vm_button_pending_text", "#FDE68A")

        return (
            "QPushButton {"
            f"background-color: {background};"
            f"color: {text};"
            f"border: {border_width}px solid {border};"
            f"border-radius: {radius}px;"
            f"padding: {padding_v}px {padding_h}px;"
            "font-weight: 700;"
            f"min-height: {min_height}px;"
            "}"
        ) + self._font_style_block("QPushButton", size_key)

    def _apply_file_visual_state(self, state: dict) -> None:
        editable = not bool(state.get("read_only", True))
        color = self._desktop_color()
        card = getattr(self.w, "desktop_file_card", None)
        if card is not None:
            border = color.get("file_card_editable_border" if editable else "file_card_readonly_border", "#22C55E" if editable else "#EF4444")
            bg = color.get("file_card_editable_bg" if editable else "file_card_readonly_bg", "rgba(18, 42, 32, 0.94)" if editable else "rgba(42, 22, 26, 0.92)")
            width = self._size_int("file_card_border_width_editable" if editable else "file_card_border_width_readonly")
            radius = self._size_int("file_card_border_radius")
            card.setStyleSheet(
                "QFrame#desktopFileCard {"
                f"background-color: {bg};"
                f"border: {width}px solid {border};"
                f"border-radius: {radius}px;"
                "}"
            )

        toggle = getattr(self.w, "desktop_file_edit_toggle", None)
        if toggle is not None:
            border = color.get("file_toggle_editable_border" if editable else "file_toggle_readonly_border", "#22C55E" if editable else "#EF4444")
            bg = color.get("file_toggle_editable_bg" if editable else "file_toggle_readonly_bg", "rgba(20, 58, 42, 0.96)" if editable else "rgba(54, 26, 30, 0.95)")
            radius = self._size_int("file_toggle_border_radius")
            border_width = self._size_int("file_toggle_border_width")
            padding_v = self._size_int("file_toggle_padding_v")
            padding_h = self._size_int("file_toggle_padding_h")
            toggle.setStyleSheet(
                "QPushButton {"
                f"background-color: {bg};"
                "color: #FFFFFF;"
                f"border: {border_width}px solid {border};"
                f"border-radius: {radius}px;"
                "font-weight: 700;"
                f"padding: {padding_v}px {padding_h}px;"
                "}"
            )

        hint_color = color.get("file_hint_editable_text" if editable else "file_hint_readonly_text", "#D6F5E1" if editable else "#A7B0C0")
        for attr_name in ("desktop_file_hint_label", "desktop_disk_hint_label", "desktop_file_path_label"):
            label = getattr(self.w, attr_name, None)
            if label is not None:
                label.setStyleSheet(f"color: {hint_color};")

        for attr_name in ("desktop_disk_table", "desktop_file_table"):
            table = getattr(self.w, attr_name, None)
            if table is not None:
                table.setStyleSheet(self._file_table_style(editable))

    def _apply_software_visual_state(self, state: dict) -> None:
        editable = not bool(state.get("apps_read_only", True))
        color = self._desktop_color()
        card = getattr(self.w, "desktop_software_card", None)
        if card is not None:
            border = color.get("software_card_editable_border" if editable else "software_card_readonly_border", "#22C55E" if editable else "#EF4444")
            bg = color.get("software_card_editable_bg" if editable else "software_card_readonly_bg", "rgba(18, 42, 32, 0.94)" if editable else "rgba(42, 22, 26, 0.92)")
            width = self._size_int("file_card_border_width_editable" if editable else "file_card_border_width_readonly")
            radius = self._size_int("file_card_border_radius")
            card.setStyleSheet(
                "QFrame#desktopSoftwareCard {"
                f"background-color: {bg};"
                f"border: {width}px solid {border};"
                f"border-radius: {radius}px;"
                "}"
            )

        toggle = getattr(self.w, "desktop_apps_edit_toggle", None)
        if toggle is not None:
            border = color.get("software_toggle_editable_border" if editable else "software_toggle_readonly_border", "#22C55E" if editable else "#EF4444")
            bg = color.get("software_toggle_editable_bg" if editable else "software_toggle_readonly_bg", "rgba(20, 58, 42, 0.96)" if editable else "rgba(54, 26, 30, 0.95)")
            radius = self._size_int("file_toggle_border_radius")
            border_width = self._size_int("file_toggle_border_width")
            padding_v = self._size_int("file_toggle_padding_v")
            padding_h = self._size_int("file_toggle_padding_h")
            toggle.setStyleSheet(
                "QPushButton {"
                f"background-color: {bg};"
                "color: #FFFFFF;"
                f"border: {border_width}px solid {border};"
                f"border-radius: {radius}px;"
                "font-weight: 700;"
                f"padding: {padding_v}px {padding_h}px;"
                "}"
            )

        hint_color = color.get("file_hint_editable_text" if editable else "file_hint_readonly_text", "#D6F5E1" if editable else "#A7B0C0")
        for attr_name in ("desktop_apps_hint_label", "desktop_software_discovered_label", "desktop_software_confirmed_label", "desktop_software_hidden_label"):
            label = getattr(self.w, attr_name, None)
            if label is not None:
                label.setStyleSheet(f"color: {hint_color};")

    def _file_table_style(self, editable: bool, preset: dict | None = None) -> str:
        preset = preset or {}
        color = self._desktop_color()
        bg = color.get("file_table_editable_bg" if editable else "file_table_readonly_bg", "rgba(12, 24, 20, 0.92)" if editable else "rgba(8, 12, 20, 0.90)")
        hover = color.get("file_table_editable_hover" if editable else "file_table_readonly_hover", "rgba(34, 197, 94, 0.16)" if editable else "rgba(54, 26, 30, 0.45)")
        radius = self._size_int("desktop_table_border_radius")
        border_width = self._size_int("desktop_table_border_width")
        item_separator_width = self._size_int("desktop_table_item_separator_width")
        header_separator_width = self._size_int("desktop_table_header_separator_width")
        table_padding = self._size_int("desktop_table_padding")
        item_padding_v = self._size_int("desktop_table_item_padding_v")
        item_padding_h = self._size_int("desktop_table_item_padding_h")
        header_padding_v = self._preset_int(preset, "desktop_table_header_padding_v")
        header_padding_h = self._preset_int(preset, "desktop_table_header_padding_h")
        return (
            "QTableWidget {"
            f"background-color: {bg};"
            "alternate-background-color: rgba(17, 26, 40, 0.92);"
            f"border: {border_width}px solid rgba(110, 138, 180, 0.30);"
            f"border-radius: {radius}px;"
            f"padding: {table_padding}px;"
            "gridline-color: rgba(110, 138, 180, 0.24);"
            "}"
            "QTableWidget::item {"
            f"padding: {item_padding_v}px {item_padding_h}px;"
            f"border-bottom: {item_separator_width}px solid rgba(110, 138, 180, 0.12);"
            "}"
            "QTableWidget::item:hover {"
            f"background-color: {hover};"
            "}"
            "QHeaderView::section {"
            "background-color: rgba(20, 31, 48, 0.96);"
            "color: #DCE6FA;"
            "border: none;"
            f"border-right: {header_separator_width}px solid rgba(148, 163, 184, 0.34);"
            f"border-bottom: {header_separator_width}px solid rgba(110, 138, 180, 0.30);"
            f"padding: {header_padding_v}px {header_padding_h}px;"
            "font-weight: 700;"
            "}"
        )

    def _apply_table_font(self, attr_name: str, size_key: str) -> None:
        table = getattr(self.w, attr_name, None)
        if table is None:
            return
        font = table.font()
        font.setPointSize(self._font_points(size_key))
        table.setFont(font)
        header_font = table.horizontalHeader().font()
        header_font.setPointSize(self._font_points(size_key))
        table.horizontalHeader().setFont(header_font)
        for row in range(table.rowCount()):
            for column in range(table.columnCount()):
                item = table.item(row, column)
                if item is not None:
                    item.setFont(font)

    def _apply_widget_font(self, widget, size_key: str) -> None:
        if widget is None:
            return
        points = self._font_points(size_key)
        font = widget.font()
        font.setPointSize(points)
        widget.setFont(font)
        style = str(widget.styleSheet() or "").strip()
        style = re.sub(r"font-size:\s*\d+pt;\s*", "", style)
        font_rule = f"font-size: {points}pt;"
        if "{" in style:
            selector = type(widget).__name__
            widget.setStyleSheet(f"{style}{selector} {{{font_rule}}}")
        else:
            separator = "" if not style or style.endswith(";") else ";"
            widget.setStyleSheet(f"{style}{separator}{font_rule}")

    def _apply_result_font(self, attr_name: str, size_key: str) -> None:
        widget = getattr(self.w, attr_name, None)
        if widget is None:
            return
        font = widget.font()
        font.setPointSize(self._font_points(size_key))
        widget.setFont(font)

    def _apply_desktop_label_fonts(self) -> None:
        controller = getattr(self.w, "desktop_controller", None)
        runtime = getattr(controller, "runtime", None)
        if runtime is None:
            return

        for attr_name in (
            "desktop_file_hint_label",
            "desktop_disk_hint_label",
            "desktop_file_path_label",
            "desktop_readonly_summary_label",
        ):
            self._apply_widget_font(getattr(self.w, attr_name, None), runtime.object_font_size)

        for attr_name in (
            "desktop_apps_hint_label",
            "desktop_software_discovered_label",
            "desktop_software_confirmed_label",
            "desktop_software_hidden_label",
            "desktop_sandbox_summary_label",
        ):
            self._apply_widget_font(getattr(self.w, attr_name, None), runtime.software_font_size)
        self._apply_software_scan_label_fonts()

    def _apply_software_scan_label_fonts(self) -> None:
        controller = getattr(self.w, "desktop_controller", None)
        runtime = getattr(controller, "runtime", None)
        if runtime is None:
            return
        for attr_name in (
            "desktop_software_scan_stage_label",
            "desktop_software_scan_stats_label",
            "desktop_software_scan_log_label",
        ):
            self._apply_widget_font(getattr(self.w, attr_name, None), runtime.software_font_size)

    def _set_software_scan_status(self) -> None:
        runtime = getattr(getattr(self.w, "desktop_controller", None), "runtime", None)
        if runtime is None:
            return
        self._set_text("desktop_software_scan_stage_label", self.software_scan_status_presenter.format_stage_text(runtime))
        self._set_text("desktop_software_scan_stats_label", self.software_scan_status_presenter.format_stats_text(runtime))
        self._set_text("desktop_software_scan_log_label", self.software_scan_status_presenter.format_log_preview(runtime))
        scanning = bool(getattr(runtime, "software_scan_in_progress", False))
        percent = int(getattr(runtime, "software_scan_progress_percent", 0) or 0)
        percent = max(0, min(100, percent))

        progress_bar = getattr(self.w, "desktop_software_scan_progress_bar", None)
        if progress_bar is not None:
            progress_bar.setValue(percent)
            progress_bar.setVisible(bool(scanning or percent >= 100))

        animation_label = getattr(self.w, "desktop_software_scan_animation_label", None)
        if animation_label is None:
            return
        movie = getattr(animation_label, "_desktop_scan_feedback_movie", None)
        if scanning:
            path = self._asset_path("desktop.scan_feedback_gif")
            size = self._size_int("software_scan_feedback_icon_size")
            if movie is None or getattr(animation_label, "_desktop_scan_feedback_movie_path", "") != path:
                movie = QMovie(path)
                movie.setScaledSize(QSize(size, size))
                animation_label._desktop_scan_feedback_movie = movie
                animation_label._desktop_scan_feedback_movie_path = path
                animation_label.setMovie(movie)
            animation_label.setVisible(True)
            if movie.state() != QMovie.MovieState.Running:
                movie.start()
            return

        if movie is not None:
            movie.stop()
        animation_label.setVisible(False)

    def _restore_desktop_page_scroll(self) -> None:
        controller = getattr(self.w, "desktop_controller", None)
        runtime = getattr(controller, "runtime", None)
        scroll_area = getattr(self.w, "desktop_scroll_area", None)
        if runtime is None or scroll_area is None:
            return
        value = int(getattr(runtime, "desktop_page_scroll_value", 0) or 0)
        bar = scroll_area.verticalScrollBar()
        if bar is None:
            return

        def restore() -> None:
            bar.setValue(min(value, bar.maximum()))

        QTimer.singleShot(0, restore)

    def _restore_table_scroll(self, attr_name: str, *, vertical_attr: str | None = None, horizontal_attr: str | None = None) -> None:
        controller = getattr(self.w, "desktop_controller", None)
        runtime = getattr(controller, "runtime", None)
        table = getattr(self.w, attr_name, None)
        if runtime is None or table is None:
            return

        if vertical_attr:
            bar = table.verticalScrollBar()
            value = int(getattr(runtime, vertical_attr, 0) or 0)
            bar.setValue(min(value, bar.maximum()))
            setattr(runtime, vertical_attr, int(bar.value()))
        if horizontal_attr:
            bar = table.horizontalScrollBar()
            value = int(getattr(runtime, horizontal_attr, 0) or 0)
            bar.setValue(min(value, bar.maximum()))
            setattr(runtime, horizontal_attr, int(bar.value()))

    def _restore_desktop_table_scrolls(self) -> None:
        self._restore_table_scroll(
            "desktop_file_table",
            vertical_attr="file_table_vertical_scroll_value",
            horizontal_attr="file_table_horizontal_scroll_value",
        )
        self._restore_table_scroll(
            "desktop_apps_table",
            vertical_attr="software_table_scroll_value",
            horizontal_attr="software_table_horizontal_scroll_value",
        )

    def _font_points(self, size_key: str) -> int:
        size_name = str(size_key or "medium").strip()
        config_key = {
            "small": "desktop_font_small",
            "medium": "desktop_font_medium",
            "large": "desktop_font_large",
        }.get(size_name, "desktop_font_medium")
        return self._size_int(config_key)

    def _font_css(self, size_key: str) -> str:
        return f"font-size: {self._font_points(size_key)}pt;"

    def _font_style_block(self, selector: str, size_key: str | None) -> str:
        if not size_key:
            return ""
        return f"{selector} {{{self._font_css(size_key)}}}"

    def _software_action_button_size(self, size_key: str) -> tuple[int, int]:
        size_name = str(size_key or "medium").strip().lower()
        width_key = {
            "small": "software_action_button_width_small",
            "medium": "software_action_button_width_medium",
            "large": "software_action_button_width_large",
        }.get(size_name, "software_action_button_width")
        height_key = {
            "small": "software_action_button_height_small",
            "medium": "software_action_button_height_medium",
            "large": "software_action_button_height_large",
        }.get(size_name, "software_action_button_height")
        return self._size_int(width_key), self._size_int(height_key)

    def _layout_breakpoints(self) -> dict:
        breakpoints = getattr(self.w, "DESKTOP_LAYOUT_BREAKPOINTS", {})
        return breakpoints if isinstance(breakpoints, dict) else {}

    def _layout_presets(self) -> dict:
        presets = getattr(self.w, "DESKTOP_LAYOUT_PRESETS", {})
        return presets if isinstance(presets, dict) else {}

    def _current_file_layout_width(self) -> int:
        card = getattr(self.w, "desktop_file_card", None)
        if card is not None and card.width() > 0:
            return int(card.width())

        widths = []
        for attr_name in ("desktop_file_table", "desktop_disk_table"):
            table = getattr(self.w, attr_name, None)
            if table is None:
                continue
            viewport = table.viewport()
            width = viewport.width() if viewport is not None else table.width()
            if width > 0:
                widths.append(int(width))
        return max(widths) if widths else 0

    def _resolve_layout_preset(self) -> tuple[str, dict]:
        width = self._current_file_layout_width()
        breakpoints = self._layout_breakpoints()
        compact_max = int(breakpoints.get("compact_max", 1180))
        normal_max = int(breakpoints.get("normal_max", 1580))

        if width <= compact_max:
            name = "compact"
        elif width <= normal_max:
            name = "normal"
        else:
            name = "wide"

        presets = self._layout_presets()
        preset = presets.get(name, {})
        if not isinstance(preset, dict):
            preset = {}
        return name, preset

    def _preset_int(self, preset: dict | None, key: str, default: int | None = None) -> int:
        if isinstance(preset, dict) and key in preset:
            return int(preset[key])
        if default is not None:
            return int(default)
        return self._size_int(key)

    def _table_view_width(self, table) -> int:
        if table is None:
            return 0
        viewport = table.viewport()
        width = viewport.width() if viewport is not None else table.width()
        return int(width) if width > 0 else int(table.width())

    def _set_table_column_widths(self, table, widths: dict[int, int]) -> None:
        if table is None:
            return
        header = table.horizontalHeader()
        old_blocked = header.blockSignals(True) if header is not None else False
        try:
            for column, width in widths.items():
                table.setColumnWidth(int(column), max(1, int(width)))
        finally:
            if header is not None:
                header.blockSignals(old_blocked)

    def _apply_table_row_height(self, table, row_height: int) -> None:
        if table is None:
            return
        for row in range(table.rowCount()):
            table.setRowHeight(row, int(row_height))

    def _is_file_governance_editable(self) -> bool:
        toggle = getattr(self.w, "desktop_file_edit_toggle", None)
        return bool(toggle is not None and toggle.isChecked())

    def _pretty_json_text(self, data: dict) -> str:
        if not isinstance(data, dict) or not data:
            return ""
        try:
            return json.dumps(data, ensure_ascii=False, indent=2)
        except Exception:
            return ""

    def _disk_button_style(self, *, selected: bool, status_color: str, size_key: str | None = None) -> str:
        accent = str(status_color or "#5B6C8A").strip() or "#5B6C8A"
        border = accent if selected else "rgba(148, 163, 184, 0.70)"
        background = "rgba(37, 58, 88, 0.96)" if selected else "rgba(17, 27, 41, 0.94)"
        text = "#FFFFFF" if selected else "#DCE6FA"
        radius = self._size_int("disk_name_button_radius")
        padding_v = self._size_int("disk_name_button_padding_v")
        padding_h = self._size_int("disk_name_button_padding_h")
        min_height = self._size_int("disk_name_button_min_height")
        border_width = self._size_int("disk_name_button_border_width")
        return (
            "QPushButton {"
            f"background-color: {background};"
            f"color: {text};"
            f"border: {border_width}px solid {border};"
            f"border-radius: {radius}px;"
            f"padding: {padding_v}px {padding_h}px;"
            "font-weight: 700;"
            "text-align: left;"
            f"min-height: {min_height}px;"
            "}"
            "QPushButton:hover {"
            "background-color: rgba(45, 68, 102, 0.96);"
            "}"
        ) + self._font_style_block("QPushButton", size_key)

    def _name_cell_style(self, size_key: str | None = None) -> str:
        radius = self._size_int("name_cell_radius")
        padding_v = self._size_int("name_cell_padding_v")
        padding_h = self._size_int("name_cell_padding_h")
        border_width = self._size_int("name_cell_border_width")
        return (
            "QLabel {"
            "background-color: rgba(18, 30, 46, 0.96);"
            "color: #E8F0FF;"
            f"border: {border_width}px solid rgba(148, 163, 184, 0.72);"
            f"border-radius: {radius}px;"
            f"padding: {padding_v}px {padding_h}px;"
            "font-weight: 700;"
            "}"
        ) + self._font_style_block("QLabel", size_key)

    def _software_name_cell_style(self, size_key: str | None = None) -> str:
        radius = self._size_int("name_cell_radius")
        padding_v = self._size_int("name_cell_padding_v")
        padding_h = self._size_int("name_cell_padding_h")
        border_width = self._size_int("name_cell_border_width")
        return (
            "QLabel {"
            "background-color: rgba(18, 30, 46, 0.88);"
            "color: #E8F0FF;"
            f"border: {border_width}px solid rgba(110, 138, 180, 0.50);"
            f"border-radius: {radius}px;"
            f"padding: {padding_v}px {padding_h}px;"
            "font-weight: 700;"
            "}"
        ) + self._font_style_block("QLabel", size_key)

    def _action_button_style(self, size_key: str | None = None) -> str:
        radius = self._size_int("action_button_radius")
        padding_v = self._size_int("action_button_padding_v")
        padding_h = self._size_int("action_button_padding_h")
        min_height = self._size_int("action_button_min_height")
        border_width = self._size_int("action_button_border_width")
        return (
            "QPushButton {"
            "background-color: rgba(17, 27, 41, 0.94);"
            "color: #DCE6FA;"
            f"border: {border_width}px solid rgba(110, 138, 180, 0.52);"
            f"border-radius: {radius}px;"
            f"padding: {padding_v}px {padding_h}px;"
            "font-weight: 700;"
            f"min-height: {min_height}px;"
            "}"
            "QPushButton:hover {"
            "background-color: rgba(45, 68, 102, 0.96);"
            "border-color: rgba(191, 219, 254, 0.72);"
            "}"
            "QPushButton:disabled {"
            "color: #64748B;"
            "background-color: #1E293B;"
            "border: 1px solid #334155;"
            "}"
        ) + self._font_style_block("QPushButton", size_key)

    def _file_action_button_style(self, size_key: str | None = None) -> str:
        font_size = self._size_int("file_action_button_font_size")
        return (
            self._action_button_style(size_key)
            + "QPushButton {"
            f"font-size: {font_size}px;"
            "font-weight: 700;"
            "}"
        )

    def _disk_status_tooltip(self, row: dict) -> str:
        permission_state = str(row.get("permission_state", "deny") or "deny").strip().lower()
        if permission_state in {"unset", "deny", ""}:
            summary = "当前权限说明：不展开、不扫描、不查询，也不显示内部内容。"
        elif permission_state == "once":
            summary = "当前权限说明：允许按开关展开、扫描、查询；允许基础文件动作。"
        elif permission_state == "allow":
            summary = "当前权限说明：允许按开关展开、扫描、查询；允许完整文件动作。"
        else:
            summary = "当前权限说明：按当前模式和对象权限判断可用动作。"
        return f"权限：点击切换 否 / 受限 / 是\n{summary}"

    def _disk_toggle_tooltip(self, row: dict, field: str, *, state_allows_adjust: bool = True) -> str:
        action_text = {
            "allow_expand": "允许展开：是否允许展开该磁盘根目录",
            "allow_scan": "允许扫描：是否允许扫描并写入缓存",
            "allow_index": "允许查询：是否允许 LLM 或后台查询缓存",
            "file_actions_enabled": "文件动作：是否允许进入文件动作判断",
        }.get(field, "点击切换")
        if not state_allows_adjust:
            action_text = f"{action_text}；当前磁盘状态不允许调整此项"
        return action_text

    def _file_open_tooltip(self, row: dict) -> str:
        base = str(row.get("tooltip", "")).strip()
        if bool(row.get("can_open", False)):
            return base
        reason = str(row.get("open_disabled_reason", "")).strip() or "当前对象暂不允许操作。"
        return f"{base}\n\n当前不可操作：{reason}".strip()

    def _populate_disk_table(self, rows: list[dict], *, selected_disk: str) -> None:
        table = getattr(self.w, "desktop_disk_table", None)
        if table is None:
            return

        scroll_value = table.verticalScrollBar().value()
        font_size = getattr(getattr(self.w, "desktop_controller", None), "runtime", None)
        font_size_key = getattr(font_size, "disk_font_size", "medium")
        table.clearContents()
        table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            is_selected = str(row.get("disk_id", "")) == selected_disk
            button = QPushButton(str(row.get("title", "-")))
            self._apply_widget_font(button, font_size_key)
            button.clicked.connect(lambda _checked=False, disk_id=row["disk_id"]: self.w.desktop_controller.select_disk(disk_id))
            button.setToolTip(str(row.get("tooltip", "")))
            button.setStyleSheet(self._disk_button_style(selected=is_selected, status_color=str(row.get("status_color", "#5B6C8A")), size_key=font_size_key))
            table.setCellWidget(row_index, 0, button)

            status_button = QPushButton(str(row.get("status_text", "-")))
            self._apply_widget_font(status_button, font_size_key)
            status_button.setToolTip(self._disk_status_tooltip(row))
            status_button.setStyleSheet(self._status_badge_style(str(row.get("status_color", "#F5F5F5")), font_size_key))
            status_button.setEnabled(bool(row.get("can_adjust", False)))
            status_button.clicked.connect(lambda _checked=False, disk_id=row["disk_id"]: self.w.desktop_controller.cycle_disk_status(disk_id))
            table.setCellWidget(row_index, 1, status_button)

            for column, field in (
                (2, "allow_expand"),
                (3, "allow_scan"),
                (4, "allow_index"),
                (5, "file_actions_enabled"),
            ):
                permission_state = str(row.get("permission_state", "unset")).strip().lower()
                can_adjust = bool(row.get("can_adjust", False))

                # Host 正式治理：只有 allow / once 可调整
                # VM 测试治理：test 也允许作为 UI 测试开关调整
                state_allows_adjust = permission_state in {"allow", "once", "test"}

                toggle_enabled = can_adjust and state_allows_adjust
                toggle = QPushButton("是" if row.get(field) else "否")
                self._apply_widget_font(toggle, font_size_key)
                toggle.setToolTip(self._disk_toggle_tooltip(row, field, state_allows_adjust=state_allows_adjust))
                toggle.setEnabled(toggle_enabled)
                toggle.setStyleSheet(self._toggle_button_style(bool(row.get(field, False)), interactive=toggle_enabled, size_key=font_size_key))
                toggle.clicked.connect(
                    lambda _checked=False, disk_id=row["disk_id"], key=field, current=bool(row.get(field, False)): (
                        self.w.desktop_controller.toggle_disk_expand(disk_id, not current)
                        if key == "allow_expand"
                        else self.w.desktop_controller.toggle_disk_scan(disk_id, not current)
                        if key == "allow_scan"
                        else self.w.desktop_controller.toggle_disk_file_actions(disk_id)
                        if key == "file_actions_enabled"
                        else self.w.desktop_controller.toggle_disk_index(disk_id, not current)
                    )
                )
                table.setCellWidget(row_index, column, toggle)

            table.setRowHeight(row_index, self._size_int("disk_row_height"))
        table.verticalScrollBar().setValue(min(scroll_value, table.verticalScrollBar().maximum()))

    def _populate_file_table(self, rows: list[dict], *, read_only: bool, file_actions_enabled: bool) -> None:
        table = getattr(self.w, "desktop_file_table", None)
        if table is None:
            return

        runtime = getattr(getattr(self.w, "desktop_controller", None), "runtime", None)
        controller = getattr(self.w, "desktop_controller", None)
        actions_available = bool(controller.desktop_actions_available()) if controller is not None else False
        font_size_key = getattr(runtime, "object_font_size", "medium")
        developer_enabled = self._developer_mode_enabled()
        remembered_v = int(getattr(runtime, "file_table_vertical_scroll_value", table.verticalScrollBar().value()) or 0)
        remembered_h = int(getattr(runtime, "file_table_horizontal_scroll_value", table.horizontalScrollBar().value()) or 0)
        scroll_value = max(remembered_v, table.verticalScrollBar().value())
        h_scroll_value = max(remembered_h, table.horizontalScrollBar().value())
        table.clearContents()
        table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            tooltip = str(row.get("tooltip", ""))
            enabled_box = QCheckBox()
            self._apply_widget_font(enabled_box, font_size_key)
            enabled_box.setChecked(bool(row.get("enabled", False)))
            root_fields = {"project_root", "downloads_root", "documents_root"}
            enabled_box.setEnabled(bool(row.get("can_adjust", False)) and str(row.get("object_key", "")) in root_fields)
            if enabled_box.isEnabled():
                enabled_box.toggled.connect(
                    lambda checked, root_id=row["object_key"]: self.w.desktop_controller.toggle_root_flag(root_id, "enabled", checked)
                )
            enabled_box.setToolTip(tooltip)
            table.setCellWidget(row_index, 0, enabled_box)

            name_label = QLabel(str(row.get("name", "-")))
            self._apply_widget_font(name_label, font_size_key)
            name_label.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
            name_label.setStyleSheet(self._name_cell_style(font_size_key))
            name_label.setToolTip(tooltip)
            table.setCellWidget(row_index, 1, name_label)

            for column, text in (
                (2, str(row.get("path_short", "-"))),
                (5, str(row.get("target_type", "-"))),
            ):
                item = self._make_item(text, align_center=(column == 5))
                item.setToolTip(tooltip)
                table.setItem(row_index, column, item)

            open_label = str(row.get("open_label", "查看"))
            open_button = QPushButton("")
            is_navigation = str(row.get("open_action", "")).strip() == "navigate"
            is_directory = bool(row.get("is_dir", False)) or str(row.get("object_type", "")).strip().lower() == "directory"
            mode = str(row.get("mode", "") or "").strip().lower()
            if mode not in {"disabled", "restricted", "trusted", "test"}:
                mode = ""
            if not mode and controller is not None:
                try:
                    mode = controller._current_mode()
                except Exception:
                    mode = "disabled"
            permission_state = str(
                row.get("effective_permission_state", row.get("permission_state", "unset")) or "unset"
            ).strip().lower()
            real_open_allowed = (
                not read_only
                and bool(row.get("can_open", False))
                and not is_navigation
                and bool(file_actions_enabled)
                and actions_available
                and (
                    (mode == "trusted" and permission_state in {"allow", "once"})
                    or (mode == "test" and permission_state in {"allow", "once", "test"})
                )
            )
            operation_allowed = (
                bool(row.get("can_open", False))
                and (
                    (is_navigation and is_directory)
                    or ((not read_only) and actions_available and real_open_allowed)
                )
            )
            open_button.setEnabled(operation_allowed)
            if not actions_available and not is_navigation:
                open_tooltip = f"{tooltip}\n\n当前模式不允许文件真实动作。"
            elif not is_navigation and bool(row.get("can_open", False)) and not file_actions_enabled:
                open_tooltip = f"{tooltip}\n\n当前不可操作：文件动作已关闭。"
            else:
                open_tooltip = self._file_open_tooltip(row)
            open_button.setToolTip(f"{open_tooltip}\n\n动作：{open_label}".strip())
            open_button.clicked.connect(
                lambda _checked=False, payload=row: self.w.desktop_controller.trigger_file_action(
                    action_kind=str(payload.get("open_action", "inspect")),
                    object_key=str(payload.get("object_key", "")),
                    target_path=str(payload.get("target_path", "")),
                    target_name=str(payload.get("target_name", payload.get("name", "-"))),
                    target_type=str(payload.get("target_type", "对象")),
                    root_id=str(payload.get("root_id", "")),
                    relative_path=str(payload.get("relative_path", "")),
                    permission_state=str(payload.get("permission_state", "unset")),
                    effective_permission_state=str(payload.get("effective_permission_state", payload.get("permission_state", "unset"))),
                    permission_source_type=str(payload.get("permission_source_type", "")),
                    permission_source_key=str(payload.get("permission_source_key", "")),
                    request_allowed=bool(payload.get("request_allowed", payload.get("can_open", False))),
                    apply_ui_allowed=bool(payload.get("apply_ui_allowed", False)),
                    file_actions_enabled=bool(file_actions_enabled),
                )
            )
            self._apply_widget_font(open_button, font_size_key)
            self._make_icon_only_button(
                open_button,
                "desktop.forward_icon",
                "desktop_table_button_icon_size",
                open_label,
                button_size_key="desktop_table_icon_button_size",
            )
            open_button.setStyleSheet(self._file_action_button_style(font_size_key))

            # ===== 打开列：只放打开 / 进入下一级按钮 =====
            open_widget = QWidget()
            open_layout = QHBoxLayout(open_widget)
            open_layout.setContentsMargins(0, 0, 0, 0)
            open_layout.setSpacing(0)
            open_layout.addStretch()
            open_layout.addWidget(open_button)
            open_layout.addStretch()
            table.setCellWidget(row_index, 3, open_widget)

            # ===== 管理列：只在开发者模式显示重命名 / 删除，不显示关闭 =====
            row_source = str(row.get("source", "") or "").strip().lower()

            rename_allowed = bool(
                developer_enabled
                and not read_only
                and mode == "trusted"
                and bool(file_actions_enabled)
                and permission_state in {"allow", "once"}
                and row_source in {"host_cache", "host_scan"}
                and str(row.get("target_path", "") or "").strip()
            )

            delete_allowed = bool(
                developer_enabled
                and not read_only
                and mode == "trusted"
                and bool(file_actions_enabled)
                and permission_state == "allow"
                and row_source in {"host_cache", "host_scan"}
                and str(row.get("target_path", "") or "").strip()
            )

            manage_widget = QWidget()
            manage_layout = QHBoxLayout(manage_widget)
            manage_layout.setContentsMargins(0, 0, 0, 0)
            manage_layout.setSpacing(self._size_int("file_manage_button_spacing"))

            icon_button_w = self._size_int("file_manage_button_width")
            icon_button_h = self._size_int("file_manage_button_height")
            icon_size = self._size_int("file_manage_icon_size")

            rename_button = QPushButton("")
            rename_button.setIcon(QIcon(self._asset_path("desktop.rename_icon")))
            rename_button.setIconSize(QSize(icon_size, icon_size))
            rename_button.setFixedSize(icon_button_w, icon_button_h)
            self._apply_widget_font(rename_button, font_size_key)
            rename_button.setEnabled(rename_allowed)
            rename_button.setToolTip(
                "重命名文件或文件夹。受限 / 是 权限可用。"
                if rename_allowed
                else "当前对象不可重命名。"
            )
            rename_button.setStyleSheet(self._file_action_button_style(font_size_key))
            rename_button.clicked.connect(
                lambda _checked=False, payload=row: self.w.desktop_controller.rename_host_file_object(payload)
            )
            manage_layout.addWidget(rename_button)

            delete_button = QPushButton("")
            delete_button.setIcon(QIcon(self._asset_path("desktop.delete_icon")))
            delete_button.setIconSize(QSize(icon_size, icon_size))
            delete_button.setFixedSize(icon_button_w, icon_button_h)
            self._apply_widget_font(delete_button, font_size_key)
            delete_button.setEnabled(delete_allowed)
            delete_button.setToolTip(
                "移动到少府隔离区，可通过少府材料恢复。"
                if delete_allowed
                else "当前对象不可删除：需要信任模式、文件动作开启、权限为“是”。"
            )
            delete_button.setStyleSheet(self._file_action_button_style(font_size_key))
            delete_button.clicked.connect(
                lambda _checked=False, payload=row: self.w.desktop_controller.delete_host_file_object(payload)
            )
            manage_layout.addWidget(delete_button)
            table.setCellWidget(row_index, 4, manage_widget)

            status_label = QLabel(str(row.get("status_text", "-")))
            self._apply_widget_font(status_label, font_size_key)
            status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            status_label.setStyleSheet(self._status_badge_style(str(row.get("status_color", "#F5F5F5")), font_size_key))
            status_label.setToolTip(tooltip)
            table.setCellWidget(row_index, 6, status_label)

            permission_button = QPushButton(str(row.get("permission_text", "否")))
            self._apply_widget_font(permission_button, font_size_key)
            permission_button.setStyleSheet(self._permission_button_style(font_size_key))
            permission_button.setEnabled(not read_only and bool(row.get("can_adjust", False)))
            permission_button.setToolTip(tooltip)
            permission_button.clicked.connect(
                lambda _checked=False,
                object_key=row["object_key"],
                current=str(row.get("effective_permission_state", row.get("permission_state", "unset"))): (
                    self.w.desktop_controller.cycle_file_permission(object_key, current)
                )
            )
            table.setCellWidget(row_index, 7, permission_button)
            table.setRowHeight(row_index, self._size_int("file_row_height"))
            
        table.verticalScrollBar().setValue(min(scroll_value, table.verticalScrollBar().maximum()))
        table.horizontalScrollBar().setValue(min(h_scroll_value, table.horizontalScrollBar().maximum()))
        if runtime is not None:
            runtime.file_table_vertical_scroll_value = int(table.verticalScrollBar().value())
            runtime.file_table_horizontal_scroll_value = int(table.horizontalScrollBar().value())

    def _populate_apps_table(self, rows: list[dict], *, read_only: bool) -> None:
        self.software_panel_loader.populate_apps_table_batched(rows, read_only=read_only)

    def apply_responsive_layout(self) -> None:
        disk_table = getattr(self.w, "desktop_disk_table", None)
        file_table = getattr(self.w, "desktop_file_table", None)
        apps_table = getattr(self.w, "desktop_apps_table", None)
        readonly_display = getattr(self.w, "desktop_readonly_result_display", None)
        sandbox_display = getattr(self.w, "desktop_sandbox_result_display", None)
        preset_name, preset = self._resolve_layout_preset()
        setattr(self.w, "desktop_current_layout_preset", preset_name)
        editable = self._is_file_governance_editable()

        # ===== 磁盘表列宽 =====
        if disk_table is not None:
            disk_table.setMinimumHeight(self._size_int("disk_table_min_height"))
            disk_table.setStyleSheet(self._file_table_style(editable, preset))

            bool_w = self._preset_int(preset, "disk_column_width_bool")
            bool_total = bool_w * 4
            name_min = self._preset_int(preset, "disk_name_min", self._size_int("disk_column_width_name"))
            status_min = self._preset_int(preset, "disk_status_min", self._size_int("disk_column_width_status"))
            table_width = self._table_view_width(disk_table)
            if table_width <= 0:
                table_width = bool_total + name_min + status_min
            remain = max(0, table_width - bool_total)
            name_w = max(name_min, int(remain * 0.40))
            status_w = max(status_min, remain - name_w)

            self._set_table_column_widths(
                disk_table,
                {
                    0: name_w,
                    1: status_w,
                    2: bool_w,
                    3: bool_w,
                    4: bool_w,
                    5: bool_w,
                },
            )
            self._apply_table_row_height(disk_table, self._preset_int(preset, "disk_row_height"))

        # ===== 文件对象表列宽 =====
        if file_table is not None:
            file_table.setMinimumHeight(self._size_int("file_table_min_height"))
            file_table.setStyleSheet(self._file_table_style(editable, preset))

            developer_enabled = self._developer_mode_enabled()

            enabled_w = self._preset_int(preset, "file_column_width_enabled")
            open_w = self._preset_int(preset, "file_column_width_open")
            manage_w = self._preset_int(preset, "file_column_width_manage")
            type_w = self._preset_int(preset, "file_column_width_type")
            status_w = self._preset_int(preset, "file_column_width_status")
            permission_w = self._preset_int(preset, "file_column_width_permission")

            fixed_total = enabled_w + open_w + type_w + status_w + permission_w
            if developer_enabled:
                fixed_total += manage_w

            name_min = self._preset_int(preset, "file_name_min", self._size_int("file_column_width_name"))
            path_min = self._preset_int(preset, "file_path_min", self._size_int("file_column_width_path"))
            table_width = self._table_view_width(file_table)

            if table_width <= 0:
                table_width = fixed_total + name_min + path_min

            remain = max(0, table_width - fixed_total)
            name_w = max(name_min, int(remain * 0.35))
            path_w = max(path_min, remain - name_w)

            self._set_table_column_widths(
                file_table,
                {
                    0: enabled_w,
                    1: name_w,
                    2: path_w,
                    3: open_w,
                    4: manage_w,
                    5: type_w,
                    6: status_w,
                    7: permission_w,
                },
            )
            file_table.setColumnHidden(4, not developer_enabled)
            self._apply_table_row_height(file_table, self._preset_int(preset, "file_row_height"))
        # ===== 其他区块高度也可以顺手接配置 =====
        if apps_table is not None:
            apps_table.setMinimumHeight(self._size_int("software_table_min_height"))
            icon_w = self._size_int("software_column_width_icon")
            name_w = self._size_int("software_column_width_name")
            permission_w = self._size_int("software_column_width_permission")
            runtime = getattr(getattr(self.w, "desktop_controller", None), "runtime", None)
            software_font_size = getattr(runtime, "software_font_size", "medium")
            action_button_width, _action_button_height = self._software_action_button_size(software_font_size)
            action_spacing = self._size_int("software_action_button_spacing")
            actions_min = action_button_width * 7 + action_spacing * 6 + 12
            actions_w = max(self._size_int("software_column_width_actions"), actions_min)
            status_w = self._size_int("software_column_width_status")
            clear_w = self._size_int("software_column_width_clear")
            fixed_total = icon_w + name_w + permission_w + actions_w + status_w + clear_w
            path_min = self._size_int("software_path_min_width")
            table_width = self._table_view_width(apps_table)
            path_w = max(path_min, table_width - fixed_total)
            self._set_table_column_widths(
                apps_table,
                {
                    0: icon_w,
                    1: name_w,
                    2: permission_w,
                    3: actions_w,
                    4: path_w,
                    5: status_w,
                    6: clear_w,
                },
            )
            self._apply_table_row_height(apps_table, self._size_int("software_row_height"))
        if readonly_display is not None:
            readonly_display.setMinimumHeight(self._size_int("readonly_result_min_height"))
        if sandbox_display is not None:
            sandbox_display.setMinimumHeight(self._size_int("sandbox_result_min_height"))
        refresh_size_badges(self.w)
