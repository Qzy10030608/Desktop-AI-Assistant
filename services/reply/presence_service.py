from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


@dataclass
class PresencePlan:
    enabled: bool
    text: str
    speak: bool = False
    temporary: bool = True


class PresenceService:
    """
    互动层：
    不做深推理，只负责给用户一个很快的“在场回应”。
    """

    DEFAULT_TEXTS: Dict[str, str] = {
        "chat": "我在。",
        "comfort": "我在，你慢慢说。",
        "search": "我先帮你查一下。",
        "control": "我先帮你看看怎么操作。",
        "task": "我先帮你整理一下。",
    }

    ROLE_SOFT_TEXTS: Dict[str, str] = {
        "chat": "我在，和你说。",
        "comfort": "我在，别急，我陪你。",
        "search": "这个我先帮你查一下。",
        "control": "这个我先帮你处理看看。",
        "task": "这个我先帮你整理一下。",
    }

    def build_presence_plan(
        self,
        *,
        request_type: str,
        role_name: str = "",
        output_mode: str = "text_voice",
        enabled: bool = True,
    ) -> PresencePlan:
        if not enabled:
            return PresencePlan(enabled=False, text="")

        request_type = (request_type or "chat").strip().lower()
        role_name = (role_name or "").strip()

        if role_name:
            text = self.ROLE_SOFT_TEXTS.get(request_type, "我先看看。")
        else:
            text = self.DEFAULT_TEXTS.get(request_type, "我先看看。")

        # 第一轮先只做文本 presence，不走语音
        return PresencePlan(
            enabled=True,
            text=text,
            speak=False,
            temporary=True,
        )