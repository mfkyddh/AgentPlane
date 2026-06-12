from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _inventory_path(repo_root: Path, target: str) -> Path:
    return repo_root / "inventory" / "servers" / target / "inventory.json"


def _load_inventory(repo_root: Path, target: str) -> dict[str, Any]:
    inventory_file = _inventory_path(repo_root, target)
    if not inventory_file.exists():
        return {}
    try:
        return json.loads(inventory_file.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _host_status(inventory: dict[str, Any]) -> str:
    has_services = bool(inventory.get("services"))
    return "connected" if has_services else "unknown"
