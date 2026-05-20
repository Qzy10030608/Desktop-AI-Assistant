from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from services.desktop.tianting.command_schema import make_context_pack


class ContextPackService:
    def __init__(self, project_root: str | Path | None = None) -> None:
        self.project_root = Path(project_root or Path(__file__).resolve().parents[3]).expanduser().resolve()

    def build_context_pack(
        self,
        *,
        conversation_recent_summary: dict[str, Any] | None = None,
        observed_runtime_summary: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return make_context_pack(
            conversation_recent_summary=conversation_recent_summary or {},
            desktop_recent_summary=self._desktop_recent_summary(),
            pending_task_summary=self._pending_task_summary(),
            shaofu_material_summary=self._shaofu_material_summary(),
            yushitai_event_summary=self._yushitai_event_summary(),
            observed_runtime_summary=observed_runtime_summary or {},
        )

    def _pending_task_summary(self) -> dict[str, Any]:
        pending_dir = self.project_root / "data" / "runtime" / "desktop" / "pending_tasks"
        try:
            if not pending_dir.exists():
                return {"has_pending_task": False, "pending_count": 0, "items": []}
            items: list[dict[str, Any]] = []
            for path in sorted(pending_dir.glob("*.json"))[:5]:
                data = self._read_json(path)
                items.append({
                    "pending_task_id": str(data.get("pending_task_id", data.get("task_id", path.stem)) or path.stem),
                    "status": str(data.get("status", "") or ""),
                    "action": str(data.get("action", "") or ""),
                    "safe_label": str(data.get("safe_label", data.get("target_name", "")) or ""),
                })
            return {
                "has_pending_task": bool(items),
                "pending_count": len(list(pending_dir.glob("*.json"))),
                "items": items,
            }
        except Exception:
            return {"has_pending_task": False, "pending_count": 0, "items": []}

    def _desktop_recent_summary(self) -> dict[str, Any]:
        try:
            from services.desktop.qin.yushitai.report_writer import ReportWriter

            writer = ReportWriter(self.project_root)
            run_id = writer.current_session_run_id("host") or writer.current_session_run_id("vm")
            return {"latest_run_id": run_id, "summary_available": bool(run_id)}
        except Exception:
            return {"summary_available": False}

    def _yushitai_event_summary(self) -> dict[str, Any]:
        try:
            from services.desktop.qin.yushitai.event_store import YushitaiEventStore

            events = YushitaiEventStore(self.project_root).read_current_events(limit=5)
            safe_events = []
            for item in events[-5:]:
                safe_events.append({
                    "event_type": str(item.get("event_type", "") or ""),
                    "action": str(item.get("action", "") or ""),
                    "backend": str(item.get("backend", "") or ""),
                    "decision": str(item.get("decision", "") or ""),
                    "ok": bool(item.get("ok", False)),
                })
            return {"event_count": len(safe_events), "recent_events": safe_events}
        except Exception:
            return {"event_count": 0, "recent_events": []}

    def _shaofu_material_summary(self) -> dict[str, Any]:
        try:
            from services.desktop.qin.shaofu.storage_index import StorageIndex

            index = StorageIndex(self.project_root)
            summarize = getattr(index, "summarize", None)
            if callable(summarize):
                data = summarize()
                return data if isinstance(data, dict) else {"summary_available": False}
            return {"summary_available": False}
        except Exception:
            return {"summary_available": False}

    def _read_json(self, path: Path) -> dict[str, Any]:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}


def build_context_pack(
    *,
    project_root: str | Path | None = None,
    conversation_recent_summary: dict[str, Any] | None = None,
    observed_runtime_summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return ContextPackService(project_root).build_context_pack(
        conversation_recent_summary=conversation_recent_summary,
        observed_runtime_summary=observed_runtime_summary,
    )
