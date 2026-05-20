from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict

from services.desktop.desktop_models import ConnectorTestResult, RouteResult


class ConnectorBase(ABC):
    connector_id: str = "base"
    display_name: str = "Base Connector"
    capabilities: list[str] = []

    def available(self) -> bool:
        return True

    def connect(self) -> bool:
        return True

    def describe_capabilities(self) -> Dict[str, Any]:
        return {
            "connector_id": self.connector_id,
            "display_name": self.display_name,
            "capabilities": list(self.capabilities),
            "execute_deprecated": True,
        }

    def health_check(self) -> ConnectorTestResult:
        return self.test()

    @abstractmethod
    def test(self) -> ConnectorTestResult:
        raise NotImplementedError

    @abstractmethod
    def execute(self, action: str, payload: Dict[str, Any]) -> RouteResult:
        raise NotImplementedError
