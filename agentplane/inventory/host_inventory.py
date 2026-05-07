from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_host_inventory(repo_root: Path, target: str) -> dict[str, Any]:
    """Load inventory.json for a given target.

    This is the single source of truth for reading host inventory.
    All domain registries should use this instead of maintaining their own copies.
    """
    inventory_file = repo_root / "inventory" / "servers" / target / "inventory.json"
    if not inventory_file.is_file():
        raise ValueError(f"缺少 inventory 文件: {inventory_file}")
    payload = json.loads(inventory_file.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"inventory 顶层必须是对象: {inventory_file}")
    return payload
