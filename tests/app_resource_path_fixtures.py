from __future__ import annotations

from pathlib import Path


def resource_relative(target: str, app: str, kind: str) -> str:
    return f"secrets/hosts/{target}/apps/{app}/resources/{kind}.env"


def resource_root(root: Path, target: str, app: str) -> Path:
    return root / "secrets" / "hosts" / target / "apps" / app / "resources"
