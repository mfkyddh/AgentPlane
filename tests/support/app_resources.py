from __future__ import annotations

from pathlib import Path


def resource_relative(target: str, app: str, resource: str) -> str:
    return f"secrets/hosts/{target}/apps/{app}/resources/{resource}.env"


def resource_root(repo_root: Path, target: str, app: str) -> Path:
    return repo_root / "secrets" / "hosts" / target / "apps" / app / "resources"
