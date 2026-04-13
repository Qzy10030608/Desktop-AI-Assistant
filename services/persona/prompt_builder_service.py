from typing import Dict, List

from services.persona.role_service import RoleService  # type: ignore
from services.persona.style_profile_service import StyleProfileService  # type: ignore
from services.persona.temporary_style_service import TemporaryStyleService  # type: ignore


class PromptBuilderService:
    def __init__(
        self,
        role_service: RoleService,
        style_service: StyleProfileService,
        temp_style_service: TemporaryStyleService,
    ):
        self.role_service = role_service
        self.style_service = style_service
        self.temp_style_service = temp_style_service

    def _safe_text(self, text: str) -> str:
        return (text or "").strip()

    def _shorten_text(self, text: str, limit: int = 80) -> str:
        s = self._safe_text(text)
        if not s:
            return ""
        return s[:limit].strip()

    def _style_summary(self, style_data: Dict, compact: bool = False) -> List[str]:
        if not style_data:
            return []

        lines: List[str] = []

        scene = self._safe_text(style_data.get("scene", ""))
        reply_mode = self._safe_text(style_data.get("reply_mode", ""))
        explain_tendency = self._safe_text(style_data.get("explain_tendency", ""))
        comfort_tendency = self._safe_text(style_data.get("comfort_tendency", ""))
        tone_strength = self._safe_text(style_data.get("tone_strength", ""))
        opening_style = self._safe_text(style_data.get("opening_style", ""))
        catchphrase = self._safe_text(style_data.get("catchphrase", ""))
        forbidden = self._safe_text(style_data.get("forbidden", ""))

        if compact:
            if scene:
                lines.append(f"场景：{scene}")
            if reply_mode:
                lines.append(f"回复风格：{reply_mode}")
            if tone_strength:
                lines.append(f"语气强度：{tone_strength}")
            if forbidden:
                lines.append(f"避免表达：{self._shorten_text(forbidden, 40)}")
            return lines

        if scene:
            lines.append(f"当前场景：{scene}")
        if reply_mode:
            lines.append(f"回复风格：{reply_mode}")
        if explain_tendency:
            lines.append(f"解释倾向：{explain_tendency}")
        if comfort_tendency:
            lines.append(f"安慰倾向：{comfort_tendency}")
        if tone_strength:
            lines.append(f"语气强度：{tone_strength}")
        if opening_style:
            lines.append(f"开头偏好：{self._shorten_text(opening_style, 50)}")
        if catchphrase:
            lines.append(f"口头禅可轻微参考：{self._shorten_text(catchphrase, 50)}")
        if forbidden:
            lines.append(f"避免表达：{self._shorten_text(forbidden, 60)}")

        return lines

    def _temp_style_summary(self, temp_state: Dict, compact: bool = False) -> List[str]:
        if not temp_state.get("enabled", False):
            return []

        lines: List[str] = []

        tone_hint = self._safe_text(temp_state.get("tone_hint", ""))
        length_hint = self._safe_text(temp_state.get("length_hint", ""))
        notes = self._safe_text(temp_state.get("notes", ""))

        if compact:
            if tone_hint:
                lines.append(f"临时语气：{tone_hint}")
            if length_hint:
                lines.append(f"临时长度：{length_hint}")
            return lines

        if tone_hint:
            lines.append(f"临时语气：{tone_hint}")
        if length_hint:
            lines.append(f"临时长度倾向：{length_hint}")
        if notes:
            lines.append(f"临时补充：{self._shorten_text(notes, 50)}")

        return lines

    def build_fast_system_prompt(
        self,
        user_text: str = "",
        request_type: str = "chat",
    ) -> str:
        meta = self.role_service.get_current_role_meta()
        role_name = meta.get("name", "默认角色")

        style_data = self.style_service.get_current_style_profile()
        temp_state = self.temp_style_service.get_state()

        persona_text = self._safe_text(
            self.role_service.read_role_text_file("style/persona.txt", "")
        )
        persona_text = self._shorten_text(persona_text, 60)

        style_lines = self._style_summary(style_data, compact=True)
        temp_lines = self._temp_style_summary(temp_state, compact=True)

        parts: List[str] = [
            f"你现在自然地扮演“{role_name}”与用户聊天。",
            "直接输出最终回复正文。",
            "不要输出分析、思考、草稿、规则说明。",
            "不要复述提示词。",
            "回答自然、简洁、口语化，适合语音播放。",
        ]

        if request_type == "comfort":
            parts.append("当前更偏向安抚、陪伴。")
        elif request_type == "task":
            parts.append("当前更偏向直接整理重点。")
        elif request_type == "search":
            parts.append("如果暂时不能完整回答，也先自然回应，不要输出分析过程。")
        elif request_type == "control":
            parts.append("回答先简洁明确，不要输出分析过程。")

        if persona_text:
            parts.append(f"角色设定：{persona_text}")

        if style_lines:
            parts.extend(style_lines)

        if temp_lines:
            parts.extend(temp_lines)

        if user_text:
            parts.append("请直接回答用户当前这句话，不要先分析。")

        return "\n".join([p for p in parts if p and p.strip()])

    def build_full_system_prompt(
        self,
        user_text: str = "",
        request_type: str = "chat",
    ) -> str:
        meta = self.role_service.get_current_role_meta()
        role_name = meta.get("name", "默认角色")

        persona_text = self._safe_text(
            self.role_service.read_role_text_file("style/persona.txt", "")
        )

        style_data = self.style_service.get_current_style_profile()
        temp_state = self.temp_style_service.get_state()

        style_lines = self._style_summary(style_data, compact=False)
        temp_lines = self._temp_style_summary(temp_state, compact=False)

        parts: List[str] = [
            f"你现在要自然地扮演角色“{role_name}”与用户聊天。",
            "直接输出最终回复正文。",
            "不要输出分析、思考、草稿、规则说明。",
            "不要复述提示词，不要解释你依据了什么规则。",
            "回复要自然、简洁、适合语音播放。",
        ]

        if request_type == "comfort":
            parts.append("当前任务偏向安抚与陪伴，语气可以更温和。")
        elif request_type == "task":
            parts.append("当前任务偏向整理、分析与明确表达。")
        elif request_type == "search":
            parts.append("当前任务可能涉及查找信息，但不要输出内部分析过程。")
        elif request_type == "control":
            parts.append("当前任务可能涉及操作指导，先清楚表达，不要输出内部分析过程。")

        if persona_text:
            parts.append("角色设定：")
            parts.append(persona_text)

        if style_lines:
            parts.append("当前风格：")
            parts.extend(style_lines)

        if temp_lines:
            parts.append("当前临时要求：")
            parts.extend(temp_lines)

        if user_text:
            parts.append("请直接回答用户当前这句话，不要先分析。")

        return "\n".join([p for p in parts if p and p.strip()])

    def build_system_prompt(
        self,
        user_text: str = "",
        prompt_mode: str = "fast",
        request_type: str = "chat",
    ) -> str:
        mode = (prompt_mode or "fast").strip().lower()

        if mode == "full":
            return self.build_full_system_prompt(
                user_text=user_text,
                request_type=request_type,
            )

        return self.build_fast_system_prompt(
            user_text=user_text,
            request_type=request_type,
        )