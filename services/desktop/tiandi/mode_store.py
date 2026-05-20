from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, TypeGuard

from services.desktop.desktop_models import DesktopMode, ModeState, now_iso


ALLOWED_MODES: tuple[DesktopMode, ...] = (
    "disabled",
    "restricted",
    "trusted",
    "test",
)

TEST_BACKENDS = (
    "sandbox",
    "vm",
)

REAL_DESKTOP_MODES = {
    "disabled",
    "restricted",
    "trusted",
}


def _is_desktop_mode(value: str) -> TypeGuard[DesktopMode]:
    return value in ALLOWED_MODES


def _is_real_desktop_mode(value: str) -> bool:
    return str(value or "").strip().lower() in REAL_DESKTOP_MODES


def _normalize_real_mode(value: str, fallback: str = "trusted") -> str:
    normalized = str(value or "").strip().lower()
    if normalized in REAL_DESKTOP_MODES:
        return normalized

    fallback_normalized = str(fallback or "").strip().lower()
    if fallback_normalized in REAL_DESKTOP_MODES:
        return fallback_normalized

    return "trusted"


def _normalize_test_backend(value: str, fallback: str = "sandbox") -> str:
    normalized = str(value or "").strip().lower()
    if normalized in TEST_BACKENDS:
        return normalized

    fallback_normalized = str(fallback or "").strip().lower()
    if fallback_normalized in TEST_BACKENDS:
        return fallback_normalized

    return "sandbox"


class ModeStore:
    def __init__(self, project_root: Path | None = None) -> None:
        self.project_root = project_root or Path(__file__).resolve().parents[3]

        self.defaults_path = self.project_root / "data" / "defaults" / "desktop_mode.json"
        self.local_path = self.project_root / "data" / "user_prefs" / "desktop_mode.local.json"
        self.runtime_path = self.project_root / "data" / "runtime" / "desktop_runtime.json"

        self.local_path.parent.mkdir(parents=True, exist_ok=True)
        self.runtime_path.parent.mkdir(parents=True, exist_ok=True)
        self._repair_startup_test_mode()

    def _read_json(self, path: Path, default: Dict[str, Any]) -> Dict[str, Any]:
        if not path.exists():
            return dict(default)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else dict(default)
        except Exception:
            return dict(default)

    def _write_json(self, path: Path, data: Dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _repair_startup_test_mode(self) -> None:
        """
        只在 ModeStore 初始化时执行一次。

        目的：
        - 如果上次关闭程序时停在 test，则启动时恢复到 last_real_mode；
        - 但程序运行中用户再次点击 test 时，不再被 get_mode_state() 强制改回真实模式。
        """
        local = self._read_json(self.local_path, {})
        runtime = self._read_json(self.runtime_path, {})

        raw_mode = str(
            local.get("desktop_mode")
            or local.get("current_mode")
            or runtime.get("desktop_mode")
            or runtime.get("current_mode")
            or ""
        ).strip().lower()

        if raw_mode != "test":
            return

        last_real_mode = _normalize_real_mode(
            str(
                local.get("last_real_mode")
                or runtime.get("last_real_mode")
                or "trusted"
            ),
            fallback="trusted",
        )

        updated_at = now_iso()
        host_execution_enabled = last_real_mode == "trusted"

        local.update({
            "current_mode": last_real_mode,
            "desktop_mode": last_real_mode,
            "last_real_mode": last_real_mode,
            "test_backend": "sandbox",
            "host_execution_enabled": host_execution_enabled,
            "updated_at": updated_at,
        })

        runtime_state = {
            "desktop_mode": last_real_mode,
            "current_mode": last_real_mode,
            "last_real_mode": last_real_mode,
            "test_backend": "sandbox",
            "execution_backend": "host" if host_execution_enabled else "none",
            "host_execution_enabled": host_execution_enabled,
            "updated_at": updated_at,
        }

        self._write_json(self.local_path, local)
        self._write_json(self.runtime_path, runtime_state)

    def _default_mode(self) -> DesktopMode:
        defaults = self._read_json(
            self.defaults_path,
            {
                "available_modes": ["disabled", "restricted", "trusted", "test"],
                "default_mode": "disabled",
            },
        )

        raw_default_mode = str(defaults.get("default_mode", "disabled")).strip().lower()
        if _is_desktop_mode(raw_default_mode):
            return raw_default_mode

        return "disabled"

    def get_available_modes(self) -> list[str]:
        data = self._read_json(
            self.defaults_path,
            {
                "available_modes": ["disabled", "restricted", "trusted", "test"],
                "default_mode": "disabled",
            },
        )

        raw_modes = data.get(
            "available_modes",
            ["disabled", "restricted", "trusted", "test"],
        )

        result: list[str] = []

        if isinstance(raw_modes, list):
            for item in raw_modes:
                mode = str(item or "").strip().lower()
                if mode and mode not in result:
                    result.append(mode)

        return result or ["disabled", "restricted", "trusted", "test"]

    def get_mode_state(self) -> ModeState:
        """
        读取当前桌面模式。

        注意：
        - 启动时恢复 test 的逻辑已经在 _repair_startup_test_mode() 中处理；
        - 这里不能再把 test 自动转回 last_real_mode；
        - 否则用户点击测试模式后会立刻被读回 trusted，导致按钮无效。
        """
        default_mode = self._default_mode()

        data = self._read_json(
            self.local_path,
            {
                "current_mode": default_mode,
                "desktop_mode": default_mode,
                "last_real_mode": "trusted",
                "test_backend": "sandbox",
                "updated_at": now_iso(),
            },
        )

        raw_current_mode = str(
            data.get("desktop_mode", data.get("current_mode", default_mode))
        ).strip().lower() or default_mode

        if not _is_desktop_mode(raw_current_mode):
            raw_current_mode = default_mode

        return ModeState(
            current_mode=raw_current_mode,
            updated_at=str(data.get("updated_at", now_iso())).strip() or now_iso(),
        )

    def get_runtime_state(self) -> Dict[str, Any]:
        """
        获取运行态。

        固定规则：
        - desktop_mode 来自 get_mode_state()；
        - get_mode_state() 已经保证启动时不会恢复 test；
        - 如果当前不是 test，则 execution_backend 按真实模式计算；
        - 如果当前是 test，则 test_backend 参与 execution_backend；
        - test_backend 默认 sandbox。
        """
        mode_state = self.get_mode_state()

        runtime = self._read_json(self.runtime_path, {})
        local = self._read_json(self.local_path, {})

        desktop_mode = mode_state.current_mode

        last_real_mode = _normalize_real_mode(
            str(local.get("last_real_mode", runtime.get("last_real_mode", "trusted")) or "trusted"),
            fallback="trusted",
        )

        test_backend = _normalize_test_backend(
            str(runtime.get("test_backend", local.get("test_backend", "sandbox")) or "sandbox"),
            fallback="sandbox",
        )

        host_execution_enabled = desktop_mode == "trusted"

        execution_backend = (
            test_backend
            if desktop_mode == "test"
            else ("host" if host_execution_enabled else "none")
        )

        return {
            "desktop_mode": desktop_mode,
            "current_mode": desktop_mode,
            "last_real_mode": last_real_mode,
            "test_backend": test_backend,
            "execution_backend": execution_backend,
            "host_execution_enabled": host_execution_enabled,
            "updated_at": mode_state.updated_at,
        }

    def set_mode(self, mode: str) -> ModeState:
        """
        设置桌面模式。

        关键规则：
        - 用户主动进入 test 时，默认 test_backend 必须是 sandbox；
        - VM 只能通过 set_test_backend("vm") 进入；
        - 退出 test 时，保存 last_real_mode；
        - test 不作为 last_real_mode。
        """
        normalized_mode = str(mode or "").strip().lower()

        if not _is_desktop_mode(normalized_mode):
            raise ValueError(f"不支持的模式: {mode}")

        runtime_state = self.get_runtime_state()

        previous_mode = str(
            runtime_state.get("desktop_mode", runtime_state.get("current_mode", "trusted")) or "trusted"
        ).strip().lower()

        previous_last_real = str(
            runtime_state.get("last_real_mode", "trusted") or "trusted"
        ).strip().lower()

        if normalized_mode == "test":
            # 进入测试模式时，记录从哪个真实模式进入。
            last_real_mode = _normalize_real_mode(
                previous_mode,
                fallback=previous_last_real,
            )

            # 重点：每次主动进入测试模式，默认都回到 sandbox。
            test_backend = "sandbox"
        else:
            last_real_mode = _normalize_real_mode(
                normalized_mode,
                fallback="trusted",
            )

            # 非测试模式下保留 sandbox 作为安全默认，不继承 VM。
            test_backend = "sandbox"

        updated_at = now_iso()
        host_execution_enabled = normalized_mode == "trusted"

        execution_backend = (
            test_backend
            if normalized_mode == "test"
            else ("host" if host_execution_enabled else "none")
        )

        local_state = {
            "current_mode": normalized_mode,
            "desktop_mode": normalized_mode,
            "last_real_mode": last_real_mode,
            "test_backend": test_backend,
            "host_execution_enabled": host_execution_enabled,
            "updated_at": updated_at,
        }

        runtime_state_out = {
            "desktop_mode": normalized_mode,
            "current_mode": normalized_mode,
            "last_real_mode": last_real_mode,
            "test_backend": test_backend,
            "execution_backend": execution_backend,
            "host_execution_enabled": host_execution_enabled,
            "updated_at": updated_at,
        }

        self._write_json(self.local_path, local_state)
        self._write_json(self.runtime_path, runtime_state_out)

        return ModeState(
            current_mode=normalized_mode,
            updated_at=updated_at,
        )

    def set_test_backend(self, backend: str) -> Dict[str, Any]:
        """
        设置测试出口。

        关键规则：
        - 只有用户明确选择 VM 时，才把 test_backend 写成 vm；
        - 如果当前不是 test，允许保存 test_backend，但不会启动 VM；
        - 下次用户再次点击“测试模式”时，set_mode("test") 仍会重置为 sandbox。
        """
        normalized = _normalize_test_backend(backend, fallback="sandbox")
        state = self.get_mode_state()
        current_runtime = self.get_runtime_state()

        updated_at = now_iso()

        last_real_mode = _normalize_real_mode(
            str(current_runtime.get("last_real_mode", "trusted") or "trusted"),
            fallback="trusted",
        )

        host_execution_enabled = state.current_mode == "trusted"

        execution_backend = (
            normalized
            if state.current_mode == "test"
            else ("host" if host_execution_enabled else "none")
        )

        runtime_state = {
            "desktop_mode": state.current_mode,
            "current_mode": state.current_mode,
            "last_real_mode": last_real_mode,
            "test_backend": normalized,
            "execution_backend": execution_backend,
            "host_execution_enabled": host_execution_enabled,
            "updated_at": updated_at,
        }

        local = self._read_json(self.local_path, {})
        local.update({
            "current_mode": state.current_mode,
            "desktop_mode": state.current_mode,
            "last_real_mode": last_real_mode,
            "test_backend": normalized,
            "host_execution_enabled": host_execution_enabled,
            "updated_at": updated_at,
        })

        self._write_json(self.local_path, local)
        self._write_json(self.runtime_path, runtime_state)

        return runtime_state

    def set_host_execution_enabled(self, enabled: bool) -> Dict[str, Any]:
        """
        兼容旧入口。

        注意：
        - Host 是否启用不再由传入 enabled 直接决定；
        - trusted 模式下 Host 执行开启；
        - 其他模式下 Host 执行关闭。
        """
        runtime_state = self.get_runtime_state()
        local = self._read_json(self.local_path, {})

        mode = str(
            runtime_state.get("desktop_mode")
            or runtime_state.get("current_mode")
            or "disabled"
        ).strip().lower()

        if not _is_desktop_mode(mode):
            mode = "disabled"

        last_real_mode = _normalize_real_mode(
            str(runtime_state.get("last_real_mode", "trusted") or "trusted"),
            fallback="trusted",
        )

        test_backend = _normalize_test_backend(
            str(runtime_state.get("test_backend", "sandbox") or "sandbox"),
            fallback="sandbox",
        )

        host_enabled = mode == "trusted"
        updated_at = now_iso()

        local.update({
            "current_mode": mode,
            "desktop_mode": mode,
            "last_real_mode": last_real_mode,
            "test_backend": test_backend,
            "host_execution_enabled": host_enabled,
            "updated_at": updated_at,
        })

        runtime_state_out = {
            "desktop_mode": mode,
            "current_mode": mode,
            "last_real_mode": last_real_mode,
            "test_backend": test_backend,
            "execution_backend": "host" if mode == "trusted" else (test_backend if mode == "test" else "none"),
            "host_execution_enabled": host_enabled,
            "updated_at": updated_at,
        }

        self._write_json(self.local_path, local)
        self._write_json(self.runtime_path, runtime_state_out)

        return runtime_state_out