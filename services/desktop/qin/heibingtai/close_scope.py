from __future__ import annotations

CLOSE_SCOPE_CURRENT = "current"
CLOSE_SCOPE_REGISTERED = "registered"
CLOSE_SCOPE_MATCHING_PATH = "matching_path"
CLOSE_SCOPE_ALL_MATCHING_PATH = "all_matching_path"
CLOSE_SCOPE_SELECTED_CANDIDATES = "selected_candidates"

VALID_CLOSE_SCOPES = {
    CLOSE_SCOPE_CURRENT,
    CLOSE_SCOPE_REGISTERED,
    CLOSE_SCOPE_MATCHING_PATH,
    CLOSE_SCOPE_ALL_MATCHING_PATH,
    CLOSE_SCOPE_SELECTED_CANDIDATES,
}


def normalize_close_scope(value: str, *, default: str) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in VALID_CLOSE_SCOPES:
        return normalized
    return default
