class ControlCenterForms:
    """
    控制中心表单层

    作用：
    1. 收集第一页、第二页、第三页表单数据
    2. 将 style / voice profile 回填到页面
    3. 统一字段读写，减少主窗口负担
    """

    def __init__(self, window):
        self.w = window

    # =========================================================
    # 第二页：收集文本模板数据
    # =========================================================
    def collect_style_form_data(self) -> dict:
        return {
            "name": self.w.role_config_name_edit.text().strip() if self.w.role_config_name_edit else "",
            "scene": self.w.text_scene_combo.currentData() if getattr(self.w, "text_scene_combo", None) else "daily",
            "reply_mode": self.w.reply_mode_combo.currentData() if self.w.reply_mode_combo else "gentle",
            "explain_tendency": self.w.explain_tendency_combo.currentData() if getattr(self.w, "explain_tendency_combo", None) else "medium",
            "comfort_tendency": self.w.comfort_tendency_combo.currentData() if getattr(self.w, "comfort_tendency_combo", None) else "medium",
            "tone_strength": self.w.tone_strength_combo.currentData() if getattr(self.w, "tone_strength_combo", None) else "medium",
            "catchphrase": self.w.catchphrase_edit.toPlainText().strip() if self.w.catchphrase_edit else "",
            "opening_style": self.w.opening_style_edit.toPlainText().strip() if self.w.opening_style_edit else "",
            "forbidden": self.w.forbidden_edit.toPlainText().strip() if self.w.forbidden_edit else "",
        }

    # =========================================================
    # 第二页：收集发声模板数据
    # =========================================================
    def collect_voice_form_data(self) -> dict:
        backend = self.w.tts_model_combo.currentData() if getattr(self.w, "tts_model_combo", None) else "edge"

        return {
            "name": self.w.voice_config_name_edit.text().strip() if self.w.voice_config_name_edit else "",
            "backend": backend or "edge",
            "voice": "zh-CN-XiaoxiaoNeural",
            "scene": self.w.scene_combo.currentData() if getattr(self.w, "scene_combo", None) else "daily",
            "emotion": self.w.emotion_combo.currentData() if getattr(self.w, "emotion_combo", None) else "gentle",
            "emotion_strength": self.w.emotion_strength_combo.currentData() if getattr(self.w, "emotion_strength_combo", None) else "medium",
            "speed": self.w.speed_combo.currentData() if getattr(self.w, "speed_combo", None) else "normal",
            "pause": self.w.pause_combo.currentData() if getattr(self.w, "pause_combo", None) else "medium",
            "intonation": self.w.intonation_combo.currentData() if getattr(self.w, "intonation_combo", None) else "normal",
            "emphasis": self.w.emphasis_combo.currentData() if getattr(self.w, "emphasis_combo", None) else "natural",
        }

    # =========================================================
    # 第三页：收集角色组合数据
    # =========================================================
    def collect_info_form_data(self) -> dict:
        scheme_data = self.w.combo_scheme_name_combo.currentData() if getattr(self.w, "combo_scheme_name_combo", None) else {}
        style_data = self.w.combo_role_config_combo.currentData() if getattr(self.w, "combo_role_config_combo", None) else {}
        voice_data = self.w.combo_voice_config_combo.currentData() if getattr(self.w, "combo_voice_config_combo", None) else {}
        package_data = self.w.combo_voice_combo.currentData() if getattr(self.w, "combo_voice_combo", None) else {}

        role_id = scheme_data.get("role_id", "") if isinstance(scheme_data, dict) else ""
        style_id = style_data.get("id", "") if isinstance(style_data, dict) else ""
        voice_id = voice_data.get("id", "") if isinstance(voice_data, dict) else ""
        package_id = package_data.get("id", "") if isinstance(package_data, dict) else ""

        current_model = self.w.model_service.get_current_model() or {}
        model_id = current_model.get("id", "")

        return {
            "name": self.w.combo_name_edit.text().strip() if self.w.combo_name_edit else "",
            "persona": self.w.combo_persona_edit.toPlainText().strip() if self.w.combo_persona_edit else "",
            "role_id": role_id or "",
            "style_id": style_id or "",
            "voice_id": voice_id or "",
            "package_id": package_id or "",
            "model_id": model_id or "",
            "output_mode": self.w.current_output_mode,
        }

    # =========================================================
    # 第二页：回填发声模板到页面
    # =========================================================
    def fill_voice_editor_from_current_profile(self):
        profile = self.w.voice_service.get_current_voice_profile() or {}

        if hasattr(self.w, "voice_config_name_edit") and self.w.voice_config_name_edit is not None:
            self.w.voice_config_name_edit.blockSignals(True)
            self.w.voice_config_name_edit.setText(profile.get("name", profile.get("id", "")))
            self.w.voice_config_name_edit.blockSignals(False)

        if hasattr(self.w, "scene_combo") and self.w.scene_combo is not None:
            idx = self.w.scene_combo.findData(profile.get("scene", "daily"))
            if idx >= 0:
                self.w.scene_combo.blockSignals(True)
                self.w.scene_combo.setCurrentIndex(idx)
                self.w.scene_combo.blockSignals(False)

        if hasattr(self.w, "emotion_combo") and self.w.emotion_combo is not None:
            idx = self.w.emotion_combo.findData(profile.get("emotion", "gentle"))
            if idx >= 0:
                self.w.emotion_combo.blockSignals(True)
                self.w.emotion_combo.setCurrentIndex(idx)
                self.w.emotion_combo.blockSignals(False)

        if hasattr(self.w, "emotion_strength_combo") and self.w.emotion_strength_combo is not None:
            idx = self.w.emotion_strength_combo.findData(profile.get("emotion_strength", "medium"))
            if idx >= 0:
                self.w.emotion_strength_combo.blockSignals(True)
                self.w.emotion_strength_combo.setCurrentIndex(idx)
                self.w.emotion_strength_combo.blockSignals(False)

        if hasattr(self.w, "speed_combo") and self.w.speed_combo is not None:
            idx = self.w.speed_combo.findData(profile.get("speed", "normal"))
            if idx >= 0:
                self.w.speed_combo.blockSignals(True)
                self.w.speed_combo.setCurrentIndex(idx)
                self.w.speed_combo.blockSignals(False)

        if hasattr(self.w, "pause_combo") and self.w.pause_combo is not None:
            idx = self.w.pause_combo.findData(profile.get("pause", "medium"))
            if idx >= 0:
                self.w.pause_combo.blockSignals(True)
                self.w.pause_combo.setCurrentIndex(idx)
                self.w.pause_combo.blockSignals(False)

        if hasattr(self.w, "intonation_combo") and self.w.intonation_combo is not None:
            idx = self.w.intonation_combo.findData(profile.get("intonation", "normal"))
            if idx >= 0:
                self.w.intonation_combo.blockSignals(True)
                self.w.intonation_combo.setCurrentIndex(idx)
                self.w.intonation_combo.blockSignals(False)

        if hasattr(self.w, "emphasis_combo") and self.w.emphasis_combo is not None:
            idx = self.w.emphasis_combo.findData(profile.get("emphasis", "natural"))
            if idx >= 0:
                self.w.emphasis_combo.blockSignals(True)
                self.w.emphasis_combo.setCurrentIndex(idx)
                self.w.emphasis_combo.blockSignals(False)

    # =========================================================
    # 第二页：回填文本模板到页面
    # =========================================================
    def fill_style_editor_from_current_profile(self):
        profile = self.w.style_service.get_current_style_profile() or {}

        if hasattr(self.w, "role_config_name_edit") and self.w.role_config_name_edit is not None:
            self.w.role_config_name_edit.blockSignals(True)
            self.w.role_config_name_edit.setText(profile.get("name", profile.get("id", "")))
            self.w.role_config_name_edit.blockSignals(False)

        if hasattr(self.w, "text_scene_combo") and self.w.text_scene_combo is not None:
            idx = self.w.text_scene_combo.findData(profile.get("scene", "daily"))
            if idx >= 0:
                self.w.text_scene_combo.blockSignals(True)
                self.w.text_scene_combo.setCurrentIndex(idx)
                self.w.text_scene_combo.blockSignals(False)

        if hasattr(self.w, "reply_mode_combo") and self.w.reply_mode_combo is not None:
            idx = self.w.reply_mode_combo.findData(profile.get("reply_mode", "gentle"))
            if idx >= 0:
                self.w.reply_mode_combo.blockSignals(True)
                self.w.reply_mode_combo.setCurrentIndex(idx)
                self.w.reply_mode_combo.blockSignals(False)

        if hasattr(self.w, "explain_tendency_combo") and self.w.explain_tendency_combo is not None:
            idx = self.w.explain_tendency_combo.findData(profile.get("explain_tendency", "medium"))
            if idx >= 0:
                self.w.explain_tendency_combo.blockSignals(True)
                self.w.explain_tendency_combo.setCurrentIndex(idx)
                self.w.explain_tendency_combo.blockSignals(False)

        if hasattr(self.w, "comfort_tendency_combo") and self.w.comfort_tendency_combo is not None:
            idx = self.w.comfort_tendency_combo.findData(profile.get("comfort_tendency", "medium"))
            if idx >= 0:
                self.w.comfort_tendency_combo.blockSignals(True)
                self.w.comfort_tendency_combo.setCurrentIndex(idx)
                self.w.comfort_tendency_combo.blockSignals(False)

        if hasattr(self.w, "tone_strength_combo") and self.w.tone_strength_combo is not None:
            idx = self.w.tone_strength_combo.findData(profile.get("tone_strength", "medium"))
            if idx >= 0:
                self.w.tone_strength_combo.blockSignals(True)
                self.w.tone_strength_combo.setCurrentIndex(idx)
                self.w.tone_strength_combo.blockSignals(False)

        if hasattr(self.w, "catchphrase_edit") and self.w.catchphrase_edit is not None:
            self.w.catchphrase_edit.blockSignals(True)
            self.w.catchphrase_edit.setPlainText(profile.get("catchphrase", ""))
            self.w.catchphrase_edit.blockSignals(False)

        if hasattr(self.w, "opening_style_edit") and self.w.opening_style_edit is not None:
            self.w.opening_style_edit.blockSignals(True)
            self.w.opening_style_edit.setPlainText(profile.get("opening_style", ""))
            self.w.opening_style_edit.blockSignals(False)

        if hasattr(self.w, "forbidden_edit") and self.w.forbidden_edit is not None:
            self.w.forbidden_edit.blockSignals(True)
            self.w.forbidden_edit.setPlainText(profile.get("forbidden", ""))
            self.w.forbidden_edit.blockSignals(False)