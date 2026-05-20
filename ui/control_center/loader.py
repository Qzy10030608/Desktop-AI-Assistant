from pathlib import Path
import json
from PySide6.QtCore import Qt

class ControlCenterLoader:
    """
    控制中心加载与刷新层

    作用：
    1. 加载第一页、第二页、第三页的下拉框与当前状态
    2. 刷新第一页运行总览
    3. 刷新第三页右侧简略信息栏
    4. 读取工作区草稿与已保存方案
    5. 加载连接配置页与桌面连接页
    """

    def __init__(self, window):
        self.w = window
        self.desktop_page_loaded = False

    # =========================================================
    # 总加载入口
    # =========================================================
    def load_current_state(self):
        self.w._loading = True
        try:
            self.reload_role_list()
            self.reload_model_list()
            self.reload_voice_list()
            self.reload_style_list()
            self.refresh_top_bar()
            self.refresh_info_page()
            self.reload_scheme_list()
            self.reload_saved_combo_list()
            self.load_workspace_draft()
            self.load_connection_page()

            if hasattr(self.w, "output_mode_combo") and self.w.output_mode_combo is not None:
                self.w.output_mode_combo.blockSignals(True)
                idx = self.w.output_mode_combo.findData(self.w.current_output_mode)
                if idx >= 0:
                    self.w.output_mode_combo.setCurrentIndex(idx)
                self.w.output_mode_combo.blockSignals(False)

            if hasattr(self.w, "logic") and self.w.logic is not None:
                self.w.logic.update_model_page_mode_visibility()

            self.w.apply_page_button_group("model")
            self.w.apply_page_button_group("style")
            self.w.apply_page_button_group("info")
            self.w.apply_page_button_group("connection")
            self.w.apply_page_button_group("desktop")
        finally:
            self.w._loading = False

    # =========================================================
    # 角色列表（兼容旧控件）
    # =========================================================
    def reload_role_list(self):
        roles = self.w.role_service.list_role_dirs()
        current_role_id = self.w.role_service.get_current_role_id()

        target_combos = []
        for combo_name in [
            "role_model_combo",
            "combo_role_combo",
        ]:
            combo = getattr(self.w, combo_name, None)
            if combo is not None:
                target_combos.append(combo)

        for combo in target_combos:
            combo.blockSignals(True)
            combo.clear()

            current_index = 0
            for idx, item in enumerate(roles):
                combo.addItem(item.get("name", item.get("id", "-")), item.get("id", ""))
                if item.get("id") == current_role_id:
                    current_index = idx

            if combo.count() > 0:
                combo.setCurrentIndex(current_index)

            combo.blockSignals(False)

    # =========================================================
    # 第1页：语言模型列表
    # =========================================================
    def reload_model_list(self):
        if not hasattr(self.w, "chat_model_combo") or self.w.chat_model_combo is None:
            return

        self.w.chat_model_combo.blockSignals(True)
        self.w.chat_model_combo.clear()

        models = self.w.model_service.list_available_models()
        current_model = self.w.model_service.get_current_model()
        current_model_id = current_model.get("id", "")
        current_tts_backend = self.w.voice_service.get_current_tts_backend()

        current_index = 0

        if not models:
            self.w.chat_model_combo.addItem("暂无可用模型，请先到连接配置页刷新。", "")
        else:
            for idx, item in enumerate(models):
                provider = str(item.get("provider", "ollama")).strip().lower()
                provider_name = {
                    "ollama": "Ollama",
                    "local": "Local",
                    "api": "API",
                }.get(provider, provider or "Unknown")

                text = f"{provider_name} / {item.get('model_name', item.get('name', '-'))}"
                self.w.chat_model_combo.addItem(text, item.get("id", ""))

                if item.get("id") == current_model_id:
                    current_index = idx

            self.w.chat_model_combo.setCurrentIndex(current_index)

        if hasattr(self.w, "tts_model_combo") and self.w.tts_model_combo is not None:
            self.w.tts_model_combo.blockSignals(True)
            idx = self.w.tts_model_combo.findData(current_tts_backend)
            if idx >= 0:
                self.w.tts_model_combo.setCurrentIndex(idx)
            self.w.tts_model_combo.blockSignals(False)

        self.w.chat_model_combo.blockSignals(False)

    # =========================================================
    # 统一入口：第2页 / 第3页语音相关列表
    # =========================================================
    def reload_voice_list(self):
        self.reload_voice_profile_list()
        self.reload_tts_package_list()

    # =========================================================
    # 第2页 / 第3页：表现模板列表
    # =========================================================
    def reload_voice_profile_list(self):
        voices = self.w.voice_service.list_voice_profiles()
        current_voice_id = self.w.voice_service.get_current_voice_id()

        target_combos = []
        for combo_name in [
            "current_voice_config_combo",
            "combo_voice_config_combo",
        ]:
            combo = getattr(self.w, combo_name, None)
            if combo is not None:
                target_combos.append(combo)

        for combo in target_combos:
            combo.blockSignals(True)
            combo.clear()

            current_index = 0
            for idx, item in enumerate(voices):
                combo.addItem(item.get("name", item.get("id", "-")), item)
                if item.get("id") == current_voice_id:
                    current_index = idx

            if combo.count() > 0:
                combo.setCurrentIndex(current_index)

            combo.blockSignals(False)

        if hasattr(self.w, "fill_voice_editor_from_current_profile"):
            self.w.fill_voice_editor_from_current_profile()

    # =========================================================
    # 第2页 / 第3页：语音包列表
    # =========================================================
    def reload_tts_package_list(self, backend: str | None = None):
        if backend is None:
            if hasattr(self.w, "tts_model_combo") and self.w.tts_model_combo is not None:
                backend = self.w.tts_model_combo.currentData()
            if not backend:
                backend = self.w.voice_service.get_current_tts_backend()

        backend = str(backend or "gpt_sovits").strip().lower()

        packages = self.w.tts_package_service.list_packages(backend)
        current_package_id = self.w.tts_package_service.get_current_package_id(backend)
        if not current_package_id and packages:
            current_package_id = packages[0].get("id", "")

        combo = getattr(self.w, "combo_voice_combo", None)
        if combo is None:
            return

        combo.blockSignals(True)
        combo.clear()

        current_index = 0
        for idx, item in enumerate(packages):
            combo.addItem(item.get("name", item.get("id", "-")), item)

            item_id = str(item.get("id", "")).strip()
            item_name = str(item.get("name", "")).strip()
            item_dir_name = str(item.get("dir_name", "")).strip()
            item_path_name = Path(str(item.get("path", "")).strip()).name if item.get("path") else ""

            if current_package_id in (item_id, item_name, item_dir_name, item_path_name):
                current_index = idx

        if combo.count() > 0:
            combo.setCurrentIndex(current_index)

        combo.blockSignals(False)

    # =========================================================
    # 第2页 / 第3页：文本模板列表
    # =========================================================
    def reload_style_list(self):
        styles = self.w.style_service.list_styles()
        current_style_id = self.w.style_service.get_current_style_id()

        target_combos = []
        for combo_name in [
            "current_style_config_combo",
            "combo_role_config_combo",
        ]:
            combo = getattr(self.w, combo_name, None)
            if combo is not None:
                target_combos.append(combo)

        for combo in target_combos:
            combo.blockSignals(True)
            combo.clear()

            current_index = 0
            for idx, item in enumerate(styles):
                combo.addItem(item.get("name", item.get("id", "-")), item)
                if item.get("id") == current_style_id:
                    current_index = idx

            if combo.count() > 0:
                combo.setCurrentIndex(current_index)

            combo.blockSignals(False)

        if hasattr(self.w, "fill_style_editor_from_current_profile"):
            self.w.fill_style_editor_from_current_profile()

    # =========================================================
    # 第1页：运行总览刷新
    # =========================================================
    def refresh_top_bar(self):
        role_meta = self.w.role_service.get_current_role_meta() or {}
        current_model = self.w.model_service.get_current_model() or {}
        current_style = self.w.style_service.get_current_style_profile() or {}
        current_voice_profile = self.w.voice_service.get_current_voice_profile() or {}

        tts_backend = self.w.voice_service.get_current_tts_backend()
        tts_backend_name = {
            "edge": "Edge-TTS",
            "gpt_sovits": "GPT-SoVITS",
        }.get(tts_backend, tts_backend or "-")

        current_package = self.w.tts_package_service.get_current_package(tts_backend) or {}
        current_package_name = current_package.get("name", current_package.get("id", "-"))

        output_mode_map = {
            "text_only": "仅文字",
            "text_voice": "文字+语音",
            "voice_only": "仅语音",
        }
        output_mode_name = output_mode_map.get(self.w.current_output_mode, "文字+语音")

        identity = self._read_json_file(Path(self.w.WORKSPACE_DRAFT_IDENTITY_FILE))
        active_scheme_name = str(identity.get("name", "")).strip() or "-"

        if getattr(self.w, "summary_role_label", None) is not None:
            self.w.summary_role_label.setText(f"组合方案：{active_scheme_name}")

        if getattr(self.w, "summary_voice_label", None) is not None:
            self.w.summary_voice_label.setText(f"语音包：{current_package_name}")

        if getattr(self.w, "summary_role_config_label", None) is not None:
            self.w.summary_role_config_label.setText(
                f"文本模板：{current_style.get('name', current_style.get('id', '-'))}"
            )

        if getattr(self.w, "summary_voice_config_label", None) is not None:
            self.w.summary_voice_config_label.setText(
                f"表现模板：{current_voice_profile.get('name', current_voice_profile.get('id', '-'))}"
            )

        if getattr(self.w, "summary_output_mode_label", None) is not None:
            self.w.summary_output_mode_label.setText(f"输出模式：{output_mode_name}")

        if getattr(self.w, "summary_model_label", None) is not None:
            self.w.summary_model_label.setText(
                f"语言模型：{current_model.get('name', current_model.get('model_name', '-'))}"
            )

        if getattr(self.w, "summary_tts_model_label", None) is not None:
            self.w.summary_tts_model_label.setText(f"语音后端：{tts_backend_name}")

        runtime_state = {}
        try:
            runtime_state = self.w.desktop_controller.service.mode_store.get_runtime_state()
        except Exception:
            runtime_state = {}
        desktop_mode = str(runtime_state.get("desktop_mode", runtime_state.get("current_mode", "disabled")) or "disabled")
        desktop_mode_name = {
            "disabled": "不启用",
            "restricted": "限制模式",
            "trusted": "信任模式",
            "test": "测试模式",
        }.get(desktop_mode, "不启用")
        if getattr(self.w, "summary_desktop_mode_label", None) is not None:
            self.w.summary_desktop_mode_label.setText(f"桌面模式：{desktop_mode_name}")

        developer_enabled = False
        try:
            developer_enabled = bool(getattr(self.w, "developer_mode_enabled_at_startup", False))
        except Exception:
            developer_enabled = False
        developer_label = getattr(self.w, "summary_developer_mode_label", None)
        backend_label = getattr(self.w, "summary_execution_backend_label", None)
        if developer_label is not None:
            developer_label.setVisible(developer_enabled)
            developer_label.setText("开发者模式：开启")
        if backend_label is not None:
            backend = str(runtime_state.get("execution_backend", "none") or "none").strip().lower()
            backend_name = {
                "host": "Host",
                "vm": "VM",
                "sandbox": "Sandbox",
                "none": "None",
                "": "None",
            }.get(backend, backend or "None")
            backend_label.setVisible(developer_enabled)
            backend_label.setText(f"执行出口：{backend_name}")

        self.w.current_state_changed.emit({
            "role": role_meta.get("name", "-"),
            "model": current_model.get("name", current_model.get("model_name", "-")),
            "style": current_style.get("name", current_style.get("id", "-")),
            "performance": current_voice_profile.get("name", current_voice_profile.get("id", "-")),
            "voice": current_package_name,
            "voice_model": tts_backend_name,
            "tts_backend": tts_backend,
            "output_mode": self.w.current_output_mode,
        })

    # =========================================================
    # 第3页：当前方案下拉刷新
    # =========================================================
    def refresh_info_page(self):
        combo = getattr(self.w, "combo_scheme_name_combo", None)
        if combo is None:
            return

        identity = self._read_json_file(Path(self.w.WORKSPACE_DRAFT_IDENTITY_FILE))
        current_scheme_name = str(identity.get("name", "")).strip()

        combo.blockSignals(True)
        combo.clear()

        current_index = 0
        for idx, path in enumerate(sorted(self.w.combo_presets_dir.glob("*.json"))):
            data = self._read_json_file(path)
            scheme_name = str(data.get("name", path.stem)).strip() or path.stem

            combo_data = {
                "name": scheme_name,
                "persona": data.get("persona", ""),
                "role_id": data.get("role_id", ""),
                "style_id": data.get("style_id", ""),
                "voice_id": data.get("voice_id", ""),
                "package_id": data.get("package_id", ""),
                "model_id": data.get("model_id", ""),
                "output_mode": data.get("output_mode", self.w.current_output_mode),
                "preset_path": str(path),
            }

            combo.addItem(scheme_name, combo_data)

            if current_scheme_name and scheme_name == current_scheme_name:
                current_index = idx

        if combo.count() > 0:
            combo.setCurrentIndex(current_index)

        combo.blockSignals(False)

    # =========================================================
    # 第1页：当前运行方案摘要
    # =========================================================
    def reload_scheme_list(self):
        combo = getattr(self.w, "combo_scheme_combo", None)
        if combo is None:
            return

        combo.blockSignals(True)
        combo.clear()

        identity = self._read_json_file(Path(self.w.WORKSPACE_DRAFT_IDENTITY_FILE))
        active_scheme_name = str(identity.get("name", "")).strip()

        current_index = 0
        loaded_any = False

        for idx, path in enumerate(sorted(self.w.combo_presets_dir.glob("*.json"))):
            data = self._read_json_file(path)
            scheme_name = str(data.get("name", path.stem)).strip() or path.stem

            combo_data = {
                "name": scheme_name,
                "persona": data.get("persona", ""),
                "role_id": data.get("role_id", ""),
                "style_id": data.get("style_id", ""),
                "voice_id": data.get("voice_id", ""),
                "package_id": data.get("package_id", ""),
                "model_id": data.get("model_id", ""),
                "output_mode": data.get("output_mode", self.w.current_output_mode),
                "preset_path": str(path),
            }

            combo.addItem(scheme_name, combo_data)
            loaded_any = True

            if active_scheme_name and scheme_name == active_scheme_name:
                current_index = idx

        if loaded_any and combo.count() > 0:
            combo.setCurrentIndex(current_index)

        combo.blockSignals(False)

        active_scheme_name = str(identity.get("name", "")).strip() or "-"
        current_style = self.w.style_service.get_current_style_profile() or {}
        current_voice_profile = self.w.voice_service.get_current_voice_profile() or {}
        tts_backend = (self.w.voice_service.get_current_tts_backend() or "").strip().lower()
        current_package = self.w.tts_package_service.get_current_package(tts_backend) or {}

        if tts_backend == "gpt_sovits":
            tts_backend_name = "GPT-SoVITS"
        elif tts_backend == "edge":
            tts_backend_name = "Edge-TTS"
        else:
            tts_backend_name = tts_backend or "-"

        style_name = current_style.get("name", current_style.get("id", "-"))
        voice_name = current_voice_profile.get("name", current_voice_profile.get("id", "-"))
        package_name = current_package.get("name", current_package.get("id", "-"))

        if getattr(self.w, "current_scheme_display", None) is not None:
            self.w.current_scheme_display.setPlainText(
                f"组合名称：{active_scheme_name}\n"
                f"语音模型：{tts_backend_name}\n"
                f"文本模板：{style_name}\n"
                f"表现模板：{voice_name}\n"
                f"语音包：{package_name}"
            )

    # =========================================================
    # 第3页：已保存方案列表
    # =========================================================
    def reload_saved_combo_list(self):
        widget = getattr(self.w, "saved_combo_combo", None)
        if widget is None:
            return

        widget.blockSignals(True)
        widget.clear()

        from PySide6.QtWidgets import QListWidgetItem

        for path in sorted(self.w.combo_presets_dir.glob("*.json")):
            data = self._read_json_file(path)
            combo_name = str(data.get("name", path.stem)).strip() or path.stem

            item = QListWidgetItem(combo_name)
            item.setData(Qt.ItemDataRole.UserRole, str(path))
            widget.addItem(item)

        widget.blockSignals(False)

        if widget.count() > 0 and widget.currentRow() < 0:
            widget.setCurrentRow(0)

    # =========================================================
    # 第3页：读取工作区草稿
    # =========================================================
    def load_workspace_draft(self):
        identity = self._read_json_file(Path(self.w.WORKSPACE_DRAFT_IDENTITY_FILE))
        style_sel = self._read_json_file(Path(self.w.WORKSPACE_STYLE_SELECTION_FILE))
        voice_sel = self._read_json_file(Path(self.w.WORKSPACE_VOICE_SELECTION_FILE))

        if getattr(self.w, "combo_name_edit", None) is not None:
            self.w.combo_name_edit.blockSignals(True)
            self.w.combo_name_edit.setText(identity.get("name", ""))
            self.w.combo_name_edit.blockSignals(False)

        if getattr(self.w, "combo_persona_edit", None) is not None:
            try:
                persona_text = Path(self.w.WORKSPACE_PERSONA_DRAFT_FILE).read_text(encoding="utf-8")
            except Exception:
                persona_text = ""
            self.w.combo_persona_edit.blockSignals(True)
            self.w.combo_persona_edit.setPlainText(persona_text)
            self.w.combo_persona_edit.blockSignals(False)

        style_id = style_sel.get("id", "")
        voice_id = voice_sel.get("id", "")
        package_id = identity.get("package_id", "")

        combo_style = getattr(self.w, "combo_role_config_combo", None)
        if combo_style is not None and style_id:
            for i in range(combo_style.count()):
                data = combo_style.itemData(i)
                if isinstance(data, dict) and data.get("id") == style_id:
                    combo_style.blockSignals(True)
                    combo_style.setCurrentIndex(i)
                    combo_style.blockSignals(False)
                    break

        combo_voice = getattr(self.w, "combo_voice_config_combo", None)
        if combo_voice is not None and voice_id:
            for i in range(combo_voice.count()):
                data = combo_voice.itemData(i)
                if isinstance(data, dict) and data.get("id") == voice_id:
                    combo_voice.blockSignals(True)
                    combo_voice.setCurrentIndex(i)
                    combo_voice.blockSignals(False)
                    break

        combo_package = getattr(self.w, "combo_voice_combo", None)
        if combo_package is not None and package_id:
            for i in range(combo_package.count()):
                data = combo_package.itemData(i)
                if not isinstance(data, dict):
                    continue

                item_id = str(data.get("id", "")).strip()
                item_name = str(data.get("name", "")).strip()
                item_dir_name = str(data.get("dir_name", "")).strip()
                item_path_name = Path(str(data.get("path", "")).strip()).name if data.get("path") else ""

                if package_id in (item_id, item_name, item_dir_name, item_path_name):
                    combo_package.blockSignals(True)
                    combo_package.setCurrentIndex(i)
                    combo_package.blockSignals(False)
                    break

        combo_scheme = getattr(self.w, "combo_scheme_name_combo", None)
        if combo_scheme is not None:
            combo_scheme.blockSignals(True)
            combo_scheme.clear()

            for path in sorted(self.w.combo_presets_dir.glob("*.json")):
                data = self._read_json_file(path)
                scheme_name = str(data.get("name", path.stem)).strip() or path.stem

                combo_data = {
                    "name": scheme_name,
                    "persona": data.get("persona", ""),
                    "role_id": data.get("role_id", ""),
                    "style_id": data.get("style_id", ""),
                    "voice_id": data.get("voice_id", ""),
                    "package_id": data.get("package_id", ""),
                    "model_id": data.get("model_id", ""),
                    "output_mode": data.get("output_mode", self.w.current_output_mode),
                    "preset_path": str(path),
                }
                combo_scheme.addItem(scheme_name, combo_data)

            combo_scheme.blockSignals(False)

    # =========================================================
    # 工具函数
    # =========================================================
    def _read_json_file(self, path: Path) -> dict:
        if not path.exists():
            return {}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _pretty_json_text(self, data: dict) -> str:
        if not isinstance(data, dict) or not data:
            return ""
        try:
            return json.dumps(data, ensure_ascii=False, indent=2)
        except Exception:
            return ""

    # =========================================================
    # 桌面连接页
    # =========================================================
    def load_desktop_page(self, *, light: bool = False):
        desktop_loader = getattr(self.w, "desktop_page_loader", None)
        if desktop_loader is not None:
            if light and hasattr(desktop_loader, "load_page_light"):
                desktop_loader.load_page_light()
            else:
                desktop_loader.load_page()
            self.desktop_page_loaded = True

    def load_desktop_page_on_demand(self, *, force: bool = False):
        """
        桌面连接页按需加载。
        控制中心打开时不加载桌面页；用户首次进入桌面连接页时再加载。
        force=True 用于用户明确刷新或已有页面需要强制重载。
        """
        if self.desktop_page_loaded and not force:
            return
        self.load_desktop_page(light=not force)

    # =========================================================
    # 连接配置页
    # =========================================================
    def load_connection_page(self):
        machine_profile = self.w.machine_profile_service.get_profile()
        ollama_cfg = self.w.machine_profile_service.get_ollama_config()
        gpt_cfg = self.w.machine_profile_service.get_gpt_sovits_config()

        preferred_provider = str(
            (machine_profile.get("llm", {}) or {}).get("preferred_provider", "ollama")
        ).strip().lower() or "ollama"

        current_tts_backend = str(self.w.voice_service.get_current_tts_backend() or "edge").strip().lower()
        if getattr(self.w, "llm_provider_combo", None) is not None:
            self.w.llm_provider_combo.blockSignals(True)
            idx = self.w.llm_provider_combo.findData(preferred_provider)
            if idx >= 0:
                self.w.llm_provider_combo.setCurrentIndex(idx)
            self.w.llm_provider_combo.blockSignals(False)
        # -------------------------
        # Ollama 状态
        # -------------------------
        ollama_ok = bool(ollama_cfg.get("last_health_ok", False))
        ollama_error = str(ollama_cfg.get("last_error", "")).strip()

        if getattr(self.w, "ollama_status_label", None) is not None:
            if ollama_ok:
                self.w.ollama_status_label.setText("Ollama 状态：已连接")
            else:
                self.w.ollama_status_label.setText(
                    f"Ollama 状态：未连接{' | ' + ollama_error if ollama_error else ''}"
                )

        # -------------------------
        # 模型下拉
        # -------------------------
        current_model_id = self.w.model_service.get_current_model_id()
        combo_models = self.w.model_service.list_connection_candidate_models(provider="ollama")

        if getattr(self.w, "connection_model_combo", None) is not None:
            self.w.connection_model_combo.blockSignals(True)
            self.w.connection_model_combo.clear()

            current_index = 0

            for idx, item in enumerate(combo_models):
                model_id = item.get("id", "")
                model_name = item.get("model_name", item.get("name", "-"))
                available = bool(item.get("available", False))

                text = model_name
                if not available:
                    text += " [未确认可用]"

                self.w.connection_model_combo.addItem(text, model_id)

                if model_id == current_model_id:
                    current_index = idx

            if self.w.connection_model_combo.count() > 0:
                found_current = False
                for idx in range(self.w.connection_model_combo.count()):
                    if self.w.connection_model_combo.itemData(idx) == current_model_id:
                        current_index = idx
                        found_current = True
                        break

                if not found_current:
                    current_index = 0

                self.w.connection_model_combo.setCurrentIndex(current_index)

            self.w.connection_model_combo.blockSignals(False)

        # -------------------------
        # GPT-SoVITS 配置
        # -------------------------
        if getattr(self.w, "gpt_sovits_root_edit", None) is not None:
            self.w.gpt_sovits_root_edit.setText(gpt_cfg.get("root_dir", ""))

        if getattr(self.w, "gpt_sovits_python_edit", None) is not None:
            self.w.gpt_sovits_python_edit.setText(gpt_cfg.get("python_exe", ""))

        if getattr(self.w, "gpt_sovits_host_edit", None) is not None:
            self.w.gpt_sovits_host_edit.setText(gpt_cfg.get("host", "127.0.0.1"))

        if getattr(self.w, "gpt_sovits_port_edit", None) is not None:
            self.w.gpt_sovits_port_edit.setText(str(gpt_cfg.get("port", 9880)))

        if getattr(self.w, "gpt_sovits_api_script_edit", None) is not None:
            self.w.gpt_sovits_api_script_edit.setText(gpt_cfg.get("api_script", "api_v2.py"))

        if getattr(self.w, "gpt_sovits_tts_config_edit", None) is not None:
            self.w.gpt_sovits_tts_config_edit.setText(
                gpt_cfg.get("tts_config", "GPT_SoVITS/configs/tts_infer.yaml")
            )

        gpt_ok = bool(gpt_cfg.get("last_health_ok", False))
        gpt_error = str(gpt_cfg.get("last_error", "")).strip()

        if getattr(self.w, "gpt_sovits_status_label", None) is not None:
            if gpt_ok:
                self.w.gpt_sovits_status_label.setText("GPT-SoVITS 状态：最近一次检查通过")
            else:
                self.w.gpt_sovits_status_label.setText(
                    f"GPT-SoVITS 状态：未通过{f' | {gpt_error}' if gpt_error else ''}"
                )

        # -------------------------
        # GPT-SoVITS 配置区显隐
        # -------------------------
        config_frame = getattr(self.w, "gpt_sovits_config_frame", None)
        if config_frame is not None:
            config_frame.setVisible(current_tts_backend == "gpt_sovits")
        tts_backend_name = {
            "edge": "Edge-TTS",
            "gpt_sovits": "GPT-SoVITS",
        }.get(current_tts_backend, current_tts_backend or "-")

        if getattr(self.w, "current_tts_backend_label", None) is not None:
            self.w.current_tts_backend_label.setText(f"当前运行语音引擎：{tts_backend_name}")

        if getattr(self.w, "tts_connection_hint_label", None) is not None:
            if current_tts_backend == "gpt_sovits":
                self.w.tts_connection_hint_label.setText("当前正在配置 GPT-SoVITS 本地连接参数。")
            else:
                self.w.tts_connection_hint_label.setText("当前语音引擎无需额外本地连接配置。")
        # -------------------------
        # LLM Provider 可见性
        # -------------------------
        if hasattr(self.w, "update_connection_page_provider_visibility"):
            self.w.update_connection_page_provider_visibility()
        if hasattr(self.w, "refresh_developer_mode_section"):
            self.w.refresh_developer_mode_section()

    # =========================================================
    # 连接页：模型回复策略区
    # =========================================================
    def load_connection_policy_section(self, model: dict | None = None):
        model = model or self.w.model_service.get_current_model() or {}

        family = str(model.get("family", "unknown")).strip() or "unknown"
        size_tier = str(model.get("size_tier", "medium")).strip() or "medium"
        policy_profile = model.get("policy_profile", {}) or {}
        policy_name = str(policy_profile.get("policy_name", "-")).strip() or "-"

        family_override = str(model.get("family_override", "")).strip()
        size_tier_override = str(model.get("size_tier_override", "")).strip()
        policy_override = model.get("policy_override", {}) or {}
        template_override = str(policy_override.get("template", "")).strip()

        policy_patch = dict(policy_override)
        policy_patch.pop("template", None)

        if getattr(self.w, "policy_detected_family_label", None) is not None:
            self.w.policy_detected_family_label.setText(f"自动识别 Family：{family}")

        if getattr(self.w, "policy_detected_size_tier_label", None) is not None:
            self.w.policy_detected_size_tier_label.setText(f"自动识别 Size Tier：{size_tier}")

        if getattr(self.w, "policy_detected_template_label", None) is not None:
            self.w.policy_detected_template_label.setText(f"自动识别策略模板：{policy_name}")

        combo = getattr(self.w, "policy_family_override_combo", None)
        if combo is not None:
            combo.blockSignals(True)
            idx = combo.findData(family_override)
            combo.setCurrentIndex(idx if idx >= 0 else 0)
            combo.blockSignals(False)

        combo = getattr(self.w, "policy_size_tier_override_combo", None)
        if combo is not None:
            combo.blockSignals(True)
            idx = combo.findData(size_tier_override)
            combo.setCurrentIndex(idx if idx >= 0 else 0)
            combo.blockSignals(False)

        combo = getattr(self.w, "policy_template_override_combo", None)
        if combo is not None:
            combo.blockSignals(True)
            idx = combo.findData(template_override)
            combo.setCurrentIndex(idx if idx >= 0 else 0)
            combo.blockSignals(False)

        edit = getattr(self.w, "policy_override_json_edit", None)
        if edit is not None:
            edit.blockSignals(True)
            edit.setPlainText(self._pretty_json_text(policy_patch))
            edit.blockSignals(False)

        if hasattr(self.w, "cc_actions") and self.w.cc_actions is not None:
            self.w.cc_actions.refresh_connection_policy_preview(model=model)
