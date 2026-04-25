from __future__ import annotations

from pathlib import Path
from typing import Any

from agentplane.scripts.onepanel.public_ingress import (
    ensure_public_ingress,
    plan_public_ingress,
    verify_public_ingress,
)


def plan_onepanel_public_ingress(target: str, config_file: Path, cloudflare_env_file: Path) -> dict[str, Any]:
    return plan_public_ingress(target, config_file, cloudflare_env_file)


def ensure_onepanel_public_ingress(target: str, config_file: Path, cloudflare_env_file: Path) -> dict[str, Any]:
    return ensure_public_ingress(target, config_file, cloudflare_env_file)


def verify_onepanel_public_ingress(target: str, config_file: Path, cloudflare_env_file: Path) -> dict[str, Any]:
    return verify_public_ingress(target, config_file, cloudflare_env_file)
