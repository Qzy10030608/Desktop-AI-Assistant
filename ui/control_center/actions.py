from pathlib import Path
import json

import numpy as np
import sounddevice as sd
from PySide6.QtCore import QObject, QThread, Signal, QUrl, Qt, QTimer
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QApplication, QMessageBox, QInputDialog
import requests

from config import (  # type: ignore
    DEFAULT_OUTPUT_MODE,
    STYLES_DIR,
    VOICES_DIR,
    WORKSPACE_DRAFT_IDENTITY_FILE,
    WORKSPACE_STYLE_SELECTION_FILE,
    WORKSPACE_VOICE_SELECTION_FILE,
    WORKSPACE_PERSONA_DRAFT_FILE,
    WORKSPACE_PREVIEW_TEXT_FILE,
    RECORD_DTYPE,
    SAMPLE_RATE,
    CHANNELS,
    TTS_OUTPUT_EXTENSION,
)
from ui.control_center.config import UI_COLOR  # type: ignore
from services.tts.tts_service import TTSRequest, generate_tts  # type: ignore
from services.runtime.audio.input_device_service import InputDeviceService  # type: ignore
from services.runtime.chat_display_config_service import ChatDisplayConfigService  # type: ignore

class _TTSBackendLoadWorker(QObject):
    finished = Signal(dict)
    error = Signal(str)

    def __init__(self, controller, backend: str):
        super().__init__()
        self.controller = controller
        self.backend = backend

    def run(self):
        try:
            status = self.controller.ensure_backend_ready(self.backend)
            self.finished.emit(status)
        except Exception as e:
            self.error.emit(str(e))


class _TTSBackendPreloadWorker(QObject):
    finished = Signal(dict)
    error = Signal(str)
    progress = Signal(str, int)

    def __init__(self, controller, voice_profile_service, tts_package_service):
        super().__init__()
        self.controller = controller
        self.voice_profile_service = voice_profile_service
        self.tts_package_service = tts_package_service

    def run(self):
        try:
            result = self.controller.prepare_current_runtime(
                voice_profile_service=self.voice_profile_service,
                tts_package_service=self.tts_package_service,
                progress_cb=lambda text, percent: self.progress.emit(text, percent),
            )
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class _OllamaPullWorker(QObject):
    finished = Signal(dict)
    error = Signal(str)

    def __init__(self, host: str, model_name: str):
        super().__init__()
        self.host = (host or "http://localhost:11434").rstrip("/")
        self.model_name = (model_name or "").strip()

    def run(self):
        if not self.model_name:
            self.error.emit("模型名称为空。")
            return

        url = f"{self.host}/api/pull"

        try:
            resp = requests.post(
                url,
                json={
                    "name": self.model_name,
                    "stream": False,
                },
                timeout=(10, 1800),
            )
            resp.raise_for_status()
            data = resp.json() if resp.content else {}
            self.finished.emit({
                "ok": True,
                "model_name": self.model_name,
                "data": data,
            })
        except Exception as e:
            self.error.emit(str(e))


class ControlCenterActions:
    def __init__(self, window):
        self.w = window
        self._tts_load_thread = None
        self._tts_load_worker = None
        self._ollama_pull_thread = None
        self._ollama_pull_worker = None
        self._combo_preview_duration = 0
        self._tts_apply_busy = False
        self._tts_apply_token = 0
        self._tts_preload_thread = None
        self._tts_preload_worker = None
        self.audio_device_service = InputDeviceService()
        self.chat_display_config_service = getattr(
            self.w,
            "chat_display_config_service",
            ChatDisplayConfigService(),
        )
        self._loading_audio_device_combos = False
        self._mic_test_stream = None
        self._mic_test_timer = None
        self._mic_test_peak = 0.0
        self._mic_test_rms = 0.0
        self._mic_test_active = False
        self._mic_test_device_name = ""
        self._mic_test_used_fallback = False
    # =========================================================
    # 页面应用
    # =========================================================
    def apply_page(self, page_key: str):
        if page_key == "model":
            self.apply_model_page()
        elif page_key == "style":
            self.apply_style_page()
        elif page_key == "info":
            self.apply_info_page()

    def _persist_selected_tts_backend_lightweight(self):
        """
        仅保存当前选择的语音后端到当前表现模板，不做探活和预加载。
        """
        backend = self._get_selected_tts_backend()
        current_voice_id = self.w.voice_service.get_current_voice_id()
        current_voice_profile = self.w.voice_service.get_current_voice_profile() or {}

        if not current_voice_id:
            return

        voice_save_data = {
            "name": current_voice_profile.get("name", current_voice_id),
            "backend": backend,
            "voice": ((current_voice_profile.get("tts_config", {}) or {}).get("voice") or "zh-CN-XiaoxiaoNeural"),
            "scene": current_voice_profile.get("scene", "daily"),
            "emotion": current_voice_profile.get("emotion", "gentle"),
            "emotion_strength": current_voice_profile.get("emotion_strength", "medium"),
            "speed": current_voice_profile.get("speed", "normal"),
            "pause": current_voice_profile.get("pause", "medium"),
            "intonation": current_voice_profile.get("intonation", "normal"),
            "emphasis": current_voice_profile.get("emphasis", "natural"),
        }

        self.w.voice_service.save_voice_profile(current_voice_id, voice_save_data)
        self.w.voice_service.set_current_voice(current_voice_id)

    def apply_model_page(self):
        model_id = self.w.chat_model_combo.currentData() if self.w.chat_model_combo else None
        if model_id:
            self.w.model_service.set_current_model(model_id)

        output_mode = self.w.output_mode_combo.currentData() if self.w.output_mode_combo else None
        if output_mode:
            self.w.current_output_mode = output_mode

        scheme_data = self.w.combo_scheme_combo.currentData() if self.w.combo_scheme_combo else None
        if isinstance(scheme_data, dict):
            scheme_role_id = scheme_data.get("role_id")
            scheme_voice_id = scheme_data.get("voice_id") or scheme_data.get("voice_profile_id")
            scheme_style_id = scheme_data.get("style_id")
            scheme_package_id = scheme_data.get("package_id")

            if scheme_role_id:
                self.w.role_service.set_current_role(scheme_role_id)
            if scheme_voice_id:
                self.w.voice_service.set_current_voice(scheme_voice_id)
            if scheme_style_id:
                self.w.style_service.set_current_style(scheme_style_id)

            backend = self._get_selected_tts_backend()
            if backend and scheme_package_id:
                ok, err, _runtime_cfg = self._validate_tts_package_before_apply(backend, scheme_package_id)
                if not ok:
                    QMessageBox.warning(self.w, "语音包无效", f"当前方案中的语音包无法应用：\n{err}")
                    return
                self.w.tts_package_service.set_current_package(backend, scheme_package_id)

        backend = self._get_selected_tts_backend()
        if backend:
            self._sync_valid_tts_package_for_backend(backend)

        self._persist_selected_tts_backend_lightweight()
        self.w.loader.refresh_top_bar()
        self.w.loader.reload_scheme_list()
        self.w.refresh_info_page()

        # 第一页不参与脏状态
        self.w.settings_applied.emit()
        self._start_gpt_sovits_preload_after_apply()

    def save_model_page_default(self):
        self.apply_model_page()
        QMessageBox.information(self.w, "提示", "运行配置已保存为默认状态。")

    def apply_style_page(self):
        style_form = self.w.collect_style_form_data()
        voice_form = self.w.collect_voice_form_data()

        style_id = self.get_selected_style_id_for_save()
        voice_id = self.get_selected_voice_id_for_save()

        saved_style_id = self.w.style_service.save_style_profile(style_id, style_form)
        saved_voice_id = self.w.voice_service.save_voice_profile(voice_id, voice_form)

        self.w.style_service.set_current_style(saved_style_id)
        self.w.voice_service.set_current_voice(saved_voice_id)

        self.w.reload_style_list()
        self.w.reload_voice_list()
        self.w.fill_style_editor_from_current_profile()
        self.w.fill_voice_editor_from_current_profile()

        self.w.refresh_top_bar()
        self.w.refresh_info_page()
        self.w.reload_scheme_list()

        self.w.capture_snapshot("style")
        self.w.settings_applied.emit()

    def save_style_page(self):
        self.apply_style_page()
        QMessageBox.information(self.w, "提示", "当前文本模板和表现模板已保存并应用。")

    def reset_style_page(self):
        self.w.fill_style_editor_from_current_profile()
        self.w.fill_voice_editor_from_current_profile()
        self.w.logic.initialize_style_scene_defaults()
        self.w.capture_snapshot("style")

    def apply_info_page(self):
        data = self.w.collect_info_form_data()

        if not self._apply_scheme_data_to_runtime(data):
            return False

        self.w.reload_model_list()
        self.w.reload_role_list()
        self.w.reload_style_list()
        self.w.reload_voice_list()
        self.w.refresh_top_bar()
        self.w.refresh_info_page()
        self.w.reload_scheme_list()
        self.w.reload_saved_combo_list()

        self.w.capture_snapshot("info")
        self.w.settings_applied.emit()
        self._start_gpt_sovits_preload_after_apply()
        return True

    # =========================================================
    # 页面事件回调
    # =========================================================
    def on_role_changed_in_model_page(self):
        # 第一页不参与脏状态
        if self.w._loading:
            return
        self.w.reload_voice_list()
        self.w.reload_style_list()

    def on_voice_profile_selected(self):
        voice_data = self.w.current_voice_config_combo.currentData() if self.w.current_voice_config_combo else None
        if isinstance(voice_data, dict):
            voice_id = voice_data.get("id")
            if voice_id:
                self.w.voice_service.set_current_voice(voice_id)

        self.w.fill_voice_editor_from_current_profile()
        self.w.refresh_dirty("style")

    def on_style_profile_selected(self):
        style_data = self.w.current_style_config_combo.currentData() if self.w.current_style_config_combo else None
        if isinstance(style_data, dict):
            style_id = style_data.get("id")
            if style_id:
                self.w.style_service.set_current_style(style_id)

        self.w.fill_style_editor_from_current_profile()
        self.w.refresh_dirty("style")

    def _fill_info_page_from_combo_data(self, data: dict):
        if not data:
            return

        if self.w.combo_name_edit is not None:
            self.w.combo_name_edit.setText(data.get("name", ""))

        if self.w.combo_persona_edit is not None:
            self.w.combo_persona_edit.setPlainText(data.get("persona", ""))

        style_id = data.get("style_id", "")
        voice_id = data.get("voice_id", "")
        package_id = data.get("package_id", "")

        if style_id and self.w.combo_role_config_combo is not None:
            for i in range(self.w.combo_role_config_combo.count()):
                combo_data = self.w.combo_role_config_combo.itemData(i)
                if isinstance(combo_data, dict) and combo_data.get("id") == style_id:
                    self.w.combo_role_config_combo.setCurrentIndex(i)
                    break

        if voice_id and self.w.combo_voice_config_combo is not None:
            for i in range(self.w.combo_voice_config_combo.count()):
                combo_data = self.w.combo_voice_config_combo.itemData(i)
                if isinstance(combo_data, dict) and combo_data.get("id") == voice_id:
                    self.w.combo_voice_config_combo.setCurrentIndex(i)
                    break

        if package_id and self.w.combo_voice_combo is not None:
            for i in range(self.w.combo_voice_combo.count()):
                combo_data = self.w.combo_voice_combo.itemData(i)
                if not isinstance(combo_data, dict):
                    continue
                if (
                    combo_data.get("id") == package_id
                    or combo_data.get("dir_name") == package_id
                    or combo_data.get("name") == package_id
                ):
                    self.w.combo_voice_combo.setCurrentIndex(i)
                    break

        style_name = style_id or "-"
        for item_data in self.w.style_service.list_styles():
            if item_data.get("id") == style_id:
                style_name = item_data.get("name", style_id)
                break

        voice_name = voice_id or "-"
        for item_data in self.w.voice_service.list_voice_profiles():
            if item_data.get("id") == voice_id:
                voice_name = item_data.get("name", voice_id)
                break

        backend = self.w.voice_service.get_current_tts_backend()
        package_name = package_id or "-"
        for item_data in self.w.tts_package_service.list_packages(backend):
            if (
                item_data.get("id") == package_id
                or item_data.get("dir_name") == package_id
                or item_data.get("name") == package_id
            ):
                package_name = item_data.get("name", package_id)
                break

        scheme_name = data.get("name", "-")

        if self.w.combo_scheme_list is not None:
            self.w.combo_scheme_list.setPlainText(
                f"当前方案：{scheme_name}\n"
                f"文本模板：{style_name}\n"
                f"表现模板：{voice_name}\n"
                f"语音包：{package_name}"
            )

        if self.w.combo_voice_preview is not None:
            self.w.combo_voice_preview.setPlainText(
                f"测试选中方案：{scheme_name}\n\n"
                f"当前方案：{scheme_name}\n"
                f"文本模板：{style_name}\n"
                f"表现模板：{voice_name}\n"
                f"语音包：{package_name}\n"
                f"语言模型：{data.get('model_id', '-')}\n"
                f"输出模式：{data.get('output_mode', '-')}\n\n"
                f"人设说明：\n{data.get('persona', '-')}"
            )

        if self.w.combo_waiting_label is not None:
            self.w.combo_waiting_label.setText("预计等待：已选中方案并载入当前组合")

        self.w.refresh_dirty("info")

    def on_scheme_name_selected_in_info_page(self):
        combo = getattr(self.w, "combo_scheme_name_combo", None)
        if combo is None:
            return

        data = combo.currentData()
        if not isinstance(data, dict):
            return

        preset_path = data.get("preset_path", "")
        if preset_path:
            loaded = self._read_json_file(Path(preset_path))
            if loaded:
                self._fill_info_page_from_combo_data(loaded)
                return

        self._fill_info_page_from_combo_data(data)

    def on_saved_combo_selected(self):
        if self.w.saved_combo_combo is None:
            return

        item = self.w.saved_combo_combo.currentItem()
        if item is None:
            return

        file_path = item.data(Qt.ItemDataRole.UserRole)
        if not file_path:
            return

        data = self._read_json_file(Path(file_path))
        if not data:
            return

        self._fill_info_page_from_combo_data(data)

    def on_tts_model_changed(self):
        if self.w._loading:
            return

        backend = self.w.tts_model_combo.currentData() if self.w.tts_model_combo else None
        self.w.loader.reload_tts_package_list(backend)

        current_backend = (self.w.voice_service.get_current_tts_backend() or "").strip().lower()
        selected_backend = self._get_selected_tts_backend()

        if selected_backend != current_backend:
            self._mark_tts_backend_pending()
            self.hide_tts_loading_inline()
        else:
            self.refresh_tts_backend_status()

        # 第一页不参与脏状态

    def on_model_page_selection_changed(self):
        # 第一页不参与脏状态
        return

    def on_output_mode_changed_in_model_page(self):
        if self.w._loading:
            return
        self.w.logic.update_model_page_mode_visibility()
        # 第一页不参与脏状态

    def on_connection_page_changed(self):
        self.update_connection_page_provider_visibility()

    def _get_connection_provider(self) -> str:
        combo = getattr(self.w, "llm_provider_combo", None)
        if combo is None:
            return "ollama"
        return str(combo.currentData() or "ollama").strip().lower() or "ollama"

    def _get_connection_ollama_host(self) -> str:
        try:
            cfg = self.w.machine_profile_service.get_ollama_config()
            return str(cfg.get("host", "http://localhost:11434")).strip() or "http://localhost:11434"
        except Exception:
            return "http://localhost:11434"

    def _build_connection_gpt_config(self) -> dict:
        root_dir = self.w.gpt_sovits_root_edit.text().strip() if self.w.gpt_sovits_root_edit else ""
        python_exe = self.w.gpt_sovits_python_edit.text().strip() if self.w.gpt_sovits_python_edit else ""
        host = self.w.gpt_sovits_host_edit.text().strip() if self.w.gpt_sovits_host_edit else "127.0.0.1"
        port_text = self.w.gpt_sovits_port_edit.text().strip() if self.w.gpt_sovits_port_edit else "9880"
        api_script = self.w.gpt_sovits_api_script_edit.text().strip() if self.w.gpt_sovits_api_script_edit else "api_v2.py"
        tts_config = self.w.gpt_sovits_tts_config_edit.text().strip() if self.w.gpt_sovits_tts_config_edit else "GPT_SoVITS/configs/tts_infer.yaml"

        try:
            port = int(port_text or "9880")
        except Exception:
            port = 9880

        return {
            "root_dir": root_dir,
            "python_exe": python_exe,
            "host": host or "127.0.0.1",
            "port": port,
            "api_script": api_script or "api_v2.py",
            "tts_config": tts_config or "GPT_SoVITS/configs/tts_infer.yaml",
        }

    def test_ollama_connection(self):
        host = self._get_connection_ollama_host()
        result = self.w.llm_backend_controller.health_check(
            provider="ollama",
            model_config={"host": host},
        )

        label = getattr(self.w, "ollama_status_label", None)
        if label is not None:
            if result.get("ok"):
                label.setText(
                    f"Ollama 状态：已连接 | 已安装模型数={result.get('model_count', 0)}"
                )
            else:
                label.setText(
                    f"Ollama 状态：连接失败 | {result.get('error', '')}"
                )

    def refresh_ollama_model_runtime(self):
        host = self._get_connection_ollama_host()

        health = self.w.llm_backend_controller.health_check(
            provider="ollama",
            model_config={"host": host},
        )
        if not health.get("ok"):
            if self.w.ollama_status_label is not None:
                self.w.ollama_status_label.setText(
                    f"Ollama 状态：连接失败 | {health.get('error', '')}"
                )
            return

        runtime_models = self.w.llm_backend_controller.list_models(
            provider="ollama",
            model_config={"host": host},
        )

        synced_models = self.w.model_service.sync_runtime_models(
            provider="ollama",
            runtime_models=runtime_models,
        )

        available_models = [
            item for item in synced_models
            if bool(item.get("available", False))
        ]

        current_model = self.w.model_service.get_current_model()
        if not bool(current_model.get("available", False)):
            best = self.w.model_service.get_best_available_model(provider="ollama")
            if best:
                self.w.model_service.set_current_model(best.get("id", ""))

        if self.w.ollama_status_label is not None:
            if available_models:
                self.w.ollama_status_label.setText(
                    f"Ollama 状态：已连接 | 已发现 {len(available_models)} 个可用模型"
                )
            else:
                self.w.ollama_status_label.setText(
                    "Ollama 状态：已连接 | 当前没有真实可用模型"
                )

        self.w.loader.reload_model_list()
        self.w.loader.load_desktop_page()

    def on_ollama_download_model_selected(self):
        combo = getattr(self.w, "ollama_download_model_combo", None)
        if combo is None:
            return

        data = combo.currentData()
        model_name = str(data or "").strip()

        if not model_name:
            return

        if model_name == "__custom__":
            model_name, ok = QInputDialog.getText(
                self.w,
                "手动输入模型名",
                "请输入 Ollama 模型名，例如 qwen3:4b",
            )
            if not ok:
                combo.blockSignals(True)
                combo.setCurrentIndex(0)
                combo.blockSignals(False)
                return
            model_name = model_name.strip()

        if not model_name:
            combo.blockSignals(True)
            combo.setCurrentIndex(0)
            combo.blockSignals(False)
            return

        reply = QMessageBox.question(
            self.w,
            "确认下载",
            f"确定下载模型：{model_name} 吗？\n\n下载过程可能较久，请耐心等待。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        combo.blockSignals(True)
        combo.setCurrentIndex(0)
        combo.blockSignals(False)

        if reply != QMessageBox.StandardButton.Yes:
            return

        self.download_ollama_model(model_name)

    def _get_builtin_ollama_models(self) -> list[str]:
        return [
            "qwen3:4b",
            "qwen3:8b",
            "qwen3:30b",
            "qwen3-coder:30b",
            "qwen3-vl:4b",
            "qwen3-vl:8b",
            "qwen3-vl:30b",
            "deepseek-r1:8b",
        ]

    def update_connection_page_provider_visibility(self):
        provider = self._get_connection_provider()
        is_ollama = provider == "ollama"

        frame = getattr(self.w, "ollama_runtime_frame", None)
        if frame is not None:
            frame.setVisible(is_ollama)

    def download_ollama_model(self, model_name: str):
        if self._ollama_pull_thread is not None and self._ollama_pull_thread.isRunning():
            QMessageBox.information(self.w, "提示", "当前已有模型正在下载，请稍候。")
            return

        host = self._get_connection_ollama_host()
        model_name = (model_name or "").strip()
        if not model_name:
            QMessageBox.information(self.w, "提示", "模型名称不能为空。")
            return

        if self.w.ollama_status_label is not None:
            self.w.ollama_status_label.setText(f"Ollama 状态：正在下载模型 {model_name} ...")

        self._ollama_pull_thread = QThread(self.w)
        self._ollama_pull_worker = _OllamaPullWorker(host, model_name)
        self._ollama_pull_worker.moveToThread(self._ollama_pull_thread)

        self._ollama_pull_thread.started.connect(self._ollama_pull_worker.run)
        self._ollama_pull_worker.finished.connect(self._on_ollama_pull_finished)
        self._ollama_pull_worker.error.connect(self._on_ollama_pull_failed)

        self._ollama_pull_worker.finished.connect(self._ollama_pull_thread.quit)
        self._ollama_pull_worker.error.connect(self._ollama_pull_thread.quit)
        self._ollama_pull_worker.finished.connect(self._ollama_pull_worker.deleteLater)
        self._ollama_pull_worker.error.connect(self._ollama_pull_worker.deleteLater)
        self._ollama_pull_thread.finished.connect(self._ollama_pull_thread.deleteLater)

        self._ollama_pull_thread.start()

    def _on_ollama_pull_finished(self, result: dict):
        try:
            model_name = str(result.get("model_name", "")).strip() or "未知模型"

            if self.w.ollama_status_label is not None:
                self.w.ollama_status_label.setText(f"Ollama 状态：模型下载完成 | {model_name}")

            QMessageBox.information(self.w, "提示", f"模型下载完成：{model_name}")
            self.refresh_ollama_model_runtime()
        finally:
            self._ollama_pull_thread = None
            self._ollama_pull_worker = None

    def _on_ollama_pull_failed(self, msg: str):
        try:
            if self.w.ollama_status_label is not None:
                self.w.ollama_status_label.setText(f"Ollama 状态：模型下载失败 | {msg}")

            QMessageBox.warning(self.w, "下载失败", f"Ollama 模型下载失败：\n{msg}")
        finally:
            self._ollama_pull_thread = None
            self._ollama_pull_worker = None

    def use_selected_connection_model(self):
        combo = getattr(self.w, "connection_model_combo", None)
        if combo is None:
            return

        model_id = combo.currentData()
        if not model_id:
            QMessageBox.information(self.w, "提示", "请先选择一个模型。")
            return

        model = self.w.model_service.get_model_by_id(model_id)
        if not model:
            QMessageBox.information(self.w, "提示", "当前模型不存在。")
            return

        if not bool(model.get("available", False)):
            QMessageBox.information(self.w, "提示", "当前模型未确认可用，请先刷新模型列表。")
            return

        self.w.model_service.set_current_model(model_id)
        self.w.loader.reload_model_list()
        self.w.loader.refresh_top_bar()
        self.w.loader.load_connection_page()
        self.w.settings_applied.emit()

    def test_gpt_sovits_connection(self):
        cfg = self._build_connection_gpt_config()

        root_dir = Path(cfg["root_dir"]) if cfg["root_dir"] else None
        status_text = []

        if root_dir is None or not root_dir.exists():
            status_text.append("根目录不存在")
        else:
            api_script_path = root_dir / cfg["api_script"]
            tts_config_path = root_dir / cfg["tts_config"]

            if not api_script_path.exists():
                status_text.append("缺少 API 脚本")
            if not tts_config_path.exists():
                status_text.append("缺少 TTS 配置")

            if cfg["python_exe"]:
                if not Path(cfg["python_exe"]).exists():
                    status_text.append("Python 路径不存在")

        label = getattr(self.w, "gpt_sovits_status_label", None)
        if label is not None:
            if status_text:
                label.setText("GPT-SoVITS 状态：检测失败 | " + "；".join(status_text))
            else:
                label.setText("GPT-SoVITS 状态：路径检查通过")

    def run_connection_startup_check(self):
        self.save_connection_page(silent=True)

        report = self.w.startup_check_service.run(auto_patch=False)
        self.w.loader.load_connection_page()


    def save_connection_page(self, silent: bool = False):
        provider = self._get_connection_provider()
        gpt_cfg = self._build_connection_gpt_config()

        old_ollama_cfg = self.w.machine_profile_service.get_ollama_config()
        old_host = str(old_ollama_cfg.get("host", "http://localhost:11434")).strip() or "http://localhost:11434"

        self.w.machine_profile_service.update_section(
            "llm",
            {
                "preferred_provider": provider,
            },
        )
        self.w.machine_profile_service.update_section(
            "ollama",
            {
                "enabled": True,
                "provider": "ollama",
                "host": old_host,
            },
        )
        self.w.machine_profile_service.update_section(
            "gpt_sovits",
            {
                "enabled": True,
                **gpt_cfg,
            },
        )

        self.w.loader.load_connection_page()
        self.w.loader.refresh_top_bar()

        if not silent:
            QMessageBox.information(self.w, "提示", "连接配置已保存。")

    def refresh_developer_mode_section(self):
        enabled = bool(self.w.developer_mode_service.is_enabled())
        for label_name in ("developer_mode_status_label", "basic_developer_mode_status_label"):
            label = getattr(self.w, label_name, None)
            if label is not None:
                label.setText("当前状态：开启" if enabled else "当前状态：关闭")
        for button_name in ("btn_toggle_developer_mode", "btn_basic_toggle_developer_mode"):
            button = getattr(self.w, button_name, None)
            if button is not None:
                button.setText("关闭开发者模式" if enabled else "开启开发者模式")
        restore_card = getattr(self.w, "basic_restore_initial_environment_card", None)
        if restore_card is not None:
            restore_card.setVisible(enabled)

    def toggle_developer_mode(self):
        enabled = bool(self.w.developer_mode_service.is_enabled())
        state = self.w.developer_mode_service.set_enabled(not enabled)
        next_enabled = bool(state.get("developer_mode_enabled", False))
        self.refresh_developer_mode_section()
        message = "开发者模式已开启，请重启项目后生效。" if next_enabled else "开发者模式已关闭，请重启项目后生效。"
        QMessageBox.information(self.w, "开发者设置", message)

    def scan_project_cleanup(self):
        result = self.w.cleanup_service.scan()
        self._update_cleanup_rows(result)

    def delete_selected_project_cleanup(self):
        selected = self._selected_cleanup_keys()
        if not selected:
            QMessageBox.information(self.w, "项目清扫", "请选择清理对象。")
            return
        reply = QMessageBox.question(
            self.w,
            "项目清扫",
            "将清理可安全删除的选中项目；受保护项目会跳过。是否继续？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        result = self.w.cleanup_service.delete_selected(selected)
        self._update_cleanup_rows(result.get("scan", {}))
        failed_count = int(result.get("failed_count", 0) or 0)
        deleted_count = int(result.get("deleted_count", 0) or 0)
        deleted_size_text = str(result.get("deleted_size_text", "0 B") or "0 B")

        if deleted_count <= 0 and failed_count <= 0:
            message = "当前没有符合清理条件的项目。"
        else:
            message = (
                f"删除数量：{deleted_count}\n"
                f"删除大小：{deleted_size_text}\n"
                f"失败数量：{failed_count}"
            )

        QMessageBox.information(
            self.w,
            "项目清扫",
            message,
        )

    def open_selected_cleanup_folder(self):
        selected = self._selected_cleanup_keys()
        if len(selected) != 1:
            QMessageBox.information(self.w, "项目清扫", "请只选择一个分类。")
            return
        result = self.w.cleanup_service.open_category_folder(selected[0])
        if not result.get("ok", False):
            QMessageBox.information(
                self.w,
                "项目清扫",
                str(result.get("message", "该分类暂无可打开目录") or "该分类暂无可打开目录"),
            )
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(result.get("path", ""))))

    def _selected_cleanup_keys(self) -> list[str]:
        checks = self._active_cleanup_checks()
        return [key for key, check in checks.items() if check is not None and check.isChecked()]

    def _update_cleanup_rows(self, result: dict):
        categories = result.get("categories", []) if isinstance(result, dict) else []
        by_key = {str(item.get("key", "")): item for item in categories if isinstance(item, dict)}
        label_pairs = (
            (
                getattr(self.w, "cleanup_count_labels", {}) or {},
                getattr(self.w, "cleanup_size_labels", {}) or {},
            ),
            (
                getattr(self.w, "basic_cleanup_count_labels", {}) or {},
                getattr(self.w, "basic_cleanup_size_labels", {}) or {},
            ),
        )
        for count_labels, size_labels in label_pairs:
            for key, count_label in count_labels.items():
                item = by_key.get(key, {})
                risk = str(item.get("risk", "") or "")
                suffix = f" / {risk}" if risk else ""
                count_label.setText(f"数量：{item.get('count', item.get('item_count', item.get('file_count', '-')))}{suffix}")
            for key, size_label in size_labels.items():
                item = by_key.get(key, {})
                size_label.setText(f"大小：{item.get('size_label', item.get('total_size_text', '-'))}")

    def _active_cleanup_checks(self) -> dict:
        use_basic = False
        try:
            use_basic = self.w.page_key_from_index(self.w.stack.currentIndex()) == "basic_settings"
        except Exception:
            use_basic = False
        if use_basic:
            checks = getattr(self.w, "basic_cleanup_category_checks", {}) or {}
            if checks:
                return checks
        return getattr(self.w, "cleanup_category_checks", {}) or {}

    # =========================================================
    # 基础设置：音频设备
    # =========================================================
    def refresh_basic_audio_devices(self):
        output_combo = getattr(self.w, "audio_output_device_combo", None)
        input_combo = getattr(self.w, "audio_input_device_combo", None)

        if output_combo is None and input_combo is None:
            return

        self._loading_audio_device_combos = True

        try:
            config = self.audio_device_service.load_config()
            output_cfg = config.get("output", {}) if isinstance(config, dict) else {}
            input_cfg = config.get("input", {}) if isinstance(config, dict) else {}

            if output_combo is not None:
                self._fill_audio_device_combo(
                    combo=output_combo,
                    devices=self.audio_device_service.list_output_devices(),
                    selected_cfg=output_cfg,
                    default_text="系统默认",
                )

            if input_combo is not None:
                self._fill_audio_device_combo(
                    combo=input_combo,
                    devices=self.audio_device_service.list_input_devices(),
                    selected_cfg=input_cfg,
                    default_text="系统默认",
                )

        finally:
            self._loading_audio_device_combos = False

    def _safe_optional_int(self, value) -> int | None:
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None
        
    def _fill_audio_device_combo(self, combo, devices: list[dict], selected_cfg: dict, default_text: str):
        combo.blockSignals(True)
        combo.clear()

        combo.addItem(default_text, {"use_system_default": True, "device_index": None, "device_name": ""})

        selected_index = self._safe_optional_int(selected_cfg.get("device_index"))
        selected_name = str(selected_cfg.get("device_name", "") or "").strip()
        use_default = bool(selected_cfg.get("use_system_default", True))

        target_combo_index = 0

        for device in devices:
            raw_index = device.get("index")
            device_index = self._safe_optional_int(raw_index)
            name = str(device.get("display_name") or device.get("name") or f"设备 {raw_index}")
            combo.addItem(name, device)

            row = combo.count() - 1
            if not use_default:
                if (
                    selected_index is not None
                    and device_index is not None
                    and device_index == selected_index
                ):
                    target_combo_index = row
                elif selected_name and selected_name == str(device.get("name", "")):
                    target_combo_index = row

        if combo.count() == 1:
            combo.addItem("未发现可用设备", {"disabled": True})

        combo.setCurrentIndex(target_combo_index)
        combo.blockSignals(False)

    def on_audio_output_device_selected(self):
        if getattr(self, "_loading_audio_device_combos", False):
            return

        combo = getattr(self.w, "audio_output_device_combo", None)
        if combo is None:
            return

        data = combo.currentData()
        if not isinstance(data, dict):
            return

        if data.get("disabled"):
            return

        if data.get("use_system_default", False):
            self.audio_device_service.reset_output_to_default()
            self.w.setWindowTitle("控制中心")
            return

        device_index = self._safe_optional_int(data.get("index"))
        if device_index is None:
            return

        self.audio_device_service.set_output_device(
            device_index,
            str(data.get("name", "") or ""),
        )

    def on_audio_input_device_selected(self):
        if getattr(self, "_loading_audio_device_combos", False):
            return

        combo = getattr(self.w, "audio_input_device_combo", None)
        if combo is None:
            return

        data = combo.currentData()
        if not isinstance(data, dict):
            return

        if data.get("disabled"):
            return

        if data.get("use_system_default", False):
            self.audio_device_service.reset_input_to_default()
            return

        device_index = self._safe_optional_int(data.get("index"))
        if device_index is None:
            return

        self.audio_device_service.set_input_device(
            device_index,
            str(data.get("name", "") or ""),
        )
    def test_audio_input_device(self):
        if self._mic_test_active:
            self.stop_audio_input_live_test()
            return
        self._start_audio_input_live_test()

    def _start_audio_input_live_test(self):
        frame = getattr(self.w, "audio_input_test_frame", None)
        if frame is not None:
            frame.setVisible(True)

        button = getattr(self.w, "btn_test_audio_input_device", None)
        if button is not None:
            button.setText("停止测试")

        self._mic_test_peak = 0.0
        self._mic_test_rms = 0.0
        self._mic_test_used_fallback = False

        try:
            resolution = self.audio_device_service.resolve_input_device()
            device_index = self._safe_optional_int(resolution.get("device_index"))
            self._mic_test_device_name = (
                str(resolution.get("device_name", "") or "").strip()
                or self._current_audio_input_name()
            )
            self._mic_test_used_fallback = bool(resolution.get("fallback", False))

            self._mic_test_stream = self._open_mic_test_stream(device_index)
            self._mic_test_stream.start()

            self._mic_test_timer = QTimer(self.w)
            self._mic_test_timer.setInterval(int(self.w.UI_SIZE["basic_audio_test_update_ms"]))
            self._mic_test_timer.timeout.connect(self._update_mic_test_ui)
            self._mic_test_timer.start()

            self._mic_test_active = True
            self._set_audio_input_test_status(
                "当前状态：正在监听，未检测到明显声音",
                "峰值：0.0000  RMS：0.0000",
                status_color=UI_COLOR["basic_audio_test_status_silent"],
                bar_value=0,
                bar_color=UI_COLOR["basic_audio_level_idle"],
            )
            print(
                "[AudioInputLiveTest] start "
                f"device_index={device_index!r} "
                f"device_name={self._mic_test_device_name!r} "
                f"fallback={self._mic_test_used_fallback!r}"
            )
        except Exception as exc:
            self.stop_audio_input_live_test(update_status=False)
            if button is not None:
                button.setText("测试麦克风")
            self._set_audio_input_test_status(
                f"当前状态：测试麦克风失败：{exc}",
                "峰值：-  RMS：-",
                status_color=UI_COLOR["basic_audio_test_status_error"],
                bar_value=0,
                bar_color=UI_COLOR["basic_audio_level_idle"],
            )
            QMessageBox.warning(self.w, "音频设备", f"测试麦克风失败：\n{exc}")

    def _open_mic_test_stream(self, device_index: int | None):
        stream_kwargs = {
            "samplerate": SAMPLE_RATE,
            "channels": CHANNELS,
            "dtype": RECORD_DTYPE,
            "callback": self._on_mic_test_audio,
        }
        if device_index is not None:
            stream_kwargs["device"] = device_index

        try:
            return sd.InputStream(**stream_kwargs)
        except Exception as exc:
            if device_index is None:
                raise
            print(
                "[AudioInputLiveTest] selected_device_failed "
                f"device_index={device_index!r} error={exc!r}"
            )
            stream_kwargs.pop("device", None)
            self._mic_test_used_fallback = True
            self._mic_test_device_name = "系统默认"
            return sd.InputStream(**stream_kwargs)

    def _on_mic_test_audio(self, indata, frames, time_info, status):
        audio = self._prepare_audio_input_test_audio(indata)
        peak, _mean_abs, rms, _silent = self._audio_input_test_metrics(audio)
        self._mic_test_peak = peak
        self._mic_test_rms = rms

    def stop_audio_input_live_test(self, update_status: bool = True):
        timer = self._mic_test_timer
        self._mic_test_timer = None
        if timer is not None:
            try:
                timer.stop()
                timer.deleteLater()
            except Exception:
                pass

        stream = self._mic_test_stream
        self._mic_test_stream = None
        if stream is not None:
            try:
                stream.stop()
                stream.close()
            except Exception:
                pass

        was_active = self._mic_test_active
        self._mic_test_active = False

        button = getattr(self.w, "btn_test_audio_input_device", None)
        if button is not None:
            button.setText("测试麦克风")

        if update_status and was_active:
            self._set_audio_input_test_status(
                "当前状态：未测试",
                "峰值：-  RMS：-",
                status_color=UI_COLOR["basic_audio_test_status_idle"],
                bar_value=0,
                bar_color=UI_COLOR["basic_audio_level_idle"],
            )
            frame = getattr(self.w, "audio_input_test_frame", None)
            if frame is not None:
                frame.setVisible(False)
                frame.updateGeometry()

    def _update_mic_test_ui(self):
        peak = float(self._mic_test_peak or 0.0)
        rms = float(self._mic_test_rms or 0.0)
        silent = peak < 0.01 and rms < 0.003
        value = min(100, max(0, int(max(peak * 500, rms * 2000))))
        bar_color = self._mic_level_color(value)

        if silent:
            status_text = "当前状态：未检测到明显声音"
            status_color = UI_COLOR["basic_audio_test_status_silent"]

            # 长提示不要放进 label 正文，否则会撑宽页面。
            if self._looks_like_nvidia_broadcast(self._mic_test_device_name):
                status_text = "当前状态：虚拟麦克风未检测到声音"
                status_tooltip = "请检查 NVIDIA Broadcast 的输入源，或切换为真实麦克风。"
            else:
                status_tooltip = ""
        else:
            status_text = "当前状态：检测到麦克风输入"
            status_color = UI_COLOR["basic_audio_test_status_active"]
            status_tooltip = ""

        if self._mic_test_used_fallback:
            status_text += "（已使用系统默认输入）"

        self._set_audio_input_test_status(
            status_text,
            f"峰值：{peak:.4f}  RMS：{rms:.4f}",
            status_color=status_color,
            bar_value=value,
            bar_color=bar_color,
        )

    def _mic_level_color(self, value: int) -> str:
        if value < 10:
            return UI_COLOR["basic_audio_level_idle"]
        if value < 45:
            return UI_COLOR["basic_audio_level_low"]
        if value < 80:
            return UI_COLOR["basic_audio_level_mid"]
        if value < 95:
            return UI_COLOR["basic_audio_level_high"]
        return UI_COLOR["basic_audio_level_clip"]

    def _set_audio_input_test_status(
        self,
        status: str,
        detail: str,
        *,
        status_color: str,
        bar_value: int,
        bar_color: str,
    ):
        status_label = getattr(self.w, "audio_input_test_status_label", None)
        detail_label = getattr(self.w, "audio_input_test_detail_label", None)
        level_bar = getattr(self.w, "audio_input_level_bar", None)
        if status_label is not None:
            status_label.setText(status)
            status_label.setStyleSheet(f"color: {status_color};")
        if detail_label is not None:
            detail_label.setText(detail)
        if level_bar is not None:
            level_bar.setValue(max(0, min(100, int(bar_value))))
            self._apply_audio_level_bar_style(level_bar, bar_color)

    def _apply_audio_level_bar_style(self, level_bar, bar_color: str):
        size = self.w.UI_SIZE
        level_bar.setStyleSheet(
            "QProgressBar {"
            f"background-color: {UI_COLOR['basic_audio_test_frame_bg']};"
            f"border: {size['basic_audio_test_frame_border_width']}px solid {UI_COLOR['basic_audio_test_frame_border']};"
            f"border-radius: {size['basic_audio_test_frame_radius']}px;"
            "text-align: center;"
            "}"
            "QProgressBar::chunk {"
            f"background-color: {bar_color};"
            f"border-radius: {size['basic_audio_test_frame_radius']}px;"
            "}"
        )

    def _prepare_audio_input_test_audio(self, audio) -> np.ndarray:
        arr = np.asarray(audio, dtype=np.float32)
        if arr.ndim == 2:
            arr = arr.mean(axis=1)
        arr = np.squeeze(arr)
        arr = np.nan_to_num(arr, nan=0.0, posinf=0.0, neginf=0.0)
        arr = np.clip(arr, -1.0, 1.0)
        return arr.astype(np.float32)

    def _audio_input_test_metrics(self, audio: np.ndarray) -> tuple[float, float, float, bool]:
        abs_audio = np.abs(audio) if audio.size > 0 else np.asarray([], dtype=np.float32)
        peak = float(np.max(abs_audio)) if abs_audio.size > 0 else 0.0
        mean_abs = float(np.mean(abs_audio)) if abs_audio.size > 0 else 0.0
        rms = float(np.sqrt(np.mean(np.square(audio)))) if audio.size > 0 else 0.0
        silent = peak < 0.01 and rms < 0.003
        return peak, mean_abs, rms, silent

    def _current_audio_input_name(self) -> str:
        combo = getattr(self.w, "audio_input_device_combo", None)
        return combo.currentText() if combo is not None else ""

    def _looks_like_nvidia_broadcast(self, device_name: str) -> bool:
        lowered = str(device_name or "").lower()
        return "nvidia" in lowered or "broadcast" in lowered

    def run_project_integrity_check(self):
        try:
            # 1. 重新创建项目基础目录和默认文件
            try:
                from config import ensure_project_dirs  # type: ignore
                ensure_project_dirs()
            except Exception as exc:
                print(f"[IntegrityCheck] ensure_project_dirs failed: {exc!r}")

            # 2. 重新准备桌面本地默认文件
            try:
                from bootstrap.hundun.load import ensure_local_data_files  # type: ignore
                ensure_local_data_files()
            except Exception as exc:
                print(f"[IntegrityCheck] ensure_local_data_files failed: {exc!r}")

            # 3. 执行启动检查，并允许修复 GPT-SoVITS 路径
            report = self.w.startup_check_service.run(auto_patch=True)

            # 4. 刷新页面
            try:
                self.w.loader.load_connection_page()
                self.w.loader.refresh_top_bar()
                self.refresh_basic_audio_devices()
            except Exception as exc:
                print(f"[IntegrityCheck] refresh ui failed: {exc!r}")

            ollama = report.get("ollama", {}) if isinstance(report, dict) else {}
            gpt = report.get("gpt_sovits", {}) if isinstance(report, dict) else {}

            ollama_ok = bool(ollama.get("ok", False))
            gpt_ok = bool(gpt.get("ok", False))
            auto_patched = bool(report.get("auto_patched_profile", False))

            QMessageBox.information(
                self.w,
                "完整度检查",
                "完整度检查已完成。\n\n"
                "已执行：\n"
                "1. 检查并创建基础目录\n"
                "2. 检查并创建默认配置\n"
                "3. 检查 Ollama / GPT-SoVITS 连接配置\n\n"
                f"Ollama：{'正常' if ollama_ok else '需要检查'}\n"
                f"GPT-SoVITS：{'正常' if gpt_ok else '需要检查'}\n"
                f"默认配置修复：{'已修复' if auto_patched else '无需修复'}"
            )
        except Exception as exc:
            QMessageBox.warning(
                self.w,
                "完整度检查失败",
                f"完整度检查执行失败：\n{exc}"
            )

    def _safe_remove_path_inside_project(self, path: Path) -> tuple[int, int, list[str]]:
        import shutil

        project_root = Path(getattr(self.w.machine_profile_service, "project_root", Path.cwd())).resolve(strict=False)
        target = Path(path).resolve(strict=False)
        errors: list[str] = []

        try:
            target.relative_to(project_root)
        except Exception:
            return 0, 0, [f"跳过项目外路径：{target}"]

        if not target.exists():
            return 0, 0, []

        count = 0
        size = 0

        try:
            if target.is_file() or target.is_symlink():
                try:
                    size = target.stat().st_size
                except Exception:
                    size = 0
                target.unlink()
                return 1, size, []

            for child in target.rglob("*"):
                try:
                    if child.is_file() or child.is_symlink():
                        size += child.stat().st_size
                        count += 1
                    elif child.is_dir():
                        count += 1
                except Exception:
                    pass

            shutil.rmtree(target)
            return count + 1, size, []
        except Exception as exc:
            errors.append(f"{target} -> {exc}")
            return 0, 0, errors

    def _restore_initial_environment_keep_files(self) -> set[str]:
        from config import USER_PREFS_DIR  # type: ignore

        base = Path(USER_PREFS_DIR)
        return {
            str((base / "machine.local.json").resolve(strict=False)),
            str((base / "engines.local.json").resolve(strict=False)),
            str((base / "audio_device.local.json").resolve(strict=False)),
            str((base / "developer.local.json").resolve(strict=False)),
            str((base / "chat_display.local.json").resolve(strict=False)),
        }

    def _clear_user_prefs_except_keep_files(self) -> tuple[int, int, list[str]]:
        from config import USER_PREFS_DIR  # type: ignore

        base = Path(USER_PREFS_DIR).resolve(strict=False)
        keep = self._restore_initial_environment_keep_files()

        deleted_count = 0
        deleted_size = 0
        errors: list[str] = []

        if not base.exists():
            return 0, 0, []

        for child in base.iterdir():
            child_resolved = str(child.resolve(strict=False))
            if child_resolved in keep:
                continue
            count, size, child_errors = self._safe_remove_path_inside_project(child)
            deleted_count += count
            deleted_size += size
            errors.extend(child_errors)

        return deleted_count, deleted_size, errors

    def _format_bytes_for_reset(self, size: int) -> str:
        value = float(max(0, int(size)))
        for unit in ("B", "KB", "MB", "GB"):
            if value < 1024 or unit == "GB":
                return f"{int(value)} B" if unit == "B" else f"{value:.1f} {unit}"
            value /= 1024
        return f"{value:.1f} GB"
            
    def restore_initial_environment(self):
        try:
            if not bool(self.w.developer_mode_service.is_enabled()):
                QMessageBox.information(
                    self.w,
                    "恢复初始环境",
                    "该功能仅在开发者模式开启时可用。"
                )
                return

            first = QMessageBox.question(
                self.w,
                "恢复初始环境",
                "该操作会清理运行记录、缓存、历史聊天、临时文件和部分用户记忆。\n\n"
                "会保留：本机模型路径、连接配置、麦克风设备、开发者模式、AI显示名称。\n\n"
                "是否继续？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if first != QMessageBox.StandardButton.Yes:
                return

            second = QMessageBox.question(
                self.w,
                "二次确认",
                "请再次确认：恢复初始环境后，运行材料和历史记录将被清理。\n\n"
                "该操作不可自动撤回。是否继续？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if second != QMessageBox.StandardButton.Yes:
                return

            from config import (  # type: ignore
                BASE_DIR,
                RUNTIME_DIR,
                HISTORIES_DIR,
                LOGS_DIR,
                WORKSPACE_DIR,
                TEMP_DIR,
                DOWNLOADS_FOLDER,
                FAVORITES_FOLDER,
                ensure_project_dirs,
            )
            from bootstrap.hundun.load import ensure_local_data_files  # type: ignore

            targets = [
                Path(RUNTIME_DIR),
                Path(HISTORIES_DIR),
                Path(LOGS_DIR),
                Path(WORKSPACE_DIR),
                Path(TEMP_DIR),
                Path(DOWNLOADS_FOLDER),
                Path(FAVORITES_FOLDER),
                Path(BASE_DIR) / "data" / "runtime",
                Path(BASE_DIR) / "data" / "histories",
                Path(BASE_DIR) / "data" / "logs",
                Path(BASE_DIR) / "data" / "workspace",
            ]

            deleted_count = 0
            deleted_size = 0
            errors: list[str] = []

            for target in targets:
                count, size, target_errors = self._safe_remove_path_inside_project(target)
                deleted_count += count
                deleted_size += size
                errors.extend(target_errors)

            count, size, pref_errors = self._clear_user_prefs_except_keep_files()
            deleted_count += count
            deleted_size += size
            errors.extend(pref_errors)

            # 重建基础目录、默认文件、本机 local 文件
            ensure_project_dirs()
            ensure_local_data_files(force=False)

            # 重建 temp 目录
            try:
                if hasattr(self.w, "temp_cleanup_service"):
                    self.w.temp_cleanup_service.ensure_temp_dirs()
            except Exception:
                pass

            # 刷新 UI
            try:
                self.w.loader.refresh_top_bar()
                self.w.loader.load_connection_page()
                self.refresh_basic_audio_devices()
                self.scan_project_cleanup()
            except Exception as exc:
                print(f"[RestoreInitialEnvironment] refresh ui failed: {exc!r}")

            message = (
                "恢复初始环境已完成。\n\n"
                f"清理数量：{deleted_count}\n"
                f"清理大小：{self._format_bytes_for_reset(deleted_size)}\n"
                f"失败数量：{len(errors)}"
            )
            if errors:
                message += "\n\n部分失败：\n" + "\n".join(errors[:8])

            QMessageBox.information(self.w, "恢复初始环境", message)

        except Exception as exc:
            QMessageBox.warning(
                self.w,
                "恢复初始环境失败",
                f"恢复初始环境执行失败：\n{exc}"
            )

    def save_chat_display_settings(self):
        edit = getattr(self.w, "chat_assistant_display_name_edit", None)
        raw_name = edit.text() if edit is not None else ""
        saved = self.chat_display_config_service.set_assistant_display_name(raw_name)
        display_name = str(saved.get("assistant_display_name", "") or "AI").strip() or "AI"
        if edit is not None:
            edit.setText(display_name)

        self._refresh_open_chat_display_names(display_name)
        QMessageBox.information(self.w, "显示设置", f"AI 显示名称已保存为：{display_name}")

    def _refresh_open_chat_display_names(self, display_name: str):
        for widget in QApplication.topLevelWidgets():
            if widget is self.w:
                continue
            setter = getattr(widget, "set_assistant_display_name", None)
            if callable(setter):
                try:
                    setter(display_name)
                except Exception:
                    pass

    def _get_main_host_window(self):
        p = self.w.parent()
        if p is not None and hasattr(p, "set_status") and hasattr(p, "set_tts_runtime_status"):
            return p
        return None

    def _notify_main_tts_status(self, text: str, temporary: bool = True):
        host = self._get_main_host_window()
        if host is not None:
            try:
                host.set_tts_runtime_status(text)
                host.set_status(text, temporary=temporary)
            except Exception:
                pass

    # =========================================================
    # TTS
    # =========================================================
    def _build_combo_preview_audio_path(self, backend: str) -> str:
        ext = ".wav" if (backend or "").strip().lower() == "gpt_sovits" else TTS_OUTPUT_EXTENSION
        return str(self.w.temp_test_audio_dir / f"combo_preview{ext}")

    def _get_selected_combo_package(self) -> dict:
        combo = self.w.combo_voice_combo
        if combo is None:
            return {}
        data = combo.currentData()
        return data if isinstance(data, dict) else {}

    def _get_selected_tts_backend(self) -> str:
        backend = self.w.tts_model_combo.currentData() if self.w.tts_model_combo else None
        return (backend or "edge").strip().lower()

    def _get_selected_tts_package(self) -> dict:
        combo = self.w.combo_voice_combo
        if combo is not None:
            data = combo.currentData()
            if isinstance(data, dict):
                return data

        backend = self._get_selected_tts_backend()
        return self.w.tts_package_service.get_current_package(backend) or {}

    def _set_tts_backend_dot_color(self, color_value: str):
        if self.w.tts_backend_status_dot is not None:
            self.w.tts_backend_status_dot.setStyleSheet(
                f"color: {color_value}; font-size: 18px; font-weight: bold;"
            )

    def _mark_tts_backend_pending(self):
        self._set_tts_backend_dot_color(UI_COLOR["status_idle"])

    def _mark_tts_backend_ready(self):
        self._set_tts_backend_dot_color(UI_COLOR["status_ready"])

    def _mark_tts_backend_error(self):
        self._set_tts_backend_dot_color(UI_COLOR["status_error"])

    def _sync_valid_tts_package_for_backend(self, backend: str) -> dict:
        detail = self.w.tts_package_service.ensure_valid_current_package(backend)
        return detail if isinstance(detail, dict) else {}

    def update_tts_backend_indicator(self, status: dict):
        backend = status.get("backend", "edge")
        healthy = bool(status.get("healthy", False))

        if backend == "edge":
            self._mark_tts_backend_ready()
            self.hide_tts_loading_inline()
            return

        if healthy:
            self._mark_tts_backend_ready()
            self.hide_tts_loading_inline()
            return

        self._mark_tts_backend_error()

    def refresh_tts_backend_status(self):
        backend = self._get_selected_tts_backend()
        current_backend = (self.w.voice_service.get_current_tts_backend() or "").strip().lower()

        if backend != current_backend:
            self._mark_tts_backend_pending()
            return

        try:
            status = self.w.tts_backend_controller.get_backend_status(backend)
            self.update_tts_backend_indicator(status)
        except Exception:
            self._mark_tts_backend_error()

    def apply_chat_model_selection(self):
        model_id = self.w.chat_model_combo.currentData() if self.w.chat_model_combo else None
        if not model_id:
            return

        self.w.model_service.set_current_model(model_id)
        self.w.loader.refresh_top_bar()
        self.w.loader.reload_scheme_list()
        self.w.settings_applied.emit()

    def apply_combo_scheme_selection(self):
        combo = getattr(self.w, "combo_scheme_combo", None)
        if combo is None:
            return

        scheme_data = combo.currentData()
        if not isinstance(scheme_data, dict):
            return

        role_id = scheme_data.get("role_id", "")
        style_id = scheme_data.get("style_id", "")
        voice_id = scheme_data.get("voice_id", "")
        package_id = scheme_data.get("package_id", "")
        output_mode = scheme_data.get("output_mode", DEFAULT_OUTPUT_MODE)

        if role_id:
            self.w.role_service.set_current_role(role_id)
        if style_id:
            self.w.style_service.set_current_style(style_id)
        if voice_id:
            self.w.voice_service.set_current_voice(voice_id)

        backend = self.w.voice_service.get_current_tts_backend()
        if package_id and backend:
            self.w.tts_package_service.set_current_package(backend, package_id)

        self.w.current_output_mode = output_mode

        self._write_json_file(
            Path(WORKSPACE_DRAFT_IDENTITY_FILE),
            {
                "name": scheme_data.get("name", ""),
                "role_id": role_id,
                "model_id": scheme_data.get("model_id", ""),
                "package_id": package_id,
                "output_mode": output_mode,
            },
        )
        self._write_json_file(Path(WORKSPACE_STYLE_SELECTION_FILE), {"id": style_id})
        self._write_json_file(Path(WORKSPACE_VOICE_SELECTION_FILE), {"id": voice_id})

        self.w.reload_role_list()
        self.w.reload_style_list()
        self.w.reload_voice_list()
        self.w.refresh_top_bar()
        self.w.reload_scheme_list()
        self.w.refresh_info_page()

        self.w.settings_applied.emit()

    def _set_tts_apply_busy(self, busy: bool):
        self._tts_apply_busy = busy

        for name in [
            "btn_apply_tts_backend",
            "btn_apply_model",
            "btn_refresh_tts_models",
            "btn_apply_chat_model",
            "btn_refresh_models",
            "btn_refresh_combo_schemes",
            "btn_apply_combo_scheme",
        ]:
            btn = getattr(self.w, name, None)
            if btn is not None:
                btn.setEnabled(not busy)

        if getattr(self.w, "tts_model_combo", None) is not None:
            self.w.tts_model_combo.setEnabled(not busy)

        if getattr(self.w, "chat_model_combo", None) is not None:
            self.w.chat_model_combo.setEnabled(not busy)

        if getattr(self.w, "combo_scheme_combo", None) is not None:
            self.w.combo_scheme_combo.setEnabled(not busy)

        if getattr(self.w, "output_mode_combo", None) is not None:
            self.w.output_mode_combo.setEnabled(not busy)

        if getattr(self.w, "async_voice_combo", None) is not None:
            self.w.async_voice_combo.setEnabled(not busy)

    def apply_tts_backend_selection(self):
        backend = self._get_selected_tts_backend()
        current_backend = (self.w.voice_service.get_current_tts_backend() or "").strip().lower()

        if self._tts_apply_busy:
            return

        if self._tts_load_thread is not None and self._tts_load_thread.isRunning():
            self.update_tts_loading_inline("语音后端正在加载中，请稍候…", 20)
            return

        if backend == current_backend:
            self._set_tts_apply_busy(False)
            return

        self._tts_apply_token += 1
        self._set_tts_apply_busy(True)

        self._tts_load_thread = None
        self._tts_load_worker = None

        self.show_tts_loading_inline(f"正在加载 {backend} …", 10)
        self.update_tts_loading_inline(f"正在检查 {backend} 状态…", 20)

        self._tts_load_thread = QThread(self.w)
        self._tts_load_worker = _TTSBackendLoadWorker(self.w.tts_backend_controller, backend)
        self._tts_load_worker.moveToThread(self._tts_load_thread)

        self._tts_load_thread.started.connect(self._tts_load_worker.run)
        self._tts_load_worker.finished.connect(self._on_tts_backend_loaded)
        self._tts_load_worker.error.connect(self._on_tts_backend_load_failed)

        self._tts_load_worker.finished.connect(self._tts_load_thread.quit)
        self._tts_load_worker.error.connect(self._tts_load_thread.quit)
        self._tts_load_worker.finished.connect(self._tts_load_worker.deleteLater)
        self._tts_load_worker.error.connect(self._tts_load_worker.deleteLater)
        self._tts_load_thread.finished.connect(self._tts_load_thread.deleteLater)

        self._tts_load_thread.start()
        QTimer.singleShot(30000, self._ensure_tts_apply_not_stuck)

    def _on_tts_backend_loaded(self, status: dict):
        error_msg = None

        try:
            backend = str(status.get("backend") or self._get_selected_tts_backend()).strip().lower()

            self.update_tts_loading_inline(f"{backend} 已连接，正在保存配置…", 70)

            self._persist_selected_tts_backend_lightweight()
            self._sync_valid_tts_package_for_backend(backend)

            self.update_tts_loading_inline("加载完成，正在刷新界面…", 90)

            self.update_tts_backend_indicator(status)

            try:
                self.w.loader.reload_tts_package_list(backend)
            except Exception:
                pass

            self.w.loader.refresh_top_bar()

        except Exception as e:
            error_msg = str(e)
            self._mark_tts_backend_error()

        finally:
            self.hide_tts_loading_inline()
            self._tts_load_thread = None
            self._tts_load_worker = None
            self._set_tts_apply_busy(False)

            if error_msg:
                QMessageBox.warning(self.w, "提示", f"语音后端加载成功，但界面同步失败：\n{error_msg}")
                return

            try:
                self.w.settings_applied.emit()
            except Exception:
                pass

            self._start_gpt_sovits_preload_after_apply()

    def _on_tts_backend_load_failed(self, msg: str):
        try:
            self._mark_tts_backend_error()
            self.update_tts_loading_inline(f"加载失败：{msg}", 0)
            QMessageBox.warning(self.w, "语音后端加载失败", msg)
        finally:
            self.hide_tts_loading_inline()
            self._tts_load_thread = None
            self._tts_load_worker = None
            self._set_tts_apply_busy(False)

    def show_tts_loading_inline(self, text: str = "正在加载语音后端…", percent: int = 0):
        self._mark_tts_backend_pending()

        if self.w.tts_loading_frame is not None:
            self.w.tts_loading_frame.setVisible(True)

        if self.w.tts_loading_text_label is not None:
            self.w.tts_loading_text_label.setText(text)

        if self.w.tts_loading_percent_label is not None:
            self.w.tts_loading_percent_label.setText(f"{max(0, min(percent, 100))}%")

        if self.w.tts_loading_movie is not None:
            self.w.tts_loading_movie.start()

    def update_tts_loading_inline(self, text: str, percent: int):
        self._mark_tts_backend_pending()

        if self.w.tts_loading_frame is not None and not self.w.tts_loading_frame.isVisible():
            self.w.tts_loading_frame.setVisible(True)

        if self.w.tts_loading_text_label is not None:
            self.w.tts_loading_text_label.setText(text)

        if self.w.tts_loading_percent_label is not None:
            self.w.tts_loading_percent_label.setText(f"{max(0, min(percent, 100))}%")

    def hide_tts_loading_inline(self):
        if self.w.tts_loading_movie is not None:
            self.w.tts_loading_movie.stop()

        if self.w.tts_loading_frame is not None:
            self.w.tts_loading_frame.setVisible(False)

    # =========================================================
    # 文件夹
    # =========================================================
    def open_role_config_folder(self):
        folder = Path(STYLES_DIR)
        folder.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))

    def open_voice_config_folder(self):
        folder = Path(VOICES_DIR)
        folder.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))

    # =========================================================
    # 预览 / 模拟
    # =========================================================
    def preview_role_config_text(self):
        QMessageBox.information(self.w, "提示", "第一版先预留文本模板预览入口。")

    def run_combo_preview(self):
        text = self.w.combo_input_text.toPlainText().strip() if self.w.combo_input_text else ""
        if not text:
            QMessageBox.information(self.w, "提示", "请先输入测试文本。")
            return

        if self.apply_info_page() is False:
            return

        backend = self._get_selected_tts_backend()
        package = self._get_selected_combo_package()
        voice_profile = self.w.voice_service.get_current_voice_profile() or {}
        style_profile = self.w.style_service.get_current_style_profile() or {}
        role_meta = self.w.role_service.get_current_role_meta() or {}

        output_file = self._build_combo_preview_audio_path(backend)
        runtime_cfg = self.w.tts_package_service.build_runtime_config(backend, package)

        voice_profile = {
            **voice_profile,
            "ref_audio_path": runtime_cfg.get("ref_audio_path", ""),
            "ref_wav": runtime_cfg.get("ref_audio_path", ""),
            "prompt_text_path": runtime_cfg.get("prompt_text_path", ""),
            "ref_txt": runtime_cfg.get("prompt_text_path", ""),
            "prompt_text": runtime_cfg.get("prompt_text", ""),
            "gpt_sovits_json": runtime_cfg.get("model_config_path", ""),
            "api_url": runtime_cfg.get("api_url", ""),
            "text_lang": runtime_cfg.get("text_lang", ""),
            "prompt_lang": runtime_cfg.get("prompt_lang", ""),
            "gpt_model_path": runtime_cfg.get("gpt_model_path", ""),
            "sovits_model_path": runtime_cfg.get("sovits_model_path", ""),
        }

        request_voice = runtime_cfg.get("voice")
        if not request_voice and backend == "edge":
            request_voice = self.w.voice_service.get_current_tts_voice_name()

        performance_profile = {
            "rate": style_profile.get("rate", 0),
            "volume": style_profile.get("volume", 0),
            "pitch": style_profile.get("pitch", 0),
            "style_name": style_profile.get("name", style_profile.get("id", "")),
            "scene": voice_profile.get("scene", "daily"),
            "emotion": voice_profile.get("emotion", "gentle"),
            "emotion_strength": voice_profile.get("emotion_strength", "medium"),
            "speed": voice_profile.get("speed", "normal"),
            "pause": voice_profile.get("pause", "medium"),
            "intonation": voice_profile.get("intonation", "normal"),
            "emphasis": voice_profile.get("emphasis", "natural"),
        }

        request = TTSRequest(
            text=text,
            output_file=output_file,
            backend=backend,
            voice=request_voice,
            voice_profile=voice_profile,
            performance_profile=performance_profile,
            extra={
                "role_id": role_meta.get("id", ""),
                "style_id": style_profile.get("id", ""),
                "voice_id": voice_profile.get("id", ""),
                "tts_package_id": runtime_cfg.get("package_id", ""),
                "tts_package_name": runtime_cfg.get("package_name", ""),
                "tts_package_path": runtime_cfg.get("package_path", ""),
                "text_lang": runtime_cfg.get("text_lang", ""),
                "prompt_lang": runtime_cfg.get("prompt_lang", ""),
                "api_url": runtime_cfg.get("api_url", ""),
                "model_config_path": runtime_cfg.get("model_config_path", ""),
            },
        )

        try:
            if self.w.combo_waiting_label is not None:
                self.w.combo_waiting_label.setText("预计等待：正在生成语音…")

            generate_tts(request)
            self.w.current_test_audio_path = output_file
            self._write_text_file(Path(WORKSPACE_PREVIEW_TEXT_FILE), text)

            scheme_name = self.w.combo_name_edit.text().strip() if self.w.combo_name_edit else "-"
            if not scheme_name:
                scheme_name = "-"

            style_name = self.w.combo_role_config_combo.currentText() if self.w.combo_role_config_combo else "-"
            voice_name = self.w.combo_voice_config_combo.currentText() if self.w.combo_voice_config_combo else "-"
            package_name = package.get("name", package.get("id", "-"))

            if getattr(self.w, "combo_test_config_preview", None) is not None:
                self.w.combo_test_config_preview.setPlainText(
                    f"创建方案名称：{self.w.combo_name_edit.text().strip() if self.w.combo_name_edit else '-'}\n"
                    f"当前方案：{scheme_name}\n"
                    f"文本模板：{style_name}\n"
                    f"表现模板：{voice_name}\n"
                    f"语音包：{package_name}\n"
                    f"语音后端：{backend}\n"
                    f"输出模式：{self.w.current_output_mode}\n\n"
                    f"测试文本：\n{text}\n\n"
                    f"人设说明：\n{self.w.combo_persona_edit.toPlainText().strip() if self.w.combo_persona_edit else '-'}"
                )

            if self.w.combo_voice_preview is not None:
                self.w.combo_voice_preview.setPlainText(
                    f"测试选中方案：{self.w.combo_name_edit.text().strip() if self.w.combo_name_edit else '-'}\n\n"
                    f"当前方案：{scheme_name}\n"
                    f"文本模板：{style_name}\n"
                    f"表现模板：{voice_name}\n"
                    f"语音包：{package_name}\n"
                    f"语音后端：{backend}\n"
                    f"输出模式：{self.w.current_output_mode}"
                )

            if self.w.combo_waiting_label is not None:
                self.w.combo_waiting_label.setText("预计等待：语音已生成")

            self.w.capture_snapshot("info")
            self.w.preview_audio_player.stop()
            self.w.preview_audio_player.setSource(QUrl())
            self.mock_audio_play()

        except Exception as e:
            if self.w.combo_waiting_label is not None:
                self.w.combo_waiting_label.setText("预计等待：生成失败")
            QMessageBox.warning(self.w, "生成失败", f"第三页纯 TTS 生成失败：\n{str(e)}")

    def toggle_combo_loop(self):
        self.w.combo_loop_enabled = not getattr(self.w, "combo_loop_enabled", False)
        self.w.refresh_combo_loop_button()

    def seek_combo_audio(self, value: int):
        duration = self.w.preview_audio_player.duration()
        if duration <= 0:
            return
        position = int(duration * value / 1000)
        self.w.preview_audio_player.setPosition(position)

    def mock_audio_play(self):
        path = self.w.current_test_audio_path
        if not path or not Path(path).exists():
            QMessageBox.information(self.w, "提示", "请先生成测试语音。")
            return

        speed = 1.0
        if self.w.combo_speed_combo is not None:
            speed = float(self.w.combo_speed_combo.currentData() or 1.0)

        current_source = self.w.preview_audio_player.source().toLocalFile()
        state = self.w.preview_audio_player.playbackState()

        if current_source == path and state == self.w.preview_audio_player.PlaybackState.PlayingState:
            self.w.preview_audio_player.pause()
            if self.w.combo_waiting_label is not None:
                self.w.combo_waiting_label.setText("预计等待：已暂停")
            return

        if current_source != path:
            self.w.preview_audio_player.stop()
            self.w.preview_audio_player.setSource(QUrl.fromLocalFile(path))

        self.w.preview_audio_player.setPlaybackRate(speed)
        self.w.preview_audio_player.play()

        if self.w.combo_waiting_label is not None:
            loop_text = "，循环开启" if getattr(self.w, "combo_loop_enabled", False) else ""
            self.w.combo_waiting_label.setText(f"预计等待：正在播放（{speed:.1f}x{loop_text}）")

    # =========================================================
    # 第三页方案
    # =========================================================
    def get_selected_style_id_for_save(self) -> str:
        combo = self.w.current_style_config_combo
        if combo is not None:
            data = combo.currentData()
            if isinstance(data, dict):
                return data.get("id", "") or ""
        return self.w.style_service.get_current_style_id()

    def get_selected_voice_id_for_save(self) -> str:
        combo = self.w.current_voice_config_combo
        if combo is not None:
            data = combo.currentData()
            if isinstance(data, dict):
                return data.get("id", "") or ""
        return self.w.voice_service.get_current_voice_id()

    def save_combo_preset(self):
        data = self.w.collect_info_form_data()
        combo_name = data.get("name", "").strip()

        if not combo_name:
            QMessageBox.information(self.w, "提示", "请先填写方案名称。")
            return

        combo_id = self._normalize_combo_id(combo_name)
        target_file = self.w.combo_presets_dir / f"{combo_id}.json"

        self._write_json_file(target_file, data)
        self.save_workspace_draft()
        self.w.reload_saved_combo_list()
        self.w.reload_scheme_list()
        self.w.refresh_top_bar()

        if self.w.combo_scheme_combo is not None:
            for i in range(self.w.combo_scheme_combo.count()):
                combo_data = self.w.combo_scheme_combo.itemData(i)
                if isinstance(combo_data, dict) and combo_data.get("name") == combo_name:
                    self.w.combo_scheme_combo.setCurrentIndex(i)
                    break

        self.w.capture_snapshot("info")
        QMessageBox.information(self.w, "提示", f"组合方案已保存：{combo_name}")

        if self.w.saved_combo_combo is not None:
            for i in range(self.w.saved_combo_combo.count()):
                item = self.w.saved_combo_combo.item(i)
                if item and item.text() == combo_name:
                    self.w.saved_combo_combo.setCurrentRow(i)
                    break

    def load_combo_preset(self):
        if self.w.saved_combo_combo is None:
            return

        item = self.w.saved_combo_combo.currentItem()
        if item is None:
            QMessageBox.information(self.w, "提示", "请先选择一个已保存方案。")
            return

        file_path = item.data(Qt.ItemDataRole.UserRole)
        if not file_path:
            return

        data = self._read_json_file(Path(file_path))
        if not data:
            QMessageBox.information(self.w, "提示", "方案文件读取失败。")
            return

        self._fill_info_page_from_combo_data(data)

        if not self._apply_scheme_data_to_runtime(data):
            return

        self.w.reload_model_list()
        self.w.reload_role_list()
        self.w.reload_style_list()
        self.w.reload_voice_list()
        self.w.refresh_top_bar()
        self.w.refresh_info_page()
        self.w.reload_scheme_list()
        self.w.reload_saved_combo_list()

        if self.w.combo_scheme_combo is not None:
            for i in range(self.w.combo_scheme_combo.count()):
                combo_data = self.w.combo_scheme_combo.itemData(i)
                if isinstance(combo_data, dict) and combo_data.get("name") == data.get("name", ""):
                    self.w.combo_scheme_combo.setCurrentIndex(i)
                    break

        self.w.capture_snapshot("info")
        self.w.settings_applied.emit()
        self._start_gpt_sovits_preload_after_apply()

        QMessageBox.information(self.w, "提示", f"方案已应用：{data.get('name', '-')}")

    def delete_combo_preset(self):
        if self.w.saved_combo_combo is None:
            return

        item = self.w.saved_combo_combo.currentItem()
        if item is None:
            QMessageBox.information(self.w, "提示", "请先选择一个已保存方案。")
            return

        file_path = item.data(Qt.ItemDataRole.UserRole)
        if not file_path:
            QMessageBox.information(self.w, "提示", "当前方案路径无效。")
            return

        path = Path(file_path)
        if not path.exists():
            QMessageBox.warning(self.w, "提示", "方案文件不存在。")
            return

        reply = QMessageBox.question(
            self.w,
            "确认删除",
            f"确定删除方案：{path.stem} 吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            path.unlink()
            self.w.reload_saved_combo_list()
            self.w.reload_scheme_list()
            self.w.refresh_top_bar()
            QMessageBox.information(self.w, "提示", "方案已删除。")
        except Exception as e:
            QMessageBox.warning(self.w, "提示", f"删除失败：\n{str(e)}")

    def _apply_scheme_data_to_runtime(self, data: dict) -> bool:
        if not isinstance(data, dict):
            return False

        model_id = str(data.get("model_id", "")).strip()
        role_id = str(data.get("role_id", "")).strip()
        style_id = str(data.get("style_id", "")).strip()
        voice_id = str(data.get("voice_id", "")).strip()
        package_id = str(data.get("package_id", "")).strip()
        output_mode = data.get("output_mode", DEFAULT_OUTPUT_MODE)
        scheme_name = str(data.get("name", "")).strip()
        persona = str(data.get("persona", "")).strip()

        backend = self._get_selected_tts_backend()

        if backend:
            ok, err, _runtime_cfg = self._validate_tts_package_before_apply(backend, package_id)
            if not ok:
                QMessageBox.warning(self.w, "语音包无效", f"当前语音包无法应用：\n{err}")
                return False

        if model_id:
            self.w.model_service.set_current_model(model_id)
        if role_id:
            self.w.role_service.set_current_role(role_id)
        if style_id:
            self.w.style_service.set_current_style(style_id)
        if voice_id:
            self.w.voice_service.set_current_voice(voice_id)

        if package_id and backend:
            self.w.tts_package_service.set_current_package(backend, package_id)
        elif backend:
            self._sync_valid_tts_package_for_backend(backend)

        self.w.current_output_mode = output_mode
        self._persist_selected_tts_backend_lightweight()

        self._write_json_file(
            Path(WORKSPACE_DRAFT_IDENTITY_FILE),
            {
                "name": scheme_name,
                "role_id": role_id,
                "model_id": model_id,
                "package_id": package_id,
                "output_mode": output_mode,
            },
        )
        self._write_json_file(Path(WORKSPACE_STYLE_SELECTION_FILE), {"id": style_id})
        self._write_json_file(Path(WORKSPACE_VOICE_SELECTION_FILE), {"id": voice_id})
        self._write_text_file(Path(WORKSPACE_PERSONA_DRAFT_FILE), persona)

        return True

    # =========================================================
    # 草稿 / 文件工具
    # =========================================================
    def save_workspace_draft(self):
        data = self.w.collect_info_form_data()

        self._write_json_file(
            Path(WORKSPACE_DRAFT_IDENTITY_FILE),
            {
                "name": data.get("name", ""),
                "role_id": data.get("role_id", ""),
                "model_id": data.get("model_id", ""),
                "package_id": data.get("package_id", ""),
                "output_mode": data.get("output_mode", DEFAULT_OUTPUT_MODE),
            },
        )

        self._write_json_file(Path(WORKSPACE_STYLE_SELECTION_FILE), {"id": data.get("style_id", "")})
        self._write_json_file(Path(WORKSPACE_VOICE_SELECTION_FILE), {"id": data.get("voice_id", "")})
        self._write_text_file(Path(WORKSPACE_PERSONA_DRAFT_FILE), data.get("persona", ""))

    def _read_json_file(self, path: Path) -> dict:
        if not path.exists():
            return {}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _write_json_file(self, path: Path, data: dict):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def _write_text_file(self, path: Path, text: str):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text or "", encoding="utf-8")

    def _normalize_combo_id(self, name: str) -> str:
        text = (name or "").strip()
        if not text:
            return "combo_default"

        safe = []
        for ch in text:
            if ch.isalnum() or ch in ("_", "-"):
                safe.append(ch)
            elif ch in (" ", "　"):
                safe.append("_")
            else:
                safe.append("_")

        combo_id = "".join(safe).strip("_").lower()
        return combo_id or "combo_default"

    def _ensure_tts_apply_not_stuck(self):
        if not self._tts_apply_busy:
            return

        thread = self._tts_load_thread
        if thread is not None and thread.isRunning():
            return

        self.hide_tts_loading_inline()
        self._set_tts_apply_busy(False)

    def _collect_connection_policy_override_data(self) -> dict:
        family_override = ""
        size_tier_override = ""
        template_override = ""
        patch_data = {}

        combo = getattr(self.w, "policy_family_override_combo", None)
        if combo is not None:
            family_override = str(combo.currentData() or "").strip().lower()

        combo = getattr(self.w, "policy_size_tier_override_combo", None)
        if combo is not None:
            size_tier_override = str(combo.currentData() or "").strip().lower()

        combo = getattr(self.w, "policy_template_override_combo", None)
        if combo is not None:
            template_override = str(combo.currentData() or "").strip()

        edit = getattr(self.w, "policy_override_json_edit", None)
        raw_text = edit.toPlainText().strip() if edit is not None else ""

        if raw_text:
            try:
                parsed = json.loads(raw_text)
                if isinstance(parsed, dict):
                    patch_data = parsed
                else:
                    raise ValueError("JSON 不是对象。")
            except Exception as e:
                raise ValueError(f"策略补丁 JSON 格式错误：{e}")

        if template_override:
            patch_data["template"] = template_override

        return {
            "family_override": family_override,
            "size_tier_override": size_tier_override,
            "policy_override": patch_data,
        }

    def refresh_connection_policy_preview(self, model: dict | None = None):
        model = model or self.w.model_service.get_current_model() or {}

        preview = getattr(self.w, "connection_policy_preview_display", None)
        if preview is None:
            return

        family = str(model.get("family", "unknown")).strip() or "unknown"
        size_tier = str(model.get("size_tier", "medium")).strip() or "medium"
        family_override = str(model.get("family_override", "")).strip() or "自动"
        size_tier_override = str(model.get("size_tier_override", "")).strip() or "自动"
        policy_profile = model.get("policy_profile", {}) or {}
        policy_name = str(policy_profile.get("policy_name", "-")).strip() or "-"
        policy_version = str(model.get("policy_version", "v1")).strip() or "v1"
        selected_at = str(model.get("policy_selected_at", "")).strip() or "-"

        preview.setPlainText(
            f"当前模型：{model.get('model_name', model.get('name', '-'))}\n"
            f"Family：{family}\n"
            f"Size Tier：{size_tier}\n"
            f"Family 覆盖：{family_override}\n"
            f"Size Tier 覆盖：{size_tier_override}\n"
            f"策略名称：{policy_name}\n"
            f"策略版本：{policy_version}\n"
            f"策略生成时间：{selected_at}\n\n"
            f"最终策略：\n{json.dumps(policy_profile, ensure_ascii=False, indent=2)}"
        )

    def on_connection_model_changed(self):
        combo = getattr(self.w, "connection_model_combo", None)
        if combo is None:
            return

        model_id = combo.currentData()
        if not model_id:
            return

        model = self.w.model_service.get_model_by_id(model_id)
        if not model:
            return

    def clear_connection_policy_override(self):
        combo = getattr(self.w, "policy_family_override_combo", None)
        if combo is not None:
            combo.blockSignals(True)
            combo.setCurrentIndex(0)
            combo.blockSignals(False)

        combo = getattr(self.w, "policy_size_tier_override_combo", None)
        if combo is not None:
            combo.blockSignals(True)
            combo.setCurrentIndex(0)
            combo.blockSignals(False)

        combo = getattr(self.w, "policy_template_override_combo", None)
        if combo is not None:
            combo.blockSignals(True)
            combo.setCurrentIndex(0)
            combo.blockSignals(False)

        edit = getattr(self.w, "policy_override_json_edit", None)
        if edit is not None:
            edit.blockSignals(True)
            edit.clear()
            edit.blockSignals(False)

        self.on_connection_page_changed()

    def apply_connection_policy_override(self):
        combo = getattr(self.w, "connection_model_combo", None)
        if combo is None:
            QMessageBox.information(self.w, "提示", "当前没有模型选择框。")
            return

        model_id = combo.currentData()
        if not model_id:
            QMessageBox.information(self.w, "提示", "请先选择一个模型。")
            return

        model = self.w.model_service.get_model_by_id(model_id)
        if not model:
            QMessageBox.information(self.w, "提示", "当前模型不存在。")
            return

        try:
            override_data = self._collect_connection_policy_override_data()
        except Exception as e:
            QMessageBox.warning(self.w, "提示", str(e))
            return

        merged = dict(model)
        merged.update(override_data)

        saved = self.w.model_service.upsert_model(merged)

        current_model_id = self.w.model_service.get_current_model_id()
        if model_id == current_model_id:
            self.w.model_service.set_current_model(model_id)

        self.w.loader.load_connection_policy_section(saved)
        self.w.loader.refresh_top_bar()

        QMessageBox.information(self.w, "提示", "模型策略覆盖已应用。")

    def _start_gpt_sovits_preload_after_apply(self):
        backend = self._get_selected_tts_backend()

        if backend != "gpt_sovits":
            self._notify_main_tts_status("当前语音后端无需预加载")
            return

        if self._tts_preload_thread is not None and self._tts_preload_thread.isRunning():
            self.update_tts_loading_inline("GPT-SoVITS 预加载中，请稍候…", 20)
            self._notify_main_tts_status("GPT-SoVITS 正在连接中…")
            return

        self.show_tts_loading_inline("正在预加载 GPT-SoVITS…", 5)
        self._notify_main_tts_status("正在连接 GPT-SoVITS…")

        self._tts_preload_thread = QThread(self.w)
        self._tts_preload_worker = _TTSBackendPreloadWorker(
            self.w.tts_backend_controller,
            self.w.voice_service,
            self.w.tts_package_service,
        )
        self._tts_preload_worker.moveToThread(self._tts_preload_thread)

        self._tts_preload_thread.started.connect(self._tts_preload_worker.run)
        self._tts_preload_worker.progress.connect(self.update_tts_loading_inline)

        self._tts_preload_worker.finished.connect(self._on_tts_backend_preload_finished)
        self._tts_preload_worker.error.connect(self._on_tts_backend_preload_failed)

        self._tts_preload_worker.finished.connect(self._tts_preload_thread.quit)
        self._tts_preload_worker.error.connect(self._tts_preload_thread.quit)
        self._tts_preload_worker.finished.connect(self._tts_preload_worker.deleteLater)
        self._tts_preload_worker.error.connect(self._tts_preload_worker.deleteLater)
        self._tts_preload_thread.finished.connect(self._tts_preload_thread.deleteLater)

        self._tts_preload_thread.start()

    def _on_tts_backend_preload_finished(self, result: dict):
        try:
            self.hide_tts_loading_inline()
            self._mark_tts_backend_ready()
            self.w.loader.refresh_top_bar()

            detail = str(result.get("detail", "")).strip() or str(result.get("package_id", "")).strip() or "当前语音包"
            self._notify_main_tts_status(f"GPT-SoVITS 已连接成功：{detail}")
        finally:
            self._tts_preload_thread = None
            self._tts_preload_worker = None

    def _on_tts_backend_preload_failed(self, msg: str):
        try:
            self.hide_tts_loading_inline()
            self._mark_tts_backend_error()
            self._notify_main_tts_status(f"GPT-SoVITS 连接失败：{msg}")
            self.update_tts_loading_inline(f"预加载失败：{msg}", 0)
        finally:
            self._tts_preload_thread = None
            self._tts_preload_worker = None

    def _validate_tts_package_before_apply(self, backend: str, package_id: str) -> tuple[bool, str, dict]:
        backend = (backend or "edge").strip().lower()

        try:
            if package_id:
                package = self.w.tts_package_service.get_package_detail(backend, package_id) or {}
            else:
                package = self.w.tts_package_service.get_current_package(backend) or {}

            if not package:
                return False, "未找到对应语音包。", {}

            runtime_cfg = self.w.tts_package_service.build_runtime_config(backend, package)

            if backend == "gpt_sovits":
                gpt_model_path = str(runtime_cfg.get("gpt_model_path", "")).strip()
                sovits_model_path = str(runtime_cfg.get("sovits_model_path", "")).strip()

                if not gpt_model_path or not sovits_model_path:
                    return False, "该语音包缺少 gpt_model_path 或 sovits_model_path。", {}

            return True, "", runtime_cfg

        except Exception as e:
            return False, str(e), {}
