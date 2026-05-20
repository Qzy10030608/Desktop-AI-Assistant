from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from PySide6.QtCore import QThread, QTimer
from PySide6.QtWidgets import QFileDialog, QInputDialog, QMessageBox

from services.desktop.software_view_cache_service import SoftwareViewCacheService
from services.desktop.file_view_cache_service import FileViewCacheService
from services.desktop.qin.libu.vm_app_normalizer import normalize_vm_apps
from services.desktop.qin.libu.vm_connection_memory import VmConnectionMemoryStore
from services.desktop.qin.hubu.desktop_metrics_service import DesktopMetricsService
from services.desktop.qin.yushitai.event_store import YushitaiEventStore
from services.desktop.qin.yushitai.report_writer import ReportWriter
from services.desktop.qin.gongbu.adapters.vm_adapter import get_default_vm_adapter
from services.desktop.tianting.vm_bridge.vm_connect_worker import VmConnectWorker

from ui.control_center.desktop.runtime import DesktopPageRuntime
from ui.control_center.desktop.software_scan_worker import SoftwareScanWorker
from ui.control_center.desktop.host_files_refresh_worker import HostFilesRefreshWorker
from ui.control_center.desktop.vm_apps_refresh_worker import VmAppsRefreshWorker
from ui.control_center.desktop.vm_files_refresh_worker import VmFilesRefreshWorker

class DesktopController:
    def __init__(self, window, *, runtime: DesktopPageRuntime | None = None) -> None:
        self.w = window
        self.runtime = runtime or DesktopPageRuntime(window)
        self._software_scan_fake_timer = QTimer(self.w)
        self._software_scan_fake_timer.setInterval(120)
        self._software_scan_fake_timer.timeout.connect(self._tick_software_scan_fake_progress)
        self._last_software_scan_request: tuple[str, float] = ("", 0.0)
        self.software_view_cache = SoftwareViewCacheService(self.runtime.project_root)
        self.file_view_cache = FileViewCacheService(self.runtime.project_root)

    @property
    def service(self):
        return self.runtime.service

    @property
    def qin_runtime(self):
        return self.runtime.qin_runtime

    def reload_page(self) -> None:
        self._remember_desktop_page_scroll()
        self._remember_table_scrolls()
        self.w.desktop_page_loader.load_page()

    def refresh_mode_only(self) -> None:
        loader = getattr(self.w, "desktop_page_loader", None)
        if loader is not None and hasattr(loader, "refresh_mode_controls"):
            loader.refresh_mode_controls()
            return
        self.reload_page()

    def reload_software_panel(self) -> None:
        if bool(getattr(self.runtime, "software_table_rendering", False)):
            self.runtime.software_refresh_pending = True
            return

        self._remember_software_area_scroll()
        self.w.desktop_page_loader.load_software_panel()
        self._restore_software_area_scroll_later()

    def load_software_memory_records(self) -> None:
        """
        兼容旧按钮“刷新列表 / 加载上次记录”。
        - 不重新扫描
        - 不重新 merge
        - 只读取 software_view_cache.json
        """
        self.load_software_view_cache()

    def load_software_view_cache(self) -> None:
        """
        加载软件列表。

        规则：
        - Host / sandbox：读取 Host 软件缓存 software_view_cache.json
        - VM：读取 runtime.vm_apps_result，不允许回退到 Host 缓存
        """
        self._remember_software_area_scroll()

        loader = getattr(self.w, "desktop_page_loader", None)
        if loader is None:
            return

        if self._vm_software_context_ready():
            state = self.get_vm_software_governance_state()
            rows = state.get("rows", []) if isinstance(state.get("rows", []), list) else []

            self.runtime.software_cache_state = state
            self.runtime.software_cache_loaded = bool(rows)
            self.runtime.software_cache_source = "vm"
            self.runtime.software_last_state = dict(state)
            self.runtime.software_table_loaded = bool(rows)

            loader.load_software_panel(
                software_state=state,
                force_full=bool(rows),
            )
            self._restore_software_area_scroll_later()
            return

        cached = self.software_view_cache.read()
        rows = cached.get("rows", []) if isinstance(cached.get("rows", []), list) else []

        self.runtime.software_cache_state = cached
        self.runtime.software_cache_loaded = bool(rows)
        self.runtime.software_cache_source = str(cached.get("source", "empty") or "empty")
        self.runtime.software_last_state = dict(cached)
        self.runtime.software_table_loaded = bool(rows)

        loader.load_software_panel(
            software_state=cached,
            force_full=bool(rows),
        )
        self._restore_software_area_scroll_later()

    def _host_software_view_mode(self) -> str:
        """
        软件区显示数据源模式。

        规则：
        - 信任模式：显示 Host 软件治理数据
        - 测试模式 + sandbox：仍显示 Host 软件治理数据，只是执行出口走 sandbox
        - 测试模式 + vm：不走这里，VM 有独立 get_vm_software_governance_state()
        """
        if self._is_test_mode() and self._effective_test_backend() == "sandbox":
            return "trusted"
        return self._current_mode()

    def rebuild_and_save_software_view_cache(self, *, scan_profile: str = "") -> dict:
        """
        扫描完成后生成最终 UI state 并写入缓存。

        注意：
        - sandbox 测试模式显示的是 Host 软件数据；
        - sandbox 只改变执行出口，不应该把软件显示数据源改成 VM/test 空状态。
        """
        view_mode = self._host_software_view_mode()

        state = self.service.get_software_governance_state(
            mode=view_mode,
            filter_key=self.current_filter_key(),
            editable=self.runtime.apps_editable,
        )

        # 当前真实 desktop mode 仍保留，方便 UI/日志判断。
        state = dict(state or {})
        state["desktop_mode"] = self._current_mode()
        state["software_view_mode"] = view_mode
        state["execution_backend"] = self.software_action_backend()

        cached = self.software_view_cache.write(
            state,
            scan_profile=scan_profile,
            source="cache",
        )
        return cached

    def reload_software_scan_status(self) -> None:
        self.w.desktop_page_loader.refresh_software_scan_status()

    def desktop_actions_available(self) -> bool:
        return bool(self.effective_execution_backend())
    def host_execution_enabled(self) -> bool:
        try:
            runtime_state = self.service.mode_store.get_runtime_state()
        except Exception:
            runtime_state = {}
        return bool(runtime_state.get("host_execution_enabled", False))

    def effective_execution_backend(self) -> str:
        if self._is_test_mode():
            return self._effective_test_backend() or "sandbox"

        try:
            mode = self._current_mode()
        except Exception:
            mode = "disabled"

        if mode == "trusted":
            return "host"

        return ""

    def software_action_backend(self, row: dict | None = None) -> str:
        """
        软件治理区按钮使用的轻量出口。

        trusted 模式直接代表 Host 真实执行；sandbox 只存在于 test 模式。
        """
        if self._is_test_mode():
            return self._effective_test_backend() or "sandbox"

        try:
            mode = self._current_mode()
        except Exception:
            mode = "disabled"

        if mode == "trusted":
            return "host"

        return ""

    def _show_desktop_actions_unavailable(self) -> None:
        QMessageBox.information(
            self.w,
            "桌面连接",
            "当前桌面模式不允许执行该动作。",
        )

    def open_shaofu_viewer(self) -> None:
        try:
            from ui.control_center.desktop.shaofu_viewer_dialog import ShaofuViewerDialog

            dialog = getattr(self, "_shaofu_viewer_dialog", None)
            if dialog is None:
                project_root = getattr(self.qin_runtime, "project_root", None)
                current_environment = "vm" if self._is_vm_test_backend() else "host"
                dialog = ShaofuViewerDialog(self.w, project_root=project_root, current_environment=current_environment)
                self._shaofu_viewer_dialog = dialog
            elif hasattr(dialog, "set_current_environment"):
                current_environment = "vm" if self._is_vm_test_backend() else "host"
                dialog.set_current_environment(current_environment)
            dialog.show()
            dialog.raise_()
            dialog.activateWindow()
            QTimer.singleShot(0, lambda dialog=dialog: self._refresh_shaofu_dialog(dialog))
        except Exception as exc:
            QMessageBox.warning(self.w, "记录", f"打开记录窗口失败：\n{exc}")

    def _refresh_shaofu_dialog(self, dialog) -> None:
        try:
            dialog.refresh()
        except Exception as exc:
            QMessageBox.warning(self.w, "记录", f"刷新记录窗口失败：\n{exc}")

    def request_shaofu_undo(self, material: dict) -> dict:
        return {
            "ok": False,
            "message": "撤回入口已预留，当前版本尚未执行真实恢复。",
            "preview_only": True,
            "material_id": str((material or {}).get("material_id", "") or ""),
            "checkpoint_id": str((material or {}).get("checkpoint_id", "") or ""),
        }

    def request_shaofu_delete_record(self, material: dict) -> dict:
        try:
            from services.desktop.qin.shaofu.restore_registry import RestoreRegistry
            from services.desktop.qin.shaofu.storage_index import StorageIndex

            project_root = getattr(self.qin_runtime, "project_root", None)
            material_id = str((material or {}).get("material_id", "") or "").strip()
            checkpoint_id = str((material or {}).get("checkpoint_id", "") or "").strip()
            registry_result = RestoreRegistry(project_root).mark_record_deleted(
                material_id=material_id,
                checkpoint_id=checkpoint_id,
                reason="user_deleted_record",
            )
            index_result = StorageIndex(project_root).mark_record_deleted(
                material_id=material_id,
                checkpoint_id=checkpoint_id,
                reason="user_deleted_record",
            )
            ok = bool(registry_result.get("ok", False) or index_result.get("ok", False))
            return {
                "ok": ok,
                "message": "已删除少府记录。真实备份、隔离文件以及 VM/Host 文件均未删除。" if ok else "未找到可删除的少府记录。",
                "registry": registry_result,
                "storage_index": index_result,
            }
        except Exception as exc:
            return {"ok": False, "message": f"删除少府记录失败：{exc}"}

    def request_shaofu_cleanup_expired(self, *, environment: str = "vm", retention_days: int = 14) -> dict:
        """
        少府清理：只清理少府记录，不删除真实文件。

        清理 = 按 StorageIndex.cleanup_candidates() 返回的候选，
        批量标记 restore_registry / storage_index 中的记录为 deleted。
        不删除真实备份、隔离文件、VM/Host 文件。
        """
        try:
            from services.desktop.qin.shaofu.restore_registry import RestoreRegistry
            from services.desktop.qin.shaofu.storage_index import StorageIndex

            project_root = getattr(self.qin_runtime, "project_root", None)
            normalized_environment = str(environment or "").strip().lower()
            normalized_days = int(retention_days or 14)

            registry = RestoreRegistry(project_root)
            storage_index = StorageIndex(project_root)

            raw_candidates = storage_index.cleanup_candidates(
                environment=normalized_environment,
                retention_days=normalized_days,
            )

            candidates: list[dict[str, Any]] = [
                item for item in raw_candidates
                if isinstance(item, dict)
            ] if isinstance(raw_candidates, list) else []

            cleaned_count = 0
            skipped_count = 0
            failed: list[dict[str, Any]] = []
            cleaned_ids: list[str] = []

            for item in candidates:
                material_id = str(item.get("material_id", "") or "").strip()
                checkpoint_id = str(item.get("checkpoint_id", "") or "").strip()

                if not material_id and not checkpoint_id:
                    skipped_count += 1
                    continue

                registry_result = registry.mark_record_deleted(
                    material_id=material_id,
                    checkpoint_id=checkpoint_id,
                    reason="shaofu_rule_cleanup",
                )
                index_result = storage_index.mark_record_deleted(
                    material_id=material_id,
                    checkpoint_id=checkpoint_id,
                    reason="shaofu_rule_cleanup",
                )

                ok = bool(registry_result.get("ok", False) or index_result.get("ok", False))

                if ok:
                    cleaned_count += 1
                    cleaned_ids.append(material_id or checkpoint_id)
                else:
                    failed.append({
                        "material_id": material_id,
                        "checkpoint_id": checkpoint_id,
                        "registry": registry_result,
                        "storage_index": index_result,
                    })

            return {
                "ok": True,
                "preview_only": False,
                "candidate_count": len(candidates),
                "cleaned_count": cleaned_count,
                "skipped_count": skipped_count,
                "failed_count": len(failed),
                "failed": failed,
                "cleaned_ids": cleaned_ids,
                "message": (
                    f"少府清理完成。\n"
                    f"候选记录：{len(candidates)} 条\n"
                    f"已清理记录：{cleaned_count} 条\n"
                    f"跳过记录：{skipped_count} 条\n"
                    f"失败记录：{len(failed)} 条\n\n"
                    f"说明：本次只清理少府记录索引，不删除真实备份、隔离文件，也不删除 VM/Host 文件。"
                ),
            }

        except Exception as exc:
            return {
                "ok": False,
                "preview_only": False,
                "candidate_count": 0,
                "cleaned_count": 0,
                "skipped_count": 0,
                "failed_count": 1,
                "failed": [{"error": str(exc)}],
                "message": f"少府清理失败：{exc}",
            }
        
    def request_shaofu_update_retention_days(self, days: int) -> dict:
        try:
            from services.desktop.qin.shaofu.storage_index import StorageIndex

            project_root = getattr(self.qin_runtime, "project_root", None)
            return StorageIndex(project_root).update_retention_days(int(days or 14))
        except Exception as exc:
            return {"ok": False, "message": f"更新少府保留天数失败：{exc}"}

    def _queue_ui_call(self, callback) -> None:
        QTimer.singleShot(0, self.w, callback)

    def _start_software_scan_fake_progress(self) -> None:
        self.runtime.software_scan_progress_percent = max(
            int(getattr(self.runtime, "software_scan_progress_percent", 0) or 0),
            3,
        )
        self._software_scan_fake_timer.start()

    def _stop_software_scan_fake_progress(self) -> None:
        if self._software_scan_fake_timer.isActive():
            self._software_scan_fake_timer.stop()

    def _tick_software_scan_fake_progress(self) -> None:
        if not bool(getattr(self.runtime, "software_scan_in_progress", False)):
            self._stop_software_scan_fake_progress()
            return

        current = int(getattr(self.runtime, "software_scan_progress_percent", 0) or 0)
        if current >= 92:
            return

        if current < 20:
            step = 2
        elif current < 60:
            step = 1
        else:
            step = 1 if current % 3 == 0 else 0

        if step <= 0:
            return

        self.runtime.software_scan_progress_percent = min(92, current + step)
        self.reload_software_scan_status()

    def _remember_desktop_page_scroll(self) -> None:
        scroll_area = getattr(self.w, "desktop_scroll_area", None)
        if scroll_area is None:
            return
        bar = scroll_area.verticalScrollBar()
        if bar is not None:
            self.runtime.desktop_page_scroll_value = int(bar.value())

    def _remember_software_scroll(self) -> None:
        table = getattr(self.w, "desktop_apps_table", None)
        if table is not None:
            self.runtime.software_table_scroll_value = int(table.verticalScrollBar().value())
            self.runtime.software_table_horizontal_scroll_value = int(table.horizontalScrollBar().value())

    def _remember_software_area_scroll(self) -> None:
        """
        记录当前桌面页滚动位置和软件表滚动位置。
        用于软件区局部刷新后恢复到原位置。
        """
        self._remember_desktop_page_scroll()
        self._remember_software_scroll()

    def _restore_software_area_scroll_later(self) -> None:
        """
        软件区刷新后恢复滚动位置。
        只恢复滚动，不重新加载页面。
        """
        loader = getattr(self.w, "desktop_page_loader", None)
        if loader is None:
            return
        QTimer.singleShot(0, loader._restore_desktop_page_scroll)
        QTimer.singleShot(
            0,
            lambda: loader._restore_table_scroll(
                "desktop_apps_table",
                vertical_attr="software_table_scroll_value",
                horizontal_attr="software_table_horizontal_scroll_value",
            ),
        )

    def _remember_file_scroll(self) -> None:
        table = getattr(self.w, "desktop_file_table", None)
        if table is not None:
            self.runtime.file_table_vertical_scroll_value = int(table.verticalScrollBar().value())
            self.runtime.file_table_horizontal_scroll_value = int(table.horizontalScrollBar().value())

    def _remember_table_scrolls(self) -> None:
        self._remember_file_scroll()
        self._remember_software_scroll()

    def set_layout_size_value(self, key: str, value: int, *, reload_page: bool = True) -> None:
        self.runtime.layout_overrides[str(key)] = int(value)
        if reload_page:
            self.reload_page()

    def reset_layout_size_values(self) -> None:
        self.runtime.layout_overrides.clear()
        self.reload_page()

    def on_table_section_resized(self, table_name: str, column: int, width: int) -> None:
        key = {
            "desktop_disk_table": {
                0: "disk_column_width_name",
                1: "disk_column_width_status",
                2: "disk_column_width_bool",
                3: "disk_column_width_bool",
                4: "disk_column_width_bool",
                5: "disk_column_width_bool",
            },
            "desktop_file_table": {
                0: "file_column_width_enabled",
                1: "file_column_width_name",
                2: "file_column_width_path",
                3: "file_column_width_open",
                4: "file_column_width_manage",
                5: "file_column_width_type",
                6: "file_column_width_status",
                7: "file_column_width_permission",
            },
            "desktop_apps_table": {
                0: "software_column_width_icon",
                1: "software_column_width_name",
                2: "software_column_width_permission",
                3: "software_column_width_actions",
                4: "software_column_width_path",
                5: "software_column_width_status",
                6: "software_column_width_clear",
            },
        }.get(str(table_name), {}).get(int(column))
        if key:
            self.set_layout_size_value(key, int(width), reload_page=False)

    def current_filter_key(self) -> str:
        combo = getattr(self.w, "desktop_app_filter_combo", None)
        if combo is None:
            return "all"
        return str(combo.currentData() or "all").strip() or "all"

    def _current_mode(self) -> str:
        try:
            runtime_state = self.service.mode_store.get_runtime_state()
        except Exception:
            runtime_state = {}

        mode = str(
            runtime_state.get("desktop_mode")
            or runtime_state.get("current_mode")
            or runtime_state.get("governance_mode")
            or "disabled"
        ).strip().lower()

        return mode if mode in {"disabled", "restricted", "trusted", "test"} else "disabled"
    
    def _is_test_mode(self) -> bool:
        return self._current_mode() == "test"

    def _effective_test_backend(self) -> str:
        if not self._is_test_mode():
            return ""
        backend = str(getattr(self.runtime, "test_backend", "sandbox") or "sandbox").strip().lower()
        return backend if backend in {"sandbox", "vm"} else "sandbox"

    def _is_vm_test_backend(self) -> bool:
        return self._effective_test_backend() == "vm"
    
    def _vm_software_context_ready(self) -> bool:
        """
        当前是否应该使用 VM 软件区数据源。

        注意：
        - 只要当前是 test + vm，就不能再读 Host software_view_cache；
        - VM 是否已连接，只决定能不能刷新 VM 列表；
        - 不决定是否回退到 Host 数据。
        """
        return self._is_test_mode() and self._effective_test_backend() == "vm"

    def toggle_test_mode(self) -> None:
        """
        测试模式总开关。
        """
        current_mode = self._current_mode()

        if current_mode == "test":
            try:
                runtime_state = self.service.mode_store.get_runtime_state()
                target_mode = str(runtime_state.get("last_real_mode", "trusted") or "trusted").strip()
            except Exception:
                target_mode = "trusted"

            if target_mode not in {"disabled", "restricted", "trusted"}:
                target_mode = "trusted"

            self.set_mode(target_mode)
            return

        self.set_mode("test")

    def set_mode(self, mode: str) -> None:
        try:
            self.service.set_mode(mode)
        except Exception as exc:
            QMessageBox.warning(self.w, "桌面连接", f"切换桌面连接模式失败：\n{exc}")
            return

        self.runtime.test_mode_enabled = mode == "test"
        # 用户主动进入测试模式时，默认进入 sandbox。
        # 不继承上次 VM，避免测试模式一打开就尝试连接虚拟机。
        if mode == "test":
            self.runtime.test_backend = "sandbox"
            try:
                self.service.mode_store.set_test_backend("sandbox")
            except Exception:
                pass
        if mode not in {"trusted", "test"}:
            self.runtime.apps_editable = False
            self.runtime.file_governance_editable = False
        if mode == "disabled":
            self.runtime.sandbox_result = None
        self.runtime.cleared_app_ids.clear()

        # 模式切换必须清掉跨出口残留，不能只刷新按钮。
        # 否则 Host / VM / Sandbox 的文件区和软件区容易混显示旧数据。
        if mode != "test":
            self.runtime.sandbox_result = None
            self._clear_vm_runtime_cache()
            self.runtime.vm_connection_state = "unchecked"
            self.runtime.vm_test_available = False
            self.runtime.vm_status_text = "虚拟机测试代理：未检查"

        self.runtime.software_table_loaded = False
        self.runtime.software_last_state = None
        self.runtime.software_cache_state = None

        self.reload_page()
        # Host / sandbox 模式进入后，自动重新读取 Host 软件缓存。
        # VM 模式不读 Host cache，避免 VM/Host 软件区混显示。
        if mode == "trusted" or (mode == "test" and self._effective_test_backend() == "sandbox"):
            QTimer.singleShot(0, self.load_software_view_cache)

    def _sync_legacy_file_runtime(self) -> None:
        self.runtime.file_view_mode = self.runtime.object_view_mode
        self.runtime.file_filter_key = self.runtime.object_filter_key
        self.runtime.file_font_size = self.runtime.object_font_size

    def _ensure_vm_file_runtime_defaults(self) -> None:
        if not hasattr(self.runtime, "vm_file_roots_result"):
            setattr(self.runtime, "vm_file_roots_result", None)
        if not hasattr(self.runtime, "vm_selected_file_root_id"):
            setattr(self.runtime, "vm_selected_file_root_id", "vm_drive_c")
        if not hasattr(self.runtime, "vm_current_relative_path"):
            setattr(self.runtime, "vm_current_relative_path", "")
        if not hasattr(self.runtime, "vm_file_scan_message"):
            setattr(self.runtime, "vm_file_scan_message", "")
        if not hasattr(self.runtime, "vm_file_scan_total_count"):
            setattr(self.runtime, "vm_file_scan_total_count", 0)
        if not hasattr(self.runtime, "vm_file_scan_visible_count"):
            setattr(self.runtime, "vm_file_scan_visible_count", 0)
        if not hasattr(self.runtime, "vm_file_scan_hidden_count"):
            setattr(self.runtime, "vm_file_scan_hidden_count", 0)
        if not hasattr(self.runtime, "vm_file_scan_thread"):
            setattr(self.runtime, "vm_file_scan_thread", None)
        if not hasattr(self.runtime, "vm_file_scan_worker"):
            setattr(self.runtime, "vm_file_scan_worker", None)
        if not hasattr(self.runtime, "vm_file_scan_id"):
            setattr(self.runtime, "vm_file_scan_id", 0)
        if not hasattr(self.runtime, "vm_file_scan_stage"):
            setattr(self.runtime, "vm_file_scan_stage", "")
        if not hasattr(self.runtime, "vm_file_scan_error"):
            setattr(self.runtime, "vm_file_scan_error", "")
        if not hasattr(self.runtime, "vm_file_scan_progress_percent"):
            setattr(self.runtime, "vm_file_scan_progress_percent", 0)


    def _refresh_vm_files_list(
        self,
        *,
        root_id: str | None = None,
        relative_path: str | None = None,
        refresh_roots: bool = False,
        show_error: bool = False,
    ) -> bool:
        self._ensure_vm_file_runtime_defaults()

        normalized_root = (
            str(root_id or getattr(self.runtime, "vm_selected_file_root_id", "vm_drive_c") or "vm_drive_c").strip()
            or "vm_drive_c"
        )
        normalized_relative = str(
            relative_path
            if relative_path is not None
            else getattr(self.runtime, "vm_current_relative_path", "") or ""
        ).strip()

        try:
            adapter = get_default_vm_adapter()

            if refresh_roots or not isinstance(getattr(self.runtime, "vm_file_roots_result", None), dict):
                roots = adapter.list_file_roots()
                setattr(self.runtime, "vm_file_roots_result", roots)

                if not isinstance(roots, dict) or not bool(roots.get("ok", False)):
                    error_text = (
                        str(roots.get("error", roots.get("message", "")) or "").strip()
                        if isinstance(roots, dict)
                        else ""
                    ) or "VM 文件根目录读取失败"

                    self.runtime.vm_file_result = {
                        "ok": False,
                        "items": [],
                        "root_id": normalized_root,
                        "relative_path": normalized_relative,
                        "error": error_text,
                    }

                    if show_error:
                        QMessageBox.warning(self.w, "桌面连接", error_text)

                    return False

            files = adapter.list_files(normalized_root, normalized_relative)
            files_dict = files if isinstance(files, dict) else {}

            self.runtime.vm_file_result = files_dict

            if bool(files_dict.get("ok", False)):
                setattr(
                    self.runtime,
                    "vm_selected_file_root_id",
                    str(files_dict.get("root_id", normalized_root) or normalized_root),
                )
                setattr(
                    self.runtime,
                    "vm_current_relative_path",
                    str(files_dict.get("relative_path", normalized_relative) or ""),
                )

                self.runtime.selected_disk = str(files_dict.get("root_id", normalized_root) or normalized_root)
                self.runtime.object_view_mode = "objects"
                self.runtime.current_directory = str(files_dict.get("current_path", "") or "")

                items = files_dict.get("items", [])
                if isinstance(items, list):
                    total_count = len([item for item in items if isinstance(item, dict)])
                else:
                    total_count = 0

                self.runtime.vm_file_scan_total_count = total_count

                self._sync_legacy_file_runtime()
                return True

            error_text = str(
                files_dict.get(
                    "error",
                    files_dict.get("message", "VM 文件列表读取失败"),
                )
                or "VM 文件列表读取失败"
            )

            self.runtime.vm_file_result = {
                **files_dict,
                "ok": False,
                "items": files_dict.get("items", []) if isinstance(files_dict.get("items", []), list) else [],
                "root_id": files_dict.get("root_id", normalized_root),
                "relative_path": files_dict.get("relative_path", normalized_relative),
                "error": error_text,
            }

            if show_error:
                QMessageBox.warning(self.w, "桌面连接", error_text)

            return False

        except Exception as exc:
            error_text = f"刷新 VM 文件列表失败：{exc}"

            self.runtime.vm_file_result = {
                "ok": False,
                "items": [],
                "root_id": normalized_root,
                "relative_path": normalized_relative,
                "error": error_text,
            }

            if show_error:
                QMessageBox.warning(self.w, "桌面连接", error_text)

            return False

    def run_initialization(self) -> None:
        state = self.service.get_page_state(
            filter_key=self.current_filter_key(),
            apps_editable=self.runtime.apps_editable,
        )
        if not state.get("can_init", False):
            QMessageBox.information(self.w, "桌面连接", "当前状态不允许初始化本地连接。")
            return

        try:
            refreshed = self.service.initialize_local_connection()
        except Exception as exc:
            QMessageBox.warning(self.w, "桌面连接", f"初始化本地连接失败：\n{exc}")
            return

        self.runtime.apps_editable = False
        self.runtime.file_governance_editable = False
        self.reload_page()
        QMessageBox.information(
            self.w,
            "桌面连接",
            (
                "桌面连接初始化已完成。\n"
                f"根目录数量：{refreshed['root_count']}\n"
                f"已确认软件数量：{refreshed['confirmed_app_count']}"
            ),
        )

    def format_local_files(self) -> None:
        try:
            self.service.format_local_files()
        except Exception as exc:
            QMessageBox.warning(self.w, "桌面连接", f"信息格式化失败：\n{exc}")
            return
        self.reload_page()

    def rescan_apps(self, scan_profile: str = "quick") -> None:
        self._remember_software_area_scroll()

        # VM 模式下，扫描按钮必须刷新 VM 软件列表。
        # 不能进入 Host SoftwareScanWorker，否则会显示宿机软件。
        if self._vm_software_context_ready():
            if (
                str(getattr(self.runtime, "vm_connection_state", "unchecked") or "unchecked").strip().lower() != "connected"
                or not bool(getattr(self.runtime, "vm_test_available", False))
            ):
                QMessageBox.information(self.w, "桌面连接", "VM 尚未连接，请先连接 VM。")
                return

            self.refresh_vm_apps_list(
                reason=f"manual_{str(scan_profile or 'quick').strip().lower() or 'quick'}_rescan"
            )
            return

        if self.runtime.software_scan_in_progress or self.runtime.software_scan_thread is not None:
            QMessageBox.information(self.w, "桌面连接", "软件扫描正在进行中，请稍后。")
            return

        state = self.service.get_page_state(
            filter_key=self.current_filter_key(),
            apps_editable=self.runtime.apps_editable,
        )

        sandbox_test_scan = self._is_test_mode() and self._effective_test_backend() == "sandbox"

        if not state.get("can_scan", False) and not sandbox_test_scan:
            QMessageBox.information(self.w, "桌面连接", "当前状态不允许扫描软件。")
            return

        profile = str(scan_profile or "quick").strip().lower()
        if profile not in {"quick", "full"}:
            profile = "quick"

        now = time.monotonic()
        last_profile, last_at = self._last_software_scan_request
        if last_profile == profile and now - last_at < 1.0:
            return
        self._last_software_scan_request = (profile, now)

        thread = QThread(self.w)
        worker = SoftwareScanWorker(self.runtime.project_root, scan_profile=profile)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.progress.connect(self._on_software_scan_progress)
        worker.log.connect(self._on_software_scan_log)
        worker.finished.connect(self._on_software_scan_finished)
        worker.failed.connect(self._on_software_scan_failed)
        worker.finished.connect(thread.quit)
        worker.failed.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        worker.failed.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._clear_software_scan_thread)

        self.runtime.software_scan_thread = thread
        self.runtime.software_scan_worker = worker
        self.runtime.software_scan_profile = profile
        self.runtime.software_scan_in_progress = True
        self.runtime.software_scan_stage = "preparing"
        self.runtime.software_scan_message = "正在准备快速扫描" if profile == "quick" else "正在准备完整扫描"
        self.runtime.software_scan_progress_percent = 1
        self.runtime.software_scan_progress_stats = {"scan_profile": profile}
        self.runtime.software_scan_log_lines = ["quick scan preparing" if profile == "quick" else "full scan preparing"]

        self._start_software_scan_fake_progress()
        self.reload_software_scan_status()
        self._restore_software_area_scroll_later()
        thread.start()

    def refresh_vm_apps_list(self, *, reason: str = "manual_rescan") -> None:
        if not self._is_vm_test_backend():
            return

        if (
            str(getattr(self.runtime, "vm_connection_state", "unchecked") or "unchecked").strip().lower() != "connected"
            or not bool(getattr(self.runtime, "vm_test_available", False))
        ):
            QMessageBox.information(self.w, "桌面连接", "VM 尚未连接，请先连接 VM。")
            return

        if self.runtime.software_scan_in_progress or self.runtime.software_scan_thread is not None:
            QMessageBox.information(self.w, "桌面连接", "软件扫描正在进行中，请稍后。")
            return

        self._remember_software_area_scroll()
        normalized_reason = str(reason or "manual_rescan").strip() or "manual_rescan"
        self._record_vm_software_event("vm.software.rescan.started", reason=normalized_reason, ok=True)

        thread = QThread(self.w)
        worker = VmAppsRefreshWorker(reason=normalized_reason)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(self._on_vm_apps_refresh_finished)
        worker.failed.connect(self._on_vm_apps_refresh_failed)
        worker.finished.connect(thread.quit)
        worker.failed.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        worker.failed.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._clear_software_scan_thread)

        self.runtime.software_scan_thread = thread
        self.runtime.software_scan_worker = worker
        self.runtime.software_scan_profile = "vm"
        self.runtime.software_scan_in_progress = True
        self.runtime.software_scan_stage = "vm_apps_list"
        self.runtime.software_scan_message = "正在刷新 VM 软件列表"
        self.runtime.software_scan_progress_percent = 5
        self.runtime.software_scan_progress_stats = {"reason": normalized_reason, "backend": "vm"}
        self.runtime.software_scan_log_lines = [
            *self.runtime.software_scan_log_lines[-23:],
            f"vm apps/list refresh started: {normalized_reason}",
        ]

        self.reload_software_scan_status()
        self._restore_software_area_scroll_later()
        thread.start()

    def _clear_software_scan_thread(self) -> None:
        self.runtime.software_scan_thread = None
        self.runtime.software_scan_worker = None

    def _on_vm_apps_refresh_finished(self, payload: object) -> None:
        self._queue_ui_call(lambda payload=payload: self._apply_vm_apps_refresh_finished(payload))

    def _on_vm_apps_refresh_failed(self, error_text: str) -> None:
        self._queue_ui_call(lambda error_text=error_text: self._apply_vm_apps_refresh_failed(error_text))

    def _apply_vm_apps_refresh_finished(self, payload: object) -> None:
        result = payload if isinstance(payload, dict) else {}
        reason = str(result.get("reason", "manual_rescan") or "manual_rescan")

        health = result.get("health") if isinstance(result.get("health"), dict) else {}
        apps = result.get("apps") if isinstance(result.get("apps"), dict) else {}

        if bool(result.get("ok", False)) and apps:
            normalized_apps = self._normalize_vm_apps_result(apps)
            self.runtime.vm_apps_result = normalized_apps
            self.runtime.vm_health_result = health or self.runtime.vm_health_result or {}
            self.runtime.vm_last_error = ""
            self.runtime.cleared_app_ids.clear()

            stats = (
                normalized_apps.get("normalize_stats", {})
                if isinstance(normalized_apps.get("normalize_stats", {}), dict)
                else {}
            )

            self.runtime.software_scan_in_progress = False
            self.runtime.software_scan_stage = "completed"
            self.runtime.software_scan_message = "VM 软件列表刷新完成"
            self.runtime.software_scan_progress_percent = 100
            self.runtime.software_scan_progress_stats = {
                "reason": reason,
                "backend": "vm",
                **stats,
            }
            self.runtime.software_scan_log_lines = [
                *self.runtime.software_scan_log_lines[-23:],
                "vm apps/list refreshed",
            ]

            self._record_vm_software_event(
                "vm.software.rescan.completed",
                reason=reason,
                ok=True,
                data={"normalize_stats": stats},
            )

            if reason == "clear_stale":
                self._record_vm_software_event(
                    "vm.software.clear_stale.completed",
                    reason=reason,
                    ok=True,
                    data={"normalize_stats": stats},
                )

            vm_state = self.get_vm_software_governance_state()
            vm_rows = vm_state.get("rows", []) if isinstance(vm_state.get("rows", []), list) else []

            self.runtime.software_cache_state = vm_state
            self.runtime.software_cache_loaded = bool(vm_rows)
            self.runtime.software_cache_source = "vm"
            self.runtime.software_last_state = dict(vm_state)
            self.runtime.software_table_loaded = bool(vm_rows)

            self._remember_software_area_scroll()

            loader = getattr(self.w, "desktop_page_loader", None)
            if loader is not None:
                loader.load_software_panel(
                    software_state=vm_state,
                    force_full=bool(vm_rows),
                )

            self._restore_software_area_scroll_later()
            return

        apps_dict = apps if isinstance(apps, dict) else {}
        error_text = str(
            result.get("error", "")
            or apps_dict.get("error", "")
            or apps_dict.get("message", "")
            or "VM 软件列表刷新失败"
        )

        self.runtime.software_scan_in_progress = False
        self.runtime.software_scan_stage = "failed"
        self.runtime.software_scan_message = "VM 软件列表刷新失败"
        self.runtime.software_scan_progress_percent = 0
        self.runtime.vm_last_error = error_text
        self.runtime.software_scan_log_lines = [
            *self.runtime.software_scan_log_lines[-23:],
            f"vm apps/list refresh failed: {error_text}",
        ]

        self._record_vm_software_event(
            "vm.software.rescan.failed",
            reason=reason,
            ok=False,
            error=error_text,
        )

        if reason == "clear_stale":
            self._record_vm_software_event(
                "vm.software.clear_stale.completed",
                reason=reason,
                ok=False,
                error=error_text,
            )

        self.reload_software_scan_status()
        QMessageBox.warning(self.w, "桌面连接", f"刷新 VM 软件列表失败：\n{error_text}")

    def _apply_vm_apps_refresh_failed(self, error_text: str) -> None:
        self.runtime.software_scan_in_progress = False
        self.runtime.software_scan_stage = "failed"
        self.runtime.software_scan_message = "VM 软件列表刷新失败"
        self.runtime.software_scan_progress_percent = 0
        self.runtime.vm_last_error = str(error_text or "")
        self.runtime.software_scan_log_lines = [
            *self.runtime.software_scan_log_lines[-23:],
            "vm apps/list refresh failed",
        ]
        self._record_vm_software_event(
            "vm.software.rescan.failed",
            reason="worker_failed",
            ok=False,
            error=str(error_text or ""),
        )
        self.reload_software_scan_status()
        QMessageBox.warning(self.w, "桌面连接", f"刷新 VM 软件列表失败：\n{error_text}")

    def _record_vm_software_event(self, event_type: str, *, reason: str, ok: bool, error: str = "", data: dict | None = None) -> None:
        try:
            YushitaiEventStore(self.runtime.project_root).record(
                event_type=event_type,
                department="tianting",
                action="vm.software.rescan",
                backend="vm",
                execution_backend="vm",
                target_environment="virtual_machine",
                path_namespace="vm_windows",
                target={"name": "VM software list", "type": "vm_apps"},
                decision="vm_only",
                route_result="vm.apps_list",
                adapter_id="vm",
                reason=str(reason or ""),
                result={"ok": bool(ok), "message": str(error or reason or "")},
                data=data if isinstance(data, dict) else {},
            )
        except Exception:
            return

    def clear_third_party_connections(self) -> None:
        reply = QMessageBox.question(
            self.w,
            "桌面连接",
            "将清空第三方软件连接并保留基础对象，是否继续？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            self.service.clear_third_party_connections()
        except Exception as exc:
            QMessageBox.warning(self.w, "桌面连接", f"清空第三方连接失败：\n{exc}")
            return

        empty = (
            self.software_view_cache.empty_state()
            if hasattr(self.software_view_cache, "empty_state")
            else {
                "ok": False,
                "source": "empty",
                "discovered_count": 0,
                "trusted_count": 0,
                "confirmed_count": 0,
                "hidden_count": 0,
                "read_only": True,
                "rows": [],
            }
        )
        self.runtime.software_last_state = empty
        self.runtime.software_cache_state = empty
        self.runtime.software_table_loaded = False
        self.runtime.cleared_app_ids.clear()

        loader = getattr(self.w, "desktop_page_loader", None)
        if loader is not None:
            loader.load_software_panel(software_state=empty, force_full=False)

    def on_filter_changed(self) -> None:
        if self._vm_software_context_ready():
            state = self.get_vm_software_governance_state()
            raw_rows = state.get("rows", [])
            rows: list[dict] = [
                row for row in raw_rows if isinstance(row, dict)
            ] if isinstance(raw_rows, list) else []

            filter_key = self.current_filter_key()

            if filter_key != "all":
                def match(row: dict) -> bool:
                    state_value = str(
                        row.get("permission_state", row.get("effective_permission_state", "test"))
                        or "test"
                    ).strip().lower()

                    if filter_key == "allow":
                        return state_value in {"allow", "test"}
                    if filter_key == "once":
                        return state_value == "once"
                    if filter_key == "deny":
                        return state_value in {"deny", "unset", ""}
                    if filter_key == "unset":
                        return state_value == "unset"

                    return True

                rows = [row for row in rows if match(row)]

            filtered = dict(state)
            filtered["rows"] = rows
            filtered["discovered_count"] = len(rows)
            filtered["trusted_count"] = len(rows)
            filtered["confirmed_count"] = len(rows)
            filtered["source"] = "vm"
            filtered["software_view_mode"] = "vm"
            filtered["execution_backend"] = "vm"

            self.runtime.software_cache_state = filtered
            self.runtime.software_cache_loaded = bool(rows)
            self.runtime.software_cache_source = "vm"
            self.runtime.software_last_state = filtered
            self.runtime.software_table_loaded = bool(rows)

            self.w.desktop_page_loader.load_software_panel(
                software_state=filtered,
                force_full=bool(rows),
            )
            return

        cached = self.software_view_cache.read()
        raw_rows = cached.get("rows", [])
        rows: list[dict] = [
            row for row in raw_rows if isinstance(row, dict)
        ] if isinstance(raw_rows, list) else []

        filter_key = self.current_filter_key()

        if filter_key != "all":
            def match(row: dict) -> bool:
                state_value = str(
                    row.get("effective_permission_state", row.get("permission_state", "deny"))
                    or "deny"
                ).strip().lower()

                if filter_key == "allow":
                    return state_value == "allow"
                if filter_key == "once":
                    return state_value == "once"
                if filter_key == "deny":
                    return state_value == "deny"
                if filter_key == "unset":
                    return state_value in {"unset", ""}

                return True

            rows = [row for row in rows if match(row)]

        filtered = dict(cached)
        filtered["rows"] = rows
        filtered["discovered_count"] = len(rows)

        self.runtime.software_cache_state = filtered
        self.runtime.software_cache_loaded = bool(rows)
        self.runtime.software_cache_source = str(filtered.get("source", "cache") or "cache")
        self.runtime.software_last_state = filtered
        self.runtime.software_table_loaded = bool(rows)

        self.w.desktop_page_loader.load_software_panel(
            software_state=filtered,
            force_full=bool(rows),
        )

    def set_apps_editable(self, editable: bool) -> None:
        if hasattr(self.service, "get_page_shell_state"):
            state = self.service.get_page_shell_state(apps_editable=editable)
        else:
            try:
                mode = str(self.service.mode_store.get_mode_state().current_mode or "disabled")
            except Exception:
                mode = "disabled"
            state = {
                "mode": mode,
                "show_apps": mode in {"trusted", "test"},
                "apps_read_only": True,
                "can_scan": False,
                "can_toggle_apps_editable": False,
            }

        self.runtime.apps_editable = bool(editable) and bool(state.get("can_toggle_apps_editable", False))

        loader = getattr(self.w, "desktop_page_loader", None)
        if loader is None:
            return

        # 只切换当前表格按钮可点击状态，不重新渲染软件表
        if hasattr(loader, "refresh_software_editable_state"):
            loader.refresh_software_editable_state(page_state=state)
        else:
            loader.refresh_software_scan_status(page_state=state)

    def toggle_root_flag(self, root_id: str, field: str, value: bool) -> None:
        try:
            self.service.update_root_flag(root_id, field, value)
        except Exception as exc:
            QMessageBox.warning(self.w, "桌面连接", f"更新根目录治理项失败：\n{exc}")
            return

        self.reload_page()

    def cycle_app_permission(self, app_id: str) -> None:
        if not bool(getattr(self.runtime, "apps_editable", False)):
            return

        normalized_app_id = str(app_id or "").strip()
        if not normalized_app_id:
            return

        current_row = self._find_runtime_software_row(normalized_app_id)
        if isinstance(current_row, dict):
            permission_state = str(
                current_row.get("permission_state", current_row.get("effective_permission_state", ""))
                or ""
            ).strip().lower()
            platform = str(current_row.get("platform", "") or "").strip().lower()
            if permission_state == "test" or platform == "vm":
                return

        try:
            next_state = self.service.cycle_app_permission(normalized_app_id)
        except Exception as exc:
            QMessageBox.warning(self.w, "桌面连接", f"更新软件权限失败：\n{exc}")
            return

        self._update_runtime_software_permission_row(normalized_app_id, str(next_state or "deny"))

    def _find_runtime_software_row(self, app_id: str) -> dict | None:
        state = self.runtime.software_last_state
        if not isinstance(state, dict):
            return None

        rows = state.get("rows", [])
        if not isinstance(rows, list):
            return None

        normalized_app_id = str(app_id or "").strip()
        for row in rows:
            if not isinstance(row, dict):
                continue
            if str(row.get("app_id", "") or "").strip() == normalized_app_id:
                return row
        return None

    def _update_runtime_software_permission_row(self, app_id: str, next_state: str) -> None:
        state = self.runtime.software_last_state
        if not isinstance(state, dict):
            return

        rows = state.get("rows", [])
        if not isinstance(rows, list):
            return

        normalized_app_id = str(app_id or "").strip()
        normalized_state = str(next_state or "deny").strip().lower()
        if normalized_state not in {"deny", "once", "allow"}:
            normalized_state = "deny"

        label_map = {
            "deny": "否",
            "once": "受限",
            "allow": "是",
        }
        color_map = {
            "deny": "#EF4444",
            "once": "#FACC15",
            "allow": "#22C55E",
        }

        permission_open = normalized_state in {"allow", "once"}
        permission_allow = normalized_state == "allow"

        patch = {
            "permission_state": normalized_state,
            "effective_permission_state": normalized_state,
            "permission_label": label_map[normalized_state],
            "permission_text": label_map[normalized_state],
            "permission_color": color_map[normalized_state],

            # 受限 / 是：低风险动作可用
            "can_locate": permission_open,
            "can_launch": permission_open,
            "can_close": permission_open,

            # 只有“是”：高危动作按钮也可用
            "can_uninstall": permission_allow,
            "can_move": permission_allow,
            "can_update": permission_allow,
        }

        updated_row = None

        for index, row in enumerate(rows):
            if not isinstance(row, dict):
                continue
            if str(row.get("app_id", "") or "").strip() != normalized_app_id:
                continue

            updated = dict(row)
            updated.update(patch)

            rows[index] = updated
            updated_row = updated
            break

        if updated_row is None:
            return

        state["rows"] = rows
        self.runtime.software_last_state = state
        self.runtime.software_cache_state = state

        # 同步 software_view_cache.json，避免点击“刷新列表”后权限回退。
        try:
            if hasattr(self.software_view_cache, "update_row_permission"):
                cached = self.software_view_cache.update_row_permission(normalized_app_id, patch)
                if isinstance(cached, dict) and isinstance(cached.get("rows", []), list):
                    self.runtime.software_cache_state = cached
        except Exception:
            # cache 同步失败不影响当前行 UI，但刷新列表可能仍会读到旧 cache。
            pass

        loader = getattr(self.w, "desktop_page_loader", None)
        if loader is None:
            return

        panel_loader = getattr(loader, "software_panel_loader", None)
        if panel_loader is None:
            return

        if hasattr(panel_loader, "refresh_one_app_row"):
            panel_loader.refresh_one_app_row(app_id=normalized_app_id, row=updated_row)
        else:
            shell_state = (
                self.service.get_page_shell_state(apps_editable=self.runtime.apps_editable)
                if hasattr(self.service, "get_page_shell_state")
                else {}
            )
            panel_loader.refresh_apps_table_interactive_state(
                software_state=state,
                page_state=loader._software_page_state_for_runtime(shell_state),
            )

    def on_runtime_root_changed(self) -> None:
        combo = getattr(self.w, "desktop_runtime_root_combo", None)
        if combo is None:
            return
        self.runtime.readonly_selected_root_id = str(combo.currentData() or "").strip() or "project_root"
        self.reload_page()

    def run_readonly_datetime(self) -> None:
        self._run_readonly_task({
            "action": "system_info.read_datetime",
            "target_path": "",
            "root_id": "",
            "arguments": {},
        })

    def run_readonly_list_dir(self) -> None:
        root_target = self._selected_root_target()
        if root_target is None:
            return
        self._run_readonly_task({
            "action": "filesystem.list_dir",
            "target_path": root_target["path"],
            "root_id": root_target["root_id"],
            "arguments": {},
        })

    def run_readonly_path_meta(self) -> None:
        root_target = self._selected_root_target()
        if root_target is None:
            return
        self._run_readonly_task({
            "action": "filesystem.path_meta",
            "target_path": root_target["path"],
            "root_id": root_target["root_id"],
            "arguments": {},
        })

    def run_readonly_open_directory(self) -> None:
        root_target = self._selected_root_target()
        if root_target is None:
            return
        self._run_readonly_task({
            "action": "explorer.open_directory",
            "target_path": root_target["path"],
            "root_id": root_target["root_id"],
            "arguments": {},
        })

    def clear_readonly_result(self) -> None:
        self.runtime.readonly_result = None
        self.reload_page()

    def set_file_governance_editable(self, editable: bool) -> None:
        self.runtime.file_governance_editable = self._current_mode() in {"trusted", "test"} and bool(editable)
        self.reload_page()

    def toggle_disk_file_actions(self, disk_id: str) -> None:
        if self._is_vm_test_backend():
            self.runtime.vm_file_actions_enabled = not bool(
                getattr(self.runtime, "vm_file_actions_enabled", False)
            )
            self.reload_page()
            return

        if not self._can_adjust_file_governance():
            return

        normalized_disk = str(disk_id or "").strip().upper()
        if not normalized_disk:
            return

        try:
            self.service.toggle_disk_file_actions_enabled(normalized_disk)
        except Exception as exc:
            QMessageBox.warning(self.w, "桌面连接", f"更新文件动作状态失败：\n{exc}")
            return

        self.reload_page()

    def set_test_backend(self, backend: str) -> None:
        normalized = str(backend or "").strip().lower()
        if not self._is_test_mode():
            self.runtime.test_backend = normalized if normalized in {"sandbox", "vm"} else "sandbox"
            try:
                self.service.mode_store.set_test_backend(self.runtime.test_backend)
            except Exception:
                pass
            self.reload_page()
            return

        if normalized == "sandbox":
            self.runtime.test_backend = "sandbox"
            try:
                self.service.mode_store.set_test_backend("sandbox")
            except Exception:
                pass
            self.runtime.apps_editable = False
            self._clear_vm_runtime_cache()
            self.runtime.vm_connection_state = "unchecked"
            self.runtime.vm_status_text = "虚拟机状态：未连接"
            self.runtime.sandbox_result = self.runtime.sandbox_result if isinstance(self.runtime.sandbox_result, dict) else None
            self.runtime.software_table_loaded = False
            self.runtime.software_last_state = None
            self.runtime.software_cache_state = None
            self.reload_page()

            # sandbox 显示 Host 软件数据，但执行出口走 sandbox。
            QTimer.singleShot(0, self.load_software_view_cache)
            return

        if normalized == "vm":
            self.runtime.test_backend = "vm"
            try:
                self.service.mode_store.set_test_backend("vm")
            except Exception:
                pass

            self.runtime.apps_editable = False

            # 进入 VM 前先清掉 Host/sandbox 软件表，避免混显示。
            self.runtime.software_table_loaded = False
            self.runtime.software_last_state = None
            self.runtime.software_cache_state = None

            self._update_yushitai_run_meta(test_backend="vm")
            self._review_and_start_vm_connection()
            return

    def refresh_vm_test_status(self, *, reload_page: bool = True) -> None:
        """Refresh VM bridge status."""

        if not self._is_test_mode():
            self.reload_page()
            return
        self.runtime.test_backend = "vm"
        try:
            self.service.mode_store.set_test_backend("vm")
        except Exception:
            pass
        self.runtime.apps_editable = False
        self._update_yushitai_run_meta(test_backend="vm")
        self._review_and_start_vm_connection()

    def _update_yushitai_run_meta(self, *, test_backend: str) -> None:
        try:
            ReportWriter(self.runtime.project_root).update_run_meta(
                test_backend=str(test_backend or "").strip().lower(),
                current_mode=self._current_mode(),
                desktop_mode=self._current_mode(),
                execution_backend=self._effective_test_backend() or "none",
                host_execution_enabled=False,
            )
        except Exception:
            return

    def _clear_vm_runtime_cache(self) -> None:
        self.runtime.vm_test_available = False
        self.runtime.vm_health_result = None
        setattr(self.runtime, "vm_file_roots_result", None)
        setattr(self.runtime, "vm_selected_file_root_id", "vm_drive_c")
        setattr(self.runtime, "vm_current_relative_path", "")
        self.runtime.vm_apps_result = None
        self.runtime.vm_file_result = None
        self.runtime.vm_file_actions_enabled = False
        self.runtime.vm_last_error = ""
        self.runtime.vm_file_scan_in_progress = False
        self.runtime.vm_file_scan_message = ""
        self.runtime.vm_file_scan_total_count = 0
        self.runtime.vm_file_scan_visible_count = 0
        self.runtime.vm_file_scan_hidden_count = 0
        self.runtime.vm_file_scan_id = int(getattr(self.runtime, "vm_file_scan_id", 0) or 0) + 1
        self.runtime.vm_file_scan_stage = ""
        self.runtime.vm_file_scan_error = ""
        self.runtime.vm_file_scan_progress_percent = 0

    def _mark_vm_disconnected(self, error_text: str) -> None:
        error = str(error_text or "").strip() or "VM 连接失败"
        self._clear_vm_runtime_cache()
        self.runtime.vm_connection_state = "disconnected"
        self.runtime.vm_test_available = False
        self.runtime.vm_last_error = error
        self.runtime.vm_status_text = f"虚拟机状态：未连接 | {error}"

    def _review_and_start_vm_connection(self) -> None:
        self.runtime.apps_editable = False
        self._clear_vm_runtime_cache()
        self.runtime.vm_connection_state = "unchecked"
        task = {
            "action": "vm.connect",
            "target_name": "VM bridge",
            "target_type": "vm_bridge",
            "arguments": {
                "test_backend": "vm",
                "permission_state": "test",
                "effective_permission_state": "test",
                "vm_profile": {"profile_id": "default"},
            },
        }
        result = self.qin_runtime.execute_desktop_task(task)
        self._store_desktop_execution_result(result, preferred_backend="vm")
        data = result.get("data", {}) if isinstance(result, dict) and isinstance(result.get("data", {}), dict) else {}
        approved = (
            bool(result.get("ok", False))
            and str(data.get("decision", "")).strip().lower() == "vm_only"
            and str(data.get("route_result", "")).strip().lower() == "vm.bridge"
        )
        if not approved:
            message = str(result.get("message", "") or "VM 连接审议未通过")
            self._mark_vm_disconnected(message)
            self.refresh_mode_only()
            return
        self.start_vm_connection()

    def start_vm_connection(self) -> None:
        if self.runtime.vm_connect_thread is not None:
            self.refresh_mode_only()
            return

        self._clear_vm_runtime_cache()
        self.runtime.vm_connection_state = "connecting"
        self.runtime.vm_status_text = "虚拟机状态：连接中..."
        self.runtime.vm_connection_started_at = time.monotonic()
        self.refresh_mode_only()

        thread = QThread(self.w)
        worker = VmConnectWorker()
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(self._on_vm_connection_finished)
        worker.failed.connect(self._on_vm_connection_failed)
        worker.finished.connect(thread.quit)
        worker.failed.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        worker.failed.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._clear_vm_connect_thread)
        self.runtime.vm_connect_thread = thread
        self.runtime.vm_connect_worker = worker
        thread.start()

    def _clear_vm_connect_thread(self) -> None:
        self.runtime.vm_connect_thread = None
        self.runtime.vm_connect_worker = None

    def _on_vm_connection_finished(self, payload: object) -> None:
        self._queue_ui_call(lambda payload=payload: self._apply_vm_connection_finished(payload))

    def _on_vm_connection_failed(self, error_text: str) -> None:
        self._queue_ui_call(lambda error_text=error_text: self._apply_vm_connection_failed(error_text))

    def _apply_vm_connection_finished(self, payload: object) -> None:
        if not self._is_vm_test_backend():
            return
        result = payload if isinstance(payload, dict) else {}
        health = result.get("health") if isinstance(result.get("health"), dict) else None
        apps = result.get("apps") if isinstance(result.get("apps"), dict) else None
        files = result.get("files") if isinstance(result.get("files"), dict) else None
        ok = bool(result.get("ok", False))

        if ok and (health is not None or apps is not None or files is not None):
            apps = self._normalize_vm_apps_result(apps or {})
            result = dict(result)
            result["apps"] = apps
            self.runtime.vm_connection_state = "connected"
            self.runtime.vm_test_available = True
            self.runtime.vm_last_error = ""
            self.runtime.vm_health_result = health or {}
            self.runtime.vm_apps_result = apps
            self.runtime.vm_file_result = files or {"ok": False, "items": [], "error": "VM 文件读取失败"}
            self._refresh_vm_files_list(root_id="vm_drive_c", relative_path="", refresh_roots=True)
            hostname = str((health or apps).get("hostname", "-") or "-")
            latest_files = self.runtime.vm_file_result if isinstance(self.runtime.vm_file_result, dict) else files
            workspace = str((health or {}).get("workspace", (latest_files or {}).get("root_path", (latest_files or {}).get("root", "-"))) or "-")
            self.runtime.vm_status_text = f"虚拟机状态：已连接 | {hostname} | {workspace}"
            self._update_yushitai_run_meta(test_backend="vm")
            self._record_vm_connection_memory(ok=True, result=result, error_text="")
            self.reload_page()
            return

        error_text = str(result.get("error", "") or "").strip()
        if not error_text and health:
            error_text = str(health.get("error", health.get("message", "")) or "").strip()
        if not error_text and apps:
            error_text = str(apps.get("error", apps.get("message", "")) or "").strip()
        self._record_vm_connection_memory(ok=False, result=result, error_text=error_text or "VM 连接失败")
        self._mark_vm_disconnected(error_text or "VM 连接失败")
        self.reload_page()

    def _normalize_vm_apps_result(self, apps: dict) -> dict:
        if not isinstance(apps, dict):
            return {"ok": False, "apps": [], "error": "VM 软件读取失败"}

        raw_apps = apps.get("apps")
        if not isinstance(raw_apps, list):
            raw_apps = apps.get("items")
        if not isinstance(raw_apps, list):
            raw_apps = []

        normalized = normalize_vm_apps(raw_apps)
        return {
            **apps,
            "apps": normalized["apps"],
            "items": normalized["apps"],
            "raw_apps": normalized["raw"],
            "normalize_stats": normalized["stats"],
            "hidden_apps": normalized["hidden"],
        }

    def _apply_vm_connection_failed(self, error_text: str) -> None:
        if not self._is_vm_test_backend():
            return
        self._record_vm_connection_memory(ok=False, result={}, error_text=error_text)
        self._mark_vm_disconnected(error_text)
        self.reload_page()

    def _record_vm_connection_memory(self, *, ok: bool, result: dict, error_text: str) -> None:
        try:
            started_at = float(getattr(self.runtime, "vm_connection_started_at", 0.0) or 0.0)
            duration_ms = round((time.monotonic() - started_at) * 1000, 2) if started_at else 0.0
            health = result.get("health", {}) if isinstance(result.get("health", {}), dict) else {}
            apps = result.get("apps", {}) if isinstance(result.get("apps", {}), dict) else {}
            files = result.get("files", {}) if isinstance(result.get("files", {}), dict) else {}
            apps_list = apps.get("apps", apps.get("items", [])) if isinstance(apps, dict) else []
            files_list = files.get("items", []) if isinstance(files, dict) else []
            raw_normalize_stats = apps.get("normalize_stats", {}) if isinstance(apps, dict) else {}
            normalize_stats = raw_normalize_stats if isinstance(raw_normalize_stats, dict) else {}

            vm_apps_count = len(apps_list) if isinstance(apps_list, list) else 0
            vm_files_count = len(files_list) if isinstance(files_list, list) else 0

            raw_count_value = normalize_stats.get("raw", vm_apps_count)
            hidden_count_value = normalize_stats.get("hidden", 0)
            merged_uninstallers_value = normalize_stats.get("merged_uninstallers", 0)

            try:
                vm_software_raw_count = int(raw_count_value) if raw_count_value is not None else 0
            except (TypeError, ValueError):
                vm_software_raw_count = vm_apps_count

            try:
                vm_software_hidden_count = int(hidden_count_value) if hidden_count_value is not None else 0
            except (TypeError, ValueError):
                vm_software_hidden_count = 0

            try:
                vm_software_merged_uninstallers = int(merged_uninstallers_value) if merged_uninstallers_value is not None else 0
            except (TypeError, ValueError):
                vm_software_merged_uninstallers = 0
            sandbox_result = getattr(self.runtime, "sandbox_result", None)
            sandbox_result_dict = sandbox_result if isinstance(sandbox_result, dict) else {}
            sandbox_data = sandbox_result_dict.get("data", {})
            review_data = sandbox_data if isinstance(sandbox_data, dict) else {}
            memory = VmConnectionMemoryStore(self.runtime.project_root).record_memory(
                action="vm.connect",
                ok=ok,
                base_url=str(health.get("base_url", "") or ""),
                hostname=str(health.get("hostname", apps.get("hostname", "")) or ""),
                protocol_version=str(health.get("protocol_version", health.get("protocol", "")) or ""),
                agent_version=str(health.get("agent_version", health.get("version", "")) or ""),
                duration_ms=duration_ms,
                apps_count=vm_apps_count,
                files_count=vm_files_count,
                review_stage=str(review_data.get("review_stage", "") or ""),
                route_result=str(review_data.get("route_result", "") or ""),
                error=str(error_text or ""),
            )
            snapshot = {
                "desktop_mode": self._current_mode(),
                "test_backend": str(getattr(self.runtime, "test_backend", "") or ""),
                "execution_backend": self._effective_test_backend() or "none",
                "host_execution_enabled": False,
                "vm_connection_state": str(getattr(self.runtime, "vm_connection_state", "") or ""),
                "vm_test_available": bool(getattr(self.runtime, "vm_test_available", False)),
                "vm_apps_count": vm_apps_count,
                "vm_files_count": vm_files_count,
                "vm_software_raw_count": vm_software_raw_count,
                "vm_software_final_count": vm_apps_count,
                "vm_software_hidden_count": vm_software_hidden_count,
                "vm_software_merged_uninstallers": vm_software_merged_uninstallers,
                "vm_software_normalize_stats": normalize_stats,
                "latest_vm_connection_memory": memory,
                "metrics": DesktopMetricsService(self.runtime.project_root).collect_metrics(
                    runtime_state={
                        "desktop_mode": self._current_mode(),
                        "test_backend": str(getattr(self.runtime, "test_backend", "") or ""),
                        "execution_backend": self._effective_test_backend() or "none",
                        "host_execution_enabled": False,
                        "vm_connection_state": str(getattr(self.runtime, "vm_connection_state", "") or ""),
                        "vm_apps_count": vm_apps_count,
                        "vm_files_count": vm_files_count,
                        "vm_software_raw_count": vm_software_raw_count,
                        "vm_software_final_count": vm_apps_count,
                        "vm_software_hidden_count": vm_software_hidden_count,
                        "vm_software_merged_uninstallers": vm_software_merged_uninstallers,
                    }
                ),
            }
            writer = ReportWriter(self.runtime.project_root)
            writer.write_snapshot(snapshot)
            writer.write_named_snapshot("latest_vm_state.json", snapshot)
            YushitaiEventStore(self.runtime.project_root).record(
                event_type="vm.connection.completed",
                department="tianting",
                action="vm.connect",
                backend="vm",
                target={"name": "VM bridge", "type": "vm_bridge"},
                decision="vm_only",
                route_result=str(review_data.get("route_result", "vm.bridge") or "vm.bridge"),
                adapter_id="vm",
                reason=str(error_text or ""),
                result={
                    "ok": ok,
                    "message": str(error_text or ("VM connected." if ok else "VM connection failed.")),
                    "executed_in": "vm",
                },
                data={
                    "ok": ok,
                    "review_stage": str(review_data.get("review_stage", "") or ""),
                    "apps_count": vm_apps_count,
                    "files_count": vm_files_count,
                },
                raw={"memory": memory},
            )
            writer.generate_report(stage="v3_v4_desktop_test", runtime_state=snapshot)
        except Exception:
            return


    def _set_vm_status_from_result(self, result: dict, *, fallback_error: str = "-") -> None:
        ok = bool(result.get("ok", False)) if isinstance(result, dict) else False
        self.runtime.vm_test_available = ok

        if ok:
            hostname = result.get("hostname", "-")
            workspace = result.get("workspace", result.get("root", "-"))
            self.runtime.vm_status_text = f"虚拟机测试代理：已连接 | {hostname} | {workspace}"
            return

        error_text = str(
            result.get("error", result.get("message", fallback_error))
            if isinstance(result, dict)
            else fallback_error
        ).strip() or "-"

        self.runtime.vm_status_text = f"虚拟机测试代理：未连接 | {error_text}"

    def get_vm_file_governance_state(self) -> dict:
        """Build VM file governance roots/list state."""

        self._ensure_vm_file_runtime_defaults()

        result = self.runtime.vm_file_result if isinstance(self.runtime.vm_file_result, dict) else None
        roots_result = getattr(self.runtime, "vm_file_roots_result", None)

        state = str(getattr(self.runtime, "vm_connection_state", "unchecked") or "unchecked").strip().lower()
        vm_available = bool(getattr(self.runtime, "vm_test_available", False))

        selected_root_id = (
            str(getattr(self.runtime, "vm_selected_file_root_id", "vm_drive_c") or "vm_drive_c").strip()
            or "vm_drive_c"
        )
        current_relative_path = str(getattr(self.runtime, "vm_current_relative_path", "") or "").strip()

        # VM 未连接或文件结果为空时，生成安全的错误结果
        if state != "connected" or not vm_available:
            if state == "connecting":
                error = "虚拟机状态：连接中..."
            else:
                error = str(getattr(self.runtime, "vm_last_error", "") or "").strip() or "VM 文件读取失败"

            result = {
                "ok": False,
                "items": [],
                "root_id": selected_root_id,
                "relative_path": current_relative_path,
                "error": error,
            }

        elif result is None:
            result = {
                "ok": False,
                "items": [],
                "root_id": selected_root_id,
                "relative_path": current_relative_path,
                "error": "VM 文件读取失败",
            }

        self.runtime.vm_file_result = result

        # VM 连接状态只看 VM bridge 状态，不再依赖 /files/list 的 ok。
        # /files/list 成功或失败只影响下层文件表，不影响上层 VM root 治理区是否可调整。
        vm_connected = state == "connected" and vm_available
        vm_file_list_ok = bool(result.get("ok", False))

        vm_editable = (
            self._current_mode() == "test"
            and vm_connected
            and bool(getattr(self.runtime, "file_governance_editable", False))
        )

        root_path = str(result.get("root_path", result.get("root", "")) or "")
        current_path = str(result.get("current_path", root_path) or root_path)

        # roots 来源：优先使用 /files/roots；没有时用当前 root_path 兜底
        roots: list[dict] = []
        if isinstance(roots_result, dict) and isinstance(roots_result.get("roots"), list):
            roots = [item for item in roots_result.get("roots", []) if isinstance(item, dict)]

        if not roots and root_path:
            roots = [{
                "root_id": selected_root_id,
                "title": "C:",
                "path": root_path,
                "permission_state": "test",
                "can_expand": True,
                "can_scan": True,
                "can_index": True,
                "file_actions_enabled": False,
            }]

        # 下层文件对象 rows
        rows: list[dict] = []

        if not bool(result.get("ok", False)):
            error_text = str(result.get("error", "") or "VM 文件列表读取失败")
            rows.append({
                "enabled": True,
                "name": "VM 文件读取失败",
                "path_short": error_text,
                "target_path": "",
                "target_name": "VM 文件读取失败",
                "target_type": "错误",
                "object_type": "error",
                "is_dir": False,
                "object_key": "vm_error",
                "root_id": selected_root_id,
                "relative_path": "",
                "permission_state": "deny",
                "effective_permission_state": "deny",
                "permission_text": "禁止",
                "status_text": "失败",
                "status_color": "#EF4444",
                "can_adjust": False,
                "can_open": False,
                "open_label": "查看",
                "open_action": "inspect",
                "request_allowed": False,
                "apply_ui_allowed": False,
                "tooltip": error_text,
            })

        else:
            items = result.get("items", [])
            if not isinstance(items, list):
                items = []

            total_count = len([item for item in items if isinstance(item, dict)])
            visible_items = []
            hidden_count = 0

            for item in items:
                if not isinstance(item, dict):
                    continue
                if self._should_hide_vm_file_item(item):
                    hidden_count += 1
                    continue
                visible_items.append(item)

            self.runtime.vm_file_scan_total_count = total_count
            self.runtime.vm_file_scan_visible_count = len(visible_items)
            self.runtime.vm_file_scan_hidden_count = hidden_count

            for item in visible_items:

                name = str(item.get("name", "-") or "-")
                path = str(item.get("path", "") or "")
                relative_path = str(item.get("relative_path", "") or "")

                raw_object_type = str(item.get("object_type", item.get("type", "")) or "").strip().lower()
                is_dir = bool(item.get("is_dir", False)) or raw_object_type == "directory"
                object_type = "directory" if is_dir else "file"
                is_blocked = bool(item.get("blocked", False))

                can_navigate = is_dir and not is_blocked
                item_root_id = (
                    str(item.get("root_id", result.get("root_id", selected_root_id)) or selected_root_id).strip()
                    or selected_root_id
                )

                object_key = str(
                    item.get("object_id", f"vm::{item_root_id}::{relative_path or path}")
                    or f"vm::{item_root_id}::{relative_path or path}"
                )

                rows.append({
                    "enabled": True,
                    "name": name,
                    "path_short": path,
                    "target_path": path,
                    "target_name": name,
                    "target_type": "目录" if is_dir else "文件",
                    "object_type": object_type,
                    "is_dir": is_dir,
                    "object_key": object_key,
                    "root_id": item_root_id,
                    "relative_path": relative_path,
                    "permission_state": "deny" if is_blocked else "allow",
                    "effective_permission_state": "deny" if is_blocked else "allow",
                    "permission_text": "允许",
                    "status_text": "屏蔽" if is_blocked else "VM",
                    "status_color": "#EF4444" if is_blocked else "#22C55E",
                    "can_adjust": False,
                    "can_open": can_navigate,
                    "open_label": "进入" if can_navigate else "查看",
                    "open_action": "blocked" if is_blocked else ("navigate" if can_navigate else "inspect"),
                    "request_allowed": can_navigate,
                    "apply_ui_allowed": can_navigate,
                    "tooltip": f"VM 文件对象：{path}",
                })

        # 上层磁盘 / VM 测试根 rows
        disk_rows: list[dict] = []

        for root in roots:
            root_id = str(root.get("root_id", "") or "").strip() or "vm_drive_c"
            if root_id == "vm_test_root":
                continue

            root_title = str(root.get("title", root_id) or root_id)
            root_path_text = str(root.get("path", "") or "")

            disk_rows.append({
                "disk_id": root_id,
                "title": root_title,
                "path": root_path_text,
                "permission_state": str(root.get("permission_state", "test") or "test"),
                "status_text": "测试",
                "status_color": "#22C55E",

                # VM 模式下这四个先作为 UI 测试开关，不直接改变 VM Agent 真实能力
                "allow_expand": bool(getattr(self.runtime, "vm_allow_expand", root.get("can_expand", True))),
                "allow_scan": bool(getattr(self.runtime, "vm_allow_scan", root.get("can_scan", True))),
                "allow_index": bool(getattr(self.runtime, "vm_allow_index", root.get("can_index", False))),
                "file_actions_enabled": bool(getattr(self.runtime, "vm_file_actions_enabled", False)),

                "can_adjust": True,
                "tooltip": f"VM 测试根：{root_path_text}",
            })

        return {
            "read_only": not vm_editable,
            "view_mode": "objects",
            "current_path": current_path,
            "current_relative_path": current_relative_path,
            "selected_disk": selected_root_id,
            "file_actions_enabled": bool(getattr(self.runtime, "vm_file_actions_enabled", False)),
            "can_rescan_disk": bool(getattr(self.runtime, "vm_allow_scan", True)),
            "disk_rows": disk_rows,
            "trusted_disk_rows": disk_rows,
            "rows": rows,
        }
    def _should_hide_vm_file_item(self, item: dict) -> bool:
        name = str(item.get("name", "") or "").strip().lower()
        path = str(item.get("path", "") or "").strip().lower()

        # VM 测试根 C:\AI_VM_TEST 下默认显示，避免测试目录被系统名规则误伤。
        if path.startswith("c:\\ai_vm_test"):
            return False

        if bool(item.get("blocked", False)):
            return True

        hidden_names = {
            "$recycle.bin",
            "system volume information",
            "windows",
            "program files",
            "program files (x86)",
            "programdata",
            "pagefile.sys",
            "hiberfil.sys",
            "swapfile.sys",
            "recovery",
            "boot",
            "efi",
        }

        return name in hidden_names

    def on_file_view_changed(self) -> None:
        self.on_object_view_changed()

    def on_file_filter_changed(self) -> None:
        self.on_object_filter_changed()

    def on_file_font_size_changed(self) -> None:
        self.on_object_font_size_changed()

    def on_disk_filter_changed(self) -> None:
        combo = getattr(self.w, "desktop_disk_filter_combo", None)
        if combo is not None:
            self.runtime.disk_filter_key = str(combo.currentData() or "all").strip() or "all"
        self.reload_page()

    def on_disk_font_size_changed(self) -> None:
        combo = getattr(self.w, "desktop_disk_font_combo", None)
        if combo is not None:
            self.runtime.disk_font_size = str(combo.currentData() or "medium").strip() or "medium"
        self.reload_page()

    def on_object_view_changed(self) -> None:
        combo = getattr(self.w, "desktop_object_view_combo", None) or getattr(self.w, "desktop_file_view_combo", None)
        if combo is not None:
            self.runtime.object_view_mode = str(combo.currentData() or "roots").strip() or "roots"
            self._sync_legacy_file_runtime()
        self.reload_page()

    def on_object_filter_changed(self) -> None:
        combo = getattr(self.w, "desktop_object_filter_combo", None) or getattr(self.w, "desktop_file_filter_combo", None)
        if combo is not None:
            self.runtime.object_filter_key = str(combo.currentData() or "all").strip() or "all"
            self._sync_legacy_file_runtime()
        self.reload_page()

    def on_object_font_size_changed(self) -> None:
        combo = getattr(self.w, "desktop_object_font_combo", None) or getattr(self.w, "desktop_file_font_combo", None)
        if combo is not None:
            self.runtime.object_font_size = str(combo.currentData() or "medium").strip() or "medium"
            self._sync_legacy_file_runtime()
        self.reload_page()

    def on_trusted_disk_changed(self) -> None:
        combo = getattr(self.w, "desktop_trusted_disk_combo", None)
        if combo is None:
            return

        next_disk = str(combo.currentData() or "").strip().upper()
        if not next_disk:
            return

        self.runtime.selected_disk = next_disk
        self.runtime.current_directory = ""
        self.runtime.file_navigation_stack.clear()

        root_path = self._host_disk_root_path(next_disk)
        if root_path:
            # 用户主动切换可信磁盘：进入该磁盘根目录。
            # 有缓存则读缓存；无缓存且允许扫描则自动扫描一层。
            self.navigate_host_directory(root_path, push_current=False)
            return

        self.runtime.object_view_mode = "roots"
        self._sync_legacy_file_runtime()
        self.reload_page()

    def on_software_font_size_changed(self) -> None:
        combo = getattr(self.w, "desktop_software_font_combo", None)
        if combo is not None:
            self.runtime.software_font_size = str(combo.currentData() or "medium").strip() or "medium"
        if bool(getattr(self.runtime, "software_table_loaded", False)):
            self.reload_software_panel()
        else:
            self.reload_software_scan_status()

    def select_disk(self, disk_id: str) -> None:
        if self._is_vm_test_backend():
            normalized = str(disk_id or "").strip() or "vm_drive_c"
            setattr(self.runtime, "vm_selected_file_root_id", normalized)
            setattr(self.runtime, "vm_current_relative_path", "")
            self.runtime.selected_disk = normalized
            self._refresh_vm_files_list(root_id=normalized, relative_path="", show_error=True)
            self.reload_page()
            return

        next_disk = str(disk_id or "").strip().upper()
        if not next_disk:
            return

        self.runtime.selected_disk = next_disk
        self.runtime.current_directory = ""
        self.runtime.file_navigation_stack.clear()

        root_path = self._host_disk_root_path(next_disk)
        if root_path:
            # 点击磁盘名属于明确用户动作：
            # 1. 有缓存 -> 显示缓存
            # 2. 无缓存且 allow_scan -> 自动扫描当前磁盘根目录一层
            # 3. 无权限/不可扫描 -> 显示原因
            self.navigate_host_directory(root_path, push_current=False)
            return

        self.runtime.object_view_mode = "roots"
        self._sync_legacy_file_runtime()
        self.reload_page()

    def _host_disk_root_path(self, disk_id: str = "") -> str:
        normalized = str(disk_id or self.runtime.selected_disk or "").strip().upper()
        if not normalized:
            return ""
        try:
            rows = self.service.build_disk_rows(self._current_mode())
        except Exception:
            rows = []
        for row in rows:
            if str(row.get("disk_id", "") or "").strip().upper() == normalized:
                return str(row.get("path", "") or "").strip()
        return f"{normalized}\\"

    def _refresh_file_governance_panel(self) -> None:
        loader = getattr(self.w, "desktop_page_loader", None)
        if loader is None:
            return
        self._remember_table_scrolls()
        loader.load_file_governance_deferred(None)
    def navigate_host_directory(self, target_path: str, *, push_current: bool = True) -> None:
        """
        Host 文件区目录导航入口。

        规则：
        - 点击目录属于明确用户动作，可以自动读取缓存；
        - 如果当前目录没有缓存，但磁盘权限和 allow_scan 允许，则自动扫描当前目录一层；
        - 不做递归全盘扫描；
        - 不绕过磁盘权限。
        """
        path_text = str(target_path or "").strip()
        if not path_text:
            return

        target = Path(path_text).expanduser().resolve(strict=False)
        if not target.exists() or not target.is_dir():
            QMessageBox.information(self.w, "桌面连接", "目标目录不存在或不是目录。")
            return

        next_path = str(target)

        current_path = (
            str(getattr(self.runtime, "host_file_current_path", "") or "").strip()
            or str(getattr(self.runtime, "current_directory", "") or "").strip()
        )

        if push_current and current_path and current_path != next_path:
            self.runtime.file_navigation_stack.append(current_path)

        self.runtime.host_file_current_path = next_path
        self.runtime.current_directory = next_path
        self.runtime.selected_disk = self._drive_key_for_path(next_path)
        self.runtime.object_view_mode = "objects"
        self._sync_legacy_file_runtime()

        cache = self.file_view_cache.read_host_path_cache(next_path)
        rows = cache.get("rows", []) if isinstance(cache, dict) else []

        if isinstance(rows, list) and rows:
            self.load_host_file_cache(next_path)
            return

        ok, reason = self._can_scan_host_file_root(next_path)
        if ok:
            self.scan_host_file_root(
                next_path,
                trigger_source="user_navigation",
                request_id="host_directory_navigation",
            )
            return

        # 不能扫描时只显示当前目录未扫描/不可扫描状态，不回退旧页面。
        self.runtime.host_file_cache_state = self.file_view_cache.empty_state(
            root_path=next_path,
            source="host_cache",
            message=reason or "当前目录尚未扫描，请点击刷新扫描。",
        )
        self.runtime.host_file_scan_status = "empty"
        self.runtime.host_file_scan_message = reason or "当前目录尚未扫描，请点击刷新扫描。"
        self.runtime.host_file_last_error = reason or ""
        self._refresh_file_governance_panel()
    def load_host_file_cache(self, root_path: str) -> None:
        root_text = str(root_path or "").strip()
        if not root_text:
            return
        cache = self.file_view_cache.read_host_path_cache(root_text)
        rows = cache.get("rows", []) if isinstance(cache, dict) else []
        if not isinstance(rows, list) or not rows:
            cache = self.file_view_cache.empty_state(
                root_path=root_text,
                source="host_cache",
                message="当前目录尚未扫描，请点击刷新扫描。",
            )

        self.runtime.host_file_current_root = root_text
        self.runtime.host_file_current_path = str(cache.get("current_path") or root_text)
        self.runtime.host_file_cache_state = cache
        self.runtime.host_file_scan_status = "cached" if rows else "empty"
        self.runtime.host_file_scan_message = (
            f"已读取缓存：{len(rows)} 项。"
            if rows
            else "当前目录尚未扫描，请点击刷新扫描。"
        )
        self.runtime.host_file_last_error = ""
        self.runtime.selected_disk = self._drive_key_for_path(root_text)
        self.runtime.current_directory = self.runtime.host_file_current_path
        self.runtime.object_view_mode = "objects"
        self._sync_legacy_file_runtime()
        self._refresh_file_governance_panel()

    def _can_scan_host_file_root(self, root_path: str) -> tuple[bool, str]:
        mode = self._current_mode()
        if mode not in {"restricted", "trusted"}:
            return False, "当前模式不允许扫描 Host 文件。"
        root_text = str(root_path or "").strip()
        if not root_text:
            return False, "当前没有可扫描的磁盘或目录。"
        disk_id = self._drive_key_for_path(root_text)
        try:
            rows = self.service.build_disk_rows(mode)
        except Exception:
            rows = []
        disk_row = next(
            (
                row for row in rows
                if str(row.get("disk_id", "") or "").strip().upper() == disk_id
            ),
            None,
        )
        if not disk_row:
            return False, "当前磁盘未纳入治理。"
        permission_state = str(disk_row.get("permission_state", "unset") or "unset").strip().lower()
        if permission_state not in {"allow", "once"}:
            return False, "当前磁盘权限为否，不能扫描。"
        if not bool(disk_row.get("allow_scan", False)):
            return False, "当前磁盘未允许扫描。"
        return True, ""

    def scan_host_file_root(
        self,
        root_path: str,
        *,
        trigger_source: str = "user",
        request_id: str = "",
    ) -> None:
        root_text = str(root_path or "").strip()
        ok, reason = self._can_scan_host_file_root(root_text)
        if not ok:
            if str(trigger_source or "user").strip().lower() == "user":
                QMessageBox.information(self.w, "桌面连接", reason)
            self.runtime.host_file_scan_status = "rejected"
            self.runtime.host_file_scan_message = reason
            self.runtime.host_file_last_error = reason
            self._refresh_file_governance_panel()
            return

        if getattr(self.runtime, "host_file_scan_thread", None) is not None:
            return
        scan_id = int(getattr(self.runtime, "host_file_scan_id", 0) or 0) + 1
        self.runtime.host_file_scan_id = scan_id

        thread = QThread(self.w)
        worker = HostFilesRefreshWorker(
            root_path=root_text,
            max_entries=2000,
            recursive=False,
            trigger_source=trigger_source,
            request_id=request_id,
            scan_id=scan_id,
        )
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.progress.connect(self._on_host_file_scan_progress)
        worker.finished.connect(self._on_host_file_scan_finished)
        worker.failed.connect(self._on_host_file_scan_failed)
        worker.finished.connect(thread.quit)
        worker.failed.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        worker.failed.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._clear_host_file_scan_thread)

        self.runtime.host_file_current_root = root_text
        self.runtime.host_file_current_path = root_text
        self.runtime.host_file_trigger_source = str(trigger_source or "user").strip().lower() or "user"
        self.runtime.host_file_request_id = str(request_id or "").strip()
        self.runtime.host_file_scan_status = "scanning"
        self.runtime.host_file_scan_progress = 5
        self.runtime.host_file_scan_message = "正在扫描当前目录..."
        self.runtime.host_file_last_error = ""
        self.runtime.host_file_scan_thread = thread
        self.runtime.host_file_scan_worker = worker
        self.runtime.selected_disk = self._drive_key_for_path(root_text)
        self.runtime.current_directory = root_text
        self.runtime.object_view_mode = "objects"
        self._sync_legacy_file_runtime()
        self._refresh_file_governance_panel()
        thread.start()

    def refresh_host_file_list(self, root_path: str) -> None:
        self.scan_host_file_root(root_path, trigger_source="user")

    def refresh_host_file_cache_for_path(self, root_path: str) -> None:
        """
        开发测试入口：使用正式 HostFilesRefreshWorker 刷新指定目录缓存。

        注意：
        - 仍然走 scan_host_file_root()
        - 仍然受 _can_scan_host_file_root() 权限限制
        - 不扫描全盘
        - 不执行打开/复制/删除
        """
        root_text = str(root_path or "").strip()
        if not root_text:
            QMessageBox.information(self.w, "桌面连接", "缺少要扫描的目录。")
            return

        self.scan_host_file_root(
            root_text,
            trigger_source="developer_cache_refresh",
            request_id="manual_host_file_cache_refresh",
        )
        
    def _current_host_directory(self) -> str:
        for value in (
            getattr(self.runtime, "host_file_current_path", ""),
            getattr(self.runtime, "current_directory", ""),
        ):
            text = str(value or "").strip()
            if text and text != "-":
                return text
        return ""

    def _validate_file_object_name(self, name: str) -> tuple[bool, str]:
        text = str(name or "").strip()
        if not text:
            return False, "名称不能为空。"
        if text in {".", ".."}:
            return False, "名称不能是 . 或 ..。"
        if any(ch in text for ch in '<>:"/\\|?*'):
            return False, "名称不能包含路径分隔符或 Windows 保留字符。"
        return True, ""

    def _host_file_disk_row_for_path(self, target_path: str) -> dict | None:
        disk_id = self._drive_key_for_path(target_path)
        try:
            rows = self.service.build_disk_rows(self._current_mode())
        except Exception:
            rows = []
        for row in rows:
            if str(row.get("disk_id", "") or "").strip().upper() == disk_id:
                return row
        return None

    def _can_host_file_write(
        self,
        target_path: str,
        *,
        required_permission: str,
        object_permission: str = "",
    ) -> tuple[bool, str, dict | None]:
        if self._current_mode() != "trusted":
            return False, "当前不是信任模式，不能执行 Host 文件写入动作。", None

        path_text = str(target_path or "").strip()
        if not path_text:
            return False, "缺少目标路径。", None

        disk_row = self._host_file_disk_row_for_path(path_text)
        if not disk_row:
            return False, "目标路径所在磁盘未纳入治理。", None

        disk_permission = str(disk_row.get("permission_state", "unset") or "unset").strip().lower()
        if disk_permission not in {"allow", "once"}:
            return False, "当前磁盘权限为否，不能执行文件动作。", disk_row

        disk_id = str(disk_row.get("disk_id", "") or "").strip().upper()
        if not self.service.get_disk_file_actions_enabled(disk_id):
            return False, "当前磁盘未允许文件动作。", disk_row

        normalized_required = str(required_permission or "").strip().lower()
        normalized_object = str(object_permission or disk_permission).strip().lower()
        if normalized_required == "allow" and disk_permission != "allow":
            return False, "创建文件或文件夹需要磁盘权限为“是”。", disk_row
        if normalized_required == "rename" and normalized_object not in {"allow", "once"}:
            return False, "当前对象权限不允许重命名。", disk_row

        return True, "", disk_row

    def create_host_file_object(self, kind: str) -> None:
        normalized_kind = str(kind or "").strip().lower()
        if normalized_kind not in {"file", "folder", "directory"}:
            return

        parent_text = self._current_host_directory()
        ok, reason, _disk_row = self._can_host_file_write(parent_text, required_permission="allow")
        if not ok:
            QMessageBox.information(self.w, "桌面连接", reason)
            return

        is_folder = normalized_kind in {"folder", "directory"}
        title = "新建文件夹" if is_folder else "新建文件"
        default_name = "新建文件夹" if is_folder else "新建文件.txt"
        name, accepted = QInputDialog.getText(self.w, title, "名称：", text=default_name)
        if not accepted:
            return

        valid, message = self._validate_file_object_name(name)
        if not valid:
            QMessageBox.warning(self.w, title, message)
            return

        parent = Path(parent_text).expanduser().resolve(strict=False)
        if not parent.exists() or not parent.is_dir():
            QMessageBox.warning(self.w, title, "当前目录不存在，已取消创建。")
            return
        target = parent / str(name).strip()
        if target.exists():
            QMessageBox.warning(self.w, title, "目标已存在，已取消创建。")
            return

        action = "folder.create" if is_folder else "file.create"
        target_type = "directory" if is_folder else "file"
        result = self.qin_runtime.execute_desktop_task({
            "action": action,
            "target_path": str(target),
            "root_id": self._guess_root_id(str(parent)),
            "target_name": str(name).strip(),
            "target_type": target_type,
            "target_id": str(target),
            "arguments": {
                "permission_state": "allow",
                "effective_permission_state": "allow",
                "request_allowed": True,
                "host_execution_enabled": True,
                "target_path": str(target),
                "target_type": target_type,
                "parent_path": str(parent),
                "name": str(name).strip(),
            },
        })
        self._store_desktop_execution_result(result, preferred_backend="vm")
        if isinstance(result, dict) and bool(result.get("ok", False)):
            self.scan_host_file_root(str(parent), trigger_source="user")
            return
        self._refresh_file_governance_panel()

    def create_host_file(self) -> None:
        self.create_host_file_object("file")

    def create_host_folder(self) -> None:
        self.create_host_file_object("folder")

    def rename_host_file_object(self, row: dict) -> None:
        payload = row if isinstance(row, dict) else {}
        source_text = str(payload.get("target_path") or payload.get("path") or "").strip()
        if not source_text:
            return

        source = Path(source_text).expanduser().resolve(strict=False)
        if not source.exists():
            QMessageBox.warning(self.w, "重命名", "目标路径不存在。")
            return

        permission = str(
            payload.get("effective_permission_state", payload.get("permission_state", "unset"))
            or "unset"
        ).strip().lower()
        ok, reason, _disk_row = self._can_host_file_write(
            str(source),
            required_permission="rename",
            object_permission=permission,
        )
        if not ok:
            QMessageBox.information(self.w, "桌面连接", reason)
            return

        new_name, accepted = QInputDialog.getText(self.w, "重命名", "新名称：", text=source.name)
        if not accepted:
            return

        valid, message = self._validate_file_object_name(new_name)
        if not valid:
            QMessageBox.warning(self.w, "重命名", message)
            return

        clean_name = str(new_name).strip()
        if clean_name == source.name:
            return

        dest = source.parent / clean_name
        if dest.exists():
            QMessageBox.warning(self.w, "重命名", "目标名称已存在，已取消重命名。")
            return

        is_folder = source.is_dir()
        action = "folder.rename" if is_folder else "file.rename"
        target_type = "directory" if is_folder else "file"
        result = self.qin_runtime.execute_desktop_task({
            "action": action,
            "target_path": str(source),
            "source_path": str(source),
            "dest_path": str(dest),
            "root_id": str(payload.get("root_id") or self._guess_root_id(str(source))),
            "target_name": source.name,
            "target_type": target_type,
            "target_id": str(payload.get("object_key") or source),
            "arguments": {
                "permission_state": permission,
                "effective_permission_state": permission,
                "request_allowed": True,
                "host_execution_enabled": True,
                "source_path": str(source),
                "dest_path": str(dest),
                "parent_path": str(source.parent),
                "new_name": clean_name,
                # HostWindowsAdapter 当前将 target_path 作为重命名源路径读取；dest_path 是新路径。
                "target_path": str(source),
                "target_new_path": str(dest),
                "new_target_path": str(dest),
                "target_type": target_type,
            },
        })
        self._store_desktop_execution_result(result, preferred_backend="host")
        if isinstance(result, dict) and bool(result.get("ok", False)):
            self.scan_host_file_root(str(source.parent), trigger_source="user")
            return
        self._refresh_file_governance_panel()

    def delete_host_file_object(self, row: dict) -> None:
        payload = row if isinstance(row, dict) else {}
        source_text = str(payload.get("target_path") or payload.get("path") or "").strip()
        if not source_text:
            return

        source = Path(source_text).expanduser().resolve(strict=False)
        if not source.exists():
            QMessageBox.warning(self.w, "删除", "目标路径不存在。")
            return

        permission = str(
            payload.get("effective_permission_state", payload.get("permission_state", "unset"))
            or "unset"
        ).strip().lower()
        ok, reason, _disk_row = self._can_host_file_write(
            str(source),
            required_permission="allow",
            object_permission=permission,
        )
        if not ok:
            QMessageBox.information(self.w, "桌面连接", reason)
            return
        if permission != "allow":
            QMessageBox.information(self.w, "桌面连接", "删除需要对象权限为“是”。")
            return

        is_folder = source.is_dir()
        title = "删除文件夹" if is_folder else "删除文件"
        if QMessageBox.question(
            self.w,
            title,
            "将移动到少府隔离区，可从少府材料恢复。是否继续？",
        ) != QMessageBox.StandardButton.Yes:
            return

        action = "folder.delete" if is_folder else "file.delete"
        target_type = "directory" if is_folder else "file"
        result = self.qin_runtime.execute_desktop_task({
            "action": action,
            "target_path": str(source),
            "source_path": str(source),
            "root_id": str(payload.get("root_id") or self._guess_root_id(str(source))),
            "target_name": source.name,
            "target_type": target_type,
            "target_id": str(payload.get("object_key") or source),
            "arguments": {
                "permission_state": permission,
                "effective_permission_state": permission,
                "request_allowed": True,
                "file_actions_enabled": True,
                "host_execution_enabled": True,
                "confirmed": True,
                "source_path": str(source),
                "original_path": str(source),
                "target_path": str(source),
                "target_type": target_type,
            },
        })
        self._store_desktop_execution_result(result, preferred_backend="host")
        if isinstance(result, dict) and bool(result.get("ok", False)):
            self.scan_host_file_root(str(source.parent), trigger_source="user")
            return
        self._refresh_file_governance_panel()

    def close_host_file_object(self, row: dict) -> None:
        payload = row if isinstance(row, dict) else {}
        target_text = str(payload.get("target_path") or payload.get("path") or "").strip()
        if not target_text:
            return
        permission = str(
            payload.get("effective_permission_state", payload.get("permission_state", "unset"))
            or "unset"
        ).strip().lower()
        if self._current_mode() != "trusted":
            QMessageBox.information(self.w, "桌面连接", "当前不是信任模式，不能执行 Host 关闭动作。")
            return
        if permission not in {"allow", "once"}:
            QMessageBox.information(self.w, "桌面连接", "当前对象权限不允许关闭。")
            return
        target = Path(target_text).expanduser().resolve(strict=False)
        is_folder = bool(payload.get("is_dir", False)) or str(payload.get("target_type", "")).strip().lower() in {"directory", "folder", "目录", "文件夹"}
        action = "folder.close" if is_folder else "file.close"
        result = self.qin_runtime.execute_desktop_task({
            "action": action,
            "target_path": str(target),
            "root_id": str(payload.get("root_id") or self._guess_root_id(str(target))),
            "target_name": str(payload.get("target_name", payload.get("name", target.name)) or target.name),
            "target_type": "directory" if is_folder else "file",
            "target_id": str(payload.get("object_key") or target),
            "arguments": {
                "permission_state": permission,
                "effective_permission_state": permission,
                "request_allowed": True,
                "host_execution_enabled": True,
                "target_path": str(target),
                "target_type": "directory" if is_folder else "file",
            },
        })
        self._store_desktop_execution_result(result, preferred_backend="host")
        data = result.get("data", {}) if isinstance(result, dict) and isinstance(result.get("data", {}), dict) else {}
        if isinstance(result, dict) and not bool(result.get("ok", False)):
            error = str(data.get("error", "") or "")
            if error in {"unsupported_precise_close", "unowned_window_not_supported", "window_not_found", "needs_user_save_confirmation"}:
                QMessageBox.information(self.w, "桌面连接", str(result.get("message", "") or error))
        self._refresh_file_governance_panel()

    def restore_host_file_from_material(self, material_id: str) -> dict:
        return self._restore_host_file_from_material(material_id, expected_type="file")

    def restore_host_folder_from_material(self, material_id: str) -> dict:
        return self._restore_host_file_from_material(material_id, expected_type="directory")

    def _restore_host_file_from_material(self, material_id: str, *, expected_type: str = "") -> dict:
        normalized_id = str(material_id or "").strip()
        if not normalized_id:
            return {"ok": False, "message": "missing material_id", "data": {"error": "material_not_found"}}
        try:
            from services.desktop.qin.shaofu.restore_registry import RestoreRegistry

            material = RestoreRegistry(self.runtime.project_root).find_by_material_id(normalized_id, include_deleted=True)
        except Exception:
            material = None
        if not isinstance(material, dict):
            return {"ok": False, "message": "material not found", "data": {"error": "material_not_found"}}

        original_path = str(material.get("original_path", material.get("source_path", "")) or "").strip()
        quarantine_path = str(material.get("quarantine_path", "") or "").strip()
        target_type = str(material.get("target_type", expected_type) or expected_type or "file").strip().lower()
        is_folder = target_type in {"directory", "folder", "目录", "文件夹"}
        action = "folder.restore" if is_folder else "file.restore"
        result = self.qin_runtime.execute_desktop_task({
            "action": action,
            "target_path": original_path,
            "root_id": self._guess_root_id(original_path),
            "target_name": Path(original_path).name if original_path else str(material.get("target_name", "")),
            "target_type": "directory" if is_folder else "file",
            "target_id": normalized_id,
            "arguments": {
                "permission_state": "allow",
                "effective_permission_state": "allow",
                "request_allowed": True,
                "file_actions_enabled": True,
                "host_execution_enabled": True,
                "material_id": normalized_id,
                "restore_token": str(material.get("restore_token", "") or ""),
                "quarantine_path": quarantine_path,
                "original_path": original_path,
                "target_path": original_path,
                "target_type": "directory" if is_folder else "file",
            },
        })
        self._store_desktop_execution_result(result, preferred_backend="host")
        if isinstance(result, dict) and bool(result.get("ok", False)) and original_path:
            self.scan_host_file_root(str(Path(original_path).parent), trigger_source="user")
        else:
            self._refresh_file_governance_panel()
        return result

    def _on_host_file_scan_progress(self, payload: dict) -> None:
        self._queue_ui_call(lambda payload=payload: self._apply_host_file_scan_progress(payload))

    def _on_host_file_scan_finished(self, payload: dict) -> None:
        self._queue_ui_call(lambda payload=payload: self._apply_host_file_scan_finished(payload))

    def _on_host_file_scan_failed(self, payload: dict) -> None:
        self._queue_ui_call(lambda payload=payload: self._apply_host_file_scan_failed(payload))

    def _is_current_host_file_scan(self, payload: dict) -> bool:
        data = payload if isinstance(payload, dict) else {}
        payload_scan_id = int(data.get("scan_id", 0) or 0)
        current_scan_id = int(getattr(self.runtime, "host_file_scan_id", 0) or 0)
        return payload_scan_id == 0 or payload_scan_id == current_scan_id

    def _apply_host_file_scan_progress(self, payload: dict) -> None:
        if not self._is_current_host_file_scan(payload):
            return
    
        data = payload if isinstance(payload, dict) else {}
        count = int(data.get("entries_count", 0) or 0)
        self.runtime.host_file_scan_status = "scanning"
        self.runtime.host_file_scan_progress = min(95, max(5, count // 20))
        self.runtime.host_file_scan_message = f"正在扫描当前目录：已发现 {count} 项。"

        # 进度阶段不要重建整个文件表，只刷新顶部状态/按钮即可。
        self._refresh_host_file_scan_status_only()

    def _refresh_host_file_scan_status_only(self) -> None:
        loader = getattr(self.w, "desktop_page_loader", None)
        if loader is None:
            return

        if hasattr(loader, "refresh_file_scan_status"):
            loader.refresh_file_scan_status()
            return

        # 没有轻量函数时，先不要在 progress 中整页刷新。
        # 避免扫描过程中反复重建表格。
        return
    def _clear_host_file_scan_thread(self) -> None:
        self.runtime.host_file_scan_thread = None
        self.runtime.host_file_scan_worker = None

    def _apply_host_file_scan_finished(self, result: dict) -> None:
        if not self._is_current_host_file_scan(result):
            return
        
        payload = result if isinstance(result, dict) else {}
        root_path = str(payload.get("current_path") or payload.get("root_path") or self.runtime.host_file_current_root or "").strip()
        cached = self.file_view_cache.write_host_path_cache(root_path, payload)
        rows = cached.get("rows", []) if isinstance(cached.get("rows", []), list) else []
        try:
            print(
                "[HostFileCache] wrote "
                f"current_path={cached.get('current_path', '')!r} "
                f"entries_count={len(rows)} "
                f"path_hash={cached.get('path_hash', '')!r}"
            )
        except Exception:
            pass
        self.runtime.host_file_current_root = str(cached.get("root_path") or root_path)
        self.runtime.host_file_current_path = str(cached.get("current_path") or root_path)
        self.runtime.host_file_cache_state = cached
        self.runtime.host_file_scan_status = "ready"
        self.runtime.host_file_scan_progress = 100
        self.runtime.host_file_scan_message = f"扫描完成：{len(rows)} 项。"
        self.runtime.host_file_last_error = ""
        self.runtime.host_file_trigger_source = str(cached.get("trigger_source") or self.runtime.host_file_trigger_source or "")
        self.runtime.host_file_request_id = str(cached.get("request_id") or self.runtime.host_file_request_id or "")
        self.runtime.selected_disk = self._drive_key_for_path(self.runtime.host_file_current_path)
        self.runtime.current_directory = self.runtime.host_file_current_path
        self.runtime.object_view_mode = "objects"
        self._sync_legacy_file_runtime()
        self._refresh_file_governance_panel()

    def _apply_host_file_scan_failed(self, error: dict) -> None:
        if not self._is_current_host_file_scan(error):
            return
        
        payload = error if isinstance(error, dict) else {}
        message = str(payload.get("message") or payload.get("error") or "Host 文件扫描失败。").strip()
        root_path = str(payload.get("current_path") or payload.get("root_path") or self.runtime.host_file_current_root or "").strip()
        self.runtime.host_file_scan_status = "failed"
        self.runtime.host_file_scan_progress = 0
        self.runtime.host_file_scan_message = message
        self.runtime.host_file_last_error = message
        if root_path:
            self.runtime.host_file_cache_state = self.file_view_cache.empty_state(
                root_path=root_path,
                source="host_cache",
                message=message,
            )
            self.runtime.current_directory = root_path
            self.runtime.object_view_mode = "objects"
        self._sync_legacy_file_runtime()
        self._refresh_file_governance_panel()

    def go_to_parent_directory(self) -> None:
        if self._is_vm_test_backend():
            current_relative = str(getattr(self.runtime, "vm_current_relative_path", "") or "").strip().strip("\\/")
            if not current_relative:
                return
            parent = str(Path(current_relative).parent)
            parent_relative = "" if parent in {"", "."} else parent
            root_id = str(getattr(self.runtime, "vm_selected_file_root_id", "vm_drive_c") or "vm_drive_c")
            self._refresh_vm_files_list(root_id=root_id, relative_path=parent_relative, show_error=True)
            self.reload_page()
            return

        current_text = (
            str(getattr(self.runtime, "host_file_current_path", "") or "").strip()
            or str(getattr(self.runtime, "current_directory", "") or "").strip()
        )
        if not current_text:
            return

        current = Path(current_text).expanduser().resolve(strict=False)
        parent = current.parent

        if parent == current:
            return

        selected_disk = str(getattr(self.runtime, "selected_disk", "") or "").strip().upper()
        disk_root_text = self._host_disk_root_path(selected_disk)
        if disk_root_text:
            disk_root = Path(disk_root_text).expanduser().resolve(strict=False)
            try:
                parent.relative_to(disk_root)
            except Exception:
                parent = disk_root

        self.navigate_host_directory(str(parent), push_current=False)

    def back_to_roots_view(self) -> None:
        if self._is_vm_test_backend():
            root_id = str(getattr(self.runtime, "vm_selected_file_root_id", "vm_drive_c") or "vm_drive_c")
            self._refresh_vm_files_list(root_id=root_id, relative_path="", show_error=True)
            self.reload_page()
            return

        selected_disk = str(getattr(self.runtime, "selected_disk", "") or "").strip().upper()
        root_path = self._host_disk_root_path(selected_disk)

        if root_path:
            self.runtime.file_navigation_stack.clear()
            self.navigate_host_directory(root_path, push_current=False)
            return

        self.runtime.object_view_mode = "roots"
        self._sync_legacy_file_runtime()
        self.reload_page()

    def rescan_current_disk(self) -> None:
        if self._is_vm_test_backend():
            self._ensure_vm_file_runtime_defaults()

            if (
                bool(getattr(self.runtime, "vm_file_scan_in_progress", False))
                or getattr(self.runtime, "vm_file_scan_thread", None) is not None
            ):
                return

            if not bool(getattr(self.runtime, "vm_allow_scan", True)):
                QMessageBox.information(self.w, "桌面连接", "当前 VM 测试根未允许扫描。")
                return

            if (
                str(getattr(self.runtime, "vm_connection_state", "unchecked") or "unchecked").strip().lower()
                != "connected"
                or not bool(getattr(self.runtime, "vm_test_available", False))
            ):
                QMessageBox.information(self.w, "桌面连接", "VM 尚未连接，请先连接 VM。")
                return

            root_id = (
                str(getattr(self.runtime, "vm_selected_file_root_id", "vm_drive_c") or "vm_drive_c").strip()
                or "vm_drive_c"
            )
            relative_path = str(getattr(self.runtime, "vm_current_relative_path", "") or "").strip()
            scan_id = int(getattr(self.runtime, "vm_file_scan_id", 0) or 0) + 1

            thread = QThread(self.w)
            worker = VmFilesRefreshWorker(
                root_id=root_id,
                relative_path=relative_path,
                scan_id=scan_id,
                reason="manual_file_rescan",
                refresh_roots=True,
            )
            worker.moveToThread(thread)

            thread.started.connect(worker.run)
            worker.finished.connect(self._on_vm_files_refresh_finished)
            worker.failed.connect(
                lambda error_text, scan_id=scan_id: self._on_vm_files_refresh_failed(error_text, scan_id)
            )
            worker.finished.connect(thread.quit)
            worker.failed.connect(thread.quit)
            worker.finished.connect(worker.deleteLater)
            worker.failed.connect(worker.deleteLater)
            thread.finished.connect(thread.deleteLater)
            thread.finished.connect(lambda scan_id=scan_id: self._clear_vm_file_scan_thread(scan_id))

            self.runtime.vm_file_scan_thread = thread
            self.runtime.vm_file_scan_worker = worker
            self.runtime.vm_file_scan_id = scan_id
            self.runtime.vm_file_scan_in_progress = True
            self.runtime.vm_file_scan_stage = "requesting"
            self.runtime.vm_file_scan_error = ""
            self.runtime.vm_file_scan_progress_percent = 5
            self.runtime.vm_file_scan_message = "正在请求 VM Agent：/files/roots -> /files/list"
            self.runtime.latest_vm_action_result = {
                "ok": True,
                "adapter_id": "vm",
                "action": "files.rescan",
                "message": self.runtime.vm_file_scan_message,
                "data": {
                    "current_action": "files.rescan",
                    "current_target": root_id,
                    "review_result": "started",
                    "route_result": "vm.files_list",
                    "executed_in": "vm",
                    "scan_id": scan_id,
                    "root_id": root_id,
                    "relative_path": relative_path,
                    "endpoints": ["/health", "/files/roots", "/files/list"],
                },
            }

            self.reload_page()
            thread.start()
            return

        state = self.get_file_governance_state()
        disk_row = next(
            (
                item for item in state.get("disk_rows", [])
                if str(item.get("disk_id", "")).strip().upper()
                == str(state.get("selected_disk", "")).strip().upper()
            ),
            None,
        )

        if not disk_row or not state.get("can_rescan_disk", False):
            QMessageBox.information(self.w, "桌面连接", "当前目录不允许扫描。")
            return

        current_path = (
            str(getattr(self.runtime, "host_file_current_path", "") or "").strip()
            or str(getattr(self.runtime, "current_directory", "") or "").strip()
            or str(disk_row.get("path", "") or "").strip()
        )

        self.scan_host_file_root(current_path, trigger_source="user")


    def _clear_vm_file_scan_thread(self, scan_id: int = 0) -> None:
        current_scan_id = int(getattr(self.runtime, "vm_file_scan_id", 0) or 0)

        # 即使 scan_id 不一致，也不要让 UI 永远停在扫描中。
        self.runtime.vm_file_scan_thread = None
        self.runtime.vm_file_scan_worker = None

        if bool(getattr(self.runtime, "vm_file_scan_in_progress", False)):
            self.runtime.vm_file_scan_in_progress = False

            if not str(getattr(self.runtime, "vm_file_scan_message", "") or "").strip():
                self.runtime.vm_file_scan_message = "VM 文件扫描已结束。"

            if scan_id and scan_id != current_scan_id:
                self.runtime.vm_file_scan_stage = "stale_finished"
                self.runtime.vm_file_scan_message = "VM 文件扫描已结束，旧扫描回执已忽略。"

            self.reload_page()


    def _on_vm_files_refresh_finished(self, payload: object) -> None:
        self._queue_ui_call(lambda payload=payload: self._apply_vm_files_refresh_finished(payload))


    def _on_vm_files_refresh_failed(self, error_text: str, scan_id: int = 0) -> None:
        self._queue_ui_call(
            lambda error_text=error_text, scan_id=scan_id: self._apply_vm_files_refresh_failed(error_text, scan_id)
        )


    def _vm_file_scan_counts(self, files: dict) -> tuple[int, int, int]:
        items = files.get("items", []) if isinstance(files, dict) else []
        if not isinstance(items, list):
            items = []

        total_count = len([item for item in items if isinstance(item, dict)])
        hidden_count = len([
            item for item in items
            if isinstance(item, dict) and self._should_hide_vm_file_item(item)
        ])
        visible_count = max(0, total_count - hidden_count)

        return total_count, visible_count, hidden_count


    def _apply_vm_files_refresh_finished(self, payload: object) -> None:
        result = payload if isinstance(payload, dict) else {}
        scan_id = int(result.get("scan_id", 0) or 0)

        if scan_id != int(getattr(self.runtime, "vm_file_scan_id", 0) or 0):
            return

        root_id = (
            str(result.get("root_id", getattr(self.runtime, "vm_selected_file_root_id", "vm_drive_c")) or "vm_drive_c")
            .strip()
            or "vm_drive_c"
        )
        relative_path = str(
            result.get("relative_path", getattr(self.runtime, "vm_current_relative_path", "")) or ""
        ).strip()

        health_obj = result.get("health")
        health = health_obj if isinstance(health_obj, dict) else {}

        roots_obj = result.get("roots")
        roots = roots_obj if isinstance(roots_obj, dict) else None

        files_obj = result.get("files")
        files = files_obj if isinstance(files_obj, dict) else {}

        ok = bool(result.get("ok", False)) and bool(files.get("ok", False))
        error_text = str(
            result.get("error", "")
            or files.get("error", "")
            or files.get("message", "")
            or ""
        ).strip()

        if roots is not None:
            self.runtime.vm_file_roots_result = roots

        self.runtime.vm_health_result = health or self.runtime.vm_health_result or {}

        if ok:
            self.runtime.vm_file_result = files

            next_root_id = str(files.get("root_id", root_id) or root_id).strip() or root_id
            next_relative_path = str(files.get("relative_path", relative_path) or "").strip()

            self.runtime.vm_selected_file_root_id = next_root_id
            self.runtime.vm_current_relative_path = next_relative_path
            self.runtime.selected_disk = next_root_id
            self.runtime.object_view_mode = "objects"
            self.runtime.current_directory = str(files.get("current_path", "") or "")

            self._sync_legacy_file_runtime()

            total_count, visible_count, hidden_count = self._vm_file_scan_counts(files)

            self.runtime.vm_file_scan_total_count = total_count
            self.runtime.vm_file_scan_visible_count = visible_count
            self.runtime.vm_file_scan_hidden_count = hidden_count
            self.runtime.vm_file_scan_stage = "completed"
            self.runtime.vm_file_scan_error = ""
            self.runtime.vm_file_scan_progress_percent = 100
            root_count = 0
            roots_result = getattr(self.runtime, "vm_file_roots_result", None)
            if isinstance(roots_result, dict):
                roots_list = roots_result.get("roots", [])
                if isinstance(roots_list, list):
                    root_count = len([
                        item for item in roots_list
                        if isinstance(item, dict)
                        and str(item.get("root_id", "") or "").strip() != "vm_test_root"
                    ])
            self.runtime.vm_file_scan_message = (
                f"磁盘根目录 {root_count} 个；当前目录回传 {total_count} 个，"
                f"显示 {visible_count} 个，屏蔽 {hidden_count} 个"
            )
            review_result = "vm_file_list"

        else:
            safe_items = files.get("items", [])
            if not isinstance(safe_items, list):
                safe_items = []

            self.runtime.vm_file_result = {
                **files,
                "ok": False,
                "items": safe_items,
                "root_id": files.get("root_id", root_id),
                "relative_path": files.get("relative_path", relative_path),
                "error": error_text or "VM 文件扫描失败",
            }

            total_count, visible_count, hidden_count = self._vm_file_scan_counts(self.runtime.vm_file_result)

            self.runtime.vm_file_scan_total_count = total_count
            self.runtime.vm_file_scan_visible_count = visible_count
            self.runtime.vm_file_scan_hidden_count = hidden_count
            self.runtime.vm_file_scan_stage = "failed"
            self.runtime.vm_file_scan_error = error_text or "VM 文件扫描失败"
            self.runtime.vm_file_scan_progress_percent = 0
            self.runtime.vm_file_scan_message = f"VM 文件扫描失败：{self.runtime.vm_file_scan_error}"
            review_result = "failed"

        self.runtime.vm_file_scan_in_progress = False
        self.runtime.vm_file_scan_thread = None
        self.runtime.vm_file_scan_worker = None

        self.runtime.latest_vm_action_result = {
            "ok": ok,
            "adapter_id": "vm",
            "action": "files.rescan",
            "message": self.runtime.vm_file_scan_message,
            "data": {
                "current_action": "files.rescan",
                "current_target": root_id,
                "review_result": review_result,
                "route_result": "vm.files_list",
                "executed_in": "vm",
                "scan_id": scan_id,
                "stage": str(result.get("stage", "") or self.runtime.vm_file_scan_stage),
                "root_id": root_id,
                "relative_path": relative_path,
                "total_count": int(getattr(self.runtime, "vm_file_scan_total_count", 0) or 0),
                "visible_count": int(getattr(self.runtime, "vm_file_scan_visible_count", 0) or 0),
                "hidden_count": int(getattr(self.runtime, "vm_file_scan_hidden_count", 0) or 0),
                "hostname": str(health.get("hostname", "") or ""),
                "endpoints": ["/health", "/files/roots", "/files/list"],
                "error": str(getattr(self.runtime, "vm_file_scan_error", "") or ""),
            },
        }

        self.reload_page()


    def _apply_vm_files_refresh_failed(self, error_text: str, scan_id: int = 0) -> None:
        scan_id = int(scan_id or 0)

        if scan_id != int(getattr(self.runtime, "vm_file_scan_id", 0) or 0):
            return

        self.runtime.vm_file_scan_in_progress = False
        self.runtime.vm_file_scan_thread = None
        self.runtime.vm_file_scan_worker = None
        self.runtime.vm_file_scan_stage = "failed"
        self.runtime.vm_file_scan_error = str(error_text or "").strip() or "VM file refresh worker failed"
        self.runtime.vm_file_scan_progress_percent = 0
        self.runtime.vm_file_scan_message = f"VM 文件扫描失败：{self.runtime.vm_file_scan_error}"

        self.runtime.latest_vm_action_result = {
            "ok": False,
            "adapter_id": "vm",
            "action": "files.rescan",
            "message": self.runtime.vm_file_scan_message,
            "data": {
                "current_action": "files.rescan",
                "review_result": "failed",
                "route_result": "vm.files_list",
                "executed_in": "vm",
                "scan_id": scan_id,
                "stage": "worker_failed",
                "error": self.runtime.vm_file_scan_error,
            },
        }

        self.reload_page()
    def _can_adjust_file_governance(self) -> bool:
        return self._current_mode() in {"trusted", "test"} and bool(self.runtime.file_governance_editable)

    def cycle_disk_status(self, disk_id: str) -> None:
        if self._is_vm_test_backend():
            # VM 模式下暂时不循环真实权限，只保留测试态
            self.reload_page()
            return

        if not disk_id or not self._can_adjust_file_governance():
            return

        try:
            self.service.cycle_disk_status(disk_id)
        except Exception as exc:
            QMessageBox.warning(self.w, "桌面连接", f"更新磁盘状态失败：\n{exc}")
            return

        self.reload_page()

    def toggle_disk_expand(self, disk_id: str, value: bool) -> None:
        if self._is_vm_test_backend():
            self.runtime.vm_allow_expand = bool(value)
            self.reload_page()
            return

        if not disk_id or not self._can_adjust_file_governance():
            return

        try:
            self.service.toggle_disk_expand(disk_id, value)
        except Exception as exc:
            QMessageBox.warning(self.w, "桌面连接", f"更新磁盘展开权限失败：\n{exc}")
            return

        self.reload_page()

    def toggle_disk_scan(self, disk_id: str, value: bool) -> None:
        if self._is_vm_test_backend():
            self.runtime.vm_allow_scan = bool(value)
            self.reload_page()
            return

        if not disk_id or not self._can_adjust_file_governance():
            return

        try:
            self.service.toggle_disk_scan(disk_id, value)
        except Exception as exc:
            QMessageBox.warning(self.w, "桌面连接", f"更新磁盘扫描权限失败：\n{exc}")
            return

        self.reload_page()

    def toggle_disk_index(self, disk_id: str, value: bool) -> None:
        if self._is_vm_test_backend():
            self.runtime.vm_allow_index = bool(value)
            self.reload_page()
            return

        if not disk_id or not self._can_adjust_file_governance():
            return

        try:
            self.service.toggle_disk_index(disk_id, value)
        except Exception as exc:
            QMessageBox.warning(self.w, "桌面连接", f"更新磁盘索引权限失败：\n{exc}")
            return

        self.reload_page()

    def cycle_file_permission(self, object_key: str, current_state: str | None = None) -> None:
        if not object_key:
            return
        if not self._can_adjust_file_governance():
            return
        source_state = current_state if current_state is not None else self.runtime.file_permission_overrides.get(object_key, "unset")
        self.runtime.file_permission_overrides[object_key] = self.service.cycle_file_permission(source_state)
        self.reload_page()

    def trigger_file_sandbox_action(
        self,
        *,
        action_kind: str,
        object_key: str,
        target_path: str,
        target_name: str,
        target_type: str,
        root_id: str = "",
        relative_path: str = "",
        permission_state: str = "unset",
        effective_permission_state: str = "",
        permission_source_type: str = "",
        permission_source_key: str = "",
        request_allowed: bool | None = None,
        apply_ui_allowed: bool | None = None,
        file_actions_enabled: bool | None = None,
    ) -> None:
        self.trigger_file_action(
            action_kind=action_kind,
            object_key=object_key,
            target_path=target_path,
            target_name=target_name,
            target_type=target_type,
            root_id=root_id,
            relative_path=relative_path,
            permission_state=permission_state,
            effective_permission_state=effective_permission_state,
            permission_source_type=permission_source_type,
            permission_source_key=permission_source_key,
            request_allowed=request_allowed,
            apply_ui_allowed=apply_ui_allowed,
            file_actions_enabled=file_actions_enabled,
        )

    def trigger_file_action(
        self,
        *,
        action_kind: str,
        object_key: str,
        target_path: str,
        target_name: str,
        target_type: str,
        root_id: str = "",
        relative_path: str = "",
        permission_state: str = "unset",
        effective_permission_state: str = "",
        permission_source_type: str = "",
        permission_source_key: str = "",
        request_allowed: bool | None = None,
        apply_ui_allowed: bool | None = None,
        file_actions_enabled: bool | None = None,
    ) -> None:
        if not target_path:
            return
        mode = self._current_mode()
        action_text = str(action_kind or "").strip().lower()
        normalized_permission = str(effective_permission_state or permission_state or "unset").strip().lower() or "unset"
        normalized_source_type = str(permission_source_type or "").strip().lower()
        normalized_source_key = str(permission_source_key or "").strip()

        if self._is_vm_test_backend():
            if action_text == "navigate":
                normalized_root = str(root_id or getattr(self.runtime, "vm_selected_file_root_id", "vm_drive_c") or "vm_drive_c").strip() or "vm_drive_c"
                normalized_relative = str(relative_path or "").strip()
                if not normalized_relative:
                    state = self.get_vm_file_governance_state()
                    for row in state.get("rows", []):
                        if str(row.get("object_key", "")) == str(object_key or ""):
                            normalized_relative = str(row.get("relative_path", "") or "")
                            break
                if not normalized_relative:
                    normalized_relative = str(target_path or "").strip()
                self._refresh_vm_files_list(root_id=normalized_root, relative_path=normalized_relative, show_error=True)
                self.reload_page()
                return

            if action_text not in {"open", "inspect"}:
                return
            if not bool(file_actions_enabled):
                QMessageBox.information(self.w, "桌面连接", "当前磁盘未允许文件动作。")
                return
            if normalized_permission not in {"allow", "once", "test"} or not bool(request_allowed):
                QMessageBox.information(self.w, "桌面连接", "当前文件对象未获得 VM 测试打开权限。")
                return

            type_text = str(target_type or "").strip().lower()
            is_vm_directory = type_text in {"directory", "folder", "目录", "文件夹"}
            resolved_action = "folder.open" if is_vm_directory else "file.open"
            result = self.qin_runtime.execute_desktop_task({
                "action": resolved_action,
                "target_path": target_path,
                "root_id": root_id or getattr(self.runtime, "vm_selected_file_root_id", "vm_drive_c") or "vm_drive_c",
                "target_name": target_name,
                "target_type": "directory" if is_vm_directory else "file",
                "target_id": object_key,
                "arguments": {
                    "permission_state": normalized_permission,
                    "effective_permission_state": normalized_permission,
                    "permission_source_type": normalized_source_type,
                    "permission_source_key": normalized_source_key,
                    "request_allowed": True,
                    "target_path": target_path,
                    "target_type": "directory" if is_vm_directory else "file",
                    "test_backend": "vm",
                },
            })
            self._store_desktop_execution_result(result, preferred_backend="vm")
            self.reload_page()
            return

        target = Path(target_path)
        is_directory = target.is_dir()
        is_directory_navigation = action_text == "navigate" and is_directory

        if is_directory_navigation:
            self.navigate_host_directory(target_path, push_current=True)
            return

        backend = self.effective_execution_backend()
        if not backend:
            self._show_desktop_actions_unavailable()
            return

        if action_text not in {"open", "inspect"}:
            QMessageBox.information(self.w, "桌面连接", "当前阶段仅开放文件打开动作。")
            return

        if mode == "trusted":
            if not bool(file_actions_enabled):
                QMessageBox.information(self.w, "桌面连接", "当前磁盘未允许文件动作。")
                return
            if normalized_permission not in {"allow", "once"} or not bool(request_allowed):
                QMessageBox.information(self.w, "桌面连接", "当前文件对象未获得 Host 打开权限。")
                return

            resolved_action = "folder.open" if is_directory else "file.open"
            arguments: dict[str, object] = {
                "permission_state": normalized_permission,
                "effective_permission_state": normalized_permission,
                "permission_source_type": normalized_source_type,
                "permission_source_key": normalized_source_key,
                "request_allowed": True,
                "target_path": target_path,
                "target_type": "directory" if is_directory else "file",
            }

            result = self.qin_runtime.execute_desktop_task({
                "action": resolved_action,
                "target_path": target_path,
                "root_id": root_id or self._guess_root_id(target_path),
                "target_name": target_name,
                "target_type": "目录" if is_directory else target_type,
                "target_id": object_key,
                "arguments": arguments,
            })
            self._store_desktop_execution_result(result, preferred_backend="host")
            self.reload_page()
            return

        if mode != "test":
            self._show_desktop_actions_unavailable()
            return

        resolved_action = "folder.open" if is_directory else "file.open"

        action_disk_id = self._drive_key_for_path(target_path)
        if not self.service.get_disk_file_actions_enabled(action_disk_id):
            QMessageBox.information(self.w, "桌面连接", "当前磁盘未允许文件动作。")
            return
        if normalized_permission not in {"allow", "once", "test"} or not bool(request_allowed):
            QMessageBox.information(self.w, "桌面连接", "当前文件对象未获得测试打开权限。")
            return

        arguments: dict[str, object] = {
            "permission_state": normalized_permission,
            "effective_permission_state": normalized_permission,
            "permission_source_type": normalized_source_type,
            "permission_source_key": normalized_source_key,
            "request_allowed": True,
            "target_path": target_path,
            "target_type": "directory" if is_directory else "file",
        }
        if request_allowed is not None:
            arguments["request_allowed"] = bool(request_allowed)
        if apply_ui_allowed is not None:
            arguments["apply_ui_allowed"] = bool(apply_ui_allowed)
        if backend in {"sandbox", "vm"}:
            arguments["test_backend"] = backend

        result = self.qin_runtime.execute_desktop_task({
            "action": resolved_action,
            "target_path": target_path,
            "root_id": root_id or self._guess_root_id(target_path),
            "target_name": target_name,
            "target_type": target_type,
            "target_id": object_key,
            "arguments": arguments,
        })
        result_data = result.get("data", {}) if isinstance(result, dict) else {}
        if bool(result.get("ok", False)) and bool(result_data.get("ui_effect_allowed", False)) and is_directory_navigation:
            if self.runtime.current_directory and self.runtime.current_directory != target_path:
                self.runtime.file_navigation_stack.append(self.runtime.current_directory)
            self.runtime.object_view_mode = "objects"
            self.runtime.current_directory = target_path
            self._sync_legacy_file_runtime()

        # once 当前作为“受限”长期权限使用，不再执行后自动消费。

        self._store_desktop_execution_result(result, preferred_backend=backend)
        self.reload_page()

    def _consume_file_once_permission(self, permission_source_type: str, permission_source_key: str) -> None:
        """
        兼容旧权限消费接口。

        once 当前已作为“受限”长期权限使用，不再执行后自动回退。
        """
        return

    def _legacy_trigger_app_sandbox_action_initial(
        self,
        *,
        app_id: str,
        action_kind: str,
        title: str,
        target_path: str,
        permission_state: str = "unset",
    ) -> None:
        self._remember_software_scroll()
        if not self.desktop_actions_available():
            self._show_desktop_actions_unavailable()
            return
        normalized_path = "" if str(target_path or "").strip() == "-" else str(target_path or "").strip()
        self.runtime.last_software_app_id = str(app_id or "").strip()
        self.runtime.last_software_action = str(action_kind or "").strip()
        result = self.qin_runtime.execute_v2_sandbox({
            "action": action_kind,
            "target_path": normalized_path,
            "root_id": "",
            "target_name": title,
            "target_type": "软件",
            "target_id": app_id,
            "arguments": {
                "permission_state": str(permission_state or "unset").strip().lower() or "unset",
            },
        })
        self._store_software_action_result("sandbox", result)
        if str(action_kind or "").strip().lower() in {"app.locate", "app.launch", "app.close"}:
            self._update_software_row_after_action(str(app_id or "").strip(), result)
            return
        self.reload_software_panel()

    def show_app_action_not_enabled(self, action_label: str) -> None:
        label = str(action_label or "当前操作").strip()
        QMessageBox.information(
            self.w,
            "桌面连接",
            f"{label} 在当前 V2.5 测试阶段尚未启用。",
        )

    def hide_app_from_current_view(self, app_id: str) -> None:
        normalized = str(app_id or "").strip()
        if not normalized:
            return

        if self._is_vm_test_backend():
            self.clear_vm_software_stale_cache(normalized)
            return

        self.runtime.cleared_app_ids.add(normalized)
        self.runtime.last_software_app_id = normalized
        self.runtime.last_software_action = "clear.display"

        state = self.runtime.software_last_state
        if not isinstance(state, dict):
            return

        raw_rows = state.get("rows", [])
        if not isinstance(raw_rows, list):
            raw_rows = []

        rows: list[dict] = [
            row
            for row in raw_rows
            if isinstance(row, dict)
            and str(row.get("app_id", "")).strip() != normalized
        ]

        hidden_raw = state.get("hidden_count", 0)

        if isinstance(hidden_raw, int):
            hidden_count = hidden_raw
        elif isinstance(hidden_raw, str) and hidden_raw.strip().isdigit():
            hidden_count = int(hidden_raw.strip())
        else:
            hidden_count = 0

        updated = dict(state)
        updated["rows"] = rows
        updated["discovered_count"] = len(rows)
        updated["hidden_count"] = hidden_count + 1

        self.runtime.software_last_state = updated
        self.runtime.software_cache_state = updated
        self.runtime.software_table_loaded = bool(rows)

        loader = getattr(self.w, "desktop_page_loader", None)
        panel_loader = getattr(loader, "software_panel_loader", None) if loader is not None else None
        removed = False
        if panel_loader is not None and hasattr(panel_loader, "remove_app_row"):
            removed = bool(panel_loader.remove_app_row(normalized))

        if removed:
            if hasattr(self.service, "get_page_shell_state"):
                page_state = self.service.get_page_shell_state(
                    apps_editable=self.runtime.apps_editable,
                )
            else:
                page_state = {
                    "mode": self._current_mode(),
                    "show_apps": self._current_mode() in {"trusted", "test"},
                    "apps_read_only": not bool(getattr(self.runtime, "apps_editable", False)),
                    "can_scan": False,
                    "can_toggle_apps_editable": False,
                }
            if loader is not None and hasattr(loader, "_software_page_state_for_runtime"):
                page_state = loader._software_page_state_for_runtime(page_state)
            if panel_loader is not None and hasattr(panel_loader, "refresh_panel_chrome"):
                panel_loader.refresh_panel_chrome(updated, page_state)
            return

        # 异常回退：当前表格中找不到目标行时，才重建软件区 rows。
        if loader is not None:
            loader.load_software_panel(
                software_state=updated,
                force_full=True,
            )

    def clear_vm_software_stale_cache(self, app_id: str | None = None) -> None:
        normalized = str(app_id or "").strip()
        self._remember_software_scroll()
        if normalized:
            self.runtime.cleared_app_ids.add(normalized)
            self.runtime.last_software_app_id = normalized
        self.runtime.last_software_action = "vm.clear_stale"
        self._record_vm_software_event(
            "vm.software.clear_stale.requested",
            reason="clear_stale",
            ok=True,
            data={"app_id": normalized},
        )
        self.refresh_vm_apps_list(reason="clear_stale")

    def clear_sandbox_result(self) -> None:
        self.runtime.sandbox_result = None
        self.reload_page()

    def get_readonly_panel_state(self) -> dict:
        page_state = self.service.get_page_state(
            filter_key=self.current_filter_key(),
            apps_editable=self.runtime.apps_editable,
        )
        roots = [item for item in page_state.get("roots", []) if bool(item.get("enabled", False))]
        options = [
            {
                "root_id": str(item.get("root_id", "")).strip(),
                "title": str(item.get("title", item.get("root_id", "-"))).strip() or "-",
                "path": str(item.get("path", "")).strip(),
            }
            for item in roots
            if str(item.get("root_id", "")).strip()
        ]

        selected = self._pick_selected_root(options)
        if selected is not None:
            self.runtime.readonly_selected_root_id = selected["root_id"]

        mode = str(page_state.get("mode", "disabled")).strip() or "disabled"
        readonly_enabled = mode in {"restricted", "trusted", "test"}

        if not readonly_enabled:
            summary = "当前模式未启用基础只读验证。"
        elif selected is None:
            summary = "当前没有可用的目标根目录。"
        else:
            summary = f"当前目标根目录：{selected['title']}"

        return {
            "mode": mode,
            "enabled": readonly_enabled,
            "root_options": options,
            "selected_root_id": selected["root_id"] if selected else "",
            "selected_root_title": selected["title"] if selected else "-",
            "selected_root_path": selected["path"] if selected else "-",
            "summary": summary,
            "can_read_datetime": readonly_enabled,
            "can_use_root_actions": readonly_enabled and selected is not None,
            "result": self.runtime.readonly_result,
        }

    def get_file_governance_state(self) -> dict:
        if self._is_vm_test_backend():
            return self.get_vm_file_governance_state()

        return self.service.get_file_governance_state(
            mode=self._current_mode(),
            disk_filter_key=self.runtime.disk_filter_key,
            object_view_mode=self.runtime.object_view_mode,
            object_filter_key=self.runtime.object_filter_key,
            editable=self.runtime.file_governance_editable,
            selected_disk=self.runtime.selected_disk,
            current_path=self.runtime.current_directory,
            permission_overrides=self.runtime.file_permission_overrides,
            host_file_cache_state=self.runtime.host_file_cache_state,
        )

    def get_software_governance_state(self) -> dict:
        if self._is_vm_test_backend():
            return self.get_vm_software_governance_state()

        state = self.service.get_software_governance_state(
            mode=self._current_mode(),
            filter_key=self.current_filter_key(),
            editable=self.runtime.apps_editable,
        )
        cleared = set(getattr(self.runtime, "cleared_app_ids", set()) or set())
        if not cleared:
            return state

        rows = [
            row for row in state.get("rows", [])
            if str(row.get("app_id", "")).strip() not in cleared
        ]
        hidden_delta = len(state.get("rows", [])) - len(rows)
        updated = dict(state)
        updated["rows"] = rows
        updated["hidden_count"] = int(updated.get("hidden_count", 0)) + len(cleared)
        return updated

    def get_vm_software_governance_state(self) -> dict:
        mode = self._current_mode()
        state = str(getattr(self.runtime, "vm_connection_state", "unchecked") or "unchecked").strip().lower()
        vm_available = bool(getattr(self.runtime, "vm_test_available", False))

        vm_editable = (
            mode == "test"
            and state == "connected"
            and vm_available
            and bool(getattr(self.runtime, "apps_editable", False))
        )

        read_only = not vm_editable

        base_state = {
            "mode": mode,
            "read_only": read_only,
            "apps_read_only": read_only,
            "apps_editable": vm_editable,
            "discovered_count": 0,
            "trusted_count": 0,
            "confirmed_count": 0,
            "hidden_count": 0,
            "rows": [],
            "ok": True,
            "source": "vm",
            "scan_profile": "vm",
            "software_view_mode": "vm",
            "execution_backend": "vm",
        }

        result = self.runtime.vm_apps_result

        if state != "connected" or not vm_available:
            if state == "connecting":
                result = {"ok": False, "apps": [], "error": "虚拟机状态：连接中..."}
            else:
                error = str(getattr(self.runtime, "vm_last_error", "") or "").strip()
                result = {"ok": False, "apps": [], "error": error or "VM 软件读取失败"}

        elif not isinstance(result, dict):
            result = {"ok": False, "apps": [], "error": "VM 软件读取失败"}

        if not isinstance(result, dict) or not bool(result.get("ok", False)):
            error_text = str(
                result.get("error", "VM 软件读取失败")
                if isinstance(result, dict)
                else "VM 软件读取失败"
            )
            row = self._vm_software_error_row(error_text)
            return {
                **base_state,
                "read_only": True,
                "apps_read_only": True,
                "apps_editable": False,
                "discovered_count": 1,
                "hidden_count": 0,
                "rows": [row],
            }

        apps = result.get("apps")
        if not isinstance(apps, list):
            apps = result.get("items")
        if not isinstance(apps, list):
            apps = []

        rows = [
            self._vm_app_row(item, index)
            for index, item in enumerate(apps)
            if isinstance(item, dict)
        ]

        return {
            **base_state,
            "discovered_count": len(rows),
            "trusted_count": len(rows),
            "confirmed_count": len(rows),
            "rows": rows,
        }

    def _vm_software_error_row(self, error_text: str) -> dict:
        tooltip = "VM 软件读取失败：" + str(error_text)
        return {
            "app_id": "vm_apps_error",
            "title": "VM 软件读取失败",
            "permission_label": "禁用",
            "permission_text": "禁用",
            "permission_color": "#EF4444",
            "permission_state": "deny",
            "can_adjust": False,
            "can_locate": False,
            "can_launch": False,
            "can_close": False,
            "can_uninstall": False,
            "can_move": False,
            "can_update": False,
            "can_bind_path": False,
            "can_clear": False,
            "path_short": "-",
            "target_path": "",
            "effective_target_path": "",
            "launch_target_kind": "missing",
            "launch_target_raw": "",
            "effective_launch_target_kind": "missing",
            "effective_launch_target_raw": "",
            "platform": "vm",
            "platform_object_id": "",
            "platform_object_type": "vm_error",
            "entry_path": "",
            "install_dir": "",
            "candidate_kind": "vm_error",
            "route_confidence": "low",
            "status_badge": "失败",
            "status_text": "失败",
            "status_color": "#FEE2E2",
            "status_tooltip": tooltip,
            "tooltip": tooltip,
            "icon_text": "VM",
            "icon_kind": "missing",
            "icon_source_path": "",
        }

    def _vm_app_row(self, item: dict, index: int) -> dict:
        app_id = str(item.get("app_id", item.get("id", f"vm_app_{index}")) or f"vm_app_{index}").strip()
        title = str(item.get("title", item.get("name", app_id)) or app_id).strip()
        target_path = str(item.get("target_path", item.get("path", "")) or "").strip()
        launch_target_kind = str(item.get("launch_target_kind", item.get("kind", "missing")) or "missing").strip()
        launch_target_raw = str(item.get("launch_target_raw", item.get("entry", "")) or "").strip()
        shell_entry = str(item.get("shell_entry", launch_target_raw if launch_target_kind == "appx" else "") or "").strip()
        locate_entry = str(item.get("locate_entry", shell_entry) or "").strip()
        can_close = bool(item.get("can_close", False))
        icon_kind = str(item.get("icon_kind", "app") or "app").strip()

        tooltip = str(item.get("tooltip", "") or "").strip()
        if not tooltip:
            tooltip = f"VM 软件对象：{title}"
        if target_path:
            tooltip = f"{tooltip}\n{target_path}"

        return {
            "app_id": app_id,
            "title": title,
            "permission_label": "测试",
            "permission_text": "测试",
            "permission_color": "#38BDF8",
            "permission_state": "test",
            "effective_permission_state": "test",
            "can_adjust": False,
            "can_locate": bool(item.get("can_locate", False)),
            "can_launch": bool(item.get("can_launch", False)),
            "can_close": can_close,
            "can_uninstall": bool(item.get("can_uninstall", False)),
            "can_move": bool(item.get("can_move", False)),
            "can_update": bool(item.get("can_update", False)),
            "can_bind_path": False,
            "can_clear": True,
            "path_short": str(item.get("path_short", target_path or launch_target_raw or "-") or "-"),
            "target_path": target_path,
            "effective_target_path": target_path,
            "launch_target_kind": launch_target_kind,
            "launch_target_raw": launch_target_raw,
            "shell_entry": shell_entry,
            "locate_entry": locate_entry,
            "effective_launch_target_kind": launch_target_kind,
            "effective_launch_target_raw": launch_target_raw,
            "platform": str(item.get("platform", "vm") or "vm"),
            "platform_object_id": str(item.get("platform_object_id", app_id) or app_id),
            "platform_object_type": str(item.get("platform_object_type", "vm_app") or "vm_app"),
            "entry_path": str(item.get("entry_path", "") or ""),
            "install_dir": str(item.get("install_dir", "") or ""),
            "uninstall_string": str(item.get("uninstall_string", "") or ""),
            "quiet_uninstall_string": str(item.get("quiet_uninstall_string", "") or ""),
            "updater_path": str(item.get("updater_path", "") or ""),
            "winget_id": str(item.get("winget_id", "") or ""),
            "update_source_dir": str(item.get("update_source_dir", "") or ""),
            "process_name": str(item.get("process_name", "") or ""),
            "process_names": item.get("process_names", []) if isinstance(item.get("process_names", []), list) else [str(item.get("process_names", "") or "")],
            "publisher": str(item.get("publisher", "") or ""),
            "version": str(item.get("version", "") or ""),
            "source": str(item.get("source", "") or ""),
            "candidate_kind": str(item.get("candidate_kind", "vm_app") or "vm_app"),
            "route_confidence": str(item.get("route_confidence", "medium") or "medium"),
            "status_badge": "VM测试",
            "status_text": "VM测试",
            "status_color": "#38BDF8",
            "status_tooltip": tooltip,
            "tooltip": tooltip,
            "icon_text": str(item.get("icon_text", "APP") or "APP"),
            "icon_kind": icon_kind,
            "icon_source_path": str(item.get("icon_source_path", "") or ""),
        }

    def get_sandbox_panel_state(self) -> dict:
        mode = self._current_mode()
        backend = str(getattr(self.runtime, "test_backend", "sandbox") or "sandbox").strip().lower()
        result = self.runtime.sandbox_result if isinstance(self.runtime.sandbox_result, dict) else None

        # 只要进入“测试模式 + 沙盒出口”，V2 沙盒面板就应该显示。
        # 不能等到执行过 sandbox 动作后才显示，否则用户会误以为面板被删除。
        visible = bool(mode == "test" and backend == "sandbox")

        data = (
            result.get("data", {})
            if isinstance(result, dict) and isinstance(result.get("data", {}), dict)
            else {}
        )

        if not visible:
            summary = "当前模式未启用 V2 沙盒测试。"
        elif result:
            summary = (
                f"最近动作：{data.get('current_action', '-')} | "
                f"目标：{data.get('current_target', '-')} | "
                f"审议：{data.get('review_result', '-')}"
            )
        else:
            summary = "V2 沙盒测试面板已启用，尚未执行沙盒动作。"

        return {
            "visible": visible,
            "summary": summary,
            "result": result if visible else None,
        }

    def _pick_selected_root(self, options: list[dict]) -> dict | None:
        if not options:
            return None
        for root in options:
            if root["root_id"] == self.runtime.readonly_selected_root_id:
                return root
        for root in options:
            if root["root_id"] == "project_root":
                return root
        return options[0]

    def _selected_root_target(self) -> dict | None:
        selected = self.get_readonly_panel_state().get("selected_root_id", "")
        if not selected:
            self.runtime.readonly_result = {
                "ok": False,
                "action": "",
                "adapter_id": "",
                "message": "尚未选择目标根目录。",
                "data": {},
            }
            self.reload_page()
            return None

        for item in self.get_readonly_panel_state().get("root_options", []):
            if item.get("root_id") == selected:
                return item

        self.runtime.readonly_result = {
            "ok": False,
            "action": "",
            "adapter_id": "",
            "message": "未找到当前选择的目标根目录。",
            "data": {},
        }
        self.reload_page()
        return None

    def _guess_root_id(self, target_path: str) -> str:
        normalized = Path(target_path).expanduser().resolve(strict=False)
        state = self.service.get_page_state(
            filter_key=self.current_filter_key(),
            apps_editable=self.runtime.apps_editable,
        )
        for item in state.get("roots", []):
            root_path = str(item.get("path", "")).strip()
            if not root_path or not bool(item.get("enabled", False)):
                continue
            try:
                normalized.relative_to(Path(root_path).expanduser().resolve(strict=False))
                return str(item.get("root_id", "")).strip()
            except Exception:
                continue
        return ""

    def _drive_key_for_path(self, target_path: str) -> str:
        text = str(target_path or "").strip()
        if not text:
            return ""
        path = Path(text).expanduser().resolve(strict=False)
        drive = str(path.drive or path.anchor or "").strip()
        return drive.upper() if drive else str(path).strip().upper()

    def _is_path_under_enabled_root(self, target_path: Path) -> bool:
        normalized = target_path.expanduser().resolve(strict=False)
        state = self.service.get_page_state(
            filter_key=self.current_filter_key(),
            apps_editable=self.runtime.apps_editable,
        )
        for item in state.get("roots", []):
            root_path = str(item.get("path", "")).strip()
            if not root_path or not bool(item.get("enabled", False)):
                continue
            try:
                normalized.relative_to(Path(root_path).expanduser().resolve(strict=False))
                return True
            except Exception:
                continue
        return False

    def _run_readonly_task(self, task: dict) -> None:
        self.runtime.readonly_result = self.qin_runtime.execute(task)
        self.reload_page()

    def _is_vm_connection_failure_result(self, result: object) -> bool:
        if not isinstance(result, dict) or bool(result.get("ok", False)):
            return False

        data = result.get("data", {})
        data = data if isinstance(data, dict) else {}

        text = " ".join(
            str(value or "")
            for value in (
                result.get("error"),
                result.get("message"),
                data.get("error"),
                data.get("message"),
                data.get("vm_agent_message"),
            )
        ).lower()

        markers = (
            "urlopen",
            "timed out",
            "timeout",
            "connection refused",
            "actively refused",
            "winerror 10061",
            "no route",
            "unreachable",
            "failed to establish",
            "connection failed",
            "connection error",
            "连接失败",
            "拒绝连接",
            "超时",
            "无法连接",
        )

        return any(marker in text for marker in markers)

    def _vm_result_error_text(self, result: object) -> str:
        if not isinstance(result, dict):
            return "VM 连接失败"

        data = result.get("data", {})
        data = data if isinstance(data, dict) else {}

        for value in (
            result.get("error"),
            data.get("error"),
            result.get("message"),
            data.get("message"),
            data.get("vm_agent_message"),
        ):
            text = str(value or "").strip()
            if text:
                return text

        return "VM 连接失败"

    def trigger_app_sandbox_action(
        self,
        *,
        row: dict | None = None,
        app_id: str,
        action_kind: str,
        title: str,
        target_path: str,
        permission_state: str = "unset",
        launch_target_kind: str = "missing",
        launch_target_raw: str = "",
        shell_entry: str = "",
        locate_entry: str = "",
        platform: str = "unknown",
        platform_object_id: str = "",
        platform_object_type: str = "",
        entry_path: str = "",
        install_dir: str = "",
        uninstall_string: str = "",
        quiet_uninstall_string: str = "",
        updater_path: str = "",
        winget_id: str = "",
        update_source_dir: str = "",
        process_name: str = "",
        process_names: object = None,
        publisher: str = "",
        version: str = "",
        source: str = "",
        category: str = "",
        candidate_kind: str = "",
        path_status: str = "",
        route_confidence: str = "low",
        confirmed: bool = False,
        source_path: str = "",
        dest_root: str = "",
        dest_path: str = "",
        move_mode: str = "",
        relocate_strategy: str = "",
        relocate_target_mode: str = "",
        path_namespace: str = "",
    ) -> None:
        self._remember_software_scroll()
        backend = self.software_action_backend(row)
        if not backend:
            self._show_desktop_actions_unavailable()
            return

        normalized_path = "" if str(target_path or "").strip() == "-" else str(target_path or "").strip()
        self.runtime.last_software_app_id = str(app_id or "").strip()
        self.runtime.last_software_action = str(action_kind or "").strip()
        normalized_path_namespace = str(path_namespace or "").strip()
        if not normalized_path_namespace:
            normalized_path_namespace = "vm_windows" if backend == "vm" else ("host_windows" if backend == "host" else "sandbox")
        target_environment = {
            "vm": "virtual_machine",
            "host": "local_host",
        }.get(backend, "sandbox_simulation")
        agent_id = {
            "vm": "desktop_vm_agent",
            "host": "host_adapter",
        }.get(backend, "sandbox_adapter")

        task = {
            "action": action_kind,
            "target_path": normalized_path,
            "root_id": "",
            "target_name": title,
            "target_type": "软件",
            "target_id": app_id,
            "arguments": {
                "test_backend": backend,
                "execution_backend": backend,
                "adapter_stage": backend,
                "target_environment": target_environment,
                "path_namespace": normalized_path_namespace,
                "machine_id": "",
                "agent_id": agent_id,
                "permission_state": str(permission_state or "unset").strip().lower() or "unset",
                "effective_permission_state": str(permission_state or "unset").strip().lower() or "unset",
                "launch_target_kind": str(launch_target_kind or "missing").strip() or "missing",
                "launch_target_raw": str(launch_target_raw or "").strip(),
                "shell_entry": str(shell_entry or "").strip(),
                "locate_entry": str(locate_entry or "").strip(),
                "platform": str(platform or "unknown").strip() or "unknown",
                "platform_object_id": str(platform_object_id or "").strip(),
                "platform_object_type": str(platform_object_type or "").strip(),
                "entry_path": str(entry_path or "").strip(),
                "install_dir": str(install_dir or "").strip(),
                "uninstall_string": str(uninstall_string or "").strip(),
                "quiet_uninstall_string": str(quiet_uninstall_string or "").strip(),
                "updater_path": str(updater_path or "").strip(),
                "winget_id": str(winget_id or "").strip(),
                "update_source_dir": str(update_source_dir or "").strip(),
                "process_name": str(process_name or "").strip(),
                "process_names": process_names if isinstance(process_names, list) else [],
                "publisher": str(publisher or "").strip(),
                "version": str(version or "").strip(),
                "source": str(source or "").strip(),
                "category": str(category or "").strip(),
                "candidate_kind": str(candidate_kind or "").strip(),
                "path_status": str(path_status or "").strip(),
                "route_confidence": str(route_confidence or "low").strip() or "low",
                "app_id": str(app_id or "").strip(),
                "confirmed": bool(confirmed),
                "source_path": str(source_path or install_dir or normalized_path or "").strip(),
                "dest_root": str(dest_root or "").strip(),
                "dest_path": str(dest_path or "").strip(),
                "move_target_path": str(dest_path or "").strip(),
                "move_mode": str(move_mode or "").strip(),
                "relocate_strategy": str(relocate_strategy or "").strip(),
                "relocate_target_mode": str(relocate_target_mode or "").strip(),
                "path_namespace": normalized_path_namespace,
            },
        }
        result = self.qin_runtime.execute_desktop_task(task)

        self._store_software_action_result(backend, result)
        if (
            self._is_vm_test_backend()
            and self._is_vm_connection_failure_result(result)
        ):
            self._mark_vm_disconnected(self._vm_result_error_text(result))

        if backend == "vm" and str(action_kind or "").strip().lower() == "app.relocate" and isinstance(result, dict) and not bool(result.get("ok", False)):
            self._show_vm_relocate_failure_hint(result)

        # once 当前作为“受限”长期权限使用，不再执行后自动消费。

        if (
            backend == "vm"
            and str(action_kind or "").strip().lower() == "app.relocate"
            and isinstance(result, dict)
            and bool(result.get("ok", False))
        ):
            self.refresh_vm_apps_list(reason="app_relocate_completed")
            return

        if str(action_kind or "").strip().lower() in {"app.locate", "app.launch", "app.close"}:
            self._update_software_row_after_action(str(app_id or "").strip(), result)
            return

        self.reload_page()

    def _store_software_action_result(self, backend: str, result: dict) -> None:
        self._store_desktop_execution_result(result, preferred_backend=backend)

    def _store_desktop_execution_result(self, result: dict, *, preferred_backend: str = "") -> None:
        data = result.get("data", {}) if isinstance(result, dict) and isinstance(result.get("data", {}), dict) else {}
        normalized_backend = str(preferred_backend or "").strip().lower()
        executed_in = str(
            data.get("executed_in", data.get("execution_backend", normalized_backend))
            or normalized_backend
        ).strip().lower()
        adapter_id = str(result.get("adapter_id", data.get("adapter_id", "")) if isinstance(result, dict) else "").strip().lower()
        result_backend = executed_in or adapter_id or normalized_backend
        is_sandbox = result_backend in {"sandbox", "sandbox_adapter"}
        if is_sandbox and self._current_mode() == "test":
            self.runtime.sandbox_result = result
            return
        self.runtime.latest_desktop_action_result = result
        if result_backend in {"host", "host_windows"} or normalized_backend == "host":
            self.runtime.latest_host_action_result = result
        if result_backend == "vm" or normalized_backend == "vm":
            self.runtime.latest_vm_action_result = result

    def _update_software_row_after_action(self, app_id: str, result: dict) -> None:
        normalized_app_id = str(app_id or "").strip()
        if not normalized_app_id:
            return

        raw_state = getattr(self.runtime, "software_last_state", None)
        if not isinstance(raw_state, dict):
            return

        state: dict[str, Any] = dict(raw_state)

        raw_rows = state.get("rows", [])
        if not isinstance(raw_rows, list):
            return

        rows: list[dict[str, Any]] = [
            dict(row) for row in raw_rows
            if isinstance(row, dict)
        ]

        result_data = result.get("data", {}) if isinstance(result, dict) and isinstance(result.get("data", {}), dict) else {}
        ok = bool(result.get("ok", False)) if isinstance(result, dict) else False
        action = str(result_data.get("current_action", result.get("action", self.runtime.last_software_action)) or "").strip()
        message = str(result.get("message", "") or result_data.get("message", "") or "").strip()
        error = str(result.get("error", "") or result_data.get("error", "") or "").strip()

        badge = "已执行" if ok else "未关闭" if action == "app.close" else "失败"
        color = "#22C55E" if ok else "#F97316" if action == "app.close" else "#EF4444"
        tooltip = message or error or "软件动作已返回。"

        updated_row: dict[str, Any] | None = None

        for index, row in enumerate(rows):
            if str(row.get("app_id", "") or "").strip() != normalized_app_id:
                continue

            next_row = dict(row)
            next_row.update({
                "status_badge": badge,
                "status_color": color,
                "status_tooltip": tooltip,
                "last_action": action,
                "last_action_ok": ok,
                "last_action_error": error,
            })

            rows[index] = next_row
            updated_row = next_row
            break

        if updated_row is None:
            return

        next_state: dict[str, Any] = dict(state)
        next_state["rows"] = rows

        self.runtime.software_last_state = next_state
        self.runtime.software_cache_state = next_state

        try:
            if hasattr(self.software_view_cache, "update_row_permission"):
                self.software_view_cache.update_row_permission(normalized_app_id, {
                    "status_badge": updated_row.get("status_badge", ""),
                    "status_color": updated_row.get("status_color", ""),
                    "status_tooltip": updated_row.get("status_tooltip", ""),
                    "last_action": updated_row.get("last_action", ""),
                    "last_action_ok": updated_row.get("last_action_ok", False),
                    "last_action_error": updated_row.get("last_action_error", ""),
                })
        except Exception:
            pass

        loader = getattr(self.w, "desktop_page_loader", None)
        panel_loader = getattr(loader, "software_panel_loader", None) if loader is not None else None
        if panel_loader is not None and hasattr(panel_loader, "refresh_one_app_row"):
            panel_loader.refresh_one_app_row(app_id=normalized_app_id, row=updated_row)

    def _show_vm_relocate_failure_hint(self, result: dict) -> None:
        data = result.get("data", {}) if isinstance(result.get("data"), dict) else {}
        error = str(result.get("error", "") or data.get("error", "") or data.get("error_category", "") or "").strip()
        error_category = str(data.get("error_category", "") or "").strip()
        relocate_status = str(data.get("relocate_status", "") or "").strip()
        winerror = str(data.get("winerror", "") or "").strip()
        text = " ".join([error, error_category, relocate_status, winerror]).lower()

        message = ""

        if (
            "process_path_still_in_use" in text
            or "source_path_in_use" in text
            or ("original_rename_failed" in text and winerror == "32")
        ):
            processes = data.get("running_processes", []) if isinstance(data.get("running_processes"), list) else []
            lines = [
                "检测到软件仍在后台运行。",
                "请先在虚拟机中完全退出该软件，然后再重试迁移。",
            ]

            shown = 0
            for item in processes:
                if not isinstance(item, dict) or shown >= 5:
                    continue
                name = str(item.get("name", "") or "-")
                pid = str(item.get("pid", "") or "-")
                lines.append(f"- {name} / pid={pid}")
                shown += 1

            message = "\n".join(lines)

        elif "process_close_failed" in text:
            message = "无法关闭相关进程，请在虚拟机中手动关闭软件后重试。"
        elif "service_stop_failed" in text:
            message = "无法停止相关服务，请在虚拟机中检查服务状态后重试。"
        elif "admin_required" in text:
            message = "VM Agent 需要以管理员权限运行后才能执行该操作。"
        elif "destination_exists" in text:
            message = "目标位置已存在同名目录，请更换目标位置后重试。"
        elif "copy_failed" in text:
            message = "复制文件失败，请检查目标磁盘空间或权限。"

        if message:
            QMessageBox.warning(self.w, "软件迁移", message)

    def bind_app_path(self, app_id: str) -> None:
        selected_path, _selected_filter = QFileDialog.getOpenFileName(
            self.w,
            "选择软件入口文件",
            str(self.runtime.project_root),
            "Supported Files (*.exe *.lnk *.url);;Executable (*.exe);;Shortcut (*.lnk);;URL Shortcut (*.url)",
        )
        if not selected_path:
            return

        try:
            self.service.bind_app_path(app_id, selected_path)
        except Exception as exc:
            QMessageBox.warning(self.w, "桌面连接", f"补充软件路径失败：\n{exc}")
            return

        self.reload_software_panel()

    def _on_software_scan_finished(self, result: object) -> None:
        self._queue_ui_call(lambda result=result: self._apply_software_scan_finished(result))

    def _apply_software_scan_finished(self, result: object) -> None:
        """
        Host / sandbox 软件扫描完成回调。

        注意：
        - 这个回调来自 SoftwareScanWorker，本质是 Host 软件扫描；
        - VM 软件扫描不应该走这里；
        - 如果因为旧信号或残留线程误入 VM 模式，必须阻断，避免 Host 软件写进 VM 软件区。
        """
        self._remember_software_area_scroll()
        self._stop_software_scan_fake_progress()
        self.runtime.software_scan_in_progress = False

        # VM 模式下不允许把 Host SoftwareScanWorker 的结果写入软件区。
        # 正确的 VM 刷新入口是 refresh_vm_apps_list() -> _apply_vm_apps_refresh_finished()
        if self._vm_software_context_ready():
            self.runtime.software_scan_stage = "ignored"
            self.runtime.software_scan_message = "已忽略 Host 软件扫描结果：当前处于 VM 软件区。"
            self.runtime.software_scan_progress_percent = 0
            self.runtime.software_scan_log_lines = [
                *self.runtime.software_scan_log_lines[-23:],
                "host software scan result ignored in vm context",
            ]

            # 重新显示 VM 软件 state，防止旧 Host 结果残留。
            state = self.get_vm_software_governance_state()
            rows = state.get("rows", []) if isinstance(state.get("rows", []), list) else []

            self.runtime.software_cache_state = state
            self.runtime.software_cache_loaded = bool(rows)
            self.runtime.software_cache_source = "vm"
            self.runtime.software_last_state = dict(state)
            self.runtime.software_table_loaded = bool(rows)

            loader = getattr(self.w, "desktop_page_loader", None)
            if loader is not None:
                loader.load_software_panel(
                    software_state=state,
                    force_full=bool(rows),
                )

            self._restore_software_area_scroll_later()
            return

        self.runtime.cleared_app_ids.clear()

        count = int(result) if isinstance(result, int) else 0
        profile = str(
            getattr(self.runtime, "software_scan_profile", "quick") or "quick"
        ).strip().lower()

        if profile not in {"quick", "full"}:
            profile = "quick"

        label = "快速扫描" if profile == "quick" else "完整扫描"

        self.runtime.software_scan_stage = "completed"
        self.runtime.software_scan_message = f"{label}完成，发现 {count} 个对象"
        self.runtime.software_scan_progress_percent = 100

        try:
            cached = self.rebuild_and_save_software_view_cache(scan_profile=profile)
        except Exception as exc:
            self.runtime.software_scan_log_lines = [
                *self.runtime.software_scan_log_lines[-23:],
                f"software view cache build failed: {exc}",
            ]
            self.reload_software_scan_status()
            self._restore_software_area_scroll_later()
            return

        self.runtime.software_cache_state = cached
        self.runtime.software_cache_loaded = True
        self.runtime.software_cache_source = "cache"
        self.runtime.software_last_state = dict(cached)
        self.runtime.software_table_loaded = True

        self.w.desktop_page_loader.load_software_panel(
            software_state=cached,
            force_full=True,
        )
        self._restore_software_area_scroll_later()

    def _on_software_scan_failed(self, error_text: str) -> None:
        self._queue_ui_call(lambda error_text=error_text: self._apply_software_scan_failed(error_text))

    def _apply_software_scan_failed(self, error_text: str) -> None:
        self._stop_software_scan_fake_progress()
        self.runtime.software_scan_in_progress = False

        profile = str(getattr(self.runtime, "software_scan_profile", "quick") or "quick").strip().lower()
        label = "快速扫描" if profile == "quick" else "完整扫描"

        self.runtime.software_scan_stage = "failed"
        self.runtime.software_scan_message = f"{label}失败"
        self.runtime.software_scan_log_lines = [
            *self.runtime.software_scan_log_lines[-23:],
            f"{label} failed: {error_text}",
        ]

        self.reload_software_scan_status()
        QMessageBox.warning(self.w, "桌面连接", f"重新扫描软件失败：\n{error_text}")

    def _on_software_scan_progress(self, payload: object) -> None:
        self._queue_ui_call(lambda payload=payload: self._apply_software_scan_progress(payload))

    def _apply_software_scan_progress(self, payload: object) -> None:
        if not isinstance(payload, dict):
            return
        stage = str(payload.get("stage", "") or "").strip()
        message = str(payload.get("message", "") or "").strip()
        stats = payload.get("stats")
        percent = payload.get("percent")
        if stage:
            self.runtime.software_scan_stage = stage
        if message:
            self.runtime.software_scan_message = message
        if isinstance(stats, dict):
            self.runtime.software_scan_progress_stats = dict(stats)
            profile = str(stats.get("scan_profile", "") or "").strip().lower()
            if profile in {"quick", "full"}:
                self.runtime.software_scan_profile = profile
        if percent is not None:
            try:
                new_percent = int(percent)
                old_percent = int(getattr(self.runtime, "software_scan_progress_percent", 0) or 0)
                self.runtime.software_scan_progress_percent = max(old_percent, new_percent)
            except Exception:
                pass
        self.reload_software_scan_status()

    def _on_software_scan_log(self, line: str) -> None:
        self._queue_ui_call(lambda line=line: self._apply_software_scan_log(line))

    def _apply_software_scan_log(self, line: str) -> None:
        text = str(line or "").strip()
        if not text:
            return
        self.runtime.software_scan_log_lines = [*self.runtime.software_scan_log_lines[-23:], text]
        self.reload_software_scan_status()
