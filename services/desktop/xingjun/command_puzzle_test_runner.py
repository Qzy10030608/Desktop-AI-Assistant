from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from services.desktop.xingjun.llm_bridge_dry_run import dry_run_followup, dry_run_user_text


def run_test_cases(test_cases: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    cases = test_cases if test_cases is not None else _load_default_cases()
    results: list[dict[str, Any]] = []
    last_pending_task_id = ""
    for item in cases:
        if isinstance(item, dict):
            raw_user_text = str(item.get("raw_user_text", "") or "")
            actor_role = str(item.get("actor_role", "normal_user") or "normal_user")
            input_channel = str(item.get("input_channel", "text") or "text")
            followup = str(item.get("followup", "") or "")
            use_last_pending = bool(item.get("use_last_pending", False))
        else:
            raw_user_text = str(item or "")
            actor_role = "normal_user"
            input_channel = "text"
            followup = ""
            use_last_pending = False

        if followup:
            dry_result = dry_run_user_text(raw_user_text, actor_role=actor_role, input_channel=input_channel)
            pending_task_id = str(dry_result.get("pending_task_id", "") or "")
            follow_result = dry_run_followup(followup, pending_task_id or None)
            results.append(_result_row(raw_user_text, dry_result, followup_result=follow_result, followup=followup))
            last_pending_task_id = pending_task_id or last_pending_task_id
            continue

        if use_last_pending:
            follow_result = dry_run_followup(raw_user_text, last_pending_task_id or None)
            results.append(_followup_row(raw_user_text, follow_result))
            continue

        dry_result = dry_run_user_text(raw_user_text, actor_role=actor_role, input_channel=input_channel)
        last_pending_task_id = str(dry_result.get("pending_task_id", "") or "") or last_pending_task_id
        results.append(_result_row(raw_user_text, dry_result))
    return results


def _result_row(
    raw_user_text: str,
    dry_result: dict[str, Any],
    *,
    followup_result: dict[str, Any] | None = None,
    followup: str = "",
) -> dict[str, Any]:
    puzzle = dry_result.get("puzzle", {}) if isinstance(dry_result.get("puzzle"), dict) else {}
    receipt = dry_result.get("receipt_packet", {}) if isinstance(dry_result.get("receipt_packet"), dict) else {}
    candidate_result = dry_result.get("candidate_result", {}) if isinstance(dry_result.get("candidate_result"), dict) else {}
    row = {
        "raw_user_text": raw_user_text,
        "selected_action_hint": str(puzzle.get("selected_action_hint", "") or ""),
        "receipt_status": str(receipt.get("status", "") or ""),
        "pending_task_id": str(dry_result.get("pending_task_id", "") or ""),
        "candidate_count": int(candidate_result.get("candidate_count", 0) or 0),
        "selected_candidate": {},
    }
    if followup_result is not None:
        resolution = followup_result.get("resolution", {}) if isinstance(followup_result.get("resolution"), dict) else {}
        row["followup"] = followup
        row["followup_status"] = str((followup_result.get("receipt_packet", {}) if isinstance(followup_result.get("receipt_packet"), dict) else {}).get("status", "") or "")
        row["selected_candidate"] = resolution.get("selected_candidate", {}) if isinstance(resolution.get("selected_candidate"), dict) else {}
    return row


def _followup_row(raw_user_text: str, follow_result: dict[str, Any]) -> dict[str, Any]:
    receipt = follow_result.get("receipt_packet", {}) if isinstance(follow_result.get("receipt_packet"), dict) else {}
    resolution = follow_result.get("resolution", {}) if isinstance(follow_result.get("resolution"), dict) else {}
    return {
        "raw_user_text": raw_user_text,
        "selected_action_hint": "",
        "receipt_status": str(receipt.get("status", "") or ""),
        "pending_task_id": str(follow_result.get("pending_task_id", "") or ""),
        "candidate_count": 0,
        "selected_candidate": resolution.get("selected_candidate", {}) if isinstance(resolution.get("selected_candidate"), dict) else {},
    }


def _load_default_cases() -> list[dict[str, Any]]:
    path = Path(__file__).resolve().parent / "puzzle_test_cases.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict)]
    except Exception:
        pass
    return []
