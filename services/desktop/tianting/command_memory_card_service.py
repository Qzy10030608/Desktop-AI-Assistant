from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4


CARD_SCHEMA_VERSION = "desktop_memory_card_v1"


class CommandMemoryCardService:
    """Append-only learning evidence for command understanding.

    Cards are learning records only. They do not grant permission, pick a
    backend, or provide execution targets directly.
    """

    def __init__(self, project_root: str | Path | None = None) -> None:
        self.project_root = Path(project_root or Path(__file__).resolve().parents[3]).expanduser().resolve()
        self.card_dir = self.project_root / "data" / "runtime" / "desktop" / "tianting" / "command_memory_cards"
        self.exports_dir = self.card_dir / "exports"

    def append_observation_card(
        self,
        *,
        raw_text: str,
        input_channel: str = "text",
        locale: str = "zh-CN",
        route: str = "",
        action_hint: str = "",
        confidence: float = 0.0,
        matched_rules: list[str] | None = None,
        target_hint: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        card = self._base_card(raw_text=raw_text, input_channel=input_channel, locale=locale)
        card["route"].update({
            "route": str(route or ""),
            "action_hint": str(action_hint or ""),
            "confidence": _bounded_float(confidence),
            "matched_rules": [str(item) for item in (matched_rules or [])],
        })
        if isinstance(target_hint, dict):
            card["target"].update(_target_from_hint(target_hint))
        self._append_jsonl("cards.jsonl", card)
        return card

    def append_candidate_card(
        self,
        *,
        action: str,
        raw_target: str = "",
        expanded_terms: list[str] | None = None,
        candidates: list[dict[str, Any]] | None = None,
        score: float = 0.0,
        permission_state: str = "",
        source: list[str] | str | None = None,
    ) -> dict[str, Any]:
        card = self._base_card(raw_text=raw_target)
        card["route"]["action_hint"] = str(action or "")
        card["target"].update({
            "raw_target": str(raw_target or ""),
            "expanded_terms": [str(item) for item in (expanded_terms or []) if str(item or "").strip()],
        })
        card["candidates"] = _safe_candidates(candidates or [])
        card["outcome"].update({
            "status": "candidate_observed",
            "permission_state": str(permission_state or ""),
        })
        card["learning"].update({
            "confidence_after_feedback": _bounded_float(score),
            "requires_developer_review": True,
        })
        card["debug_summary"] = {
            "source": _source_list(source),
            "candidate_count": len(card["candidates"]),
        }
        self._append_jsonl("cards.jsonl", card)
        return card

    def append_feedback_card(
        self,
        *,
        pending_task_id: str = "",
        feedback_type: str = "none",
        feedback_text: str = "",
        selected_candidate: dict[str, Any] | None = None,
        rejected_candidate: dict[str, Any] | None = None,
        original_task: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        task = original_task if isinstance(original_task, dict) else {}
        card = self._base_card(raw_text=str(feedback_text or ""))
        action = str(task.get("action", task.get("original_action", "")) or "")
        selected = selected_candidate if isinstance(selected_candidate, dict) else {}
        rejected = rejected_candidate if isinstance(rejected_candidate, dict) else {}
        normalized_feedback = _feedback_type(feedback_type)
        card["route"]["route"] = "pending_followup"
        card["route"]["action_hint"] = action
        card["target"].update({
            "selected_target_label": str(selected.get("label", "") or ""),
            "selected_target_id": str(selected.get("candidate_id", selected.get("app_id", "")) or ""),
            "target_source": "pending_task",
        })
        card["user_feedback"].update({
            "feedback_type": normalized_feedback,
            "feedback_text": str(feedback_text or ""),
            "selected_candidate_id": str(selected.get("candidate_id", selected.get("app_id", "")) or ""),
            "rejected_candidate_id": str(rejected.get("candidate_id", rejected.get("app_id", "")) or ""),
            "pending_task_id": str(pending_task_id or ""),
            "confirmed_at": _now_iso() if normalized_feedback == "confirmed" else "",
        })
        card["learning"].update({
            "suggested_term": str(task.get("original_user_text", "") or ""),
            "suggested_target_label": str(selected.get("label", "") or ""),
            "can_promote_to_active_memory": normalized_feedback == "confirmed",
            "requires_developer_review": True,
        })
        self._append_jsonl("cards.jsonl", card)
        if normalized_feedback == "confirmed":
            self._append_jsonl("confirmed_cards.jsonl", card)
            self._append_jsonl("review_queue.jsonl", card)
        elif normalized_feedback in {"rejected", "cancelled"}:
            self._append_jsonl("rejected_cards.jsonl", card)
        return card

    def promote_confirmed_card(
        self,
        card: dict[str, Any],
        *,
        memory_domain: str = "",
    ) -> dict[str, Any]:
        payload = card if isinstance(card, dict) else {}
        feedback = payload.get("user_feedback", {}) if isinstance(payload.get("user_feedback"), dict) else {}
        if str(feedback.get("feedback_type", "") or "") != "confirmed":
            return {"ok": False, "reason": "card_not_confirmed"}

        learning = payload.get("learning", {}) if isinstance(payload.get("learning"), dict) else {}
        domain = str(memory_domain or learning.get("memory_domain", "") or "software_terms").strip()
        term = str(learning.get("suggested_term", "") or payload.get("input", {}).get("raw_text", "") or "").strip()
        target_label = str(learning.get("suggested_target_label", "") or payload.get("target", {}).get("selected_target_label", "") or "").strip()
        if not term or not target_label:
            return {"ok": False, "reason": "missing_term_or_target"}

        try:
            from services.desktop.tianting.command_memory_service import CommandMemoryService

            service = CommandMemoryService()
            return service.promote_confirmed_term(
                domain,
                term,
                target_label,
                aliases=[],
                source_card_id=str(payload.get("card_id", "") or ""),
            )
        except Exception as exc:
            return {"ok": False, "reason": str(exc)}

    def export_training_dataset(self) -> dict[str, Any]:
        rows = []
        for card in self._iter_cards("cards.jsonl"):
            rows.append({
                "raw_text": str((card.get("input", {}) or {}).get("raw_text", "") or ""),
                "route": str((card.get("route", {}) or {}).get("route", "") or ""),
                "action_hint": str((card.get("route", {}) or {}).get("action_hint", "") or ""),
                "raw_target": str((card.get("target", {}) or {}).get("raw_target", "") or ""),
                "expanded_terms": list((card.get("target", {}) or {}).get("expanded_terms", []) or []),
                "selected_target_label": str((card.get("target", {}) or {}).get("selected_target_label", "") or ""),
                "feedback_type": str((card.get("user_feedback", {}) or {}).get("feedback_type", "none") or "none"),
                "outcome_status": str((card.get("outcome", {}) or {}).get("status", "") or ""),
            })
        self.exports_dir.mkdir(parents=True, exist_ok=True)
        output_path = self.exports_dir / "desktop_command_dataset.jsonl"
        try:
            output_path.write_text(
                "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
                encoding="utf-8",
            )
        except Exception as exc:
            return {"ok": False, "count": 0, "error": str(exc)}
        return {"ok": True, "count": len(rows), "path": str(output_path)}

    def _base_card(self, *, raw_text: str = "", input_channel: str = "text", locale: str = "zh-CN") -> dict[str, Any]:
        return {
            "schema_version": CARD_SCHEMA_VERSION,
            "card_id": f"card_{uuid4().hex}",
            "created_at": _now_iso(),
            "input": {
                "raw_text": str(raw_text or ""),
                "input_channel": str(input_channel or "text"),
                "locale": str(locale or "zh-CN"),
                "normalized_text": _normalize_text(raw_text),
            },
            "route": {
                "route": "",
                "action_hint": "",
                "confidence": 0.0,
                "matched_rules": [],
            },
            "target": {
                "target_type": "unknown",
                "raw_target": str(raw_text or ""),
                "expanded_terms": [],
                "selected_target_label": "",
                "selected_target_id": "",
                "target_source": "",
            },
            "candidates": [],
            "user_feedback": {
                "feedback_type": "none",
                "feedback_text": "",
                "selected_candidate_id": "",
                "confirmed_at": "",
            },
            "outcome": {
                "status": "",
                "result_status": "",
                "message_key": "",
                "execution_backend": "",
            },
            "learning": {
                "memory_domain": "",
                "suggested_term": "",
                "suggested_target_label": "",
                "confidence_after_feedback": 0.0,
                "can_promote_to_active_memory": False,
                "requires_developer_review": True,
            },
            "privacy": {
                "contains_full_path": False,
                "contains_pid": False,
                "contains_hwnd": False,
                "safe_for_llm_hint": False,
                "safe_for_training_export": False,
            },
        }

    def _append_jsonl(self, name: str, payload: dict[str, Any]) -> None:
        try:
            self.card_dir.mkdir(parents=True, exist_ok=True)
            with (self.card_dir / name).open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(payload, ensure_ascii=False) + "\n")
        except Exception:
            return

    def _iter_cards(self, name: str) -> list[dict[str, Any]]:
        path = self.card_dir / name
        try:
            rows = []
            for line in path.read_text(encoding="utf-8").splitlines():
                try:
                    item = json.loads(line)
                except Exception:
                    continue
                if isinstance(item, dict):
                    rows.append(item)
            return rows
        except Exception:
            return []


def append_observation_card(**kwargs: Any) -> dict[str, Any]:
    return CommandMemoryCardService().append_observation_card(**kwargs)


def append_candidate_card(**kwargs: Any) -> dict[str, Any]:
    return CommandMemoryCardService().append_candidate_card(**kwargs)


def append_feedback_card(**kwargs: Any) -> dict[str, Any]:
    return CommandMemoryCardService().append_feedback_card(**kwargs)


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _normalize_text(text: str) -> str:
    return " ".join(str(text or "").strip().lower().split())


def _bounded_float(value: Any) -> float:
    try:
        return max(0.0, min(1.0, float(value or 0.0)))
    except Exception:
        return 0.0


def _source_list(source: list[str] | str | None) -> list[str]:
    if isinstance(source, list):
        return [str(item) for item in source if str(item or "").strip()]
    if isinstance(source, str) and source.strip():
        return [source.strip()]
    return []


def _safe_candidates(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    safe = []
    for candidate in candidates[:20]:
        if not isinstance(candidate, dict):
            continue
        safe.append({
            "candidate_id": str(candidate.get("candidate_id", "") or ""),
            "label": str(candidate.get("label", "") or ""),
            "score": candidate.get("score", 0.0),
            "permission_state": str(candidate.get("permission_state", candidate.get("effective_permission_state", "")) or ""),
            "source": _source_list(candidate.get("source")),
        })
    return safe


def _target_from_hint(target_hint: dict[str, Any]) -> dict[str, Any]:
    inner = target_hint.get("target_hint") if isinstance(target_hint.get("target_hint"), dict) else target_hint
    return {
        "raw_target": str(inner.get("term", "") or ""),
        "selected_target_label": str(inner.get("target_label", inner.get("target_label_hint", "")) or ""),
        "selected_target_id": str(inner.get("target_app_id", "") or ""),
        "target_source": str(target_hint.get("source", "") or inner.get("source", "") or ""),
    }


def _feedback_type(value: str) -> str:
    text = str(value or "none").strip().lower()
    if text in {"confirmed", "rejected", "cancelled", "corrected"}:
        return text
    return "none"
