import os
import subprocess
import sys
from pathlib import Path

from tests.support.cli import run_agentplane_cli as run_cli
from tests.support.paths import REPO_ROOT


def run_app_delivery_cli(
    action: str,
    *,
    repo_root: Path,
    app: str,
    target: str = "prod0-main",
    extra_args: tuple[str, ...] = (),
    cwd: Path | None = None,
    env_overrides: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return run_cli(
        "app",
        "delivery",
        action,
        "--target",
        target,
        "--app",
        app,
        "--repo-root",
        str(repo_root),
        *extra_args,
        cwd=cwd,
        env_overrides=env_overrides,
    )
