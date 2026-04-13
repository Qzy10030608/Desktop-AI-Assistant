class ControlCenterLogic:
    """
    控制中心联动逻辑层

    作用：
    1. 第一页输出模式与异步语音显隐联动
    2. 第二页文本模板场景梯度规则
    3. 第二页发声模板场景梯度规则
    4. 通用下拉框选项重建与默认值切换
    """

    def __init__(self, window):
        self.w = window

    # =========================================================
    # 第一页：输出模式联动
    # =========================================================
    def update_model_page_mode_visibility(self):
        """
        只在“文字+语音”模式时显示异步语音选项
        """
        if not hasattr(self.w, "output_mode_combo"):
            return
        if not hasattr(self.w, "async_voice_combo"):
            return

        if self.w.output_mode_combo is None or self.w.async_voice_combo is None:
            return

        mode = self.w.output_mode_combo.currentData()
        visible = (mode == "text_voice")

        self.w.async_voice_combo.setVisible(visible)

        if hasattr(self.w, "async_voice_label") and self.w.async_voice_label is not None:
            self.w.async_voice_label.setVisible(visible)

    # =========================================================
    # 通用工具：重建下拉框选项
    # =========================================================
    def rebuild_combo_items(self, combo, items, target_data=None):
        """
        重建下拉框选项：
        items 格式：[("显示文本", data), ...]
        target_data 为希望选中的 data
        """
        if combo is None:
            return

        combo.blockSignals(True)
        combo.clear()

        target_index = 0
        for idx, (text, data) in enumerate(items):
            combo.addItem(text, data)
            if data == target_data:
                target_index = idx

        if combo.count() > 0:
            combo.setCurrentIndex(target_index)

        combo.blockSignals(False)

    def set_combo_data_if_exists(self, combo, data_value):
        """
        如果目标 data 在下拉框中存在，就切换到该选项
        """
        if combo is None:
            return
        idx = combo.findData(data_value)
        if idx >= 0:
            combo.blockSignals(True)
            combo.setCurrentIndex(idx)
            combo.blockSignals(False)

    # =========================================================
    # 第二页：文本模板场景规则
    # 第一层：场景
    # 第二层：允许范围
    # 第三层：默认值
    # =========================================================
    def get_text_scene_rules(self) -> dict:
        return {
            "daily": {
                "options": {
                    "reply_mode": [
                        ("直接", "direct"),
                        ("温和", "gentle"),
                        ("陪伴", "companion"),
                    ],
                    "explain_tendency": [
                        ("低", "low"),
                        ("中", "medium"),
                        ("高", "high"),
                    ],
                    "comfort_tendency": [
                        ("低", "low"),
                        ("中", "medium"),
                        ("高", "high"),
                    ],
                    "tone_strength": [
                        ("弱", "low"),
                        ("中", "medium"),
                        ("强", "high"),
                    ],
                },
                "defaults": {
                    "reply_mode": "gentle",
                    "explain_tendency": "medium",
                    "comfort_tendency": "medium",
                    "tone_strength": "medium",
                },
            },
            "comfort": {
                "options": {
                    "reply_mode": [
                        ("温和", "gentle"),
                        ("陪伴", "companion"),
                    ],
                    "explain_tendency": [
                        ("低", "low"),
                        ("中", "medium"),
                    ],
                    "comfort_tendency": [
                        ("中", "medium"),
                        ("高", "high"),
                    ],
                    "tone_strength": [
                        ("弱", "low"),
                        ("中", "medium"),
                    ],
                },
                "defaults": {
                    "reply_mode": "companion",
                    "explain_tendency": "low",
                    "comfort_tendency": "high",
                    "tone_strength": "medium",
                },
            },
            "explain": {
                "options": {
                    "reply_mode": [
                        ("直接", "direct"),
                        ("温和", "gentle"),
                        ("教学", "teaching"),
                    ],
                    "explain_tendency": [
                        ("中", "medium"),
                        ("高", "high"),
                    ],
                    "comfort_tendency": [
                        ("低", "low"),
                        ("中", "medium"),
                    ],
                    "tone_strength": [
                        ("弱", "low"),
                        ("中", "medium"),
                    ],
                },
                "defaults": {
                    "reply_mode": "teaching",
                    "explain_tendency": "high",
                    "comfort_tendency": "low",
                    "tone_strength": "medium",
                },
            },
            "light": {
                "options": {
                    "reply_mode": [
                        ("直接", "direct"),
                        ("温和", "gentle"),
                    ],
                    "explain_tendency": [
                        ("低", "low"),
                        ("中", "medium"),
                    ],
                    "comfort_tendency": [
                        ("低", "low"),
                        ("中", "medium"),
                    ],
                    "tone_strength": [
                        ("中", "medium"),
                        ("强", "high"),
                    ],
                },
                "defaults": {
                    "reply_mode": "gentle",
                    "explain_tendency": "low",
                    "comfort_tendency": "medium",
                    "tone_strength": "high",
                },
            },
        }

    # =========================================================
    # 第二页：发声模板场景规则
    # =========================================================
    def get_voice_scene_rules(self) -> dict:
        return {
            "daily": {
                "options": {
                    "emotion": [
                        ("冷静", "calm"),
                        ("温和", "gentle"),
                        ("活泼", "lively"),
                    ],
                    "emotion_strength": [
                        ("弱", "low"),
                        ("中", "medium"),
                        ("强", "high"),
                    ],
                    "speed": [
                        ("慢", "slow"),
                        ("中", "normal"),
                        ("快", "fast"),
                    ],
                    "pause": [
                        ("少", "low"),
                        ("中", "medium"),
                        ("多", "high"),
                    ],
                    "intonation": [
                        ("弱", "weak"),
                        ("中", "normal"),
                        ("强", "strong"),
                    ],
                    "emphasis": [
                        ("自然", "natural"),
                        ("关键词", "keyword"),
                        ("句首", "start"),
                    ],
                },
                "defaults": {
                    "emotion": "gentle",
                    "emotion_strength": "medium",
                    "speed": "normal",
                    "pause": "medium",
                    "intonation": "normal",
                    "emphasis": "natural",
                },
            },
            "comfort": {
                "options": {
                    "emotion": [
                        ("冷静", "calm"),
                        ("温和", "gentle"),
                    ],
                    "emotion_strength": [
                        ("弱", "low"),
                        ("中", "medium"),
                    ],
                    "speed": [
                        ("慢", "slow"),
                        ("中", "normal"),
                    ],
                    "pause": [
                        ("中", "medium"),
                        ("多", "high"),
                    ],
                    "intonation": [
                        ("弱", "weak"),
                        ("中", "normal"),
                    ],
                    "emphasis": [
                        ("自然", "natural"),
                    ],
                },
                "defaults": {
                    "emotion": "gentle",
                    "emotion_strength": "medium",
                    "speed": "slow",
                    "pause": "high",
                    "intonation": "weak",
                    "emphasis": "natural",
                },
            },
            "explain": {
                "options": {
                    "emotion": [
                        ("冷静", "calm"),
                        ("温和", "gentle"),
                    ],
                    "emotion_strength": [
                        ("弱", "low"),
                        ("中", "medium"),
                    ],
                    "speed": [
                        ("中", "normal"),
                        ("快", "fast"),
                    ],
                    "pause": [
                        ("少", "low"),
                        ("中", "medium"),
                        ("多", "high"),
                    ],
                    "intonation": [
                        ("弱", "weak"),
                        ("中", "normal"),
                    ],
                    "emphasis": [
                        ("自然", "natural"),
                        ("关键词", "keyword"),
                    ],
                },
                "defaults": {
                    "emotion": "calm",
                    "emotion_strength": "low",
                    "speed": "normal",
                    "pause": "medium",
                    "intonation": "normal",
                    "emphasis": "keyword",
                },
            },
            "light": {
                "options": {
                    "emotion": [
                        ("温和", "gentle"),
                        ("活泼", "lively"),
                    ],
                    "emotion_strength": [
                        ("中", "medium"),
                        ("强", "high"),
                    ],
                    "speed": [
                        ("中", "normal"),
                        ("快", "fast"),
                    ],
                    "pause": [
                        ("少", "low"),
                        ("中", "medium"),
                    ],
                    "intonation": [
                        ("中", "normal"),
                        ("强", "strong"),
                    ],
                    "emphasis": [
                        ("自然", "natural"),
                        ("句首", "start"),
                    ],
                },
                "defaults": {
                    "emotion": "lively",
                    "emotion_strength": "high",
                    "speed": "fast",
                    "pause": "low",
                    "intonation": "strong",
                    "emphasis": "start",
                },
            },
        }

    # =========================================================
    # 第二页：文本模板场景变化
    # =========================================================
    def on_text_scene_changed(self):
        """
        文本模板场景联动：
        1. 根据场景限制可选项
        2. 套用该场景默认值
        """
        if self.w._loading:
            return

        scene = self.w.text_scene_combo.currentData() if hasattr(self.w, "text_scene_combo") else "daily"
        rules = self.get_text_scene_rules()
        rule = rules.get(scene, rules["daily"])

        options = rule["options"]
        defaults = rule["defaults"]

        self.rebuild_combo_items(self.w.reply_mode_combo, options["reply_mode"], defaults["reply_mode"])
        self.rebuild_combo_items(self.w.explain_tendency_combo, options["explain_tendency"], defaults["explain_tendency"])
        self.rebuild_combo_items(self.w.comfort_tendency_combo, options["comfort_tendency"], defaults["comfort_tendency"])
        self.rebuild_combo_items(self.w.tone_strength_combo, options["tone_strength"], defaults["tone_strength"])

        self.w.refresh_dirty("style")

    # =========================================================
    # 第二页：发声模板场景变化
    # =========================================================
    def on_voice_scene_changed(self):
        """
        发声模板场景联动：
        1. 根据场景限制可选项
        2. 套用该场景默认值
        """
        if self.w._loading:
            return

        scene = self.w.scene_combo.currentData() if hasattr(self.w, "scene_combo") else "daily"
        rules = self.get_voice_scene_rules()
        rule = rules.get(scene, rules["daily"])

        options = rule["options"]
        defaults = rule["defaults"]

        self.rebuild_combo_items(self.w.emotion_combo, options["emotion"], defaults["emotion"])
        self.rebuild_combo_items(self.w.emotion_strength_combo, options["emotion_strength"], defaults["emotion_strength"])
        self.rebuild_combo_items(self.w.speed_combo, options["speed"], defaults["speed"])
        self.rebuild_combo_items(self.w.pause_combo, options["pause"], defaults["pause"])
        self.rebuild_combo_items(self.w.intonation_combo, options["intonation"], defaults["intonation"])
        self.rebuild_combo_items(self.w.emphasis_combo, options["emphasis"], defaults["emphasis"])

        self.w.refresh_dirty("style")

    # =========================================================
    # 第二页：初始化默认场景
    # =========================================================
    def initialize_style_scene_defaults(self):
        """
        页面初次加载后，按默认场景做一次梯度初始化
        """
        if hasattr(self.w, "text_scene_combo") and self.w.text_scene_combo is not None:
            self.on_text_scene_changed()

        if hasattr(self.w, "scene_combo") and self.w.scene_combo is not None:
            self.on_voice_scene_changed()