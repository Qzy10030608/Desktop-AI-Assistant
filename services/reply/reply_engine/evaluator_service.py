from __future__ import annotations

from typing import Dict, Any
import re


class EvaluatorService:
    DRAFT_MARKERS = [
        "首先，用户的问题是",
        "用户的问题是",
        "用户问的是",
        "我需要以",
        "我需要用",
        "我需要根据",
        "我应该以",
        "我应该用",
        "我应该先",
        "因此我应该",
        "所以我应该",
        "所以我得",
        "关键点：",
        "在中文中",
        "意思是",
        "表示",
        "风格是",
        "开头偏好是",
        "可以参考口头禅",
        "避免表达",
        "适合后续语音播放",
        "回复要求",
        "角色设定参考",
        "当前风格偏好",
        "当前临时语气偏好",
        "最终输出格式要求",
        "内部控制信息",
        "输出协议",
        "ROLE_NAME",
        "STYLE_TEMPLATE",
        "检查是否自然",
        "适合语音",
        "不要过长",
        "完整回复：",
        "最终输出：",
        "直接输出：",
    ]

    def _safe_text(self, text: str) -> str:
        return (text or "").strip()

    def _looks_like_draft(self, text: str) -> bool:
        s = self._safe_text(text)
        if not s:
            return True
        return any(marker in s for marker in self.DRAFT_MARKERS)

    def _is_too_short(self, text: str) -> bool:
        s = self._safe_text(text)
        return len(s) < 4

    def _is_incomplete(self, text: str) -> bool:
        s = self._safe_text(text)
        if not s:
            return True

        bad_tails = (
            "我应该以",
            "我需要以",
            "然后：",
            "比如：",
            "开头：",
            "关键点：",
            "所以：",
            "因此：",
            "例如：",
            "答：",
            "说：",
            "完整回复：",
            "最终输出：",
            "直接输出：",
        )
        if s.endswith(bad_tails):
            return True

        if re.search(r"(我应该|我需要|用户问|关键点|完整回复|最终输出|直接输出)[:：]?$", s):
            return True

        return False

    def _looks_like_answer(self, user_text: str, text: str) -> bool:
        s = self._safe_text(text)
        if not s:
            return False

        user_text = self._safe_text(user_text)

        if any(ch in s for ch in ["。", "！", "？", "，", ","]):
            return True

        if any(key in s for key in ["等于", "叫我", "我是", "可以叫我", "觉得"]):
            return True

        if user_text and any(ch in user_text for ch in ["多少", "什么", "谁", "名字"]):
            if len(s) >= 4:
                return True

        return False

    def evaluate(self, *, user_text: str, raw_text: str, candidate_text: str) -> Dict[str, Any]:
        raw = self._safe_text(raw_text)
        candidate = self._safe_text(candidate_text)

        raw_looks_like_draft = self._looks_like_draft(raw)
        candidate_looks_like_draft = self._looks_like_draft(candidate)

        looks_like_draft = candidate_looks_like_draft
        too_short = self._is_too_short(candidate)
        incomplete = self._is_incomplete(candidate)
        looks_like_answer = self._looks_like_answer(user_text, candidate)

        can_use_directly = bool(candidate) and (not looks_like_draft) and (not incomplete) and looks_like_answer

        confidence = 0.15
        if candidate:
            confidence += 0.25
        if not looks_like_draft:
            confidence += 0.25
        if not too_short:
            confidence += 0.15
        if not incomplete:
            confidence += 0.1
        if looks_like_answer:
            confidence += 0.1

        confidence = max(0.0, min(confidence, 1.0))

        return {
            "raw_text": raw,
            "candidate_text": candidate,
            "raw_looks_like_draft": raw_looks_like_draft,
            "looks_like_draft": looks_like_draft,
            "too_short": too_short,
            "incomplete": incomplete,
            "looks_like_answer": looks_like_answer,
            "can_use_directly": can_use_directly,
            "needs_repair": not can_use_directly,
            "confidence": confidence,
        }