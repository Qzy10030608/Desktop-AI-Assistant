from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Iterable, List


class SoftwareSourceBase(ABC):
    source_id: str = "base"

    @abstractmethod
    def collect(self, *, existing_app_ids: Iterable[str] | None = None, app_map: Dict[str, Any] | None = None) -> List[Dict[str, Any]]:
        raise NotImplementedError

    def health_check(self) -> Dict[str, Any]:
        return {
            "source_id": self.source_id,
            "ok": True,
            "message": "source available",
        }
