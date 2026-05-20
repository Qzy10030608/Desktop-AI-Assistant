from __future__ import annotations

from services.desktop.qin.heibingtai.close_models import ClosePlan, CloseTask
from services.desktop.qin.heibingtai.close_scope import (
    CLOSE_SCOPE_ALL_MATCHING_PATH,
    normalize_close_scope,
)


class FolderClosePlanner:
    def __init__(self, registered_resolver, unregistered_resolver) -> None:
        self.registered_resolver = registered_resolver
        self.unregistered_resolver = unregistered_resolver

    def plan(self, task: CloseTask) -> ClosePlan:
        scope = normalize_close_scope(task.close_scope, default=CLOSE_SCOPE_ALL_MATCHING_PATH)
        session = self.registered_resolver.find_registered_session(task)
        target_origin = "registered" if session else "unregistered"
        close_level = "registered_folder_path" if session else "unregistered_folder_path"
        target_path = str((session or {}).get("target_path", task.target_path) or task.target_path)
        target_type = str(task.target_type or (session or {}).get("target_type", "") or "directory")
        arguments = dict(task.arguments or {})
        if session:
            arguments["open_session_owned"] = True
            for key in (
                "session_id",
                "open_method",
                "process_name",
                "pid",
                "hwnd",
                "window_title",
                "close_strategy",
                "run_id",
                "run_backend",
            ):
                value = session.get(key, "")
                if value not in (None, ""):
                    arguments[key] = value
        else:
            self.unregistered_resolver.resolve_path(task)

        arguments.update({
            "target_path": target_path,
            "target_type": target_type,
            "close_scope": scope,
            "heibingtai_enabled": True,
            "target_origin": target_origin,
            "close_level": close_level,
        })
        return ClosePlan(
            action="folder.close",
            target_path=target_path,
            target_type=target_type,
            close_scope=scope,
            close_level=close_level,
            target_origin=target_origin,
            strategy="wm_close_explorer_path",
            adapter_task={
                "action": "folder.close",
                "adapter_id": "host",
                "execution_backend": "host",
                "target_path": target_path,
                "target_type": target_type,
                "target_name": task.target_name,
                "arguments": arguments,
            },
        )
