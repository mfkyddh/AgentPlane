from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ServiceDefinition:
    name: str
    runtime_kind: str
    control_plane: str
    supported_operations: tuple[str, ...]
    supported_targets: tuple[str, ...]
    inventory_key: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

