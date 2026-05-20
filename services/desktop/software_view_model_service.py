from __future__ import annotations

from typing import Any, Dict, Iterable, List, Tuple

from services.desktop.qin.liyi.permission_rules import (
    PERMISSION_COLORS,
    PermissionState,
    normalize_permission_state,
)
from services.desktop.software_models import SoftwareRecord, SoftwareViewRow


FILTER_TO_PERMISSION = {
    "all": None,
    "allow": "allow",
    "deny": "deny",
    "unset": "unset",
    "once": "once",
}


class SoftwareViewModelService:
    ENTRY_LAUNCH_KINDS = {"appx", "shell_app", "protocol", "launcher", "command"}

    def _clean_text(self, value: str | None, default: str = "") -> str:
        text = str(value or "").strip()
        if text.lower() == "none":
            return default
        return text or default

    def _is_nonlocal_entry(self, value: str | None) -> bool:
        text = str(value or "").strip().lower()
        return text.startswith(
            (
                "shell:",
                "steam://",
                "http://",
                "https://",
                "ms-settings:",
                "microsoft-edge:",
                "calculator:",
                "appx:",
            )
        )

    def _typed_permission_state(self, value: str | None) -> PermissionState:
        return normalize_permission_state(value)

    def _display_permission_state(self, permission_state: str | None) -> PermissionState:
        normalized = self._typed_permission_state(str(permission_state or "unset").strip().lower() or "unset")
        return "deny" if normalized == "unset" else normalized

    def _permission_label(self, permission_state: str | None) -> str:
        return {
            "allow": "是",
            "deny": "否",
            "once": "受限",
        }.get(self._display_permission_state(permission_state), "否")

    def _filter_matches(self, permission_state: str | None, filter_key: str) -> bool:
        matched_permission = FILTER_TO_PERMISSION.get(filter_key)
        if matched_permission is None:
            return True
        if matched_permission == "deny":
            return self._display_permission_state(permission_state) == "deny"
        return self._typed_permission_state(str(permission_state or "unset").strip().lower() or "unset") == matched_permission

    def _effective_target_path(self, item: SoftwareRecord) -> str:
        for candidate in (item.manual_target_path, item.target_path):
            text = self._clean_text(candidate)
            if text:
                return text
        return ""

    def _effective_launch_target_kind(self, item: SoftwareRecord) -> str:
        for candidate in (item.manual_launch_target_kind, item.launch_target_kind):
            text = self._clean_text(candidate)
            if text and text != "missing":
                return text
        return "missing"

    def _effective_launch_target_raw(self, item: SoftwareRecord) -> str:
        for candidate in (item.manual_launch_target_raw, item.launch_target_raw):
            text = self._clean_text(candidate)
            if text:
                return text
        return ""

    def _effective_entry_path(self, item: SoftwareRecord) -> str:
        for candidate in (item.manual_entry_path, item.entry_path, item.manual_target_path, item.target_path):
            text = self._clean_text(candidate)
            if text:
                return text
        return ""

    def _effective_icon_source_path(self, item: SoftwareRecord) -> str:
        for candidate in (
            item.manual_target_path,
            item.manual_entry_path,
            item.icon_source_path,
            item.entry_path,
            item.target_path,
        ):
            text = self._clean_text(candidate)
            if text and not self._is_nonlocal_entry(text):
                return text
        return ""

    def _status_profile(self, item: SoftwareRecord) -> Tuple[str, str]:
        effective_target_path = self._effective_target_path(item)
        effective_launch_target_kind = self._effective_launch_target_kind(item)
        effective_launch_target_raw = self._effective_launch_target_raw(item)
        path_status = self._clean_text(item.path_status, "missing")

        if effective_target_path:
            if item.manual_bound:
                return "已补路径", "#38BDF8"
            if item.builtin:
                return "内置", "#60A5FA"
            if item.source == "confirmed":
                return "已信任", "#22C55E"
            return "候选", "#FACC15"

        if effective_launch_target_raw and effective_launch_target_kind in self.ENTRY_LAUNCH_KINDS:
            if item.manual_bound:
                return "已补入口", "#A78BFA"
            if item.platform == "steam" or effective_launch_target_raw.lower().startswith("steam://"):
                return "Steam 游戏", "#6EE7F9"
            if effective_launch_target_kind == "appx":
                return "AppX 入口", "#60A5FA"
            if effective_launch_target_kind == "shell_app":
                return "Shell 入口", "#60A5FA"
            if effective_launch_target_kind == "protocol":
                return "协议入口", "#A78BFA"
            if item.platform not in {"", "unknown"} and item.platform_object_type == "game":
                return f"{item.platform.capitalize()}游戏", "#A78BFA"
            return "平台入口", "#A78BFA"

        if path_status == "driver_or_runtime":
            return "驱动/运行时", "#64748B"
        if path_status == "installer_bundle":
            return "安装器/卸载器", "#FB7185"
        if path_status == "registry_residual":
            return "注册表残留", "#F59E0B"
        if item.manual_bound:
            return "绑定待确认", "#38BDF8"
        return "路径缺失", "#F97316"

    def _truncate_path(self, path_text: str, *, limit: int = 72) -> str:
        text = str(path_text or "").strip()
        if len(text) <= limit:
            return text or "-"
        return f"...{text[-(limit - 3):]}"

    def _path_display(self, item: SoftwareRecord) -> Tuple[str, str]:
        effective_target_path = self._effective_target_path(item)
        effective_launch_target_kind = self._effective_launch_target_kind(item)
        effective_launch_target_raw = self._effective_launch_target_raw(item)
        path_status = self._clean_text(item.path_status, "missing")

        if effective_target_path:
            return self._truncate_path(effective_target_path), effective_target_path
        if effective_launch_target_raw and effective_launch_target_kind in self.ENTRY_LAUNCH_KINDS:
            if item.platform == "steam" or effective_launch_target_raw.lower().startswith("steam://"):
                label = "Steam 游戏"
            elif effective_launch_target_kind == "appx":
                label = "AppX 入口"
            elif effective_launch_target_kind == "shell_app":
                label = "Shell 入口"
            elif effective_launch_target_kind == "protocol":
                label = "协议入口"
            else:
                label = "平台入口"
            return self._truncate_path(effective_launch_target_raw or label), effective_launch_target_raw or label
        if path_status == "registry_residual":
            return "注册表残留", ""
        if path_status == "driver_or_runtime":
            return "驱动/运行时", ""
        if path_status == "installer_bundle":
            return "安装器/卸载器", ""
        return "路径缺失", ""

    def _capability_summary(self, *, mode: str, permission_state: str, item: SoftwareRecord) -> str:
        display_state = self._display_permission_state(permission_state)
        if mode != "trusted":
            return "当前模式不执行软件动作。"
        if item.path_status == "driver_or_runtime":
            return "当前对象为驱动或运行时组件，默认只用于诊断，不进入软件治理主动作链。"
        if item.path_status == "installer_bundle":
            return "当前对象为安装器或卸载器，默认不进入软件治理主动作链。"
        if item.path_status == "registry_residual":
            return "当前对象更像注册表残留条目；已保留展示语义，但暂不能进入软件动作。"
        if item.candidate_kind == "weak_missing_path":
            return "当前对象缺少可用入口；可先补路径，再由用户手动调整权限。"
        if (
            self._effective_launch_target_raw(item)
            and self._effective_launch_target_kind(item) in self.ENTRY_LAUNCH_KINDS
            and not self._effective_target_path(item)
        ):
            return "当前对象为 AppX、Shell、平台或协议入口；执行结果会提示缺少信息或按入口类型处理。"
        if display_state == "allow":
            return "当前权限说明：允许定位、启动、关闭、卸载、迁移、更新操作。"
        if display_state == "once":
            return "当前权限说明：允许定位、启动、关闭操作；卸载、迁移、更新不可执行。"
        return "当前权限说明：所有软件动作禁用。"

    def _icon_text(self, item: SoftwareRecord) -> str:
        icon_kind = str(item.icon_kind or "").strip().lower()
        platform = str(item.platform or "").strip().lower()

        if icon_kind == "system":
            return "SYS"

        if icon_kind in {"steam_platform", "steam_cached_icon"} or platform == "steam":
            return "STEAM"

        if icon_kind == "epic_platform" or platform == "epic":
            return "EPIC"

        if icon_kind == "battlenet_platform" or platform == "battlenet":
            return "BNET"

        if icon_kind == "ea_platform" or platform == "ea":
            return "EA"

        if icon_kind in {"missing", "protocol"}:
            return "?"

        return "APP"

    def build_state(
        self,
        *,
        mode: str,
        filter_key: str,
        editable: bool,
        merged_apps: Iterable[SoftwareRecord],
        hidden_ids: Iterable[str] | None = None,
    ) -> Dict[str, Any]:
        hidden_ids = {str(item).strip() for item in (hidden_ids or []) if str(item).strip()}
        can_adjust = mode == "trusted" and editable
        rows: List[Dict[str, Any]] = []
        trusted_count = 0
        deny_count = 0
        discovered_count = 0

        for item in merged_apps:
            if item.hidden or item.app_id in hidden_ids:
                continue

            permission_state_raw = self._typed_permission_state(str(item.permission_state).strip().lower() or "unset")
            permission_state = self._display_permission_state(permission_state_raw)
            if not self._filter_matches(permission_state_raw, filter_key):
                continue

            discovered_count += 1
            if item.source == "confirmed":
                trusted_count += 1
            if permission_state == "deny":
                deny_count += 1

            effective_target_path = self._effective_target_path(item)
            effective_launch_target_kind = self._effective_launch_target_kind(item)
            effective_launch_target_raw = self._effective_launch_target_raw(item)
            effective_entry_path = self._effective_entry_path(item)
            effective_icon_source_path = self._effective_icon_source_path(item)

            status_badge, status_color = self._status_profile(item)
            path_short, path_full = self._path_display(item)
            can_sandbox_action = (
                mode == "trusted"
                and bool(permission_state in {"allow", "once"})
                and (
                    bool(effective_target_path)
                    or bool(effective_launch_target_raw and effective_launch_target_kind in self.ENTRY_LAUNCH_KINDS)
                )
            )
            if item.path_status in {"driver_or_runtime", "installer_bundle", "registry_residual"}:
                can_sandbox_action = False
            if item.candidate_kind == "weak_missing_path" and not effective_target_path and not effective_launch_target_raw:
                can_sandbox_action = False

            can_bind_path = (
                mode == "trusted"
                and effective_launch_target_kind == "missing"
                and not effective_target_path
                and not effective_launch_target_raw
            )
            title = str(item.title or item.app_id or "-").strip() or "-"
            capability_summary = self._capability_summary(mode=mode, permission_state=permission_state, item=item)
            tooltip = (
                f"软件名：{title}\n"
                f"完整路径：{path_full or '-'}\n"
                f"平台：{item.platform or '-'}\n"
                f"原始入口：{effective_launch_target_raw or '-'}\n"
                f"当前权限：{self._permission_label(permission_state)}\n"
                f"当前状态：{status_badge}\n"
                f"当前模式能力：{capability_summary}\n"
                f"可见性说明：{item.visibility_reason or '-'}"
            )
            if item.manual_bound:
                tooltip += (
                    f"\n手动绑定：是"
                    f"\n绑定来源：{item.bind_source or '-'}"
                    f"\n绑定时间：{item.bound_at or '-'}"
                )

            row = SoftwareViewRow(
                app_id=item.app_id,
                title=title,
                target_path=item.target_path,
                effective_target_path=effective_target_path,
                path_short=path_short,
                permission_state=permission_state,
                permission_state_raw=str(permission_state_raw),
                effective_permission_state=permission_state,
                permission_label=self._permission_label(permission_state),
                permission_color=PERMISSION_COLORS[permission_state],
                status_badge=status_badge,
                status_color=status_color,
                tooltip=tooltip,
                status_tooltip=tooltip,
                icon_text=self._icon_text(item),
                icon_source_path=effective_icon_source_path,
                icon_kind=item.icon_kind,
                can_locate=can_sandbox_action,
                can_launch=can_sandbox_action,
                can_close=can_sandbox_action,
                can_uninstall=can_sandbox_action,
                can_move=can_sandbox_action,
                can_update=can_sandbox_action,
                can_clear=True,
                can_adjust=can_adjust and item.candidate_kind != "weak_missing_path",
                can_bind_path=can_bind_path,
                candidate_kind=item.candidate_kind,
                candidate_strength=item.candidate_strength,
                path_status=item.path_status,
                launch_target_kind=item.launch_target_kind,
                launch_target_raw=item.launch_target_raw,
                effective_launch_target_kind=effective_launch_target_kind,
                effective_launch_target_raw=effective_launch_target_raw,
                platform=item.platform,
                platform_object_id=item.platform_object_id,
                platform_object_type=item.platform_object_type,
                entry_path=effective_entry_path,
                install_dir=item.install_dir,
                route_confidence=item.route_confidence,
                manual_bound=item.manual_bound,
                canonical_app_id=item.canonical_app_id,
                risk_hint=item.risk_hint,
                sensitivity=item.sensitivity,
                allowed_actions=[
                    "app.locate",
                    "app.launch",
                    "app.close",
                    "app.bind_path",
                    "app.uninstall",
                    "app.move",
                    "app.update",
                ],
            )
            rows.append(row.to_dict())

        return {
            "mode": mode,
            "visible": mode == "trusted",
            "read_only": not can_adjust,
            "discovered_count": discovered_count,
            "trusted_count": trusted_count,
            "confirmed_count": trusted_count,
            "hidden_count": len(hidden_ids),
            "deny_count": deny_count,
            "rows": rows,
        }
