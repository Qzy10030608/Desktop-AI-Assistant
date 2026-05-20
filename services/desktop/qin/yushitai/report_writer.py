from __future__ import annotations

import json
import socket
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from services.desktop.qin.yushitai.report_analyzer import ReportAnalyzer
from services.desktop.qin.yushitai.report_collector import ReportCollector
from services.desktop.qin.yushitai.report_presenter import ReportPresenter

_SESSION_RUNS: dict[str, dict[str, str]] = {}
_SESSION_CONTEXTS: dict[str, dict[str, str]] = {}

RUN_MATERIAL_DIRS = (
    "reports",
    "jiuchasi",
    "jiuchasi/sessions",
    "pending_tasks",
    "pending_tasks/items",
)

RUN_MATERIAL_FILES = (
    "ai_commands.jsonl",
)


def _lookup_backend_value(payload: dict[str, Any], key: str) -> Any:
    if not isinstance(payload, dict):
        return ""
    if key in payload:
        return payload.get(key)
    for nested_key in ("arguments", "result", "data", "raw", "review"):
        nested = payload.get(nested_key)
        if isinstance(nested, dict) and key in nested:
            return nested.get(key)
    return ""


def _resolve_run_backend(
    payload: dict[str, Any] | None = None,
    *,
    execution_backend: str = "",
    test_backend: str = "",
    desktop_mode: str = "",
    adapter_id: str = "",
) -> str:
    source = payload if isinstance(payload, dict) else {}

    execution = str(execution_backend or _lookup_backend_value(source, "execution_backend") or "").strip().lower()
    backend = str(_lookup_backend_value(source, "backend") or "").strip().lower()
    test = str(test_backend or _lookup_backend_value(source, "test_backend") or "").strip().lower()
    mode = str(desktop_mode or _lookup_backend_value(source, "desktop_mode") or _lookup_backend_value(source, "current_mode") or "").strip().lower()
    adapter = str(adapter_id or _lookup_backend_value(source, "adapter_id") or "").strip().lower()
    adapter_stage = str(_lookup_backend_value(source, "adapter_stage") or "").strip().lower()
    executed_in = str(_lookup_backend_value(source, "executed_in") or "").strip().lower()
    target_environment = str(_lookup_backend_value(source, "target_environment") or "").strip().lower()
    path_namespace = str(_lookup_backend_value(source, "path_namespace") or "").strip().lower()
    host_enabled = bool(_lookup_backend_value(source, "host_execution_enabled"))

    if (
        execution == "host"
        or backend == "host"
        or adapter in {"host", "host_windows"}
        or adapter_stage == "host_windows"
        or executed_in == "host"
        or target_environment in {"local_host", "host_machine"}
        or path_namespace == "host_windows"
        or (host_enabled and mode == "trusted")
    ):
        return "host"

    if (
        execution == "vm"
        or backend == "vm"
        or test == "vm"
        or adapter == "vm"
        or adapter_stage == "vm"
        or executed_in == "vm"
        or target_environment in {"virtual_machine", "vm"}
        or path_namespace == "vm_windows"
        or (mode == "test" and test == "vm")
    ):
        return "vm"

    if (
        execution == "sandbox"
        or backend == "sandbox"
        or test == "sandbox"
        or adapter == "sandbox"
        or adapter_stage == "sandbox"
        or executed_in == "sandbox"
        or target_environment == "sandbox_simulation"
        or path_namespace == "sandbox"
        or (mode == "test" and test == "sandbox")
    ):
        return "sandbox"

    return "none"


class ReportWriter:
    def __init__(self, project_root: str | Path | None = None) -> None:
        self.project_root = Path(project_root or Path(__file__).resolve().parents[4]).expanduser().resolve()
        self.base_dir = self.project_root / "data" / "runtime" / "desktop" / "yushitai"
        self.index_path = self.base_dir / "index.json"
        self.runs_dir = self.base_dir / "runs"
        self.collector = ReportCollector(self.project_root)
        self.analyzer = ReportAnalyzer()
        self.presenter = ReportPresenter()
        self._session_key = str(self.project_root)

    def configure_session(self, *, run_scope: str = "app_session", started_by: str = "app_startup") -> None:
        _SESSION_CONTEXTS[self._session_key] = {
            "run_scope": str(run_scope or "app_session"),
            "started_by": str(started_by or "app_startup"),
        }

    def current_session_run_id(self, backend: str) -> str:
        normalized_backend = str(backend or "").strip().lower()
        if normalized_backend not in {"host", "vm"}:
            return ""
        return str(_SESSION_RUNS.get(self._session_key, {}).get(normalized_backend, "") or "").strip()

    def current_session_run_dir(self, backend: str) -> Path | None:
        run_id = self.current_session_run_id(backend)
        if not run_id:
            return None
        run_dir = self._run_dir_for(run_id, backend)
        if run_dir.exists():
            self.ensure_run_material_dirs(run_id, backend)
        return run_dir if run_dir.exists() else None

    def ensure_session_run(
        self,
        run_backend: str = "host",
        *,
        desktop_mode: str = "",
        test_backend: str = "",
        execution_backend: str = "",
        host_execution_enabled: bool = False,
        run_scope: str = "",
        started_by: str = "",
    ) -> dict[str, Any]:
        normalized_backend = str(run_backend or "").strip().lower()
        if normalized_backend not in {"host", "vm"}:
            normalized_backend = _resolve_run_backend(
                execution_backend=execution_backend,
                test_backend=test_backend,
                desktop_mode=desktop_mode,
                payload={"host_execution_enabled": bool(host_execution_enabled)},
            )
        if normalized_backend not in {"host", "vm"}:
            return {
                "ok": False,
                "run_id": "",
                "run_backend": normalized_backend,
                "skipped_yushitai_run": True,
                "skip_reason": f"{normalized_backend}_result_not_recorded_in_yushitai_runs"
                if normalized_backend == "sandbox"
                else "none_backend_not_recorded_in_yushitai_runs",
            }

        memory_run_id = self.current_session_run_id(normalized_backend)
        if memory_run_id:
            meta = self.read_run_meta(memory_run_id, normalized_backend)
            if str(meta.get("status", "") or "").strip().lower() == "running":
                run_dir = self._run_dir_for(memory_run_id, normalized_backend)
                if run_dir.exists():
                    self.ensure_run_material_dirs(memory_run_id, normalized_backend)
                    return meta

        running = self.find_running_run(normalized_backend)
        if running is not None:
            self._remember_session_run(normalized_backend, str(running.get("run_id", "") or ""))
            self.ensure_run_material_dirs(str(running.get("run_id", "") or ""), normalized_backend)
            return running

        return self.start_run(
            run_backend=normalized_backend,
            desktop_mode=desktop_mode or ("trusted" if normalized_backend == "host" else "test"),
            test_backend=test_backend or ("vm" if normalized_backend == "vm" else ""),
            execution_backend=execution_backend or normalized_backend,
            host_execution_enabled=bool(host_execution_enabled or normalized_backend == "host"),
            run_scope=run_scope,
            started_by=started_by,
        )

    def find_running_run(self, run_backend: str) -> dict[str, Any] | None:
        normalized_backend = str(run_backend or "").strip().lower()
        if normalized_backend not in {"host", "vm"}:
            return None
        index = self._read_index()
        candidates: list[str] = []
        for key in (
            f"active_{normalized_backend}_run_id",
            f"{normalized_backend}_active_run_id",
            "active_run_id",
        ):
            value = str(index.get(key, "") or "").strip()
            if value:
                candidates.append(value)
        if str(index.get("latest_run_backend", "") or "").strip().lower() == normalized_backend:
            value = str(index.get("latest_run_id", "") or "").strip()
            if value:
                candidates.append(value)
        runs = index.get("runs", []) if isinstance(index.get("runs"), list) else []
        for item in reversed(runs):
            if not isinstance(item, dict):
                continue
            if str(item.get("run_backend", "") or "").strip().lower() != normalized_backend:
                continue
            run_id = str(item.get("run_id", "") or "").strip()
            if run_id:
                candidates.append(run_id)

        seen: set[str] = set()
        for run_id in candidates:
            if run_id in seen:
                continue
            seen.add(run_id)
            meta = self.read_run_meta(run_id, normalized_backend)
            if str(meta.get("status", "") or "").strip().lower() != "running":
                continue
            run_dir = self._run_dir_for(run_id, normalized_backend)
            if run_dir.exists():
                return meta
        return None

    def read_run_meta(self, run_id: str, run_backend: str) -> dict[str, Any]:
        normalized_run_id = str(run_id or "").strip()
        normalized_backend = str(run_backend or "").strip().lower()
        if not normalized_run_id:
            return {}
        return self._read_json(self._run_dir_for(normalized_run_id, normalized_backend) / "run_meta.json", {})

    def _remember_session_run(self, run_backend: str, run_id: str) -> None:
        normalized_backend = str(run_backend or "").strip().lower()
        normalized_run_id = str(run_id or "").strip()
        if normalized_backend in {"host", "vm"} and normalized_run_id:
            _SESSION_RUNS.setdefault(self._session_key, {})[normalized_backend] = normalized_run_id

    def close_session_runs(
        self,
        *,
        current_mode: str = "",
        desktop_mode: str = "",
        test_backend: str = "",
    ) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        session_runs = dict(_SESSION_RUNS.get(self._session_key, {}))
        for backend in ("host", "vm"):
            run_id = str(session_runs.get(backend, "") or "").strip()
            if not run_id:
                running = self.find_running_run(backend)
                run_id = str((running or {}).get("run_id", "") or "").strip()
            if not run_id:
                continue
            results.append(
                self.close_run(
                    run_id=run_id,
                    run_backend=backend,
                    current_mode=current_mode,
                    desktop_mode=("trusted" if backend == "host" else "test") if not desktop_mode else desktop_mode,
                    test_backend="vm" if backend == "vm" else test_backend,
                    execution_backend=backend,
                    host_execution_enabled=backend == "host",
                    generate_report=True,
                )
            )
        _SESSION_RUNS.pop(self._session_key, None)
        return results

    def start_run(
        self,
        *,
        run_backend: str = "",
        current_mode: str = "",
        desktop_mode: str = "",
        test_backend: str = "",
        execution_backend: str = "",
        host_execution_enabled: bool = False,
        project_version: str = "",
        run_scope: str = "",
        started_by: str = "",
    ) -> dict[str, Any]:
        resolved_mode = str(desktop_mode or current_mode or "").strip().lower()
        resolved_execution_backend = str(execution_backend or "").strip().lower()
        resolved_test_backend = str(test_backend or "").strip().lower()
        requested_run_backend = str(run_backend or "").strip().lower()
        if not resolved_execution_backend:
            if requested_run_backend in {"host", "vm"}:
                resolved_execution_backend = requested_run_backend
            elif resolved_mode == "trusted":
                resolved_execution_backend = "host"
            elif resolved_mode == "test":
                resolved_execution_backend = resolved_test_backend or "sandbox"
        resolved_run_backend = (
            requested_run_backend
            if requested_run_backend in {"host", "vm", "sandbox"}
            else _resolve_run_backend(
                execution_backend=resolved_execution_backend,
                test_backend=resolved_test_backend,
                desktop_mode=resolved_mode,
                payload={"host_execution_enabled": bool(host_execution_enabled or resolved_mode == "trusted")},
            )
        )
        if resolved_run_backend not in {"host", "vm"}:
            return {
                "ok": False,
                "run_id": "",
                "run_backend": resolved_run_backend,
                "skipped_yushitai_run": True,
                "skip_reason": f"{resolved_run_backend}_result_not_recorded_in_yushitai_runs"
                if resolved_run_backend == "sandbox"
                else "none_backend_not_recorded_in_yushitai_runs",
            }

        self.runs_dir.mkdir(parents=True, exist_ok=True)
        (self.runs_dir / resolved_run_backend).mkdir(parents=True, exist_ok=True)
        index = self._read_index()
        self._mark_latest_running_interrupted(index, resolved_run_backend)

        run_id = self._new_run_id()
        run_dir = self._run_dir_for(run_id, resolved_run_backend)
        self.ensure_run_material_dirs(run_id, resolved_run_backend)
        context = _SESSION_CONTEXTS.get(self._session_key, {})
        resolved_run_scope = str(run_scope or context.get("run_scope", "") or "direct_session")
        resolved_started_by = str(started_by or context.get("started_by", "") or "direct_execute_desktop_task")

        meta = {
            "run_id": run_id,
            "run_backend": resolved_run_backend,
            "run_scope": resolved_run_scope,
            "started_by": resolved_started_by,
            "run_dir": str(run_dir),
            "started_at": self._now_iso(),
            "closed_at": "",
            "ended_at": "",
            "status": "running",
            "project_version": str(project_version or "local"),
            "hostname": socket.gethostname(),
            "current_mode": str(current_mode or desktop_mode or ""),
            "desktop_mode": str(desktop_mode or current_mode or ""),
            "test_backend": str(resolved_test_backend or ""),
            "execution_backend": str(resolved_execution_backend or resolved_run_backend),
            "host_execution_enabled": bool(host_execution_enabled or resolved_run_backend == "host"),
        }
        self._write_json(run_dir / "run_meta.json", meta)

        runs = index.get("runs", []) if isinstance(index.get("runs"), list) else []
        runs.append(dict(meta))
        index["latest_run_id"] = run_id
        index["latest_run_backend"] = resolved_run_backend
        index["runs"] = runs[-200:]
        self._write_json(self.index_path, index)
        _SESSION_RUNS.setdefault(self._session_key, {})[resolved_run_backend] = run_id
        return meta

    def close_run(
        self,
        *,
        run_id: str = "",
        run_backend: str = "",
        current_mode: str = "",
        desktop_mode: str = "",
        test_backend: str = "",
        execution_backend: str = "",
        host_execution_enabled: bool | None = None,
        generate_report: bool = True,
    ) -> dict[str, Any]:
        index = self._read_index()
        normalized_backend = str(run_backend or "").strip().lower()
        target_run_id = str(run_id or (self.current_session_run_id(normalized_backend) if normalized_backend else "")).strip()
        if not target_run_id:
            return {}
        run_dir = self._run_dir_for(target_run_id, normalized_backend or str(index.get("latest_run_backend", "") or ""))
        meta_path = run_dir / "run_meta.json"
        meta = self._read_json(meta_path, {})
        if not meta:
            return {}
        normalized_backend = str(normalized_backend or meta.get("run_backend", "") or "").strip().lower()
        if str(meta.get("status", "")).strip().lower() == "running":
            meta["status"] = "closed"
            closed_at = self._now_iso()
            meta["closed_at"] = closed_at
            meta["ended_at"] = closed_at
        resolved_current_mode = str(current_mode or "").strip()
        resolved_desktop_mode = str(desktop_mode or "").strip()
        if resolved_current_mode:
            meta["current_mode"] = resolved_current_mode
        if resolved_desktop_mode:
            meta["desktop_mode"] = resolved_desktop_mode
        if test_backend:
            meta["test_backend"] = str(test_backend)
        if execution_backend:
            meta["execution_backend"] = str(execution_backend)
        if host_execution_enabled is not None:
            meta["host_execution_enabled"] = bool(host_execution_enabled)
        resolved_backend = _resolve_run_backend(meta)
        if resolved_backend in {"host", "vm"}:
            meta["run_backend"] = resolved_backend
            meta["run_dir"] = str(self._run_dir_for(target_run_id, resolved_backend))
            self.ensure_run_material_dirs(target_run_id, resolved_backend)
        self._write_json(meta_path, meta)
        self._replace_run_in_index(index, meta)
        if generate_report and resolved_backend in {"host", "vm"}:
            self.generate_report(
                stage="v3_v4_desktop_test",
                runtime_state={
                    "desktop_mode": str(meta.get("desktop_mode", "") or ""),
                    "current_mode": str(meta.get("current_mode", "") or ""),
                    "test_backend": str(meta.get("test_backend", "") or ""),
                    "execution_backend": resolved_backend,
                    "host_execution_enabled": bool(meta.get("host_execution_enabled", False)),
                },
            )
        return meta

    def update_run_meta(self, **patch: Any) -> dict[str, Any]:
        index = self._read_index()
        resolved_patch_backend = _resolve_run_backend(patch)
        target_run_id = self.current_session_run_id(resolved_patch_backend)
        if not target_run_id:
            return {}
        run_dir = self._run_dir_for(target_run_id, resolved_patch_backend)
        meta_path = run_dir / "run_meta.json"
        meta = self._read_json(meta_path, {})
        if not meta:
            return {}
        meta.update({key: value for key, value in patch.items() if key != "run_id"})
        meta["run_id"] = target_run_id
        resolved_backend = _resolve_run_backend(meta)
        if resolved_backend in {"host", "vm"}:
            meta["run_backend"] = resolved_backend
            meta["run_dir"] = str(self._run_dir_for(target_run_id, resolved_backend))
            self.ensure_run_material_dirs(target_run_id, resolved_backend)
        self._write_json(meta_path, meta)
        self._replace_run_in_index(index, meta)
        return meta

    def write_snapshot(self, state: dict[str, Any]) -> Path:
        return self.write_named_snapshot("latest_state.json", state)

    def write_named_snapshot(self, name: str, state: dict[str, Any]) -> Path:
        run_backend = _resolve_run_backend(state if isinstance(state, dict) else {})
        if run_backend not in {"host", "vm"}:
            raise ValueError(f"{run_backend}_result_not_recorded_in_yushitai_runs")
        run_dir = self._current_run_dir(backend=run_backend)
        snapshots_dir = run_dir / "snapshots"
        snapshots_dir.mkdir(parents=True, exist_ok=True)
        safe_name = str(name or "latest_state.json").strip() or "latest_state.json"
        path = snapshots_dir / safe_name
        path.write_text(json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
        return path

    def append_event(self, event: dict[str, Any]) -> Path:
        backend = _resolve_run_backend(event)
        if backend == "sandbox":
            raise ValueError("sandbox_result_not_recorded_in_yushitai_runs")
        if backend not in {"host", "vm"}:
            raise ValueError("none_backend_not_recorded_in_yushitai_runs")
        run_dir = self._current_run_dir(backend=backend)
        path = run_dir / "events.jsonl"
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")
        return path

    def generate_report(self, *, stage: str = "v3_03_preflight", runtime_state: dict[str, Any] | None = None) -> dict[str, Any]:
        run_backend = _resolve_run_backend(runtime_state if isinstance(runtime_state, dict) else {})
        if run_backend == "sandbox":
            return {
                "ok": True,
                "skipped_yushitai_report": True,
                "skip_reason": "sandbox_result_not_recorded_in_yushitai_runs",
                "run_backend": "sandbox",
            }
        if run_backend not in {"host", "vm"}:
            return {
                "ok": True,
                "skipped_yushitai_report": True,
                "skip_reason": "none_backend_not_recorded_in_yushitai_runs",
                "run_backend": run_backend,
            }

        collected = self.collector.collect(runtime_state=runtime_state)
        report = self.analyzer.analyze(collected, stage=stage)
        run_dir = self._current_run_dir(backend=run_backend)
        reports_dir = run_dir / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)

        json_path = reports_dir / "yushitai_report_latest.json"
        md_path = reports_dir / "yushitai_report_latest.md"
        json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
        md_path.write_text(self.presenter.to_markdown(report), encoding="utf-8")
        self._update_index(report, json_path=json_path, md_path=md_path, run_backend=run_backend)
        return {
            "ok": True,
            "report": report,
            "json_path": str(json_path),
            "markdown_path": str(md_path),
        }

    def _update_index(self, report: dict[str, Any], *, json_path: Path, md_path: Path, run_backend: str = "") -> None:
        index = self._read_index()
        run_dir = json_path.parent.parent
        run_id = str(run_dir.name or index.get("latest_run_id", "") or "")
        metadata = report.get("metadata", {}) if isinstance(report.get("metadata"), dict) else {}
        patch = {
            "run_id": run_id,
            "report_id": metadata.get("report_id", ""),
            "latest_report_created_at": metadata.get("created_at", ""),
            "latest_report_json_path": str(json_path),
            "latest_report_markdown_path": str(md_path),
        }
        normalized_backend = str(run_backend or "").strip().lower()
        if normalized_backend in {"host", "vm"}:
            patch["run_backend"] = normalized_backend
            patch["run_dir"] = str(run_dir)
        self._replace_run_in_index(index, patch)

    def _current_run_dir(self, *, backend: str = "") -> Path:
        normalized_backend = str(backend or "").strip().lower()
        if normalized_backend in {"host", "vm"}:
            run_id = self.current_session_run_id(normalized_backend)
            run_dir = self._run_dir_for(run_id, normalized_backend) if run_id else None
            if run_dir is not None and run_dir.exists():
                return run_dir
        meta = self.ensure_session_run(
            run_backend=normalized_backend,
            desktop_mode="trusted" if normalized_backend == "host" else ("test" if normalized_backend == "vm" else ""),
            test_backend="vm" if normalized_backend == "vm" else "",
            execution_backend=normalized_backend,
            host_execution_enabled=normalized_backend == "host",
        )
        run_id = str(meta.get("run_id", "") or "").strip()
        if not run_id:
            raise RuntimeError(str(meta.get("skip_reason", "no_yushitai_run_available")))
        return self._run_dir_for(run_id, str(meta.get("run_backend", normalized_backend) or normalized_backend))

    def ensure_run_material_dirs(self, run_id: str, backend: str = "") -> dict[str, Any]:
        normalized_run_id = str(run_id or "").strip()
        normalized_backend = str(backend or "").strip().lower()
        if not normalized_run_id or normalized_backend not in {"host", "vm"}:
            return {
                "ok": False,
                "run_id": normalized_run_id,
                "run_backend": normalized_backend,
                "paths": [],
                "error": "missing_run_id_or_backend",
            }
        run_dir = self._run_dir_for(normalized_run_id, normalized_backend)
        run_dir.mkdir(parents=True, exist_ok=True)
        paths: list[str] = []
        for relative in RUN_MATERIAL_DIRS:
            path = run_dir / relative
            path.mkdir(parents=True, exist_ok=True)
            paths.append(str(path))
        files: list[str] = []
        for relative in RUN_MATERIAL_FILES:
            path = run_dir / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            if not path.exists():
                path.write_text("", encoding="utf-8")
            files.append(str(path))
        return {
            "ok": True,
            "run_id": normalized_run_id,
            "run_backend": normalized_backend,
            "run_dir": str(run_dir),
            "paths": paths,
            "files": files,
        }

    def _run_dir_for(self, run_id: str, backend: str = "") -> Path:
        normalized_run_id = str(run_id or "").strip()
        normalized_backend = str(backend or "").strip().lower()
        index = self._read_index()
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

    def _new_run_id(self) -> str:
        base = datetime.now().strftime("%Y%m%d_%H%M%S")
        candidate = base
        counter = 1
        while (
            (self.runs_dir / "host" / candidate).exists()
            or (self.runs_dir / "vm" / candidate).exists()
            or (self.runs_dir / candidate).exists()
        ):
            candidate = f"{base}_{counter:02d}"
            counter += 1
        return candidate

    def _mark_latest_running_interrupted(self, index: dict[str, Any], backend: str = "") -> None:
        normalized_backend = str(backend or "").strip().lower()
        latest_run_id = ""
        if normalized_backend in {"host", "vm"}:
            runs = index.get("runs", []) if isinstance(index.get("runs"), list) else []
            for item in reversed(runs):
                if not isinstance(item, dict):
                    continue
                if str(item.get("run_backend", "") or "").strip().lower() == normalized_backend:
                    latest_run_id = str(item.get("run_id", "") or "").strip()
                    break
        else:
            latest_run_id = str(index.get("latest_run_id", "") or "").strip()
        if not latest_run_id:
            return
        meta_path = self._run_dir_for(latest_run_id, str(index.get("latest_run_backend", "") or "")) / "run_meta.json"
        meta = self._read_json(meta_path, {})
        if str(meta.get("status", "")).strip().lower() != "running":
            return
        meta["status"] = "interrupted"
        closed_at = self._now_iso()
        meta["closed_at"] = closed_at
        meta["ended_at"] = closed_at
        self._write_json(meta_path, meta)
        self._replace_run_in_index(index, meta, write=False)

    def _replace_run_in_index(self, index: dict[str, Any], patch: dict[str, Any], *, write: bool = True) -> None:
        run_id = str(patch.get("run_id", "") or "").strip()
        if not run_id:
            return
        runs = index.get("runs", []) if isinstance(index.get("runs"), list) else []
        replaced = False
        next_runs = []
        for item in runs:
            if isinstance(item, dict) and str(item.get("run_id", "") or "") == run_id:
                merged = dict(item)
                merged.update(patch)
                next_runs.append(merged)
                replaced = True
            else:
                next_runs.append(item)
        if not replaced:
            next_runs.append(dict(patch))
        index["runs"] = next_runs[-200:]
        run_backend = str(patch.get("run_backend", "") or "").strip().lower()
        if run_backend in {"host", "vm"}:
            index["latest_run_id"] = run_id
            index["latest_run_backend"] = run_backend
        if write:
            self._write_json(self.index_path, index)

    def _read_index(self) -> dict[str, Any]:
        return self._read_json(self.index_path, {"latest_run_id": "", "runs": []})

    def _read_json(self, path: Path, default: dict[str, Any]) -> dict[str, Any]:
        if not path.exists():
            return dict(default)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return dict(default)
        return data if isinstance(data, dict) else dict(default)

    def _write_json(self, path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")

    def _now_iso(self) -> str:
        return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
