from __future__ import annotations

from pathlib import Path


def contract_app_root(contract_path: Path) -> Path:
    resolved = contract_path.resolve()
    if resolved.parent.name in {"op", "agentplane"} and resolved.parent.parent.name == "deploy":
        return resolved.parents[2]
    return resolved.parent


def contract_validation_target(target: str) -> str:
    return target
