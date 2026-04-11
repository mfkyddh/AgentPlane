from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class AppResourceDefinition:
    app: str
    owner_app: str
    resource_kinds: tuple[str, ...]
    ledger_status: dict[str, Any] = field(default_factory=dict)
    resources: dict[str, dict[str, Any]] = field(default_factory=dict)
    secret_files: tuple[str, ...] = ()
