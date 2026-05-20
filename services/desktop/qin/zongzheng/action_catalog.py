from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal

ActionScope = Literal["system", "file", "app"]
ActionCapability = Literal[
    "inspect",
    "list",
    "meta",
    "navigate",
    "locate",
    "launch",
    "close",
    "scan",
    "index",
    "open",
    "delete",
    "restore",
    "rename",
    "copy",
    "create",
    "mkdir",
    "touch",
    "uninstall",
    "move",
    "update",
    "connect",
    "health",
    "cleanup",
]


@dataclass(frozen=True)
class ActionDefinition:
    action_id: str
    scope: ActionScope
    capability: ActionCapability
    title: str
    description: str
    v25_route: str
    v25_enabled: bool
    host_reserved: bool
    risk_key: str
    side_effects: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["side_effects"] = list(self.side_effects)
        return data


ACTION_SYSTEM_DATETIME = "system_info.read_datetime"
ACTION_WEATHER_READ_CURRENT = "weather.read_current"
ACTION_CALENDAR_READ_EVENTS = "calendar.read_events"
ACTION_FILESYSTEM_LIST_DIR = "filesystem.list_dir"
ACTION_FILESYSTEM_PATH_META = "filesystem.path_meta"
ACTION_EXPLORER_OPEN_DIRECTORY = "explorer.open_directory"

ACTION_FILE_NAVIGATE = "file.navigate"
ACTION_FILE_INSPECT = "file.inspect"
ACTION_FILE_LOCATE = "file.locate"
ACTION_FILE_OPEN = "file.open"
ACTION_FILE_CLOSE = "file.close"
ACTION_FILE_CLOSE_ALL = "file.close.all"
ACTION_FILE_DISK_RESCAN = "file.disk_rescan"
ACTION_FILE_CREATE = "file.create"
ACTION_FILE_DELETE = "file.delete"
ACTION_FILE_MOVE = "file.move"
ACTION_FILE_RENAME = "file.rename"
ACTION_FILE_COPY = "file.copy"
ACTION_FILE_MKDIR = "file.mkdir"
ACTION_FILE_TOUCH = "file.touch"
ACTION_FILE_RESTORE = "file.restore"
ACTION_FOLDER_OPEN = "folder.open"
ACTION_FOLDER_CLOSE = "folder.close"
ACTION_FOLDER_RENAME = "folder.rename"
ACTION_FOLDER_CREATE = "folder.create"
ACTION_FOLDER_MKDIR = "folder.mkdir"
ACTION_FOLDER_MOVE = "folder.move"
ACTION_FOLDER_DELETE = "folder.delete"
ACTION_FOLDER_RESTORE = "folder.restore"

ACTION_APP_LOCATE = "app.locate"
ACTION_APP_LAUNCH = "app.launch"
ACTION_APP_CLOSE = "app.close"
ACTION_APP_UNINSTALL = "app.uninstall"
ACTION_APP_MOVE = "app.move"
ACTION_APP_RELOCATE = "app.relocate"
ACTION_APP_UPDATE = "app.update"

ACTION_BROWSER_SEARCH_OPEN = "browser.search_open"

ACTION_VM_CONNECT = "vm.connect"
ACTION_VM_HEALTH_CHECK = "vm.health_check"
ACTION_VM_LIST_APPS = "vm.list_apps"
ACTION_VM_LIST_FILES = "vm.list_files"
ACTION_VM_CLEANUP = "vm.cleanup"


ACTION_CATALOG: dict[str, ActionDefinition] = {
    ACTION_SYSTEM_DATETIME: ActionDefinition(
        action_id=ACTION_SYSTEM_DATETIME,
        scope="system",
        capability="inspect",
        title="Read date and time",
        description="Read current local date and time.",
        v25_route="sandbox.system_info",
        v25_enabled=True,
        host_reserved=False,
        risk_key="readonly",
    ),
    ACTION_WEATHER_READ_CURRENT: ActionDefinition(
        action_id=ACTION_WEATHER_READ_CURRENT,
        scope="system",
        capability="inspect",
        title="Read current weather",
        description="Reserved weather read action. No provider is connected in V1.",
        v25_route="sandbox.system_info",
        v25_enabled=True,
        host_reserved=False,
        risk_key="readonly",
    ),
    ACTION_CALENDAR_READ_EVENTS: ActionDefinition(
        action_id=ACTION_CALENDAR_READ_EVENTS,
        scope="system",
        capability="inspect",
        title="Read calendar events",
        description="Reserved calendar read action. Requires future user authorization.",
        v25_route="sandbox.system_info",
        v25_enabled=True,
        host_reserved=False,
        risk_key="readonly",
    ),
    ACTION_FILESYSTEM_LIST_DIR: ActionDefinition(
        action_id=ACTION_FILESYSTEM_LIST_DIR,
        scope="file",
        capability="list",
        title="List directory",
        description="List entries under a governed directory.",
        v25_route="sandbox.file_governance",
        v25_enabled=True,
        host_reserved=False,
        risk_key="readonly",
    ),
    ACTION_FILESYSTEM_PATH_META: ActionDefinition(
        action_id=ACTION_FILESYSTEM_PATH_META,
        scope="file",
        capability="meta",
        title="Read path metadata",
        description="Read metadata for a governed path.",
        v25_route="sandbox.file_governance",
        v25_enabled=True,
        host_reserved=False,
        risk_key="readonly",
    ),
    ACTION_EXPLORER_OPEN_DIRECTORY: ActionDefinition(
        action_id=ACTION_EXPLORER_OPEN_DIRECTORY,
        scope="file",
        capability="open",
        title="Open directory",
        description="Open a governed directory in the system file explorer.",
        v25_route="sandbox.file_governance",
        v25_enabled=True,
        host_reserved=True,
        risk_key="host_visible",
        side_effects=("opens_host_app",),
    ),
    ACTION_FILE_NAVIGATE: ActionDefinition(
        action_id=ACTION_FILE_NAVIGATE,
        scope="file",
        capability="navigate",
        title="Navigate file object",
        description="Navigate inside a governed file view.",
        v25_route="sandbox.file_governance",
        v25_enabled=True,
        host_reserved=False,
        risk_key="ui_only",
    ),
    ACTION_FILE_INSPECT: ActionDefinition(
        action_id=ACTION_FILE_INSPECT,
        scope="file",
        capability="inspect",
        title="Inspect file object",
        description="Inspect a governed file object without opening it.",
        v25_route="sandbox.file_governance",
        v25_enabled=True,
        host_reserved=False,
        risk_key="readonly",
    ),
    ACTION_FILE_LOCATE: ActionDefinition(
        action_id=ACTION_FILE_LOCATE,
        scope="file",
        capability="locate",
        title="Locate file object",
        description="Locate a governed file object inside the VM.",
        v25_route="sandbox.file_governance",
        v25_enabled=True,
        host_reserved=True,
        risk_key="host_visible",
        side_effects=("opens_vm_location",),
    ),
    ACTION_FILE_OPEN: ActionDefinition(
        action_id=ACTION_FILE_OPEN,
        scope="file",
        capability="open",
        title="Open file",
        description="Open a governed file or folder inside the VM.",
        v25_route="sandbox.file_governance",
        v25_enabled=True,
        host_reserved=True,
        risk_key="vm_file_open",
        side_effects=("opens_vm_window",),
    ),
    ACTION_FILE_CLOSE: ActionDefinition(
        action_id=ACTION_FILE_CLOSE,
        scope="file",
        capability="close",
        title="Close file",
        description="Close a file or folder window opened inside the VM.",
        v25_route="sandbox.file_governance",
        v25_enabled=True,
        host_reserved=True,
        risk_key="process_stop",
        side_effects=("closes_vm_window",),
    ),
    ACTION_FILE_CLOSE_ALL: ActionDefinition(
        action_id=ACTION_FILE_CLOSE_ALL,
        scope="file",
        capability="close",
        title="Close all file windows",
        description="Close governed file windows opened inside the VM.",
        v25_route="sandbox.file_governance",
        v25_enabled=True,
        host_reserved=True,
        risk_key="process_stop",
        side_effects=("closes_vm_windows",),
    ),
    ACTION_FILE_DISK_RESCAN: ActionDefinition(
        action_id=ACTION_FILE_DISK_RESCAN,
        scope="file",
        capability="scan",
        title="Rescan disk",
        description="Scan a governed disk for V2.5 governance testing.",
        v25_route="sandbox.file_governance",
        v25_enabled=True,
        host_reserved=False,
        risk_key="scan",
    ),
    ACTION_FILE_DELETE: ActionDefinition(
        action_id=ACTION_FILE_DELETE,
        scope="file",
        capability="delete",
        title="Delete file",
        description="Delete a governed file object in VM testing.",
        v25_route="sandbox.file_governance",
        v25_enabled=True,
        host_reserved=True,
        risk_key="file_delete",
        side_effects=("deletes_file",),
    ),
    ACTION_FILE_MOVE: ActionDefinition(
        action_id=ACTION_FILE_MOVE,
        scope="file",
        capability="move",
        title="Move file",
        description="Move a governed file object in VM testing.",
        v25_route="sandbox.file_governance",
        v25_enabled=True,
        host_reserved=True,
        risk_key="file_move",
        side_effects=("moves_file",),
    ),
    ACTION_FILE_RENAME: ActionDefinition(
        action_id=ACTION_FILE_RENAME,
        scope="file",
        capability="rename",
        title="Rename file",
        description="Rename a governed file object in VM testing.",
        v25_route="sandbox.file_governance",
        v25_enabled=True,
        host_reserved=True,
        risk_key="file_move",
        side_effects=("renames_file",),
    ),
    ACTION_FILE_COPY: ActionDefinition(
        action_id=ACTION_FILE_COPY,
        scope="file",
        capability="copy",
        title="Copy file",
        description="Copy a governed file object in VM testing.",
        v25_route="sandbox.file_governance",
        v25_enabled=True,
        host_reserved=True,
        risk_key="file_move",
        side_effects=("writes_file",),
    ),
    ACTION_FILE_MKDIR: ActionDefinition(
        action_id=ACTION_FILE_MKDIR,
        scope="file",
        capability="mkdir",
        title="Create directory",
        description="Create a directory in VM testing.",
        v25_route="sandbox.file_governance",
        v25_enabled=True,
        host_reserved=True,
        risk_key="file_create",
        side_effects=("creates_directory",),
    ),
    ACTION_FILE_TOUCH: ActionDefinition(
        action_id=ACTION_FILE_TOUCH,
        scope="file",
        capability="touch",
        title="Create file",
        description="Create a file in VM testing.",
        v25_route="sandbox.file_governance",
        v25_enabled=True,
        host_reserved=True,
        risk_key="file_create",
        side_effects=("creates_file",),
    ),
    ACTION_FILE_CREATE: ActionDefinition(
        action_id=ACTION_FILE_CREATE,
        scope="file",
        capability="create",
        title="Create file",
        description="Create a file in VM testing.",
        v25_route="sandbox.file_governance",
        v25_enabled=True,
        host_reserved=True,
        risk_key="file_create",
        side_effects=("creates_file",),
    ),
    ACTION_FILE_RESTORE: ActionDefinition(
        action_id=ACTION_FILE_RESTORE,
        scope="file",
        capability="restore",
        title="Restore file",
        description="Restore a file from VM Shaofu material.",
        v25_route="sandbox.file_governance",
        v25_enabled=True,
        host_reserved=True,
        risk_key="file_restore",
        side_effects=("restores_file",),
    ),
    ACTION_FOLDER_OPEN: ActionDefinition(
        action_id=ACTION_FOLDER_OPEN,
        scope="file",
        capability="open",
        title="Open folder",
        description="Open a governed folder inside the VM.",
        v25_route="sandbox.file_governance",
        v25_enabled=True,
        host_reserved=True,
        risk_key="vm_file_open",
        side_effects=("opens_vm_window",),
    ),
    ACTION_FOLDER_CLOSE: ActionDefinition(
        action_id=ACTION_FOLDER_CLOSE,
        scope="file",
        capability="close",
        title="Close folder",
        description="Close a folder window opened inside the VM.",
        v25_route="sandbox.file_governance",
        v25_enabled=True,
        host_reserved=True,
        risk_key="process_stop",
        side_effects=("closes_vm_window",),
    ),
    ACTION_FOLDER_RENAME: ActionDefinition(
        action_id=ACTION_FOLDER_RENAME,
        scope="file",
        capability="rename",
        title="Rename folder",
        description="Rename a governed folder object in VM testing.",
        v25_route="sandbox.file_governance",
        v25_enabled=True,
        host_reserved=True,
        risk_key="file_move",
        side_effects=("renames_directory",),
    ),
    ACTION_FOLDER_CREATE: ActionDefinition(
        action_id=ACTION_FOLDER_CREATE,
        scope="file",
        capability="create",
        title="Create folder",
        description="Create a folder in VM testing.",
        v25_route="sandbox.file_governance",
        v25_enabled=True,
        host_reserved=True,
        risk_key="file_create",
        side_effects=("creates_directory",),
    ),
    ACTION_FOLDER_MKDIR: ActionDefinition(
        action_id=ACTION_FOLDER_MKDIR,
        scope="file",
        capability="mkdir",
        title="Create folder",
        description="Create a folder in VM testing.",
        v25_route="sandbox.file_governance",
        v25_enabled=True,
        host_reserved=True,
        risk_key="file_create",
        side_effects=("creates_directory",),
    ),
    ACTION_FOLDER_MOVE: ActionDefinition(
        action_id=ACTION_FOLDER_MOVE,
        scope="file",
        capability="move",
        title="Move folder",
        description="Move a folder in VM testing.",
        v25_route="sandbox.file_governance",
        v25_enabled=True,
        host_reserved=True,
        risk_key="file_move",
        side_effects=("moves_directory",),
    ),
    ACTION_FOLDER_DELETE: ActionDefinition(
        action_id=ACTION_FOLDER_DELETE,
        scope="file",
        capability="delete",
        title="Delete folder",
        description="Delete a folder in VM testing.",
        v25_route="sandbox.file_governance",
        v25_enabled=True,
        host_reserved=True,
        risk_key="file_delete",
        side_effects=("deletes_directory",),
    ),
    ACTION_FOLDER_RESTORE: ActionDefinition(
        action_id=ACTION_FOLDER_RESTORE,
        scope="file",
        capability="restore",
        title="Restore folder",
        description="Restore a folder from VM Shaofu material.",
        v25_route="sandbox.file_governance",
        v25_enabled=True,
        host_reserved=True,
        risk_key="file_restore",
        side_effects=("restores_directory",),
    ),
    ACTION_APP_LOCATE: ActionDefinition(
        action_id=ACTION_APP_LOCATE,
        scope="app",
        capability="locate",
        title="Locate app",
        description="Locate an app object in the software governance list.",
        v25_route="sandbox.software_governance",
        v25_enabled=True,
        host_reserved=True,
        risk_key="host_visible",
        side_effects=("may_open_host_location",),
    ),
    ACTION_APP_LAUNCH: ActionDefinition(
        action_id=ACTION_APP_LAUNCH,
        scope="app",
        capability="launch",
        title="Launch app",
        description="Launch a governed app.",
        v25_route="sandbox.software_governance",
        v25_enabled=True,
        host_reserved=True,
        risk_key="process_start",
        side_effects=("starts_process",),
    ),
    ACTION_APP_CLOSE: ActionDefinition(
        action_id=ACTION_APP_CLOSE,
        scope="app",
        capability="close",
        title="Close app",
        description="Close a governed app.",
        v25_route="sandbox.software_governance",
        v25_enabled=True,
        host_reserved=True,
        risk_key="process_stop",
        side_effects=("stops_process",),
    ),
    ACTION_APP_UNINSTALL: ActionDefinition(
        action_id=ACTION_APP_UNINSTALL,
        scope="app",
        capability="uninstall",
        title="Uninstall app",
        description="Simulate uninstalling an app in the V2.5 sandbox.",
        v25_route="sandbox.software_governance",
        v25_enabled=True,
        host_reserved=True,
        risk_key="destructive_simulation",
        side_effects=("removes_software",),
    ),
    ACTION_APP_MOVE: ActionDefinition(
        action_id=ACTION_APP_MOVE,
        scope="app",
        capability="move",
        title="Move app",
        description="Simulate moving an app or app entry in the V2.5 sandbox.",
        v25_route="sandbox.software_governance",
        v25_enabled=True,
        host_reserved=True,
        risk_key="destructive_simulation",
        side_effects=("moves_installation",),
    ),
    ACTION_APP_RELOCATE: ActionDefinition(
        action_id=ACTION_APP_RELOCATE,
        scope="app",
        capability="relocate",
        title="Relocate app",
        description="Relocate an installed app with compatibility material in VM testing.",
        v25_route="sandbox.software_governance",
        v25_enabled=True,
        host_reserved=True,
        risk_key="installed_app_relocate",
        side_effects=("copies_installation", "renames_installation", "creates_junction"),
    ),
    ACTION_APP_UPDATE: ActionDefinition(
        action_id=ACTION_APP_UPDATE,
        scope="app",
        capability="update",
        title="Update app",
        description="Simulate updating an app in the V2.5 sandbox.",
        v25_route="sandbox.software_governance",
        v25_enabled=True,
        host_reserved=True,
        risk_key="destructive_simulation",
        side_effects=("changes_installation",),
    ),
    ACTION_BROWSER_SEARCH_OPEN: ActionDefinition(
        action_id=ACTION_BROWSER_SEARCH_OPEN,
        scope="app",
        capability="open",
        title="Open browser search",
        description="Open a search query in a governed browser during VM testing.",
        v25_route="sandbox.browser_governance",
        v25_enabled=True,
        host_reserved=True,
        risk_key="network_search",
        side_effects=("opens_browser", "network_request"),
    ),
    ACTION_VM_CONNECT: ActionDefinition(
        action_id=ACTION_VM_CONNECT,
        scope="system",
        capability="connect",
        title="Connect VM bridge",
        description="Review and authorize VM bridge connection.",
        v25_route="sandbox.vm_bridge",
        v25_enabled=True,
        host_reserved=False,
        risk_key="vm_connection",
    ),
    ACTION_VM_HEALTH_CHECK: ActionDefinition(
        action_id=ACTION_VM_HEALTH_CHECK,
        scope="system",
        capability="health",
        title="Check VM health",
        description="Review and authorize VM health check.",
        v25_route="sandbox.vm_bridge",
        v25_enabled=True,
        host_reserved=False,
        risk_key="vm_connection",
    ),
    ACTION_VM_LIST_APPS: ActionDefinition(
        action_id=ACTION_VM_LIST_APPS,
        scope="system",
        capability="list",
        title="List VM apps",
        description="Review and authorize VM app list retrieval.",
        v25_route="sandbox.vm_bridge",
        v25_enabled=True,
        host_reserved=False,
        risk_key="vm_connection",
    ),
    ACTION_VM_LIST_FILES: ActionDefinition(
        action_id=ACTION_VM_LIST_FILES,
        scope="system",
        capability="list",
        title="List VM files",
        description="Review and authorize VM file list retrieval.",
        v25_route="sandbox.vm_bridge",
        v25_enabled=True,
        host_reserved=False,
        risk_key="vm_connection",
    ),
    ACTION_VM_CLEANUP: ActionDefinition(
        action_id=ACTION_VM_CLEANUP,
        scope="system",
        capability="cleanup",
        title="Cleanup VM session",
        description="Review and authorize VM session cleanup.",
        v25_route="sandbox.vm_bridge",
        v25_enabled=True,
        host_reserved=False,
        risk_key="vm_connection",
    ),
}


def normalize_action(action: str | None) -> str:
    return str(action or "").strip().lower()


def get_action(action: str | None) -> ActionDefinition | None:
    return ACTION_CATALOG.get(normalize_action(action))


def is_supported_action(action: str | None) -> bool:
    return get_action(action) is not None


def is_v25_enabled(action: str | None) -> bool:
    definition = get_action(action)
    return bool(definition and definition.v25_enabled)


def list_actions(scope: ActionScope | None = None) -> list[ActionDefinition]:
    actions = list(ACTION_CATALOG.values())
    if scope is not None:
        actions = [item for item in actions if item.scope == scope]
    return sorted(actions, key=lambda item: item.action_id)


def route_for_v25(action: str | None) -> str:
    definition = get_action(action)
    return definition.v25_route if definition is not None else "sandbox.unknown"
