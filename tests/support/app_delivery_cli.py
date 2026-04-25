import os
import subprocess
import sys
from pathlib import Path

from tests.support.paths import REPO_ROOT


def run_cli(*args: str, cwd: Path | None = None, env_overrides: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    # Keep subprocess cwd aligned with an explicit --repo-root to avoid "false green"
    # when an implementation mistakenly infers repo-root from cwd.
    env = None
    if cwd is None:
        repo_root: Path | None = None
        for idx, token in enumerate(args):
            if token == "--repo-root" and idx + 1 < len(args):
                repo_root = Path(args[idx + 1])
                break
            if token.startswith("--repo-root="):
                repo_root = Path(token.split("=", 1)[1])
                break
        if repo_root is not None:
            cwd = repo_root
            env = os.environ.copy()
            existing = env.get("PYTHONPATH", "")
            repo_path = str(REPO_ROOT)
            env["PYTHONPATH"] = repo_path if not existing else f"{repo_path}{os.pathsep}{existing}"
    if env_overrides:
        env = dict(env or os.environ.copy())
        env.update(env_overrides)
        if "FAKE_CMD_LOG" in env_overrides:
            env.setdefault("AGENTPLANE_DISABLE_WSL_SSH", "1")
    return subprocess.run(
        [sys.executable, "-m", "agentplane.cli", *args],
        cwd=cwd or REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


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
