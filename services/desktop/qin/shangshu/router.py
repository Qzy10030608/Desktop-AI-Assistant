from __future__ import annotations

from services.desktop.qin.zongzheng.action_catalog import is_supported_action


class DesktopRouter:
    """Action-to-adapter router for Qin desktop V1/V2.5 compatibility."""

    ACTION_TO_ADAPTER = {
        "system_info.read_datetime": "system_info",
        "filesystem.list_dir": "filesystem_readonly",
        "filesystem.path_meta": "filesystem_readonly",
        "explorer.open_directory": "explorer",
    }

    RESERVED_ADAPTER_IDS = frozenset({"sandbox", "vm", "host_windows"})

    def resolve_adapter_id(self, task: dict) -> str:
        action = str((task or {}).get("action", "")).strip()
        if not action:
            raise ValueError("Missing action field: action")

        explicit_adapter_id = str((task or {}).get("adapter_id", "")).strip()
        if explicit_adapter_id in self.RESERVED_ADAPTER_IDS:
            return explicit_adapter_id

        if action in self.ACTION_TO_ADAPTER:
            return self.ACTION_TO_ADAPTER[action]

        if is_supported_action(action) and (action.startswith("file.") or action.startswith("app.")):
            return "sandbox"

        raise ValueError(f"Unsupported action: {action}")
