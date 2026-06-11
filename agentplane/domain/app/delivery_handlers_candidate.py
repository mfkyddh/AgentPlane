"""Candidate runtime material and precheck step planning for delivery deploy."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml
from agentplane.domain.app.lifecycle import (
    plan_remote_copy_step,
    plan_remote_shell_step,
)
from agentplane.runtime.execution import CommandStep


def _candidate_host_binding(app_cli: Any, host_binding: str) -> str:
    host_ip, host_port = app_cli._split_host_binding(host_binding)
    port = int(host_port)
    if port <= 64535:
        candidate_port = port + 1000
    elif port > 1000:
        candidate_port = port - 1000
    else:
        raise ValueError(f"无法为 candidate runtime 推导预检端口: {host_binding}")
    return f"{host_ip}:{candidate_port}"


def _candidate_runtime_material(
    app_cli: Any,
    contract: dict[str, Any],
    *,
    repo_root: Path,
    target: str,
    image_ref: str | None,
    rollout_id: str,
    persist_local_compose: bool,
) -> dict[str, Any]:
    app_id = str(contract["app_id"])
    suffix = rollout_id.replace("-", "")[-8:]
    runtime = deepcopy(contract["runtime"])
    base_container_name = app_cli._runtime_container_name(app_id, runtime, target=target)
    candidate_runtime = dict(runtime)
    candidate_runtime["container_name"] = f"{base_container_name}-candidate-{suffix}"
    candidate_runtime["host_binding"] = _candidate_host_binding(app_cli, str(runtime["host_binding"]))

    candidate_contract = deepcopy(contract)
    candidate_contract["runtime"] = candidate_runtime
    rendered = app_cli.render_runtime(candidate_contract, repo_root=repo_root, target=target, image_ref=image_ref)

    compose_payload = yaml.safe_load(str(rendered["compose"]))
    if not isinstance(compose_payload, dict):
        raise ValueError("candidate rendered compose 必须是对象")
    services = compose_payload.get("services")
    if not isinstance(services, dict):
        raise ValueError("candidate rendered compose 缺少 services")
    service = services.get(app_id)
    if not isinstance(service, dict):
        raise ValueError(f"candidate rendered compose 缺少 services.{app_id}")

    remote_compose_name = app_cli._remote_compose_filename(target).removesuffix(".yml") + f".candidate.{suffix}.yml"
    remote_compose_dir = f"/opt/agentplane/infra/compose/{app_id}"
    remote_compose = f"{remote_compose_dir}/{remote_compose_name}"
    remote_env = app_cli._remote_env_path(app_id, target, candidate_suffix=suffix)
    service["env_file"] = [remote_env]
    candidate_compose_text = yaml.safe_dump(compose_payload, sort_keys=False, allow_unicode=False)

    local_compose = repo_root / "tmp" / "rendered-compose" / f"{app_id}-{suffix}-candidate.yml"
    if persist_local_compose:
        local_compose.parent.mkdir(parents=True, exist_ok=True)
        local_compose.write_text(candidate_compose_text, encoding="utf-8")

    health_path = str(candidate_runtime["healthcheck"]["path"])
    _, candidate_port = app_cli._split_host_binding(str(candidate_runtime["host_binding"]))
    return {
        "rollout_id": rollout_id,
        "contract": candidate_contract,
        "compose_text": candidate_compose_text,
        "container_name": str(candidate_runtime["container_name"]),
        "project_name": f"{app_id}-candidate-{suffix}",
        "host_binding": str(candidate_runtime["host_binding"]),
        "health_url": f"http://127.0.0.1:{candidate_port}{health_path}",
        "local_compose": local_compose,
        "local_env": app_cli._service_env_path(repo_root, app_id, target),
        "remote_compose_dir": remote_compose_dir,
        "remote_compose_name": remote_compose_name,
        "remote_compose": remote_compose,
        "remote_env": remote_env,
        "remote_env_dir": app_cli._remote_env_parent(remote_env),
    }


def _candidate_precheck_steps(
    app_cli: Any, repo_root: Path, *, target: str, material: dict[str, Any]
) -> dict[str, list[CommandStep]]:
    ssh_target = app_cli._target_ssh_target(repo_root, target)
    local_env = Path(material["local_env"])
    remote_tmp_env = f"/tmp/{local_env.name}"
    up_command = (
        f"cd {material['remote_compose_dir']} && "
        f"docker compose -p {material['project_name']} -f {material['remote_compose_name']} up -d --pull never"
    )
    down_command = (
        f"cd {material['remote_compose_dir']} && "
        f"docker compose -p {material['project_name']} -f {material['remote_compose_name']} down || true"
    )
    cleanup_remote_command = f"rm -f {material['remote_compose']} {material['remote_env']}"
    origin_health_wait = app_cli._origin_health_wait_command(
        material["contract"], container_name=str(material["container_name"])
    )
    prepare = [
        plan_remote_shell_step(
            "candidate.prepare.remote-dirs",
            ssh_target=ssh_target,
            cwd=None,
            argv=("mkdir", "-p", material["remote_compose_dir"], material["remote_env_dir"]),
            capabilities=("ssh",),
        ),
        plan_remote_copy_step(
            "candidate.prepare.copy-compose",
            ssh_target=ssh_target,
            local_path=Path(material["local_compose"]),
            remote_path=str(material["remote_compose"]),
            expected_outputs=("remote-compose",),
        ),
        plan_remote_copy_step(
            "candidate.prepare.copy-env",
            ssh_target=ssh_target,
            local_path=local_env,
            remote_path=remote_tmp_env,
            expected_outputs=("remote-env-staging",),
        ),
        plan_remote_shell_step(
            "candidate.prepare.install-env",
            ssh_target=ssh_target,
            cwd=None,
            argv=("sh",),
            shell_command=f"install -Dm600 {remote_tmp_env} {material['remote_env']} && rm -f {remote_tmp_env}",
            capabilities=("ssh",),
        ),
        plan_remote_shell_step(
            "candidate.prepare.compose-up",
            ssh_target=ssh_target,
            cwd=None,
            argv=("sh",),
            shell_command=up_command,
            capabilities=("ssh", "docker"),
        ),
    ]
    verify = [
        plan_remote_shell_step(
            "candidate.verify.inspect",
            ssh_target=ssh_target,
            cwd=None,
            argv=("docker", "inspect", str(material["container_name"])),
            capabilities=("ssh", "docker"),
        ),
        plan_remote_shell_step(
            "candidate.verify.health",
            ssh_target=ssh_target,
            cwd=None,
            argv=("sh",),
            shell_command=origin_health_wait,
            capabilities=("ssh", "docker", "curl"),
        ),
    ]
    cleanup = [
        plan_remote_shell_step(
            "candidate.cleanup.compose-down",
            ssh_target=ssh_target,
            cwd=None,
            argv=("sh",),
            shell_command=down_command,
            capabilities=("ssh", "docker"),
        ),
        plan_remote_shell_step(
            "candidate.cleanup.remove-remote-files",
            ssh_target=ssh_target,
            cwd=None,
            argv=("sh",),
            shell_command=cleanup_remote_command,
            capabilities=("ssh",),
        ),
    ]
    return {"prepare": prepare, "verify": verify, "cleanup": cleanup}
