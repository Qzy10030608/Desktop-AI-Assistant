from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional, Dict, Tuple
import re


@dataclass
class ReplyPackage:
    raw_text: str = ""
    visible_text: str = ""
    tts_text: str = ""
    is_draft_leaked: bool = False
    is_repaired: bool = False


class ReplyPostprocessService:
    HARD_DRAFT_MARKERS = [
        "内部控制信息",
        "输出协议",
        "ROLE_NAME",
        "STYLE_TEMPLATE",
        "ROLE_CORE",
        "ROLE_PERSONA",
        "ROLE_REPLY_RULES",
        "name=",
        "reply_mode=",
        "catchphrase=",
        "opening_style=",
        "forbidden=",
        "style_rules=",
    ]

    NATURAL_DRAFT_PREFIXES = (
        "首先，用户的问题是",
        "首先，用户问的是",
        "我需要以",
        "我需要用",
        "我应该以",
        "我应该用",
        "关键点：",
        "在中文中",
        "我的角色是",
        "我是“",
        "我是「",
        "我是默认角色",
        "提示中",
        "提示说",
        "提示要求",
        "用户的问题是",
        "用户问的是",
        "用户问了",
        "所以我得",
        "所以我要",
        "所以我应该",
        "因此我应该",
        "作为教学风格",
        "作为",
        "我需要根据",
        "我需要先",
        "我应该先",
        "下面根据",
        "先回答风格",
        "最终输出格式要求",
        "回复要求",
        "角色设定参考",
        "当前风格偏好",
        "当前临时语气偏好",
        "口头表达可轻微参考",
        "以下表达尽量避免",
        "长度：",
        "检查是否自然：",
        "适合语音：",
        "不要过长：",
        "确认：",
        "输出必须是纯文本",
        "避免任何其他内容：",
        "完整回复：",
        "最终输出：",
        "直接输出：",
    )

    NATURAL_DRAFT_CONTAINS = (
        "提示中没有指定",
        "这是中文的",
        "意思是",
        "表示谦逊",
        "所以可以",
        "回复要自然",
        "适合后续语音播放",
        "不要过长",
        "不要解释",
        "不要分析",
        "不要复述规则",
        "只输出最终回复正文",
        "用户可见回复",
        "最终回复正文",
        "回复风格：",
        "开头偏好：",
        "可轻微参考口头禅：",
        "避免表达：",
        "只输出回复正文",
        "不要加标签",
        "不要加任何解释",
        "不要复述提示词",
        "像真人说话",
    )

    USER_DIRECT_PATTERNS = [
        r"^你好[呀啊，,！!]*",
        r"^你可以叫我",
        r"^我叫",
        r"^我是",
        r"^你可以叫",
        r"^很高兴",
        r"^当然",
        r"^可以呀",
        r"^可以哦",
        r"^没问题",
        r"^这题",
        r"^这个问题",
        r"^简单说",
        r"^比如",
        r"^亲，",
        r"^奴家觉得",
    ]

    def _safe(self, text: str) -> str:
        return (text or "").strip()

    def _looks_like_internal_draft(self, text: str) -> bool:
        s = self._safe(text)
        if not s:
            return True
        return any(m in s for m in self.HARD_DRAFT_MARKERS)

    def _remove_tag_blocks(self, text: str) -> str:
        cleaned = re.sub(
            r"</?(thinking|think|analysis|final_reply)>",
            "",
            text or "",
            flags=re.IGNORECASE,
        )
        return cleaned.strip()

    def _extract_final_reply_tag(self, text: str) -> str:
        raw = self._safe(text)
        if not raw:
            return ""

        match = re.search(
            r"<final_reply>\s*(.*?)\s*</final_reply>",
            raw,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if match:
            return match.group(1).strip()

        return ""

    def _extract_by_explicit_marker(self, text: str) -> str:
        cleaned = self._safe(text)
        if not cleaned:
            return ""

        explicit_markers = [
            "最终输出：", "最终输出:",
            "直接输出：", "直接输出:",
            "完整回复：", "完整回复:",
            "最终回复：", "最终回复:",
            "最终回答：", "最终回答:",
            "回复正文：", "回复正文:",
            "用户可见回复：", "用户可见回复:",
        ]

        best_tail = ""
        best_pos = -1
        for marker in explicit_markers:
            pos = cleaned.rfind(marker)
            if pos > best_pos:
                tail = cleaned[pos + len(marker):].strip()
                if tail:
                    best_pos = pos
                    best_tail = tail

        if best_tail:
            first_line = best_tail.splitlines()[0].strip()
            return first_line or best_tail

        return cleaned

    def _is_natural_draft_line(self, s: str) -> bool:
        s = self._safe(s)
        if not s:
            return True

        if any(m in s for m in self.HARD_DRAFT_MARKERS):
            return True
        if s.startswith(self.NATURAL_DRAFT_PREFIXES):
            return True
        if any(key in s for key in self.NATURAL_DRAFT_CONTAINS):
            return True
        if re.match(r"^\d+\.", s):
            return True
        if re.match(r"^-\s*", s):
            return True
        if s.endswith("我应该：") or s.endswith("所以我应该："):
            return True
        if any(key in s for key in [
            "我需要以", "我需要用", "风格是", "关键点：", "在中文中",
            "作为教学风格的角色", "我应该直接回答", "检查是否自然",
            "适合语音", "不要过长", "完美。"
        ]):
            return True

        return False

    def _split_candidate_lines(self, text: str) -> list[str]:
        parts: list[str] = []
        for block in self._safe(text).splitlines():
            block = block.strip()
            if not block:
                continue

            sub_parts = re.split(r"(?<=[。！？!?；;])", block)
            for item in sub_parts:
                item = item.strip()
                if item:
                    parts.append(item)

        return parts

    def _pick_user_visible_lines(self, lines: list[str]) -> list[str]:
        visible: list[str] = []

        for s in lines:
            if self._is_natural_draft_line(s):
                continue
            visible.append(s)

        if visible:
            return visible

        fallback: list[str] = []
        for s in lines:
            if len(s) < 3:
                continue
            if any(re.match(p, s) for p in self.USER_DIRECT_PATTERNS):
                fallback.append(s)
                continue
            if "你" in s or "我们" in s or "吧" in s or "呀" in s or "哦" in s or "等于" in s:
                fallback.append(s)

        return fallback

    def sanitize_visible_reply(self, text: str) -> str:
        raw = self._safe(text)
        if not raw:
            return ""

        tagged = self._extract_final_reply_tag(raw)
        if tagged:
            return tagged.strip()

        # 先去掉 think 标签
        cleaned = self._remove_tag_blocks(raw)

        # 明确标记抽取
        explicit = self._extract_by_explicit_marker(cleaned)
        if explicit and not self._is_natural_draft_line(explicit):
            return explicit.strip()

        # 最后才做旧式删除清理
        lines = self._split_candidate_lines(cleaned)
        visible_lines = self._pick_user_visible_lines(lines)

        result = "".join(visible_lines).strip()

        if self._looks_like_internal_draft(result):
            return ""
        if self._is_natural_draft_line(result):
            return ""

        return result

    def repair_visible_reply_with_llm(
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
        repair_prompt = (
            "你是最终回复整理器。"
            "我会给你一段后台草稿，其中混有角色说明、回复规则、分析过程。"
            "你只能输出用户最终会看到的一句自然中文回复。"
            "禁止输出任何过程说明。"
            "禁止输出“用户的问题是”“我需要以”“风格是”“关键点”“在中文中”“我应该直接回答”这类句子。"
            "只输出最终答案正文。"
        )

        repair_input = (
            f"用户问题：{self._safe(user_text)}\n\n"
            f"后台草稿：\n{self._safe(raw_ai_text)}\n\n"
            "请直接输出最终给用户看的回复："
        )

        try:
            repaired = chat_callable(
                repair_input,
                history=[],
                model_name=model_name,
                system_prompt=repair_prompt,
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

    def build_package(
        self,
        *,
        user_text: str,
        raw_ai_text: str,
        chat_callable: Optional[Callable[..., str]] = None,
        model_name: str = "",
        host: str = "",
        timeout: Tuple[int, int] = (10, 300),
    ) -> ReplyPackage:
        raw_text = self._safe(raw_ai_text)
        visible_text = self.sanitize_visible_reply(raw_text)
        is_repaired = False

        needs_repair = (
            not visible_text
            or self._looks_like_internal_draft(raw_text)
            or self._is_natural_draft_line(visible_text)
        )

        if needs_repair and chat_callable is not None:
            repaired = self.repair_visible_reply_with_llm(
                user_text=user_text,
                raw_ai_text=raw_text,
                chat_callable=chat_callable,
                model_name=model_name,
                host=host,
                timeout=timeout,
            )
            visible_text = self.sanitize_visible_reply(repaired)
            is_repaired = bool(visible_text)

        if not visible_text:
            visible_text = "抱歉，当前没有成功提取到最终回复。"

        return ReplyPackage(
            raw_text=raw_text,
            visible_text=visible_text,
            tts_text=visible_text,
            is_draft_leaked=self._looks_like_internal_draft(raw_text),
            is_repaired=is_repaired,
        )