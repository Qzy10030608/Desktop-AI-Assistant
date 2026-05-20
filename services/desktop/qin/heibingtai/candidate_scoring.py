from __future__ import annotations


def score_close_candidate(candidate: dict) -> int:
    """Placeholder for future selected_candidates support."""
    if not isinstance(candidate, dict):
        return 0
    score = 0
    if candidate.get("path_matched"):
        score += 100
    if candidate.get("registered"):
        score += 50
    return score
