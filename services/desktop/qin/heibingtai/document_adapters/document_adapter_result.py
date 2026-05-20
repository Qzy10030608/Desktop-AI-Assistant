from __future__ import annotations

from pathlib import Path
from typing import Any


def normalize_path(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    try:
        return str(Path(text).expanduser().resolve(strict=False)).rstrip("\\/").lower()
    except Exception:
        return text.rstrip("\\/").lower()


def session_value(session: dict[str, Any], key: str) -> str:
    return str((session or {}).get(key, "") or "").strip()


def target_path_for(task, session: dict[str, Any]) -> str:
    return session_value(session, "target_path") or str(getattr(task, "target_path", "") or "").strip()


def common_document_data(task, session: dict[str, Any], *, adapter: str, strategy: str, level: str) -> dict[str, Any]:
    target_path = target_path_for(task, session)
    return {
        "heibingtai_enabled": True,
        "close_family": "file_close",
        "close_level": level,
        "target_origin": "registered",
        "close_scope": str(getattr(task, "close_scope", "") or "current"),
        "close_strategy": strategy,
        "target_path": target_path,
        "target_type": session_value(session, "target_type") or str(getattr(task, "target_type", "") or "file"),
        "app_kind": session_value(session, "app_kind"),
        "process_name": session_value(session, "process_name"),
        "pid": session_value(session, "pid"),
        "hwnd": session_value(session, "hwnd"),
        "window_title": session_value(session, "window_title"),
        "document_adapter": adapter,
        "document_adapter_stage": adapter,
        "document_fullname": target_path,
        "document_saved": "",
        "save_state": "",
        "requires_user_save_confirmation": False,
        "matched_count": 0,
        "closed_count": 0,
        "skipped_count": 0,
        "failed_hwnds": [],
        "skip_reasons": {},
        "close_error": "",
        "requires_user_choice": False,
    }


def adapter_ok(
    task,
    session: dict[str, Any],
    *,
    adapter: str,
    strategy: str,
    level: str,
    message: str,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    data = common_document_data(task, session, adapter=adapter, strategy=strategy, level=level)
    data.update({
        "matched_count": 1,
        "closed_count": 1,
        "close_succeeded": True,
    })
    if extra:
        data.update(extra)
    return {
        "ok": True,
        "action": "file.close",
        "adapter_id": "heibingtai_document_adapter",
        "message": message,
        "data": data,
    }


def adapter_error(
    task,
    session: dict[str, Any],
    *,
    adapter: str,
    strategy: str,
    level: str,
    error: str,
    message: str,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    data = common_document_data(task, session, adapter=adapter, strategy=strategy, level=level)
    data.update({
        "error": error,
        "close_error": error,
        "skipped_count": 1,
    })
    if error == "needs_user_save_confirmation":
        data["requires_user_save_confirmation"] = True
        data["save_state"] = "dirty"
    if extra:
        data.update(extra)
    return {
        "ok": False,
        "action": "file.close",
        "adapter_id": "heibingtai_document_adapter",
        "message": message,
        "error": error,
        "data": data,
    }
