from __future__ import annotations

from typing import Any


class TestMatrixEvaluator:
    """Evaluate simple sandbox/vm/host matrix results without executing tasks."""

    def evaluate(self, results: list[dict[str, Any]]) -> dict[str, Any]:
        rows = [item for item in results if isinstance(item, dict)]
        failures = [item for item in rows if not bool(item.get("passed", item.get("ok", False)))]
        return {
            "total": len(rows),
            "passed": len(rows) - len(failures),
            "failed": len(failures),
            "failures": failures,
            "overall_status": "ok" if not failures else "warning",
        }
