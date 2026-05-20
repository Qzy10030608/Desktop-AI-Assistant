# -*- coding: utf-8 -*-
"""
V2.5 VM Adapter

当前只负责：
1. 检查 VM Agent 是否在线
2. 读取 VM workspace 文件列表

禁止：
- 不做删除
- 不做移动
- 不做重命名
- 不做宿主机真实执行
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[5]
VM_PROFILE_PATH = PROJECT_ROOT / "data" / "user_prefs" / "vm_profiles.local.json"
VM_HEALTH_TIMEOUT = 1.2
VM_LIST_TIMEOUT = 3.0
VM_ACTION_TIMEOUT = 1.5


def _load_default_profile() -> dict[str, Any]:
    if not VM_PROFILE_PATH.exists():
        return {
            "name": "V2.5 测试虚拟机",
            "enabled": False,
            "base_url": "",
            "token": "",
        }

    with VM_PROFILE_PATH.open("r", encoding="utf-8") as f:
        data = json.load(f)

    return data.get("default", {})


def _request_json(
    url: str,
    timeout: float = VM_LIST_TIMEOUT,
    *,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
    token: str = "",
) -> dict[str, Any]:
    data = None
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "voice-ai-v25-vm-adapter",
        },
        method=method,
    )
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")

    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(req, data=data, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            return json.loads(raw)
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            payload = json.loads(raw)
        except Exception:
            payload = {}
        if not isinstance(payload, dict):
            payload = {}
        payload.setdefault("ok", False)
        payload.setdefault("adapter_id", "vm")
        payload.setdefault("message", raw.strip() or f"VM Agent HTTP {exc.code}")
        payload.setdefault("error", f"HTTP {exc.code}: {exc.reason}")
        payload["http_status"] = exc.code
        payload["http_reason"] = str(exc.reason or "")
        return payload


def _error_result(
    *,
    error: str,
    message: str = "",
    apps: list[dict[str, Any]] | None = None,
    items: list[dict[str, Any]] | None = None,
    data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    normalized_error = str(error or "").strip() or "VM request failed"
    return {
        "ok": False,
        "adapter_id": "vm",
        "message": str(message or "").strip() or f"VM 请求失败：{normalized_error}",
        "error": normalized_error,
        "apps": apps if apps is not None else [],
        "items": items if items is not None else [],
        "data": data if isinstance(data, dict) else {},
    }


class VmAdapter:
    def __init__(self, profile_id: str = "default") -> None:
        self.profile_id = profile_id
        self.profile = _load_default_profile()
        self.base_url = str(self.profile.get("base_url", "")).rstrip("/")
        self.token = str(self.profile.get("token", "") or "")

    def is_configured(self) -> bool:
        return bool(self.profile.get("enabled")) and bool(self.base_url)

    def health_check(self) -> dict[str, Any]:
        if not self.is_configured():
            return _error_result(error="VM profile 未启用或 base_url 为空")
        try:
            return _request_json(f"{self.base_url}/health", timeout=VM_HEALTH_TIMEOUT, token=self.token)
        except Exception as e:
            return _error_result(error=str(e))

        if not self.is_configured():
            return {
                "ok": False,
                "error": "VM profile 未启用或 base_url 为空",
            }

        try:
            return _request_json(f"{self.base_url}/health", token=self.token)
        except Exception as e:
            return {
                "ok": False,
                "error": str(e),
            }

    def list_file_roots(self) -> dict[str, Any]:
        if not self.is_configured():
            return _error_result(error="VM profile 未启用或 base_url 为空", data={"roots": []})
        try:
            return _request_json(f"{self.base_url}/files/roots", timeout=VM_LIST_TIMEOUT, token=self.token)
        except Exception as e:
            return _error_result(error=str(e), data={"roots": []})

    def list_files(self, root_id: str = "vm_drive_c", relative_path: str = "") -> dict[str, Any]:
        if not self.is_configured():
            return _error_result(error="VM profile 未启用或 base_url 为空", items=[])
        try:
            query = urllib.parse.urlencode({
                "root_id": str(root_id or "vm_drive_c"),
                "relative_path": str(relative_path or ""),
            })
            return _request_json(f"{self.base_url}/files/list?{query}", timeout=VM_LIST_TIMEOUT, token=self.token)
        except Exception as e:
            return _error_result(error=str(e), items=[])

        if not self.is_configured():
            return {
                "ok": False,
                "items": [],
                "error": "VM profile 未启用或 base_url 为空",
            }

        try:
            return _request_json(f"{self.base_url}/files/list", token=self.token)
        except Exception as e:
            return {
                "ok": False,
                "items": [],
                "error": str(e),
            }

    def list_apps(self) -> dict[str, Any]:
        if not self.is_configured():
            return _error_result(error="VM profile 未启用或 base_url 为空", apps=[])
        try:
            return _request_json(f"{self.base_url}/apps/list", timeout=VM_LIST_TIMEOUT, token=self.token)
        except Exception as e:
            return _error_result(error=str(e), apps=[])

        if not self.is_configured():
            return {
                "ok": False,
                "apps": [],
                "error": "VM profile 未启用或 base_url 为空",
            }

        try:
            return _request_json(f"{self.base_url}/apps/list", token=self.token)
        except Exception as e:
            return {
                "ok": False,
                "apps": [],
                "error": str(e),
            }

    def _post_app_action(self, endpoint: str, app_id: str) -> dict[str, Any]:
        normalized_app_id = str(app_id or "").strip()
        if not self.is_configured():
            return _error_result(
                error="VM profile 未启用或 base_url 为空",
                data={"app_id": normalized_app_id},
            )
        try:
            return _request_json(
                f"{self.base_url}{endpoint}",
                timeout=VM_ACTION_TIMEOUT,
                method="POST",
                payload={"app_id": normalized_app_id},
                token=self.token,
            )
        except Exception as e:
            return _error_result(error=str(e), data={"app_id": normalized_app_id})

        if not self.is_configured():
            return {
                "ok": False,
                "adapter_id": "vm",
                "error": "VM profile 未启用或 base_url 为空",
                "data": {"app_id": str(app_id or "").strip()},
            }

        try:
            return _request_json(
                f"{self.base_url}{endpoint}",
                method="POST",
                payload={"app_id": str(app_id or "").strip()},
                token=self.token,
            )
        except Exception as e:
            return {
                "ok": False,
                "adapter_id": "vm",
                "error": str(e),
                "data": {"app_id": str(app_id or "").strip()},
            }

    def locate_app(self, app_id: str) -> dict[str, Any]:
        return self._post_app_action("/apps/locate", app_id)

    def launch_app(self, app_id: str) -> dict[str, Any]:
        return self._post_app_action("/apps/launch", app_id)

    def close_app(self, app_id: str) -> dict[str, Any]:
        return self._post_app_action("/apps/close", app_id)

    def execute_action(self, payload: dict[str, Any], *, timeout: float | None = None) -> dict[str, Any]:
        normalized_payload = payload if isinstance(payload, dict) else {}
        if not self.is_configured():
            return _error_result(
                error="VM profile is not enabled or base_url is empty",
                data={"payload": normalized_payload},
            )
        try:
            return _request_json(
                f"{self.base_url}/action",
                timeout=float(timeout or VM_ACTION_TIMEOUT),
                method="POST",
                payload=normalized_payload,
                token=self.token,
            )
        except Exception as e:
            return _error_result(error=str(e), data={"payload": normalized_payload})


def get_default_vm_adapter() -> VmAdapter:
    return VmAdapter(profile_id="default")
