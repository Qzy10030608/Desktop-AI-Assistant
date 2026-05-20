from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QTableWidget, QVBoxLayout, QWidget


def attach_size_badge(window: Any, card: QFrame, attr_name: str) -> None:
    size = getattr(window, "DESKTOP_UI_SIZE", {})
    layout = card.layout()
    if not isinstance(layout, QVBoxLayout) or layout.count() <= 0:
        return
    title_item = layout.itemAt(0)
    title = title_item.widget() if title_item is not None else None
    if title is None:
        return

    layout.removeWidget(title)
    row = QHBoxLayout()
    row.setSpacing(window.UI_SIZE["spacing_small"])
    row.addWidget(title)

    badge = QLabel("尺寸")
    badge.setObjectName("desktopSizeBadge")
    badge.setStyleSheet(
        "QLabel#desktopSizeBadge {"
        "color: #B8C7E0;"
        "background-color: rgba(18, 30, 46, 0.92);"
        f"border: {int(size['desktop_debug_badge_border_width'])}px solid rgba(148, 163, 184, 0.56);"
        f"border-radius: {int(size['desktop_debug_badge_radius'])}px;"
        f"padding: {int(size['desktop_debug_badge_padding_v'])}px {int(size['desktop_debug_badge_padding_h'])}px;"
        f"font-size: {int(size['desktop_debug_badge_font_size'])}px;"
        "font-weight: 700;"
        "}"
    )
    badge.setToolTip("尺寸信息会在页面刷新后显示。")
    row.addWidget(badge)
    row.addStretch()
    layout.insertLayout(0, row)
    setattr(window, attr_name, badge)


def install_desktop_debug_tools(window: Any) -> None:
    tools = getattr(window, "desktop_debug_tools", None)
    if not isinstance(tools, DesktopDebugTools):
        tools = DesktopDebugTools(window)
        setattr(window, "desktop_debug_tools", tools)
    tools.refresh_size_badges()


def apply_debug_layout_values(window: Any) -> None:
    # Scheme A: debug tools are display-only and must not apply size overrides.
    return


def refresh_size_badges(window: Any) -> None:
    tools = getattr(window, "desktop_debug_tools", None)
    if isinstance(tools, DesktopDebugTools):
        tools.refresh_size_badges()


class DesktopDebugTools:
    def __init__(self, window: Any) -> None:
        self.window = window

    def refresh_size_badges(self) -> None:
        disk_columns = self._column_widths("desktop_disk_table", (0, 1, 2, 3, 4))
        file_columns = self._column_widths("desktop_file_table", (0, 1, 2, 3, 4, 5, 6))
        app_columns = self._column_widths("desktop_apps_table", (0, 1, 2, 3, 4, 5, 6))

        self._set_badge_tooltip(
            "desktop_overview_size_badge",
            "\n".join([
                "连接状态与模式总览区",
                f"- 区块实际尺寸: {self._widget_size_text('desktop_overview_card')}",
            ]),
        )
        self._set_badge_tooltip(
            "desktop_file_size_badge",
            "\n".join([
                "文件治理区",
                f"- 区块实际尺寸: {self._widget_size_text('desktop_file_card')}",
                f"- 磁盘表实际尺寸: {self._widget_size_text('desktop_disk_table')}",
                f"- 对象表实际尺寸: {self._widget_size_text('desktop_file_table')}",
                "",
                "【配置真源】",
                self._size_config_line("disk_table_min_height"),
                self._size_config_line("file_table_min_height"),
                self._size_config_line("disk_column_width_name"),
                self._size_config_line("disk_column_width_status"),
                self._size_config_line("disk_column_width_bool"),
                self._size_config_line("file_column_width_enabled"),
                self._size_config_line("file_column_width_name"),
                self._size_config_line("file_column_width_path"),
                self._size_config_line("file_column_width_open"),
                self._size_config_line("file_column_width_type"),
                self._size_config_line("file_column_width_status"),
                self._size_config_line("file_column_width_permission"),
                "",
                "【上层磁盘表】",
                f"- 表头高度: {self._header_height('desktop_disk_table')}",
                f"- 第1行行高: {self._row_height('desktop_disk_table', 0)}",
                (
                    f"- 各列实际宽度: 盘名 {disk_columns[0]} / 状态 {disk_columns[1]} / "
                    f"允许展开 {disk_columns[2]} / 允许扫描 {disk_columns[3]} / 允许索引 {disk_columns[4]}"
                ),
                (
                    f"- 表头格子尺寸: 盘名 {self._header_cell_size_text('desktop_disk_table', 0)} / "
                    f"状态 {self._header_cell_size_text('desktop_disk_table', 1)} / "
                    f"允许展开 {self._header_cell_size_text('desktop_disk_table', 2)} / "
                    f"允许扫描 {self._header_cell_size_text('desktop_disk_table', 3)} / "
                    f"允许索引 {self._header_cell_size_text('desktop_disk_table', 4)}"
                ),
                f"- 第1行盘名按钮实际尺寸: {self._cell_widget_size_text('desktop_disk_table', 0, 0)}",
                f"- 第1行状态按钮实际尺寸: {self._cell_widget_size_text('desktop_disk_table', 0, 1)}",
                f"- 第1行允许展开按钮实际尺寸: {self._cell_widget_size_text('desktop_disk_table', 0, 2)}",
                f"- 第1行允许扫描按钮实际尺寸: {self._cell_widget_size_text('desktop_disk_table', 0, 3)}",
                f"- 第1行允许索引按钮实际尺寸: {self._cell_widget_size_text('desktop_disk_table', 0, 4)}",
                self._pressure_line("磁盘表压力", "desktop_disk_table", (1, 2, 3, 4), "盘名列"),
                "",
                "【下层对象表】",
                f"- 表头高度: {self._header_height('desktop_file_table')}",
                f"- 第1行行高: {self._row_height('desktop_file_table', 0)}",
                (
                    f"- 各列实际宽度: 启用 {file_columns[0]} / 名称 {file_columns[1]} / "
                    f"路径 {file_columns[2]} / 打开 {file_columns[3]} / 类型 {file_columns[4]} / "
                    f"状态 {file_columns[5]} / 权限 {file_columns[6]}"
                ),
                (
                    f"- 表头格子尺寸: 启用 {self._header_cell_size_text('desktop_file_table', 0)} / "
                    f"名称 {self._header_cell_size_text('desktop_file_table', 1)} / "
                    f"路径 {self._header_cell_size_text('desktop_file_table', 2)} / "
                    f"打开 {self._header_cell_size_text('desktop_file_table', 3)} / "
                    f"类型 {self._header_cell_size_text('desktop_file_table', 4)} / "
                    f"状态 {self._header_cell_size_text('desktop_file_table', 5)} / "
                    f"权限 {self._header_cell_size_text('desktop_file_table', 6)}"
                ),
                f"- 第1行启用控件实际尺寸: {self._cell_widget_size_text('desktop_file_table', 0, 0)}",
                f"- 第1行名称蓝框实际尺寸: {self._cell_widget_size_text('desktop_file_table', 0, 1)}",
                f"- 第1行打开按钮实际尺寸: {self._cell_widget_size_text('desktop_file_table', 0, 3)}",
                f"- 第1行状态框实际尺寸: {self._cell_widget_size_text('desktop_file_table', 0, 5)}",
                f"- 第1行权限框实际尺寸: {self._cell_widget_size_text('desktop_file_table', 0, 6)}",
                self._pressure_line("对象表压力", "desktop_file_table", (0, 1, 3, 4, 5, 6), "路径列"),
            ]),
        )
        self._set_badge_tooltip(
            "desktop_software_size_badge",
            "\n".join([
                "软件治理区",
                f"- 区块实际尺寸: {self._widget_size_text('desktop_software_card')}",
                f"- 软件表实际尺寸: {self._widget_size_text('desktop_apps_table')}",
                self._size_config_line("software_table_min_height"),
                self._size_config_line("software_column_width_icon"),
                self._size_config_line("software_column_width_name"),
                self._size_config_line("software_column_width_permission"),
                self._size_config_line("software_column_width_actions"),
                self._size_config_line("software_column_width_path"),
                self._size_config_line("software_column_width_status"),
                self._size_config_line("software_column_width_clear"),
                (
                    f"- 软件表实际列宽: 图标 {app_columns[0]} / 名称 {app_columns[1]} / "
                    f"权限 {app_columns[2]} / 允许操作 {app_columns[3]} / 路径 {app_columns[4]} / "
                    f"状态 {app_columns[5]} / 清理 {app_columns[6]}"
                ),
            ]),
        )
        self._set_badge_tooltip(
            "desktop_readonly_size_badge",
            "\n".join([
                "基础只读验证栏（V1）",
                f"- 区块实际尺寸: {self._widget_size_text('desktop_readonly_card')}",
                f"- 结果框实际尺寸: {self._widget_size_text('desktop_readonly_result_display')}",
                self._size_config_line("readonly_result_min_height"),
            ]),
        )
        self._set_badge_tooltip(
            "desktop_sandbox_size_badge",
            "\n".join([
                "V2 沙盒测试栏",
                f"- 区块实际尺寸: {self._widget_size_text('desktop_sandbox_card')}",
                f"- 结果框实际尺寸: {self._widget_size_text('desktop_sandbox_result_display')}",
                self._size_config_line("sandbox_result_min_height"),
            ]),
        )

    def _size_value(self, key: str) -> int:
        overrides = self._layout_overrides()
        if key in overrides:
            return int(overrides[key])
        return int(getattr(self.window, "DESKTOP_UI_SIZE", {})[key])

    def _size_source(self, key: str) -> str:
        return "运行时" if key in self._layout_overrides() else "默认"

    def _layout_overrides(self) -> dict:
        controller = getattr(self.window, "desktop_controller", None)
        runtime = getattr(controller, "runtime", None)
        overrides = getattr(runtime, "layout_overrides", {}) if runtime is not None else {}
        return overrides if isinstance(overrides, dict) else {}

    def _table(self, attr_name: str) -> QTableWidget | None:
        table = getattr(self.window, attr_name, None)
        return table if isinstance(table, QTableWidget) else None

    def _widget_size_text(self, attr_name: str) -> str:
        widget = getattr(self.window, attr_name, None)
        if not isinstance(widget, QWidget):
            return "-"
        return f"{widget.width()} x {widget.height()}"

    def _table_view_width(self, attr_name: str) -> int:
        table = self._table(attr_name)
        if table is None:
            return 0
        viewport = table.viewport()
        return viewport.width() if viewport is not None else table.width()

    def _column_widths(self, attr_name: str, columns: tuple[int, ...]) -> list[int]:
        table = self._table(attr_name)
        if table is None:
            return [0 for _ in columns]
        return [int(table.columnWidth(column)) for column in columns]

    def _header_height(self, table_attr: str) -> int:
        table = self._table(table_attr)
        if table is None:
            return 0
        return int(table.horizontalHeader().height())

    def _row_height(self, table_attr: str, row: int = 0) -> int:
        table = self._table(table_attr)
        if table is None or row < 0 or row >= table.rowCount():
            return 0
        return int(table.rowHeight(row))

    def _header_cell_size_text(self, table_attr: str, column: int) -> str:
        table = self._table(table_attr)
        if table is None or column < 0 or column >= table.columnCount():
            return "-"
        return f"{int(table.columnWidth(column))} x {self._header_height(table_attr)}"

    def _cell_widget_size_text(self, table_attr: str, row: int, col: int) -> str:
        table = self._table(table_attr)
        if table is None or row < 0 or row >= table.rowCount() or col < 0 or col >= table.columnCount():
            return "-"
        widget = table.cellWidget(row, col)
        if not isinstance(widget, QWidget):
            return "-"
        return f"{widget.width()} x {widget.height()}"

    def _size_config_line(self, key: str) -> str:
        return f"- {key}: {self._size_value(key)} ({self._size_source(key)})"

    def _pressure_line(self, label: str, table_attr: str, fixed_columns: tuple[int, ...], elastic_label: str) -> str:
        view_width = self._table_view_width(table_attr)
        fixed_width = sum(self._column_widths(table_attr, fixed_columns))
        remaining = view_width - fixed_width
        state = "正常" if remaining >= self._size_value("desktop_debug_pressure_min_width") else "偏挤"
        return f"- {label}: 表格 {view_width} / 固定列 {fixed_width} / {elastic_label}剩余 {remaining}（{state}）"

    def _set_badge_tooltip(self, attr_name: str, tooltip: str) -> None:
        badge = getattr(self.window, attr_name, None)
        if isinstance(badge, QLabel):
            badge.setToolTip(tooltip)
