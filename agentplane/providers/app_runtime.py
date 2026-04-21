from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module
from typing import Any


@dataclass(frozen=True)
class AppRuntimeGateway:
    """Adapter boundary for legacy app runtime helpers."""

    module_name: str = "agentplane.cli.apps"

    def __getattr__(self, name: str) -> Any:
        return getattr(import_module(self.module_name), name)


def default_app_runtime_gateway() -> AppRuntimeGateway:
    return AppRuntimeGateway()
