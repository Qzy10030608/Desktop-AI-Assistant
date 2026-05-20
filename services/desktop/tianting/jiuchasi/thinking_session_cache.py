from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any
from uuid import uuid4


THINKING_SESSION_SCHEMA_VERSION = "jiuchasi_thinking_session_v1"


class ThinkingSessionCache:
    """
    天庭·纠察司：当前判断会话缓存。

    作用：
    - 保存当前用户请求、初判、证据、LLM 判断、pending question。
    - 用于承接“是的 / 第一个 / 不是”等后续回答。
    - 默认短 TTL，不是长期记忆。
    """

    def __init__(
        self,
        project_root: str | Path | None = None,
        ttl_seconds: int = 120,
        material_writer: Any | None = None,
        backend: str = "host",
    ) -> None:
        self.project_root = Path(project_root or Path(__file__).resolve().parents[4]).expanduser().resolve()
        self.ttl_seconds = max(10, int(ttl_seconds or 120))
        self.material_writer = material_writer
        self.backend = str(backend or "host").strip().lower() or "host"
        self._session_paths: dict[str, Path] = {}
        self.session_dir = (
            self.project_root
            / "data"
            / "runtime"
            / "desktop"
            / "jiuchasi"
            / "thinking_sessions"
        )

    def create_session(
        self,
        *,
        user_text: str,
        route_hint: dict[str, Any] | None = None,
        understanding_packet: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        now = int(time.time())
        session_id = f"jcs_{uuid4().hex}"

        payload = {
            "schema_version": THINKING_SESSION_SCHEMA_VERSION,
            "session_id": session_id,
            "status": "active",
            "created_at_ts": now,
            "updated_at_ts": now,
            "expires_at_ts": now + self.ttl_seconds,
            "user_text": str(user_text or ""),
            "route_hint": route_hint if isinstance(route_hint, dict) else {},
            "understanding_packet": understanding_packet if isinstance(understanding_packet, dict) else {},
            "evidence": {},
            "llm_thinking": {},
            "decision": {},
            "pending_question": {},
            "steps": [],
            "metadata": metadata if isinstance(metadata, dict) else {},
        }

        self._write_session(payload)
        self._write_latest_pointer(session_id)
        return payload

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        sid = str(session_id or "").strip()
        if not sid:
            return None

        data = self._read_json(self._session_paths.get(sid, Path()))
        if not isinstance(data, dict):
            data = self._read_json(self.session_dir / f"{sid}.json")
        if not isinstance(data, dict):
            pointer = self._read_latest_pointer()
            if str(pointer.get("session_id", "") or "").strip() == sid:
                path_text = str(pointer.get("session_path", "") or "").strip()
                data = self._read_json(Path(path_text)) if path_text else None
        if not isinstance(data, dict):
            return None

        if self._is_expired(data):
            data["status"] = "expired"
            self._write_session(data)
            return None

        return data

    def get_latest_active_session(self) -> dict[str, Any] | None:
        pointer = self._read_latest_pointer()
        if not isinstance(pointer, dict):
            return None

        session_id = str(pointer.get("session_id", "") or "").strip()
        if not session_id:
            return None

        path_text = str(pointer.get("session_path", "") or "").strip()
        if path_text:
            self._session_paths[session_id] = Path(path_text)

        return self.get_session(session_id)

    def update_session(self, session_id: str, **fields: Any) -> dict[str, Any] | None:
        data = self.get_session(session_id)
        if not data:
            return None

        for key, value in fields.items():
            if key in {"schema_version", "session_id", "created_at_ts"}:
                continue
            data[key] = value

        data["updated_at_ts"] = int(time.time())
        self._write_session(data)
        return data

    def append_step(
        self,
        session_id: str,
        *,
        stage: str,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        data = self.get_session(session_id)
        if not data:
            return None

        steps = data.get("steps", [])
        if not isinstance(steps, list):
            steps = []

        steps.append(
            {
                "ts": int(time.time()),
                "stage": str(stage or ""),
                "payload": payload if isinstance(payload, dict) else {},
            }
        )

        data["steps"] = steps[-30:]
        data["updated_at_ts"] = int(time.time())
        self._write_session(data)
        return data

    def close_session(self, session_id: str, *, status: str = "closed") -> dict[str, Any] | None:
        data = self.get_session(session_id)
        if not data:
            return None

        data["status"] = str(status or "closed")
        data["updated_at_ts"] = int(time.time())
        self._write_session(data)
        return data

    def clear_expired(self) -> int:
        removed = 0
        try:
            if not self.session_dir.exists():
                return 0

            for path in self.session_dir.glob("jcs_*.json"):
                data = self._read_json(path)
                if not isinstance(data, dict):
                    continue
                if self._is_expired(data):
                    path.unlink(missing_ok=True)
                    removed += 1
        except Exception:
            return removed

        return removed

    def _is_expired(self, data: dict[str, Any]) -> bool:
        try:
            expires_at = int(data.get("expires_at_ts", 0) or 0)
            return expires_at > 0 and int(time.time()) > expires_at
        except Exception:
            return True

    def _session_path(self, session_id: str) -> Path:
        return self.session_dir / f"{session_id}.json"

    def _write_session(self, payload: dict[str, Any]) -> None:
        session_id = str(payload.get("session_id", "") or "").strip()
        if not session_id:
            return

        if self.material_writer is not None:
            try:
                path = self.material_writer.write_jiuchasi_session(
                    session_id,
                    payload,
                    backend=self.backend,
                )
                self._session_paths[session_id] = Path(path)
                return
            except Exception:
                pass

        self.session_dir.mkdir(parents=True, exist_ok=True)
        self._session_path(session_id).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _write_latest_pointer(self, session_id: str) -> None:
        if self.material_writer is not None:
            try:
                path = self._session_paths.get(session_id)
                context = (
                    self.material_writer.last_context
                    if hasattr(self.material_writer, "last_context")
                    else {}
                )
                if path is None:
                    path_text = str(context.get("session_path", "") or "").strip()
                    path = Path(path_text) if path_text else None
                if path is not None:
                    self.material_writer.write_legacy_jiuchasi_latest_pointer(
                        session_id,
                        str(context.get("backend", "") or self.backend),
                        str(context.get("run_id", "") or ""),
                        path,
                    )
                    return
            except Exception:
                pass

        self.session_dir.mkdir(parents=True, exist_ok=True)
        path = self.session_dir / "_latest.json"
        path.write_text(
            json.dumps(
                {
                    "session_id": session_id,
                    "updated_at_ts": int(time.time()),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    def session_path_for(self, session_id: str) -> str:
        sid = str(session_id or "").strip()
        if not sid:
            return ""
        path = self._session_paths.get(sid)
        if path is not None:
            return str(path)
        pointer = self._read_latest_pointer()
        if str(pointer.get("session_id", "") or "").strip() == sid:
            return str(pointer.get("session_path", "") or "")
        return ""

    def _read_latest_pointer(self) -> dict[str, Any]:
        pointer = self._read_json(self.session_dir / "_latest.json")
        if isinstance(pointer, dict):
            return pointer
        pointer = self._read_json(
            self.project_root
            / "data"
            / "runtime"
            / "desktop"
            / "jiuchasi"
            / "latest_session.json"
        )
        return pointer if isinstance(pointer, dict) else {}

    def _read_json(self, path: Path) -> dict[str, Any] | None:
        try:
            if not path.exists():
                return None
            data = json.loads(path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else None
        except Exception:
            return None
