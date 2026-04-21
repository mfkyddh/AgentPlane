from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agentplane.runtime.wsl_bridge import wsl_unc_to_posix


def load_inventory(repo_root: Path, target: str) -> tuple[Path, dict[str, Any]]:
    inventory_file = repo_root / "inventory" / "servers" / target / "inventory.json"
    if not inventory_file.exists():
        return inventory_file, {}
    payload = json.loads(inventory_file.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"inventory 顶层必须是对象: {inventory_file}")
    return inventory_file, payload


def nested_get(payload: dict[str, Any], dotted_key: str) -> Any:
    current: Any = payload
    for part in dotted_key.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def render_domain_path(path: Path | str) -> str:
    wsl_posix = wsl_unc_to_posix(path)
    if wsl_posix is not None:
        return wsl_posix.as_posix()
    if isinstance(path, Path):
        rendered = str(path)
    else:
        rendered = path
    return rendered.replace("\\", "/") if rendered.startswith("/") else rendered
