from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any
from uuid import uuid4

from services.desktop.desktop_models import now_iso


@dataclass
class VmConnectionMemory:
    action: str
    ok: bool
    base_url: str = ""
    hostname: str = ""
    protocol_version: str = ""
    agent_version: str = ""
    duration_ms: float = 0.0
    apps_count: int = 0
    files_count: int = 0
    review_stage: str = ""
    route_result: str = ""
    error: str = ""
    memory_id: str = field(default_factory=lambda: f"vm_memory_{uuid4().hex}")
    created_at: str = field(default_factory=now_iso)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class VmConnectionMemoryStore:
    def __init__(self, project_root: str | Path | None = None) -> None:
        self.project_root = Path(project_root or Path(__file__).resolve().parents[4]).expanduser().resolve()
        self.path = self.project_root / "data" / "runtime" / "desktop" / "vm_connection_memory.json"

    def record_memory(self, **kwargs: Any) -> dict[str, Any]:
        memory = VmConnectionMemory(
            action=str(kwargs.get("action", "vm.connect") or "vm.connect"),
            ok=bool(kwargs.get("ok", False)),
            base_url=str(kwargs.get("base_url", "") or ""),
            hostname=str(kwargs.get("hostname", "") or ""),
            protocol_version=str(kwargs.get("protocol_version", "") or ""),
            agent_version=str(kwargs.get("agent_version", "") or ""),
            duration_ms=float(kwargs.get("duration_ms", 0) or 0),
            apps_count=int(kwargs.get("apps_count", 0) or 0),
            files_count=int(kwargs.get("files_count", 0) or 0),
            review_stage=str(kwargs.get("review_stage", "") or ""),
            route_result=str(kwargs.get("route_result", "") or ""),
            error=str(kwargs.get("error", "") or ""),
        )
        data = self._read()
        memories = data.get("memories", []) if isinstance(data.get("memories"), list) else []
        memories.append(memory.to_dict())
        data["memories"] = memories
        self._write(data)
        self.keep_latest(3)
        return memory.to_dict()

    def list_recent(self, limit: int = 3) -> list[dict[str, Any]]:
        memories = self._read().get("memories", [])
        if not isinstance(memories, list):
            return []
        return [item for item in memories if isinstance(item, dict)][-max(1, int(limit)):]

    def keep_latest(self, count: int = 3) -> None:
        self.clear_old_keep_latest(count)

    def clear_old_keep_latest(self, count: int = 3) -> None:
        data = self._read()
        memories = data.get("memories", []) if isinstance(data.get("memories"), list) else []
        data["memories"] = [item for item in memories if isinstance(item, dict)][-max(1, int(count)):]
        self._write(data)

    def _read(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"memories": []}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return {"memories": []}
        return data if isinstance(data, dict) else {"memories": []}

    def _write(self, data: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
