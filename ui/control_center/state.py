from __future__ import annotations

from copy import deepcopy

from PySide6.QtWidgets import QMessageBox


class ControlCenterState:
    def __init__(self, window):
        self.w = window
        self.applied_snapshots = {
            "model": {},
            "style": {},
            "info": {},
        }

    # =========================================================
    # 基础工具
    # =========================================================
    def _normalize_dict(self, data: dict | None) -> dict:
        if not isinstance(data, dict):
            return {}
        normalized = {}
        for key, value in data.items():
            if isinstance(value, str):
                normalized[key] = value.strip()
            else:
                normalized[key] = value
        return normalized

    def _snapshot_equals(self, left: dict, right: dict) -> bool:
        return self._normalize_dict(left) == self._normalize_dict(right)

    def page_key_from_index(self, index: int) -> str:
        mapping = {0: "model", 1: "style", 2: "info"}
        return mapping.get(index, "model")

    # =========================================================
    # 快照构建
    # =========================================================
    def build_model_snapshot(self) -> dict:
        scheme_data = self.w.model_scheme_combo.currentData() if getattr(self.w, "model_scheme_combo", None) else {}
        if not isinstance(scheme_data, dict):
            scheme_data = {}

        scheme_voice_id = scheme_data.get("voice_id") or scheme_data.get("voice_profile_id") or ""

        tts_backend = self.w.tts_model_combo.currentData() if getattr(self.w, "tts_model_combo", None) else None
        if isinstance(tts_backend, str):
            tts_backend = tts_backend.strip().lower()

        return {
            "model_id": self.w.chat_model_combo.currentData() if getattr(self.w, "chat_model_combo", None) else None,
            "role_id": self.w.role_model_combo.currentData() if getattr(self.w, "role_model_combo", None) else None,
            "tts_backend": tts_backend,
            "output_mode": self.w.output_mode_combo.currentData() if getattr(self.w, "output_mode_combo", None) else None,
            "async_voice": self.w.async_voice_combo.currentData() if getattr(self.w, "async_voice_combo", None) else None,
            "scheme_role_id": scheme_data.get("role_id", ""),
            "scheme_style_id": scheme_data.get("style_id", ""),
            "scheme_voice_id": scheme_voice_id,
        }

    def build_style_snapshot(self) -> dict:
        style_data = self.w.current_style_config_combo.currentData() if getattr(self.w, "current_style_config_combo", None) else {}
        voice_data = self.w.current_voice_config_combo.currentData() if getattr(self.w, "current_voice_config_combo", None) else {}

        style_id = style_data.get("id", "") if isinstance(style_data, dict) else ""
        voice_id = voice_data.get("id", "") if isinstance(voice_data, dict) else ""

        return {
            "style_id": style_id,
            "voice_id": voice_id,
            "style_form": self.w.collect_style_form_data(),
            "voice_form": self.w.collect_voice_form_data(),
        }

    def build_info_snapshot(self) -> dict:
        return self.w.collect_info_form_data()

    def build_snapshot(self, page_key: str) -> dict:
        if page_key == "model":
            return self.build_model_snapshot()
        if page_key == "style":
            return self.build_style_snapshot()
        if page_key == "info":
            return self.build_info_snapshot()
        return {}

    # =========================================================
    # 脏状态中心
    # =========================================================
    def set_dirty(self, page_key: str, dirty: bool):
        if self.w._loading:
            return

        if page_key == "model":
            self.w.page_dirty["model"] = False
            self.update_window_title()
            return

        self.w.page_dirty[page_key] = dirty
        self.update_window_title()

    def refresh_dirty(self, page_key: str):
        if self.w._loading:
            return

        if page_key == "model":
            self.w.page_dirty["model"] = False
            self.update_window_title()
            return

        current = self.build_snapshot(page_key)
        applied = self.applied_snapshots.get(page_key, {})
        self.w.page_dirty[page_key] = not self._snapshot_equals(current, applied)
        self.update_window_title()

    def refresh_all_dirty(self):
        if self.w._loading:
            return
        for page_key in ["model", "style", "info"]:
            self.refresh_dirty(page_key)

    def capture_snapshot(self, page_key: str):
        self.applied_snapshots[page_key] = deepcopy(self.build_snapshot(page_key))
        self.w.page_dirty[page_key] = False
        self.update_window_title()

    def capture_all_snapshots(self):
        for page_key in ["model", "style", "info"]:
            self.applied_snapshots[page_key] = deepcopy(self.build_snapshot(page_key))
            self.w.page_dirty[page_key] = False
        self.update_window_title()

    def discard_page_changes(self, page_key: str):
        self.capture_snapshot(page_key)

    def update_window_title(self):
        current_key = self.page_key_from_index(self.w.stack.currentIndex())
        page_name_map = {
            "model": "运行配置",
            "style": "风格设计",
            "info": "角色组合",
        }

        if self.w.page_dirty.get(current_key, False):
            self.w.setWindowTitle(f'控制中心 *未应用: {page_name_map.get(current_key, current_key)}')
        else:
            self.w.setWindowTitle("控制中心")

    def sync_nav_buttons(self):
        index = self.w.stack.currentIndex()
        self.w.btn_model.setChecked(index == 0)
        self.w.btn_style.setChecked(index == 1)
        self.w.btn_info.setChecked(index == 2)

    def ask_apply_changes(self, page_key: str) -> str:
        page_name_map = {
            "model": "运行配置页",
            "style": "风格设计页",
            "info": "组合与模拟页",
        }
        page_name = page_name_map.get(page_key, "当前页面")

        msg = QMessageBox(self.w)
        msg.setWindowTitle("检测到未应用修改")
        msg.setText(f"{page_name}有未应用的修改，是否先应用？")

        apply_btn = msg.addButton("应用并切换", QMessageBox.ButtonRole.AcceptRole)
        discard_btn = msg.addButton("不应用，直接切换", QMessageBox.ButtonRole.DestructiveRole)
        msg.addButton("取消", QMessageBox.ButtonRole.RejectRole)
        msg.exec()

        clicked = msg.clickedButton()
        if clicked == apply_btn:
            return "apply"
        if clicked == discard_btn:
            return "discard"
        return "cancel"

    def try_switch_page(self, page_index: int, target_key: str):
        current_index = self.w.stack.currentIndex()
        current_key = self.page_key_from_index(current_index)
        if current_key == "model":
            self.w.page_dirty["model"] = False
            self.w.stack.setCurrentIndex(page_index)
            self.sync_nav_buttons()
            self.update_window_title()
            return
        if self.w.page_dirty.get(current_key, False):
            result = self.ask_apply_changes(current_key)
            if result == "cancel":
                self.sync_nav_buttons()
                return

            if result == "apply":
                self.w.apply_page(current_key)
            elif result == "discard":
                self.discard_page_changes(current_key)

        self.w.stack.setCurrentIndex(page_index)
        self.sync_nav_buttons()
        self.update_window_title()

    def is_model_page_changed(self) -> bool:
        return False

    def is_style_page_changed(self) -> bool:
        current = self.build_style_snapshot()
        applied = self.applied_snapshots.get("style", {})
        return not self._snapshot_equals(current, applied)

    def is_info_page_changed(self) -> bool:
        current = self.build_info_snapshot()
        applied = self.applied_snapshots.get("info", {})
        return not self._snapshot_equals(current, applied)

    def close_event(self, event):
        dirty_pages = [k for k, v in self.w.page_dirty.items() if v and k != "model"]
        if not dirty_pages:
            event.accept()
            return

        page_name_map = {
            "model": "模型选择页",
            "style": "风格设计页",
            "info": "组合与模拟页",
        }
        dirty_names: list[str] = [page_name_map.get(k) or k for k in dirty_pages]

        msg = QMessageBox(self.w)
        msg.setWindowTitle("存在未应用修改")
        msg.setText("以下页面有未应用的修改：\n\n" + "\n".join(dirty_names) + "\n\n确定直接关闭吗？")
        close_btn = msg.addButton("直接关闭", QMessageBox.ButtonRole.AcceptRole)
        msg.addButton("取消", QMessageBox.ButtonRole.RejectRole)
        msg.exec()

        if msg.clickedButton() == close_btn:
            event.accept()
        else:
            event.ignore()
