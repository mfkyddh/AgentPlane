from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Literal, Mapping

from agentplane.runtime.backends import build_backend_runner
from agentplane.runtime.execution import CommandRunner, ExecutionBindings, ExecutionPlan
from agentplane.runtime.platform import HostPlatform, detect_host_platform
from agentplane.runtime.redaction import redact_execution_payload

LIVE_GATE_PROFILES: tuple[str, ...] = ("wsl", "prod0-main", "prod2-main")
DEFAULT_APP = "sub2api"
DEFAULT_WSL_PROJECTION_PROFILE = "wsl-fixture"
LiveGateExecution = Literal["infra", "linux-backend"]


@dataclass(frozen=True)
class LiveGateStep:
    key: str
    argv: tuple[str, ...]
    capabilities: tuple[str, ...]
    cwd: Path
    execution: LiveGateExecution = "infra"
    timeout: int = 300

    def to_payload(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "argv": list(self.argv),
            "cwd": str(self.cwd),
            "capabilities": list(self.capabilities),
            "execution": self.execution,
            "timeout": self.timeout,
        }


def _cli(repo_root: Path, *args: str) -> tuple[str, ...]:
    return ("uv", "run", "python", "-m", "agentplane.cli", *args, "--repo-root", str(repo_root))


def _remote_cli(repo_root: Path, target: str, *remote_args: str) -> tuple[str, ...]:
    return (
        "uv",
        "run",
        "python",
        "-m",
        "agentplane.cli",
        "infra",
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
            execution="linux-backend",
        ),
        LiveGateStep(
            key="toolchain.docker",
            argv=("docker", "version", "--format", "{{.Server.Version}}"),
            cwd=repo_root,
            capabilities=("docker",),
            execution="linux-backend",
        ),
        LiveGateStep(
            key="toolchain.docker-compose",
            argv=("docker", "compose", "version"),
            cwd=repo_root,
            capabilities=("docker",),
            execution="linux-backend",
        ),
        LiveGateStep(
            key="host.inventory",
            argv=_cli(repo_root, "infra", "inventory", "wsl"),
            cwd=repo_root,
            capabilities=("uv",),
        ),
        LiveGateStep(
            key="host.audit",
            argv=_cli(repo_root, "infra", "audit", "wsl"),
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
            key="projection.runtime-env.verify",
            argv=_cli(repo_root, "projection", "runtime-env", "verify", "--target", "wsl", "--app", app),
            cwd=repo_root,
            capabilities=("uv",),
        ),
        LiveGateStep(
            key="service.verify",
            argv=_cli(repo_root, "service", "verify", "--target", "wsl", "--name", app),
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
            key="projection.runtime-env.verify",
            argv=_cli(repo_root, "projection", "runtime-env", "verify", "--target", target, "--app", app),
            cwd=repo_root,
            capabilities=("uv", "ssh"),
        ),
        LiveGateStep(
            key="service.verify",
            argv=_cli(repo_root, "service", "verify", "--target", target, "--name", app),
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


def assert_live_gate_checkout(
    repo_root: Path | str,
    *,
    profile: str | None = None,
    host_platform: HostPlatform | None = None,
) -> None:
    facts = host_platform or detect_host_platform()
    root = Path(repo_root)
    if not root.is_dir():
        raise ValueError(f"live integration gate repo root does not exist: {root}")
    if profile == "wsl":
        if facts.os_name == "windows" and not facts.is_wsl:
            if not facts.has_wsl:
                raise ValueError("wsl live integration gate on Windows requires WSL.")
            return
        if facts.os_name == "linux" and facts.is_wsl:
            return
        raise ValueError("wsl live integration gate must run from Windows with WSL or inside WSL.")


def _run_step_with_backend(step: LiveGateStep) -> dict[str, Any]:
    plan = ExecutionPlan(
        backend_type="windows-wsl",
        cwd_ref="repo_root",
        argv=step.argv,
        env_refs=(),
        input_refs=(),
        expected_outputs=(),
        capabilities=step.capabilities,
        timeout=step.timeout,
    )
    result = build_backend_runner().execute(
        plan,
        bindings=ExecutionBindings(cwd_values={"repo_root": step.cwd}),
    )
    payload = {
        "key": step.key,
        "execution": step.execution,
        **result.to_payload(),
    }
    return redact_execution_payload(payload)


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
        "required_checkout": "single-checkout",
        "checkout_policy": "clone once; Windows hosts keep formal CLI on the host and route Linux-only toolchain steps through the WSL bridge",
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
    facts = host_platform or detect_host_platform()
    assert_live_gate_checkout(root, profile=profile, host_platform=facts)

    command_runner = runner or CommandRunner()
    results: list[dict[str, Any]] = []
    for step in build_live_gate_steps(root, profile=profile, app=app, projection_profile=projection_profile):
        if (
            runner is None
            and profile == "wsl"
            and facts.os_name == "windows"
            and not facts.is_wsl
            and step.execution == "linux-backend"
        ):
            result = _run_step_with_backend(step)
        else:
            completed = command_runner.run(step.argv, cwd=step.cwd, timeout=step.timeout)
            result = {
                "key": step.key,
                "argv": list(step.argv),
                "cwd": str(step.cwd),
                "execution": step.execution,
                "returncode": completed.returncode,
                "stdout": completed.stdout,
                "stderr": completed.stderr,
                "ok": completed.returncode == 0,
            }
            result = redact_execution_payload(result)
        results.append(result)
        if not result["ok"]:
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
