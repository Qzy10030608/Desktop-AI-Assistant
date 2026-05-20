from __future__ import annotations

from typing import Any

from services.desktop.tianting.vm_bridge.vm_connection_types import (
    VM_STATE_CONNECTED,
    VM_STATE_CONNECTING,
)


def build_vm_status_text(state: str, health: dict[str, Any] | None = None, error: str = "") -> str:
    normalized = str(state or "").strip().lower()
    if normalized == VM_STATE_CONNECTING:
        return "虚拟机状态：连接中..."
    if normalized == VM_STATE_CONNECTED:
        payload = health if isinstance(health, dict) else {}
        hostname = str(payload.get("hostname", "-") or "-")
        workspace = str(payload.get("workspace", "-") or "-")
        return f"虚拟机状态：已连接 | {hostname} | {workspace}"
    error_text = str(error or "").strip() or "-"
    return f"虚拟机状态：未连接 | {error_text}"


def build_test_backend_label(backend: str, vm_state: str) -> str:
    normalized_backend = str(backend or "").strip().lower()
    normalized_state = str(vm_state or "").strip().lower()
    if normalized_backend != "vm":
        return "沙盒测试"
    if normalized_state == VM_STATE_CONNECTING:
        return "虚拟机测试（连接中）"
    if normalized_state == VM_STATE_CONNECTED:
        return "虚拟机测试"
    return "虚拟机测试（VM 未连接）"

