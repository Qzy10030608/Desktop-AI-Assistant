from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Any
from services.desktop.language.language_service import DesktopLanguageService

DECISION_SCHEMA_VERSION = "jiuchasi_desktop_decision_v2"


class DesktopDecisionPolicy:
    """
    天庭·纠察司：结构化判断策略。

    这一层只做：
    - 判断 status
    - 生成 message_intent/message_key/slots
    - 生成 qin_task_patch
    - 标记是否需要确认、澄清、候选选择

    这一层不负责：
    - 生成自然语言句子
    - 多语言表达
    - 执行桌面动作
    - 授权权限
    - 编造路径、进程、backend
    """

    def __init__(self, project_root: str | Path | None = None) -> None:
        self.project_root = Path(project_root or Path(__file__).resolve().parents[4]).expanduser().resolve()
        self.language_service = DesktopLanguageService()

    def decide(
        self,
        *,
        user_text: str,
        action_hint: str = "",
        target_normalized: str = "",
        evidence_packet: dict[str, Any] | None = None,
        llm_thinking: dict[str, Any] | None = None,
        original_task_draft: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        evidence_packet = evidence_packet if isinstance(evidence_packet, dict) else {}
        llm_thinking = llm_thinking if isinstance(llm_thinking, dict) else {}
        original_task_draft = original_task_draft if isinstance(original_task_draft, dict) else {}

        action = str(action_hint or original_task_draft.get("action", "") or "").strip()
        target = str(target_normalized or original_task_draft.get("target", "") or "").strip()
        text = str(user_text or "").strip()

        if self._looks_like_software_query(text):
            return self._decide_software_query(
                user_text=text,
                target_normalized=target,
                evidence_packet=evidence_packet,
                llm_thinking=llm_thinking,
            )

        # 对未决桌面动作，先用 evidence 判断是不是文件夹/盘符。
        # 不再依赖上游 action_hint 一定正确。
        if action in {"desktop.resolve", ""}:
            resolved_app_action = self._resolve_app_action_from_text(text)
            if resolved_app_action:
                return self._decide_app_action(
                    user_text=text,
                    action_hint=resolved_app_action,
                    target_normalized=target,
                    evidence_packet=evidence_packet,
                    llm_thinking=llm_thinking,
                    original_task_draft=original_task_draft,
                )
            return self._decide_folder_open(
                user_text=text,
                target_normalized=target,
                evidence_packet=evidence_packet,
                original_task_draft=original_task_draft,
            )

        if action.startswith("folder."):
            return self._decide_folder_open(
                user_text=text,
                target_normalized=target,
                evidence_packet=evidence_packet,
                original_task_draft=original_task_draft,
            )

        if action in {"app.launch", "app.close"}:
            return self._decide_app_action(
                user_text=text,
                action_hint=action,
                target_normalized=target,
                evidence_packet=evidence_packet,
                llm_thinking=llm_thinking,
                original_task_draft=original_task_draft,
            )

        return self._decision(
            status="need_clarification",
            reason="no_supported_decision_path",
            message_intent="clarify_desktop_action",
            message_key="desktop.generic.need_clarification",
            slots={},
        )

    def _decide_software_query(
        self,
        *,
        user_text: str,
        target_normalized: str,
        evidence_packet: dict[str, Any],
        llm_thinking: dict[str, Any],
    ) -> dict[str, Any]:
        hint = self._llm_target_hint(llm_thinking)
        label = str(hint.get("target_label_hint", "") or "").strip()

        if label:
            return self._decision(
                status="chat_reply",
                reason="software_query_matched_by_llm_hint",
                message_intent="software_query_matched",
                message_key="desktop.software.query.matched",
                slots={
                    "target": label,
                    "count": 1,
                },
                evidence_refs={
                    "target_label_hint": label,
                    "confidence": hint.get("confidence", 0.0),
                },
            )

        labels = self._software_labels(evidence_packet)
        keyword = target_normalized or self._rough_query_keyword(user_text)
        matches = self._simple_label_matches(keyword, labels)

        if matches:
            return self._decision(
                status="chat_reply",
                reason="software_query_matched_by_keyword",
                message_intent="software_query_matched",
                message_key="desktop.software.query.matched",
                slots={
                    "target": "、".join(matches[:5]),
                    "count": len(matches),
                },
                evidence_refs={
                    "matches": matches[:10],
                },
            )

        return self._decision(
            status="chat_reply",
            reason="software_query_not_found",
            message_intent="software_query_not_found",
            message_key="desktop.software.query.not_found",
            slots={
                "target": keyword,
            },
        )

    def _try_decide_folder_from_evidence(
        self,
        *,
        user_text: str,
        target_normalized: str,
        evidence_packet: dict[str, Any],
        original_task_draft: dict[str, Any],
    ) -> dict[str, Any] | None:
        drive_root = self._drive_root_from_sources(
            user_text=user_text,
            target_normalized=target_normalized,
            original_task_draft=original_task_draft,
        )
        if not drive_root:
            return None

        roots = self._file_roots(evidence_packet)
        if not roots:
            return None

        known_paths = {
            str(item.get("path", "") or "").casefold()
            for item in roots
            if isinstance(item, dict)
        }

        if drive_root.casefold() not in known_paths:
            return None

        return self._decide_folder_open(
            user_text=user_text,
            target_normalized=target_normalized,
            evidence_packet=evidence_packet,
            original_task_draft=original_task_draft,
        )
    def _decide_folder_open(
        self,
        *,
        user_text: str,
        target_normalized: str,
        evidence_packet: dict[str, Any],
        original_task_draft: dict[str, Any],
    ) -> dict[str, Any]:
        target_text = str(target_normalized or "").strip()

        drive_root = self._extract_drive_root(user_text) or self._extract_drive_root(target_text)
        query_text = self._folder_query_text(user_text=user_text, target_normalized=target_text)

        # 只有“纯盘符根目录”才直接打开根目录。
        if drive_root and self._is_drive_root_request_only(user_text=user_text, target_normalized=target_text, query_text=query_text):
            roots = self._file_roots(evidence_packet)
            known_paths = {str(item.get("path", "") or "").casefold() for item in roots if isinstance(item, dict)}

            if known_paths and drive_root.casefold() not in known_paths:
                return self._decision(
                    status="need_clarification",
                    reason="drive_root_not_in_evidence",
                    message_intent="folder_root_not_confirmed",
                    message_key="desktop.folder.open.root_not_confirmed",
                    slots={"target": drive_root},
                    evidence_refs={
                        "drive_root": drive_root,
                        "known_paths": sorted(known_paths),
                    },
                )

            task_patch = dict(original_task_draft)
            task_patch.update(
                {
                    "action": "folder.open",
                    "target": drive_root,
                    "path_hint": drive_root,
                    "candidate_search": False,
                    "source": "jiuchasi_decision_policy",
                    "needs": {
                        "user_clarification": False,
                        "candidate_search": False,
                    },
                }
            )

            return self._decision(
                status="ready_for_qin",
                reason="folder_open_drive_root_ready",
                message_intent="folder_open_ready",
                message_key="desktop.folder.open.candidate_ready",
                slots={"target": drive_root},
                qin_task_patch=task_patch,
                evidence_refs={"drive_root": drive_root},
            )

        # 不是纯盘符，就是具体文件夹搜索。
        file_candidates = self._file_candidates(evidence_packet)
        candidates = [
            item for item in file_candidates
            if isinstance(item, dict) and str(item.get("kind", "") or "") == "folder"
        ]

        if len(candidates) == 1 and float(candidates[0].get("confidence", 0.0) or 0.0) >= 0.86:
            candidate = candidates[0]
            target_path = str(candidate.get("target_path", "") or candidate.get("path", "") or "").strip()

            task_patch = dict(original_task_draft)
            task_patch.update(
                {
                    "action": "folder.open",
                    "target": target_path,
                    "path_hint": target_path,
                    "candidate_search": False,
                    "requires_confirmation": False,
                    "source": "jiuchasi_decision_policy",
                    "needs": {
                        "user_clarification": False,
                        "candidate_search": False,
                    },
                }
            )

            return self._decision(
                status="ready_for_qin",
                reason="single_folder_candidate_ready",
                message_intent="folder_open_ready",
                message_key="desktop.folder.open.candidate_ready",
                slots={"target": target_path},
                qin_task_patch=task_patch,
                evidence_refs={
                    "candidate": candidate,
                    "query": query_text,
                },
            )

        if candidates:
            safe_candidates = []
            for index, item in enumerate(candidates[:10], start=1):
                safe_candidates.append(
                    {
                        "candidate_id": str(item.get("candidate_id", "") or f"folder_{index:03d}"),
                        "display_index": index,
                        "label": str(item.get("label", "") or item.get("name", "") or item.get("target_path", "")),
                        "subtitle": str(item.get("target_path", "") or item.get("path", "")),
                        "kind": "folder",
                        "target_path": str(item.get("target_path", "") or item.get("path", "")),
                        "source": str(item.get("source", "") or "file_candidates"),
                    }
                )

            return self._decision(
                status="multiple_candidates",
                reason="multiple_folder_candidates",
                message_intent="choose_folder_candidate",
                message_key="desktop.generic.pending_choice",
                slots={"count": len(safe_candidates), "target": query_text},
                candidates=safe_candidates,
                evidence_refs={"query": query_text},
            )

        return self._decision(
            status="need_clarification",
            reason="folder_candidate_not_found",
            message_intent="clarify_folder_target",
            message_key="desktop.folder.open.need_clarification",
            slots={"target": query_text or target_text},
            evidence_refs={
                "query": query_text,
                "drive_root": drive_root,
                "file_candidate_count": 0,
            },
        )
    
    def _decide_app_action(
        self,
        *,
        user_text: str,
        action_hint: str,
        target_normalized: str,
        evidence_packet: dict[str, Any],
        llm_thinking: dict[str, Any],
        original_task_draft: dict[str, Any],
    ) -> dict[str, Any]:
        hint = self._llm_target_hint(llm_thinking)
        label = str(hint.get("target_label_hint", "") or "").strip()

        if label:
            hint_source = str(hint.get("source", "") or "").strip()
            memory_source = str(hint.get("memory_source", "") or "").strip()
            trusted = bool(hint.get("trusted", False))
            confidence = float(hint.get("confidence", 0.0) or 0.0)

            clear_target = (
                trusted
                or hint_source in {"target_memory", "direct_label_match"}
                or memory_source in {"user_confirmed", "local"}
                or confidence >= 0.88
            )

            task_patch = dict(original_task_draft)
            task_patch.update(
                {
                    "action": action_hint,
                    "target": label,
                    "target_label_hint": label,
                    "candidate_search": True,
                    "requires_confirmation": not clear_target,
                    "source": "jiuchasi_decision_policy",
                }
            )

            if clear_target:
                return self._decision(
                    status="ready_for_qin",
                    reason="trusted_app_target_ready",
                    message_intent="software_target_ready",
                    message_key="desktop.app.launch.candidate_ready"
                    if action_hint == "app.launch"
                    else "desktop.app.close.plan_ready",
                    slots={
                        "target": label,
                    },
                    qin_task_patch=task_patch,
                    evidence_refs={
                        "target_label_hint": label,
                        "confidence": confidence,
                        "source": hint_source,
                        "memory_source": memory_source,
                        "trusted": trusted,
                    },
                )

            if action_hint == "app.launch":
                message_intent = "confirm_app_launch"
                message_key = "desktop.app.launch.need_confirmation"
            else:
                message_intent = "confirm_app_close"
                message_key = "desktop.app.close.need_confirmation"

            return self._decision(
                status="need_confirmation",
                reason="untrusted_target_hint_requires_user_confirmation",
                message_intent=message_intent,
                message_key=message_key,
                slots={
                    "target": label,
                    "user_phrase": target_normalized,
                },
                qin_task_patch=task_patch,
                pending_question={
                    "type": "app_action_confirmation",
                    "action": action_hint,
                    "target": label,
                    "confirm_words_supported": True,
                },
                evidence_refs={
                    "target_label_hint": label,
                    "confidence": confidence,
                    "source": hint_source,
                    "memory_source": memory_source,
                    "trusted": trusted,
                },
            )

        labels = self._software_labels(evidence_packet)
        matches = self._simple_label_matches(target_normalized, labels)

        if len(matches) == 1:
            label = matches[0]
            task_patch = dict(original_task_draft)
            task_patch.update(
                {
                    "action": action_hint,
                    "target": label,
                    "target_label_hint": label,
                    "candidate_search": True,
                    "requires_confirmation": False,
                    "source": "jiuchasi_decision_policy",
                }
            )

            return self._decision(
                status="ready_for_qin",
                reason="single_software_label_match_ready",
                message_intent="software_target_ready",
                message_key="desktop.app.launch.candidate_ready"
                if action_hint == "app.launch"
                else "desktop.app.close.plan_ready",
                slots={
                    "target": label,
                },
                qin_task_patch=task_patch,
                evidence_refs={
                    "matched_label": label,
                },
            )

        if len(matches) > 1:
            candidates = [
                {
                    "display_index": index,
                    "label": label,
                    "candidate_id": f"software_{index:03d}",
                }
                for index, label in enumerate(matches[:10], start=1)
            ]

            return self._decision(
                status="multiple_candidates",
                reason="multiple_software_label_matches",
                message_intent="choose_software_candidate",
                message_key="desktop.app.launch.pending_choice"
                if action_hint == "app.launch"
                else "desktop.app.close.pending_choice",
                slots={
                    "count": len(candidates),
                },
                candidates=candidates,
            )

        return self._decision(
            status="need_clarification",
            reason="software_target_not_resolved",
            message_intent="clarify_software_target",
            message_key="desktop.app.launch.need_clarification"
            if action_hint == "app.launch"
            else "desktop.app.close.need_clarification",
            slots={
                "target": target_normalized,
            },
            evidence_refs={
                "target_normalized": target_normalized,
                "known_label_count": len(labels),
            },
        )
    def _app_task_patch(
        self,
        *,
        original_task_draft: dict[str, Any],
        action_hint: str,
        label: str,
        requires_confirmation: bool,
    ) -> dict[str, Any]:
        task_patch = dict(original_task_draft if isinstance(original_task_draft, dict) else {})
        task_patch.update(
            {
                "action": action_hint,
                "target": label,
                "target_label_hint": label,
                "candidate_search": True,
                "requires_confirmation": bool(requires_confirmation),
                "source": "jiuchasi_decision_policy",
                "needs": {
                    "user_clarification": False,
                    "candidate_search": True,
                },
            }
        )
        return task_patch

    def _permission_state_for_label(self, label: str, evidence_packet: dict[str, Any]) -> str:
        target = str(label or "").strip().casefold()
        if not target:
            return ""
        providers = evidence_packet.get("providers", {}) if isinstance(evidence_packet, dict) else {}
        software = providers.get("software_governance", {}) if isinstance(providers, dict) else {}
        rows = software.get("rows", []) if isinstance(software, dict) else []
        if not isinstance(rows, list):
            return ""
        for row in rows:
            if not isinstance(row, dict):
                continue
            row_labels = [
                str(row.get("title", "") or ""),
                str(row.get("name", "") or ""),
                str(row.get("app_id", "") or ""),
                str(row.get("canonical_app_id", "") or ""),
            ]
            if any(item.strip().casefold() == target for item in row_labels if item.strip()):
                return str(row.get("permission_state", "") or "").strip().lower()
        return ""

    def _permission_allows_review(self, permission_state: str) -> bool:
        return str(permission_state or "").strip().lower() in {"allow", "once", "restricted"}

    def _permission_blocks_review(self, permission_state: str) -> bool:
        state = str(permission_state or "").strip().lower()
        return state in {
            "deny",
            "denied",
            "blocked",
            "forbid",
            "forbidden",
            "false",
            "0",
            "no",
            "否",
        }
    
    def _decision(
        self,
        *,
        status: str,
        reason: str,
        message_intent: str,
        message_key: str,
        slots: dict[str, Any] | None = None,
        qin_task_patch: dict[str, Any] | None = None,
        pending_question: dict[str, Any] | None = None,
        candidates: list[dict[str, Any]] | None = None,
        evidence_refs: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        slots = slots if isinstance(slots, dict) else {}

        return {
            "schema_version": DECISION_SCHEMA_VERSION,
            "created_at_ts": int(time.time()),
            "status": str(status or ""),
            "reason": str(reason or ""),
            "message": {
                "intent": str(message_intent or ""),
                "key": str(message_key or ""),
                "slots": slots,
                "allow_llm_rewrite": True,
            },
            "message_intent": str(message_intent or ""),
            "message_key": str(message_key or ""),
            "message_slots": slots,
            "qin_task_patch": qin_task_patch if isinstance(qin_task_patch, dict) else {},
            "pending_question": pending_question if isinstance(pending_question, dict) else {},
            "candidates": candidates if isinstance(candidates, list) else [],
            "evidence_refs": evidence_refs if isinstance(evidence_refs, dict) else {},
            "direct_execution_allowed": False,

            # 兼容旧调用方。后续接入 ResponseComposer 后，外部不应再依赖这个字段。
            "safe_user_message": "",
        }

    def _resolve_app_action_from_text(self, text: str) -> str:
        raw = str(text or "").strip()
        if not raw:
            return ""

        profile = self.language_service.profile_for_text(raw)

        open_words = self.language_service.list(profile, "command.open_verbs")
        close_words = self.language_service.list(profile, "command.close_verbs")

        has_open = self.language_service.contains_any(raw, open_words)
        has_close = self.language_service.contains_any(raw, close_words)

        if has_open and not has_close:
            return "app.launch"

        if has_close and not has_open:
            return "app.close"

        return ""

    def _looks_like_software_query(self, text: str) -> bool:
        raw = str(text or "").strip()
        if not raw:
            return False

        profile = self.language_service.profile_for_text(raw)

        query_words = self.language_service.list(profile, "command.software_query.query_words")
        object_words = self.language_service.list(profile, "command.software_query.object_words")

        if not query_words or not object_words:
            return False

        return (
            self.language_service.contains_any(raw, query_words)
            and self.language_service.contains_any(raw, object_words)
        )
    
    def _llm_target_hint(self, llm_thinking: dict[str, Any]) -> dict[str, Any]:
        hint = llm_thinking.get("llm_target_hint", {})
        return hint if isinstance(hint, dict) else {}

    def _software_labels(self, evidence_packet: dict[str, Any]) -> list[str]:
        providers = evidence_packet.get("providers", {})
        if not isinstance(providers, dict):
            return []

        software = providers.get("software_governance", {})
        if not isinstance(software, dict):
            return []

        labels = software.get("labels", [])
        if not isinstance(labels, list):
            return []

        result: list[str] = []
        seen: set[str] = set()
        for item in labels:
            text = str(item or "").strip()
            key = text.casefold()
            if text and key not in seen:
                seen.add(key)
                result.append(text)
        return result

    def _file_roots(self, evidence_packet: dict[str, Any]) -> list[dict[str, Any]]:
        providers = evidence_packet.get("providers", {})
        if not isinstance(providers, dict):
            return []

        roots_packet = providers.get("file_roots", {})
        if not isinstance(roots_packet, dict):
            return []

        roots = roots_packet.get("roots", [])
        return roots if isinstance(roots, list) else []

    def _file_candidates(self, evidence_packet: dict[str, Any]) -> list[dict[str, Any]]:
        providers = evidence_packet.get("providers", {})
        if not isinstance(providers, dict):
            return []

        packet = providers.get("file_candidates", {})
        if not isinstance(packet, dict):
            return []

        candidates = packet.get("candidates", [])
        return candidates if isinstance(candidates, list) else []


    def _folder_query_text(self, *, user_text: str, target_normalized: str) -> str:
        text = str(target_normalized or user_text or "").strip()
        if not text:
            return ""

        compact = text.replace(" ", "").replace("　", "")
        compact = re.sub(r"(?i)^[a-z][:：]?[\\/]+", "", compact)
        compact = re.sub(r"(?i)^[a-z]盘的?", "", compact)

        for suffix in ("文件夹", "目录", "根目录", "根路径", "路径"):
            if compact.endswith(suffix):
                compact = compact[: -len(suffix)]

        return compact.strip()


    def _is_drive_root_request_only(self, *, user_text: str, target_normalized: str, query_text: str) -> bool:
        text = str(target_normalized or user_text or "").replace(" ", "").replace("　", "")

        if not query_text:
            return True

        # G盘 / G盘根目录 / G:\ 这类才算纯根目录
        if re.fullmatch(r"(?i)[a-z][:：]?[\\/]*", text):
            return True

        if re.fullmatch(r"(?i)[a-z]盘(根目录|根路径|目录|文件夹)?", text):
            return True

        return False

    def _simple_label_matches(self, keyword: str, labels: list[str]) -> list[str]:
        key = str(keyword or "").strip().casefold()
        if not key:
            return []

        matches: list[str] = []
        seen: set[str] = set()

        for label in labels:
            text = str(label or "").strip()
            low = text.casefold()
            if key and (key in low or low in key):
                if low not in seen:
                    seen.add(low)
                    matches.append(text)

        return matches

    def _rough_query_keyword(self, text: str) -> str:
        raw = str(text or "").strip()
        if not raw:
            return ""

        profile = self.language_service.profile_for_text(raw)
        tokens: list[str] = []
        tokens.extend(self.language_service.list(profile, "command.software_query.query_words"))
        tokens.extend(self.language_service.list(profile, "command.software_query.object_words"))
        tokens.extend(self.language_service.list(profile, "command.question_particles"))

        cleaned = raw
        for token in sorted(set(tokens), key=len, reverse=True):
            cleaned = cleaned.replace(str(token), " ")

        return " ".join(cleaned.split()).strip()

    def _extract_drive_root(self, text: str) -> str:
        raw = str(text or "")
        compact = raw.replace(" ", "").replace("　", "")
        if not compact:
            return ""

        root_match = re.search(r"(?i)(?:^|[^a-z0-9])([a-z])\s*[:：]\s*(?:[\\/]|$)", compact)
        if root_match:
            return f"{root_match.group(1).upper()}:\\"

        profile = self.language_service.profile_for_text(raw)
        drive_suffixes = self.language_service.list(profile, "command.filesystem.drive_suffixes")
        drive_suffixes = list(dict.fromkeys([*drive_suffixes, "盘", "盤"]))

        for suffix in drive_suffixes:
            clean_suffix = str(suffix or "").strip()
            if not clean_suffix:
                continue
            match = re.search(r"(?i)([a-zA-Z])\s*[:：]?\s*" + re.escape(clean_suffix), compact)
            if match:
                return f"{match.group(1).upper()}:\\"

        match = re.search(r"(?i)\b([a-zA-Z])[:：][\\/]", compact)
        if match:
            return f"{match.group(1).upper()}:\\"

        return ""

    def _drive_root_from_sources(
        self,
        *,
        user_text: str,
        target_normalized: str,
        original_task_draft: dict[str, Any],
    ) -> str:
        task = original_task_draft if isinstance(original_task_draft, dict) else {}
        target = task.get("target", {}) if isinstance(task.get("target"), dict) else {}
        sources = [
            target_normalized,
            user_text,
            target.get("path_hint", ""),
            target.get("identity", ""),
            target.get("name_hint", ""),
        ]
        for value in sources:
            drive_root = self._extract_drive_root(str(value or ""))
            if drive_root:
                return drive_root
        return ""


def _safe_float(value: Any, *, default: float) -> float:
    try:
        return float(value)
    except Exception:
        return default
