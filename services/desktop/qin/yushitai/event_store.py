from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from services.desktop.qin.zongzheng.records.audit_event_schema import AuditEvent, make_audit_event, normalize_event
from services.desktop.qin.yushitai.report_writer import _resolve_run_backend


class YushitaiEventStore:
    """Current-run event store for Yushitai. It is not the long-term ledger."""

    def __init__(self, project_root: str | Path | None = None) -> None:
        self.project_root = Path(project_root or Path(__file__).resolve().parents[4]).expanduser().resolve()
        self.base_dir = self.project_root / "data" / "runtime" / "desktop" / "yushitai"
        self.index_path = self.base_dir / "index.json"
        self.runs_dir = self.base_dir / "runs"

    def current_run_id(self) -> str:
        from services.desktop.qin.yushitai.report_writer import ReportWriter

        writer = ReportWriter(self.project_root)
        return writer.current_session_run_id("host") or writer.current_session_run_id("vm")

    def current_run_dir(self) -> Path:
        from services.desktop.qin.yushitai.report_writer import ReportWriter

        writer = ReportWriter(self.project_root)
        run_dir = writer.current_session_run_dir("host") or writer.current_session_run_dir("vm")
        if run_dir is not None:
            return run_dir
        meta = writer.ensure_session_run(
            run_backend="host",
            desktop_mode="trusted",
            execution_backend="host",
            host_execution_enabled=True,
        )
        return self._run_dir_for(str(meta.get("run_id", "") or ""), str(meta.get("run_backend", "") or ""))

    def current_run_dir_for_backend(self, backend: str) -> Path | None:
        normalized_backend = str(backend or "").strip().lower()
        if normalized_backend not in {"host", "vm"}:
            return None
        from services.desktop.qin.yushitai.report_writer import ReportWriter

        writer = ReportWriter(self.project_root)
        run_dir = writer.current_session_run_dir(normalized_backend)
        if run_dir is not None:
            meta = writer.read_run_meta(run_dir.name, normalized_backend)
            if str(meta.get("status", "") or "").strip().lower() == "running":
                return run_dir
        running = writer.find_running_run(normalized_backend)
        if running is not None:
            return self._run_dir_for(str(running.get("run_id", "") or ""), normalized_backend)
        meta = writer.ensure_session_run(
            run_backend=normalized_backend,
            desktop_mode="trusted" if normalized_backend == "host" else "test",
            test_backend="vm" if normalized_backend == "vm" else "",
            execution_backend=normalized_backend,
            host_execution_enabled=normalized_backend == "host",
        )
        run_id = str(meta.get("run_id", "") or "").strip()
        if not run_id:
            return None
        return self._run_dir_for(run_id, str(meta.get("run_backend", normalized_backend) or normalized_backend))

    def append(self, event: AuditEvent | dict[str, Any]) -> dict[str, Any]:
        payload = normalize_event(event)
        backend = _resolve_run_backend(payload)
        if backend == "sandbox":
            payload["skipped_yushitai_run"] = True
            payload["skip_reason"] = "sandbox_result_not_recorded_in_yushitai_runs"
            return payload
        if backend not in {"host", "vm"}:
            payload["skipped_yushitai_run"] = True
            payload["skip_reason"] = "none_backend_not_recorded_in_yushitai_runs"
            return payload

        from services.desktop.qin.yushitai.report_writer import ReportWriter

        meta = ReportWriter(self.project_root).ensure_session_run(
            run_backend=backend,
            desktop_mode="trusted" if backend == "host" else "test",
            test_backend="vm" if backend == "vm" else "",
            execution_backend=backend,
            host_execution_enabled=backend == "host",
        )
        run_id = str(meta.get("run_id", "") or "").strip()
        run_dir = self._run_dir_for(run_id, str(meta.get("run_backend", backend) or backend)) if run_id else None
        if run_dir is None:
            payload["skipped_yushitai_run"] = True
            payload["skip_reason"] = str(meta.get("skip_reason", "no_yushitai_run_available") or "no_yushitai_run_available")
            return payload
        path = run_dir / "events.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")
        return payload

    def record(self, **kwargs: Any) -> dict[str, Any]:
        return self.append(make_audit_event(**kwargs))

    def read_current_events(self, limit: int = 200) -> list[dict[str, Any]]:
        from services.desktop.qin.yushitai.report_writer import ReportWriter

        writer = ReportWriter(self.project_root)
        run_dir = writer.current_session_run_dir("host") or writer.current_session_run_dir("vm")
        if run_dir is None:
            index = self._read_json(self.index_path, {"latest_run_id": "", "latest_run_backend": "", "runs": []})
            run_id = str(index.get("latest_run_id", "") or "").strip()
            run_dir = self._run_dir_for(run_id) if run_id else None
        path = run_dir / "events.jsonl" if run_dir is not None else self.base_dir / "events.jsonl"
        if not path.exists():
            return []
        lines = path.read_text(encoding="utf-8").splitlines()
        result: list[dict[str, Any]] = []
        for line in lines[-max(1, int(limit)):]:
            try:
                item = json.loads(line)
            except Exception:
                continue
            if isinstance(item, dict):
                result.append(item)
        return result

    def _read_json(self, path: Path, default: dict[str, Any]) -> dict[str, Any]:
        if not path.exists():
            return dict(default)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return dict(default)
        return data if isinstance(data, dict) else dict(default)

    def _run_dir_for(self, run_id: str, backend: str = "") -> Path:
        normalized_run_id = str(run_id or "").strip()
        normalized_backend = str(backend or "").strip().lower()
        index = self._read_json(self.index_path, {"latest_run_id": "", "runs": []})
        for item in index.get("runs", []) if isinstance(index.get("runs"), list) else []:
            if not isinstance(item, dict) or str(item.get("run_id", "") or "").strip() != normalized_run_id:
                continue
            recorded_dir = str(item.get("run_dir", "") or "").strip()
            if recorded_dir:
                return Path(recorded_dir)
            recorded_backend = str(item.get("run_backend", "") or "").strip().lower()
            if recorded_backend in {"host", "vm"}:
                return self.runs_dir / recorded_backend / normalized_run_id
        if normalized_backend in {"host", "vm"}:
            return self.runs_dir / normalized_backend / normalized_run_id
        for candidate_backend in ("host", "vm"):
            candidate = self.runs_dir / candidate_backend / normalized_run_id
            if candidate.exists():
                return candidate
        return self.runs_dir / normalized_run_id
