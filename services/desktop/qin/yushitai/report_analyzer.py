from __future__ import annotations

from typing import Any

from services.desktop.qin.yushitai.report_schema import YushitaiReport, new_report_metadata


class ReportAnalyzer:
    """Build a read-only Yushitai report from collected data."""

    def analyze(self, collected: dict[str, Any], *, stage: str = "v3_03_preflight") -> dict[str, Any]:
        yushitai_events = collected.get("yushitai_events", []) if isinstance(collected.get("yushitai_events"), list) else []
        audit_events = collected.get("audit_events", []) if isinstance(collected.get("audit_events"), list) else []
        primary_events = yushitai_events or audit_events
        checkpoints = collected.get("checkpoints", []) if isinstance(collected.get("checkpoints"), list) else []
        materials = collected.get("shaofu_restore_registry", []) if isinstance(collected.get("shaofu_restore_registry"), list) else []
        memories = collected.get("vm_connection_memory", []) if isinstance(collected.get("vm_connection_memory"), list) else []
        runtime_state = collected.get("runtime_state", {}) if isinstance(collected.get("runtime_state"), dict) else {}

        sandbox_actions = self._count_backend(primary_events, "sandbox")
        vm_actions = self._count_backend(primary_events, "vm")
        host_blocked = len([
            item for item in primary_events
            if self._value(item, "backend").strip().lower() == "host"
            or self._value(item, "adapter_id").strip().lower() in {"host", "host_windows"}
            or self._value(item, "route_result").strip().lower().startswith("host.")
            or "host execution" in self._value(item, "reason").strip().lower()
        ])
        primary_failures = [
            self._normalize_failure(item)
            for item in primary_events
            if self._is_failed(item)
        ]
        checkpoint_failures = [
            self._normalize_failure(item)
            for item in checkpoints[-30:]
            if self._is_failed(item)
        ]
        merged_failures = self._dedupe_failures(primary_failures + checkpoint_failures)
        failed_actions = len(merged_failures)
        dangerous_actions = len([
            item for item in primary_events
            if self._value(item, "action").strip().lower() in {
                "app.uninstall", "app.move", "app.relocate", "app.update",
                "file.delete", "file.move", "file.rename", "file.copy", "file.mkdir", "file.touch",
            }
        ])
        vm_attempts = len(memories)
        vm_success = len([item for item in memories if bool(item.get("ok", False))])
        durations = [
            float(item.get("duration_ms", 0) or 0)
            for item in memories
            if float(item.get("duration_ms", 0) or 0) > 0
        ]
        avg_duration = round(sum(durations) / len(durations), 2) if durations else 0.0
        recent_failures = merged_failures[-10:]
        breakpoints = self._breakpoints(primary_events + checkpoints[-30:], materials)

        latest_memory = memories[-1] if memories else {}
        vm_software_count = self._safe_int(
            runtime_state.get("vm_apps_count", latest_memory.get("apps_count", 0))
        )
        vm_software_raw_count = self._safe_int(runtime_state.get("vm_software_raw_count", vm_software_count))
        vm_software_final_count = self._safe_int(runtime_state.get("vm_software_final_count", vm_software_count))
        vm_software_hidden_count = self._safe_int(runtime_state.get("vm_software_hidden_count", 0))
        vm_software_merged_uninstallers = self._safe_int(runtime_state.get("vm_software_merged_uninstallers", 0))
        desktop_mode = str(runtime_state.get("desktop_mode", runtime_state.get("current_mode", "")) or "")
        effective_test_backend = str(runtime_state.get("test_backend", "") or "") if desktop_mode == "test" else ""
        execution_backend = str(runtime_state.get("execution_backend", effective_test_backend if desktop_mode == "test" else "none") or "")
        host_execution_enabled = bool(runtime_state.get("host_execution_enabled", False))
        report = YushitaiReport(
            metadata=new_report_metadata(stage=stage),
            summary={
                "overall_status": "warning" if failed_actions or (vm_attempts and vm_success == 0) else "ok",
                "total_actions": len(primary_events),
                "current_run_events": len(yushitai_events),
                "long_term_audit_events": len(audit_events),
                "failed_actions": failed_actions,
                "vm_connected": bool(latest_memory.get("ok", False)),
                "vm_software_count": vm_software_count,
                "vm_software_raw_count": vm_software_raw_count,
                "vm_software_final_count": vm_software_final_count,
                "vm_software_hidden_count": vm_software_hidden_count,
                "vm_software_merged_uninstallers": vm_software_merged_uninstallers,
            },
            system_state={
                "current_backend": effective_test_backend,
                "test_backend": effective_test_backend,
                "execution_backend": execution_backend,
                "desktop_mode": desktop_mode,
                "governance_mode": desktop_mode,
                "host_execution_enabled": host_execution_enabled,
                "vm_connected": bool(latest_memory.get("ok", False)),
                "vm_software_count": vm_software_count,
                "vm_software_raw_count": vm_software_raw_count,
                "vm_software_final_count": vm_software_final_count,
                "vm_software_hidden_count": vm_software_hidden_count,
                "vm_software_merged_uninstallers": vm_software_merged_uninstallers,
            },
            exit_matrix={
                "sandbox_actions": sandbox_actions,
                "vm_actions": vm_actions,
                "host_blocked_actions": host_blocked,
            },
            department_coverage={
                "menxia_review": True,
                "gongbu_execution": True,
                "libu_checkpoint": bool(checkpoints),
                "xingbu_confirm": True,
                "bingbu_guard": True,
                "liyi_receipt": True,
                "hubu_metrics": True,
                "shaofu_material": bool(materials),
            },
            vm_quality={
                "vm_connect_attempts": vm_attempts,
                "vm_connect_success": vm_success,
                "vm_connect_failed": max(0, vm_attempts - vm_success),
                "avg_vm_connect_duration_ms": avg_duration,
                "vm_software_count": vm_software_count,
                "vm_software_raw_count": vm_software_raw_count,
                "vm_software_final_count": vm_software_final_count,
                "vm_software_hidden_count": vm_software_hidden_count,
                "vm_software_merged_uninstallers": vm_software_merged_uninstallers,
                "latest": latest_memory,
                "vm_agent_version": latest_memory.get("agent_version", ""),
                "vm_protocol_version": latest_memory.get("protocol_version", ""),
            },
            dangerous_action_supervision={
                "dangerous_actions": dangerous_actions,
                "requires_confirm": True,
                "checkpoint_before_vm": True,
                "materials": len(materials),
                "confirm_modes": self._count_material_field(materials, "confirm_mode"),
                "shaofu_locations": self._count_material_field(materials, "shaofu_location"),
                "retention_policies": self._count_material_field(materials, "retention_policy"),
                "material_records": self._material_records(materials),
                "breakpoints": breakpoints,
            },
            checkpoints={
                "active_checkpoints": len(checkpoints),
                "latest": checkpoints[-1] if checkpoints else {},
            },
            recent_failures=recent_failures,
            risk_assessment={
                "level": "medium" if failed_actions or dangerous_actions else "low",
                "host_execution_enabled": host_execution_enabled,
                "vm_failure_fallback_blocked": True,
                "breakpoints": breakpoints,
            },
            recommendations=self._recommendations(
                failed_actions=failed_actions,
                vm_attempts=vm_attempts,
                vm_success=vm_success,
                breakpoints=breakpoints,
            ),
            raw_refs=collected.get("paths", {}) if isinstance(collected.get("paths"), dict) else {},
        )
        return report.to_dict()

    def _count_adapter(self, events: list[dict[str, Any]], adapter_id: str) -> int:
        normalized = str(adapter_id or "").strip().lower()
        return len([item for item in events if str(item.get("adapter_id", "")).strip().lower() == normalized])

    def _count_backend(self, events: list[dict[str, Any]], backend: str) -> int:
        normalized = str(backend or "").strip().lower()
        return len([
            item for item in events
            if self._value(item, "backend").strip().lower() == normalized
            or self._value(item, "adapter_id").strip().lower() == normalized
            or self._nested_value(item, ("result", "executed_in")).strip().lower() == normalized
        ])

    def _value(self, item: dict[str, Any], key: str) -> str:
        value = item.get(key, "")
        if value not in (None, ""):
            return str(value)
        data = item.get("data", {}) if isinstance(item.get("data"), dict) else {}
        result = item.get("result", {}) if isinstance(item.get("result"), dict) else {}
        return str(data.get(key, result.get(key, "")) or "")

    def _nested_value(self, item: dict[str, Any], path: tuple[str, ...]) -> str:
        value: Any = item
        for key in path:
            if not isinstance(value, dict):
                return ""
            value = value.get(key, "")
        return str(value or "")

    def _deep_get(self, item: dict[str, Any], path: tuple[str, ...] | list[str] | str, default: Any = None) -> Any:
        keys = tuple(path.split(".")) if isinstance(path, str) else tuple(path)
        value: Any = item
        for key in keys:
            if not isinstance(value, dict) or key not in value:
                return default
            value = value.get(key)
        return value

    def _deep_bool_false(self, item: dict[str, Any], paths: list[tuple[str, ...]]) -> bool:
        sentinel = object()
        for path in paths:
            value = self._deep_get(item, path, sentinel)
            if value is False:
                return True
        return False

    def _deep_error_present(self, item: dict[str, Any], paths: list[tuple[str, ...]]) -> bool:
        sentinel = object()
        for path in paths:
            value = self._deep_get(item, path, sentinel)
            if value is sentinel or value is None:
                continue
            if str(value).strip():
                return True
        return False

    def _http_status(self, item: dict[str, Any], paths: list[tuple[str, ...]]) -> int:
        for path in paths:
            value = self._deep_get(item, path)
            try:
                status = int(value)
            except Exception:
                continue
            if status > 0:
                return status
        return 0

    def _http_failed(self, item: dict[str, Any]) -> bool:
        return self._http_status(item, [
            ("data", "result", "data", "http_status"),
            ("result", "http_status"),
            ("raw", "result", "data", "http_status"),
            ("raw", "result", "http_status"),
            ("data", "http_status"),
        ]) >= 400

    def _is_failed(self, item: dict[str, Any]) -> bool:
        decision = self._value(item, "decision").strip().lower()
        if decision in {"deny", "confirm_required"}:
            return True
        if self._deep_bool_false(item, [
            ("ok",),
            ("result", "ok"),
            ("data", "ok"),
            ("data", "result", "ok"),
            ("raw", "result", "ok"),
            ("after_state", "ok"),
            ("checkpoint", "after_state", "ok"),
            ("checkpoint", "data", "result", "ok"),
        ]):
            return True
        if self._http_failed(item):
            return True
        return self._deep_error_present(item, [
            ("data", "result", "data", "error"),
            ("raw", "result", "data", "error"),
            ("result", "error"),
            ("raw", "result", "error"),
            ("after_state", "error"),
            ("checkpoint", "after_state", "error"),
            ("error",),
        ])

    def _first_text(self, item: dict[str, Any], paths: list[tuple[str, ...]], default: str = "") -> str:
        for path in paths:
            value = self._deep_get(item, path)
            if value not in (None, ""):
                return str(value)
        return default

    def _normalize_failure(self, item: dict[str, Any]) -> dict[str, Any]:
        target = item.get("target", {}) if isinstance(item.get("target"), dict) else {}
        checkpoint = item.get("checkpoint", {}) if isinstance(item.get("checkpoint"), dict) else {}
        material = item.get("material", {}) if isinstance(item.get("material"), dict) else {}
        action = self._first_text(item, [
            ("action",),
            ("checkpoint", "action"),
            ("data", "result", "action"),
            ("raw", "result", "action"),
        ], "-")
        target_name = str(
            target.get("name", "")
            or item.get("target_name", "")
            or checkpoint.get("target_name", "")
            or "-"
        )
        error = self._first_text(item, [
            ("error",),
            ("result", "error"),
            ("data", "result", "error"),
            ("data", "result", "data", "error"),
            ("raw", "result", "error"),
            ("raw", "result", "data", "error"),
            ("after_state", "error"),
            ("checkpoint", "after_state", "error"),
        ], "")
        error_category = self._first_text(item, [
            ("error_category",),
            ("result", "error_category"),
            ("data", "result", "data", "error_category"),
            ("raw", "result", "data", "error_category"),
        ], "")
        message = self._first_text(item, [
            ("message",),
            ("result", "message"),
            ("data", "result", "message"),
            ("data", "result", "data", "message"),
            ("raw", "result", "message"),
            ("raw", "result", "data", "message"),
            ("after_state", "message"),
            ("checkpoint", "after_state", "message"),
        ], "")
        reason = self._first_text(item, [
            ("reason",),
            ("review", "reason"),
            ("data", "review_reason"),
            ("decision",),
        ], "")
        return {
            "action": action or "-",
            "target_name": target_name or "-",
            "request_id": self._first_text(item, [
                ("request_id",),
                ("result", "request_id"),
                ("data", "request_id"),
                ("data", "result", "request_id"),
                ("data", "result", "data", "request_id"),
                ("raw", "result", "request_id"),
                ("raw", "result", "data", "request_id"),
            ], ""),
            "checkpoint_id": self._first_text(item, [
                ("checkpoint_id",),
                ("checkpoint", "checkpoint_id"),
                ("data", "checkpoint_id"),
                ("result", "checkpoint_id"),
                ("raw", "result", "data", "checkpoint_id"),
            ], ""),
            "material_id": self._first_text(item, [
                ("material_id",),
                ("material", "material_id"),
                ("data", "material_id"),
                ("result", "material_id"),
                ("raw", "result", "data", "material_id"),
            ], ""),
            "message": message,
            "error": error,
            "error_category": error_category,
            "move_mode": self._first_text(item, [
                ("data", "move_mode"),
                ("material", "move_mode"),
                ("checkpoint", "move_mode"),
                ("raw", "result", "data", "move_mode"),
            ], ""),
            "relocate_strategy": self._first_text(item, [
                ("data", "relocate_strategy"),
                ("material", "relocate_strategy"),
                ("checkpoint", "relocate_strategy"),
                ("raw", "result", "data", "relocate_strategy"),
            ], ""),
            "relocate_status": self._first_text(item, [
                ("data", "relocate_status"),
                ("material", "relocate_status"),
                ("checkpoint", "relocate_status"),
                ("raw", "result", "data", "relocate_status"),
            ], ""),
            "execution_backend": self._first_text(item, [
                ("execution_backend",),
                ("data", "execution_backend"),
                ("raw", "result", "data", "execution_backend"),
            ], ""),
            "target_environment": self._first_text(item, [
                ("target_environment",),
                ("data", "target_environment"),
                ("raw", "result", "data", "target_environment"),
            ], ""),
            "path_namespace": self._first_text(item, [
                ("path_namespace",),
                ("data", "path_namespace"),
                ("raw", "result", "data", "path_namespace"),
            ], ""),
            "http_status": self._http_status(item, [
                ("data", "result", "data", "http_status"),
                ("result", "http_status"),
                ("raw", "result", "data", "http_status"),
                ("raw", "result", "http_status"),
                ("data", "http_status"),
            ]),
            "shaofu_location": self._first_text(item, [
                ("material", "shaofu_location"),
                ("data", "shaofu_location"),
                ("raw", "result", "data", "shaofu_location"),
            ], ""),
            "confirm_mode": self._first_text(item, [
                ("material", "confirm_mode"),
                ("data", "confirm_mode"),
                ("raw", "result", "data", "confirm_mode"),
            ], ""),
            "retention_policy": self._first_text(item, [
                ("material", "retention_policy"),
                ("data", "retention_policy"),
            ], ""),
            "retain_until": self._first_text(item, [
                ("material", "retain_until"),
                ("data", "retain_until"),
            ], ""),
            "restore_token": self._first_text(item, [
                ("material", "restore_token"),
                ("data", "restore_token"),
            ], ""),
            "reason": reason,
        }

    def _dedupe_failures(self, failures: list[dict[str, Any]]) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        seen: set[str] = set()
        for item in failures:
            request_key = str(item.get("request_id", "") or "").strip()
            checkpoint_key = str(item.get("checkpoint_id", "") or "").strip()
            key = request_key or checkpoint_key or "|".join([
                str(item.get("material_id", "") or ""),
                str(item.get("action", "") or ""),
                str(item.get("target_name", "") or ""),
                str(item.get("error", item.get("error_category", "")) or ""),
            ])
            if key in seen:
                continue
            seen.add(key)
            result.append(item)
        return result

    def _breakpoints(self, events: list[dict[str, Any]], materials: list[dict[str, Any]]) -> dict[str, int]:
        known = {
            "menxia_rejected",
            "bingbu_emergency_stop",
            "bingbu_throttled",
            "bingbu_circuit_open",
            "xingbu_confirm_required",
            "libu_checkpoint_created",
            "libu_checkpoint_failed",
            "shaofu_material_prepared",
            "shaofu_material_failed",
            "shaofu_missing_strategy",
            "gongbu_execution_failed",
            "vm_adapter_failed",
            "vm_agent_http_error",
            "action_not_enabled_in_agent_config",
            "missing_path",
            "missing_source_path",
            "missing_process_name",
            "missing_update_strategy",
            "host_disabled",
            "vm_profile_not_configured",
            "vm_agent_offline",
            "gui_uninstaller_started",
            "user_confirmation_required",
            "request_timeout",
            "destination_exists",
            "destination_collision",
            "file_locked_or_access_denied",
            "process_close_failed",
            "process_path_still_in_use",
            "source_path_in_use",
            "manual_close_required",
            "original_rename_failed_winerror32",
            "relocate_preflight_failed",
            "admin_required",
            "service_stop_failed",
            "copy_failed",
            "original_rename_failed",
            "junction_create_failed",
            "verify_pending",
            "rollback_required",
            "rollback_failed",
            "path_namespace_mismatch",
            "agent_feature_missing",
            "post_action_vm_health_failed",
            "action_spawned_pending",
            "vm_agent_runtime_version_mismatch",
        }
        counts = {key: 0 for key in sorted(known)}
        for item in events:
            text = " ".join([
                self._value(item, "review_stage"),
                self._value(item, "reason"),
                self._value(item, "error"),
                self._nested_value(item, ("result", "message")),
            ]).lower()
            for key in known:
                marker = key.lower()
                if marker in text or marker.replace("_", " ") in text:
                    counts[key] += 1
            if "http_status" in text or "http error" in text:
                counts["vm_agent_http_error"] += 1
            if "host execution is disabled" in text:
                counts["host_disabled"] += 1
            for key in self._structured_breakpoints(item):
                counts[key] += 1
        for material in materials:
            status = str(material.get("material_status", "") or "").strip().lower()
            error = str(material.get("error", "") or "").strip().lower()
            if status == "ready":
                counts["shaofu_material_prepared"] += 1
            if status == "failed":
                counts["shaofu_material_failed"] += 1
            if status == "missing_strategy" or "missing_strategy" in error:
                counts["shaofu_missing_strategy"] += 1
        return {key: value for key, value in counts.items() if value}

    def _count_material_field(self, materials: list[dict[str, Any]], key: str) -> dict[str, int]:
        result: dict[str, int] = {}
        for item in materials:
            if not isinstance(item, dict):
                continue
            value = str(item.get(key, "") or "").strip().lower() or "unknown"
            result[value] = int(result.get(value, 0) or 0) + 1
        return result

    def _material_records(self, materials: list[dict[str, Any]]) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        for item in materials[-50:]:
            if not isinstance(item, dict):
                continue
            records.append({
                "action": str(item.get("action", "") or ""),
                "material_id": str(item.get("material_id", "") or ""),
                "execution_backend": str(item.get("execution_backend", "") or ""),
                "target_environment": str(item.get("target_environment", "") or ""),
                "shaofu_location": str(item.get("shaofu_location", "") or ""),
                "confirm_mode": str(item.get("confirm_mode", "") or ""),
                "retention_policy": str(item.get("retention_policy", "") or ""),
                "retain_until": str(item.get("retain_until", "") or ""),
                "restore_token": str(item.get("restore_token", "") or ""),
                "material_status": str(item.get("material_status", "") or ""),
                "restore_status": str(item.get("restore_status", "") or ""),
            })
        return records

    def _structured_breakpoints(self, item: dict[str, Any]) -> set[str]:
        points: set[str] = set()
        payloads: list[dict[str, Any]] = [item]
        for path in (
            ("result",),
            ("result", "data"),
            ("data",),
            ("data", "result"),
            ("data", "result", "data"),
            ("raw",),
            ("raw", "result"),
            ("raw", "result", "data"),
            ("after_state",),
            ("checkpoint",),
            ("checkpoint", "after_state"),
            ("checkpoint", "data"),
            ("checkpoint", "data", "result"),
            ("checkpoint", "data", "result", "data"),
            ("material",),
        ):
            value = self._deep_get(item, path)
            if isinstance(value, dict):
                payloads.append(value)
        for payload in payloads:
            status = str(payload.get("status", "") or "").strip().lower()
            error = str(payload.get("error", "") or "").strip().lower()
            error_category = str(payload.get("error_category", "") or "").strip().lower()
            execution_mode = str(payload.get("execution_mode", "") or "").strip().lower()
            http_status_raw = payload.get("http_status", 0)
            try:
                http_code = int(http_status_raw if http_status_raw is not None else 0)
            except (TypeError, ValueError):
                http_code = 0

            if status == "started" and execution_mode == "spawn":
                points.add("gui_uninstaller_started")
                points.add("action_spawned_pending")
            if bool(payload.get("requires_user_confirmation", False)):
                points.add("user_confirmation_required")
            if bool(payload.get("action_spawned_pending", False)):
                points.add("action_spawned_pending")
            if error in {"timeout", "timed_out", "request_timeout"} or "timed out" in error:
                points.add("request_timeout")
            if http_code >= 400:
                points.add("vm_agent_http_error")
            if http_code in {408, 504}:
                points.add("request_timeout")
            if error == "destination_exists":
                points.add("destination_exists")
            if bool(payload.get("destination_collision", False)):
                points.add("destination_collision")
            if error == "process_close_failed" or bool(payload.get("action_blocked_before_move", False)):
                points.add("process_close_failed")
            if error in {"process_path_still_in_use", "source_path_in_use"}:
                points.add("process_path_still_in_use")
                points.add("source_path_in_use")
                points.add("manual_close_required")
            if bool(payload.get("requires_user_close", False)) or bool(payload.get("manual_close_required", False)):
                points.add("manual_close_required")
            relocate_status = str(payload.get("relocate_status", "") or "").strip().lower()
            if relocate_status == "preflight_failed":
                points.add("relocate_preflight_failed")
            if error in {"admin_required", "requires_admin"} or bool(payload.get("admin_required", False)):
                points.add("admin_required")
            if error == "service_stop_failed" or (bool(payload.get("service_stop_attempted", False)) and not bool(payload.get("service_stop_success", True))):
                points.add("service_stop_failed")
            if error == "copy_failed" or relocate_status == "copy_failed":
                points.add("copy_failed")
            if error == "original_rename_failed" or relocate_status == "original_rename_failed":
                points.add("original_rename_failed")
            winerror_raw = payload.get("winerror", "")
            try:
                winerror = int(winerror_raw if winerror_raw not in (None, "") else 0)
            except Exception:
                winerror = 0
            if (
                error_category == "source_path_in_use"
                or bool(payload.get("source_path_in_use", False))
                or (error == "original_rename_failed" and winerror == 32)
                or (relocate_status == "original_rename_failed" and winerror == 32)
            ):
                points.add("source_path_in_use")
                points.add("manual_close_required")
                if error == "original_rename_failed" or relocate_status == "original_rename_failed" or winerror == 32:
                    points.add("original_rename_failed")
                    points.add("original_rename_failed_winerror32")
            if error == "junction_create_failed" or relocate_status == "junction_create_failed":
                points.add("junction_create_failed")
            if bool(payload.get("verify_pending", False)):
                points.add("verify_pending")
            if relocate_status == "rollback_required" or bool(payload.get("rollback_required", False)):
                points.add("rollback_required")
            if relocate_status == "rollback_failed" or bool(payload.get("rollback_failed", False)):
                points.add("rollback_failed")
            if error == "path_namespace_mismatch":
                points.add("path_namespace_mismatch")
            if error == "agent_feature_missing":
                points.add("agent_feature_missing")
            if error_category == "file_locked_or_access_denied" or bool(payload.get("possible_file_locked", False)) or bool(payload.get("file_access_denied", False)):
                points.add("file_locked_or_access_denied")
            if bool(payload.get("close_attempted", False)) and not bool(payload.get("close_success", True)):
                points.add("process_close_failed")
            if error in {"post_action_vm_health_failed", "vm_health_failed"}:
                points.add("post_action_vm_health_failed")
            
        return points

    def _safe_int(self, value: Any) -> int:
        try:
            return int(value or 0)
        except Exception:
            return 0

    def _recommendations(self, *, failed_actions: int, vm_attempts: int, vm_success: int, breakpoints: dict[str, int]) -> list[str]:
        items: list[str] = []
        if vm_attempts and vm_success == 0:
            items.append("请先检查 VM Agent 连接状态，再运行虚拟机执行测试。")
        if breakpoints.get("process_path_still_in_use", 0) or breakpoints.get("source_path_in_use", 0) or breakpoints.get("manual_close_required", 0):
            items.append("检测到软件仍在后台运行。请在虚拟机中完全退出软件，包括托盘图标、后台进程和相关服务后重试迁移。")
        if breakpoints.get("original_rename_failed_winerror32", 0):
            items.append("原安装目录仍被占用，无法改名为备份目录。建议手动退出软件或重启虚拟机后再迁移。")
        if breakpoints.get("admin_required", 0):
            items.append("VM Agent 需要管理员权限运行，才能迁移 Program Files 中的已安装软件。")
        if breakpoints.get("destination_exists", 0):
            items.append("目标目录已存在同名软件文件夹，请选择空目录或先清理测试目录。")
        if breakpoints.get("xingbu_confirm_required", 0):
            items.append("请确认危险动作弹窗已经传递 confirmed=True 后再进入 VM 执行。")
        if breakpoints.get("shaofu_material_failed", 0) or breakpoints.get("shaofu_missing_strategy", 0):
            items.append("请先准备少府恢复材料或测试恢复策略，再执行危险 VM 动作。")
        if breakpoints.get("missing_update_strategy", 0):
            items.append("软件更新测试需要提供 updater_path 或 update_source_dir。")
        if breakpoints.get("action_not_enabled_in_agent_config", 0):
            items.append("请检查 VM Agent 的危险动作开关是否已按测试目标开启。")
        if breakpoints.get("host_disabled", 0):
            items.append("保持 Host 执行禁用，并确认 VM 失败不会回落 Host。")
        if failed_actions:
            items.append("继续扩大测试前，请先复查最近被拒绝或失败的桌面任务。")
        if not items:
            items.append("可以继续 V3/V4 VM-only 验证；Host 执行仍保持禁用。")
        return items
