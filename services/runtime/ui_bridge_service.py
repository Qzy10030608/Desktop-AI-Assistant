from __future__ import annotations

from typing import Any


class UIBridgeService:
    """
    UI 桥接服务
    -------------------------
    负责把 service 层状态翻译成主窗口显示。
    当前先提供：
    - 顶部运行摘要同步
    - 输出模式切换摘要
    """

    def __init__(self, controller: Any):
        self.c = controller

    def sync_runtime_state_to_main_window(self):
        role_meta = self.c.role_service.get_current_role_meta()
        current_model = self.c.model_router_service.get_current_chat_model()
        current_style = self.c.style_profile_service.get_current_style_profile()
        current_voice = self.c.voice_profile_service.get_current_voice_profile()

        tts_backend = self.c.voice_profile_service.get_current_tts_backend()
        tts_backend_name = {
            "edge": "Edge-TTS",
            "gpt_sovits": "GPT-SoVITS",
        }.get(tts_backend, tts_backend or "-")

        current_package = self.c.tts_package_service.get_current_package(tts_backend)
        current_package_name = current_package.get("name", current_package.get("id", "-"))

        output_mode_name = self.c.output_mode_service.get_mode_name(self.c.current_output_mode)
        provider_name = self.c.model_router_service.get_provider_display_name(
            current_model.get("provider", "ollama")
        )
        model_display_name = current_model.get("name") or current_model.get("model_name", "-")
        if not bool(current_model.get("available", False)):
            model_display_name = f"{model_display_name} [不可用]"
        model_display_name = f"{provider_name} / {model_display_name}"

        summary = (
            f"当前角色：{role_meta.get('name', '-')} | "
            f"语言模型：{model_display_name} | "
            f"语音后端：{tts_backend_name} | "
            f"语音包：{current_package_name} | "
            f"文本模板：{current_style.get('name', current_style.get('id', '-'))} | "
            f"表现模板：{current_voice.get('name', current_voice.get('id', '-'))} | "
            f"输出：{output_mode_name}"
        )

        self.c.window.set_output_mode(self.c.current_output_mode)
        self.c.window.set_runtime_state_summary(summary)

    def handle_output_mode_changed(self, mode: str):
        self.c.current_output_mode = mode
        patched = self.c.output_mode_service.patch_summary_output(
            self.c.window.current_state_summary,
            mode,
        )

        if patched != self.c.window.current_state_summary:
            self.c.window.set_runtime_state_summary(patched)
        else:
            self.c.window.set_status(
                f"输出模式已切换为：{self.c.output_mode_service.get_mode_name(mode)}"
            )