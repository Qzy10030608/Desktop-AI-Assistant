from __future__ import annotations

import json
import urllib.request
from pathlib import Path
from typing import Any

from config import OLLAMA_HOST, OLLAMA_MODEL


class LLMTargetHintService:

    def __init__(
        self,
        *,
        project_root: str | Path | None = None,
        ollama_host: str = "",
        model_name: str = "",
        timeout_seconds: float = 4.0,
        allow_ollama_generate: bool = False,
    ) -> None:
        self.project_root = Path(project_root or Path(__file__).resolve().parents[3]).expanduser().resolve()
        self.ollama_host = str(ollama_host or OLLAMA_HOST).rstrip("/")
        self.model_name = str(model_name or OLLAMA_MODEL).strip()
        self.timeout_seconds = max(1.0, float(timeout_seconds or 4.0))
        self.allow_ollama_generate = bool(allow_ollama_generate)
    def build_hint(
        self,
        *,
        raw_user_text: str,
        action_hint: str = "",
        target_normalized: str = "",
        understanding_packet: dict[str, Any] | None = None,
        known_software_labels: list[str] | None = None,
    ) -> dict[str, Any]:
        labels = _dedupe_labels(known_software_labels or self.load_known_software_labels())
        debug_base = {
            "known_label_count": len(labels),
            "model_name": self.model_name,
            "ollama_host": self.ollama_host,
            "target_normalized": str(target_normalized or ""),
        }

        if not labels:
            return self._empty(
                "no_known_software_labels",
                error_kind="no_labels",
                **debug_base,
            )

        # 第一层：先查记忆层。
        # 注意：这里不写死任何“星露谷 -> Stardew Valley”之类的别名。
        # 用户语言习惯必须来自 CommandMemoryService。
        memory_hint = self._memory_label_hint(
            raw_user_text=raw_user_text,
            action_hint=action_hint,
            target_normalized=target_normalized,
            labels=labels,
        )
        if memory_hint.get("label"):
            return {
                "schema_version": "llm_target_hint_v1",
                "ok": True,
                "source": "target_memory",
                "memory_source": str(memory_hint.get("source", "") or "target_memory"),
                "trusted": bool(memory_hint.get("trusted", False)),
                "target_label_hint": str(memory_hint.get("label", "") or ""),
                "confidence": _safe_float(memory_hint.get("confidence", 0.86), default=0.86),
                "requires_confirmation": not bool(memory_hint.get("trusted", False)),
                "allow_direct_execution": False,
                "forbidden_fields": [
                    "backend",
                    "permission_state",
                    "process_name",
                    "process_names",
                    "exe_path",
                ],
                "reason": str(memory_hint.get("reason", "") or "matched_target_memory"),
                "candidates": memory_hint.get("candidates", []) if isinstance(memory_hint.get("candidates"), list) else [],
                **debug_base,
            }
        direct_label = self._direct_label_hint(
            raw_user_text=raw_user_text,
            target_normalized=target_normalized,
            labels=labels,
        )
        if direct_label:
            return {
                "schema_version": "llm_target_hint_v1",
                "ok": True,
                "source": "direct_label_match",
                "trusted": False,
                "target_label_hint": direct_label["label"],
                "confidence": direct_label["confidence"],
                "requires_confirmation": True,
                "allow_direct_execution": False,
                "forbidden_fields": [
                    "backend",
                    "permission_state",
                    "process_name",
                    "process_names",
                    "exe_path",
                ],
                "reason": direct_label["reason"],
                **debug_base,
            }
        
        if not self.allow_ollama_generate:
            return self._empty(
                "target_not_found_in_memory_or_labels",
                source="fast_evidence",
                error_kind="fast_no_match",
                skip_ollama=True,
                **debug_base,
            )
        # 第二层：记忆没有命中时，才调用 LLM。
        # LLM 只能从 known_software_labels 中选择，不允许编造路径、进程、backend 或权限。
        prompt = self._prompt(
            raw_user_text=raw_user_text,
            action_hint=action_hint,
            target_normalized=target_normalized,
            understanding_packet=understanding_packet or {},
            known_software_labels=labels,
        )

        response_text = ""
        try:
            response_text = self._ollama_generate(prompt)
            parsed = self._parse_response(response_text)
            parsed_label = str(parsed.get("target_label_hint", "") or "")
            label = self._match_label(parsed_label, labels)

            if not label:
                return self._empty(
                    "llm_returned_no_known_label",
                    error_kind="label_rejected",
                    parsed_label=parsed_label,
                    rejected_reason="not_in_known_software_labels",
                    raw_response_head=response_text[:240],
                    **debug_base,
                )

            confidence = _safe_float(parsed.get("confidence", 0.5), default=0.5)
            return {
                "schema_version": "llm_target_hint_v1",
                "ok": True,
                "source": "ollama_generate",
                "trusted": False,
                "target_label_hint": label,
                "confidence": max(0.0, min(1.0, confidence)),
                "requires_confirmation": True,
                "allow_direct_execution": False,
                "forbidden_fields": [
                    "backend",
                    "permission_state",
                    "process_name",
                    "process_names",
                    "exe_path",
                ],
                "reason": str(parsed.get("reason", "") or "selected_from_known_software_labels"),
                **debug_base,
                "raw_response_head": response_text[:240],
                "parsed_label": parsed_label,
            }

        except Exception as exc:
            return self._empty(
                "llm_target_hint_failed",
                error_kind=exc.__class__.__name__,
                error=str(exc),
                raw_response_head=response_text[:240],
                **debug_base,
            )

    def load_known_software_labels(self) -> list[str]:
        labels: list[str] = []
        try:
            from services.desktop.software_view_cache_service import SoftwareViewCacheService

            state = SoftwareViewCacheService(self.project_root).read()
            rows = state.get("rows", []) if isinstance(state.get("rows", []), list) else []
            for row in rows:
                if not isinstance(row, dict):
                    continue
                for key in ("title", "name", "app_id", "canonical_app_id"):
                    value = str(row.get(key, "") or "").strip()
                    if value:
                        labels.append(value)
        except Exception:
            pass

        if labels:
            return _dedupe_labels(labels)

        try:
            from services.desktop.qin.libu.software_ledger import SoftwareCandidateBook, SoftwareTrustedBook

            for book in (SoftwareTrustedBook(self.project_root), SoftwareCandidateBook(self.project_root)):
                for record in book.read():
                    item = record.to_dict()
                    for key in ("title", "name", "app_id", "canonical_app_id"):
                        value = str(item.get(key, "") or "").strip()
                        if value:
                            labels.append(value)
        except Exception:
            pass
        return _dedupe_labels(labels)

    def _prompt(
        self,
        *,
        raw_user_text: str,
        action_hint: str,
        target_normalized: str,
        understanding_packet: dict[str, Any],
        known_software_labels: list[str],
    ) -> str:
        labels = known_software_labels[:120]
        label_lines = "\n".join(f"- {label}" for label in labels)
        memory = understanding_packet.get("evidence", {}).get("memory_terms", [])
        memory_terms = ", ".join(str(item) for item in memory[:12]) if isinstance(memory, list) else ""
        return (
            "You are a desktop target hint selector. "
            "Choose at most one target_label_hint from known_software_labels. "
            "Do not invent labels. Do not return paths, process names, backend, or permission. "
            "If none match, return an empty target_label_hint.\n\n"
            f"raw_user_text: {raw_user_text}\n"
            f"action_hint: {action_hint}\n"
            f"target_normalized: {target_normalized}\n"
            f"memory_terms: {memory_terms}\n"
            "known_software_labels:\n"
            f"{label_lines}\n\n"
            "Return compact JSON only: "
            "{\"target_label_hint\":\"\", \"confidence\":0.0, \"reason\":\"\"}"
        )

    def _ollama_generate(self, prompt: str) -> str:
        url = f"{self.ollama_host}/api/generate"
        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0,
                "num_predict": 80,
            },
        }
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
            body = response.read().decode("utf-8", errors="replace")
        result = json.loads(body)
        return str(result.get("response", "") or "")

    def _parse_response(self, text: str) -> dict[str, Any]:
        raw = str(text or "").strip()
        if not raw:
            return {}
        start = raw.find("{")
        end = raw.rfind("}")
        if start >= 0 and end > start:
            raw = raw[start:end + 1]
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}

    def _memory_label_hint(
        self,
        *,
        raw_user_text: str,
        action_hint: str,
        target_normalized: str,
        labels: list[str],
    ) -> dict[str, Any]:
        query_text = str(target_normalized or raw_user_text or "").strip()
        if not query_text:
            return {}

        try:
            from services.desktop.tianting.command_memory_service import CommandMemoryService

            memory = CommandMemoryService()

            result = memory.lookup_target_hint(
                query_text,
                action_hint=action_hint,
                input_channel="text",
                actor_role="normal_user",
            )

            if not bool(result.get("matched", False)):
                result = memory.lookup_target_hint(
                    query_text,
                    action_hint="app.launch",
                    input_channel="text",
                    actor_role="normal_user",
                )
            if not bool(result.get("matched", False)):
                result = memory.lookup_fuzzy_target_hint(
                    query_text,
                    action_hint=action_hint or "app.launch",
                    memory_domain="software_terms",
                )

        except Exception:
            return {}

        if not isinstance(result, dict):
            return {}

        hint = result.get("target_hint", {})
        if not isinstance(hint, dict):
            hint = result

        for key in ("target_label_hint", "target_label", "label", "title", "name"):
            candidate = str(hint.get(key, "") or "").strip()
            matched = self._match_label(candidate, labels)
            if matched:
                return {
                    "label": matched,
                    "trusted": bool(result.get("trusted", False)),
                    "confidence": _safe_float(result.get("confidence", 0.0), default=0.0),
                    "source": str(result.get("source", "") or "target_memory"),
                    "reason": str(result.get("source", "") or "matched_target_memory"),
                    "candidates": result.get("candidates", []) if isinstance(result.get("candidates"), list) else [],
                }

        return {}
    
    def _direct_label_hint(
        self,
        *,
        raw_user_text: str,
        target_normalized: str,
        labels: list[str],
    ) -> dict[str, Any]:
        query = self._normalize_label_text(target_normalized or raw_user_text)
        if not query:
            return {}

        exact_matches: list[str] = []
        contains_matches: list[str] = []

        for label in labels:
            label_text = str(label or "").strip()
            label_key = self._normalize_label_text(label_text)
            if not label_text or not label_key:
                continue

            if query == label_key:
                exact_matches.append(label_text)
            elif len(query) >= 3 and (query in label_key or label_key in query):
                contains_matches.append(label_text)

        exact_matches = _dedupe_labels(exact_matches)
        if len(exact_matches) == 1:
            return {
                "label": exact_matches[0],
                "confidence": 0.88,
                "reason": "direct_exact_label_match",
            }

        contains_matches = _dedupe_labels(contains_matches)
        if len(contains_matches) == 1:
            return {
                "label": contains_matches[0],
                "confidence": 0.76,
                "reason": "direct_contains_label_match",
            }

        return {}

    def _normalize_label_text(self, value: str) -> str:
        text = str(value or "").strip().casefold()
        if not text:
            return ""
        keep: list[str] = []
        for char in text:
            if char.isalnum() or "\u4e00" <= char <= "\u9fff":
                keep.append(char)
        return "".join(keep)
    
    def _match_label(self, value: str, labels: list[str]) -> str:
        normalized = str(value or "").strip().casefold()
        if not normalized:
            return ""
        for label in labels:
            if label.casefold() == normalized:
                return label
        return ""

    def _empty(self, reason: str, **extra: Any) -> dict[str, Any]:
        payload = {
            "schema_version": "llm_target_hint_v1",
            "ok": False,
            "source": "ollama_generate",
            "trusted": False,
            "target_label_hint": "",
            "confidence": 0.0,
            "requires_confirmation": True,
            "allow_direct_execution": False,
            "reason": reason,
        }
        payload.update(extra)
        return payload


def build_llm_target_hint(**kwargs: Any) -> dict[str, Any]:
    return LLMTargetHintService(
        project_root=kwargs.pop("project_root", None),
        allow_ollama_generate=bool(kwargs.pop("allow_ollama_generate", False)),
    ).build_hint(**kwargs)

def _dedupe_labels(labels: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for label in labels:
        text = str(label or "").strip()
        key = text.casefold()
        if not text or key in seen:
            continue
        seen.add(key)
        result.append(text)
    return result


def _safe_float(value: Any, *, default: float) -> float:
    try:
        return float(value)
    except Exception:
        return default
