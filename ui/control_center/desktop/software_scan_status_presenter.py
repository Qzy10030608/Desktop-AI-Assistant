from __future__ import annotations

from typing import Any


class SoftwareScanStatusPresenter:
    def _profile_label(self, runtime) -> str:
        profile = str(getattr(runtime, "software_scan_profile", "quick") or "quick").strip().lower()
        return "快速扫描" if profile == "quick" else "完整扫描"

    def format_stage_text(self, runtime) -> str:
        stage = str(getattr(runtime, "software_scan_stage", "") or "").strip()
        message = str(getattr(runtime, "software_scan_message", "") or "").strip()
        label = self._profile_label(runtime)
        if not stage and not message:
            return "扫描状态：空闲"
        if not message:
            return f"扫描状态：{label} / {stage}"
        return f"扫描状态：{label} / {stage}\n说明：{message}"

    def format_stats_text(self, runtime) -> str:
        stats = getattr(runtime, "software_scan_progress_stats", None) or {}
        if not isinstance(stats, dict) or not stats:
            return "扫描统计：-"

        mapping = [
            ("raw_total", "raw"),
            ("filter_after_total", "filtered"),
            ("dedupe_after_total", "deduped"),
            ("strong_candidate_count", "strong"),
            ("weak_candidate_count", "weak"),
        ]

        parts: list[str] = []
        for key, label in mapping:
            value = stats.get(key)
            if value is None:
                continue
            parts.append(f"{label}={value}")

        if not parts:
            return "扫描统计：-"

        first_line = " | ".join(parts[:3])
        second_line = " | ".join(parts[3:])
        if second_line:
            return f"扫描统计：{first_line}\n{second_line}"
        return f"扫描统计：{first_line}"

    def format_log_preview(self, runtime, *, limit: int = 3) -> str:
        lines = getattr(runtime, "software_scan_log_lines", None) or []
        if not isinstance(lines, list) or not lines:
            return "最近日志：-"
        preview = [str(item).strip() for item in lines[-limit:] if str(item).strip()]
        if not preview:
            return "最近日志：-"
        return "最近日志：\n" + "\n".join(preview)

    def append_log(self, runtime, line: str, *, max_lines: int = 24) -> None:
        normalized = str(line or "").strip()
        if not normalized:
            return
        lines = list(getattr(runtime, "software_scan_log_lines", []) or [])
        lines.append(normalized)
        setattr(runtime, "software_scan_log_lines", lines[-max_lines:])

    def apply_progress_payload(self, runtime, payload: dict[str, Any]) -> None:
        if not isinstance(payload, dict):
            return
        stage = str(payload.get("stage", "") or "").strip()
        message = str(payload.get("message", "") or "").strip()
        stats = payload.get("stats")
        percent = payload.get("percent")
        if stage:
            runtime.software_scan_stage = stage
        if message:
            runtime.software_scan_message = message
        if isinstance(stats, dict):
            runtime.software_scan_progress_stats = dict(stats)
            profile = str(stats.get("scan_profile", "") or "").strip().lower()
            if profile in {"quick", "full"}:
                runtime.software_scan_profile = profile
        if percent is not None:
            try:
                runtime.software_scan_progress_percent = int(percent)
            except Exception:
                pass
