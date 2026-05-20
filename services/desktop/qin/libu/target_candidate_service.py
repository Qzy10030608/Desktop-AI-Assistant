from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import uuid4


OPEN_ACTIONS = {"file.open", "app.launch"}


def build_candidate_request(task_draft: dict[str, Any]) -> dict[str, Any]:
    task = task_draft if isinstance(task_draft, dict) else {}
    action = str(task.get("action", "") or "").strip()
    target = task.get("target", {}) if isinstance(task.get("target"), dict) else {}

    if action == "file.open":
        source_plan = [
            "recent_context",
            "yushitai_summary",
            "file_view_cache",
            "allowed_paths_only",
        ]
    elif action == "app.launch":
        source_plan = [
            "registry_service",
            "software_ledger",
            "software_view_cache",
        ]
    else:
        source_plan = []

    return {
        "schema_version": "target_candidate_request_v1",
        "request_id": f"candidate_req_{uuid4().hex}",
        "task_id": str(task.get("task_id", "") or ""),
        "action": action,
        "target_hint": _target_hint(target),
        "source_plan": source_plan,
        "dry_run_only": True,
        "execution_allowed": False,
        "note": "First stage only builds candidate request; it does not search the full disk, open files, or launch apps.",
    }


def build_candidate_result(task_draft: dict[str, Any], context_pack: dict[str, Any] | None = None) -> dict[str, Any]:
    task = task_draft if isinstance(task_draft, dict) else {}
    action = str(task.get("action", "") or "").strip()
    request = build_candidate_request(task)
    candidates: list[dict[str, Any]]
    status = "unsupported_action"
    message = "This action does not use Libu opening candidates."

    if action == "file.open":
        candidates, status, message = _file_open_candidates(task)
    elif action == "app.launch":
        candidates, status, message = _app_launch_candidates(task)

    normalized = normalize_candidates(candidates)
    if status not in {"need_user_clarification", "unsupported_action"}:
        if len(normalized) == 1:
            status = "candidate_ready"
            message = "One dry-run candidate is ready. No real action was executed."
        elif len(normalized) > 1:
            status = "pending_user_choice"
            message = "Multiple dry-run candidates were found. User choice is required."
        else:
            status = "need_user_clarification"
            message = "No safe dry-run candidate could be built from the target hint."

    return {
        "schema_version": "target_candidate_result_v1",
        "request": request,
        "task_id": str(task.get("task_id", "") or ""),
        "action": action,
        "status": status,
        "message": message,
        "candidate_count": len(normalized),
        "candidates": normalized,
        "context_pack_used": bool(context_pack),
        "dry_run_only": True,
        "execution_allowed": False,
    }

def decide_app_launch_candidate_status(
    query: dict[str, Any],
    candidates: list[dict[str, Any]],
    *,
    input_channel: str = "text",
) -> dict[str, Any]:
    """
    app.launch 候选六态判断。
    这里只判断，不执行、不授权、不写入系统。
    """
    medium_confidence = 0.52
    high_confidence = 0.84 if input_channel == "voice" else 0.74

    if not query.get("raw") and not query.get("name_hint") and not query.get("app_hint"):
        return {
            "status": "need_clarification",
            "selected_candidate": None,
            "reason": "missing_query",
            "best_score": 0.0,
            "medium_confidence": medium_confidence,
            "high_confidence": high_confidence,
            "top_count": 0,
        }

    if not candidates:
        return {
            "status": "not_found",
            "selected_candidate": None,
            "reason": "no_candidates",
            "best_score": 0.0,
            "medium_confidence": medium_confidence,
            "high_confidence": high_confidence,
            "top_count": 0,
        }

    best_score = float(candidates[0].get("score", 0.0) or 0.0)

    if best_score < medium_confidence:
        return {
            "status": "need_clarification",
            "selected_candidate": None,
            "reason": "below_medium_confidence",
            "best_score": best_score,
            "medium_confidence": medium_confidence,
            "high_confidence": high_confidence,
            "top_count": len(candidates),
        }

    top = [
        item for item in candidates
        if best_score - float(item.get("score", 0.0) or 0.0) < 0.08
    ]

    if len(top) > 1:
        return {
            "status": "multiple_candidates",
            "selected_candidate": None,
            "reason": "multiple_close_scores",
            "best_score": best_score,
            "medium_confidence": medium_confidence,
            "high_confidence": high_confidence,
            "top_count": len(top),
        }

    selected = candidates[0]

    if bool(query.get("llm_hint_requires_confirmation", False)):
        return {
            "status": "need_confirmation",
            "selected_candidate": selected,
            "reason": "llm_target_hint_requires_confirmation",
            "best_score": best_score,
            "medium_confidence": medium_confidence,
            "high_confidence": high_confidence,
            "top_count": 1,
        }

    if best_score < high_confidence:
        return {
            "status": "need_confirmation",
            "selected_candidate": selected,
            "reason": "medium_confidence_need_confirmation",
            "best_score": best_score,
            "medium_confidence": medium_confidence,
            "high_confidence": high_confidence,
            "top_count": 1,
        }

    permission = _permission_value(selected)
    if permission in {"unset", "unknown", "deny", ""}:
        return {
            "status": "need_permission",
            "selected_candidate": selected,
            "reason": "permission_not_allowed",
            "best_score": best_score,
            "medium_confidence": medium_confidence,
            "high_confidence": high_confidence,
            "top_count": 1,
            "permission_state": permission or "unset",
        }

    return {
        "status": "resolved_unique",
        "selected_candidate": selected,
        "reason": "high_confidence_permission_allowed",
        "best_score": best_score,
        "medium_confidence": medium_confidence,
        "high_confidence": high_confidence,
        "top_count": 1,
        "permission_state": permission,
    }

def resolve_app_launch_target(
    task: dict[str, Any],
    context_pack: dict[str, Any] | None = None,
    *,
    project_root: str | Path | None = None,
) -> dict[str, Any]:
    payload = task if isinstance(task, dict) else {}
    query: dict[str, Any] = _app_launch_target_query(payload)
    memory_hint = _expand_app_query_terms(query, payload)
    query["expanded_terms"] = memory_hint.get("terms", []) if isinstance(memory_hint.get("terms"), list) else []
    query["memory_source"] = str(memory_hint.get("source", "none") or "none")
    query["memory_confidence"] = str(memory_hint.get("confidence", 0.0) or 0.0)
    rows = _read_software_rows(project_root)
    exact_decision = _resolve_exact_app_hint(payload, query, rows)
    if exact_decision:
        selected_exact = exact_decision.get("selected_candidate")
        candidates = [selected_exact] if isinstance(selected_exact, dict) else []
        decision = exact_decision
    else:
        candidates = _match_app_launch_candidates(query, rows)
        decision = decide_app_launch_candidate_status(
            query,
            candidates,
            input_channel=_input_channel(payload),
        )

    status = str(decision.get("status", "") or "not_found")
    selected = decision.get("selected_candidate")
    if not isinstance(selected, dict):
        selected = None

    debug = {
        "row_count": len(rows),
        "candidate_count": len(candidates),
        "decision_reason": str(decision.get("reason", "") or ""),
        "best_score": float(decision.get("best_score", 0.0) or 0.0),
        "medium_confidence": float(decision.get("medium_confidence", 0.0) or 0.0),
        "high_confidence": float(decision.get("high_confidence", 0.0) or 0.0),
        "top_count": int(decision.get("top_count", 0) or 0),
    }

    if "permission_state" in decision:
        debug["permission_state"] = str(decision.get("permission_state", "") or "")

    if str(decision.get("reason", "") or "") == "target_label_hint_exact_permission_allowed":
        selected_label = str((selected or {}).get("label", "") or "")
        permission = str(decision.get("permission_state", "") or "")
        print(
            "[AppLaunchCandidate] exact_hint_match "
            f"query={str(query.get('normalized_target') or query.get('name_hint') or query.get('raw') or '')!r} "
            f"hint={str(decision.get('matched_hint', '') or '')!r} "
            f"selected={selected_label!r} "
            f"permission={permission!r} "
            "reason='target_label_hint_exact_permission_allowed'"
        )

    print(
        "[AppLaunchCandidate] "
        f"query={str(query.get('normalized_target') or query.get('name_hint') or query.get('raw') or '')!r} "
        f"llm_hint={str(query.get('llm_target_label_hint', '') or '')!r} "
        f"candidate_count={len(candidates)} "
        f"decision={status!r} "
        f"reason={debug.get('decision_reason', '')!r}"
    )

    result = _app_launch_result(
        status,
        query,
        candidates,
        selected,
        "",
        debug,
    )
    _append_app_candidate_card(result)
    return result

def build_real_app_candidate_result(
    task: dict[str, Any],
    context_pack: dict[str, Any] | None = None,
    *,
    project_root: str | Path | None = None,
) -> dict[str, Any]:
    return resolve_app_launch_target(task, context_pack=context_pack, project_root=project_root)


def make_pending_user_choice(
    task_draft: dict[str, Any],
    candidates: list[dict[str, Any]] | None = None,
    message: str = "",
) -> dict[str, Any]:
    task = task_draft if isinstance(task_draft, dict) else {}
    safe_candidates = normalize_candidates(candidates or [])
    return {
        "schema_version": "pending_user_choice_v1",
        "pending_task_id": f"pending_{uuid4().hex}",
        "task_id": str(task.get("task_id", "") or ""),
        "action": str(task.get("action", "") or ""),
        "status": "pending_user_choice",
        "message": message or "Multiple candidates need user choice.",
        "candidates": safe_candidates,
        "execution_allowed": False,
    }


def normalize_candidates(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for index, candidate in enumerate(candidates, start=1):
        if not isinstance(candidate, dict):
            continue
        source = candidate.get("source", [])
        if isinstance(source, str):
            source = [source]
        if not isinstance(source, list):
            source = []
        item = {
            "candidate_id": str(candidate.get("candidate_id", f"cand_{index:03d}") or f"cand_{index:03d}"),
            "display_index": int(candidate.get("display_index", index) or index),
            "label": str(candidate.get("label", "") or ""),
            "kind": str(candidate.get("kind", "") or ""),
            "safe_location": str(candidate.get("safe_location", "") or ""),
            "file_ext": str(candidate.get("file_ext", "") or ""),
            "modified_hint": str(candidate.get("modified_hint", "") or ""),
            "score": float(candidate.get("score", 0.0) or 0.0),
            "source": [str(item) for item in source if str(item or "").strip()],
            "permission_state": str(candidate.get("permission_state", "unknown") or "unknown"),
            "recommended": bool(candidate.get("recommended", False)),
        }
        for key in (
            "app_id",
            "canonical_app_id",
            "target_path",
            "shell_entry",
            "launch_target_raw",
            "launch_target_kind",
            "process_name",
            "process_names",
            "effective_permission_state",
            "can_launch",
            "permission_source",
            "permission_source_type",
            "permission_source_key",
        ):
            if key in candidate:
                item[key] = candidate[key]
        normalized.append(item)
    return normalized


def _app_launch_target_query(task: dict[str, Any]) -> dict[str, Any]:
    target = task.get("target", {}) if isinstance(task.get("target"), dict) else {}
    arguments = task.get("arguments", {}) if isinstance(task.get("arguments"), dict) else {}
    summary = task.get("original_puzzle_summary", {}) if isinstance(task.get("original_puzzle_summary"), dict) else {}

    understanding = (
        arguments.get("understanding_packet", {})
        if isinstance(arguments.get("understanding_packet"), dict)
        else {}
    )
    evidence = understanding.get("evidence", {}) if isinstance(understanding.get("evidence"), dict) else {}
    llm_hint = evidence.get("llm_hint", {}) if isinstance(evidence.get("llm_hint"), dict) else {}
    llm_target_label_hint = str(llm_hint.get("target_label_hint", "") or "").strip()

    normalized_target = str(
        arguments.get("normalized_target", "")
        or understanding.get("target_normalized", "")
        or summary.get("target_normalized", "")
        or ""
    ).strip()

    memory_terms = evidence.get("memory_terms", []) if isinstance(evidence.get("memory_terms"), list) else []

    values: list[str] = []

    def add(value: Any) -> None:
        text = str(value or "").strip()
        if text and text not in values:
            values.append(text)

    add(normalized_target)
    add(llm_target_label_hint)

    for item in memory_terms:
        add(item)

    add(task.get("target_name", ""))
    add(arguments.get("target_name", ""))
    add(arguments.get("app_name", ""))
    add(arguments.get("app_hint", ""))
    add(target.get("name_hint", ""))
    add(target.get("app_hint", ""))
    add(summary.get("raw_user_text", ""))

    raw = " ".join(values).strip()
    cleaned = _clean_app_query(raw)

    app_hint_source = (
        normalized_target
        or str(target.get("app_hint", "") or "")
        or str(arguments.get("app_hint", "") or "")
        or cleaned
    )
    app_hint = _clean_app_query(app_hint_source) or cleaned

    return {
        "raw": raw,
        "name_hint": cleaned,
        "app_hint": app_hint,
        "normalized_target": normalized_target,
        "llm_target_label_hint": llm_target_label_hint,
        "llm_hint_requires_confirmation": bool(llm_target_label_hint),
        "expanded_terms": memory_terms,
    }

def _unique_join(values: list[str]) -> str:
    parts: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value or "").strip()
        if not text:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        parts.append(text)
    return " ".join(parts).strip()


def _clean_app_query(text: str) -> str:
    result = str(text or "").strip()
    for token in ("打开", "启动", "运行", "开启", "软件", "程序", "应用", "帮我", "请"):
        result = result.replace(token, " ")
    return " ".join(result.split()).strip()


def _read_software_rows(project_root: str | Path | None = None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        from services.desktop.software_view_cache_service import SoftwareViewCacheService

        state = SoftwareViewCacheService(project_root).read()
        cache_rows = state.get("rows", []) if isinstance(state.get("rows", []), list) else []
        for row in cache_rows:
            if isinstance(row, dict):
                item = dict(row)
                item.setdefault("_source", "software_view_cache")
                rows.append(item)
    except Exception:
        pass

    if rows:
        return rows

    try:
        from services.desktop.qin.libu.software_ledger import SoftwareCandidateBook, SoftwareTrustedBook

        for source, book in (
            ("software_trusted_book", SoftwareTrustedBook(project_root)),
            ("software_candidate_book", SoftwareCandidateBook(project_root)),
        ):
            for record in book.read():
                item = record.to_dict()
                item["_source"] = source
                rows.append(item)
    except Exception:
        pass

    return rows


APP_QUERY_ALIASES = {
    "记事本": ["记事本", "notepad", "windows notepad"],
    "画图": ["画图", "paint", "mspaint"],
    "计算器": ["计算器", "calculator", "calc"],
    "浏览器": ["浏览器", "browser", "edge", "chrome"],
}


def _match_app_launch_candidates(query: dict[str, Any], rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    query_text = " ".join(
        str(query.get(key, "") or "")
        for key in ("normalized_target", "llm_target_label_hint", "raw", "name_hint", "app_hint")
    ).strip().lower()
    terms = _query_terms(query_text, query.get("expanded_terms", []))
    candidates: list[dict[str, Any]] = []
    for row in rows:
        score = _row_match_score(row, terms)
        if score <= 0:
            continue
        candidates.append(_app_launch_candidate_from_row(row, score, len(candidates) + 1))
    candidates.sort(key=lambda item: float(item.get("score", 0.0) or 0.0), reverse=True)
    for index, candidate in enumerate(candidates, start=1):
        candidate["display_index"] = index
        candidate["recommended"] = index == 1
    return candidates


def _resolve_exact_app_hint(
    task: dict[str, Any],
    query: dict[str, Any],
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    hints = _exact_app_hint_values(task)
    if not hints:
        return {}
    for hint in hints:
        normalized_hint = _normalize_app_exact_label(hint)
        if not normalized_hint:
            continue
        for row in rows:
            title = str(row.get("title", "") or "").strip()
            if not title:
                title = str(row.get("app_id", "") or "").strip()
            if not title:
                continue
            if title != hint and _normalize_app_exact_label(title) != normalized_hint:
                continue

            candidate = _app_launch_candidate_from_row(row, 1.0, 1)
            candidate["display_index"] = 1
            candidate["recommended"] = True
            permission = _permission_value(candidate)
            if permission in {"allow", "once", "restricted"}:
                return {
                    "status": "resolved_unique",
                    "selected_candidate": candidate,
                    "reason": "target_label_hint_exact_permission_allowed",
                    "best_score": 1.0,
                    "medium_confidence": 0.0,
                    "high_confidence": 0.0,
                    "top_count": 1,
                    "permission_state": permission,
                    "matched_hint": hint,
                }
            return {
                "status": "need_permission",
                "selected_candidate": candidate,
                "reason": "target_label_hint_exact_permission_not_allowed",
                "best_score": 1.0,
                "medium_confidence": 0.0,
                "high_confidence": 0.0,
                "top_count": 1,
                "permission_state": permission or "unset",
                "matched_hint": hint,
            }
    return {}


def _exact_app_hint_values(task: dict[str, Any]) -> list[str]:
    payload = task if isinstance(task, dict) else {}
    target = payload.get("target", {}) if isinstance(payload.get("target"), dict) else {}
    arguments = payload.get("arguments", {}) if isinstance(payload.get("arguments"), dict) else {}
    values: list[str] = []

    def add(value: Any) -> None:
        text = str(value or "").strip()
        if text and text not in values:
            values.append(text)

    add(arguments.get("target_label_hint", ""))
    add(arguments.get("llm_target_hint", ""))
    add(target.get("label_hint", ""))
    add(target.get("app_hint", ""))
    add(target.get("name_hint", ""))
    add(payload.get("target_label_hint", ""))
    if isinstance(payload.get("target"), str):
        add(payload.get("target", ""))
    return values


def _normalize_app_exact_label(value: Any) -> str:
    return "".join(str(value or "").strip().casefold().split())


def _query_terms(query_text: str, expanded_terms: Any = None) -> list[str]:
    terms = [item for item in query_text.replace("　", " ").split() if item]
    compact = query_text.replace(" ", "")
    if compact:
        terms.append(compact)
    if isinstance(expanded_terms, list):
        terms.extend(str(item) for item in expanded_terms if str(item or "").strip())
    return sorted({term.strip().lower() for term in terms if term.strip()}, key=len, reverse=True)


def _row_match_score(row: dict[str, Any], terms: list[str]) -> float:
    if not terms:
        return 0.0
    haystack_parts = [
        row.get("title", ""),
        row.get("name", ""),
        row.get("app_id", ""),
        row.get("canonical_app_id", ""),
        row.get("target_path", ""),
        row.get("effective_target_path", ""),
        row.get("launch_target_raw", ""),
        row.get("effective_launch_target_raw", ""),
        row.get("entry_path", ""),
        row.get("install_dir", ""),
        row.get("platform_object_id", ""),
    ]
    haystack = " ".join(str(item or "") for item in haystack_parts).lower()
    compact_haystack = haystack.replace(" ", "")
    best = 0.0
    for term in terms:
        compact_term = term.replace(" ", "")
        if not term:
            continue
        if term == str(row.get("app_id", "") or "").strip().lower():
            best = max(best, 1.0)
        elif term == str(row.get("canonical_app_id", "") or "").strip().lower():
            best = max(best, 0.98)
        elif term in haystack:
            best = max(best, 0.88 if len(term) >= 4 else 0.76)
        elif compact_term and compact_term in compact_haystack:
            best = max(best, 0.82)
    return best


def _app_launch_candidate_from_row(row: dict[str, Any], score: float, index: int) -> dict[str, Any]:
    launch_raw = str(row.get("effective_launch_target_raw", row.get("launch_target_raw", "")) or "").strip()
    launch_kind = str(row.get("effective_launch_target_kind", row.get("launch_target_kind", "")) or "").strip()
    target_path = str(row.get("effective_target_path", row.get("target_path", "")) or "").strip()
    permission_state = _normalize_permission(row.get("permission_state_raw", row.get("permission_state", "unset")))
    effective_permission = _normalize_permission(row.get("effective_permission_state", permission_state))
    process_name = _process_name_from_path(target_path)
    source = str(row.get("_source", "software_view_cache") or "software_view_cache")
    return {
        "candidate_id": str(row.get("app_id", "") or f"app_candidate_{index:03d}"),
        "display_index": index,
        "label": str(row.get("title", row.get("name", row.get("app_id", ""))) or ""),
        "app_id": str(row.get("app_id", "") or ""),
        "canonical_app_id": str(row.get("canonical_app_id", row.get("app_id", "")) or ""),
        "kind": "app",
        "target_path": target_path,
        "shell_entry": launch_raw,
        "launch_target_raw": launch_raw,
        "launch_target_kind": launch_kind,
        "process_name": process_name,
        "process_names": [process_name] if process_name else [],
        "permission_state": permission_state,
        "effective_permission_state": effective_permission,
        "can_launch": bool(row.get("can_launch", False)),
        "source": [source],
        "score": float(score),
        "recommended": False,
        "permission_source": source,
        "permission_source_type": "software_governance",
        "permission_source_key": str(row.get("app_id", "") or ""),
    }


def _normalize_permission(value: Any) -> str:
    text = str(value or "unset").strip().lower() or "unset"
    if text in {"\u662f", "\u5141\u8bb8"}:
        return "allow"
    if text in {"\u53d7\u9650"}:
        return "once"
    if text in {"\u5426", "\u62d2\u7edd"}:
        return "deny"
    if text in {"allow", "once", "restricted", "deny", "unset", "unknown"}:
        return "once" if text == "restricted" else text
    return "unknown"


def _permission_value(candidate: dict[str, Any]) -> str:
    return _normalize_permission(candidate.get("effective_permission_state", candidate.get("permission_state", "unset")))


def _process_name_from_path(path_text: str) -> str:
    try:
        name = Path(str(path_text or "")).name
        return name if name.lower().endswith(".exe") else ""
    except Exception:
        return ""


def _app_launch_result(
    status: str,
    query: dict[str, Any],
    candidates: list[dict[str, Any]],
    selected: dict[str, Any] | None,
    message: str,
    debug: dict[str, Any] | None = None,
) -> dict[str, Any]:
    message_key = _app_launch_message_key(status)
    message_params = {
        "target": str((selected or {}).get("label", "") or query.get("name_hint") or query.get("app_hint") or query.get("raw") or ""),
        "candidate_count": len(candidates),
    }
    choice_type = "none"
    ui_prompt_type = "none"
    if status == "multiple_candidates":
        choice_type = "app_launch_candidate"
        ui_prompt_type = "choose_one"
    elif status == "need_confirmation":
        choice_type = "app_launch_confirmation"
        ui_prompt_type = "confirm_or_choose"
    return {
        "schema_version": "target_candidate_result_v1",
        "action": "app.launch",
        "resolution_status": status,
        "decision": status,
        "requires_user_response": status in {"multiple_candidates", "need_confirmation", "need_clarification"},
        "choice_type": choice_type,
        "ui_prompt_type": ui_prompt_type,
        "target_query": query,
        "candidates": candidates,
        "selected_candidate": selected or None,
        "safe_user_message": message,
        "message_key": message_key,
        "message_params": message_params,
        "ui_actions": _ui_actions_for_app_launch(status),
        "debug_summary": debug or {},
        "execution_allowed": status == "resolved_unique",
    }


def _app_launch_message_key(status: str) -> str:
    return {
        "resolved_unique": "desktop.app.launch.candidate_ready",
        "need_confirmation": "desktop.app.launch.need_confirmation",
        "multiple_candidates": "desktop.app.launch.pending_choice",
        "need_permission": "desktop.app.launch.need_permission",
        "not_found": "desktop.app.launch.not_found",
        "need_clarification": "desktop.app.launch.need_clarification",
    }.get(str(status or ""), "desktop.app.launch.failed")


def _ui_actions_for_app_launch(status: str) -> list[dict[str, str]]:
    if status == "need_confirmation":
        return [
            {"action": "confirm", "label_key": "desktop.ui.action.confirm_open"},
            {"action": "cancel", "label_key": "desktop.ui.action.cancel"},
        ]
    if status == "multiple_candidates":
        return [
            {"action": "choose_first", "label_key": "desktop.ui.action.choose_first"},
            {"action": "cancel", "label_key": "desktop.ui.action.cancel"},
        ]
    return []


def _input_channel(task: dict[str, Any]) -> str:
    arguments = task.get("arguments", {}) if isinstance(task.get("arguments"), dict) else {}
    value = str(arguments.get("input_channel", task.get("input_channel", "")) or "").strip().lower()
    return "voice" if value == "voice" else "text"


def _expand_app_query_terms(query: dict[str, Any], task: dict[str, Any]) -> dict[str, Any]:

    raw = " ".join(
        str(query.get(key, "") or "")
        for key in ("normalized_target", "llm_target_label_hint", "raw", "name_hint", "app_hint")
    ).strip()
    try:
        from services.desktop.tianting.command_memory_service import CommandMemoryService

        return CommandMemoryService().expand_target_terms(
            raw,
            action_hint="app.launch",
            input_channel=_input_channel(task),
            actor_role=str((task.get("arguments", {}) if isinstance(task.get("arguments"), dict) else {}).get("actor_role", "normal_user") or "normal_user"),
        )
    except Exception:
        return {
            "matched": False,
            "terms": [raw] if raw else [],
            "source": "none",
            "confidence": 0.0,
            "trusted": False,
            "target_hint": {},
        }


def _append_app_candidate_card(result: dict[str, Any]) -> None:
    try:
        query = result.get("target_query", {}) if isinstance(result.get("target_query"), dict) else {}
        candidates = result.get("candidates", []) if isinstance(result.get("candidates"), list) else []
        selected = result.get("selected_candidate", {}) if isinstance(result.get("selected_candidate"), dict) else {}
        from services.desktop.tianting.command_memory_card_service import append_candidate_card

        append_candidate_card(
            action="app.launch",
            raw_target=str(query.get("raw", "") or query.get("name_hint", "") or query.get("app_hint", "") or ""),
            expanded_terms=query.get("expanded_terms", []) if isinstance(query.get("expanded_terms"), list) else [],
            candidates=candidates,
            score=float((selected or candidates[0] if candidates else {}).get("score", 0.0) or 0.0),
            permission_state=str((selected or {}).get("effective_permission_state", (selected or {}).get("permission_state", "")) or ""),
            source=["libu_target_candidate_service", str(query.get("memory_source", "none") or "none")],
        )
    except Exception:
        return


def _target_hint(target: dict[str, Any]) -> dict[str, Any]:
    return {
        "kind": str(target.get("kind", "") or ""),
        "name_hint": str(target.get("name_hint", "") or ""),
        "app_hint": str(target.get("app_hint", "") or ""),
        "time_hint": str(target.get("time_hint", "") or ""),
        "format_hint": str(target.get("format_hint", "") or ""),
        "identity": str(target.get("identity", "") or ""),
    }


def _combined_target_text(task: dict[str, Any]) -> str:
    target = task.get("target", {}) if isinstance(task.get("target"), dict) else {}
    summary = task.get("original_puzzle_summary", {}) if isinstance(task.get("original_puzzle_summary"), dict) else {}
    return " ".join([
        str(target.get("name_hint", "") or ""),
        str(target.get("app_hint", "") or ""),
        str(target.get("time_hint", "") or ""),
        str(target.get("format_hint", "") or ""),
        str(target.get("identity", "") or ""),
        str(summary.get("raw_user_text", "") or ""),
    ]).strip()


def _file_open_candidates(task: dict[str, Any]) -> tuple[list[dict[str, Any]], str, str]:
    text = _combined_target_text(task)
    if not text:
        return [], "need_user_clarification", "File open needs a target name hint."

    project_words = ("项目", "说明", "文档", "报告")
    if any(word in text for word in project_words):
        return [
            {
                "candidate_id": "cand_001",
                "display_index": 1,
                "label": "项目说明_修正版.docx",
                "kind": "file",
                "safe_location": "个人AI设计/docs",
                "file_ext": ".docx",
                "modified_hint": "最近修改",
                "score": 0.91,
                "source": ["dry_run", "task_hint"],
                "permission_state": "unknown",
                "recommended": True,
            },
            {
                "candidate_id": "cand_002",
                "display_index": 2,
                "label": "个人AI助手_LLM桌面连接中间层方案.json",
                "kind": "file",
                "safe_location": "个人AI设计/docs",
                "file_ext": ".json",
                "modified_hint": "设计文件",
                "score": 0.84,
                "source": ["dry_run", "task_hint"],
                "permission_state": "unknown",
                "recommended": False,
            },
            {
                "candidate_id": "cand_003",
                "display_index": 3,
                "label": "个人AI助手设计_4.0版本_完整详细结构图.docx",
                "kind": "file",
                "safe_location": "个人AI设计/docs",
                "file_ext": ".docx",
                "modified_hint": "较早设计",
                "score": 0.73,
                "source": ["dry_run", "task_hint"],
                "permission_state": "unknown",
                "recommended": False,
            },
        ], "pending_user_choice", "Multiple dry-run file candidates were generated."

    label = f"{text[:32]}".strip() or "目标文件"
    return [
        {
            "candidate_id": "cand_001",
            "display_index": 1,
            "label": label,
            "kind": "file",
            "safe_location": "安全摘要位置待吏部补全",
            "file_ext": "",
            "modified_hint": "",
            "score": 0.62,
            "source": ["dry_run", "task_hint"],
            "permission_state": "unknown",
            "recommended": True,
        }
    ], "candidate_ready", "One dry-run file candidate was generated."


def _app_launch_candidates(task: dict[str, Any]) -> tuple[list[dict[str, Any]], str, str]:
    text = _combined_target_text(task).lower()
    if not text:
        return [], "need_user_clarification", "App launch needs an app target hint."

    if "浏览器" in text or "browser" in text:
        return [_app_candidate("cand_001", 1, "默认浏览器", "system default", 0.89, True)], "candidate_ready", "Default browser dry-run candidate."
    if "steam" in text:
        return [_app_candidate("cand_001", 1, "Steam", "软件治理区", 0.9, True)], "candidate_ready", "Steam dry-run candidate."
    if "vscode" in text or "vs code" in text or "code" in text:
        return [_app_candidate("cand_001", 1, "Visual Studio Code", "软件治理区", 0.88, True)], "candidate_ready", "VSCode dry-run candidate."

    return [_app_candidate("cand_001", 1, text[:32] or "目标软件", "软件治理区待吏部补全", 0.55, True)], "candidate_ready", "Generic app dry-run candidate."


def _app_candidate(candidate_id: str, index: int, label: str, location: str, score: float, recommended: bool) -> dict[str, Any]:
    return {
        "candidate_id": candidate_id,
        "display_index": index,
        "label": label,
        "kind": "app",
        "safe_location": location,
        "file_ext": "",
        "modified_hint": "",
        "score": score,
        "source": ["dry_run", "software_hint"],
        "permission_state": "unknown",
        "recommended": recommended,
    }
