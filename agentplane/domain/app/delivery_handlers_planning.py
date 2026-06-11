"""Deploy/verify/rollback step planning for delivery handlers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from agentplane.domain.app.delivery_handlers_shared import (
    _execute_steps,
    _render_execution_steps,
    _transition_step_to_execution,
)
from agentplane.domain.app.lifecycle import (
    plan_local_backend_step,
    plan_remote_copy_step,
    plan_remote_shell_step,
)
from agentplane.runtime.execution import CommandStep
from agentplane.runtime.host_profile import detect_host_profile


def _plan_wsl_deploy_steps(
    app_cli: Any,
    contract: dict[str, Any],
    *,
    repo_root: Path,
    target: str,
    image_ref: str | None,
) -> tuple[list[CommandStep], dict[str, Any]]:
    rendered = app_cli.render_runtime(contract, repo_root=repo_root, target=target, image_ref=image_ref)
    compose_path = Path(rendered["compose_file"])
    step = plan_local_backend_step(
        "deploy.wsl.compose-up",
        backend_type=detect_host_profile().linux_backend,
        cwd=repo_root,
        argv=("docker", "compose", "-f", str(compose_path), "up", "-d", "--pull", "never"),
        capabilities=("docker",),
        expected_outputs=("compose-up",),
    )
    return [step], {"container_name": rendered["container_name"], "compose_file": str(compose_path)}


def _plan_remote_deploy_steps(
    app_cli: Any,
    contract: dict[str, Any],
    *,
    repo_root: Path,
    target: str,
    image_ref: str | None,
    rendered_compose_path: Path | None = None,
) -> tuple[list[CommandStep], dict[str, Any]]:
    rendered = app_cli.render_runtime(contract, repo_root=repo_root, target=target, image_ref=image_ref)
    ssh_target = app_cli._target_ssh_target(repo_root, target)
    env_path = Path(app_cli._service_env_path(repo_root, str(contract["app_id"]), target))
    rollback_entry = contract["rollback"]["previous_control_plane"]
    remote_compose_name = app_cli._remote_compose_filename(target)
    remote_compose = f"/opt/agentplane/infra/compose/{contract['app_id']}/{remote_compose_name}"
    remote_env = app_cli._remote_env_path(str(contract["app_id"]), target)
    remote_env_dir = app_cli._remote_env_parent(remote_env)
    compose_source = rendered_compose_path or Path("<rendered-compose>")
    steps = [
        plan_remote_shell_step(
            "deploy.remote.remote-dirs",
            ssh_target=ssh_target,
            cwd=None,
            argv=("mkdir", "-p", f"/opt/agentplane/infra/compose/{contract['app_id']}", remote_env_dir),
            capabilities=("ssh",),
        ),
        plan_remote_copy_step(
            "deploy.remote.copy-compose",
            ssh_target=ssh_target,
            local_path=compose_source,
            remote_path=remote_compose,
            expected_outputs=("remote-compose",),
        ),
        plan_remote_copy_step(
            "deploy.remote.copy-env",
            ssh_target=ssh_target,
            local_path=env_path,
            remote_path=f"/tmp/{env_path.name}",
            expected_outputs=("remote-env-staging",),
        ),
        plan_remote_shell_step(
            "deploy.remote.install-env",
            ssh_target=ssh_target,
            cwd=None,
            argv=("sh",),
            shell_command=f"install -Dm600 /tmp/{env_path.name} {remote_env} && rm -f /tmp/{env_path.name}",
            capabilities=("ssh",),
        ),
    ]
    transition_step = app_cli._control_plane_transition_step(
        repo_root, target=target, rollback_entry=rollback_entry, operate="stop"
    )
    transition_execution = _transition_step_to_execution(
        app_cli,
        repo_root=repo_root,
        target=target,
        key="deploy.remote.stop-previous-control-plane",
        transition_step=transition_step,
    )
    if transition_execution is not None:
        steps.append(transition_execution)
    steps.append(
        plan_remote_shell_step(
            "deploy.remote.compose-up",
            ssh_target=ssh_target,
            cwd=None,
            argv=("sh",),
            shell_command=(
                f"cd /opt/agentplane/infra/compose/{contract['app_id']} && "
                f"docker compose -f {remote_compose_name} up -d --pull never"
            ),
            capabilities=("ssh", "docker"),
        )
    )
    return steps, {
        "container_name": rendered["container_name"],
        "remote_compose": remote_compose,
        "remote_env": remote_env,
        "local_env": app_cli._payload_path(env_path),
    }


def _plan_delivery_verify_steps(
    app_cli: Any,
    contract: dict[str, Any],
    *,
    repo_root: Path,
    target: str,
    include_public: bool,
) -> tuple[list[CommandStep], str]:
    container_name = app_cli._runtime_container_name(str(contract["app_id"]), contract["runtime"], target=target)
    if target == "wsl":
        healthcheck_url = app_cli._healthcheck_url(contract, target=target)
        return [
            plan_local_backend_step(
                "verify.wsl.healthcheck",
                backend_type=detect_host_profile().linux_backend,
                cwd=repo_root,
                argv=("curl", "-fsS", healthcheck_url),
                capabilities=("curl",),
            )
        ], container_name

    ssh_target = app_cli._target_ssh_target(repo_root, target)
    origin_health_wait = app_cli._origin_health_wait_command(contract, container_name=container_name)
    steps = [
        plan_remote_shell_step(
            "verify.remote.inspect",
            ssh_target=ssh_target,
            cwd=None,
            argv=("docker", "inspect", container_name),
            capabilities=("ssh", "docker"),
        ),
        plan_remote_shell_step(
            "verify.remote.origin-health",
            ssh_target=ssh_target,
            cwd=None,
            argv=("sh",),
            shell_command=origin_health_wait,
            capabilities=("ssh", "docker", "curl"),
        ),
    ]
    if include_public and app_cli.has_public_ingress(contract):
        public_root = str(app_cli.public_sites(contract)[0]["public_url"]).rstrip("/")
        local_backend = detect_host_profile().linux_backend
        steps.extend(
            [
                plan_local_backend_step(
                    "verify.public.healthcheck",
                    backend_type=local_backend,
                    cwd=repo_root,
                    argv=("curl", "-fsS", f"{public_root}{contract['runtime']['healthcheck']['path']}"),
                    capabilities=("curl",),
                ),
                plan_local_backend_step(
                    "verify.public.headers",
                    backend_type=local_backend,
                    cwd=repo_root,
                    argv=("curl", "-fsSI", f"{public_root}/"),
                    capabilities=("curl",),
                ),
            ]
        )
    return steps, container_name


def _plan_delivery_rollback_steps(
    app_cli: Any,
    contract: dict[str, Any],
    *,
    repo_root: Path,
    target: str,
) -> tuple[list[CommandStep], dict[str, Any]]:
    rollback_entry = contract["rollback"]["previous_control_plane"]
    if target == "wsl" or rollback_entry.get("kind") == "none":
        return [], rollback_entry
    ssh_target = app_cli._target_ssh_target(repo_root, target)
    steps = [
        plan_remote_shell_step(
            "rollback.remote.compose-down",
            ssh_target=ssh_target,
            cwd=None,
            argv=("sh",),
            shell_command=(
                f"cd /opt/agentplane/infra/compose/{contract['app_id']} && "
                f"docker compose -f {app_cli._remote_compose_filename(target)} down || true"
            ),
            capabilities=("ssh", "docker"),
        )
    ]
    transition_step = app_cli._control_plane_transition_step(
        repo_root, target=target, rollback_entry=rollback_entry, operate="start"
    )
    transition_execution = _transition_step_to_execution(
        app_cli,
        repo_root=repo_root,
        target=target,
        key="rollback.remote.start-previous-control-plane",
        transition_step=transition_step,
    )
    if transition_execution is not None:
        steps.append(transition_execution)
    return steps, rollback_entry


def _plan_production_verify(
    app_cli: Any,
    contract: dict[str, Any],
    *,
    repo_root: Path,
    target: str,
    include_public: bool,
) -> dict[str, Any]:
    steps, container_name = _plan_delivery_verify_steps(
        app_cli,
        contract,
        repo_root=repo_root,
        target=target,
        include_public=include_public,
    )
    execution_steps = _render_execution_steps(steps)
    return {
        "container_name": container_name,
        "commands": [step["backend"]["display_command"] for step in execution_steps],
        "execution_steps": execution_steps,
        "status": "planned",
    }


def _execute_origin_verify(app_cli: Any, contract: dict[str, Any], *, repo_root: Path, target: str) -> dict[str, Any]:
    steps, container_name = _plan_delivery_verify_steps(
        app_cli,
        contract,
        repo_root=repo_root,
        target=target,
        include_public=False,
    )
    checks = _execute_steps(steps, stop_on_failure=True)
    return {
        "container_name": container_name,
        "network_preflight": app_cli._production_network_preflight(repo_root, target),
        "commands": [item["display"] for item in checks],
        "checks": {"origin": checks, "public": []},
        "ok": all(item["ok"] for item in checks),
    }


def _plan_production_rollback(
    app_cli: Any, contract: dict[str, Any], *, repo_root: Path, target: str
) -> dict[str, Any]:
    steps, rollback_entry = _plan_delivery_rollback_steps(app_cli, contract, repo_root=repo_root, target=target)
    if not steps:
        return {
            "rollback_entry": rollback_entry,
            "commands": [],
            "warning": app_cli.render_rollback_entry(rollback_entry),
            "status": "not-applicable",
        }
    execution_steps = _render_execution_steps(steps)
    return {
        "rollback_entry": rollback_entry,
        "commands": [step["backend"]["display_command"] for step in execution_steps],
        "execution_steps": execution_steps,
        "status": "planned",
    }
