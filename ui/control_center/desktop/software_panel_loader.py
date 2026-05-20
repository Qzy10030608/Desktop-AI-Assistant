from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QHBoxLayout, QLabel, QMessageBox, QPushButton, QTableWidgetItem, QWidget


class SoftwarePanelLoader:
    def __init__(self, page_loader) -> None:
        self.page_loader = page_loader
        self.w = page_loader.w

        self._pending_app_rows: list[dict] = []
        self._pending_app_read_only = True
        self._pending_app_row_index = 0

        self._pending_icon_rows: list[tuple[int, dict]] = []
        self._icon_font_size_key = "medium"

    def load_panel_summary(self, software_state: dict, page_state: dict) -> None:
        self.page_loader._set_text(
            "desktop_software_discovered_label",
            f"已发现软件数量：{software_state.get('discovered_count', 0)}",
        )
        self.page_loader._set_text(
            "desktop_software_confirmed_label",
            f"已信任软件数量：{software_state.get('trusted_count', software_state.get('confirmed_count', 0))}",
        )
        self.page_loader._set_text(
            "desktop_software_hidden_label",
            f"已隐藏对象数量：{software_state.get('hidden_count', 0)}",
        )
        self.page_loader._set_software_scan_status()
        self.page_loader._set_visible("desktop_software_card", page_state["mode"] in {"trusted", "test"})
        self.page_loader._set_software_toolbar_state(page_state)
        self.page_loader._apply_software_visual_state(page_state)

        source = str(software_state.get("source", "empty") or "empty").strip().lower()
        source_label = {
            "empty": "empty：尚未扫描",
            "memory": "memory：上次记录",
            "cache": "cache：缓存记录",
            "scanning": "scanning：扫描中",
        }.get(source, source)
        self.page_loader._set_text("desktop_software_scan_stats_label", f"当前来源：{source_label}")

        table = getattr(self.w, "desktop_apps_table", None)
        if table is None:
            return

        self._pending_icon_rows = []
        self._pending_app_rows = []
        self._pending_app_row_index = 0

        try:
            table.clearSpans()
        except Exception:
            pass

        table.clearContents()
        table.setRowCount(1)

        message = "尚未加载软件列表。请点击“加载上次记录”，或点击扫描按钮重新扫描。"
        item = QTableWidgetItem(message)
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        table.setItem(0, 0, item)

        try:
            table.setSpan(0, 0, 1, max(1, table.columnCount()))
        except Exception:
            pass

    def refresh_panel_chrome(self, software_state: dict, page_state: dict) -> None:
        self.page_loader._set_text(
            "desktop_software_discovered_label",
            f"已发现软件数量：{software_state.get('discovered_count', 0)}",
        )
        self.page_loader._set_text(
            "desktop_software_confirmed_label",
            f"已信任软件数量：{software_state.get('trusted_count', software_state.get('confirmed_count', 0))}",
        )
        self.page_loader._set_text(
            "desktop_software_hidden_label",
            f"已隐藏对象数量：{software_state.get('hidden_count', 0)}",
        )
        self.page_loader._set_software_scan_status()
        self.page_loader._set_visible("desktop_software_card", page_state["mode"] in {"trusted", "test"})
        self.page_loader._set_software_toolbar_state(page_state)
        self.page_loader._apply_software_visual_state(page_state)

        source = str(software_state.get("source", "empty") or "empty").strip().lower()
        self.page_loader._set_text("desktop_software_scan_stats_label", f"当前来源：{source}")

    def load_panel(self, software_state: dict, page_state: dict) -> None:
        self.refresh_panel_chrome(software_state, page_state)
        self.populate_apps_table_batched(
            software_state.get("rows", []),
            read_only=bool(software_state.get("read_only", True)),
        )

    def populate_apps_table(self, rows: list[dict], *, read_only: bool) -> None:
        self.populate_apps_table_batched(rows, read_only=read_only)

    def _tag_app_button(
        self,
        button: QPushButton,
        *,
        app_id: str,
        role: str,
        flag: str = "",
        action_kind: str = "",
        requires_backend: bool = False,
    ) -> None:
        """
        给软件区按钮打运行态标记。

        用途：
        - 只读 / 可调整切换时，只更新已有按钮 enabled 状态
        - 不重新渲染软件表
        - 不重新读取缓存
        - 不重新扫描
        """
        button.setProperty("desktop_app_id", str(app_id or ""))
        button.setProperty("desktop_app_button_role", str(role or ""))
        button.setProperty("desktop_app_action_flag", str(flag or ""))
        button.setProperty("desktop_app_action_kind", str(action_kind or ""))
        button.setProperty("desktop_app_requires_backend", bool(requires_backend))

    def _permission_tooltip(self, row: dict) -> str:
        state = str(
            row.get("effective_permission_state", row.get("permission_state", "deny"))
            or "deny"
        ).strip().lower()
        if state in {"unset", "deny", ""}:
            summary = "当前权限说明：所有软件动作禁用。"
        elif state == "once":
            summary = "当前权限说明：允许定位、启动、关闭操作；卸载、迁移、更新不可执行。"
        elif state in {"allow", "test"}:
            summary = "当前权限说明：允许定位、启动、关闭、卸载、迁移、更新操作。"
        else:
            summary = "当前权限说明：按当前模式和对象权限判断可用动作。"
        return f"权限：点击切换 否 / 受限 / 是\n{summary}"

    def _is_vm_test_row(self, row: dict) -> bool:
        permission_state = str(
            row.get("permission_state", row.get("effective_permission_state", ""))
            or ""
        ).strip().lower()
        platform = str(row.get("platform", "") or "").strip().lower()
        return permission_state == "test" or platform == "vm"

    def _current_execution_backend(self) -> str:
        controller = getattr(self.w, "desktop_controller", None)
        if controller is None:
            return ""
        try:
            if hasattr(controller, "software_action_backend"):
                return str(controller.software_action_backend() or "").strip().lower()
            return str(controller.effective_execution_backend() or "").strip().lower()
        except Exception:
            return ""

    def _row_permission_open(self, row: dict) -> bool:
        state = str(
            row.get("effective_permission_state", row.get("permission_state", "deny"))
            or "deny"
        ).strip().lower()
        return state in {"allow", "once", "test"}

    def _resolve_app_action_enabled(
        self,
        row: dict,
        *,
        read_only: bool,
        flag: str,
        action_kind: str = "",
    ) -> bool:
        action = str(action_kind or "").strip().lower()

        controller = getattr(self.w, "desktop_controller", None)
        backend = ""
        if controller is not None and hasattr(controller, "software_action_backend"):
            backend = str(controller.software_action_backend(row) or "").strip().lower()
        elif controller is not None:
            backend = str(controller.effective_execution_backend() or "").strip().lower()

        permission_state = str(
            row.get("effective_permission_state", row.get("permission_state", "deny"))
            or "deny"
        ).strip().lower()

        low_risk_actions = {
            "app.locate",
            "app.launch",
            "app.close",
        }

        high_risk_actions = {
            "app.uninstall",
            "app.relocate",
            "app.move",
            "app.update",
        }

        all_app_actions = low_risk_actions | high_risk_actions

        if action not in all_app_actions:
            return False

        # VM test 行：VM 测试已经完成，现在按软件区统一规则开放。
        # VM row 通常 permission_state == "test"，这里把 test 视为“可真实测试”。
        if self._is_vm_test_row(row):
            if backend != "vm":
                return False

            if permission_state in {"deny", "unset", ""}:
                return False

            if permission_state == "once":
                return action in low_risk_actions

            if permission_state in {"allow", "test"}:
                return action in all_app_actions

            return False

        # Host / sandbox 普通行
        if read_only:
            return False

        if backend not in {"host", "sandbox"}:
            return False

        if permission_state in {"deny", "unset", ""}:
            return False

        # Host 真实关闭需要基本关闭线索。
        # 否则按钮虽然能点，但 HostWindowsAdapter 会返回 Missing process_name or process_names。
        if backend == "host" and action == "app.close":
            process_name = str(row.get("process_name", "") or "").strip()
            process_names = row.get("process_names", [])
            has_process_names = (
                isinstance(process_names, list)
                and any(str(item or "").strip() for item in process_names)
            )

            target_path = str(
                row.get("effective_target_path", row.get("target_path", ""))
                or ""
            ).strip().lower()
            launch_raw = str(
                row.get("effective_launch_target_raw", row.get("launch_target_raw", ""))
                or ""
            ).strip().lower()

            has_exe_target = target_path.endswith(".exe") or launch_raw.endswith(".exe")

            if not process_name and not has_process_names and not has_exe_target:
                return False

        if permission_state == "once":
            return action in low_risk_actions

        if permission_state == "allow":
            return action in all_app_actions

        return False

    def refresh_apps_table_interactive_state(
        self,
        *,
        software_state: dict | None = None,
        page_state: dict | None = None,
    ) -> None:
        """
        只刷新软件表中已有按钮的可点击状态。

        注意：
        - 不能 clearContents()
        - 不能 setRowCount()
        - 不能 populate_apps_table_batched()
        - 不能重新读取 software_view_cache
        - 不能重新 merge / scan
        """
        table = getattr(self.w, "desktop_apps_table", None)
        controller = getattr(self.w, "desktop_controller", None)
        runtime = getattr(controller, "runtime", None) if controller is not None else None

        if table is None or controller is None:
            return

        if not isinstance(software_state, dict):
            software_state = getattr(runtime, "software_last_state", None) if runtime is not None else None

        if not isinstance(software_state, dict):
            return

        raw_rows = software_state.get("rows", [])
        if not isinstance(raw_rows, list):
            return

        rows_by_app_id: dict[str, dict] = {}
        for item in raw_rows:
            if not isinstance(item, dict):
                continue
            app_id = str(item.get("app_id", "") or "").strip()
            if app_id:
                rows_by_app_id[app_id] = item

        if page_state is not None:
            read_only = bool(page_state.get("apps_read_only", True))
        else:
            read_only = not bool(getattr(runtime, "apps_editable", False)) if runtime is not None else True

        try:
            table.setUpdatesEnabled(False)

            for row_index in range(table.rowCount()):
                widgets: list[QPushButton] = []

                permission_widget = table.cellWidget(row_index, 2)
                if isinstance(permission_widget, QPushButton):
                    widgets.append(permission_widget)

                actions_widget = table.cellWidget(row_index, 3)
                if actions_widget is not None:
                    widgets.extend(actions_widget.findChildren(QPushButton))

                clear_widget = table.cellWidget(row_index, 6)
                if isinstance(clear_widget, QPushButton):
                    widgets.append(clear_widget)

                for widget in widgets:
                    app_id = str(widget.property("desktop_app_id") or "").strip()
                    if not app_id:
                        continue

                    row = rows_by_app_id.get(app_id)
                    if not isinstance(row, dict):
                        continue

                    role = str(widget.property("desktop_app_button_role") or "").strip()
                    flag = str(widget.property("desktop_app_action_flag") or "").strip()

                    if role == "permission":
                        enabled = (not read_only) and bool(row.get("can_adjust", False))
                    elif role == "bind_path":
                        enabled = (not read_only) and bool(row.get("can_bind_path", False))
                    elif role == "clear":
                        enabled = (not read_only) and bool(row.get("can_clear", True))
                    elif role == "action":
                        action_kind = str(widget.property("desktop_app_action_kind") or "").strip()
                        enabled = self._resolve_app_action_enabled(
                            row,
                            read_only=read_only,
                            flag=flag,
                            action_kind=action_kind,
                        )
                    else:
                        continue

                    widget.setEnabled(bool(enabled))

        finally:
            table.setUpdatesEnabled(True)

    def refresh_one_app_row(self, *, app_id: str, row: dict) -> None:
        """
        只刷新一个软件行的权限显示和按钮状态。
        不清空表格，不重建 rows。
        """
        table = getattr(self.w, "desktop_apps_table", None)
        controller = getattr(self.w, "desktop_controller", None)
        if table is None or controller is None:
            return

        normalized_app_id = str(app_id or "").strip()
        if not normalized_app_id:
            return

        runtime = getattr(controller, "runtime", None)
        read_only = not bool(getattr(runtime, "apps_editable", False)) if runtime is not None else True
        font_size_key = getattr(runtime, "software_font_size", "medium") if runtime is not None else "medium"

        try:
            table.setUpdatesEnabled(False)

            for row_index in range(table.rowCount()):
                permission_widget = table.cellWidget(row_index, 2)
                if not isinstance(permission_widget, QPushButton):
                    continue

                current_app_id = str(permission_widget.property("desktop_app_id") or "").strip()
                if current_app_id != normalized_app_id:
                    continue

                permission_widget.setText(
                    str(row.get("permission_label", row.get("permission_text", "否")) or "否")
                )
                permission_widget.setStyleSheet(
                    self.page_loader._status_badge_style(
                        str(row.get("permission_color", "#EF4444")),
                        font_size_key,
                    )
                )
                permission_widget.setEnabled((not read_only) and bool(row.get("can_adjust", False)))
                permission_widget.setToolTip(self._permission_tooltip(row))

                actions_widget = table.cellWidget(row_index, 3)
                if actions_widget is not None:
                    for button in actions_widget.findChildren(QPushButton):
                        role = str(button.property("desktop_app_button_role") or "").strip()
                        if role != "action":
                            continue
                        flag = str(button.property("desktop_app_action_flag") or "").strip()
                        action_kind = str(button.property("desktop_app_action_kind") or "").strip()
                        button.setEnabled(
                            self._resolve_app_action_enabled(
                                row,
                                read_only=read_only,
                                flag=flag,
                                action_kind=action_kind,
                            )
                        )

                clear_widget = table.cellWidget(row_index, 6)
                if isinstance(clear_widget, QPushButton):
                    clear_widget.setEnabled((not read_only) and bool(row.get("can_clear", True)))

                status_widget = table.cellWidget(row_index, 5)
                if isinstance(status_widget, QLabel):
                    status_widget.setText(str(row.get("status_badge", row.get("status_text", "-"))))
                    status_widget.setStyleSheet(
                        self.page_loader._status_badge_style(
                            str(row.get("status_color", "#F5F5F5")),
                            font_size_key,
                        )
                    )
                    status_widget.setToolTip(str(row.get("status_tooltip", row.get("tooltip", ""))).strip())

                break

        finally:
            table.setUpdatesEnabled(True)

    def remove_app_row(self, app_id: str) -> bool:
        """
        只从当前 QTableWidget 删除一个显示行。
        不清空表格，不重建全表。
        """
        table = getattr(self.w, "desktop_apps_table", None)
        if table is None:
            return False

        normalized = str(app_id or "").strip()
        if not normalized:
            return False

        for row_index in range(table.rowCount()):
            widgets_to_check = []
            permission_widget = table.cellWidget(row_index, 2)
            if permission_widget is not None:
                widgets_to_check.append(permission_widget)
            actions_widget = table.cellWidget(row_index, 3)
            if actions_widget is not None:
                widgets_to_check.extend(actions_widget.findChildren(QPushButton))
            clear_widget = table.cellWidget(row_index, 6)
            if clear_widget is not None:
                widgets_to_check.append(clear_widget)

            for widget in widgets_to_check:
                current = str(widget.property("desktop_app_id") or "").strip()
                if current == normalized:
                    table.removeRow(row_index)
                    return True

        return False

    def _build_default_icon_widget(self, row: dict, tooltip: str, font_size_key: str) -> QLabel:
        label = QLabel(str(row.get("icon_text", "APP")))
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setToolTip(tooltip)
        self.page_loader._apply_widget_font(label, font_size_key)
        label.setStyleSheet(
            "QLabel {"
            "color: #B8C7E0;"
            "background-color: rgba(17, 26, 40, 0.72);"
            "border: 1px solid rgba(110, 138, 180, 0.20);"
            "border-radius: 6px;"
            "padding: 4px 6px;"
            "font-weight: 700;"
            "}"
        )
        return label

    def _schedule_icon_batches(self, rows: list[dict], font_size_key: str) -> None:
        """
        表格先显示默认图标，再分批替换真实图标。
        避免一次性读取 100+ 个 exe / lnk 图标导致 UI 假死。
        """
        self._pending_icon_rows = list(enumerate(rows or []))
        self._icon_font_size_key = font_size_key
        QTimer.singleShot(20, self._load_next_icon_batch)

    def _load_next_icon_batch(self) -> None:
        table = getattr(self.w, "desktop_apps_table", None)
        if table is None:
            return

        pending = getattr(self, "_pending_icon_rows", [])
        if not pending:
            return

        batch = pending[:6]
        self._pending_icon_rows = pending[6:]

        presenter = getattr(self.page_loader, "software_icon_presenter", None)
        if presenter is None:
            return

        font_size_key = getattr(self, "_icon_font_size_key", "medium")

        for row_index, row in batch:
            if row_index >= table.rowCount():
                continue

            tooltip = str(row.get("tooltip", "") or "").strip()

            try:
                widget = presenter.build_icon_widget(row, tooltip, font_size_key)
                table.setCellWidget(row_index, 0, widget)
            except Exception:
                # 失败时保留默认占位图标
                continue

        if self._pending_icon_rows:
            QTimer.singleShot(20, self._load_next_icon_batch)

    def _latest_app_row(self, row: dict) -> dict:
        """
        点击按钮时重新读取 runtime 中的最新 row，避免按钮 lambda 捕获旧权限状态。
        """
        app_id = str(row.get("app_id", "") or "").strip()
        if not app_id:
            return row

        controller = getattr(self.w, "desktop_controller", None)
        if controller is None:
            return row

        finder = getattr(controller, "_find_runtime_software_row", None)
        if not callable(finder):
            return row

        latest = finder(app_id)
        if isinstance(latest, dict):
            merged = dict(row)
            merged.update(latest)
            return merged

        return row
    
    def _trigger_app_action(self, row: dict, action_kind: str) -> None:
        row = self._latest_app_row(row)
        self.w.desktop_controller.trigger_app_sandbox_action(
            row=row,
            app_id=str(row.get("app_id", "")),
            action_kind=action_kind,
            title=str(row.get("title", "-")),
            target_path=str(row.get("effective_target_path", row.get("target_path", ""))),
            permission_state=str(row.get("permission_state", "deny")),
            launch_target_kind=str(
                row.get("effective_launch_target_kind", row.get("launch_target_kind", "missing"))
            ),
            launch_target_raw=str(
                row.get("effective_launch_target_raw", row.get("launch_target_raw", ""))
            ),
            shell_entry=str(row.get("shell_entry", "")),
            locate_entry=str(row.get("locate_entry", "")),
            platform=str(row.get("platform", "unknown")),
            platform_object_id=str(row.get("platform_object_id", "")),
            platform_object_type=str(row.get("platform_object_type", "")),
            entry_path=str(row.get("entry_path", "")),
            install_dir=str(row.get("install_dir", "")),
            uninstall_string=str(row.get("uninstall_string", "")),
            quiet_uninstall_string=str(row.get("quiet_uninstall_string", "")),
            updater_path=str(row.get("updater_path", "")),
            winget_id=str(row.get("winget_id", "")),
            update_source_dir=str(row.get("update_source_dir", "")),
            process_name=str(row.get("process_name", "")),
            process_names=row.get("process_names", []),
            publisher=str(row.get("publisher", "")),
            version=str(row.get("version", "")),
            source=str(row.get("source", "")),
            category=str(row.get("category", "")),
            candidate_kind=str(row.get("candidate_kind", "")),
            path_status=str(row.get("path_status", "")),
            route_confidence=str(row.get("route_confidence", "low")),
        )

    def _trigger_dangerous_app_action(self, row: dict, action_kind: str) -> None:
        row = self._latest_app_row(row)
        controller = getattr(self.w, "desktop_controller", None)
        runtime = getattr(controller, "runtime", None) if controller is not None else None

        if controller is not None and hasattr(controller, "software_action_backend"):
            backend = str(controller.software_action_backend(row) or "").strip().lower()
        elif controller is not None:
            backend = str(controller.effective_execution_backend() or "").strip().lower()
        else:
            backend = ""

        if backend not in {"host", "vm", "sandbox"}:
            QMessageBox.warning(
                self.w,
                "软件动作不可用",
                "当前模式没有可用的执行出口，请切换到信任模式或测试模式。",
            )
            return

        confirmed = False
        dest_root = ""
        dest_path = ""
        move_mode = ""
        relocate_strategy = ""
        relocate_target_mode = ""
        path_namespace = "vm_windows" if backend == "vm" else ("host_windows" if backend == "host" else "sandbox")
        source_path = str(
            row.get("install_dir", "")
            or row.get("effective_target_path", row.get("target_path", ""))
            or ""
        ).strip()

        if action_kind in {"app.move", "app.relocate"}:
            move_mode = "installed_app_relocate"
            relocate_strategy = "move_update_paths"
            relocate_target_mode = "vm_folder_dialog"
            path_namespace = "vm_windows" if backend == "vm" else ("host_windows" if backend == "host" else "sandbox")

        if backend in {"vm", "host"}:
            if backend == "vm" and action_kind in {"app.move", "app.relocate"}:
                health = getattr(runtime, "vm_health_result", {}) if runtime is not None else {}
                health_data = (
                    health.get("data", {})
                    if isinstance(health, dict) and isinstance(health.get("data"), dict)
                    else {}
                )
                feature_flags = (
                    health_data.get("feature_flags", {})
                    if isinstance(health_data.get("feature_flags"), dict)
                    else {}
                )
                if not (
                    bool(feature_flags.get("installed_app_relocate", False))
                    and bool(feature_flags.get("vm_folder_dialog", False))
                ):
                    QMessageBox.warning(
                        self.w,
                        "VM 软件迁移",
                        "当前 VM Agent 尚未声明 installed_app_relocate / vm_folder_dialog 能力，请先更新并重启 VM Agent。",
                    )
                    return

            if QMessageBox.question(
                self.w,
                "确认真实执行",
                self._dangerous_confirm_text(row, action_kind, source_path=source_path, dest_path=dest_path),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            ) != QMessageBox.StandardButton.Yes:
                return

            confirmed = True

        self.w.desktop_controller.trigger_app_sandbox_action(
            row=row,
            app_id=str(row.get("app_id", "")),
            action_kind=action_kind,
            title=str(row.get("title", "-")),
            target_path=str(row.get("effective_target_path", row.get("target_path", ""))),
            permission_state=str(row.get("permission_state", "deny")),
            launch_target_kind=str(
                row.get("effective_launch_target_kind", row.get("launch_target_kind", "missing"))
            ),
            launch_target_raw=str(
                row.get("effective_launch_target_raw", row.get("launch_target_raw", ""))
            ),
            shell_entry=str(row.get("shell_entry", "")),
            locate_entry=str(row.get("locate_entry", "")),
            platform=str(row.get("platform", "unknown")),
            platform_object_id=str(row.get("platform_object_id", "")),
            platform_object_type=str(row.get("platform_object_type", "")),
            entry_path=str(row.get("entry_path", "")),
            install_dir=str(row.get("install_dir", "")),
            uninstall_string=str(row.get("uninstall_string", "")),
            quiet_uninstall_string=str(row.get("quiet_uninstall_string", "")),
            updater_path=str(row.get("updater_path", "")),
            winget_id=str(row.get("winget_id", "")),
            update_source_dir=str(row.get("update_source_dir", "")),
            process_name=str(row.get("process_name", "")),
            process_names=row.get("process_names", []),
            publisher=str(row.get("publisher", "")),
            version=str(row.get("version", "")),
            source=str(row.get("source", "")),
            category=str(row.get("category", "")),
            candidate_kind=str(row.get("candidate_kind", "")),
            path_status=str(row.get("path_status", "")),
            route_confidence=str(row.get("route_confidence", "low")),
            confirmed=confirmed,
            source_path=source_path,
            dest_root=dest_root,
            dest_path=dest_path,
            move_mode=move_mode,
            relocate_strategy=relocate_strategy,
            relocate_target_mode=relocate_target_mode,
            path_namespace=path_namespace,
        )

    def _dangerous_confirm_text(
        self,
        row: dict,
        action_kind: str,
        *,
        source_path: str = "",
        dest_path: str = "",
    ) -> str:
        title = str(row.get("title", "-") or "-")
        install_dir = str(row.get("install_dir", "") or "").strip()

        if action_kind == "app.uninstall":
            action_text = "卸载"
        elif action_kind in {"app.move", "app.relocate"}:
            action_text = "迁移"
        else:
            action_text = "更新"

        return "\n".join(
            [
                f"即将在当前执行环境中真实执行软件{action_text}。",
                f"对象：{title}",
                f"安装目录：{install_dir or '-'}",
            ]
        )

    def populate_apps_table_batched(self, rows: list[dict], *, read_only: bool) -> None:
        """
        分批渲染软件表。

        注意：
        - 这个函数是完整渲染入口
        - 只允许在加载缓存、扫描完成后使用
        - 只读/可调整切换不能调用它
        """
        table = getattr(self.w, "desktop_apps_table", None)
        if table is None:
            return

        runtime = getattr(getattr(self.w, "desktop_controller", None), "runtime", None)

        self._pending_app_rows = list(rows or [])
        self._pending_app_read_only = bool(read_only)
        self._pending_app_row_index = 0

        # 停止上一轮图标分批加载，避免旧图标写进新表格
        self._pending_icon_rows = []

        if runtime is not None:
            runtime.software_table_rendering = True

        try:
            table.clearSpans()
        except Exception:
            pass

        table.setUpdatesEnabled(False)
        try:
            table.clearContents()
            table.setRowCount(0)
        finally:
            table.setUpdatesEnabled(True)

        QTimer.singleShot(0, self._append_next_app_rows_batch)

    def _append_next_app_rows_batch(self) -> None:
        table = getattr(self.w, "desktop_apps_table", None)
        if table is None:
            return

        rows = getattr(self, "_pending_app_rows", [])
        start = int(getattr(self, "_pending_app_row_index", 0) or 0)
        read_only = bool(getattr(self, "_pending_app_read_only", True))

        runtime = getattr(getattr(self.w, "desktop_controller", None), "runtime", None)
        controller = getattr(self.w, "desktop_controller", None)

        if start >= len(rows):
            if runtime is not None:
                runtime.software_table_rendering = False

            font_size_key = getattr(runtime, "software_font_size", "medium")
            self._schedule_icon_batches(rows, font_size_key)

            try:
                if runtime is not None:
                    table.verticalScrollBar().setValue(
                        min(
                            int(getattr(runtime, "software_table_scroll_value", 0) or 0),
                            table.verticalScrollBar().maximum(),
                        )
                    )
                    table.horizontalScrollBar().setValue(
                        min(
                            int(getattr(runtime, "software_table_horizontal_scroll_value", 0) or 0),
                            table.horizontalScrollBar().maximum(),
                        )
                    )
            except Exception:
                pass

            QTimer.singleShot(0, self.page_loader._restore_desktop_page_scroll)
            return

        font_size_key = getattr(runtime, "software_font_size", "medium")
        action_button_width, action_button_height = self.page_loader._software_action_button_size(font_size_key)
        actions_available = bool(controller.desktop_actions_available()) if controller is not None else False

        batch_size = 8
        end = min(start + batch_size, len(rows))

        table.setUpdatesEnabled(False)
        try:
            for row_index in range(start, end):
                table.insertRow(row_index)
                self._populate_app_row(
                    row_index,
                    rows[row_index],
                    read_only=read_only,
                    font_size_key=font_size_key,
                    actions_available=actions_available,
                    action_button_width=action_button_width,
                    action_button_height=action_button_height,
                )
        finally:
            table.setUpdatesEnabled(True)

        self._pending_app_row_index = end
        QTimer.singleShot(1, self._append_next_app_rows_batch)

    def _populate_app_row(
        self,
        row_index: int,
        row: dict,
        *,
        read_only: bool,
        font_size_key: str,
        actions_available: bool,
        action_button_width: int,
        action_button_height: int,
    ) -> None:
        """
        只渲染软件表的一行。

        注意：
        - 这里不能 clearContents()
        - 这里不能 setRowCount(len(rows))
        - 这里不能循环全部 rows
        - 这里不能调 _schedule_icon_batches()
        """
        table = getattr(self.w, "desktop_apps_table", None)
        if table is None:
            return

        tooltip = str(row.get("tooltip", "") or "").strip()
        app_id = str(row.get("app_id", "") or "").strip()

        table.setCellWidget(
            row_index,
            0,
            self._build_default_icon_widget(row, tooltip, font_size_key),
        )

        title_label = QLabel(str(row.get("title", "-")))
        self.page_loader._apply_widget_font(title_label, font_size_key)
        title_label.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        title_label.setStyleSheet(self.page_loader._software_name_cell_style(font_size_key))
        title_label.setToolTip(tooltip)
        table.setCellWidget(row_index, 1, title_label)

        permission_button = QPushButton(str(row.get("permission_label", row.get("permission_text", "否"))))
        self.page_loader._apply_widget_font(permission_button, font_size_key)
        permission_button.setStyleSheet(
            self.page_loader._status_badge_style(str(row.get("permission_color", "#EF4444")), font_size_key)
        )
        permission_button.setEnabled(not read_only and bool(row.get("can_adjust", False)))
        self._tag_app_button(
            permission_button,
            app_id=app_id,
            role="permission",
            flag="can_adjust",
            requires_backend=False,
        )
        permission_button.setToolTip(self._permission_tooltip(row))
        permission_button.clicked.connect(
            lambda _checked=False, current_app_id=app_id: self.w.desktop_controller.cycle_app_permission(current_app_id)
        )
        table.setCellWidget(row_index, 2, permission_button)

        actions_widget = QWidget()
        actions_layout = QHBoxLayout(actions_widget)
        actions_layout.setContentsMargins(0, 0, 0, 0)
        actions_layout.setSpacing(self.page_loader._size_int("software_action_button_spacing"))

        for label, action_kind, flag in (
            ("定位", "app.locate", "can_locate"),
            ("启动", "app.launch", "can_launch"),
            ("关闭", "app.close", "can_close"),
        ):
            button = QPushButton(label)
            self.page_loader._apply_widget_font(button, font_size_key)
            button.setFixedSize(action_button_width, action_button_height)
            button.setEnabled(
                self._resolve_app_action_enabled(
                    row,
                    read_only=read_only,
                    flag=flag,
                    action_kind=action_kind,
                )
            )
            self._tag_app_button(
                button,
                app_id=app_id,
                role="action",
                flag=flag,
                action_kind=action_kind,
                requires_backend=True,
            )
            action_tooltip = "执行当前软件动作" if actions_available else "当前模式不可执行软件动作"
            button.setToolTip(action_tooltip)
            button.setStyleSheet(self.page_loader._action_button_style(font_size_key))
            button.clicked.connect(
                lambda _checked=False, payload=row, kind=action_kind: self._trigger_app_action(payload, kind)
            )
            actions_layout.addWidget(button)

        if bool(row.get("can_bind_path", False)):
            bind_button = QPushButton("补路径")
            self.page_loader._apply_widget_font(bind_button, font_size_key)
            bind_button.setFixedSize(action_button_width, action_button_height)
            bind_button.setEnabled((not read_only) and bool(row.get("can_bind_path", False)))
            self._tag_app_button(
                bind_button,
                app_id=app_id,
                role="bind_path",
                flag="can_bind_path",
                requires_backend=False,
            )
            bind_button.setToolTip(f"{tooltip}\n\n为当前对象补充本地路径或平台入口，不会自动放开权限。".strip())
            bind_button.setStyleSheet(self.page_loader._action_button_style(font_size_key))
            bind_button.clicked.connect(
                lambda _checked=False, current_app_id=app_id: self.w.desktop_controller.bind_app_path(current_app_id)
            )
            actions_layout.addWidget(bind_button)

        for label, action_kind, flag in (
            ("卸载", "app.uninstall", "can_uninstall"),
            ("迁移", "app.relocate", "can_move"),
            ("更新", "app.update", "can_update"),
        ):
            button = QPushButton(label)
            self.page_loader._apply_widget_font(button, font_size_key)
            button.setFixedSize(action_button_width, action_button_height)
            button.setEnabled(
                self._resolve_app_action_enabled(
                    row,
                    read_only=read_only,
                    flag=flag,
                    action_kind=action_kind,
                )
            )
            self._tag_app_button(
                button,
                app_id=app_id,
                role="action",
                flag=flag,
                action_kind=action_kind,
                requires_backend=True,
            )
            button.setToolTip(
                "高风险软件动作：需要确认、审议和记录"
                if actions_available
                else "当前模式不可执行高风险软件动作"
            )
            button.setStyleSheet(self.page_loader._action_button_style(font_size_key))
            button.clicked.connect(
                lambda _checked=False, payload=row, kind=action_kind: self._trigger_dangerous_app_action(payload, kind)
            )
            actions_layout.addWidget(button)

        actions_layout.addStretch()
        table.setCellWidget(row_index, 3, actions_widget)

        path_item = self.page_loader._make_item(str(row.get("path_short", "-")))
        path_item.setToolTip(tooltip)
        table.setItem(row_index, 4, path_item)

        status_label = QLabel(str(row.get("status_badge", row.get("status_text", "-"))))
        self.page_loader._apply_widget_font(status_label, font_size_key)
        status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        status_label.setStyleSheet(
            self.page_loader._status_badge_style(str(row.get("status_color", "#F5F5F5")), font_size_key)
        )
        status_label.setToolTip(str(row.get("status_tooltip", tooltip)).strip())
        table.setCellWidget(row_index, 5, status_label)

        clear_button = QPushButton("")
        self.page_loader._make_icon_only_button(
            clear_button,
            "desktop.hide_icon",
            "software_hide_button_icon_size",
            "隐藏当前对象",
            button_size_key="desktop_table_icon_button_size",
        )
        self.page_loader._apply_widget_font(clear_button, font_size_key)
        clear_button.setEnabled((not read_only) and bool(row.get("can_clear", True)))
        self._tag_app_button(
            clear_button,
            app_id=app_id,
            role="clear",
            flag="can_clear",
            requires_backend=False,
        )
        clear_button.setToolTip(
            f"{tooltip}\n\n仅从当前显示区隐藏；不会卸载、删除或修改系统软件。重新扫描后可再次出现。".strip()
        )
        clear_button.setStyleSheet(self.page_loader._action_button_style(font_size_key))

        controller = getattr(self.w, "desktop_controller", None)
        if controller is not None and controller._is_vm_test_backend():
            clear_button.setToolTip(
                f"{tooltip}\n\n清理当前软件区缓存并重新读取 VM 软件列表，不会删除虚拟机中的软件。".strip()
            )

        clear_button.clicked.connect(
            lambda _checked=False, current_app_id=app_id: self.w.desktop_controller.hide_app_from_current_view(
                current_app_id
            )
        )
        table.setCellWidget(row_index, 6, clear_button)
        table.setRowHeight(row_index, self.page_loader._size_int("software_row_height"))

    def _populate_apps_table_sync(self, rows: list[dict], *, read_only: bool) -> None:
        """
        旧同步渲染回退入口。

        正常情况下不调用。
        保留它只是为了需要排查分批渲染时可临时回退。
        """
        table = getattr(self.w, "desktop_apps_table", None)
        if table is None:
            return

        runtime = getattr(getattr(self.w, "desktop_controller", None), "runtime", None)
        controller = getattr(self.w, "desktop_controller", None)
        actions_available = bool(controller.desktop_actions_available()) if controller is not None else False
        font_size_key = getattr(runtime, "software_font_size", "medium")
        action_button_width, action_button_height = self.page_loader._software_action_button_size(font_size_key)

        remembered_scroll = int(getattr(runtime, "software_table_scroll_value", table.verticalScrollBar().value()) or 0)
        remembered_h_scroll = int(
            getattr(runtime, "software_table_horizontal_scroll_value", table.horizontalScrollBar().value()) or 0
        )

        self._pending_icon_rows = []

        try:
            table.clearSpans()
        except Exception:
            pass

        table.clearContents()
        table.setRowCount(len(rows))

        for row_index, row in enumerate(rows):
            self._populate_app_row(
                row_index,
                row,
                read_only=read_only,
                font_size_key=font_size_key,
                actions_available=actions_available,
                action_button_width=action_button_width,
                action_button_height=action_button_height,
            )

        table.verticalScrollBar().setValue(min(remembered_scroll, table.verticalScrollBar().maximum()))
        table.horizontalScrollBar().setValue(min(remembered_h_scroll, table.horizontalScrollBar().maximum()))

        if runtime is not None:
            runtime.software_table_scroll_value = int(table.verticalScrollBar().value())
            runtime.software_table_horizontal_scroll_value = int(table.horizontalScrollBar().value())

        self._schedule_icon_batches(rows, font_size_key)
