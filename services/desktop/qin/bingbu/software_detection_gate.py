from __future__ import annotations

from typing import Any, Dict

from services.desktop.qin.bingbu.category_classifier import CategoryClassifier
from services.desktop.qin.bingbu.object_visibility_policy import ObjectVisibilityPolicy
from services.desktop.qin.bingbu.secondary_route_guard import SecondaryRouteGuard
from services.desktop.software_models import SoftwareDetectionDecision
from services.desktop.tianting.providers.icon_source_provider import IconSourceProvider
from services.desktop.tianting.providers.protocol_parser import ProtocolParser


class SoftwareDetectionGate:
    def __init__(self) -> None:
        self.protocol_parser = ProtocolParser()
        self.icon_source_provider = IconSourceProvider()
        self.category_classifier = CategoryClassifier()
        self.secondary_route_guard = SecondaryRouteGuard()
        self.visibility_policy = ObjectVisibilityPolicy()

    def detect(self, item: Dict[str, Any]) -> SoftwareDetectionDecision:
        title = str(item.get("title", item.get("app_id", ""))).strip()
        target_path = str(item.get("target_path", "")).strip()
        entry_path = str(item.get("entry_path", "")).strip()
        discover_source = str(item.get("discover_source", "unknown")).strip().lower() or "unknown"
        launch_target_kind = str(item.get("launch_target_kind", "missing")).strip().lower() or "missing"
        launch_target_raw = str(item.get("launch_target_raw", "")).strip()
        platform = str(item.get("platform", "unknown")).strip() or "unknown"
        platform_object_type = str(item.get("platform_object_type", "")).strip()
        platform_object_id = str(item.get("platform_object_id", "")).strip()

        if launch_target_raw:
            parsed = self.protocol_parser.parse(launch_target_raw)

            parsed_kind = str(parsed.get("launch_target_kind", "")).strip().lower()
            parsed_platform = str(parsed.get("platform", "")).strip()
            parsed_object_type = str(parsed.get("platform_object_type", "")).strip()
            parsed_object_id = str(parsed.get("platform_object_id", "")).strip()

            if parsed_kind and parsed_kind != "missing":
                launch_target_kind = parsed_kind
            if parsed_platform and parsed_platform != "unknown":
                platform = parsed_platform
            if parsed_object_type:
                platform_object_type = parsed_object_type
            if parsed_object_id:
                platform_object_id = parsed_object_id

            raw_lower = launch_target_raw.lower()
            if raw_lower.startswith("steam://rungameid/"):
                launch_target_kind = "protocol"
                if not platform or platform == "unknown":
                    platform = "steam"
                if not platform_object_type:
                    platform_object_type = "game"
                if not platform_object_id:
                    suffix = raw_lower.removeprefix("steam://rungameid/")
                    platform_object_id = suffix.split("/")[0].strip()
        category, candidate_kind = self.category_classifier.classify(
            title=title,
            target_path=target_path,
            launch_target_kind=launch_target_kind,
            launch_target_raw=launch_target_raw,
        )
        protected_sources = {
            "app_map",
            "app_map_fallback",
            "system_app_seed",
            "appx_installed_apps",
        }
        if (
            discover_source in protected_sources
            and category not in {"admin_tool", "installer_bundle", "driver", "runtime_env", "system_core"}
            and candidate_kind not in {"installer_bundle", "driver_or_runtime"}
        ):
            if discover_source in {"system_app_seed", "appx_installed_apps"}:
                category = "system_app"
                candidate_kind = "system_app"
        if discover_source == "system_app_seed" and platform_object_id.lower() in {"explorer", "powershell"}:
            category = "system_app"
            candidate_kind = "system_app"
        visibility, visibility_reason = self.visibility_policy.decide(
            category=category,
            candidate_kind=candidate_kind,
            launch_target_kind=launch_target_kind,
        )
        actionability = self.visibility_policy.actionability(
            candidate_kind=candidate_kind,
            launch_target_kind=launch_target_kind,
            target_path=target_path,
        )
        secondary = self.secondary_route_guard.analyze(
            {
                "launch_target_kind": launch_target_kind,
                "launch_target_raw": launch_target_raw,
                "candidate_kind": candidate_kind,
                "platform": platform,
                "route_confidence": item.get("route_confidence", ""),
            }
        )
        icon = self.icon_source_provider.describe(
            {
                "title": title,
                "target_path": target_path,
                "entry_path": entry_path or target_path,
                "launch_target_kind": launch_target_kind,
                "launch_target_raw": launch_target_raw,
                "category": category,
                "platform": platform,
                "platform_object_type": platform_object_type,
                "platform_object_id": platform_object_id,
                "install_dir": str(item.get("install_dir", "")).strip(),
                "icon_source_path": str(item.get("icon_source_path", "")).strip(),
            }
        )

        has_path = bool(target_path)
        has_secondary = bool(secondary["is_secondary_route"] and launch_target_raw)
        if has_path:
            path_status = "resolved"
        elif launch_target_kind in {"appx", "shell_app"} and launch_target_raw:
            path_status = "appx_entry"
        elif has_secondary:
            path_status = "platform_entry"
        elif candidate_kind == "installer_bundle" or category == "installer_bundle":
            path_status = "installer_bundle"
        elif candidate_kind == "driver_or_runtime" or category in {"admin_tool", "runtime_env", "driver", "system_core"}:
            path_status = "driver_or_runtime"
        elif discover_source == "uninstall_registry":
            path_status = "registry_residual"
        else:
            path_status = "missing"

        candidate_strength = "strong" if has_path or has_secondary or path_status == "appx_entry" else "weak"
        risk_tags = []
        if category in {"admin_tool", "installer_bundle", "driver", "runtime_env", "system_core"}:
            risk_tags.append(category)
        if secondary["is_secondary_route"]:
            risk_tags.append("secondary_route")

        return SoftwareDetectionDecision(
            category=category,
            candidate_kind=candidate_kind,
            visibility=visibility,
            actionability=actionability,
            is_secondary_route=bool(secondary["is_secondary_route"]),
            route_confidence=str(secondary["route_confidence"]),
            risk_tags=risk_tags,
            visibility_reason=visibility_reason,
            launch_target_kind=launch_target_kind,
            launch_target_raw=launch_target_raw,
            platform=platform,
            platform_object_type=platform_object_type,
            platform_object_id=platform_object_id,
            install_dir=str(item.get("install_dir", "")).strip(),
            entry_path=entry_path or target_path,
            icon_source_path=str(icon.get("icon_source_path", "")).strip(),
            icon_kind=str(icon.get("icon_kind", "missing")).strip() or "missing",
            path_status=path_status,
            candidate_strength=candidate_strength,
        )
