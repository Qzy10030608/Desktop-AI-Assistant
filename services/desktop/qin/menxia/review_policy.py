from __future__ import annotations

from typing import Any, Dict

DEFAULT_REVIEW_MODE = "disabled"

REVIEW_POLICIES: Dict[str, Dict[str, Any]] = {
    "disabled": {
        "mode": "disabled",
        "scope": "deny",
        "label": "未启用",
        "reason": "桌面连接未启用，默认拒绝全部桌面连接动作。",
        "show_roots": False,
        "show_apps": False,
        "roots_read_only": True,
        "allow_readonly_actions": False,
        "allow_app_adjust": False,
        "allow_candidate_rescan": False,
        "allow_full_desktop": False,
    },
    "restricted": {
        "mode": "restricted",
        "scope": "readonly",
        "label": "受限模式",
        "reason": "仅允许只读桌面连接能力，不显示软件白名单区。",
        "show_roots": True,
        "show_apps": False,
        "roots_read_only": True,
        "allow_readonly_actions": True,
        "allow_app_adjust": False,
        "allow_candidate_rescan": False,
        "allow_full_desktop": False,
    },
    "trusted": {
        "mode": "trusted",
        "scope": "full",
        "label": "信任模式",
        "reason": "允许完整桌面白名单能力，显示根目录与软件白名单区。",
        "show_roots": True,
        "show_apps": True,
        "roots_read_only": False,
        "allow_readonly_actions": True,
        "allow_app_adjust": True,
        "allow_candidate_rescan": True,
        "allow_full_desktop": True,
    },
    "test": {
        "mode": "test",
        "scope": "test",
        "label": "娴嬭瘯妯″紡",
        "reason": "Desktop test mode: sandbox/VM test exits only; Host execution remains disabled.",
        "show_roots": True,
        "show_apps": True,
        "roots_read_only": False,
        "allow_readonly_actions": True,
        "allow_app_adjust": True,
        "allow_candidate_rescan": True,
        "allow_full_desktop": False,
        "allow_test_backends": True,
    },
}


def get_review_policy(mode: str) -> Dict[str, Any]:
    key = str(mode or "").strip().lower() or DEFAULT_REVIEW_MODE
    policy = REVIEW_POLICIES.get(key, REVIEW_POLICIES[DEFAULT_REVIEW_MODE])
    return dict(policy)


def is_readonly_mode(mode: str) -> bool:
    return bool(get_review_policy(mode)["allow_readonly_actions"])


def is_trusted_mode(mode: str) -> bool:
    return bool(get_review_policy(mode)["allow_full_desktop"])
