from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from agentplane.runtime.host_profile import detect_host_profile
from agentplane.runtime.target_resolver import TargetResolver
from agentplane.ssh import resolve_ssh_target

PreflightStatus = Literal["ok", "warning", "failed"]


@dataclass(frozen=True)
class PreflightCheck:
    name: str
    status: PreflightStatus
    message: str


@dataclass(frozen=True)
class PreflightReport:
    target: str
    overall: PreflightStatus
    checks: list[PreflightCheck] = field(default_factory=list)

    def to_payload(self) -> dict[str, Any]:
        return {
            "target": self.target,
            "overall": self.overall,
            "checks": [
                {"name": c.name, "status": c.status, "message": c.message}
                for c in self.checks
            ],
        }


def _check_wsl_available() -> PreflightCheck:
    try:
        result = subprocess.run(
            ["wsl.exe", "-e", "echo", "ok"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        if result.returncode == 0 and "ok" in result.stdout:
            return PreflightCheck("wsl-available", "ok", "WSL is running and responsive")
        return PreflightCheck(
            "wsl-available", "failed",
            f"WSL check failed: {result.stderr.strip() or 'unknown error'}",
        )
    except FileNotFoundError:
        return PreflightCheck("wsl-available", "failed", "wsl.exe not found")
    except subprocess.TimeoutExpired:
        return PreflightCheck("wsl-available", "failed", "WSL check timed out")
    except OSError as exc:
        return PreflightCheck("wsl-available", "failed", f"WSL check error: {exc}")


def _check_lima_available() -> PreflightCheck:
    try:
        result = subprocess.run(
            ["limactl", "list", "--json"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        if result.returncode == 0:
            return PreflightCheck("lima-available", "ok", "Lima is installed and responsive")
        return PreflightCheck(
            "lima-available", "failed",
            f"Lima check failed: {result.stderr.strip()}",
        )
    except FileNotFoundError:
        return PreflightCheck("lima-available", "failed", "limactl not found")
    except subprocess.TimeoutExpired:
        return PreflightCheck("lima-available", "failed", "Lima check timed out")
    except OSError as exc:
        return PreflightCheck("lima-available", "failed", f"Lima check error: {exc}")


def _check_ssh_config_exists(ssh_target) -> PreflightCheck:
    if ssh_target.config_path.exists():
        return PreflightCheck("ssh-config", "ok", f"SSH config found at {ssh_target.config_path}")
    return PreflightCheck("ssh-config", "failed", f"SSH config not found: {ssh_target.config_path}")


def _check_ssh_key_permissions(ssh_target) -> PreflightCheck:
    try:
        config_text = ssh_target.config_path.read_text(encoding="utf-8")
    except OSError as exc:
        return PreflightCheck("ssh-key", "warning", f"Could not read SSH config: {exc}")

    lines = config_text.splitlines()
    current_host: str | None = None
    identity_file: str | None = None
    for line in lines:
        stripped = line.strip()
        if stripped.lower().startswith("host "):
            current_host = stripped.split(None, 1)[1].strip()
        elif stripped.lower().startswith("identityfile "):
            candidate = stripped.split(None, 1)[1].strip()
            if current_host == ssh_target.alias:
                identity_file = candidate
                break
            if identity_file is None:
                identity_file = candidate

    if not identity_file:
        return PreflightCheck("ssh-key", "warning", "No IdentityFile found in SSH config")

    identity_file = os.path.expanduser(identity_file)
    key_path = Path(identity_file)
    if not key_path.exists():
        return PreflightCheck("ssh-key", "failed", f"SSH private key not found: {key_path}")

    mode = key_path.stat().st_mode
    if mode & 0o077:
        return PreflightCheck(
            "ssh-key", "warning",
            f"SSH private key permissions are too open ({oct(mode & 0o777)}), should be 0o600",
        )
    return PreflightCheck("ssh-key", "ok", f"SSH private key exists with correct permissions: {key_path}")


def _check_ssh_reachable(ssh_target) -> PreflightCheck:
    argv = ssh_target.local_ssh_args_for_argv(["echo", "ok"])
    try:
        result = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        if result.returncode == 0 and "ok" in result.stdout:
            return PreflightCheck(
                "ssh-reachable", "ok",
                f"SSH to {ssh_target.connection_target} is reachable",
            )
        stderr = result.stderr.lower()
        if "permission denied" in stderr or "authentication" in stderr:
            return PreflightCheck(
                "ssh-reachable", "failed",
                f"SSH authentication failed: {result.stderr.strip()}",
            )
        if any(t in stderr for t in ("connection refused", "could not resolve", "no route", "network is unreachable")):
            return PreflightCheck(
                "ssh-reachable", "failed",
                f"SSH network failure: {result.stderr.strip()}",
            )
        return PreflightCheck(
            "ssh-reachable", "failed",
            f"SSH check failed (exit {result.returncode}): {result.stderr.strip() or result.stdout.strip()}",
        )
    except FileNotFoundError:
        return PreflightCheck("ssh-reachable", "failed", "ssh executable not found")
    except subprocess.TimeoutExpired:
        return PreflightCheck("ssh-reachable", "failed", "SSH check timed out after 15s")
    except OSError as exc:
        return PreflightCheck("ssh-reachable", "failed", f"SSH check error: {exc}")


def execute_remote_preflight(repo_root: Path, target: str) -> PreflightReport:
    repo_root = Path(repo_root).resolve()
    host_profile = detect_host_profile()
    target_resolution = TargetResolver(host_profile).resolve(target)

    checks: list[PreflightCheck] = []

    if target_resolution.is_local:
        if target_resolution.execution_backend == "windows-wsl":
            checks.append(_check_wsl_available())
        elif target_resolution.execution_backend == "linux-native":
            checks.append(PreflightCheck("local-shell", "ok", "Running inside Linux/WSL, no wrapper needed"))
        elif target_resolution.execution_backend == "macos-lima":
            checks.append(_check_lima_available())
    else:
        ssh_target = resolve_ssh_target(repo_root, target_resolution.ssh_alias or target)
        checks.append(_check_ssh_config_exists(ssh_target))
        checks.append(_check_ssh_key_permissions(ssh_target))
        checks.append(_check_ssh_reachable(ssh_target))

    if any(c.status == "failed" for c in checks):
        overall: PreflightStatus = "failed"
    elif any(c.status == "warning" for c in checks):
        overall = "warning"
    else:
        overall = "ok"

    return PreflightReport(target=target, overall=overall, checks=checks)
