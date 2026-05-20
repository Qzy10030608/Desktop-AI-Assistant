from __future__ import annotations

import os
from typing import Any, Dict, Optional

from services.desktop.desktop_models import ConnectorTestResult, RouteResult
from services.desktop.tianting.connector_base import ConnectorBase


class WindowsShellConnector(ConnectorBase):
    connector_id = "windows_shell"
    display_name = "Windows Shell"
    capabilities = ["probe", "describe", "health_check"]

    def test(self) -> ConnectorTestResult:
        return ConnectorTestResult(
            connector_id=self.connector_id,
            ok=(os.name == "nt"),
            stage="availability",
            message="Windows Shell 可用" if os.name == "nt" else "当前不是 Windows 环境",
            capabilities=self.capabilities,
        )

    def execute(self, action: str, payload: Dict[str, Any]) -> RouteResult:
        return RouteResult(
            False,
            action,
            "Tianting execute is deprecated. Use the Qin review/router/executor pipeline for all desktop actions.",
            payload={
                "blocked": True,
                "deprecated": True,
                "must_use_qin_pipeline": True,
                "requested_action": action,
                "target_path": str(payload.get("target_path", "")).strip(),
            },
        )


class ConnectorHub:
    def __init__(self) -> None:
        self._connectors: Dict[str, ConnectorBase] = {}
        self.register(WindowsShellConnector())

    def register(self, connector: ConnectorBase) -> None:
        self._connectors[connector.connector_id] = connector

    def get(self, connector_id: str) -> Optional[ConnectorBase]:
        return self._connectors.get(connector_id)

    def list_ids(self) -> list[str]:
        return list(self._connectors.keys())

    def describe_all(self) -> list[Dict[str, Any]]:
        return [connector.describe_capabilities() for connector in self._connectors.values()]
