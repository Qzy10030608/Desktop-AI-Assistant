from __future__ import annotations

from copy import deepcopy
from typing import Dict


class ModelReplyPolicyRegistry:
    """
    只负责提供“模板”。
    family / size / override 的判定不在这里写死。
    """

    DEFAULT_POLICY_VERSION = "v1"

    def _base_policy(self) -> Dict:
        return {
            "policy_name": "base_default",
            "policy_version": self.DEFAULT_POLICY_VERSION,

            "live_visible_mode": "light_pass",
            "final_visible_mode": "light_pass",
            "final_tts_mode": "visible_only",

            "enable_heavy_cleanup": False,
            "strip_followup_tail": False,
            "prefer_short_math_answer": False,
            "force_direct_answer_for_math": False,

            "max_visible_sentences": 2,
            "max_tts_sentences": 2,

            "notes": "默认轻量策略"
        }

    def _small_local_policy(self) -> Dict:
        data = self._base_policy()
        data.update({
            "policy_name": "small_local_strict",
            "final_visible_mode": "strict_answer_first",
            "final_tts_mode": "answer_only",
            "enable_heavy_cleanup": True,
            "strip_followup_tail": True,
            "prefer_short_math_answer": True,
            "force_direct_answer_for_math": True,
            "max_visible_sentences": 2,
            "max_tts_sentences": 1,
            "notes": "适用于小模型的强策略"
        })
        return data

    def _medium_local_policy(self) -> Dict:
        data = self._base_policy()
        data.update({
            "policy_name": "medium_local_balanced",
            "final_visible_mode": "answer_with_short_context",
            "final_tts_mode": "answer_block_only",
            "enable_heavy_cleanup": False,
            "strip_followup_tail": False,
            "prefer_short_math_answer": True,
            "force_direct_answer_for_math": False,
            "max_visible_sentences": 3,
            "max_tts_sentences": 2,
            "notes": "适用于中模型的平衡策略"
        })
        return data

    def _large_local_policy(self) -> Dict:
        data = self._base_policy()
        data.update({
            "policy_name": "large_local_light",
            "final_visible_mode": "keep_structure_light",
            "final_tts_mode": "light_tts_compress",
            "enable_heavy_cleanup": False,
            "strip_followup_tail": False,
            "prefer_short_math_answer": False,
            "force_direct_answer_for_math": False,
            "max_visible_sentences": 5,
            "max_tts_sentences": 3,
            "notes": "适用于大模型的轻量策略"
        })
        return data

    def _api_high_policy(self) -> Dict:
        data = self._base_policy()
        data.update({
            "policy_name": "api_high_trust",
            "final_visible_mode": "trust_model_light_pass",
            "final_tts_mode": "light_tts_compress",
            "enable_heavy_cleanup": False,
            "strip_followup_tail": False,
            "prefer_short_math_answer": False,
            "force_direct_answer_for_math": False,
            "max_visible_sentences": 6,
            "max_tts_sentences": 3,
            "notes": "适用于高质量 API / 大型外部模型"
        })
        return data

    def get_template(self, template_name: str) -> Dict:
        name = (template_name or "").strip().lower()

        mapping = {
            "base_default": self._base_policy,
            "small_local_strict": self._small_local_policy,
            "medium_local_balanced": self._medium_local_policy,
            "large_local_light": self._large_local_policy,
            "api_high_trust": self._api_high_policy,
        }

        builder = mapping.get(name, self._base_policy)
        return deepcopy(builder())