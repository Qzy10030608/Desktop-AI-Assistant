from __future__ import annotations

import json
from difflib import SequenceMatcher
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class CommandMemoryService:
    """Read lightweight Tianting command memory as untrusted hints only."""

    _json_cache: dict[str, tuple[float, dict[str, Any]]] = {}

    def __init__(self, memory_dir: str | Path | None = None) -> None:
        self.memory_dir = Path(memory_dir or Path(__file__).resolve().parent / "command_memory_library")

    def load_memory_pack(self) -> dict[str, Any]:
        return {
            "software_terms_seed": self._read_json("software_terms.seed.json", {"schema_version": "software_terms_seed_v1", "terms": []}),
            "software_terms": self._read_json("software_terms.local.json", {"schema_version": "software_terms_v1", "terms": []}),
            "file_terms_seed": self._read_json("file_terms.seed.json", {"schema_version": "file_terms_seed_v1", "terms": []}),
            "file_terms": self._read_json("file_terms.local.json", {"schema_version": "file_terms_v1", "terms": []}),
            "user_habits": self._read_json("user_habits.local.json", {"schema_version": "user_habits_v1", "habits": []}),
            "session_notes": self._read_json("session_notes.runtime.json", {"schema_version": "session_notes_v1", "notes": [], "pending_refs": []}),
            "learned_candidates": self._read_json("learned_candidates.json", {"schema_version": "learned_candidates_v1", "candidates": []}),
            "memory_policy": self._read_json("memory_policy.json", self._default_policy()),
        }

    def lookup_target_hint(
        self,
        text: str,
        *,
        action_hint: str = "",
        input_channel: str = "text",
        actor_role: str = "normal_user",
    ) -> dict[str, Any]:
        raw = str(text or "").strip()
        if not raw:
            return self._empty_hint()
        lowered = raw.lower()

        if str(action_hint or "").startswith("app."):
            software_terms = self._read_json(
                "software_terms.local.json",
                {"schema_version": "software_terms_v1", "terms": []},
            )
            hit = self._match_terms(lowered, software_terms.get("terms", []))
            if hit:
                return self._hint("target_memory", hit, 0.86)

        if str(action_hint or "").startswith("file."):
            file_terms = self._read_json(
                "file_terms.local.json",
                {"schema_version": "file_terms_v1", "terms": []},
            )
            hit = self._match_terms(lowered, file_terms.get("terms", []))
            if hit:
                return self._hint("target_memory", hit, 0.86)

        user_habits = self._read_json("user_habits.local.json", {"schema_version": "user_habits_v1", "habits": []})
        habit = self._match_terms(lowered, user_habits.get("habits", []), term_key="term")
        if habit:
            return self._hint("user_habits", habit, 0.55)

        session_notes = self._read_json(
            "session_notes.runtime.json",
            {"schema_version": "session_notes_v1", "notes": [], "pending_refs": []},
        )
        notes = session_notes.get("notes", [])
        if isinstance(notes, list):
            notes = notes[-20:]
        note = self._match_terms(lowered, notes, term_key="term")
        if note:
            return self._hint("session_notes", note, 0.50)

        return self._empty_hint()

    def lookup_fuzzy_target_hint(
        self,
        query_text: str,
        *,
        action_hint: str = "",
        memory_domain: str = "software_terms",
    ) -> dict[str, Any]:
        query = _normalize_memory_text(query_text)
        if not query:
            return self._empty_hint()

        if memory_domain != "software_terms" and not str(action_hint or "").startswith("app."):
            return self._empty_hint()

        data = self._read_json("software_terms.local.json", {"schema_version": "software_terms_v1", "terms": []})
        rows = data.get("terms", [])
        if not isinstance(rows, list):
            return self._empty_hint()

        scored: list[tuple[float, dict[str, Any], str]] = []
        for row in rows:
            if not isinstance(row, dict) or not bool(row.get("enabled", True)):
                continue
            variants = [row.get("term", "")]
            aliases = row.get("aliases", [])
            if isinstance(aliases, list):
                variants.extend(aliases)
            best_variant = ""
            best_score = 0.0
            for variant in variants:
                normalized_variant = _normalize_memory_text(variant)
                if not normalized_variant:
                    continue
                score = _memory_similarity(query, normalized_variant)
                if score > best_score:
                    best_score = score
                    best_variant = str(variant or "")
            if best_score > 0:
                scored.append((best_score, row, best_variant))

        if not scored:
            return self._empty_hint()

        scored.sort(key=lambda item: item[0], reverse=True)
        best_score, best_row, matched_term = scored[0]
        second_score = scored[1][0] if len(scored) > 1 else 0.0
        target_hint = self._target_hint_from_row(best_row)
        target_hint.update(
            {
                "matched_term": matched_term,
                "query_term": str(query_text or "").strip(),
            }
        )

        if best_score >= 0.78 and (best_score - second_score) >= 0.08:
            return {
                "matched": True,
                "source": "fuzzy_memory_match",
                "trusted": False,
                "confidence": max(0.0, min(1.0, best_score)),
                "target_hint": target_hint,
                "candidates": [],
            }

        close_candidates: list[dict[str, Any]] = []
        for index, (score, row, term) in enumerate(scored[:5], start=1):
            if score < 0.70:
                continue
            hint = self._target_hint_from_row(row)
            close_candidates.append(
                {
                    "candidate_id": f"fuzzy_memory_{index:03d}",
                    "display_index": index,
                    "label": str(hint.get("target_label", "") or hint.get("target_label_hint", "") or ""),
                    "matched_term": term,
                    "query_term": str(query_text or "").strip(),
                    "confidence": max(0.0, min(1.0, score)),
                    "source": "fuzzy_memory_match",
                    "kind": "app",
                }
            )

        if close_candidates:
            return {
                "matched": True,
                "source": "fuzzy_memory_match",
                "trusted": False,
                "confidence": max(0.0, min(1.0, best_score)),
                "target_hint": target_hint,
                "candidates": close_candidates,
            }

        return self._empty_hint()

    def expand_target_terms(
        self,
        text: str,
        *,
        action_hint: str = "",
        input_channel: str = "text",
        actor_role: str = "normal_user",
    ) -> dict[str, Any]:
        raw = str(text or "").strip()
        if not raw:
            return {
                "matched": False,
                "terms": [],
                "source": "none",
                "confidence": 0.0,
                "trusted": False,
                "target_hint": {},
            }

        lowered = raw.lower()
        terms = _dedupe_terms([raw])
        best_row: dict[str, Any] = {}
        best_source = "none"
        best_score = 0.0

        sources: list[tuple[str, str, str]] = []
        if str(action_hint or "").startswith("app."):
            sources.extend([
                ("software_terms.local.json", "software_terms.local", "terms"),
                ("software_terms.seed.json", "software_terms.seed", "terms"),
            ])
        if str(action_hint or "").startswith("file."):
            sources.extend([
                ("file_terms.local.json", "file_terms.local", "terms"),
                ("file_terms.seed.json", "file_terms.seed", "terms"),
            ])
        sources.extend([
            ("user_habits.local.json", "user_habits", "habits"),
            ("session_notes.runtime.json", "session_notes", "notes"),
        ])

        for file_name, source_name, row_key in sources:
            data = self._read_json(file_name, {"terms": [], "habits": [], "notes": []})
            rows = data.get(row_key, [])
            row = self._match_terms(lowered, rows, term_key="term")
            if not row:
                continue
            score = float(row.get("confidence", 0.5) or 0.5)
            aliases = row.get("aliases", [])
            row_terms = [row.get("term", "")]
            if isinstance(aliases, list):
                row_terms.extend(aliases)
            row_terms.extend([row.get("target_label_hint", ""), row.get("target_label", "")])
            terms.extend(str(item) for item in row_terms if str(item or "").strip())
            if score > best_score:
                best_row = row
                best_source = source_name
                best_score = score

        learned = self._read_json("learned_candidates.json", {"schema_version": "learned_candidates_v1", "candidates": []})
        for row in learned.get("candidates", []) if isinstance(learned.get("candidates", []), list) else []:
            if not isinstance(row, dict) or str(row.get("status", "") or "") != "pending_review":
                continue
            term = str(row.get("term", row.get("raw_text", "")) or "").strip()
            if term and term.lower() in lowered:
                terms.append(term)
                label = str(row.get("target_label_hint", row.get("target_label", "")) or "").strip()
                if label:
                    terms.append(label)
                if best_score < 0.35:
                    best_row = row
                    best_source = "learned_candidates"
                    best_score = 0.35

        target_hint = self._target_hint_from_row(best_row) if best_row else {}
        return {
            "matched": bool(best_row),
            "terms": _dedupe_terms(terms),
            "source": best_source,
            "confidence": max(0.0, min(1.0, best_score)),
            "trusted": False,
            "target_hint": target_hint,
            "input_channel": str(input_channel or "text"),
            "actor_role": str(actor_role or "normal_user"),
        }

    def lookup_term(self, memory_domain: str, term: str) -> dict[str, Any]:
        domain = str(memory_domain or "").strip()
        clean_term = str(term or "").strip()
        config = self._domain_config(domain)
        if not config:
            return {"ok": False, "found": False, "reason": "unsupported_memory_domain", "term": clean_term}
        if not clean_term:
            return {"ok": False, "found": False, "reason": "empty_term", "term": clean_term}

        local_hit = self._find_term_entry(config["file_name"], config["list_key"], clean_term)
        if local_hit:
            return self._term_lookup_result(clean_term, local_hit, "local")

        seed_file = config.get("seed_file")
        if seed_file:
            seed_hit = self._find_term_entry(str(seed_file), config["list_key"], clean_term)
            if seed_hit:
                return self._term_lookup_result(clean_term, seed_hit, "seed")

        return {
            "ok": True,
            "found": False,
            "term": clean_term,
            "target_label": "",
            "target_label_hint": "",
            "source": "none",
            "entry": {},
        }

    def list_terms_for_target(
        self,
        memory_domain: str,
        target_label: str,
        target_app_id: str = "",
    ) -> dict[str, Any]:
        domain = str(memory_domain or "").strip()
        clean_label = str(target_label or "").strip()
        clean_app_id = str(target_app_id or "").strip()
        config = self._domain_config(domain)
        if not config:
            return {"ok": False, "reason": "unsupported_memory_domain", "target_label": clean_label, "terms": []}
        if not clean_label:
            return {"ok": False, "reason": "empty_target_label", "target_label": clean_label, "terms": []}

        terms: list[dict[str, Any]] = []
        for source, file_name in (("local", config["file_name"]), ("seed", config.get("seed_file", ""))):
            if not file_name:
                continue
            data = self._read_json(str(file_name), {"schema_version": config["schema_version"], config["list_key"]: []})
            rows = data.get(config["list_key"], [])
            if not isinstance(rows, list):
                continue
            for row in rows:
                if not isinstance(row, dict) or not self._row_matches_target(row, clean_label, clean_app_id):
                    continue
                terms.append(
                    {
                        "term": str(row.get("term", "") or ""),
                        "aliases": _dedupe_terms(row.get("aliases", []) if isinstance(row.get("aliases"), list) else []),
                        "source": source,
                        "enabled": bool(row.get("enabled", True)),
                        "target_label": self._row_target_label(row),
                        "target_label_hint": str(row.get("target_label_hint", row.get("target_label", "")) or ""),
                        "target_app_id": str(row.get("target_app_id", "") or ""),
                        "canonical_app_id": str(row.get("canonical_app_id", "") or ""),
                    }
                )

        return {
            "ok": True,
            "target_label": clean_label,
            "target_app_id": clean_app_id,
            "terms": terms,
        }

    def remove_confirmed_term(
        self,
        memory_domain: str,
        term: str,
        target_label: str | None = None,
    ) -> dict[str, Any]:
        domain = str(memory_domain or "").strip()
        clean_term = str(term or "").strip()
        clean_label = str(target_label or "").strip() if target_label is not None else ""
        config = self._domain_config(domain)
        if not config:
            return {"ok": False, "removed": False, "reason": "unsupported_memory_domain", "term": clean_term}
        if not clean_term:
            return {"ok": False, "removed": False, "reason": "empty_term", "term": clean_term}

        data = self._read_json(config["file_name"], {"schema_version": config["schema_version"], config["list_key"]: []})
        rows = data.get(config["list_key"], [])
        if not isinstance(rows, list):
            rows = []

        normalized = _normalize_memory_text(clean_term)
        kept: list[Any] = []
        removed_row: dict[str, Any] = {}
        for row in rows:
            if not isinstance(row, dict) or _normalize_memory_text(row.get("term", "")) != normalized:
                kept.append(row)
                continue
            row_label = self._row_target_label(row)
            if clean_label and _normalize_memory_text(row_label) != _normalize_memory_text(clean_label):
                kept.append(row)
                return {
                    "ok": False,
                    "removed": False,
                    "reason": "target_label_mismatch",
                    "term": clean_term,
                    "target_label": clean_label,
                    "existing_target_label": row_label,
                }
            removed_row = row

        if not removed_row:
            seed_hit = self._find_term_entry(str(config.get("seed_file", "")), config["list_key"], clean_term) if config.get("seed_file") else {}
            if seed_hit:
                return {
                    "ok": False,
                    "removed": False,
                    "reason": "seed_term_read_only",
                    "term": clean_term,
                    "target_label": clean_label or self._row_target_label(seed_hit),
                }
            return {
                "ok": True,
                "removed": False,
                "reason": "not_found",
                "term": clean_term,
                "target_label": clean_label,
            }

        data[config["list_key"]] = kept
        self._write_json(config["file_name"], data)
        return {
            "ok": True,
            "removed": True,
            "reason": "removed",
            "term": clean_term,
            "target_label": self._row_target_label(removed_row),
        }

    def promote_confirmed_term(
        self,
        memory_domain: str,
        term: str,
        target_label: str,
        aliases: list[str] | None = None,
        source_card_id: str = "",
        overwrite: bool = False,
        target_app_id: str = "",
        canonical_app_id: str = "",
    ) -> dict[str, Any]:
        domain = str(memory_domain or "").strip()
        clean_term = str(term or "").strip()
        clean_label = str(target_label or "").strip()
        clean_app_id = str(target_app_id or "").strip()
        clean_canonical_app_id = str(canonical_app_id or "").strip()
        config = self._domain_config(domain)
        if not config:
            return {"ok": False, "reason": "unsupported_memory_domain"}
        if not clean_term:
            return {"ok": False, "reason": "empty_term", "term": clean_term}
        if not clean_label:
            return {"ok": False, "reason": "empty_target_label", "term": clean_term}
        if _normalize_memory_text(clean_term) == _normalize_memory_text(clean_label):
            return {
                "ok": False,
                "reason": "same_as_target_label",
                "term": clean_term,
                "target_label": clean_label,
            }

        data = self._read_json(config["file_name"], {"schema_version": config["schema_version"], config["list_key"]: []})
        rows = data.get(config["list_key"], [])
        if not isinstance(rows, list):
            rows = []
        normalized = _normalize_memory_text(clean_term)
        existing_index = -1
        existing_row: dict[str, Any] = {}
        for index, row in enumerate(rows):
            if isinstance(row, dict) and _normalize_memory_text(row.get("term", "")) == normalized:
                existing_index = index
                existing_row = row
                break

        seed_row = self._find_term_entry(str(config.get("seed_file", "")), config["list_key"], clean_term) if config.get("seed_file") else {}
        conflict_row = existing_row or seed_row
        if conflict_row:
            existing_label = self._row_target_label(conflict_row)
            same_target = _normalize_memory_text(existing_label) == _normalize_memory_text(clean_label)
            if same_target:
                return {
                    "ok": True,
                    "promoted": False,
                    "reason": "already_exists_same_target",
                    "memory_domain": domain,
                    "term": clean_term,
                    "target_label": existing_label,
                    "source": "local" if existing_row else "seed",
                }
            if not overwrite:
                return {
                    "ok": False,
                    "promoted": False,
                    "conflict": True,
                    "reason": "term_bound_to_other_target",
                    "term": clean_term,
                    "target_label": clean_label,
                    "existing_target_label": existing_label,
                    "source": "local" if existing_row else "seed",
                }

        item = {
            "term": clean_term,
            "aliases": _dedupe_terms(aliases or []),
            "target_label": clean_label,
            "target_label_hint": clean_label,
            "target_app_id": clean_app_id,
            "canonical_app_id": clean_canonical_app_id,
            "source": "user_confirmed",
            "source_card_id": str(source_card_id or ""),
            "confidence": 0.82,
            "enabled": True,
            "updated_at": _now_iso(),
        }
        if existing_row and existing_index >= 0:
            old_target = self._row_target_label(existing_row)
            rows[existing_index] = item
            data[config["list_key"]] = rows
            self._write_json(config["file_name"], data)
            return {
                "ok": True,
                "promoted": True,
                "rebind": True,
                "old_target_label": old_target,
                "memory_domain": domain,
                "term": clean_term,
                "target_label": clean_label,
            }

        rows.append(item)
        data[config["list_key"]] = rows
        self._write_json(config["file_name"], data)
        result = {"ok": True, "promoted": True, "memory_domain": domain, "term": clean_term, "target_label": clean_label}
        if seed_row:
            result.update({"rebind": True, "old_target_label": self._row_target_label(seed_row), "shadowed_source": "seed"})
        return result

    def append_session_note(self, note: dict[str, Any]) -> None:
        if not isinstance(note, dict):
            return
        data = self._read_json("session_notes.runtime.json", {"schema_version": "session_notes_v1", "notes": [], "pending_refs": []})
        notes = data.get("notes", [])
        if not isinstance(notes, list):
            notes = []
        item = dict(note)
        item.setdefault("created_at", _now_iso())
        notes.append(item)
        notes = notes[-100:]
        data["notes"] = notes
        self._write_json("session_notes.runtime.json", data)

    def append_learned_candidate(self, candidate: dict[str, Any]) -> None:
        if not isinstance(candidate, dict):
            return
        data = self._read_json("learned_candidates.json", {"schema_version": "learned_candidates_v1", "candidates": []})
        candidates = data.get("candidates", [])
        if not isinstance(candidates, list):
            candidates = []
        item = dict(candidate)
        item.setdefault("status", "pending_review")
        item.setdefault("created_at", _now_iso())
        item.setdefault("trusted", False)
        candidates.append(item)
        data["candidates"] = candidates
        self._write_json("learned_candidates.json", data)

    def _match_terms(self, lowered_text: str, rows: Any, *, term_key: str = "term") -> dict[str, Any]:
        if not isinstance(rows, list):
            return {}
        best: dict[str, Any] = {}
        best_score = 0.0
        for row in rows:
            if not isinstance(row, dict) or not bool(row.get("enabled", True)):
                continue
            term = str(row.get(term_key, "") or "").strip().lower()
            aliases = row.get("aliases", [])
            alias_values = [str(item or "").strip().lower() for item in aliases] if isinstance(aliases, list) else []
            if not term and not alias_values:
                continue
            matched_values = [value for value in [term, *alias_values] if value and value in lowered_text]
            if not matched_values:
                continue
            longest_match = max(matched_values, key=len)
            match_ratio = len(longest_match) / max(1, len(lowered_text))
            exact_bonus = 0.25 if longest_match == lowered_text else 0.0
            score = float(row.get("confidence", 0.5) or 0.5) + 0.10 + (match_ratio * 0.20) + exact_bonus
            if score > best_score:
                best = row
                best_score = score
        return dict(best)

    def _hint(self, source: str, row: dict[str, Any], confidence: float) -> dict[str, Any]:
        row_source = str(row.get("source", "") or "").strip()
        row_confidence = max(0.0, min(1.0, float(row.get("confidence", confidence) or confidence)))
        trusted = bool(row.get("trusted", False)) or row_source in {"user_confirmed", "promoted_memory"}
        if trusted:
            row_confidence = max(row_confidence, 0.85)
        return {
            "matched": True,
            "target_hint": self._target_hint_from_row(row),
            "source": "user_confirmed" if trusted and row_source == "user_confirmed" else source,
            "confidence": row_confidence,
            "trusted": trusted,
        }

    def _empty_hint(self) -> dict[str, Any]:
        return {
            "matched": False,
            "target_hint": {},
            "source": "none",
            "confidence": 0.0,
            "trusted": False,
        }

    def _read_json(self, name: str, fallback: dict[str, Any]) -> dict[str, Any]:
        try:
            path = self.memory_dir / name
            mtime = path.stat().st_mtime
            cache_key = str(path)
            cached = self._json_cache.get(cache_key)
            if cached and cached[0] == mtime:
                return dict(cached[1])
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                self._json_cache[cache_key] = (mtime, data)
                return dict(data)
            return data if isinstance(data, dict) else dict(fallback)
        except Exception:
            return dict(fallback)

    def _write_json(self, name: str, data: dict[str, Any]) -> None:
        try:
            self.memory_dir.mkdir(parents=True, exist_ok=True)
            (self.memory_dir / name).write_text(
                json.dumps(data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            self._json_cache.pop(str(self.memory_dir / name), None)
        except Exception:
            return

    def _default_policy(self) -> dict[str, Any]:
        return {
            "schema_version": "command_memory_policy_v1",
            "allow_memory_as_permission": False,
            "allow_memory_as_backend_decision": False,
            "allow_llm_hint_as_execution_target": False,
            "expose_debug_to_normal_user": False,
            "expose_debug_to_developer": True,
            "session_notes_ttl_seconds": 3600,
            "learned_candidates_require_confirmation": True,
        }

    def _target_hint_from_row(self, row: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(row, dict):
            return {}
        return {
            "term": str(row.get("term", "") or ""),
            "aliases": _dedupe_terms(row.get("aliases", []) if isinstance(row.get("aliases"), list) else []),
            "target_label": str(row.get("target_label", row.get("target_label_hint", row.get("label", ""))) or ""),
            "target_label_hint": str(row.get("target_label_hint", row.get("target_label", row.get("label", ""))) or ""),
            "target_app_id": str(row.get("target_app_id", "") or ""),
            "target_kind_hint": str(row.get("target_kind_hint", "") or ""),
            "source": str(row.get("source", "") or ""),
        }

    def _domain_config(self, domain: str) -> dict[str, Any]:
        configs = {
            "software_terms": {
                "file_name": "software_terms.local.json",
                "seed_file": "software_terms.seed.json",
                "list_key": "terms",
                "schema_version": "software_terms_v1",
            },
            "file_terms": {
                "file_name": "file_terms.local.json",
                "seed_file": "file_terms.seed.json",
                "list_key": "terms",
                "schema_version": "file_terms_v1",
            },
            "user_habits": {
                "file_name": "user_habits.local.json",
                "seed_file": "",
                "list_key": "habits",
                "schema_version": "user_habits_v1",
            },
        }
        return dict(configs.get(str(domain or "").strip(), {}))

    def _find_term_entry(self, file_name: str, list_key: str, term: str) -> dict[str, Any]:
        if not file_name:
            return {}
        data = self._read_json(file_name, {"schema_version": "", list_key: []})
        rows = data.get(list_key, [])
        if not isinstance(rows, list):
            return {}
        normalized = _normalize_memory_text(term)
        for row in rows:
            if isinstance(row, dict) and _normalize_memory_text(row.get("term", "")) == normalized:
                return dict(row)
        return {}

    def _term_lookup_result(self, term: str, entry: dict[str, Any], source: str) -> dict[str, Any]:
        return {
            "ok": True,
            "found": True,
            "term": term,
            "target_label": self._row_target_label(entry),
            "target_label_hint": str(entry.get("target_label_hint", entry.get("target_label", "")) or ""),
            "source": source,
            "entry": dict(entry),
        }

    def _row_target_label(self, row: dict[str, Any]) -> str:
        if not isinstance(row, dict):
            return ""
        return str(row.get("target_label", row.get("target_label_hint", row.get("label", ""))) or "").strip()

    def _row_matches_target(self, row: dict[str, Any], target_label: str, target_app_id: str = "") -> bool:
        if not isinstance(row, dict):
            return False
        row_label = self._row_target_label(row)
        if _normalize_memory_text(row_label) != _normalize_memory_text(target_label):
            return False
        clean_app_id = str(target_app_id or "").strip()
        if not clean_app_id:
            return True
        return clean_app_id in {
            str(row.get("target_app_id", "") or "").strip(),
            str(row.get("canonical_app_id", "") or "").strip(),
        }


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _dedupe_terms(values: list[Any] | Any) -> list[str]:
    items = values if isinstance(values, list) else [values]
    result: list[str] = []
    seen: set[str] = set()
    for value in items:
        text = str(value or "").strip()
        if not text:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(text)
    return result


def _normalize_memory_text(value: Any) -> str:
    text = str(value or "").strip().casefold()
    if not text:
        return ""
    keep: list[str] = []
    for char in text:
        if char.isalnum() or "\u4e00" <= char <= "\u9fff":
            keep.append(char)
    return "".join(keep)


def _memory_similarity(left: str, right: str) -> float:
    a = _normalize_memory_text(left)
    b = _normalize_memory_text(right)
    if not a or not b:
        return 0.0
    score = SequenceMatcher(None, a, b).ratio()

    # 短中文词里 1 个字的 ASR/输入差异会被 SequenceMatcher 压得过低。
    # 这里做通用短词补偿，不绑定任何具体软件名或别名。
    if 2 <= len(a) <= 4 and 2 <= len(b) <= 4:
        common = len(set(a) & set(b))
        if common >= min(len(a), len(b)) - 1:
            score = max(score, 0.80)

    return max(0.0, min(1.0, score))
