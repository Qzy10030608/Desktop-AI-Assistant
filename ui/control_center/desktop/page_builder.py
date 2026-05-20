from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QGridLayout,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QProgressBar,
    QSizePolicy,
    QTableWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ui.control_center.control_center_widgets.no_wheel_combo import NoWheelComboBox  # type: ignore
from ui.control_center.desktop.debug_tools import attach_size_badge, install_desktop_debug_tools
from ui.control_center.desktop.help_popover import HoverHelpButton


FILE_GOVERNANCE_HELP_TITLE = "文件治理区说明"
FILE_GOVERNANCE_HELP_BODY = """上层磁盘治理：
- 权限为“否”时，不展开、不扫描、不查询，也不显示内部内容。
- 权限为“受限”或“是”时，才允许根据开关展开、扫描或查询。
- 扫描不会自动执行，只有点击磁盘或刷新扫描时才进行。
- 已扫描内容后续会进入缓存，下次优先显示缓存。

下层对象治理：
- 对象权限决定具体文件/文件夹能否执行动作。
- “受限”允许基础动作，例如打开、进入、重命名。
- “是”允许完整动作，例如创建、移动、复制、删除、恢复。
- 删除、移动、恢复等高风险动作仍需要确认、审议和记录。

模式说明：
- 限制模式：只允许部分文件查询与只读浏览。
- 信任模式：进入 Host 真实执行。
- 测试模式 + 沙盒：只生成回执，不真实执行。
- 测试模式 + 虚拟机：进入 VM 执行。"""

SOFTWARE_GOVERNANCE_HELP_TITLE = "软件治理区说明"
SOFTWARE_GOVERNANCE_HELP_BODY = """权限规则：
- 否：所有软件动作禁用。
- 受限：允许定位、启动、关闭；卸载、迁移、更新不可执行。
- 是：允许定位、启动、关闭、卸载、迁移、更新。

执行出口：
- 信任模式：进入 Host 真实执行。
- 测试模式 + 沙盒：只生成回执，不真实执行。
- 测试模式 + 虚拟机：进入 VM 执行。
- 限制模式：不执行软件动作。

注意：
- 卸载、迁移、更新属于高风险动作，会经过确认、审议和记录。
- 如果对象入口缺少路径、进程名或启动参数，执行结果会提示缺少信息。"""


def _desktop_size(window) -> dict:
    return getattr(window, "DESKTOP_UI_SIZE", {})

def _desktop_color(window) -> dict:
    return getattr(window, "DESKTOP_UI_COLOR", {})

def _desktop_color_value(window, key: str, fallback: str = "") -> str:
    return str(_desktop_color(window).get(key, fallback))

def _size_int(size: dict, key: str) -> int:
    return int(size[key])

def _table_style(size: dict) -> str:
    radius = _size_int(size, "desktop_table_border_radius")
    border_width = _size_int(size, "desktop_table_border_width")
    item_separator_width = _size_int(size, "desktop_table_item_separator_width")
    header_separator_width = _size_int(size, "desktop_table_header_separator_width")
    table_padding = _size_int(size, "desktop_table_padding")
    item_padding_v = _size_int(size, "desktop_table_item_padding_v")
    item_padding_h = _size_int(size, "desktop_table_item_padding_h")
    header_padding_v = _size_int(size, "desktop_table_header_padding_v")
    header_padding_h = _size_int(size, "desktop_table_header_padding_h")
    return (
        "QTableWidget {"
        "background-color: rgba(9, 14, 24, 0.78);"
        "alternate-background-color: rgba(17, 26, 40, 0.92);"
        f"border: {border_width}px solid rgba(110, 138, 180, 0.30);"
        f"border-radius: {radius}px;"
        f"padding: {table_padding}px;"
        "gridline-color: rgba(110, 138, 180, 0.24);"
        "selection-background-color: rgba(64, 96, 144, 0.42);"
        "}"
        "QTableWidget::item {"
        f"padding: {item_padding_v}px {item_padding_h}px;"
        f"border-bottom: {item_separator_width}px solid rgba(110, 138, 180, 0.12);"
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


def _build_status_value() -> QLabel:
    label = QLabel("-")
    label.setWordWrap(True)
    label.setStyleSheet("color: #B8C7E0;")
    return label

def _build_table(column_count: int, headers: list[str], size: dict | None = None) -> QTableWidget:
    size = size or {}
    table = QTableWidget(0, column_count)
    table.setHorizontalHeaderLabels(headers)
    table.verticalHeader().setVisible(False)
    table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
    table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    table.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
    table.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
    table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
    table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
    table.horizontalHeader().setStretchLastSection(False)
    table.setWordWrap(False)
    table.setAlternatingRowColors(True)
    table.setShowGrid(True)
    table.setGridStyle(Qt.PenStyle.SolidLine)
    table.setStyleSheet(_table_style(size))
    return table


def _fill_permission_combo(combo: NoWheelComboBox) -> None:
    combo.addItem("全部", "all")
    combo.addItem("是", "allow")
    combo.addItem("否", "deny")
    combo.addItem("受限", "once")


def _fill_software_permission_combo(combo: NoWheelComboBox) -> None:
    combo.addItem("全部", "all")
    combo.addItem("是", "allow")
    combo.addItem("否", "deny")
    combo.addItem("受限", "once")


def _fill_font_combo(combo: NoWheelComboBox) -> None:
    combo.addItem("小", "small")
    combo.addItem("中", "medium")
    combo.addItem("大", "large")


def _attach_help_button(window, card: QFrame, attr_name: str, title: str, body: str) -> None:
    layout = card.layout()
    if not isinstance(layout, QVBoxLayout) or layout.count() <= 0:
        return
    title_item = layout.itemAt(0)
    title_widget = title_item.widget() if title_item is not None else None
    if title_widget is None:
        return

    layout.removeWidget(title_widget)
    row = QHBoxLayout()
    row.setSpacing(window.UI_SIZE["spacing_small"])
    row.addWidget(title_widget)

    button = HoverHelpButton("说明", card)
    button.set_help_content(title, body)
    row.addWidget(button)
    row.addStretch()
    layout.insertLayout(0, row)
    setattr(window, attr_name, button)


def build_desktop_page(window) -> QFrame:
    page = QFrame()
    page.setObjectName("pageCard")
    size = _desktop_size(window)

    layout = QVBoxLayout(page)
    page_margin = _size_int(size, "desktop_page_margin")
    layout.setContentsMargins(page_margin, page_margin, page_margin, page_margin)
    layout.setSpacing(window.UI_SIZE["spacing_large"])

    title = QLabel("桌面连接")
    title.setStyleSheet(f"font-size: {window.UI_SIZE['font_page_title']}px; font-weight: bold;")
    layout.addWidget(title)

    desc = QLabel("桌面连接用于管理当前桌面模式、文件区和软件区。")
    desc.setWordWrap(True)
    desc.setStyleSheet("color: #9FB3D9;")
    layout.addWidget(desc)

    overview_card = window.build_section_card("连接状态与模式总览区")
    attach_size_badge(window, overview_card, "desktop_overview_size_badge")
    overview_layout = overview_card.layout()
    overview_grid = QGridLayout()
    overview_grid.setHorizontalSpacing(window.UI_SIZE["spacing_large"])
    overview_grid.setVerticalSpacing(window.UI_SIZE["spacing_small"])

    window.desktop_status_mode_value = _build_status_value()
    window.desktop_status_local_value = _build_status_value()
    window.desktop_status_confirmed_value = _build_status_value()
    window.desktop_status_root_count_value = _build_status_value()
    window.desktop_status_app_count_value = _build_status_value()

    for row_index, (label_text, value_label) in enumerate([
        ("当前模式", window.desktop_status_mode_value),
        ("local 是否已生成", window.desktop_status_local_value),
        ("白名单是否已确认", window.desktop_status_confirmed_value),
        ("根目录数量", window.desktop_status_root_count_value),
        ("已确认软件数量", window.desktop_status_app_count_value),
    ]):
        overview_grid.addWidget(QLabel(label_text), row_index, 0)
        overview_grid.addWidget(value_label, row_index, 1)
    overview_layout.addLayout(overview_grid)

    window.desktop_mode_summary_label = QLabel("当前模式说明")
    window.desktop_mode_summary_label.setWordWrap(True)
    window.desktop_mode_summary_label.setStyleSheet("color: #B8C7E0;")
    overview_layout.addWidget(window.desktop_mode_summary_label)

    mode_row = QHBoxLayout()
    mode_row.setSpacing(window.UI_SIZE["spacing_medium"])
    window.btn_desktop_mode_disabled = QPushButton("不启用")
    window.btn_desktop_mode_restricted = QPushButton("限制模式")
    window.btn_desktop_mode_trusted = QPushButton("信任模式")
    window.btn_desktop_mode_test = QPushButton("测试模式")
    for button in (
        window.btn_desktop_mode_disabled,
        window.btn_desktop_mode_restricted,
        window.btn_desktop_mode_trusted,
        window.btn_desktop_mode_test,
    ):
        button.setCheckable(True)
    window.btn_desktop_mode_disabled.clicked.connect(lambda: window.desktop_controller.set_mode("disabled"))
    window.btn_desktop_mode_restricted.clicked.connect(lambda: window.desktop_controller.set_mode("restricted"))
    window.btn_desktop_mode_trusted.clicked.connect(lambda: window.desktop_controller.set_mode("trusted"))
    window.btn_desktop_mode_test.clicked.connect(window.desktop_controller.toggle_test_mode)
    mode_row.addWidget(window.btn_desktop_mode_disabled)
    mode_row.addWidget(window.btn_desktop_mode_restricted)
    mode_row.addWidget(window.btn_desktop_mode_trusted)
    mode_row.addWidget(window.btn_desktop_mode_test)
    mode_row.addStretch()
    overview_layout.addLayout(mode_row)

    # ===== 测试模式提示 =====
    # 颜色从 config.py 的 DESKTOP_UI_COLOR 读取，不在页面代码里写死。
    window.desktop_test_mode_label = QLabel("测试模式：开启中")
    window.desktop_test_mode_label.setObjectName("desktopTestModeLabel")
    window.desktop_test_mode_label.setWordWrap(True)
    window.desktop_test_mode_label.setStyleSheet(
        "QLabel#desktopTestModeLabel {"
        f"color: {_desktop_color_value(window, 'desktop_overview_text', '#B8C7E0')};"
        "background: transparent;"
        "border: none;"
        "}"
    )
    overview_layout.addWidget(window.desktop_test_mode_label)

    # ===== 测试出口 + 记录入口行 =====
    # 注意：
    # - 记录按钮常驻，不属于测试出口；
    # - 这一行背景从 config.py 读取，默认透明，继承总览区背景；
    # - 具体显隐由 page_loader.py 根据 desktop_mode 控制。
    window.desktop_record_widget = QWidget()
    window.desktop_record_widget.setObjectName("desktopRecordWidget")
    window.desktop_record_widget.setAutoFillBackground(False)
    window.desktop_record_widget.setStyleSheet(
        "QWidget#desktopRecordWidget {"
        "background: transparent;"
        "border: none;"
        "}"
    )
    record_row = QHBoxLayout(window.desktop_record_widget)
    record_row.setContentsMargins(0, 0, 0, 0)
    record_row.setSpacing(window.UI_SIZE["spacing_medium"])

    window.desktop_test_backend_widget = QWidget()
    window.desktop_test_backend_widget.setObjectName("desktopTestBackendWidget")
    window.desktop_test_backend_widget.setAutoFillBackground(False)
    window.desktop_test_backend_widget.setStyleSheet(
        "QWidget#desktopTestBackendWidget {"
        f"background: {_desktop_color_value(window, 'desktop_test_backend_row_bg', 'transparent')};"
        "border: none;"
        "}"
    )

    test_backend_row = QHBoxLayout(window.desktop_test_backend_widget)
    test_backend_row.setContentsMargins(
        _size_int(size, "desktop_test_backend_row_margin_l"),
        _size_int(size, "desktop_test_backend_row_margin_t"),
        _size_int(size, "desktop_test_backend_row_margin_r"),
        _size_int(size, "desktop_test_backend_row_margin_b"),
    )
    test_backend_row.setSpacing(window.UI_SIZE["spacing_medium"])

    window.desktop_test_backend_label = QLabel("测试出口：")
    window.desktop_test_backend_label.setObjectName("desktopTestBackendLabel")
    window.desktop_test_backend_label.setStyleSheet(
        "QLabel#desktopTestBackendLabel {"
        f"color: {_desktop_color_value(window, 'desktop_test_backend_label_text', '#DCE6FA')};"
        "background: transparent;"
        "border: none;"
        "font-weight: 700;"
        "}"
    )
    test_backend_row.addWidget(window.desktop_test_backend_label)

    window.btn_desktop_test_backend_sandbox = QPushButton("沙盒测试")
    window.btn_desktop_test_backend_vm = QPushButton("虚拟机测试")
    for button in (
        window.btn_desktop_test_backend_sandbox,
        window.btn_desktop_test_backend_vm,
    ):
        button.setCheckable(True)

    window.btn_desktop_test_backend_sandbox.clicked.connect(
        lambda: window.desktop_controller.set_test_backend("sandbox")
    )
    window.btn_desktop_test_backend_vm.clicked.connect(
        lambda: window.desktop_controller.set_test_backend("vm")
    )

    test_backend_row.addWidget(window.btn_desktop_test_backend_sandbox)
    test_backend_row.addWidget(window.btn_desktop_test_backend_vm)
    test_backend_row.addStretch()

    record_row.addWidget(window.desktop_test_backend_widget, 1)
    record_row.addStretch()

    window.btn_desktop_shaofu = QPushButton("记录")
    window.btn_desktop_shaofu.clicked.connect(window.desktop_controller.open_shaofu_viewer)
    record_row.addWidget(window.btn_desktop_shaofu)

    overview_layout.addWidget(window.desktop_record_widget)

    file_card = window.build_section_card("文件治理区")
    _attach_help_button(
        window,
        file_card,
        "desktop_file_help_button",
        FILE_GOVERNANCE_HELP_TITLE,
        FILE_GOVERNANCE_HELP_BODY,
    )
    file_card.setObjectName("desktopFileCard")
    file_card.setMinimumWidth(_size_int(size, "file_card_min_width"))
    file_card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
    file_layout = file_card.layout()
    file_layout.setSpacing(_size_int(size, "file_top_spacing"))

    window.desktop_file_hint_label = QLabel("")
    window.desktop_file_hint_label.setWordWrap(True)
    window.desktop_file_hint_label.setStyleSheet("color: #9FB3D9;")
    window.desktop_file_hint_label.setVisible(False)
    file_layout.addWidget(window.desktop_file_hint_label)

    disk_toolbar = QHBoxLayout()
    disk_toolbar.setSpacing(_size_int(size, "toolbar_spacing_top"))
    window.desktop_file_edit_toggle = QPushButton("只读")
    window.desktop_file_edit_toggle.setCheckable(True)
    window.desktop_file_edit_toggle.toggled.connect(window.desktop_controller.set_file_governance_editable)
    window.desktop_disk_filter_combo = NoWheelComboBox()
    _fill_permission_combo(window.desktop_disk_filter_combo)
    window.desktop_disk_filter_combo.currentIndexChanged.connect(window.desktop_controller.on_disk_filter_changed)
    window.desktop_disk_font_combo = NoWheelComboBox()
    _fill_font_combo(window.desktop_disk_font_combo)
    window.desktop_disk_font_combo.currentIndexChanged.connect(window.desktop_controller.on_disk_font_size_changed)
    window.btn_desktop_rescan_disk = QPushButton("")
    window.btn_desktop_rescan_disk.setToolTip("扫描当前磁盘")
    window.btn_desktop_rescan_disk.clicked.connect(window.desktop_controller.rescan_current_disk)
    for label_text, widget in (
        ("模式", window.desktop_file_edit_toggle),
        ("磁盘筛选", window.desktop_disk_filter_combo),
        ("磁盘字体", window.desktop_disk_font_combo),
    ):
        disk_toolbar.addWidget(QLabel(label_text))
        disk_toolbar.addWidget(widget)
        disk_toolbar.addSpacing(window.UI_SIZE["spacing_small"])
    disk_toolbar.addWidget(window.btn_desktop_rescan_disk)
    disk_toolbar.addStretch()
    file_layout.addLayout(disk_toolbar)

    window.desktop_disk_hint_label = QLabel("")
    window.desktop_disk_hint_label.setWordWrap(True)
    window.desktop_disk_hint_label.setStyleSheet("color: #B8C7E0;")
    window.desktop_disk_hint_label.setVisible(False)
    file_layout.addWidget(window.desktop_disk_hint_label)

    window.desktop_disk_table = _build_table(6, ["盘名", "状态", "允许展开", "允许扫描", "允许查询", "文件动作"], size)
    window.desktop_disk_table.setObjectName("desktopDiskTable")
    disk_header = window.desktop_disk_table.horizontalHeader()
    disk_header.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
    disk_header.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
    disk_header.setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
    disk_header.setSectionResizeMode(3, QHeaderView.ResizeMode.Interactive)
    disk_header.setSectionResizeMode(4, QHeaderView.ResizeMode.Interactive)
    disk_header.setSectionResizeMode(5, QHeaderView.ResizeMode.Interactive)
    disk_header.sectionResized.connect(
        lambda column, _old_width, width: window.desktop_controller.on_table_section_resized("desktop_disk_table", column, width)
    )

    file_layout.addWidget(window.desktop_disk_table)

    object_toolbar = QHBoxLayout()
    object_toolbar.setSpacing(_size_int(size, "toolbar_spacing_bottom"))
    window.desktop_object_view_combo = NoWheelComboBox()
    window.desktop_object_view_combo.addItem("根目录表", "roots")
    window.desktop_object_view_combo.addItem("文件对象表", "objects")
    window.desktop_object_view_combo.currentIndexChanged.connect(window.desktop_controller.on_object_view_changed)
    window.desktop_trusted_disk_combo = NoWheelComboBox()
    window.desktop_trusted_disk_combo.currentIndexChanged.connect(window.desktop_controller.on_trusted_disk_changed)
    window.desktop_object_filter_combo = NoWheelComboBox()
    _fill_permission_combo(window.desktop_object_filter_combo)
    window.desktop_object_filter_combo.currentIndexChanged.connect(window.desktop_controller.on_object_filter_changed)
    window.desktop_object_font_combo = NoWheelComboBox()
    _fill_font_combo(window.desktop_object_font_combo)
    window.desktop_object_font_combo.currentIndexChanged.connect(window.desktop_controller.on_object_font_size_changed)
    window.btn_desktop_parent_dir = QPushButton("")
    window.btn_desktop_parent_dir.setToolTip("返回上级")
    window.btn_desktop_parent_dir.clicked.connect(window.desktop_controller.go_to_parent_directory)
    window.btn_desktop_roots_view = QPushButton("")
    window.btn_desktop_roots_view.setToolTip("返回根目录")
    window.btn_desktop_roots_view.clicked.connect(window.desktop_controller.back_to_roots_view)
    for label_text, widget in (
        ("可信磁盘", window.desktop_trusted_disk_combo),
        ("对象视图", window.desktop_object_view_combo),
        ("对象筛选", window.desktop_object_filter_combo),
        ("对象字体", window.desktop_object_font_combo),
    ):
        object_toolbar.addWidget(QLabel(label_text))
        object_toolbar.addWidget(widget)
        object_toolbar.addSpacing(window.UI_SIZE["spacing_small"])
    object_toolbar.addWidget(window.btn_desktop_parent_dir)
    object_toolbar.addWidget(window.btn_desktop_roots_view)
    object_toolbar.addStretch()
    file_layout.addLayout(object_toolbar)

    # 兼容旧字段名，后续确认无引用后可删除。
    window.desktop_file_view_combo = window.desktop_object_view_combo
    window.desktop_file_filter_combo = window.desktop_object_filter_combo
    window.desktop_file_font_combo = window.desktop_object_font_combo

    window.desktop_file_path_label = QLabel("当前目标：-")
    window.desktop_file_path_label.setWordWrap(True)
    window.desktop_file_path_label.setStyleSheet("color: #B8C7E0;")
    file_layout.addWidget(window.desktop_file_path_label)

    window.desktop_file_table = _build_table(8,["启用", "名称", "路径", "打开", "管理", "类型", "状态", "权限"],size)
    window.desktop_file_table.setObjectName("desktopFileTable")
    file_header = window.desktop_file_table.horizontalHeader()
    file_header.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
    file_header.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
    file_header.setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
    file_header.setSectionResizeMode(3, QHeaderView.ResizeMode.Interactive)
    file_header.setSectionResizeMode(4, QHeaderView.ResizeMode.Interactive)
    file_header.setSectionResizeMode(5, QHeaderView.ResizeMode.Interactive)
    file_header.setSectionResizeMode(6, QHeaderView.ResizeMode.Interactive)
    file_header.setSectionResizeMode(7, QHeaderView.ResizeMode.Interactive)
    file_header.sectionResized.connect(
        lambda column, _old_width, width: window.desktop_controller.on_table_section_resized("desktop_file_table", column, width)
    )
    
    file_layout.addWidget(window.desktop_file_table)

    software_card = window.build_section_card("软件治理区")
    _attach_help_button(
        window,
        software_card,
        "desktop_software_help_button",
        SOFTWARE_GOVERNANCE_HELP_TITLE,
        SOFTWARE_GOVERNANCE_HELP_BODY,
    )
    software_card.setObjectName("desktopSoftwareCard")
    software_layout = software_card.layout()

    summary_row = QHBoxLayout()
    summary_row.setSpacing(window.UI_SIZE["spacing_large"])
    window.desktop_software_discovered_label = QLabel("已发现软件数量：0")
    window.desktop_software_confirmed_label = QLabel("已信任软件数量：0")
    window.desktop_software_hidden_label = QLabel("已隐藏对象数量：0")
    for label in (window.desktop_software_discovered_label, window.desktop_software_confirmed_label, window.desktop_software_hidden_label):
        label.setStyleSheet("color: #B8C7E0;")
        summary_row.addWidget(label)
    summary_row.addStretch()
    software_layout.addLayout(summary_row)

    software_toolbar = QHBoxLayout()
    software_toolbar.setSpacing(window.UI_SIZE["spacing_medium"])
    window.desktop_app_filter_combo = NoWheelComboBox()
    _fill_software_permission_combo(window.desktop_app_filter_combo)
    window.desktop_app_filter_combo.currentIndexChanged.connect(window.desktop_controller.on_filter_changed)
    window.desktop_software_font_combo = NoWheelComboBox()
    _fill_font_combo(window.desktop_software_font_combo)
    window.desktop_software_font_combo.currentIndexChanged.connect(window.desktop_controller.on_software_font_size_changed)
    window.desktop_apps_edit_toggle = QPushButton("只读")
    window.desktop_apps_edit_toggle.setCheckable(True)
    window.desktop_apps_edit_toggle.toggled.connect(window.desktop_controller.set_apps_editable)
    window.btn_desktop_load_apps_memory = QPushButton("加载上次记录")
    window.btn_desktop_load_apps_memory.clicked.connect(window.desktop_controller.load_software_memory_records)
    window.btn_desktop_rescan = QPushButton("")
    window.btn_desktop_rescan.setToolTip("快速扫描软件")
    window.btn_desktop_rescan.clicked.connect(
        lambda: window.desktop_controller.rescan_apps("quick")
    )

    window.btn_desktop_full_scan = QPushButton("")
    window.btn_desktop_full_scan.setToolTip("完整扫描软件")
    window.btn_desktop_full_scan.clicked.connect(
        lambda: window.desktop_controller.rescan_apps("full")
    )

    window.btn_desktop_clear_apps = QPushButton("")
    window.btn_desktop_clear_apps.setToolTip("清理连接")
    window.btn_desktop_clear_apps.clicked.connect(window.desktop_controller.clear_third_party_connections)
    for label_text, widget in (("筛选", window.desktop_app_filter_combo), ("字体", window.desktop_software_font_combo)):
        software_toolbar.addWidget(QLabel(label_text))
        software_toolbar.addWidget(widget)
        software_toolbar.addSpacing(window.UI_SIZE["spacing_small"])
    software_toolbar.addWidget(window.desktop_apps_edit_toggle)
    software_toolbar.addWidget(window.btn_desktop_load_apps_memory)
    software_toolbar.addWidget(window.btn_desktop_rescan)
    software_toolbar.addWidget(window.btn_desktop_full_scan)
    software_toolbar.addWidget(window.btn_desktop_clear_apps)
    software_toolbar.addStretch()
    software_layout.addLayout(software_toolbar)

    window.desktop_apps_hint_label = QLabel("")
    window.desktop_apps_hint_label.setWordWrap(True)
    window.desktop_apps_hint_label.setStyleSheet("color: #9FB3D9;")
    window.desktop_apps_hint_label.setVisible(False)
    software_layout.addWidget(window.desktop_apps_hint_label)
    window.desktop_software_scan_stage_label = QLabel("扫描状态：空闲")
    window.desktop_software_scan_stage_label.setWordWrap(True)
    window.desktop_software_scan_stage_label.setMinimumHeight(44)
    window.desktop_software_scan_stage_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
    window.desktop_software_scan_stage_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    window.desktop_software_scan_stage_label.setStyleSheet("color: #B8C7E0;")
    software_layout.addWidget(window.desktop_software_scan_stage_label)

    window.desktop_software_scan_stats_label = QLabel("扫描统计：-")
    window.desktop_software_scan_stats_label.setWordWrap(True)
    window.desktop_software_scan_stats_label.setMinimumHeight(44)
    window.desktop_software_scan_stats_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
    window.desktop_software_scan_stats_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    window.desktop_software_scan_stats_label.setStyleSheet("color: #9FB3D9;")
    software_layout.addWidget(window.desktop_software_scan_stats_label)

    scan_feedback_row = QHBoxLayout()
    scan_feedback_row.setSpacing(window.UI_SIZE["spacing_medium"])

    window.desktop_software_scan_animation_label = QLabel("")
    window.desktop_software_scan_animation_label.setVisible(False)
    window.desktop_software_scan_animation_label.setFixedSize(
        _size_int(size, "software_scan_feedback_icon_size"),
        _size_int(size, "software_scan_feedback_icon_size"),
    )
    scan_feedback_row.addWidget(window.desktop_software_scan_animation_label)

    window.desktop_software_scan_progress_bar = QProgressBar()
    window.desktop_software_scan_progress_bar.setRange(0, 100)
    window.desktop_software_scan_progress_bar.setValue(0)
    window.desktop_software_scan_progress_bar.setTextVisible(True)
    window.desktop_software_scan_progress_bar.setVisible(False)
    window.desktop_software_scan_progress_bar.setMinimumWidth(
        _size_int(size, "software_scan_progress_min_width")
    )
    window.desktop_software_scan_progress_bar.setFixedHeight(
        _size_int(size, "software_scan_progress_height")
    )
    scan_feedback_row.addWidget(window.desktop_software_scan_progress_bar, 1)
    scan_feedback_row.addStretch()

    software_layout.addLayout(scan_feedback_row)

    window.desktop_software_scan_log_label = QLabel("最近日志：-")
    window.desktop_software_scan_log_label.setWordWrap(True)
    window.desktop_software_scan_log_label.setMinimumHeight(52)
    window.desktop_software_scan_log_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
    window.desktop_software_scan_log_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    window.desktop_software_scan_log_label.setStyleSheet("color: #8EA4CC;")
    software_layout.addWidget(window.desktop_software_scan_log_label)

    window.desktop_apps_table = _build_table(7, ["图标", "软件名", "权限", "允许操作", "路径", "状态", "清理"], size)
    apps_header = window.desktop_apps_table.horizontalHeader()
    apps_header.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
    apps_header.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
    apps_header.setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
    apps_header.setSectionResizeMode(3, QHeaderView.ResizeMode.Interactive)
    apps_header.setSectionResizeMode(4, QHeaderView.ResizeMode.Interactive)
    apps_header.setSectionResizeMode(5, QHeaderView.ResizeMode.Interactive)
    apps_header.setSectionResizeMode(6, QHeaderView.ResizeMode.Interactive)
    apps_header.sectionResized.connect(
        lambda column, _old_width, width: window.desktop_controller.on_table_section_resized("desktop_apps_table", column, width)
    )
    
    software_layout.addWidget(window.desktop_apps_table)

    readonly_card = window.build_section_card("基础只读验证栏（V1）")
    attach_size_badge(window, readonly_card, "desktop_readonly_size_badge")
    readonly_layout = readonly_card.layout()

    window.desktop_readonly_hint_label = QLabel("V1 用于基础回归验证：读取当前时间/日期、列目录、读路径元信息，以及打开白名单目录。该栏保留真实只读链路。")
    window.desktop_readonly_hint_label.setWordWrap(True)
    window.desktop_readonly_hint_label.setStyleSheet("color: #9FB3D9;")
    readonly_layout.addWidget(window.desktop_readonly_hint_label)

    window.desktop_readonly_summary_label = QLabel("当前尚未执行基础只读验证。")
    window.desktop_readonly_summary_label.setWordWrap(True)
    window.desktop_readonly_summary_label.setStyleSheet("color: #B8C7E0;")
    readonly_layout.addWidget(window.desktop_readonly_summary_label)

    target_row = QHBoxLayout()
    target_row.setSpacing(window.UI_SIZE["spacing_medium"])
    target_row.addWidget(QLabel("目标根目录"))
    window.desktop_runtime_root_combo = NoWheelComboBox()
    window.desktop_runtime_root_combo.currentIndexChanged.connect(window.desktop_controller.on_runtime_root_changed)
    target_row.addWidget(window.desktop_runtime_root_combo, 0)
    window.desktop_runtime_target_path_label = QLabel("-")
    window.desktop_runtime_target_path_label.setWordWrap(True)
    window.desktop_runtime_target_path_label.setStyleSheet("color: #9FB3D9;")
    target_row.addWidget(window.desktop_runtime_target_path_label, 1)
    readonly_layout.addLayout(target_row)

    readonly_actions_row = QHBoxLayout()
    readonly_actions_row.setSpacing(window.UI_SIZE["spacing_medium"])
    window.btn_desktop_read_datetime = QPushButton("读取时间/日期")
    window.btn_desktop_list_root = QPushButton("列目录")
    window.btn_desktop_root_meta = QPushButton("读路径信息")
    window.btn_desktop_open_root = QPushButton("打开目录")
    window.btn_desktop_clear_result = QPushButton("清空结果")
    window.btn_desktop_read_datetime.clicked.connect(window.desktop_controller.run_readonly_datetime)
    window.btn_desktop_list_root.clicked.connect(window.desktop_controller.run_readonly_list_dir)
    window.btn_desktop_root_meta.clicked.connect(window.desktop_controller.run_readonly_path_meta)
    window.btn_desktop_open_root.clicked.connect(window.desktop_controller.run_readonly_open_directory)
    window.btn_desktop_clear_result.clicked.connect(window.desktop_controller.clear_readonly_result)
    readonly_actions_row.addWidget(window.btn_desktop_read_datetime)
    readonly_actions_row.addWidget(window.btn_desktop_list_root)
    readonly_actions_row.addWidget(window.btn_desktop_root_meta)
    readonly_actions_row.addWidget(window.btn_desktop_open_root)
    readonly_actions_row.addWidget(window.btn_desktop_clear_result)
    readonly_actions_row.addStretch()
    readonly_layout.addLayout(readonly_actions_row)

    window.desktop_readonly_result_display = QTextEdit()
    window.desktop_readonly_result_display.setReadOnly(True)
    readonly_layout.addWidget(window.desktop_readonly_result_display)

    sandbox_card = window.build_section_card("沙盒测试栏")
    attach_size_badge(window, sandbox_card, "desktop_sandbox_size_badge")
    sandbox_layout = sandbox_card.layout()

    window.desktop_sandbox_hint_label = QLabel("沙盒测试只生成审议和回执，不真实执行文件或软件动作。")
    window.desktop_sandbox_hint_label.setWordWrap(True)
    window.desktop_sandbox_hint_label.setStyleSheet("color: #9FB3D9;")
    sandbox_layout.addWidget(window.desktop_sandbox_hint_label)

    window.desktop_sandbox_summary_label = QLabel("当前尚未执行沙盒测试。")
    window.desktop_sandbox_summary_label.setWordWrap(True)
    window.desktop_sandbox_summary_label.setStyleSheet("color: #B8C7E0;")
    sandbox_layout.addWidget(window.desktop_sandbox_summary_label)

    sandbox_actions = QHBoxLayout()
    sandbox_actions.setSpacing(window.UI_SIZE["spacing_medium"])
    window.btn_desktop_clear_sandbox_result = QPushButton("清空沙盒结果")
    window.btn_desktop_clear_sandbox_result.clicked.connect(window.desktop_controller.clear_sandbox_result)
    sandbox_actions.addWidget(window.btn_desktop_clear_sandbox_result)
    sandbox_actions.addStretch()
    sandbox_layout.addLayout(sandbox_actions)

    window.desktop_sandbox_result_display = QTextEdit()
    window.desktop_sandbox_result_display.setReadOnly(True)
    sandbox_layout.addWidget(window.desktop_sandbox_result_display)

    layout.addWidget(overview_card)
    layout.addWidget(file_card)
    layout.addWidget(sandbox_card)
    layout.addWidget(software_card)
    layout.addWidget(readonly_card)
    layout.addStretch()

    window.desktop_overview_card = overview_card
    window.desktop_file_card = file_card
    window.desktop_software_card = software_card
    window.desktop_readonly_card = readonly_card
    window.desktop_sandbox_card = sandbox_card
    window.desktop_mode_card = overview_card
    window.desktop_roots_card = file_card
    window.desktop_apps_card = software_card
    install_desktop_debug_tools(window)

    return page
