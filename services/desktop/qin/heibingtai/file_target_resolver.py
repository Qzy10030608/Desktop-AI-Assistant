from __future__ import annotations

from pathlib import Path
from typing import Any

from services.desktop.qin.heibingtai.running_document_resolver import RunningDocumentResolver


class FileTargetResolver:
    """Resolve fuzzy file.close targets into candidates without executing close."""

    def __init__(
        self,
        project_root: str | Path | None = None,
        *,
        running_document_resolver: RunningDocumentResolver | None = None,
    ) -> None:
        self.project_root = Path(project_root or Path(__file__).resolve().parents[4]).expanduser().resolve()
        self.running_document_resolver = running_document_resolver or RunningDocumentResolver(self.project_root)

    def resolve(self, task: dict[str, Any]) -> dict[str, Any]:
        payload = task if isinstance(task, dict) else {}
        arguments = payload.get("arguments", {}) if isinstance(payload.get("arguments"), dict) else {}
        target_path = str(payload.get("target_path", arguments.get("target_path", "")) or "")
        target_name = str(
            payload.get("target_name", "")
            or payload.get("target_reference", "")
            or arguments.get("target_name", "")
            or arguments.get("target_reference", "")
            or ""
        )
        target_reference_raw = str(
            payload.get("target_reference", "")
            or arguments.get("target_reference", "")
            or target_name
            or target_path
            or ""
        )
        app_hint = str(payload.get("app_hint", arguments.get("app_hint", "")) or "")
        current_hint = str(payload.get("current_hint", arguments.get("current_hint", "")) or "")

        if not any([target_path, target_name, target_reference_raw, app_hint, current_hint]):
            return self._not_found(
                target_path=target_path,
                target_name=target_name,
                target_reference_raw=target_reference_raw,
                app_hint=app_hint,
                current_hint=current_hint,
                searched_sources=[],
                reason="missing_target_reference",
            )

        candidates = self.running_document_resolver.resolve_candidates({
            **payload,
            "target_path": target_path,
            "target_name": target_name or target_reference_raw,
            "arguments": {
                **arguments,
                "app_hint": app_hint,
                "current_hint": current_hint,
            },
        })
        searched_sources = self._searched_sources(candidates)

        base = {
            "target_reference_raw": target_reference_raw,
            "target_name": target_name or target_reference_raw,
            "target_path": target_path,
            "app_hint": app_hint,
            "current_hint": current_hint,
            "searched_sources": searched_sources,
            "candidate_count": len(candidates),
            "candidates": candidates,
            "needs_open_app_choice": False,
        }

        if not candidates:
            return {
                "ok": False,
                "error": "file_view_not_resolved",
                "resolution_state": "not_found",
                "requires_user_choice": False,
                "llm_reply_hint": self._llm_reply_hint("not_found", target_name or target_reference_raw, candidates),
                "user_action_required": "clarify_file_target",
                **base,
            }

        if len(candidates) == 1:
            return {
                "ok": True,
                "error": "",
                "resolution_state": "resolved_unique",
                "requires_user_choice": False,
                "selected_candidate_id": str(candidates[0].get("candidate_id", "") or ""),
                "selected_candidate": candidates[0],
                "llm_reply_hint": self._llm_reply_hint("resolved_unique", target_name or target_reference_raw, candidates),
                "user_action_required": "",
                **base,
            }

        return {
            "ok": False,
            "error": "requires_user_choice",
            "resolution_state": "ambiguous_candidates",
            "requires_user_choice": True,
            "llm_reply_hint": self._llm_reply_hint("ambiguous_candidates", target_name or target_reference_raw, candidates),
            "user_action_required": "choose_file_candidate",
            **base,
        }

    def _not_found(
        self,
        *,
        target_path: str,
        target_name: str,
        target_reference_raw: str,
        app_hint: str,
        current_hint: str,
        searched_sources: list[str],
        reason: str,
    ) -> dict[str, Any]:
        return {
            "ok": False,
            "error": "file_view_not_resolved",
            "resolution_state": "not_found",
            "target_reference_raw": target_reference_raw,
            "target_name": target_name,
            "target_path": target_path,
            "app_hint": app_hint,
            "current_hint": current_hint,
            "searched_sources": searched_sources,
            "candidate_count": 0,
            "candidates": [],
            "requires_user_choice": False,
            "needs_open_app_choice": False,
            "llm_reply_hint": self._llm_reply_hint("not_found", target_name or target_reference_raw, []),
            "user_action_required": "clarify_file_target",
            "reason": reason,
        }

    def _searched_sources(self, candidates: list[dict[str, Any]]) -> list[str]:
        sources = [
            "open_session",
            "rot",
            "office_com",
            "wps_com",
            "wps_com_probe",
            "window_title",
        ]
        observed = {
            str(candidate.get("source", "") or "").strip()
            for candidate in candidates
            if str(candidate.get("source", "") or "").strip()
        }
        return [source for source in sources if source in observed or source in {"open_session", "window_title"}]

    def _llm_reply_hint(self, state: str, target_reference: str, candidates: list[dict[str, Any]]) -> str:
        target = str(target_reference or "目标文件")
        if state == "ambiguous_candidates":
            labels = [
                str(candidate.get("label", "") or candidate.get("window_title", "") or candidate.get("app_kind", "") or "")
                for candidate in candidates[:3]
            ]
            labels = [label for label in labels if label]
            if labels:
                return f"我找到了多个可能的“{target}”：{('、').join(labels)}，请确认要操作哪一个。"
            return f"我找到了多个可能的“{target}”，请确认要操作哪一个。"
        if state == "resolved_unique":
            label = str((candidates[0] if candidates else {}).get("label", "") or target)
            return f"我已定位到“{label}”，本阶段只完成解析，尚未执行关闭。"
        return f"没有找到正在打开的“{target}”，请提供更完整的文件名、路径或所在软件。"
