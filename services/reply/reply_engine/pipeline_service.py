from __future__ import annotations

import re
from typing import Callable, Optional, Dict, Any, Tuple

from .envelope import ReplyEnvelope
from .capability_service import CapabilityService
from .evaluator_service import EvaluatorService
from .strategy_selector import StrategySelector
from .extractor_service import ExtractorService  # type: ignore


class ReplyPipelineService:
    def __init__(self):
        self.capability_service = CapabilityService()
        self.evaluator_service = EvaluatorService()
        self.strategy_selector = StrategySelector()
        self.extractor_service = ExtractorService()

    def _strip_reasoning_tags(self, text: str) -> str:
        cleaned = (text or "").strip()
        if not cleaned:
            return ""

        cleaned = cleaned.replace("<think>", "").replace("</think>", "")
        cleaned = cleaned.replace("<thinking>", "").replace("</thinking>", "")
        return cleaned.strip()

    def _split_sentences(self, text: str) -> list[str]:
        text = (text or "").replace("\r", "\n").strip()
        if not text:
            return []

        parts = re.split(r"\n+|(?<=[。！？!?])\s*", text)
        return [p.strip() for p in parts if p and p.strip()]

    def _is_followup_sentence(self, text: str) -> bool:
        t = (text or "").strip()
        if not t:
            return True

        followup_patterns = [
            "需要我再解释一下吗",
            "需要我继续吗",
            "还需要我",
            "要我再",
            "要不要我",
            "如果你愿意",
            "需要的话",
            "我可以继续",
            "还想让我",
            "要不要我继续",
            "需要我帮你",
            "要我顺便",
        ]
        return len(t) <= 32 and any(p in t for p in followup_patterns)

    def _build_answer_first_text(
        self,
        text: str,
        *,
        max_sentences: int = 2,
        strip_followup_tail: bool = False,
    ) -> str:
        cleaned = self._strip_reasoning_tags(text)
        if not cleaned:
            return ""

        sentences = self._split_sentences(cleaned)
        if not sentences:
            return cleaned

        useful: list[str] = []
        for s in sentences:
            if strip_followup_tail and self._is_followup_sentence(s):
                if useful:
                    break
                continue

            useful.append(s)
            if len(useful) >= max(1, int(max_sentences)):
                break

        candidate = "\n".join(useful).strip()
        if not candidate:
            candidate = cleaned

        candidate_sentences = self._split_sentences(candidate)
        if (
            strip_followup_tail
            and len(candidate_sentences) > 1
            and self._is_followup_sentence(candidate_sentences[-1])
        ):
            candidate = "\n".join(candidate_sentences[:-1]).strip()

        return candidate.strip()

    def _compress_for_tts(
        self,
        text: str,
        *,
        max_sentences: int = 2,
        strip_followup_tail: bool = False,
    ) -> str:
        cleaned = self._strip_reasoning_tags(text)
        if not cleaned:
            return ""

        sentences = self._split_sentences(cleaned)
        if not sentences:
            return cleaned

        picked: list[str] = []
        for s in sentences:
            if strip_followup_tail and self._is_followup_sentence(s):
                if picked:
                    break
                continue

            picked.append(s)
            if len(picked) >= max(1, int(max_sentences)):
                break

        candidate = "\n".join(picked).strip()
        return candidate or cleaned

    def _apply_policy_to_envelope(
        self,
        envelope: ReplyEnvelope,
        *,
        policy_profile: Optional[Dict[str, Any]] = None,
        request_type: str = "chat",
    ) -> ReplyEnvelope:
        policy = policy_profile if isinstance(policy_profile, dict) else {}

        raw_text = getattr(envelope, "raw_text", "") or ""
        cleaned_raw = self._strip_reasoning_tags(raw_text)

        final_text = (getattr(envelope, "final_text", "") or "").strip()
        if not final_text:
            final_text = cleaned_raw

        final_visible_mode = str(policy.get("final_visible_mode", "light_pass")).strip().lower()
        final_tts_mode = str(policy.get("final_tts_mode", "visible_only")).strip().lower()

        strip_followup_tail = bool(policy.get("strip_followup_tail", False))
        max_visible_sentences = int(policy.get("max_visible_sentences", 2) or 2)
        max_tts_sentences = int(policy.get("max_tts_sentences", 2) or 2)
        prefer_short_math_answer = bool(policy.get("prefer_short_math_answer", False))

        if request_type == "math" and prefer_short_math_answer:
            final_visible_mode = "strict_answer_first"

        if final_visible_mode == "strict_answer_first":
            visible_text = self._build_answer_first_text(
                final_text or cleaned_raw,
                max_sentences=max_visible_sentences,
                strip_followup_tail=strip_followup_tail,
            )
        elif final_visible_mode == "answer_with_short_context":
            visible_text = self._build_answer_first_text(
                final_text or cleaned_raw,
                max_sentences=max_visible_sentences,
                strip_followup_tail=False,
            )
        else:
            visible_text = final_text or cleaned_raw

        if not visible_text:
            visible_text = "抱歉，当前没有成功提取到最终回复。"

        if final_tts_mode == "answer_only":
            tts_text = self._build_answer_first_text(
                visible_text or cleaned_raw,
                max_sentences=1,
                strip_followup_tail=True,
            )
        elif final_tts_mode == "answer_block_only":
            tts_text = self._build_answer_first_text(
                visible_text or cleaned_raw,
                max_sentences=max_tts_sentences,
                strip_followup_tail=strip_followup_tail,
            )
        elif final_tts_mode == "light_tts_compress":
            tts_text = self._compress_for_tts(
                visible_text or cleaned_raw,
                max_sentences=max_tts_sentences,
                strip_followup_tail=strip_followup_tail,
            )
        else:
            tts_text = visible_text

        envelope.final_text = visible_text.strip()
        envelope.tts_text = (tts_text or visible_text).strip()
        return envelope

    def build_envelope(
        self,
        *,
        backend: str,
        model_name: str,
        user_text: str,
        raw_text: str,
        chat_callable: Optional[Callable[..., str]] = None,
        host: str = "",
        timeout: Tuple[int, int] = (10, 300),
        request_options: Optional[Dict[str, Any]] = None,
        policy_profile: Optional[Dict[str, Any]] = None,
        request_type: str = "chat",
    ) -> ReplyEnvelope:
        capability = self.capability_service.get_capability(backend, model_name)
        model_key = capability.get("model_key", f"{backend}:{model_name}")
        source_type = capability.get("backend", backend)

        first_pass = self.extractor_service.extract_by_raw_priority(
            user_text=user_text,
            raw_text=raw_text,
            source_type=source_type,
            model_key=model_key,
        )

        evaluation = self.evaluator_service.evaluate(
            user_text=user_text,
            raw_text="",
            candidate_text=first_pass.final_text,
        )

        strategy = self.strategy_selector.select(capability, evaluation)

        if strategy == "direct_use":
            first_pass.strategy_used = "direct_use"
            first_pass.confidence = evaluation.get("confidence", 0.5)
            first_pass.needs_repair = evaluation.get("needs_repair", False)
            return self._apply_policy_to_envelope(
                first_pass,
                policy_profile=policy_profile,
                request_type=request_type,
            )

        if strategy == "repair_extract" and chat_callable is not None:
            repaired = self.extractor_service.extract_by_repair_llm(
                user_text=user_text,
                raw_text=raw_text,
                source_type=source_type,
                model_key=model_key,
                chat_callable=chat_callable,
                model_name=model_name,
                host=host,
                timeout=timeout,
                request_options=request_options,
            )

            repaired_eval = self.evaluator_service.evaluate(
                user_text=user_text,
                raw_text="",
                candidate_text=repaired.final_text,
            )
            repaired.confidence = repaired_eval.get("confidence", repaired.confidence)
            repaired.needs_repair = repaired_eval.get("needs_repair", repaired.needs_repair)

            if repaired_eval.get("can_use_directly", False) and repaired.final_text:
                return self._apply_policy_to_envelope(
                    repaired,
                    policy_profile=policy_profile,
                    request_type=request_type,
                )

        legacy = self.extractor_service.extract_by_legacy_cleanup(
            user_text=user_text,
            raw_text=raw_text,
            source_type=source_type,
            model_key=model_key,
        )
        legacy_eval = self.evaluator_service.evaluate(
            user_text=user_text,
            raw_text="",
            candidate_text=legacy.final_text,
        )
        legacy.confidence = legacy_eval.get("confidence", legacy.confidence)
        legacy.needs_repair = legacy_eval.get("needs_repair", legacy.needs_repair)

        if legacy_eval.get("can_use_directly", False) and legacy.final_text:
            legacy.strategy_used = "legacy_cleanup_fallback"
            return self._apply_policy_to_envelope(
                legacy,
                policy_profile=policy_profile,
                request_type=request_type,
            )

        fallback = self.extractor_service.extract_plain_fallback(
            raw_text="抱歉，当前没有成功提取到最终回复。",
            source_type=source_type,
            model_key=model_key,
        )
        fallback.confidence = 0.0
        fallback.needs_repair = True
        fallback.strategy_used = "final_fallback"
        return self._apply_policy_to_envelope(
            fallback,
            policy_profile=policy_profile,
            request_type=request_type,
        )