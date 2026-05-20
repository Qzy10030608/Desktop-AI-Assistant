from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
)

from services.desktop.qin.hubu.storage_metrics_service import StorageMetricsService
from services.desktop.qin.shaofu.restore_registry import RestoreRegistry
from services.desktop.qin.shaofu.storage_index import StorageIndex


class ShaofuViewerDialog(QDialog):
    """Read-only Shaofu material management center."""

    ACTION_HEADERS = ["时间", "动作", "对象", "执行位置", "执行情况", "可撤回", "恢复状态", "保留时间"]
    AI_HEADERS = ["时间", "指令内容", "动作", "对象", "是否成功"]
    YUSHITAI_HEADERS = ["开始时间", "运行ID", "环境", "状态", "事件数", "报告"]
    ACTION_LABELS = {
    # 文件
    "file.open": "打开文件",
    "file.close": "关闭文件",
    "file.create": "创建文件",
    "file.delete": "删除文件",
    "file.move": "移动文件",
    "file.rename": "重命名文件",
    "file.restore": "恢复文件",

    # 文件夹
    "folder.open": "打开文件夹",
    "folder.close": "关闭文件夹",
    "folder.create": "创建文件夹",
    "folder.delete": "删除文件夹",
    "folder.move": "移动文件夹",
    "folder.rename": "重命名文件夹",
    "folder.restore": "恢复文件夹",

    # 软件
    "app.open": "打开软件",
    "app.launch": "启动软件",
    "app.close": "关闭软件",
    "app.locate": "定位软件",
    "app.relocate": "迁移软件",
    "app.move": "移动软件",
    "app.uninstall": "卸载软件",
    "app.update": "更新软件",

    # 兼容旧记录
    "software_relocate": "迁移软件",
}

    ENVIRONMENT_LABELS = {
        "current": "当前",
        "vm": "测试",
        "host": "正式",
    }

    def __init__(
        self,
        parent=None,
        *,
        project_root: str | Path | None = None,
        current_environment: str = "vm",
    ) -> None:
        super().__init__(parent)
        self.project_root = project_root
        self.registry = RestoreRegistry(project_root)
        self.storage_index = StorageIndex(project_root)
        self.metrics_service = StorageMetricsService(project_root)
        self.developer_mode = True
        self.current_environment = "vm" if str(current_environment or "").strip().lower() == "vm" else "host"
        self._record_mode = "shaofu"
        self._ai_mode = False
        self._all_materials: list[dict[str, Any]] = []
        self._visible_materials: list[dict[str, Any]] = []
        self._all_yushitai_runs: list[dict[str, Any]] = []
        self._visible_yushitai_runs: list[dict[str, Any]] = []

        self.setWindowTitle("少府 · 材料管理中心")
        layout = QVBoxLayout(self)

        self.summary_label = QLabel("-")
        self.summary_label.setWordWrap(True)
        layout.addWidget(self.summary_label)

        filter_row = QHBoxLayout()
        self.range_combo = QComboBox()
        self.range_combo.addItem("最近 10 条", 10)
        self.range_combo.addItem("最近 30 条", 30)
        self.range_combo.addItem("全部", 0)

        self.environment_combo = QComboBox()
        self.environment_combo.addItem("当前", self.current_environment)
        self.environment_combo.addItem("测试", "vm")
        self.environment_combo.addItem("正式", "host")

        self.action_combo = QComboBox()
        for label, value in (
            ("全部", "all"),
            ("文件删除", "file.delete"),
            ("文件移动", "file.move"),
            ("文件重命名", "file.rename"),
            ("软件迁移", "software_relocate"),
            ("软件卸载", "app.uninstall"),
            ("软件更新", "app.update"),
            ("其他", "other"),
        ):
            self.action_combo.addItem(label, value)

        self.status_combo = QComboBox()
        for label, value in (
            ("全部", "all"),
            ("可撤回", "undoable"),
            ("不可撤回", "not_undoable"),
            ("待验证", "unverified"),
            ("已过期", "expired"),
            ("失败", "failed"),
        ):
            self.status_combo.addItem(label, value)

        self.retention_combo = QComboBox()
        self.retention_combo.addItem("7 天", 7)
        self.retention_combo.addItem("14 天", 14)
        self.retention_combo.addItem("30 天", 30)

        self.record_mode_combo = QComboBox()
        self.record_mode_combo.addItem("少府材料", "shaofu")
        self.record_mode_combo.addItem("御史台记录", "yushitai")
        self.record_mode_combo.addItem("AI指令", "ai")
        self.record_mode_combo.currentIndexChanged.connect(self._on_record_mode_changed)

        self.range_label = QLabel("显示范围")
        self.environment_label = QLabel("当前环境")
        self.action_label_widget = QLabel("动作类型")
        self.status_label = QLabel("恢复状态")
        self.retention_label = QLabel("保留时间")
        self.record_mode_label = QLabel("记录类型")

        self.yushitai_backend_label = QLabel("运行环境")
        self.yushitai_backend_combo = QComboBox()
        self.yushitai_backend_combo.addItem("全部", "all")
        self.yushitai_backend_combo.addItem("Host", "host")
        self.yushitai_backend_combo.addItem("VM", "vm")
        self.yushitai_backend_combo.currentIndexChanged.connect(self._on_yushitai_backend_changed)
        self.yushitai_backend_label.hide()
        self.yushitai_backend_combo.hide()

        self.yushitai_run_label = QLabel("运行记录")
        self.yushitai_run_combo = QComboBox()
        self.yushitai_run_combo.currentIndexChanged.connect(self._on_yushitai_run_changed)
        self.yushitai_run_label.hide()
        self.yushitai_run_combo.hide()

        filter_row.addWidget(self.range_label)
        filter_row.addWidget(self.range_combo)
        filter_row.addWidget(self.environment_label)
        filter_row.addWidget(self.environment_combo)
        filter_row.addWidget(self.action_label_widget)
        filter_row.addWidget(self.action_combo)
        filter_row.addWidget(self.status_label)
        filter_row.addWidget(self.status_combo)
        filter_row.addWidget(self.retention_label)
        filter_row.addWidget(self.retention_combo)
        filter_row.addWidget(self.yushitai_backend_label)
        filter_row.addWidget(self.yushitai_backend_combo)
        filter_row.addWidget(self.yushitai_run_label)
        filter_row.addWidget(self.yushitai_run_combo)
        filter_row.addWidget(self.record_mode_label)
        filter_row.addWidget(self.record_mode_combo)
        layout.addLayout(filter_row)

        self.table = QTableWidget(0, len(self.ACTION_HEADERS))
        self.table.setHorizontalHeaderLabels(self.ACTION_HEADERS)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setAlternatingRowColors(True)
        self.table.setWordWrap(False)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.itemSelectionChanged.connect(self._show_selected_detail)
        layout.addWidget(self.table)

        self.detail_label = QLabel("操作说明")
        layout.addWidget(self.detail_label)
        self.user_detail = QTextEdit()
        self.user_detail.setReadOnly(True)
        layout.addWidget(self.user_detail)

        self.developer_label = QLabel("开发者详情 JSON")
        self.developer_detail = QTextEdit()
        self.developer_detail.setReadOnly(True)
        layout.addWidget(self.developer_label)
        layout.addWidget(self.developer_detail)
        if not self.developer_mode:
            self.developer_label.hide()
            self.developer_detail.hide()

        button_row = QHBoxLayout()
        button_row.addStretch()
        self.cleanup_button = QPushButton("清理")
        self.delete_button = QPushButton("删除")
        self.refresh_button = QPushButton("刷新")
        self.undo_button = QPushButton("撤回")
        self.undo_button.setEnabled(False)
        self.delete_button.setEnabled(False)
        self.cleanup_button.clicked.connect(self._request_cleanup)
        self.delete_button.clicked.connect(self._request_delete)
        self.refresh_button.clicked.connect(self.refresh)
        self.undo_button.clicked.connect(self._request_undo)
        button_row.addWidget(self.cleanup_button)
        button_row.addWidget(self.delete_button)
        button_row.addWidget(self.refresh_button)
        button_row.addWidget(self.undo_button)
        layout.addLayout(button_row)

        self.range_combo.currentIndexChanged.connect(self._apply_filters)
        self.environment_combo.currentIndexChanged.connect(self._apply_filters)
        self.action_combo.currentIndexChanged.connect(self._apply_filters)
        self.status_combo.currentIndexChanged.connect(self._apply_filters)
        self.retention_combo.currentIndexChanged.connect(self._retention_changed)
        self._select_combo_data(self.environment_combo, self.current_environment)

    def set_current_environment(self, environment: str) -> None:
        normalized = "vm" if str(environment or "").strip().lower() == "vm" else "host"
        self.current_environment = normalized
        if self.environment_combo.count():
            self.environment_combo.setItemData(0, normalized)
        self._select_combo_data(self.environment_combo, normalized)

    def refresh(self) -> None:
        if self._record_mode == "yushitai":
            self._refresh_yushitai()
            return

        if self._record_mode == "ai":
            self._refresh_ai_records()
            return

        self._refresh_shaofu()

    def _refresh_shaofu(self) -> None:
        self._load_retention_policy()
        try:
            materials = self.registry.read_all(include_deleted=False)
        except TypeError:
            materials = self.registry.read_all()

        storage_index = self.storage_index.read()
        index_items = storage_index.get("materials", []) if isinstance(storage_index.get("materials"), list) else []

        if not materials and index_items:
            materials = [
                dict(item)
                for item in index_items
                if isinstance(item, dict) and not bool(item.get("deleted", False))
            ]

        self._all_materials = list(reversed(materials))
        self._apply_filters()


    def _refresh_yushitai(self) -> None:
        self._all_yushitai_runs = self._load_yushitai_runs()
        self._apply_yushitai_backend_filter()

        self._populate_summary()

        if self._visible_yushitai_runs:
            self.yushitai_run_combo.setCurrentIndex(0)
            self._show_yushitai_run_detail(self._visible_yushitai_runs[0])
        else:
            self.user_detail.setPlainText("当前暂无御史台运行记录。")
            self.developer_detail.setPlainText("")

        self.table.hide()

    def _apply_yushitai_backend_filter(self) -> None:
        backend_filter = str(self.yushitai_backend_combo.currentData() or "all").strip().lower()

        if backend_filter == "all":
            runs = list(self._all_yushitai_runs)
        else:
            runs = [
                run for run in self._all_yushitai_runs
                if str(run.get("backend", "") or "").strip().lower() == backend_filter
            ]

        self._visible_yushitai_runs = runs

        self.yushitai_run_combo.blockSignals(True)
        self.yushitai_run_combo.clear()

        for index, run in enumerate(self._visible_yushitai_runs):
            label = self._yushitai_combo_label(run)
            self.yushitai_run_combo.addItem(label, index)

        self.yushitai_run_combo.blockSignals(False)

    def _refresh_ai_records(self) -> None:
        # AI 指令当前先复用少府材料里的 ai_command_text 字段。
        # 后续 LLM 接入后再改成读取御史台 instruction events。
        self._load_retention_policy()
        try:
            materials = self.registry.read_all(include_deleted=False)
        except TypeError:
            materials = self.registry.read_all()

        self._all_materials = list(reversed(materials))
        self._apply_filters()

    def _apply_filters(self) -> None:
        if self._record_mode == "yushitai":
            self._visible_yushitai_runs = list(self._all_yushitai_runs)
            self._populate_summary()
            self._populate_table()
            self._clear_detail()
            return

        environment = self._selected_environment()
        self.current_environment = environment

        materials = [item for item in self._all_materials if self._environment_for(item) == environment]
        materials = [item for item in materials if self._environment_for(item) not in {"sandbox", "unknown"}]

        if self._record_mode != "ai":
            action_filter = str(self.action_combo.currentData() or "all")
            status_filter = str(self.status_combo.currentData() or "all")

            if action_filter != "all":
                materials = [item for item in materials if self._matches_action_filter(item, action_filter)]
            if status_filter != "all":
                materials = [item for item in materials if self._matches_status_filter(item, status_filter)]
        else:
            materials = [item for item in materials if self._ai_command_text(item)]

        limit = int(self.range_combo.currentData() or 0)
        if limit > 0:
            materials = materials[:limit]

        self._visible_materials = materials
        self._populate_summary()
        self._populate_table()
        self._clear_detail()

    def _populate_summary(self) -> None:
        if self._record_mode == "yushitai":
            run = self._selected_yushitai_run()

            if run is None:
                self.summary_label.setText("开始时间：- | 运行ID：- | 事件数：0")
                return

            started_at = str(run.get("started_at", "") or "-")
            run_id = str(run.get("run_id", "") or "-")
            event_count = int(run.get("event_count", 0) or 0)

            self.summary_label.setText(
                f"开始时间：{started_at} | 运行ID：{run_id} | 事件数：{event_count}"
            )
            return

        if self._record_mode == "ai":
            count = len(self._visible_materials)
            self.summary_label.setText(f"AI 指令记录：{count} | 当前为预留入口")
            return

        environment = self._selected_environment()
        env_materials = [item for item in self._all_materials if self._environment_for(item) == environment]
        env_materials = [item for item in env_materials if self._environment_for(item) not in {"sandbox", "unknown"}]

        metrics = self.metrics_service.collect_metrics()
        size_bytes = int(metrics.get("shaofu_size_bytes", 0) or 0)

        text = " | ".join([
            f"材料总数：{len(env_materials)}",
            f"可撤回：{len([item for item in env_materials if self._can_request_undo(item)])}",
            f"待验证：{len([item for item in env_materials if self._normalized(self._value(item, 'verify_status')) == 'unverified'])}",
            f"已过期：{len([item for item in env_materials if self._is_expired(item)])}",
            f"占用：{self._format_size(size_bytes)}",
        ])
        self.summary_label.setText(text)

    def _populate_table(self) -> None:
        if self._record_mode == "yushitai":
            self.table.setRowCount(0)
            self.table.hide()
            return

        self.table.show()

        if self._record_mode == "ai":
            headers = self.AI_HEADERS
        else:
            headers = self.ACTION_HEADERS

        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        self.table.setRowCount(0)

        for row_index, material in enumerate(self._visible_materials):
            self.table.insertRow(row_index)
            values = self._ai_row_values(material) if self._record_mode == "ai" else self._action_row_values(material)

            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.table.setItem(row_index, column, item)

        if self._record_mode == "ai" and not self._visible_materials:
            self.user_detail.setPlainText("当前暂无 AI 指令记录。连接主页面文字/语音后会显示。")

    def _action_row_values(self, material: dict[str, Any]) -> list[str]:
        return [
            self._value(material, "created_at"),
            self._action_label(material),
            self._target_name(material),
            self._execution_location(material),
            self._execution_status(material),
            "是" if self._can_request_undo(material) else "否",
            self._restore_status_label(material),
            self._retention_until_label(material),
        ]

    def _ai_row_values(self, material: dict[str, Any]) -> list[str]:
        return [
            self._value(material, "created_at"),
            self._ai_command_text(material),
            self._action_label(material),
            self._target_name(material),
            "是" if self._truthy(self._value(material, "command_success")) else "否",
        ]
    
    def _show_yushitai_run_detail(self, run: dict[str, Any]) -> None:
        self.user_detail.setPlainText(self._read_yushitai_report(run))

        if self.developer_mode:
            payload = self._yushitai_developer_payload(run)
            self.developer_detail.setPlainText(
                json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
            )

    def _show_selected_detail(self) -> None:
        if self._record_mode == "yushitai":
            run = self._selected_yushitai_run()
            if run is None:
                self._clear_detail()
                return
            self._show_yushitai_run_detail(run)
            return

        material = self._selected_material()
        if material is None:
            self._clear_detail()
            return

        self.delete_button.setEnabled(self._record_mode != "ai")
        self.undo_button.setEnabled(False if self._record_mode == "ai" else self._can_request_undo(material))

        self.user_detail.setPlainText(self._user_description(material))

        if self.developer_mode:
            developer_payload = {
                "checkpoint_id": self._value(material, "checkpoint_id"),
                "material_id": self._value(material, "material_id"),
                "execution_backend": self._value(material, "execution_backend"),
                "target_environment": self._value(material, "target_environment"),
                "path_namespace": self._value(material, "path_namespace"),
                "restore_strategy": self._value(material, "restore_strategy"),
                "rollback_strategy": self._value(material, "rollback_strategy"),
                "material_type": self._value(material, "material_type"),
                "material_status": self._value(material, "material_status"),
                "restore_status": self._value(material, "restore_status"),
                "verify_status": self._value(material, "verify_status"),
                "retention_class": self._value(material, "retention_class"),
                "retention_policy": self._value(material, "retention_policy"),
                "retain_until": self._value(material, "retain_until"),
                "cleanup_policy": self._value(material, "cleanup_policy"),
                "shaofu_location": self._value(material, "shaofu_location"),
                "confirm_mode": self._value(material, "confirm_mode"),
                "restore_token": self._value(material, "restore_token"),
                "storage_index": self.storage_index.read().get("storage", {}),
                "material": material,
            }
            self.developer_detail.setPlainText(
                json.dumps(developer_payload, ensure_ascii=False, indent=2, sort_keys=True)
            )
    def _clear_detail(self) -> None:
        if self._record_mode == "ai" and not self._visible_materials:
            self.user_detail.setPlainText(
                "AI 指令记录尚未接入。\n\n"
                "后续这里会显示：\n"
                "- 用户自然语言指令\n"
                "- LLM 解析结果\n"
                "- 三省审议结果\n"
                "- 黑冰台 / 御史台对应事件"
            )
        elif self._record_mode == "yushitai" and not self._visible_yushitai_runs:
            self.user_detail.setPlainText("当前暂无御史台运行记录。")
        else:
            self.user_detail.setPlainText("")

        self.developer_detail.setPlainText("")
        self.undo_button.setEnabled(False)
        self.delete_button.setEnabled(False)

    def _request_delete(self) -> None:
        if self._record_mode != "shaofu":
            QMessageBox.information(self, "记录中心", "当前记录类型不支持删除。")
            return

        material = self._selected_material()
        if material is None:
            return
        reply = QMessageBox.question(
            self,
            "删除少府记录",
            "\n".join([
                "删除 = 手动删除当前选中的少府记录。",
                "",
                "这只会从少府列表中隐藏/标记删除这条记录。",
                "不会删除真实备份、隔离文件，也不会删除虚拟机或宿机文件。",
                "",
                "如果需要按规则批量整理，请使用“清理”。",
                "",
                "是否继续？",
            ]),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        controller = getattr(self.parent(), "desktop_controller", None)
        if controller is not None and hasattr(controller, "request_shaofu_delete_record"):
            result = controller.request_shaofu_delete_record(material)
        else:
            result = self._delete_record_direct(material)
        QMessageBox.information(self, "删除少府记录", str(result.get("message", "") or "-"))
        self.refresh()

    def _request_cleanup(self) -> None:
        if self._record_mode != "shaofu":
            QMessageBox.information(self, "记录中心", "当前记录类型不支持少府清理。")
            return
        environment = self._selected_environment()
        retention_days = int(self.retention_combo.currentData() or 14)

        # 先计算候选数量，用于确认提示。
        try:
            candidates = self.storage_index.cleanup_candidates(
                environment=environment,
                retention_days=retention_days,
            )
            if not isinstance(candidates, list):
                candidates = []
        except Exception:
            candidates = []

        if not candidates:
            QMessageBox.information(
                self,
                "少府清理",
                "当前没有符合清理条件的少府记录。",
            )
            return

        reply = QMessageBox.question(
            self,
            "少府清理",
            "\n".join([
                f"已找到 {len(candidates)} 条符合少府规则的可清理记录。",
                "",
                "清理规则：",
                "- 已恢复记录",
                "- 已过期记录",
                "- 不再需要保留的临时材料记录",
                "- 不可逆且已完成、无需恢复的旧记录",
                "",
                "安全边界：",
                "- 不删除真实备份文件",
                "- 不删除隔离区文件",
                "- 不删除 VM / Host 文件",
                "- 只在少府索引中标记记录为已清理",
                "",
                "是否继续？",
            ]),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        controller = getattr(self.parent(), "desktop_controller", None)
        if controller is None or not hasattr(controller, "request_shaofu_cleanup_expired"):
            QMessageBox.warning(
                self,
                "少府清理",
                "少府清理入口不可用：未找到桌面控制器。",
            )
            return

        result = controller.request_shaofu_cleanup_expired(
            environment=environment,
            retention_days=retention_days,
        )

        QMessageBox.information(
            self,
            "少府清理",
            str(result.get("message", "") or "-"),
        )
        self.refresh()

    def _request_undo(self) -> None:
        material = self._selected_material()
        if material is None or not self._can_request_undo(material):
            return
        preview = self._undo_preview(material)
        reply = QMessageBox.question(
            self,
            "少府撤回",
            "\n".join([
                "即将撤回选中的少府材料。",
                f"动作：{preview['action']}",
                f"对象：{preview['target']}",
                f"原位置：{preview['source']}",
                f"目标位置：{preview['dest']}",
                f"预计效果：{preview['effect']}",
                "",
                "是否继续？",
            ]),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        controller = getattr(self.parent(), "desktop_controller", None)
        if controller is not None and hasattr(controller, "request_shaofu_undo"):
            result = controller.request_shaofu_undo(material)
            message = str(result.get("message", "") or "撤回入口已预留，当前版本尚未执行真实恢复。")
        else:
            message = "撤回入口已预留，当前版本尚未执行真实恢复。"
        QMessageBox.information(self, "少府撤回", message)

    def _on_yushitai_backend_changed(self) -> None:
        if self._record_mode != "yushitai":
            return

        self._apply_yushitai_backend_filter()
        self._populate_summary()

        if self._visible_yushitai_runs:
            self.yushitai_run_combo.setCurrentIndex(0)
            self._show_yushitai_run_detail(self._visible_yushitai_runs[0])
        else:
            self.user_detail.setPlainText("当前暂无该环境的御史台运行记录。")
            self.developer_detail.setPlainText("")

    def _on_yushitai_run_changed(self) -> None:
        if self._record_mode != "yushitai":
            return

        run = self._selected_yushitai_run()
        if run is None:
            self._populate_summary()
            self.user_detail.setPlainText("当前暂无御史台运行记录。")
            self.developer_detail.setPlainText("")
            return

        self._populate_summary()
        self._show_yushitai_run_detail(run)

    def _on_record_mode_changed(self) -> None:
        mode = str(self.record_mode_combo.currentData() or "shaofu").strip().lower()
        if mode not in {"shaofu", "yushitai", "ai"}:
            mode = "shaofu"

        self._record_mode = mode
        self._ai_mode = mode == "ai"

        is_shaofu = mode == "shaofu"
        is_yushitai = mode == "yushitai"
        is_ai = mode == "ai"

        # 少府筛选区
        for widget in (
            self.range_label,
            self.range_combo,
            self.environment_label,
            self.environment_combo,
            self.action_label_widget,
            self.action_combo,
            self.status_label,
            self.status_combo,
            self.retention_label,
            self.retention_combo,
        ):
            widget.setVisible(is_shaofu or is_ai)

        # 御史台运行记录选择
        self.yushitai_backend_label.setVisible(is_yushitai)
        self.yushitai_backend_combo.setVisible(is_yushitai)
        self.yushitai_run_label.setVisible(is_yushitai)
        self.yushitai_run_combo.setVisible(is_yushitai)

        # 表格区域：少府 / AI 显示，御史台隐藏
        self.table.setVisible(not is_yushitai)

        # 详情标题
        if is_yushitai:
            self.detail_label.setText("运行报告")
        elif is_ai:
            self.detail_label.setText("AI 指令说明")
        else:
            self.detail_label.setText("操作说明")

        # 按钮状态
        self.cleanup_button.setEnabled(is_shaofu)
        self.delete_button.setEnabled(False)
        self.undo_button.setEnabled(False)
        self.refresh_button.setEnabled(True)

        if is_yushitai:
            self.setWindowTitle("记录中心 · 御史台运行记录")
        elif is_ai:
            self.setWindowTitle("记录中心 · AI指令")
        else:
            self.setWindowTitle("少府 · 材料管理中心")

        self.refresh()

    def _retention_changed(self) -> None:
        if self._record_mode != "shaofu":
            return
        days = int(self.retention_combo.currentData() or 14)
        controller = getattr(self.parent(), "desktop_controller", None)
        if controller is not None and hasattr(controller, "request_shaofu_update_retention_days"):
            controller.request_shaofu_update_retention_days(days)
        else:
            self.storage_index.update_retention_days(days)
        self._apply_filters()

    def _load_retention_policy(self) -> None:
        days = self.storage_index.get_retention_days()
        if days not in {7, 14, 30}:
            days = 14
        self._select_combo_data(self.retention_combo, days)

    def _load_yushitai_runs(self) -> list[dict[str, Any]]:
        root = Path(self.project_root or ".").expanduser().resolve(strict=False)
        yushitai_runs_dir = root / "data" / "runtime" / "desktop" / "yushitai" / "runs"

        results: list[dict[str, Any]] = []

        for backend in ("host", "vm"):
            backend_dir = yushitai_runs_dir / backend
            if not backend_dir.exists() or not backend_dir.is_dir():
                continue

            for run_dir in backend_dir.iterdir():
                if not run_dir.is_dir():
                    continue

                run_meta_path = run_dir / "run_meta.json"
                run_meta = self._read_json_file(run_meta_path)

                run_id = str(run_meta.get("run_id", run_dir.name) or run_dir.name)
                status = str(run_meta.get("status", "") or "").strip() or "unknown"
                started_at = str(run_meta.get("started_at", "") or "")
                closed_at = str(run_meta.get("closed_at", "") or "")

                events_path = run_dir / "events.jsonl"
                event_count = self._count_jsonl_lines(events_path)

                reports_dir = run_dir / "reports"
                report_files = []
                if reports_dir.exists() and reports_dir.is_dir():
                    report_files = sorted(
                        [path for path in reports_dir.glob("*.md") if path.is_file()],
                        key=lambda path: path.stat().st_mtime,
                        reverse=True,
                    )

                has_report = bool(report_files)

                results.append({
                    "run_id": run_id,
                    "backend": backend,
                    "status": status,
                    "started_at": started_at,
                    "closed_at": closed_at,
                    "run_dir": str(run_dir),
                    "run_meta_path": str(run_meta_path),
                    "events_path": str(events_path),
                    "event_count": event_count,
                    "reports_dir": str(reports_dir),
                    "report_files": [str(path) for path in report_files],
                    "has_report": has_report,
                    "run_meta": run_meta,
                })

        def sort_key(item: dict[str, Any]) -> str:
            return str(item.get("started_at") or item.get("run_id") or "")

        return sorted(results, key=sort_key, reverse=True)
    
    def _yushitai_combo_label(self, run: dict[str, Any]) -> str:
        started_at = str(run.get("started_at", "") or "-")
        run_id = str(run.get("run_id", "") or "-")
        backend = str(run.get("backend", "") or "-")
        status = self._yushitai_status_label(str(run.get("status", "") or ""))
        event_count = int(run.get("event_count", 0) or 0)

        return f"{started_at} | {run_id} | {backend} | {status} | 事件 {event_count}"

    def _yushitai_row_values(self, run: dict[str, Any]) -> list[str]:
        return [
            str(run.get("started_at", "") or "-"),
            str(run.get("run_id", "") or "-"),
            str(run.get("backend", "") or "-"),
            self._yushitai_status_label(str(run.get("status", "") or "")),
            str(run.get("event_count", 0) or 0),
            "有报告" if bool(run.get("has_report", False)) else "无报告",
        ]

    def _selected_yushitai_run(self) -> dict[str, Any] | None:
        if not self._visible_yushitai_runs:
            return None

        index_data = self.yushitai_run_combo.currentData()
        try:
            index = int(index_data)
        except Exception:
            index = self.yushitai_run_combo.currentIndex()

        if index < 0 or index >= len(self._visible_yushitai_runs):
            return None

        return self._visible_yushitai_runs[index]

    def _read_yushitai_report(self, run: dict[str, Any]) -> str:
        report_files = run.get("report_files", [])
        if isinstance(report_files, list):
            for file in report_files:
                path = Path(str(file))
                if path.exists() and path.is_file():
                    try:
                        return path.read_text(encoding="utf-8")
                    except UnicodeDecodeError:
                        return path.read_text(encoding="utf-8-sig", errors="replace")
                    except Exception as exc:
                        return f"读取御史台报告失败：{exc}"

        meta = run.get("run_meta", {})
        meta = meta if isinstance(meta, dict) else {}

        return "\n".join([
            "# 御史台运行记录",
            "",
            f"- 运行ID：{run.get('run_id', '-')}",
            f"- 环境：{run.get('backend', '-')}",
            f"- 状态：{self._yushitai_status_label(str(run.get('status', '') or ''))}",
            f"- 开始时间：{run.get('started_at', '-')}",
            f"- 关闭时间：{run.get('closed_at', '-') or '-'}",
            f"- 事件数量：{run.get('event_count', 0)}",
            "",
            "当前 run 暂无 Markdown 报告。",
            "",
            "后续这里会显示 reports/ 下的 md 报告内容。",
        ])


    def _yushitai_developer_payload(self, run: dict[str, Any]) -> dict[str, Any]:
        run_dir = Path(str(run.get("run_dir", "") or ""))
        events_path = Path(str(run.get("events_path", "") or ""))

        events_tail: list[Any] = []
        if events_path.exists() and events_path.is_file():
            try:
                lines = events_path.read_text(encoding="utf-8").splitlines()
            except UnicodeDecodeError:
                lines = events_path.read_text(encoding="utf-8-sig", errors="replace").splitlines()
            except Exception:
                lines = []

            for line in lines[-20:]:
                text = line.strip()
                if not text:
                    continue
                try:
                    events_tail.append(json.loads(text))
                except Exception:
                    events_tail.append(text)

        snapshots = []
        snapshots_dir = run_dir / "snapshots"
        if snapshots_dir.exists() and snapshots_dir.is_dir():
            snapshots = [path.name for path in sorted(snapshots_dir.iterdir()) if path.is_file()]

        attachments = []
        attachments_dir = run_dir / "attachments"
        if attachments_dir.exists() and attachments_dir.is_dir():
            attachments = [path.name for path in sorted(attachments_dir.iterdir()) if path.is_file()]

        reports = []
        reports_dir = run_dir / "reports"
        if reports_dir.exists() and reports_dir.is_dir():
            reports = [path.name for path in sorted(reports_dir.iterdir()) if path.is_file()]

        return {
            "run_id": run.get("run_id", ""),
            "backend": run.get("backend", ""),
            "status": run.get("status", ""),
            "run_dir": run.get("run_dir", ""),
            "run_meta": run.get("run_meta", {}),
            "event_count": run.get("event_count", 0),
            "events_tail": events_tail,
            "reports": reports,
            "snapshots": snapshots,
            "attachments": attachments,
        }


    def _read_json_file(self, path: Path) -> dict[str, Any]:
        if not path.exists() or not path.is_file():
            return {}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except UnicodeDecodeError:
            try:
                data = json.loads(path.read_text(encoding="utf-8-sig"))
                return data if isinstance(data, dict) else {}
            except Exception:
                return {}
        except Exception:
            return {}


    def _count_jsonl_lines(self, path: Path) -> int:
        if not path.exists() or not path.is_file():
            return 0
        try:
            return len([line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()])
        except UnicodeDecodeError:
            try:
                return len([line for line in path.read_text(encoding="utf-8-sig", errors="replace").splitlines() if line.strip()])
            except Exception:
                return 0
        except Exception:
            return 0


    def _yushitai_status_label(self, status: str) -> str:
        normalized = str(status or "").strip().lower()
        mapping = {
            "running": "运行中",
            "closed": "已关闭",
            "interrupted": "已中断",
            "failed": "失败",
            "unknown": "未知",
        }
        return mapping.get(normalized, normalized or "未知")

    def _selected_material(self) -> dict[str, Any] | None:
        row = self.table.currentRow()
        if row < 0 or row >= len(self._visible_materials):
            return None
        return self._visible_materials[row]

    def _matches_action_filter(self, item: dict[str, Any], action_filter: str) -> bool:
        action = self._action(item)
        if action_filter == "software_relocate":
            return self._is_software_relocate_action(item)
        if action_filter == "other":
            known = {"file.delete", "file.move", "file.rename", "app.uninstall", "app.update", "app.relocate"}
            return action not in known and not self._is_software_relocate_action(item)
        return action == action_filter

    def _matches_status_filter(self, item: dict[str, Any], status_filter: str) -> bool:
        material_status = self._normalized(self._value(item, "material_status"))
        restore_status = self._normalized(self._value(item, "restore_status"))
        verify_status = self._normalized(self._value(item, "verify_status"))
        if status_filter == "undoable":
            return self._can_request_undo(item)
        if status_filter == "not_undoable":
            return not self._can_request_undo(item)
        if status_filter == "unverified":
            return verify_status == "unverified"
        if status_filter == "expired":
            return self._is_expired(item)
        if status_filter == "failed":
            return material_status == "failed" or restore_status == "failed" or bool(self._value(item, "error"))
        return True

    def _user_description(self, item: dict[str, Any]) -> str:
        if self._ai_mode:
            return "\n".join([
                "AI 指令记录：",
                f"- 指令内容：{self._ai_command_text(item) or '-'}",
                f"- 来源：{self._value(item, 'command_source') or '-'}",
                f"- 是否成功：{'是' if self._truthy(self._value(item, 'command_success')) else '否'}",
            ])
        action = self._action(item)
        if action == "file.delete":
            effect = "尝试把文件从少府隔离区恢复到原位置"
            risk = "如果原位置已有同名文件，撤回可能被阻止"
        elif action == "file.move":
            effect = "尝试把文件从目标位置移回原位置"
            risk = "如果原位置或目标位置状态已变化，撤回可能失败"
        elif action == "file.rename":
            effect = "尝试恢复旧名称"
            risk = "如果旧名称已被占用，撤回可能被阻止"
        elif self._is_software_relocate_action(item):
            effect = "尝试恢复软件目录和相关路径信息"
            risk = "软件迁移涉及注册表、快捷方式和服务路径，本阶段仅预览撤回"
        elif action == "app.uninstall":
            effect = "本阶段不支持一键撤回软件卸载"
            risk = "建议手动重装或使用系统快照"
        else:
            effect = "当前动作没有接入少府撤回"
            risk = "仅保留材料查看"
        return "\n".join([
            "操作说明：",
            f"- 动作：{self._action_label(item)}",
            f"- 对象：{self._target_name(item)}",
            f"- 执行位置：{self._execution_location(item)}",
            f"- 执行情况：{self._execution_status(item)}",
            f"- 可撤回：{'是' if self._can_request_undo(item) else '否'}",
            f"- 恢复状态：{self._restore_status_label(item)}",
            f"- 保留时间：{self._retention_until_label(item)}",
            f"- 撤回效果：{effect}",
            f"- 风险提示：{risk}",
        ])

    def _undo_preview(self, item: dict[str, Any]) -> dict[str, str]:
        action = self._action(item)
        if action == "file.delete":
            effect = "尝试把文件从少府隔离区恢复到原位置"
        elif action == "file.move":
            effect = "尝试把文件从目标位置移回原位置"
        elif action == "file.rename":
            effect = "尝试恢复旧名称"
        else:
            effect = "预览软件迁移撤回；当前版本尚未执行真实恢复"
        return {
            "action": self._action_label(item),
            "target": self._target_name(item),
            "source": self._source_path(item),
            "dest": self._dest_path(item),
            "effect": effect,
        }

    def _can_request_undo(self, item: dict[str, Any]) -> bool:
        action = self._action(item)
        if action == "app.uninstall" or action == "app.update" or action in {"app.launch", "app.close", "app.locate"}:
            return False
        if self._normalized(self._value(item, "material_status")) in {"failed", "missing_strategy"}:
            return False
        if self._normalized(self._value(item, "restore_status")) in {"restored", "cleaned", "expired", "failed"}:
            return False
        if self._is_expired(item):
            return False
        if not self._field_present(item, "checkpoint_id") and not self._field_present(item, "material_id"):
            return False
        if action == "file.delete":
            return self._has_paths(item, ("source_path",), ("quarantine_path",))
        if action in {"file.move", "file.rename"}:
            return self._has_paths(item, ("source_path",), ("dest_path",))
        if self._is_software_relocate_action(item):
            return self._has_paths(item, ("source_path",), ("dest_path", "backup_original_path"))
        return False

    def _restore_status_label(self, item: dict[str, Any]) -> str:
        restore_status = self._normalized(self._value(item, "restore_status"))

        if restore_status == "restored":
            return "已恢复"
        if restore_status == "failed":
            return "恢复失败"
        if restore_status == "expired" or self._is_expired(item):
            return "已过期"
        if restore_status in {"cleaned", "deleted"}:
            return "已清理"

        if self._action(item) in {"app.uninstall", "app.update", "app.launch", "app.close", "app.locate"}:
            return "不可撤回"

        if self._can_request_undo(item):
            return "可撤回"

        return "不可撤回"

    def _execution_status(self, item: dict[str, Any]) -> str:
        values = {
            self._normalized(self._value(item, "material_status")),
            self._normalized(self._value(item, "relocate_status")),
            self._normalized(self._value(item, "execution_status")),
            self._normalized(self._value(item, "status")),
            self._normalized(self._value(item, "error")),
            self._normalized(self._value(item, "error_category")),
        }

        if values & {"success", "completed", "ok", "done", "closed", "restored", "path_verified"}:
            return "已完成"

        if values & {"process_path_still_in_use", "source_path_in_use"}:
            return "后台占用"

        if values & {"pending", "ready", "prepared", "quarantined"}:
            return "待确认"

        if values & {"cancelled", "canceled"}:
            return "已取消"

        if values & {
            "failed",
            "error",
            "copy_failed",
            "service_stop_failed",
            "process_close_failed",
            "original_rename_failed",
            "preflight_failed",
        }:
            return "失败"

        if bool(self._value(item, "error")) or bool(self._value(item, "error_category")):
            return "失败"

        return "未完成"

    def _retention_until_label(self, item: dict[str, Any]) -> str:
        retain_until = self._value(item, "retain_until")

        if retain_until:
            if retain_until == "project_close":
                return "项目关闭"
            if retain_until == "vm_close":
                return "VM 关闭"
            if retain_until == "long_term_report":
                return "长期保留"
            if retain_until == "manual_only":
                return "仅手动"
            parsed_retain = self._parse_datetime(retain_until)
            return parsed_retain.date().isoformat() if parsed_retain else retain_until

        if self._truthy(item.get("keep", False)):
            return "长期保留"

        cleanup_policy = self._normalized(self._value(item, "cleanup_policy"))
        retention_class = self._normalized(self._value(item, "retention_class"))
        verify_status = self._normalized(self._value(item, "verify_status"))

        if cleanup_policy == "manual_only":
            return "仅手动"
        if retention_class == "permanent_index":
            return "长期索引"
        if cleanup_policy == "cleanup_on_exit":
            return "退出清理"
        if cleanup_policy == "never_until_verified" or (retention_class == "critical_long" and verify_status == "unverified"):
            return "验证前保留"

        expire_at = self._value(item, "expire_at")
        if expire_at:
            parsed = self._parse_datetime(expire_at)
            return parsed.date().isoformat() if parsed else expire_at[:10]

        created = self._parse_datetime(self._value(item, "created_at"))
        if not created:
            return "-"

        days = int(self.retention_combo.currentData() or 14)
        return f"{days} 天"

    def _is_expired(self, item: dict[str, Any]) -> bool:
        expire_at = self._value(item, "expire_at")
        if not expire_at:
            return False
        parsed = self._parse_datetime(expire_at)
        return bool(parsed and parsed < datetime.now(timezone.utc))

    def _parse_datetime(self, value: str) -> datetime | None:
        text = str(value or "").strip()
        if not text:
            return None
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed
        except Exception:
            return None
    
    def _delete_record_direct(self, material: dict[str, Any]) -> dict[str, Any]:
        material_id = self._value(material, "material_id")
        checkpoint_id = self._value(material, "checkpoint_id")
        registry_result = self.registry.mark_record_deleted(material_id=material_id, checkpoint_id=checkpoint_id)
        index_result = self.storage_index.mark_record_deleted(material_id=material_id, checkpoint_id=checkpoint_id)
        ok = bool(registry_result.get("ok", False) or index_result.get("ok", False))
        return {"ok": ok, "message": "已删除少府记录。真实材料没有被删除。" if ok else "未找到可删除的少府记录。"}

    def _environment_for(self, item: dict[str, Any]) -> str:
        execution_backend = self._normalized(self._value(item, "execution_backend"))
        target_environment = self._normalized(self._value(item, "target_environment"))
        path_namespace = self._normalized(self._value(item, "path_namespace"))
        if execution_backend == "vm" or target_environment == "virtual_machine" or path_namespace == "vm_windows":
            return "vm"
        if execution_backend == "host" or target_environment in {"local_host", "host_machine"} or path_namespace == "host_windows":
            return "host"
        if execution_backend == "sandbox" or target_environment == "sandbox_simulation" or path_namespace == "sandbox":
            return "sandbox"
        return "unknown"

    def _is_software_relocate_action(self, item: dict[str, Any]) -> bool:
        action = self._action(item)
        return action == "app.relocate" or (action == "app.move" and self._is_legacy_software_relocate(item))

    def _is_legacy_software_relocate(self, item: dict[str, Any]) -> bool:
        text = " ".join([
            self._normalized(self._value(item, "move_mode")),
            self._normalized(self._value(item, "relocate_strategy")),
            self._normalized(self._value(item, "material_type")),
        ])
        return "installed_app_relocate" in text or "relocate" in text or "relocation" in text

    def _has_paths(self, item: dict[str, Any], *path_groups: tuple[str, ...]) -> bool:
        for group in path_groups:
            if not any(self._field_present(item, key) for key in group):
                return False
        return True

    def _field_present(self, item: dict[str, Any], key: str) -> bool:
        value = self._value(item, key)
        return bool(value and value not in {"-", "__vm_agent_auto__", "__vm_agent_select__", "__pending__"})

    def _action_label(self, item: dict[str, Any]) -> str:
        action = self._action(item)
        return self.ACTION_LABELS.get(action, action or "其他")

    def _target_name(self, item: dict[str, Any]) -> str:
        """
        普通用户看到的对象名。

        优先显示用户认识的名字：
        - target_name / app_name / title / name
        - 其次从路径中取文件名或文件夹名
        - 最后才显示 target_id
        """
        for key in ("target_name", "app_name", "title", "name", "object_name"):
            value = self._value(item, key)
            if value:
                return value

        for key in (
            "target_path",
            "source_path",
            "original_path",
            "backup_original_path",
            "dest_path",
            "quarantine_path",
        ):
            value = self._value(item, key)
            if value:
                try:
                    name = Path(value).name
                    if name:
                        return name
                except Exception:
                    pass

        return self._value(item, "target_id") or "-"

    def _source_path(self, item: dict[str, Any]) -> str:
        return self._display_path(self._value(item, "source_path") or self._value(item, "backup_original_path") or "-")

    def _execution_location(self, item: dict[str, Any]) -> str:
        """
        普通用户表格中的“执行位置”。

        优先显示动作发生的位置：
        - source_path / original_path / target_path
        - backup_original_path
        - dest_path
        """
        for key in (
            "source_path",
            "original_path",
            "target_path",
            "backup_original_path",
            "path",
            "dest_path",
            "quarantine_path",
        ):
            value = self._value(item, key)
            if value:
                return self._display_path(value)
        return "-"

    def _dest_path(self, item: dict[str, Any]) -> str:
        return self._display_path(self._value(item, "dest_path") or self._value(item, "quarantine_path") or "-")

    def _confirm_mode_label(self, item: dict[str, Any]) -> str:
        mode = self._normalized(self._value(item, "confirm_mode"))
        if mode == "vm_auto_confirm":
            return "测试自动"
        if mode == "user_confirmed":
            return "用户确认"
        if mode == "user_rejected":
            return "用户拒绝"
        return "无"

    def _selected_environment(self) -> str:
        return str(self.environment_combo.currentData() or self.current_environment or "vm")

    def _ai_command_text(self, item: dict[str, Any]) -> str:
        return self._value(item, "ai_command_text")

    def _action(self, item: dict[str, Any]) -> str:
        return self._normalized(self._value(item, "action"))

    def _display_path(self, value: str) -> str:
        text = str(value or "").strip()
        if not text or text == "-":
            return "-"
        normalized = text.replace("/", "\\").lower()
        if "temp\\shaofu" in normalized or "runtime\\desktop\\shaofu" in normalized or normalized.startswith("vm_shaofu://"):
            return "少府临时材料"
        return text

    def _value(self, item: dict[str, Any], key: str) -> str:
        value = item.get(key, "")
        if value in (None, ""):
            data = item.get("data", {}) if isinstance(item.get("data"), dict) else {}
            value = data.get(key, "")
        return "" if value in (None, "") else str(value)

    def _normalized(self, value: Any) -> str:
        return str(value or "").strip().lower()

    def _truthy(self, value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return value != 0
        return str(value or "").strip().lower() in {"1", "true", "yes", "y", "on", "是", "成功"}

    def _format_size(self, value: int) -> str:
        size = max(0, int(value or 0))
        units = ["B", "KB", "MB", "GB", "TB"]
        amount = float(size)
        for unit in units:
            if amount < 1024 or unit == units[-1]:
                return f"{amount:.1f} {unit}" if unit != "B" else f"{int(amount)} B"
            amount /= 1024
        return f"{size} B"

    def _select_combo_data(self, combo: QComboBox, value: Any) -> None:
        for index in range(combo.count()):
            if combo.itemData(index) == value:
                combo.setCurrentIndex(index)
                return
