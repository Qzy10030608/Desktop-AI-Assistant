"""Language understanding and reply orchestration facade.

Phase 1 intentionally does not execute business logic. The center only builds
standard dicts and returns chat passthrough results.
"""

from __future__ import annotations

from typing import Any

from .interaction_schema import (
    build_chat_passthrough_result,
    build_direct_reply_result,
    build_interaction_context,
    build_memory_update_plan,
)


class LanguageInteractionCenter:
    """Runtime facade for future language interaction orchestration."""

    def __init__(self, controller: Any = None):
        self.controller = controller

    def build_context(self, **kwargs: Any) -> dict[str, Any]:
        return build_interaction_context(**kwargs)

    def passthrough_chat(self, context: dict[str, Any] | None = None) -> dict[str, Any]:
        return build_chat_passthrough_result(context)

    def normalize_direct_safe_reply(
        self,
        context: dict[str, Any] | None = None,
        safe_payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return build_direct_reply_result(context, safe_payload)

    def polish_interaction_reply(self, interaction_result: dict[str, Any]) -> dict[str, Any]:
        result = dict(interaction_result) if isinstance(interaction_result, dict) else {}
        try:
            from services.runtime.interaction.receipt_reply_polisher import ReceiptReplyPolisher

            polisher = ReceiptReplyPolisher(model_config=self._current_model_config())
            polished = polisher.polish(result)
        except Exception as exc:
            print(f"[ReplyPolisher] failed error={exc!r}")
            return result

        debug_refs = result.get("debug_refs", {}) if isinstance(result.get("debug_refs"), dict) else {}
        next_debug_refs = dict(debug_refs)
        next_debug_refs["reply_polisher"] = polished if isinstance(polished, dict) else {}
        result["debug_refs"] = next_debug_refs

        if (
            isinstance(polished, dict)
            and bool(polished.get("ok", False))
            and str(polished.get("display_text", "") or "").strip()
        ):
            result["display_text"] = str(polished.get("display_text", "") or "")
            result["tts_text"] = str(polished.get("tts_text", result["display_text"]) or result["display_text"])
        return result

    def route_basic_system_skill(self, *, text: str, from_voice: bool = False) -> dict[str, Any]:
        try:
            from services.desktop.tianting.basic_system_skill_router import detect_basic_system_skill

            route = detect_basic_system_skill(
                text,
                input_channel="voice" if from_voice else "text",
            )
        except Exception as exc:
            return {
                "route": "chat_reply",
                "matched": False,
                "debug_summary": {"system_skill_error": str(exc)},
            }

        if not isinstance(route, dict):
            return {"route": "chat_reply", "matched": False}
        if str(route.get("route", "") or "") != "system_skill":
            return self._route_basic_system_skill_semantic(text=text, from_voice=from_voice)

        result = dict(route)
        result["source"] = "language_interaction_center.basic_system_skill"
        return result

    def _route_basic_system_skill_semantic(self, *, text: str, from_voice: bool = False) -> dict[str, Any]:
        try:
            from services.runtime.interaction.system_skill_semantic_router import SystemSkillSemanticRouter

            router = SystemSkillSemanticRouter(model_config=self._current_model_config())
            result = router.route(text, from_voice=from_voice)
        except Exception as exc:
            return {
                "route": "chat_reply",
                "matched": False,
                "source": "language_interaction_center.basic_system_skill_semantic",
                "debug_summary": {"semantic_router_error": str(exc)},
            }
        if not isinstance(result, dict):
            print("[SystemSkillSemantic] miss reason='invalid_result' error_kind=''")
            return {"route": "chat_reply", "matched": False}
        if str(result.get("route", "") or "") == "system_skill":
            next_result = dict(result)
            next_result["source"] = "language_interaction_center.basic_system_skill_semantic"
            print(
                "[SystemSkillSemantic] "
                f"hit action={str(next_result.get('action', '') or '')!r} "
                f"confidence={next_result.get('confidence', 0.0)!r}"
            )
            return next_result
        print(
            "[SystemSkillSemantic] "
            f"miss reason={str(result.get('reason', '') or '')!r} "
            f"error_kind={str(result.get('error_kind', '') or '')!r}"
        )
        return result

    def route_desktop_command(
        self,
        *,
        text: str,
        from_voice: bool = False,
        classifier_result: Any = None,
        actor_role: str = "",
    ) -> dict[str, Any]:
        role = str(actor_role or self._actor_role()).strip() or "normal_user"
        try:
            from services.desktop.tianting.desktop_command_detector import DesktopCommandDetector

            detector = DesktopCommandDetector()
            return detector.detect(
                text,
                input_channel="voice" if from_voice else "text",
                actor_role=role,
                classifier_result=classifier_result,
            )
        except Exception as exc:
            return {
                "schema_version": "desktop_route_decision_v1",
                "raw_user_text": text,
                "input_channel": "voice" if from_voice else "text",
                "actor_role": role,
                "route": "chat_reply",
                "confidence": 0.0,
                "matched_rules": [],
                "action_hint": "",
                "target_hint": {},
                "pending_task_id": "",
                "safe_user_message": "",
                "allow_direct_execution": False,
                "requires_qin_review": True,
                "debug_summary": {"detector_error": str(exc)},
            }

    def route_pending_followup(
        self,
        *,
        text: str,
        desktop_route: dict[str, Any],
        from_voice: bool = False,
        actor_role: str = "",
    ) -> dict[str, Any]:
        route = str((desktop_route or {}).get("route", "") or "")
        if route != "chat_reply":
            return desktop_route
        compact = str(text or "").strip().lower().replace(" ", "")
        try:
            from services.desktop.language.language_service import DesktopLanguageService

            language_service = DesktopLanguageService()
            profile = language_service.profile_for_text(text)
            pending_words: list[str] = []
            for path in ("pending.confirm_words", "pending.cancel_words", "pending.choice_words"):
                pending_words.extend(language_service.list(profile, path))
        except Exception:
            pending_words = []
        normalized_pending_words = {
            str(word or "").strip().lower().replace(" ", "")
            for word in pending_words
            if str(word or "").strip()
        }
        if compact not in normalized_pending_words:
            return desktop_route
        try:
            from services.desktop.tianting.pending_task_service import get_latest_pending_task

            pending = get_latest_pending_task()
        except Exception:
            pending = None
        if not isinstance(pending, dict):
            return desktop_route
        role = str(actor_role or (desktop_route or {}).get("actor_role", "") or self._actor_role()).strip()
        next_route = dict(desktop_route or {})
        next_route.update({
            "route": "pending_followup",
            "input_channel": "voice" if from_voice else "text",
            "actor_role": role,
            "confidence": 0.94,
            "matched_rules": [*list(next_route.get("matched_rules", []) or []), "language_interaction_center_pending_followup"],
            "pending_task_id": str(pending.get("pending_task_id", "") or ""),
            "allow_direct_execution": False,
            "requires_qin_review": True,
        })
        return next_route

    def handle_pending_ui_action(
        self,
        event: dict[str, Any],
        *,
        project_root: Any,
        selected_candidate_fn: Any,
        execute_app_close_fn: Any,
        execute_app_launch_fn: Any,
        desktop_safe_payload_fn: Any,
    ) -> dict[str, Any]:
        payload = event if isinstance(event, dict) else {}
        print(f"[PendingUI] event={payload!r}")
        pending_task_id = str(payload.get("pending_task_id", "") or "").strip()
        action = str(payload.get("action", "") or "").strip()
        if not pending_task_id:
            return desktop_safe_payload_fn(
                ok=False,
                status="failed",
                message_key="desktop.exec.failed_generic",
                fallback="桌面操作未能完成。",
                executed=False,
            )

        try:
            from services.desktop.tianting.pending_task_service import PendingTaskService

            pending_service = PendingTaskService(project_root)
            pending = pending_service.get_pending_task(pending_task_id)
            if not isinstance(pending, dict):
                return desktop_safe_payload_fn(
                    ok=False,
                    status="failed",
                    message_key="desktop.exec.failed_generic",
                    message_params={"target": ""},
                    fallback="桌面操作未能完成。",
                    executed=False,
                )

            choice_type = str(pending.get("choice_type", "") or "")
            print(f"[PendingUI] choice_type={choice_type!r}")

            if action == "cancel":
                pending_service.cancel_pending_task(pending_task_id)
                return desktop_safe_payload_fn(
                    ok=True,
                    status="choice_cancelled",
                    message_key="desktop.exec.cancelled",
                    fallback="已取消本次操作。",
                    executed=False,
                    extra={"pending_task_id": pending_task_id, "cancelled": True},
                )

            if action not in {"confirm", "select_candidate"}:
                return desktop_safe_payload_fn(
                    ok=False,
                    status="failed",
                    message_key="desktop.exec.failed_generic",
                    fallback="桌面操作未能完成。",
                    executed=False,
                )

            selected_candidate = selected_candidate_fn(pending, payload)
            if not selected_candidate:
                return desktop_safe_payload_fn(
                    ok=False,
                    status="choice_invalid",
                    message_key="desktop.generic.choice_invalid",
                    fallback="选择无效，请重新选择。",
                    executed=False,
                    extra={"pending_task_id": pending_task_id},
                )

            pending_service.complete_pending_task(pending_task_id, selected_candidate)
            resolution = {
                "ok": True,
                "status": "choice_resolved",
                "pending_task_id": pending_task_id,
                "selected_candidate": selected_candidate,
                "original_task_draft": pending.get("original_task_draft", {})
                if isinstance(pending.get("original_task_draft"), dict)
                else {},
                "original_user_text": str(pending.get("original_user_text", "") or ""),
                "choice_type": choice_type,
                "executed": False,
                "allow_direct_execution": False,
            }

            if choice_type == "app_close_candidate":
                print("[PendingUI] executing app_close via Qin ...")
                result = execute_app_close_fn(resolution)
            elif choice_type in {"app_launch_candidate", "app_launch_confirmation"}:
                print("[PendingUI] executing app_launch via Qin ...")
                result = execute_app_launch_fn(resolution)
            else:
                result = desktop_safe_payload_fn(
                    ok=False,
                    status="failed",
                    message_key="desktop.exec.failed_generic",
                    fallback="桌面操作未能完成。",
                    executed=False,
                    extra={"pending_task_id": pending_task_id, "choice_type": choice_type},
                )

            result_payload = result if isinstance(result, dict) else {}
            result_data = result_payload.get("data", {}) if isinstance(result_payload.get("data"), dict) else {}
            print(
                "[PendingUI] result "
                f"ok={bool(result_payload.get('ok', False))!r} "
                f"executed={bool(result_payload.get('executed', result_data.get('executed', False)))!r} "
                f"status={str(result_payload.get('status', result_data.get('status', '')) or '')!r}"
            )
            result_payload["pending_task_id"] = pending_task_id
            plan = self.build_memory_plan_from_pending_result(
                pending=pending,
                resolution=resolution,
                result_payload=result_payload,
            )
            result_payload["memory_update_plan"] = plan
            result_payload["memory_update_result"] = self.apply_memory_update_plan(
                project_root=project_root,
                plan=plan,
                result_payload=result_payload,
            )
            return result_payload
        except Exception as exc:
            print(f"[PendingUI] failed error={exc!r}")
            return desktop_safe_payload_fn(
                ok=False,
                status="failed",
                message_key="desktop.exec.failed_generic",
                message_params={"target": ""},
                fallback=f"桌面操作未能完成：{exc}",
                executed=False,
                extra={"error": str(exc), "pending_task_id": pending_task_id},
            )

    def build_memory_plan_from_pending_result(
        self,
        *,
        pending: dict[str, Any],
        resolution: dict[str, Any],
        result_payload: dict[str, Any],
    ) -> dict[str, Any]:
        pending_data = pending if isinstance(pending, dict) else {}
        resolution_data = resolution if isinstance(resolution, dict) else {}
        result_data = result_payload if isinstance(result_payload, dict) else {}
        choice_type = str(pending_data.get("choice_type", resolution_data.get("choice_type", "")) or "")
        selected = (
            resolution_data.get("selected_candidate", {})
            if isinstance(resolution_data.get("selected_candidate"), dict)
            else {}
        )
        ok = bool(result_data.get("ok", False))
        executed = bool(result_data.get("executed", False))

        if choice_type not in {"app_launch_candidate", "app_launch_confirmation"}:
            return build_memory_update_plan(
                enabled=False,
                reason="unsupported_choice_type",
                memory_domain="software" if choice_type.startswith("app_launch") else "",
                source="pending_confirmed_qin_success",
            )
        if not (ok and executed and selected):
            return build_memory_update_plan(
                enabled=False,
                reason="not_confirmed_or_not_executed",
                memory_domain="software",
                source="pending_confirmed_qin_success",
            )

        target_label = self._candidate_text(
            selected,
            "label",
            "target_label",
            "name",
            "target_name",
        )
        term = self._pending_memory_term(pending_data, selected)
        if not target_label:
            return build_memory_update_plan(
                enabled=False,
                reason="missing_target_label",
                memory_domain="software",
                term=term,
                source="pending_confirmed_qin_success",
            )
        if not term:
            term = target_label

        return build_memory_update_plan(
            enabled=True,
            reason="pending_confirmed_qin_success",
            memory_domain="software",
            term=term,
            target_label=target_label,
            target_app_id=self._candidate_text(selected, "app_id", "target_app_id"),
            canonical_app_id=self._candidate_text(selected, "canonical_app_id"),
            aliases=[],
            confidence=0.95,
            source="pending_confirmed_qin_success",
            requires_user_confirm=False,
            confirmed=True,
            extra={
                "debug": {
                    "choice_type": choice_type,
                    "pending_task_id": str(pending_data.get("pending_task_id", "") or ""),
                }
            },
        )

    def apply_memory_update_plan(
        self,
        *,
        project_root: Any,
        plan: dict[str, Any],
        result_payload: dict[str, Any],
    ) -> dict[str, Any]:
        plan_data = plan if isinstance(plan, dict) else {}
        result_data = result_payload if isinstance(result_payload, dict) else {}
        memory_domain = str(plan_data.get("memory_domain", "") or "")
        term = str(plan_data.get("term", "") or "").strip()
        target_label = str(plan_data.get("target_label", "") or "").strip()

        if not bool(plan_data.get("enabled", False)):
            return {
                "ok": True,
                "status": "memory_skipped",
                "reason": str(plan_data.get("reason", "plan_disabled") or "plan_disabled"),
                "memory_domain": memory_domain,
                "term": term,
                "target_label": target_label,
            }
        if not (
            bool(plan_data.get("confirmed", False))
            and memory_domain == "software"
            and bool(result_data.get("ok", False))
            and bool(result_data.get("executed", False))
            and target_label
        ):
            return {
                "ok": True,
                "status": "memory_skipped",
                "reason": "write_conditions_not_met",
                "memory_domain": memory_domain,
                "term": term,
                "target_label": target_label,
            }

        try:
            from services.desktop.tianting.command_memory_service import CommandMemoryService

            service = CommandMemoryService()
            writer = getattr(service, "promote_confirmed_term", None)
            if not callable(writer):
                return {
                    "ok": True,
                    "status": "memory_skipped",
                    "reason": "writer_not_available",
                    "memory_domain": memory_domain,
                    "term": term,
                    "target_label": target_label,
                }
            written = writer(
                "software_terms",
                term,
                target_label,
                aliases=plan_data.get("aliases", []) if isinstance(plan_data.get("aliases"), list) else [],
                source_card_id=str(plan_data.get("source", "") or ""),
                overwrite=False,
                target_app_id=str(plan_data.get("target_app_id", "") or ""),
                canonical_app_id=str(plan_data.get("canonical_app_id", "") or ""),
            )
            written_data = written if isinstance(written, dict) else {}
            return {
                "ok": bool(written_data.get("ok", False)),
                "status": "memory_written" if bool(written_data.get("ok", False)) else "memory_failed",
                "reason": str(written_data.get("reason", "") or ""),
                "memory_domain": memory_domain,
                "term": term,
                "target_label": target_label,
                "raw_result": written_data,
            }
        except Exception as exc:
            return {
                "ok": False,
                "status": "memory_failed",
                "reason": str(exc),
                "memory_domain": memory_domain,
                "term": term,
                "target_label": target_label,
            }

    def complete_pending_resolution_memory(
        self,
        *,
        project_root: Any,
        resolution: dict[str, Any],
        result_payload: dict[str, Any],
    ) -> dict[str, Any]:
        payload = result_payload if isinstance(result_payload, dict) else {}
        resolution_data = resolution if isinstance(resolution, dict) else {}
        pending_task_id = str(
            resolution_data.get("pending_task_id", payload.get("pending_task_id", ""))
            or ""
        ).strip()
        if not pending_task_id:
            payload["memory_update_plan"] = build_memory_update_plan(
                enabled=False,
                reason="missing_pending_task_id",
                source="pending_confirmed_qin_success",
            )
            payload["memory_update_result"] = {
                "ok": True,
                "status": "memory_skipped",
                "reason": "missing_pending_task_id",
                "memory_domain": "",
                "term": "",
                "target_label": "",
            }
            return payload

        try:
            from services.desktop.tianting.pending_task_service import PendingTaskService

            pending = PendingTaskService(project_root).get_pending_task(pending_task_id)
        except Exception:
            pending = None
        pending_data = pending if isinstance(pending, dict) else {}
        if not pending_data:
            payload["memory_update_plan"] = build_memory_update_plan(
                enabled=False,
                reason="pending_not_found",
                source="pending_confirmed_qin_success",
            )
            payload["memory_update_result"] = {
                "ok": True,
                "status": "memory_skipped",
                "reason": "pending_not_found",
                "memory_domain": "",
                "term": "",
                "target_label": "",
            }
            return payload

        if "choice_type" not in resolution_data:
            resolution_data = dict(resolution_data)
            resolution_data["choice_type"] = str(pending_data.get("choice_type", "") or "")
        if "selected_candidate" not in resolution_data and isinstance(pending_data.get("selected_candidate"), dict):
            resolution_data = dict(resolution_data)
            resolution_data["selected_candidate"] = pending_data.get("selected_candidate", {})

        plan = self.build_memory_plan_from_pending_result(
            pending=pending_data,
            resolution=resolution_data,
            result_payload=payload,
        )
        payload["memory_update_plan"] = plan
        payload["memory_update_result"] = self.apply_memory_update_plan(
            project_root=project_root,
            plan=plan,
            result_payload=payload,
        )
        return payload

    def _pending_memory_term(self, pending: dict[str, Any], selected_candidate: dict[str, Any]) -> str:
        task = pending.get("original_task_draft", {}) if isinstance(pending.get("original_task_draft"), dict) else {}
        target = task.get("target", {}) if isinstance(task.get("target"), dict) else {}
        arguments = task.get("arguments", {}) if isinstance(task.get("arguments"), dict) else {}
        for source in (target, arguments):
            text = self._candidate_text(
                source,
                "label_hint",
                "app_hint",
                "name_hint",
                "target_label_hint",
                "target_name",
                "app_name",
                "identity",
            )
            if text:
                return text
        return self._candidate_text(
            selected_candidate,
            "label",
            "target_label",
            "name",
            "target_name",
        )

    def _candidate_text(self, source: dict[str, Any], *keys: str) -> str:
        data = source if isinstance(source, dict) else {}
        for key in keys:
            value = str(data.get(key, "") or "").strip()
            if value:
                return value
        return ""

    def route_through_jiuchasi(
        self,
        *,
        text: str,
        actor_role: str,
        input_channel: str,
        desktop_route: dict[str, Any],
        task_draft: dict[str, Any],
        understanding_packet: dict[str, Any],
        project_root: Any,
        jiuchasi_enabled_fn: Any,
        allow_llm_reply_fn: Any,
        allow_llm_thinking_fn: Any,
        dry_run_only_fn: Any,
        target_from_task_draft_fn: Any,
        apply_qin_task_patch_fn: Any,
        result_to_safe_payload_fn: Any,
    ) -> dict[str, Any] | None:
        if not jiuchasi_enabled_fn():
            return None
        action = str(task_draft.get("action", "") or (desktop_route or {}).get("action_hint", "") or "").strip()
        if action.startswith("desktop.connection."):
            return None
        try:
            from services.desktop.qin.yushitai.report_writer import ReportWriter
            from services.desktop.qin.yushitai.runtime_material_writer import RuntimeMaterialWriter
            from services.desktop.tianting.jiuchasi.jiuchasi_service import JiuchasiService

            target_normalized = target_from_task_draft_fn(
                task_draft,
                understanding_packet=understanding_packet,
            )
            report_writer = ReportWriter(project_root)
            material_writer = RuntimeMaterialWriter(report_writer)
            service = JiuchasiService(
                project_root=project_root,
                allow_llm_reply=allow_llm_reply_fn(),
                allow_llm_thinking=allow_llm_thinking_fn(),
                material_writer=material_writer,
                backend="host",
            )
            needs: list[str] = []
            if action.startswith("folder.") or action.startswith("file."):
                needs.extend(["file_roots", "file_candidates"])
            if action.startswith("app.") or action == "desktop.resolve":
                needs.append("software_governance")
            if action == "desktop.resolve":
                needs.append("file_roots")
            needs = list(dict.fromkeys(needs))

            result = service.handle(
                user_text=text,
                action_hint=action,
                target_normalized=target_normalized,
                route_hint={
                    **dict(desktop_route or {}),
                    "actor_role": actor_role,
                    "input_channel": input_channel,
                },
                understanding_packet=understanding_packet,
                original_task_draft=task_draft,
                needs=needs,
            )
            patched_task_draft = apply_qin_task_patch_fn(
                task_draft,
                result.get("qin_task_patch", {}) if isinstance(result, dict) else {},
                jiuchasi_session_id=str((result or {}).get("session_id", "") or ""),
            )
            safe_payload = result_to_safe_payload_fn(
                user_text=text,
                jiuchasi_result=result,
                patched_task_draft=patched_task_draft,
            )
            print(
                "[JiuchasiBridge] "
                f"status={safe_payload.get('status', '')!r} "
                f"dry_run={dry_run_only_fn()} "
                f"session_id={str((result or {}).get('session_id', '') or '')!r}"
            )
            return safe_payload
        except Exception as exc:
            print(f"[JiuchasiBridge] failed error={exc}")
            return None

    def _current_model_config(self) -> dict[str, Any]:
        controller = self.controller
        router = getattr(controller, "model_router_service", None)
        if router is None or not hasattr(router, "get_current_chat_model"):
            return {}
        try:
            model = router.get_current_chat_model()
        except Exception:
            return {}
        return dict(model) if isinstance(model, dict) else {}

    def _actor_role(self) -> str:
        controller = self.controller
        getter = getattr(controller, "get_desktop_actor_role", None)
        if callable(getter):
            try:
                return str(getter() or "")
            except Exception:
                return ""
        return ""

    def handle_user_input(self, context: dict[str, Any] | None = None) -> dict[str, Any]:
        return self.passthrough_chat(context)
