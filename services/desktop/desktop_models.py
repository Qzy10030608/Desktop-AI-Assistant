from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional


DesktopMode = Literal["disabled", "restricted", "trusted", "test"]
TaskType = Literal[
    "system_info",
    "file_search",
    "open_file",
    "open_folder",
    "launch_app",
    "attach_app",
    "screenshot",
    "unknown",
]


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


@dataclass
class ModeState:
    current_mode: DesktopMode = "disabled"
    updated_at: str = field(default_factory=now_iso)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RootEntry:
    root_id: str
    title: str
    path: str
    enabled: bool = True
    index_enabled: bool = True
    allow_search: bool = True
    allow_open_file: bool = True
    allow_open_folder: bool = True
    allow_read_meta: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class AppEntry:
    app_id: str
    title: str
    target_path: str
    launch_args: List[str] = field(default_factory=list)
    enabled: bool = True
    allow_launch: bool = True
    allow_attach: bool = False
    allow_close: bool = False
    connector_id: str = "windows_shell"
    permission_state: str = "unset"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class IntentTask:
    raw_text: str
    task_type: TaskType = "unknown"
    target_name: str = ""
    target_path: str = ""
    arguments: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ReviewDecision:
    allowed: bool
    reason: str
    requires_confirm: bool = False
    matched_root_id: Optional[str] = None
    matched_app_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ConnectorTestResult:
    connector_id: str
    ok: bool
    stage: str
    message: str
    capabilities: List[str] = field(default_factory=list)
    detail: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RouteResult:
    ok: bool
    action: str
    message: str
    payload: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
