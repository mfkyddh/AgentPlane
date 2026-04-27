"""agentplane test - run tests with sensible defaults.

Provides shortcut commands that map to the right pytest invocation
depending on the test tier.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

DEFAULT_EXCLUDES = (
    "live_gate",
    "integration_wsl",
    "integration_remote",
    "external_app",
    "docker_required",
    "ssh_required",
)


def _marker_expr(include: str) -> str:
    excludes = " and ".join(f"not {marker}" for marker in DEFAULT_EXCLUDES)
    return f"({include}) and {excludes}"


def add_test_parser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser("test", help="Run tests with sensible defaults")
    parser.add_argument(
        "tier",
        nargs="?",
        default="fast",
        choices=["fast", "full", "e2e", "smoke", "unit", "integration"],
        help="Test tier: fast (unit+integration), full (all), e2e, smoke, unit, integration (default: fast)",
    )
    parser.add_argument(
        "-n",
        "--workers",
        type=int,
        default=None,
        help="Number of parallel workers (default: auto for unit/integration, 4 for e2e)",
    )
    parser.add_argument(
        "--tb",
        default="short",
        choices=["short", "long", "line", "native"],
        help="Traceback style (default: short)",
    )
    parser.set_defaults(func=handle_test_command)


def _repo_root() -> Path:
    """Find repo root by walking up from this file."""
    current = Path(__file__).resolve().parent
    for _ in range(5):
        if (current / "pyproject.toml").is_file():
            return current
        current = current.parent
    raise FileNotFoundError("Cannot locate repo root (no pyproject.toml found)")


def handle_test_command(args: argparse.Namespace) -> int:
    repo_root = _repo_root()
    tier = args.tier
    workers = args.workers

    # Build the pytest command
    cmd = [sys.executable, "-m", "pytest", "-q", f"--tb={args.tb}"]

    if tier == "unit":
        cmd.extend(["-m", _marker_expr("unit")])
        n = workers or 0  # 0 means auto in xdist
        if n > 0:
            cmd.extend(["-n", str(n)])
        else:
            cmd.extend(["-n", "auto"])

    elif tier == "integration":
        cmd.extend(["-m", _marker_expr("integration")])
        n = workers or 0
        if n > 0:
            cmd.extend(["-n", str(n)])
        else:
            cmd.extend(["-n", "auto", "--dist", "loadfile"])

    elif tier == "fast":
        cmd.extend(["-m", _marker_expr("unit or integration")])
        n = workers or 0
        if n > 0:
            cmd.extend(["-n", str(n)])
        else:
            cmd.extend(["-n", "auto", "--dist", "loadfile"])

    elif tier == "e2e":
        cmd.extend(["-m", _marker_expr("e2e")])
        n = workers or 4
        cmd.extend(["-n", str(n)])

    elif tier == "smoke":
        cmd.extend(["-m", _marker_expr("smoke")])
        n = workers or 4
        cmd.extend(["-n", str(n)])

    elif tier == "full":
        # Run unit+integration first (fast, highly parallel), then e2e (slower, limited parallel)
        # This is a compound command; we run two pytest invocations.
        fast_cmd = [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            f"--tb={args.tb}",
            "-m",
            _marker_expr("unit or integration"),
            "-n",
            "auto",
            "--dist",
            "loadfile",
        ]
        e2e_cmd = [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            f"--tb={args.tb}",
            "-m",
            _marker_expr("e2e"),
            "-n",
            str(workers or 4),
        ]

        print("Running unit + integration tests...", file=sys.stderr)
        fast_result = subprocess.run(fast_cmd, cwd=str(repo_root))
        if fast_result.returncode != 0:
            print("Unit/integration tests failed; skipping e2e.", file=sys.stderr)
            return fast_result.returncode

        print("Running e2e tests...", file=sys.stderr)
        e2e_result = subprocess.run(e2e_cmd, cwd=str(repo_root))
        return e2e_result.returncode

    result = subprocess.run(cmd, cwd=str(repo_root))
    return result.returncode
