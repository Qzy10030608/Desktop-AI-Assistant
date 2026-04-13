from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from config import MODEL_REPLY_POLICY_RULES_FILE  # type: ignore
from services.reply.model_reply_policy_registry import ModelReplyPolicyRegistry  # type: ignore


class ModelReplyPolicyService:
    def __init__(self):
        self.registry = ModelReplyPolicyRegistry()
        self.rules_path = Path(MODEL_REPLY_POLICY_RULES_FILE)

    # =========================
    # 外部主入口
    # =========================
    def enrich_model_profile(self, model: Dict[str, Any]) -> Dict[str, Any]:
        model = dict(model or {})

        provider = str(model.get("provider", "ollama")).strip().lower() or "ollama"
        model_name = str(model.get("model_name", "")).strip()
        display_name = str(model.get("name", "")).strip()
        text_for_match = model_name or display_name

        rules = self._load_rules()

        explicit_rule = self._match_explicit_model_rule(text_for_match, rules)

        family_override = str(model.get("family_override", "")).strip().lower()
        size_tier_override = str(model.get("size_tier_override", "")).strip().lower()
        policy_override = model.get("policy_override", {})
        if not isinstance(policy_override, dict):
            policy_override = {}

        family = (
            family_override
            or str(model.get("family", "")).strip().lower()
            or str(explicit_rule.get("family", "")).strip().lower()
            or self._infer_family(text_for_match, rules)
            or "unknown"
        )

        size_tier = (
            size_tier_override
            or str(model.get("size_tier", "")).strip().lower()
            or str(explicit_rule.get("size_tier", "")).strip().lower()
            or self._infer_size_tier(provider, text_for_match, rules)
            or "medium"
        )

        template_name = (
            str(policy_override.get("template", "")).strip()
            or str(explicit_rule.get("template", "")).strip()
            or self._resolve_template_name(provider, family, size_tier, rules)
        )

        policy_profile = self.registry.get_template(template_name)

        family_override_rules = (
            rules.get("family_policy_overrides", {})
            .get(family, {})
            .get(size_tier, {})
        )
        if isinstance(family_override_rules, dict):
            patch = family_override_rules.get("policy_patch", {})
            if isinstance(patch, dict):
                policy_profile.update(patch)

        explicit_patch = explicit_rule.get("policy_patch", {})
        if isinstance(explicit_patch, dict):
            policy_profile.update(explicit_patch)

        policy_profile.update(policy_override)

        model["family"] = family
        model["size_tier"] = size_tier
        model["policy_profile"] = policy_profile
        model["policy_version"] = str(
            model.get("policy_version", policy_profile.get("policy_version", "v1"))
        ).strip() or "v1"

        if not str(model.get("policy_selected_at", "")).strip():
            model["policy_selected_at"] = datetime.now().isoformat(timespec="seconds")

        # 保留手动覆盖字段，供后续 page_connection.py 使用
        model["family_override"] = family_override
        model["size_tier_override"] = size_tier_override
        model["policy_override"] = policy_override

        return model

    # =========================
    # 规则读取
    # =========================
    def _load_rules(self) -> Dict[str, Any]:
        if not self.rules_path.exists():
            return {}

        try:
            data = json.loads(self.rules_path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    # =========================
    # family / size tier 解析
    # =========================
    def _infer_family(self, text: str, rules: Dict[str, Any]) -> str:
        value = (text or "").strip().lower()
        family_aliases = rules.get("family_aliases", {})

        if isinstance(family_aliases, dict):
            for family, aliases in family_aliases.items():
                if not isinstance(aliases, list):
                    continue
                for alias in aliases:
                    alias_text = str(alias).strip().lower()
                    if alias_text and alias_text in value:
                        return str(family).strip().lower()

        return "unknown"

    def _infer_size_tier(self, provider: str, text: str, rules: Dict[str, Any]) -> str:
        provider = (provider or "").strip().lower()
        value = (text or "").strip().lower()

        if provider == "api":
            return str(
                rules.get("provider_default_tiers", {}).get("api", "large")
            ).strip().lower() or "large"

        size_num = self._extract_billion_size(value)
        if size_num is not None:
            size_tiers = rules.get("size_tiers", [])
            if isinstance(size_tiers, list):
                for item in size_tiers:
                    if not isinstance(item, dict):
                        continue

                    name = str(item.get("name", "")).strip().lower()
                    if not name:
                        continue

                    max_b = item.get("max_b", None)
                    min_b = item.get("min_b", None)

                    if max_b is not None:
                        try:
                            if size_num <= float(max_b):
                                return name
                        except Exception:
                            pass

                    if min_b is not None and max_b is None:
                        try:
                            if size_num >= float(min_b):
                                return name
                        except Exception:
                            pass

        fallback = str(
            rules.get("provider_default_tiers", {}).get(provider, "medium")
        ).strip().lower()
        return fallback or "medium"

    def _extract_billion_size(self, text: str):
        match = re.search(r"(\d+(?:\.\d+)?)\s*b\b", text)
        if not match:
            return None
        try:
            return float(match.group(1))
        except Exception:
            return None

    # =========================
    # 模板选择
    # =========================
    def _resolve_template_name(
        self,
        provider: str,
        family: str,
        size_tier: str,
        rules: Dict[str, Any],
    ) -> str:
        provider = (provider or "").strip().lower()
        family = (family or "").strip().lower()
        size_tier = (size_tier or "").strip().lower()

        family_rule = rules.get("family_policy_overrides", {}).get(family, {}).get(size_tier, {})
        if isinstance(family_rule, dict):
            family_template = str(family_rule.get("template", "")).strip()
            if family_template:
                return family_template

        tier_mapping = rules.get("tier_template_mapping", {})
        if not isinstance(tier_mapping, dict):
            tier_mapping = {}

        if provider == "api":
            return str(tier_mapping.get("api", "api_high_trust")).strip() or "api_high_trust"

        return str(tier_mapping.get(size_tier, "medium_local_balanced")).strip() or "medium_local_balanced"

    # =========================
    # 显式规则匹配
    # =========================
    def _match_explicit_model_rule(self, text: str, rules: Dict[str, Any]) -> Dict[str, Any]:
        value = (text or "").strip().lower()
        model_rules = rules.get("explicit_model_rules", [])
        if not isinstance(model_rules, list):
            return {}

        for item in model_rules:
            if not isinstance(item, dict):
                continue

            match_type = str(item.get("match_type", "contains")).strip().lower()
            target = str(item.get("value", "")).strip().lower()
            if not target:
                continue

            if match_type == "contains" and target in value:
                return item

            if match_type == "equals" and target == value:
                return item

        return {}