from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from tests.support.paths import REPO_ROOT


def repo_pythonpath_env(env_overrides: dict[str, str] | None = None) -> dict[str, str]:
    env = os.environ.copy()
    existing = env.get("PYTHONPATH", "")
    repo_path = str(REPO_ROOT)
    env["PYTHONPATH"] = repo_path if not existing else f"{repo_path}{os.pathsep}{existing}"
    if env_overrides:
        env.update(env_overrides)
    return env


def repo_root_from_args(args: tuple[str, ...]) -> Path | None:
    for idx, token in enumerate(args):
        if token == "--repo-root" and idx + 1 < len(args):
            return Path(args[idx + 1])
        if token.startswith("--repo-root="):
            return Path(token.split("=", 1)[1])
    return None


def run_agentplane_cli(
    *args: str,
    cwd: Path | None = None,
    env_overrides: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    env = None
    if cwd is None:
        parsed = repo_root_from_args(args)
        if parsed is not None and parsed.is_dir():
            cwd = parsed
            env = repo_pythonpath_env(env_overrides)
    elif env_overrides:
        env = repo_pythonpath_env(env_overrides)
    if env_overrides and "FAKE_CMD_LOG" in env_overrides:
        if env is None:
            env = os.environ.copy()
        env.setdefault("AGENTPLANE_DISABLE_WSL_SSH", "1")
    return subprocess.run(
        [sys.executable, "-m", "agentplane.cli", *args],
        cwd=cwd or REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

