from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from services.desktop.qin.yushitai.report_writer import ReportWriter


class RuntimeMaterialWriter:
    """Write runtime materials into the current Yushitai run."""

    def __init__(self, report_writer: ReportWriter) -> None:
        self.report_writer = report_writer
        self.project_root = report_writer.project_root
        self._last_context: dict[str, Any] = {}

    def write_jiuchasi_session(
        self,
        session_id: str,
        payload: dict[str, Any],
        backend: str = "host",
    ) -> Path:
        context = self._ensure_run_context(backend)
        run_dir = context["run_dir"]
        path = run_dir / "jiuchasi" / "sessions" / f"{session_id}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(payload if isinstance(payload, dict) else {}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        self._last_context = {
            **context,
            "session_path": str(path),
        }
        return path

    def append_jiuchasi_decision(
        self,
        summary: dict[str, Any],
        backend: str = "host",
    ) -> Path:
        context = self._ensure_run_context(backend)
        run_dir = context["run_dir"]
        path = run_dir / "jiuchasi" / "decisions.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)

        item = summary.copy() if isinstance(summary, dict) else {}
        item.setdefault("created_at", self._now_iso())
        item["backend"] = context["backend"]
        item["run_id"] = context["run_id"]

        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(item, ensure_ascii=False, separators=(",", ":")) + "\n")
        self._last_context = {
            **context,
            "decision_path": str(path),
        }
        return path

    def append_ai_command(
        self,
        record: dict[str, Any],
        backend: str = "host",
    ) -> Path:
        context = self._ensure_run_context(backend)
        run_dir = context["run_dir"]
        path = run_dir / "ai_commands.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)

        item = record.copy() if isinstance(record, dict) else {}
        item.setdefault("schema_version", "ai_command_record_v1")
        item.setdefault("created_at", self._now_iso())
        item["backend"] = context["backend"]
        item["run_id"] = context["run_id"]

        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(item, ensure_ascii=False, separators=(",", ":")) + "\n")
        self._last_context = {
            **context,
            "ai_commands_path": str(path),
        }
        return path

    def write_legacy_jiuchasi_latest_pointer(
        self,
        session_id: str,
        backend: str,
        run_id: str,
        new_path: str | Path,
    ) -> None:
        legacy_dir = self.project_root / "data" / "runtime" / "desktop" / "jiuchasi"
        thinking_dir = legacy_dir / "thinking_sessions"
        legacy_dir.mkdir(parents=True, exist_ok=True)
        thinking_dir.mkdir(parents=True, exist_ok=True)

        pointer = {
            "schema_version": "jiuchasi_latest_session_pointer_v1",
            "session_id": str(session_id or ""),
            "backend": str(backend or "host"),
            "run_id": str(run_id or ""),
            "session_path": str(new_path or ""),
            "updated_at": self._now_iso(),
        }
        text = json.dumps(pointer, ensure_ascii=False, indent=2)
        (legacy_dir / "latest_session.json").write_text(text, encoding="utf-8")
        (thinking_dir / "_latest.json").write_text(text, encoding="utf-8")

    def jiuchasi_session_path(self, session_id: str, backend: str = "host") -> Path:
        context = self._ensure_run_context(backend)
        return context["run_dir"] / "jiuchasi" / "sessions" / f"{session_id}.json"

    @property
    def last_context(self) -> dict[str, Any]:
        return self._last_context.copy()

    def _ensure_run_context(self, backend: str) -> dict[str, Any]:
        normalized_backend = str(backend or "host").strip().lower()
        if normalized_backend not in {"host", "vm"}:
            normalized_backend = "host"

        meta = self.report_writer.ensure_session_run(
            run_backend=normalized_backend,
            desktop_mode="trusted" if normalized_backend == "host" else "test",
            test_backend="vm" if normalized_backend == "vm" else "",
            execution_backend=normalized_backend,
            host_execution_enabled=normalized_backend == "host",
        )
        run_id = str(meta.get("run_id", "") or "").strip()
        if not run_id:
            raise RuntimeError("Yushitai run_id is not available for runtime material writing.")

        self.report_writer.ensure_run_material_dirs(run_id, normalized_backend)
        run_dir = self.report_writer.current_session_run_dir(normalized_backend)
        if run_dir is None:
            run_dir = self.report_writer.runs_dir / normalized_backend / run_id
            run_dir.mkdir(parents=True, exist_ok=True)
            self.report_writer.ensure_run_material_dirs(run_id, normalized_backend)

        return {
            "backend": normalized_backend,
            "run_id": run_id,
            "run_dir": run_dir,
        }

    def _now_iso(self) -> str:
        return datetime.now(timezone.utc).isoformat()
