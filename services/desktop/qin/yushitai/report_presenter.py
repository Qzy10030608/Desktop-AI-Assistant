from __future__ import annotations

from typing import Any


ACTION_LABELS = {
    "file.delete": "文件删除",
    "file.move": "文件移动",
    "file.rename": "文件重命名",
    "app.relocate": "软件迁移",
    "app.move": "软件移动/旧迁移",
    "app.uninstall": "软件卸载",
    "app.update": "软件更新",
    "app.launch": "软件启动",
    "app.close": "软件关闭",
    "app.locate": "软件定位",
}

ERROR_LABELS = {
    "process_path_still_in_use": "软件后台占用",
    "source_path_in_use": "原目录被占用",
    "original_rename_failed": "原目录备份失败",
    "original_rename_failed_winerror32": "原目录被占用",
    "admin_required": "需要管理员权限",
    "destination_exists": "目标目录已存在",
    "service_stop_failed": "服务停止失败",
    "process_close_failed": "进程关闭失败",
    "copy_failed": "复制失败",
    "file_locked_or_access_denied": "文件被占用或权限不足",
    "registry_update_failed": "注册表路径更新失败",
    "service_update_failed": "服务路径更新失败",
    "shortcut_update_failed": "快捷方式更新失败",
    "move_update_paths_not_implemented": "迁移执行层未启用",
}


class ReportPresenter:
    """Format Yushitai reports for humans."""

    def summary_card(self, report: dict[str, Any]) -> dict[str, str]:
        summary = report.get("summary", {}) if isinstance(report.get("summary"), dict) else {}
        system = report.get("system_state", {}) if isinstance(report.get("system_state"), dict) else {}
        return {
            "title": "御史台监察报告",
            "status": str(summary.get("overall_status", "unknown")),
            "body": (
                f"后端={system.get('current_backend', '-')}，"
                f"模式={system.get('governance_mode', '-')}，"
                f"VM连接={system.get('vm_connected', False)}，"
                f"VM软件数量={system.get('vm_software_count', 0)}"
            ),
        }

    def to_markdown(self, report: dict[str, Any]) -> str:
        metadata = report.get("metadata", {}) if isinstance(report.get("metadata"), dict) else {}
        summary = report.get("summary", {}) if isinstance(report.get("summary"), dict) else {}
        system = report.get("system_state", {}) if isinstance(report.get("system_state"), dict) else {}
        matrix = report.get("exit_matrix", {}) if isinstance(report.get("exit_matrix"), dict) else {}
        vm_quality = report.get("vm_quality", {}) if isinstance(report.get("vm_quality"), dict) else {}
        checkpoints = report.get("checkpoints", {}) if isinstance(report.get("checkpoints"), dict) else {}
        recommendations = report.get("recommendations", []) if isinstance(report.get("recommendations"), list) else []
        failures = report.get("recent_failures", []) if isinstance(report.get("recent_failures"), list) else []

        lines = [
            "# 御史台监察报告",
            "",
            f"- 报告 ID：`{metadata.get('report_id', '-')}`",
            f"- 测试阶段：`{metadata.get('stage', '-')}`",
            f"- 创建时间：`{metadata.get('created_at', '-')}`",
            f"- 总体状态：`{summary.get('overall_status', '-')}`",
            "",
            "## 当前系统状态",
            f"- 当前出口：`{system.get('current_backend', '-')}`",
            f"- 治理模式：`{system.get('governance_mode', '-')}`",
            f"- Host 执行：`{system.get('host_execution_enabled', False)}`",
            f"- VM 连接：`{system.get('vm_connected', False)}`",
            f"- VM 软件数量：`{system.get('vm_software_count', 0)}`",
            (
                "- VM 软件 raw/final/hidden："
                f"`{system.get('vm_software_raw_count', 0)} / "
                f"{system.get('vm_software_final_count', system.get('vm_software_count', 0))} / "
                f"{system.get('vm_software_hidden_count', 0)}`"
            ),
            "",
            "## 三出口测试结果",
            f"- 沙盒动作数量：`{matrix.get('sandbox_actions', 0)}`",
            f"- 虚拟机动作数量：`{matrix.get('vm_actions', 0)}`",
            f"- Host 阻断动作数量：`{matrix.get('host_blocked_actions', 0)}`",
            "",
            "## VM 连接质量",
            f"- 尝试次数：`{vm_quality.get('vm_connect_attempts', 0)}`",
            f"- 成功次数：`{vm_quality.get('vm_connect_success', 0)}`",
            f"- 失败次数：`{vm_quality.get('vm_connect_failed', 0)}`",
            f"- 平均耗时：`{vm_quality.get('avg_vm_connect_duration_ms', 0)}` ms",
            f"- VM 软件数量：`{vm_quality.get('vm_software_count', 0)}`",
            f"- 合并卸载器数量：`{vm_quality.get('vm_software_merged_uninstallers', 0)}`",
            "",
            "## 恢复点 / 材料",
            f"- 活跃恢复点：`{checkpoints.get('active_checkpoints', 0)}`",
            "",
            "## 最近失败与异常",
        ]

        if failures:
            for item in failures[-10:]:
                lines.extend(self._failure_lines(item))
        else:
            lines.append("- 暂无")

        lines.extend(["", "## 下一步建议"])
        for item in recommendations:
            lines.append(f"- {item}")
        return "\n".join(lines) + "\n"

    def _failure_lines(self, item: dict[str, Any]) -> list[str]:
        action = self._action_label(item.get("action", "-"))
        target_name = str(item.get("target_name", "") or "-")
        error_raw = str(item.get("error", "") or item.get("error_category", "") or item.get("reason", "") or "-")
        error = self._error_label(error_raw)
        http_status = str(item.get("http_status", "") or "-")
        checkpoint_id = str(item.get("checkpoint_id", "") or "-")
        material_id = str(item.get("material_id", "") or "-")
        relocate_status = str(item.get("relocate_status", "") or "")
        move_mode = str(item.get("move_mode", "") or "")
        advice = self._failure_advice(error_raw)

        lines = [
            f"- 动作：{action} / 对象：{target_name}",
            f"  错误：{error} / HTTP：{http_status}",
            f"  恢复点：`{checkpoint_id}` / 材料：`{material_id}`",
        ]
        if move_mode or relocate_status:
            lines.append(f"  模式：`{move_mode or '-'}` / 状态：`{relocate_status or '-'}`")
        if advice:
            lines.append(f"  建议：{advice}")
        return lines

    def _action_label(self, value: Any) -> str:
        text = str(value or "-").strip()
        return ACTION_LABELS.get(text, text or "-")

    def _error_label(self, value: Any) -> str:
        text = str(value or "-").strip()
        return ERROR_LABELS.get(text, text or "-")

    def _failure_advice(self, error: str) -> str:
        key = str(error or "").strip().lower()
        if key in {"process_path_still_in_use", "source_path_in_use", "original_rename_failed_winerror32"}:
            return "请在虚拟机中完全退出软件，包括托盘图标、后台进程和相关服务后重试。"
        if key == "original_rename_failed":
            return "原安装目录无法改名为备份目录，请确认软件已完全退出后重试。"
        if key == "process_close_failed":
            return "系统尝试关闭软件进程失败，请在虚拟机中手动退出软件后重试。"
        if key == "service_stop_failed":
            return "系统尝试停止相关服务失败，请手动停止服务或重启虚拟机后重试。"
        if key == "admin_required":
            return "请以管理员权限运行 VM Agent 后再迁移已安装软件。"
        if key == "destination_exists":
            return "目标目录已存在同名软件文件夹，请选择空目录或先清理测试目录。"
        if key == "copy_failed":
            return "复制软件目录失败，请检查磁盘空间、权限和目标目录状态。"
        return ""
