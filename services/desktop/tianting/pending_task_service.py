from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4
from services.desktop.language.language_service import DesktopLanguageService

PENDING_SCHEMA_VERSION = "pending_desktop_task_v1"
PENDING_STATUSES = {"pending_user_choice", "choice_resolved", "choice_cancelled", "expired"}


class PendingTaskService:
    def __init__(self, project_root: str | Path | None = None) -> None:
        self.project_root = Path(project_root or Path(__file__).resolve().parents[3]).expanduser().resolve()
        self.pending_dir = self.project_root / "data" / "runtime" / "desktop" / "pending_tasks"

    def create_pending_task(
        self,
        *,
        original_action: str,
        original_user_text: str = "",
        candidates: list[dict[str, Any]] | None = None,
        original_task_draft: dict[str, Any] | None = None,
        original_puzzle_summary: dict[str, Any] | None = None,
        choice_type: str = "",
        selected_candidate: dict[str, Any] | None = None,
        ui_prompt_type: str = "",
        message_key: str = "",
        message_params: dict[str, Any] | None = None,
        expires_after_seconds: int = 300,
        pending_task_id: str = "",
    ) -> dict[str, Any]:
        pending_id = str(pending_task_id or "").strip() or f"pending_{uuid4().hex}"
        payload = {
            "schema_version": PENDING_SCHEMA_VERSION,
            "pending_task_id": pending_id,
            "original_action": str(original_action or ""),
            "original_user_text": str(original_user_text or ""),
            "status": "pending_user_choice",
            "choice_type": str(choice_type or _default_choice_type(original_action)),
            "candidates": _safe_candidates(candidates or []),
            "selected_candidate": selected_candidate if isinstance(selected_candidate, dict) else {},
            "ui_prompt_type": str(ui_prompt_type or ""),
            "message_key": str(message_key or ""),
            "message_params": message_params if isinstance(message_params, dict) else {},
            "created_at": _now_iso(),
            "updated_at": _now_iso(),
            "expires_after_seconds": max(1, int(expires_after_seconds or 300)),
            "original_task_draft": original_task_draft if isinstance(original_task_draft, dict) else {},
            "original_puzzle_summary": original_puzzle_summary if isinstance(original_puzzle_summary, dict) else {},
        }
        self._write_pending(payload)
        return payload

    def get_pending_task(self, pending_task_id: str) -> dict[str, Any] | None:
        pending_id = str(pending_task_id or "").strip()
        if not pending_id:
            return None
        return self._read_pending(self.pending_dir / f"{pending_id}.json")

    def get_latest_pending_task(self) -> dict[str, Any] | None:
        try:
            if not self.pending_dir.exists():
                return None
            items = []
            for path in self.pending_dir.glob("*.json"):
                data = self._read_pending(path)
                if not data or str(data.get("status", "") or "") != "pending_user_choice":
                    continue
                items.append((str(data.get("created_at", "") or ""), data))
            if not items:
                return None
            items.sort(key=lambda item: item[0], reverse=True)
            return items[0][1]
        except Exception:
            return None

    def resolve_choice(self, user_text: str, pending_task_id: str | None = None) -> dict[str, Any]:
        task = self.get_pending_task(pending_task_id or "") if pending_task_id else self.get_latest_pending_task()
        if not task:
            return {
                "status": "no_pending_task",
                "pending_task_id": str(pending_task_id or ""),
                "selected_candidate": {},
                "safe_user_message": "No pending desktop choice was found.",
            }

        pending_id = str(task.get("pending_task_id", "") or "")
        text = str(user_text or "").strip()
        choice_type = str(task.get("choice_type", "") or "")
        if _is_cancel_text(text):
            self.cancel_pending_task(pending_id)
            _append_feedback(
                pending_task_id=pending_id,
                feedback_type="cancelled",
                feedback_text=text,
                original_task=task,
            )
            return {
                "status": "choice_cancelled",
                "pending_task_id": pending_id,
                "selected_candidate": {},
                "original_task_draft": task.get("original_task_draft", {}),
                "choice_type": str(task.get("choice_type", "") or ""),
                "safe_user_message": "Choice cancelled. No real desktop action was executed.",
            }

        candidates = task.get("candidates", []) if isinstance(task.get("candidates"), list) else []
        if choice_type == "app_launch_confirmation":
            if _is_confirm_text(text):
                candidate = task.get("selected_candidate", {}) if isinstance(task.get("selected_candidate"), dict) else {}
                if not candidate and candidates:
                    candidate = candidates[0]
                if candidate:
                    self.complete_pending_task(pending_id, candidate)
                    _append_feedback(
                        pending_task_id=pending_id,
                        feedback_type="confirmed",
                        feedback_text=text,
                        selected_candidate=candidate,
                        original_task=task,
                    )
                    return {
                        "status": "choice_resolved",
                        "pending_task_id": pending_id,
                        "selected_candidate": candidate,
                        "original_task_draft": task.get("original_task_draft", {}),
                        "choice_type": choice_type,
                        "safe_user_message": "Choice confirmed. No direct desktop action was executed here.",
                    }
                return {
                    "status": "choice_invalid",
                    "pending_task_id": pending_id,
                    "selected_candidate": {},
                    "original_task_draft": task.get("original_task_draft", {}),
                    "choice_type": choice_type,
                    "safe_user_message": "The confirmation target is missing.",
                }
            return {
                "status": "choice_invalid",
                "pending_task_id": pending_id,
                "selected_candidate": {},
                "original_task_draft": task.get("original_task_draft", {}),
                "choice_type": choice_type,
                "safe_user_message": "Please confirm or cancel.",
            }

        selected = _select_candidate(text, candidates)
        if selected["status"] == "choice_resolved":
            candidate = selected["candidate"]
            self.complete_pending_task(pending_id, candidate)
            _append_feedback(
                pending_task_id=pending_id,
                feedback_type="confirmed",
                feedback_text=text,
                selected_candidate=candidate,
                original_task=task,
            )
            return {
                "status": "choice_resolved",
                "pending_task_id": pending_id,
                "selected_candidate": candidate,
                "original_task_draft": task.get("original_task_draft", {}),
                "choice_type": str(task.get("choice_type", "") or ""),
                "safe_user_message": f"Selected: {candidate.get('label', '-')}. No real desktop action was executed.",
            }
        if selected["status"] == "choice_ambiguous":
            return {
                "status": "choice_ambiguous",
                "pending_task_id": pending_id,
                "selected_candidate": {},
                "original_task_draft": task.get("original_task_draft", {}),
                "choice_type": str(task.get("choice_type", "") or ""),
                "safe_user_message": "The choice matched multiple candidates. Please choose by number.",
            }
        return {
            "status": "choice_invalid",
            "pending_task_id": pending_id,
            "selected_candidate": {},
            "original_task_draft": task.get("original_task_draft", {}),
            "choice_type": str(task.get("choice_type", "") or ""),
            "safe_user_message": "I could not match that choice. Please choose by number or cancel.",
        }

    def cancel_pending_task(self, pending_task_id: str) -> dict[str, Any]:
        task = self.get_pending_task(pending_task_id)
        if not task:
            return {}
        task["status"] = "choice_cancelled"
        task["updated_at"] = _now_iso()
        self._write_pending(task)
        return task

    def complete_pending_task(self, pending_task_id: str, selected_candidate: dict[str, Any]) -> dict[str, Any]:
        task = self.get_pending_task(pending_task_id)
        if not task:
            return {}
        task["status"] = "choice_resolved"
        task["selected_candidate"] = selected_candidate if isinstance(selected_candidate, dict) else {}
        task["updated_at"] = _now_iso()
        self._write_pending(task)
        return task

    def _pending_path(self, pending_task_id: str) -> Path:
        return self.pending_dir / f"{pending_task_id}.json"

    def _read_pending(self, path: Path) -> dict[str, Any] | None:
        try:
            if not path.exists():
                return None
            data = json.loads(path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else None
        except Exception:
            return None

    def _write_pending(self, payload: dict[str, Any]) -> None:
        try:
            pending_id = str(payload.get("pending_task_id", "") or "").strip()
            if not pending_id:
                return
            self.pending_dir.mkdir(parents=True, exist_ok=True)
            self._pending_path(pending_id).write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception:
            return


def create_pending_task(**kwargs: Any) -> dict[str, Any]:
    return PendingTaskService().create_pending_task(**kwargs)


def get_pending_task(pending_task_id: str) -> dict[str, Any] | None:
    return PendingTaskService().get_pending_task(pending_task_id)


def get_latest_pending_task() -> dict[str, Any] | None:
    return PendingTaskService().get_latest_pending_task()


def resolve_choice(user_text: str, pending_task_id: str | None = None) -> dict[str, Any]:
    return PendingTaskService().resolve_choice(user_text, pending_task_id)


def cancel_pending_task(pending_task_id: str) -> dict[str, Any]:
    return PendingTaskService().cancel_pending_task(pending_task_id)


def complete_pending_task(pending_task_id: str, selected_candidate: dict[str, Any]) -> dict[str, Any]:
    return PendingTaskService().complete_pending_task(pending_task_id, selected_candidate)


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _safe_candidates(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    safe: list[dict[str, Any]] = []
    for index, candidate in enumerate(candidates, start=1):
        if not isinstance(candidate, dict):
            continue
        item = dict(candidate)
        item.setdefault("display_index", index)
        item.setdefault("candidate_id", f"cand_{index:03d}")
        item.setdefault("label", str(candidate.get("name", "") or ""))
        safe.append(item)
    return safe


def _is_cancel_text(text: str) -> bool:
    compact = str(text or "").strip().lower().replace(" ", "")
    service = DesktopLanguageService()
    profile = service.profile_for_text(text)
    words = service.list(profile, "pending.cancel_words") or [
        "取消", "算了", "不用了", "不要", "不要了", "不是", "不对", "cancel", "stop", "退出选择"
    ]
    return compact in {
        str(item).strip().lower().replace(" ", "")
        for item in words
        if str(item or "").strip()
    }

def _is_confirm_text(text: str) -> bool:
    compact = str(text or "").strip().lower().replace(" ", "")
    service = DesktopLanguageService()
    profile = service.profile_for_text(text)
    words = service.list(profile, "pending.confirm_words") or [
        "是", "对", "打开", "确认", "就是这个", "可以", "嗯", "好的", "好", "yes", "y", "confirm", "ok"
    ]
    return compact in {
        str(item).strip().lower().replace(" ", "")
        for item in words
        if str(item or "").strip()
    }

def _select_candidate(text: str, candidates: list[dict[str, Any]]) -> dict[str, Any]:
    normalized = str(text or "").strip().lower()
    compact = normalized.replace(" ", "")
    index = _choice_index(normalized)
    if index is not None:
        for candidate in candidates:
            try:
                display_index = int(candidate.get("display_index", 0) or 0)
            except Exception:
                display_index = 0
            if display_index == index:
                return {"status": "choice_resolved", "candidate": candidate}
        return {"status": "choice_invalid", "candidate": {}}

    if "最近修改" in compact or "最新" in compact:
        matches = [item for item in candidates if "最近" in str(item.get("modified_hint", "") or "")]
        return _match_result(matches)

    app_match = _select_app_close_candidate(compact, candidates)
    if app_match["status"] != "choice_invalid":
        return app_match

    for ext in (".docx", ".doc", ".pdf", ".md", ".txt", ".json", ".xlsx", ".xls", ".pptx", ".ppt"):
        if ext.replace(".", "") in normalized or ext in normalized:
            matches = [item for item in candidates if str(item.get("file_ext", "") or "").lower() == ext]
            return _match_result(matches)

    return {"status": "choice_invalid", "candidate": {}}


def _choice_index(text: str) -> int | None:
    compact = str(text or "").strip().lower().replace(" ", "")
    if not compact:
        return None

    service = DesktopLanguageService()
    profile = service.profile_for_text(text)

    choice_map = service.get(profile, "pending.choice_index_words", {})
    if isinstance(choice_map, dict):
        for index_text, words in choice_map.items():
            try:
                index = int(index_text)
            except Exception:
                continue

            if isinstance(words, list):
                normalized_words = {
                    str(item).strip().lower().replace(" ", "")
                    for item in words
                    if str(item or "").strip()
                }
                if compact in normalized_words:
                    return index

                # 兼容“就打开第一个吧”这类多余语气词
                for word in normalized_words:
                    if word and word in compact:
                        return index

    # fallback：防止语言包缺字段时完全失效
    fallback_mapping = {
        "第一个": 1,
        "第一個": 1,
        "第1个": 1,
        "第1個": 1,
        "第1": 1,
        "一": 1,
        "1": 1,
        "打开第一个": 1,
        "关闭第一个": 1,
        "第二个": 2,
        "第二個": 2,
        "第2个": 2,
        "第2個": 2,
        "第2": 2,
        "二": 2,
        "2": 2,
        "打开第二个": 2,
        "关闭第二个": 2,
        "第三个": 3,
        "第三個": 3,
        "第3个": 3,
        "第3個": 3,
        "第3": 3,
        "三": 3,
        "3": 3,
        "打开第三个": 3,
        "关闭第三个": 3,
    }

    if compact in fallback_mapping:
        return fallback_mapping[compact]

    if compact.isdigit():
        value = int(compact)
        return value if value > 0 else None

    return None

def _select_app_close_candidate(text: str, candidates: list[dict[str, Any]]) -> dict[str, Any]:
    if not candidates:
        return {"status": "choice_invalid", "candidate": {}}
    if "游戏" in text or "game" in text:
        matches = [
            item for item in candidates
            if str(item.get("target_type", "") or "") == "launcher_child_app"
            or "游戏" in _candidate_text(item)
            or "game" in _candidate_text(item)
        ]
        return _match_result(matches)
    if "客户端" in text:
        matches = [item for item in candidates if str(item.get("target_type", "") or "") == "launcher_client"]
        return _match_result(matches)
    if "启动器" in text or "launcher" in text:
        matches = [
            item for item in candidates
            if str(item.get("target_type", "") or "") == "launcher_client"
            or "launcher" in str(item.get("target_type", "") or "")
            or "启动器" in _candidate_text(item)
            or "launcher" in _candidate_text(item)
        ]
        return _match_result(matches)
    if "后台" in text or "background" in text:
        matches = [item for item in candidates if str(item.get("target_type", "") or "") == "background_process"]
        return _match_result(matches)
    if "steam" in text:
        matches = [item for item in candidates if "steam" in _candidate_text(item)]
        return _match_result(matches)
    return {"status": "choice_invalid", "candidate": {}}


def _candidate_text(candidate: dict[str, Any]) -> str:
    return " ".join(
        str(candidate.get(key, "") or "")
        for key in ("label", "window_title", "process_name", "app_id", "app_kind", "target_type")
    ).lower()


def _match_result(matches: list[dict[str, Any]]) -> dict[str, Any]:
    if len(matches) == 1:
        return {"status": "choice_resolved", "candidate": matches[0]}
    if len(matches) > 1:
        recommended = [item for item in matches if bool(item.get("recommended", False))]
        if len(recommended) == 1:
            return {"status": "choice_resolved", "candidate": recommended[0]}
        return {"status": "choice_ambiguous", "candidate": {}}
    return {"status": "choice_invalid", "candidate": {}}


def _default_choice_type(action: str) -> str:
    normalized = str(action or "").strip()
    if normalized == "app.close":
        return "app_close_candidate"
    if normalized == "file.open":
        return "file_candidate"
    if normalized == "app.launch":
        return "app_launch_candidate"
    return "candidate"


def _append_feedback(
    *,
    pending_task_id: str,
    feedback_type: str,
    feedback_text: str,
    selected_candidate: dict[str, Any] | None = None,
    original_task: dict[str, Any] | None = None,
) -> None:
    try:
        from services.desktop.tianting.command_memory_card_service import append_feedback_card

        append_feedback_card(
            pending_task_id=pending_task_id,
            feedback_type=feedback_type,
            feedback_text=feedback_text,
            selected_candidate=selected_candidate or {},
            original_task=original_task or {},
        )
    except Exception:
        return
