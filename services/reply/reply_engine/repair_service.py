from __future__ import annotations

from typing import Callable, Optional, Dict, Any, Tuple


class RepairService:
    def build_repair_prompt(self) -> str:
        return (
            "你是最终回复整理器。"
            "我会给你一段后台草稿，其中混有角色说明、回复规则、分析过程。"
            "你只能输出用户最终会看到的一句或一小段自然中文回复。"
            "禁止输出任何过程说明。"
            "禁止输出“用户的问题是”“我需要以”“风格是”“关键点”“在中文中”“我应该直接回答”这类句子。"
            "只输出最终答案正文。"
        )

    def build_repair_input(self, user_text: str, raw_ai_text: str) -> str:
        return (
            f"用户问题：{(user_text or '').strip()}\n\n"
            f"后台草稿：\n{(raw_ai_text or '').strip()}\n\n"
            "请直接输出最终给用户看的回复："
        )

    def repair_with_llm(
        self,
        *,
        user_text: str,
        raw_ai_text: str,
        chat_callable: Callable[..., str],
        model_name: str,
        host: str,
        timeout: Tuple[int, int],
        request_options: Optional[Dict[str, Any]] = None,
    ) -> str:
        prompt = self.build_repair_prompt()
        repair_input = self.build_repair_input(user_text, raw_ai_text)

        try:
            repaired = chat_callable(
                repair_input,
                history=[],
                model_name=model_name,
                system_prompt=prompt,
                host=host,
                timeout=timeout,
                request_options=request_options or {
                    "num_ctx": 1024,
                    "num_predict": -1,
                    "temperature": 0.2,
                    "top_p": 0.8,
                },
            )
            return (repaired or "").strip()
        except Exception:
            return ""