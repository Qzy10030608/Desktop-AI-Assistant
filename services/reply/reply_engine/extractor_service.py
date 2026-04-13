from __future__ import annotations

from typing import Dict, Any, Callable, Optional, Tuple
import re

from .envelope import ReplyEnvelope
from .legacy_cleanup_service import ReplyPostprocessService
from .repair_service import RepairService # type: ignore


class ExtractorService:
    def __init__(self):
        self.legacy_cleanup = ReplyPostprocessService()
        self.repair_service = RepairService()

    # =========================
    # 基础清洗
    # =========================
    def _clean_text(self, text: str) -> str:
        s = (text or "").strip()
        if not s:
            return ""
        s = s.replace("\r\n", "\n").replace("\r", "\n")
        return s.strip()

    def _normalize_answer_text(self, text: str) -> str:
        s = self._clean_text(text)
        if not s:
            return ""

        s = s.strip(" \n\t\"'“”‘’")
        s = re.sub(r"^(最终输出[:：]|直接输出[:：]|完整回复[:：]|最终回复[:：])\s*", "", s)
        s = s.strip(" \n\t\"'“”‘’")

        # 去掉前导分析类提示
        bad_prefixes = [
            "既然是“教学”",
            "长度：",
            "避免任何其他内容：",
            "输出必须是纯文本",
            "确认：",
            "检查是否自然：",
            "适合语音：",
            "不要过长：",
            "完美。",
        ]
        for prefix in bad_prefixes:
            if s.startswith(prefix):
                return ""

        # 补句号
        if s and s[-1] not in "。！？!?":
            s += "。"

        return s

    # =========================
    # 强抽取逻辑
    # =========================
    def _extract_after_think_block(self, raw_text: str) -> str:
        raw = self._clean_text(raw_text)
        if not raw:
            return ""

        # 优先取 </think> 后面的正文
        m = re.search(r"</think>\s*(.+)$", raw, flags=re.IGNORECASE | re.DOTALL)
        if m:
            tail = self._clean_text(m.group(1))
            if tail:
                return self._normalize_answer_text(tail)

        # 兼容 <think> ... </think> 中被包裹的情况
        m2 = re.search(r"</?(?:think|thinking)>", raw, flags=re.IGNORECASE)
        if m2:
            tail = self._clean_text(raw[m2.end():])
            if tail:
                return self._normalize_answer_text(tail)

        return ""

    def _extract_after_final_markers(self, raw_text: str) -> str:
        raw = self._clean_text(raw_text)
        if not raw:
            return ""

        markers = [
            "最终输出：",
            "最终输出:",
            "直接输出：",
            "直接输出:",
            "完整回复：",
            "完整回复:",
            "最终回复：",
            "最终回复:",
            "回复正文：",
            "回复正文:",
            "用户可见回复：",
            "用户可见回复:",
        ]

        best = ""
        best_pos = -1

        for marker in markers:
            pos = raw.rfind(marker)
            if pos > best_pos:
                best_pos = pos
                best = marker

        if best_pos >= 0:
            tail = raw[best_pos + len(best):].strip()
            if tail:
                first_line = tail.splitlines()[0].strip()
                if first_line:
                    return self._normalize_answer_text(first_line)

        return ""

    def _extract_quoted_candidate_answer(self, raw_text: str) -> str:
        raw = self._clean_text(raw_text)
        if not raw:
            return ""

        # 优先找包含“等于/我是/可以叫我”等内容的最后一个引号句
        quoted = re.findall(r"[“\"]([^”\"\n]{2,80})[”\"]", raw)
        if not quoted:
            return ""

        preferred = []
        for q in quoted:
            q = q.strip()
            if any(key in q for key in ["等于", "我是", "可以叫我", "你好", "觉得"]):
                preferred.append(q)

        if preferred:
            return self._normalize_answer_text(preferred[-1])

        return self._normalize_answer_text(quoted[-1])

    def _extract_last_complete_sentence(self, raw_text: str) -> str:
        raw = self._clean_text(raw_text)
        if not raw:
            return ""

        # 去掉 think 块前面的大段，只保留最后部分参与抽取
        if "</think>" in raw.lower():
            ans = self._extract_after_think_block(raw)
            if ans:
                return ans

        # 取所有完整句子，优先最后一句像答案的
        sentences = re.findall(r"[^。！？!?]+[。！？!?]", raw)
        if not sentences:
            return ""

        candidates = []
        for s in sentences:
            s = self._clean_text(s)
            if not s:
                continue
            if any(marker in s for marker in [
                "用户的问题是", "我需要", "我应该", "关键点", "检查是否", "适合语音",
                "不要过长", "输出必须", "确认：", "风格偏好", "回复风格"
            ]):
                continue
            if any(key in s for key in ["等于", "我是", "可以叫我", "你好", "觉得"]):
                candidates.append(s)

        if candidates:
            return self._normalize_answer_text(candidates[-1])

        # 再退一步，取最后一个完整句
        return self._normalize_answer_text(sentences[-1])

    def extract_final_answer_from_raw(self, raw_text: str) -> str:
        raw = self._clean_text(raw_text)
        if not raw:
            return ""

        # 1. think 后正文
        ans = self._extract_after_think_block(raw)
        if ans:
            return ans

        # 2. 明确标记后的正文
        ans = self._extract_after_final_markers(raw)
        if ans:
            return ans

        # 3. 引号中的候选答案
        ans = self._extract_quoted_candidate_answer(raw)
        if ans:
            return ans

        # 4. 最后一个完整中文句
        ans = self._extract_last_complete_sentence(raw)
        if ans:
            return ans

        # 5. 最后 fallback 到旧清理器
        ans = self.legacy_cleanup.sanitize_visible_reply(raw)
        if ans:
            return self._normalize_answer_text(ans)

        return ""

    # =========================
    # 外部接口
    # =========================
    def extract_from_structured_json(
        self,
        *,
        raw_text: str,
        parsed_data: Dict[str, Any],
        source_type: str,
        model_key: str,
    ) -> ReplyEnvelope:
        final_text = str(parsed_data.get("final_answer", "")).strip()
        thinking_text = str(parsed_data.get("thinking_summary", "")).strip()
        final_text = self._normalize_answer_text(final_text)

        return ReplyEnvelope(
            raw_text=self._clean_text(raw_text),
            thinking_text=self._clean_text(thinking_text),
            final_text=final_text,
            display_text=final_text,
            tts_text=final_text,
            source_type=source_type,
            model_key=model_key,
            strategy_used="structured_json",
            confidence=0.95 if final_text else 0.1,
            needs_repair=not bool(final_text),
            debug_notes="structured_json",
        )

    def extract_from_thinking_split(
        self,
        *,
        raw_text: str,
        thinking_text: str,
        content_text: str,
        source_type: str,
        model_key: str,
    ) -> ReplyEnvelope:
        final_text = self._normalize_answer_text(content_text)

        return ReplyEnvelope(
            raw_text=self._clean_text(raw_text),
            thinking_text=self._clean_text(thinking_text),
            final_text=final_text,
            display_text=final_text,
            tts_text=final_text,
            source_type=source_type,
            model_key=model_key,
            strategy_used="thinking_split",
            confidence=0.9 if final_text else 0.1,
            needs_repair=not bool(final_text),
            debug_notes="thinking_split",
        )

    def extract_by_raw_priority(
        self,
        *,
        user_text: str,
        raw_text: str,
        source_type: str,
        model_key: str,
    ) -> ReplyEnvelope:
        final_text = self.extract_final_answer_from_raw(raw_text)

        return ReplyEnvelope(
            raw_text=self._clean_text(raw_text),
            thinking_text="",
            final_text=final_text,
            display_text=final_text,
            tts_text=final_text,
            source_type=source_type,
            model_key=model_key,
            strategy_used="raw_priority_extract",
            confidence=0.82 if final_text else 0.1,
            needs_repair=not bool(final_text),
            debug_notes="raw_priority_extract",
        )

    def extract_by_legacy_cleanup(
        self,
        *,
        user_text: str,
        raw_text: str,
        source_type: str,
        model_key: str,
    ) -> ReplyEnvelope:
        visible_text = self.legacy_cleanup.sanitize_visible_reply(raw_text)
        visible_text = self._normalize_answer_text(visible_text)

        return ReplyEnvelope(
            raw_text=self._clean_text(raw_text),
            thinking_text="",
            final_text=visible_text,
            display_text=visible_text,
            tts_text=visible_text,
            source_type=source_type,
            model_key=model_key,
            strategy_used="legacy_cleanup",
            confidence=0.45 if visible_text else 0.1,
            needs_repair=not bool(visible_text),
            debug_notes="legacy_cleanup",
        )

    def extract_by_repair_llm(
        self,
        *,
        user_text: str,
        raw_text: str,
        source_type: str,
        model_key: str,
        chat_callable: Callable[..., str],
        model_name: str,
        host: str,
        timeout: Tuple[int, int],
        request_options: Optional[Dict[str, Any]] = None,
    ) -> ReplyEnvelope:
        repaired = self.repair_service.repair_with_llm(
            user_text=user_text,
            raw_ai_text=raw_text,
            chat_callable=chat_callable,
            model_name=model_name,
            host=host,
            timeout=timeout,
            request_options=request_options,
        )

        final_text = self.extract_final_answer_from_raw(repaired)

        bad_markers = [
            "在之前的上下文中",
            "根据提示",
            "根据设定",
            "我应该",
            "我需要",
            "用户问",
            "教学风格",
            "最终输出格式要求",
            "回复要求",
            "检查是否自然",
        ]

        if final_text and any(marker in final_text for marker in bad_markers):
            final_text = ""

        return ReplyEnvelope(
            raw_text=self._clean_text(raw_text),
            thinking_text="",
            final_text=self._normalize_answer_text(final_text),
            display_text=self._normalize_answer_text(final_text),
            tts_text=self._normalize_answer_text(final_text),
            source_type=source_type,
            model_key=model_key,
            strategy_used="repair_extract",
            confidence=0.8 if final_text else 0.15,
            needs_repair=not bool(final_text),
            debug_notes="repair_extract",
        )

    def extract_plain_fallback(
        self,
        *,
        raw_text: str,
        source_type: str,
        model_key: str,
    ) -> ReplyEnvelope:
        final_text = self._normalize_answer_text(raw_text)

        return ReplyEnvelope(
            raw_text=self._clean_text(raw_text),
            thinking_text="",
            final_text=final_text,
            display_text=final_text,
            tts_text=final_text,
            source_type=source_type,
            model_key=model_key,
            strategy_used="plain_fallback",
            confidence=0.2 if final_text else 0.0,
            needs_repair=not bool(final_text),
            debug_notes="plain_fallback",
        )