from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

from agentplane.runtime.execution import CommandRunner
from agentplane.runtime.platform import HostPlatform, detect_host_platform


LIVE_GATE_PROFILES: tuple[str, ...] = ("wsl", "prod0-main", "prod2-main")
DEFAULT_APP = "sub2api"
DEFAULT_WSL_PROJECTION_PROFILE = "wsl-fixture"


@dataclass(frozen=True)
class LiveGateStep:
    key: str
    argv: tuple[str, ...]
    capabilities: tuple[str, ...]
    cwd: Path
    timeout: int = 300

    def to_payload(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "argv": list(self.argv),
            "cwd": str(self.cwd),
            "capabilities": list(self.capabilities),
            "timeout": self.timeout,
        }


def _is_windows_drive_path(path: Path | str) -> bool:
    rendered = str(path)
    return len(rendered) >= 2 and rendered[0].isalpha() and rendered[1] == ":"


def _is_wsl_unc_path(path: Path | str) -> bool:
    rendered = str(path).replace("/", "\\").lower()
    return rendered.startswith("\\\\wsl.localhost\\") or rendered.startswith("\\\\wsl$\\")


def _is_windows_mounted_wsl_path(path: Path | str) -> bool:
    rendered = str(path).replace("\\", "/").lower().rstrip("/")
    if not rendered.startswith("/mnt/"):
        return False
    parts = rendered.split("/")
    return len(parts) >= 3 and len(parts[2]) == 1 and parts[2].isalpha()


def _cli(repo_root: Path, *args: str) -> tuple[str, ...]:
    return ("uv", "run", "python", "-m", "agentplane.cli", *args, "--repo-root", str(repo_root))


def _remote_cli(repo_root: Path, target: str, *remote_args: str) -> tuple[str, ...]:
    return (
        "uv",
        "run",
        "python",
        "-m",
        "agentplane.cli",
        "host",
        "remote",
        "bash",
        target,
        "--repo-root",
        str(repo_root),
        "--",
        *remote_args,
    )


def _wsl_steps(repo_root: Path, *, app: str, projection_profile: str) -> list[LiveGateStep]:
    return [
        LiveGateStep(
            key="toolchain.uv",
            argv=("uv", "--version"),
            cwd=repo_root,
            capabilities=("uv",),
        ),
        LiveGateStep(
            key="toolchain.docker",
            argv=("docker", "version", "--format", "{{.Server.Version}}"),
            cwd=repo_root,
            capabilities=("docker",),
        ),
        LiveGateStep(
            key="toolchain.docker-compose",
            argv=("docker", "compose", "version"),
            cwd=repo_root,
            capabilities=("docker",),
        ),
        LiveGateStep(
            key="host.inventory",
            argv=_cli(repo_root, "host", "inventory", "wsl"),
            cwd=repo_root,
            capabilities=("uv",),
        ),
        LiveGateStep(
            key="host.audit",
            argv=_cli(repo_root, "host", "audit", "wsl"),
            cwd=repo_root,
            capabilities=("uv",),
        ),
        LiveGateStep(
            key="projection.verification",
            argv=_cli(
                repo_root,
                "projection",
                "verification",
                "run",
                "--target",
                "wsl",
                "--profile",
                projection_profile,
            ),
            cwd=repo_root,
            capabilities=("uv", "docker"),
        ),
        LiveGateStep(
            key="app.object.verify",
            argv=_cli(repo_root, "app", "object", "verify", "--target", "wsl", "--app", app),
            cwd=repo_root,
            capabilities=("uv",),
        ),
        LiveGateStep(
            key="app.delivery.verify",
            argv=(
                *_cli(repo_root, "app", "delivery", "verify", "--target", "wsl", "--app", app),
                "--execute",
            ),
            cwd=repo_root,
            capabilities=("uv", "docker"),
            timeout=600,
        ),
    ]


def _ssh_target_steps(repo_root: Path, *, target: str, app: str) -> list[LiveGateStep]:
    return [
        LiveGateStep(
            key="ssh.echo",
            argv=_remote_cli(repo_root, target, "printf", "agentplane-live-gate"),
            cwd=repo_root,
            capabilities=("uv", "ssh"),
        ),
        LiveGateStep(
            key="remote.docker",
            argv=_remote_cli(repo_root, target, "docker", "version", "--format", "{{.Server.Version}}"),
            cwd=repo_root,
            capabilities=("uv", "ssh", "docker"),
        ),
        LiveGateStep(
            key="app.object.verify",
            argv=_cli(repo_root, "app", "object", "verify", "--target", target, "--app", app),
            cwd=repo_root,
            capabilities=("uv", "ssh"),
        ),
        LiveGateStep(
            key="app.delivery.verify",
            argv=(
                *_cli(repo_root, "app", "delivery", "verify", "--target", target, "--app", app),
                "--execute",
            ),
            cwd=repo_root,
            capabilities=("uv", "ssh", "docker"),
            timeout=600,
        ),
    ]


def build_live_gate_steps(
    repo_root: Path | str,
    *,
    profile: str,
    app: str = DEFAULT_APP,
    projection_profile: str = DEFAULT_WSL_PROJECTION_PROFILE,
) -> list[LiveGateStep]:
    root = Path(repo_root)
    if profile == "wsl":
        return _wsl_steps(root, app=app, projection_profile=projection_profile)
    if profile in {"prod0-main", "prod2-main"}:
        return _ssh_target_steps(root, target=profile, app=app)
    raise ValueError(f"unsupported live gate profile: {profile}")


def assert_linux_filesystem_checkout(
    repo_root: Path | str,
    *,
    profile: str | None = None,
    host_platform: HostPlatform | None = None,
) -> None:
    facts = host_platform or detect_host_platform()
    root = Path(repo_root)
    if facts.os_name == "windows" and not facts.is_wsl:
        raise ValueError(
            "live integration gate must run from a Linux filesystem checkout. "
            "Windows may be the control-plane entry host, but live WSL/SSH/Docker gates execute from "
            "a separate Linux checkout such as <linux-repo-root>."
        )
    if _is_windows_drive_path(root) or _is_wsl_unc_path(root) or _is_windows_mounted_wsl_path(root):
        raise ValueError(
            f"live integration gate refuses non-native Linux checkout: {root}. "
            "Use an independent Linux filesystem checkout, not a Windows drive, WSL UNC path, or /mnt/<drive>/... path."
        )
    if profile == "wsl" and not facts.is_wsl:
        raise ValueError("wsl live integration gate must run inside the WSL Linux filesystem checkout.")


def plan_live_gate(
    repo_root: Path | str,
    *,
    profile: str,
    app: str = DEFAULT_APP,
    projection_profile: str = DEFAULT_WSL_PROJECTION_PROFILE,
) -> dict[str, Any]:
    root = Path(repo_root)
    steps = build_live_gate_steps(root, profile=profile, app=app, projection_profile=projection_profile)
    return {
        "ok": True,
        "profile": profile,
        "app": app,
        "projection_profile": projection_profile if profile == "wsl" else None,
        "repo_root": str(root),
        "live_only": True,
        "default_pytest": "excluded",
        "required_checkout": "linux-filesystem",
        "blocked_checkouts": ["windows-drive", "wsl-unc", "/mnt/<drive>"],
        "execute_requires": "--execute",
        "pytest_markers": ["live_gate", "integration_wsl", "integration_remote", "docker_required", "ssh_required"],
        "steps": [step.to_payload() for step in steps],
    }


def run_live_gate(
    repo_root: Path | str,
    *,
    profile: str,
    app: str = DEFAULT_APP,
    projection_profile: str = DEFAULT_WSL_PROJECTION_PROFILE,
    execute: bool = False,
    runner: CommandRunner | None = None,
    host_platform: HostPlatform | None = None,
) -> dict[str, Any]:
    payload = plan_live_gate(repo_root, profile=profile, app=app, projection_profile=projection_profile)
    payload["execute_requested"] = bool(execute)
    if not execute:
        payload["executed"] = False
        payload["results"] = []
        return payload

    root = Path(repo_root)
    assert_linux_filesystem_checkout(root, profile=profile, host_platform=host_platform)
    if not root.is_dir():
        raise ValueError(f"live integration gate repo root does not exist: {root}")

    command_runner = runner or CommandRunner()
    results: list[dict[str, Any]] = []
    for step in build_live_gate_steps(root, profile=profile, app=app, projection_profile=projection_profile):
        completed = command_runner.run(step.argv, cwd=step.cwd, timeout=step.timeout)
        result = {
            "key": step.key,
            "argv": list(step.argv),
            "cwd": str(step.cwd),
            "returncode": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
            "ok": completed.returncode == 0,
        }
        results.append(result)
        if completed.returncode != 0:
            break

    payload["executed"] = True
    payload["results"] = results
    payload["ok"] = all(bool(result["ok"]) for result in results) and len(results) == len(payload["steps"])
    return payload


def summarize_capabilities(steps: Iterable[Mapping[str, Any]]) -> list[str]:
    capabilities: set[str] = set()
    for step in steps:
        raw = step.get("capabilities", [])
        if isinstance(raw, list):
            capabilities.update(str(item) for item in raw)
    return sorted(capabilities)
