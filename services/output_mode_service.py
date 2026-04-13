from __future__ import annotations

from dataclasses import dataclass


@dataclass
class OutputPlan:
    mode: str
    mode_name: str
    status_text: str
    display_text: str
    tts_text: str
    append_text_message: bool
    append_audio_message: bool
    need_tts: bool


class OutputModeService:
    MODE_NAME_MAP = {
        "text_only": "仅文字",
        "text_voice": "文字+语音",
        "voice_only": "仅语音",
    }

    def get_mode_name(self, mode: str) -> str:
        return self.MODE_NAME_MAP.get(mode, "文字+语音")

    def patch_summary_output(self, summary_text: str, mode: str) -> str:
        output_mode_name = self.get_mode_name(mode)
        current_text = summary_text or ""

        if "输出：" in current_text:
            prefix = current_text.split("输出：")[0]
            return prefix + f"输出：{output_mode_name}"

        return current_text

    def build_output_plan(
        self,
        *,
        mode: str,
        visible_text: str,
        tts_text: str,
        elapsed_text: str = "",
    ) -> OutputPlan:
        mode_name = self.get_mode_name(mode)
        final_tts_text = (tts_text or visible_text).strip()
        final_visible_text = visible_text.strip()

        display_text = final_visible_text
        if elapsed_text:
            display_text = f"{final_visible_text}\n{elapsed_text}"

        if mode == "text_only":
            return OutputPlan(
                mode=mode,
                mode_name=mode_name,
                status_text="AI 文字回复完成",
                display_text=display_text,
                tts_text="",
                append_text_message=True,
                append_audio_message=False,
                need_tts=False,
            )

        if mode == "voice_only":
            voice_only_text = "（仅语音模式）"
            if elapsed_text:
                voice_only_text += f"\n{elapsed_text}"

            return OutputPlan(
                mode=mode,
                mode_name=mode_name,
                status_text="AI 回复完成，正在生成语音...",
                display_text=voice_only_text,
                tts_text=final_tts_text,
                append_text_message=False,
                append_audio_message=True,
                need_tts=True,
            )

        return OutputPlan(
            mode="text_voice",
            mode_name="文字+语音",
            status_text="AI 文字回复完成，正在后台生成语音...",
            display_text=display_text,
            tts_text=final_tts_text,
            append_text_message=False,
            append_audio_message=True,
            need_tts=True,
        )