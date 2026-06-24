"""Deploy and verify operations extracted from runtime.py."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from agentplane.domain.app.contracts import has_public_ingress, public_sites
# Lazy imports to avoid circular dependency with runtime.py
# runtime.py re-exports deploy_app and verify_app from this module
def _get_runtime_helpers():
    from agentplane.domain.app.runtime import (
        _control_plane_transition_step,
        _execute_step,
        _local_backend_type,
        _production_network_preflight,
        _record_app_operation,
        _target_ssh_target,
        render_runtime,
    )
    from agentplane.domain.app.runtime_helpers import (
        _healthcheck_url,
        _origin_health_wait_command,
        _payload_path,
        _remote_compose_filename,
        _remote_env_parent,
        _remote_env_path,
        _runtime_container_name,
        _service_env_path,
    )
    from agentplane.runtime.operations import next_operation_id
    from agentplane.runtime.wsl_bridge import windows_path_to_wsl_posix
    
    return {
        '_control_plane_transition_step': _control_plane_transition_step,
        '_execute_step': _execute_step,
        '_local_backend_type': _local_backend_type,
        '_production_network_preflight': _production_network_preflight,
        '_record_app_operation': _record_app_operation,
        '_target_ssh_target': _target_ssh_target,
        'render_runtime': render_runtime,
        '_healthcheck_url': _healthcheck_url,
        '_origin_health_wait_command': _origin_health_wait_command,
        '_payload_path': _payload_path,
        '_remote_compose_filename': _remote_compose_filename,
        '_remote_env_parent': _remote_env_parent,
        '_remote_env_path': _remote_env_path,
        '_runtime_container_name': _runtime_container_name,
        '_service_env_path': _service_env_path,
        'next_operation_id': next_operation_id,
        'windows_path_to_wsl_posix': windows_path_to_wsl_posix,
    }


def deploy_app(
    contract: dict[str, Any], *, repo_root: Path, target: str, image_ref: str | None, dry_run: bool, execute: bool
) -> dict[str, Any]:
    # Get all imported functions lazily to avoid circular dependency
    helpers = _get_runtime_helpers()
    next_operation_id = helpers['next_operation_id']
    _local_backend_type = helpers['_local_backend_type']
    render_runtime = helpers['render_runtime']
    _record_app_operation = helpers['_record_app_operation']
    _execute_step = helpers['_execute_step']
    _target_ssh_target = helpers['_target_ssh_target']
    _control_plane_transition_step = helpers['_control_plane_transition_step']
    _production_network_preflight = helpers['_production_network_preflight']
    _service_env_path = helpers['_service_env_path']
    _remote_compose_filename = helpers['_remote_compose_filename']
    _remote_env_path = helpers['_remote_env_path']
    _remote_env_parent = helpers['_remote_env_parent']
    _payload_path = helpers['_payload_path']
    windows_path_to_wsl_posix = helpers['windows_path_to_wsl_posix']
    
    op_id = next_operation_id("deploy-app")
    local_backend = _local_backend_type()
    if execute and dry_run:
        raise ValueError("deploy 不允许同时传 --dry-run 和 --execute")
    rendered = render_runtime(contract, repo_root=repo_root, target=target, image_ref=image_ref)
    if target == "wsl":
        compose_path = Path(rendered["compose_file"])
        if not execute:
            commands = [f"docker compose -f {compose_path} up -d --pull never"]
            operation = _record_app_operation(
                repo_root,
                action="deploy",
                target=target,
                dry_run=dry_run,
                operation={"op_id": op_id, "target": target, "result": "planned" if dry_run else "local-only"},
                details={"artifact_summary": compose_path.name},
            )
            return {
                "container_name": rendered["container_name"],
                "commands": commands,
                "operation": operation,
                "dry_run": dry_run,
            }
        compose_payload = yaml.safe_load(str(rendered["compose"]))
        if not isinstance(compose_payload, dict):
            raise ValueError("rendered compose 必须是对象")
        services = compose_payload.get("services")
        if not isinstance(services, dict):
            raise ValueError("rendered compose 缺少 services")
        service_name = str(contract["app_id"])
        wsl_service = services.get(service_name)
        if not isinstance(wsl_service, dict):
            raise ValueError(f"rendered compose 缺少 services.{service_name}")
        env_file_path = _service_env_path(repo_root, service_name, target)
        wsl_env_file = windows_path_to_wsl_posix(env_file_path) or str(env_file_path)
        wsl_service["env_file"] = [wsl_env_file]
        rendered_compose = compose_path.parent / f".{compose_path.stem}.{op_id}.rendered.yml"
        rendered_compose.write_text(
            yaml.safe_dump(compose_payload, sort_keys=False, allow_unicode=False),
            encoding="utf-8",
        )
        wsl_compose_path = windows_path_to_wsl_posix(rendered_compose) or str(rendered_compose)
        step = _execute_step(
            argv=["docker", "compose", "-f", wsl_compose_path, "up", "-d", "--pull", "never"],
            display=f"docker compose -f {wsl_compose_path} up -d --pull never",
            cwd=repo_root,
            backend_type=local_backend,
            capabilities=("docker",),
        )
        ok = step["ok"]
        operation = _record_app_operation(
            repo_root,
            action="deploy",
            target=target,
            dry_run=False,
            operation={"op_id": op_id, "target": target, "result": "executed" if ok else "failed"},
            details={"artifact_summary": rendered_compose.name},
        )
        return {
            "container_name": rendered["container_name"],
            "compose_file": str(rendered_compose),
            "commands": [step["display"]],
            "results": [step],
            "operation": operation,
            "ok": ok,
            "dry_run": False,
            "backend_type": local_backend,
        }

    ssh_target = _target_ssh_target(repo_root, target)
    env_path = _service_env_path(repo_root, str(contract["app_id"]), target)
    rollback_entry = contract["rollback"]["previous_control_plane"]
    remote_compose_name = _remote_compose_filename(target)
    remote_compose = f"/opt/agentplane/infra/compose/{contract['app_id']}/{remote_compose_name}"
    remote_env = _remote_env_path(str(contract["app_id"]), target)
    remote_env_parent = _remote_env_parent(remote_env)
    commands = [
        ssh_target.display_ssh_command(
            f"mkdir -p /opt/agentplane/infra/compose/{contract['app_id']} {remote_env_parent}"
        ),
        ssh_target.display_scp_command("<rendered-compose>", remote_compose),
        ssh_target.display_scp_command(str(env_path), f"/tmp/{env_path.name}"),
        ssh_target.display_ssh_command(
            f"install -Dm600 /tmp/{env_path.name} {remote_env} && rm -f /tmp/{env_path.name}"
        ),
        ssh_target.display_ssh_command(
            f"cd /opt/agentplane/infra/compose/{contract['app_id']} && docker compose -f {remote_compose_name} up -d --pull never"
        ),
    ]
    transition_step = _control_plane_transition_step(
        repo_root, target=target, rollback_entry=rollback_entry, operate="stop"
    )
    if transition_step:
        commands.insert(-1, transition_step[1])
    if dry_run:
        operation = _record_app_operation(
            repo_root,
            action="deploy",
            target=target,
            dry_run=True,
            operation={
                "op_id": op_id,
                "target": target,
                "artifact_summary": f"{contract['app_id']} compose + {env_path.name}",
                "result": "planned",
            },
            details={
                "artifact_summary": f"{contract['app_id']} compose + {env_path.name}",
                "remote_env": remote_env,
                "remote_compose": remote_compose,
            },
        )
        return {
            "container_name": rendered["container_name"],
            "remote_compose": remote_compose,
            "remote_env": remote_env,
            "local_env": _payload_path(env_path),
            "commands": commands,
            "operation": operation,
            "dry_run": True,
        }
    if not execute:
        raise ValueError("deploy 当前默认只生成计划；如需真执行请传 --execute")

    network_preflight = _production_network_preflight(repo_root, target)
    env_path.parent.mkdir(parents=True, exist_ok=True)
    if not env_path.is_file():
        raise ValueError(f"缺少运行时 env 文件: {env_path}")
    rendered_dir = repo_root / "tmp" / "rendered-compose"
    rendered_dir.mkdir(parents=True, exist_ok=True)
    rendered_compose = rendered_dir / f"{contract['app_id']}-{op_id}.yml"
    rendered_compose.write_text(str(rendered["compose"]), encoding="utf-8")
    steps = [
        (
            ssh_target.local_ssh_args_for_shell(
                f"mkdir -p /opt/agentplane/infra/compose/{contract['app_id']} {remote_env_parent}"
            ),
            ssh_target.display_ssh_command(
                f"mkdir -p /opt/agentplane/infra/compose/{contract['app_id']} {remote_env_parent}"
            ),
        ),
        (
            ssh_target.local_scp_args(str(rendered_compose), remote_compose),
            ssh_target.display_scp_command(str(rendered_compose), remote_compose),
        ),
        (
            ssh_target.local_scp_args(str(env_path), f"/tmp/{env_path.name}"),
            ssh_target.display_scp_command(str(env_path), f"/tmp/{env_path.name}"),
        ),
        (
            ssh_target.local_ssh_args_for_shell(
                f"install -Dm600 /tmp/{env_path.name} {remote_env} && rm -f /tmp/{env_path.name}"
            ),
            ssh_target.display_ssh_command(
                f"install -Dm600 /tmp/{env_path.name} {remote_env} && rm -f /tmp/{env_path.name}"
            ),
        ),
    ]
    transition_step = _control_plane_transition_step(
        repo_root, target=target, rollback_entry=rollback_entry, operate="stop"
    )
    if transition_step:
        steps.append(transition_step)
    steps.append(
        (
            ssh_target.local_ssh_args_for_shell(
                f"cd /opt/agentplane/infra/compose/{contract['app_id']} && docker compose -f {remote_compose_name} up -d --pull never"
            ),
            ssh_target.display_ssh_command(
                f"cd /opt/agentplane/infra/compose/{contract['app_id']} && docker compose -f {remote_compose_name} up -d --pull never"
            ),
        )
    )
    step_results = [
        _execute_step(
            argv=argv,
            display=display,
            backend_type=local_backend if argv and argv[0] == "python3" else None,
            capabilities=("python3",) if argv and argv[0] == "python3" else None,
        )
        for argv, display in steps
    ]
    ok = all(item["ok"] for item in step_results)
    operation = _record_app_operation(
        repo_root,
        action="deploy",
        target=target,
        dry_run=False,
        operation={
            "op_id": op_id,
            "target": target,
            "artifact_summary": f"{contract['app_id']} compose + {env_path.name}",
            "result": "executed" if ok else "failed",
        },
        details={
            "artifact_summary": f"{contract['app_id']} compose + {env_path.name}",
            "remote_env": remote_env,
            "remote_compose": remote_compose,
        },
    )
    return {
        "container_name": rendered["container_name"],
        "remote_compose": remote_compose,
        "remote_env": remote_env,
        "local_env": _payload_path(env_path),
        "network_preflight": network_preflight,
        "commands": [display for _, display in steps],
        "results": step_results,
        "operation": operation,
        "ok": ok,
        "dry_run": False,
    }


def verify_app(
    contract: dict[str, Any], *, repo_root: Path, target: str, dry_run: bool, execute: bool
) -> dict[str, Any]:
    # Get all imported functions lazily to avoid circular dependency
    helpers = _get_runtime_helpers()
    next_operation_id = helpers['next_operation_id']
    _local_backend_type = helpers['_local_backend_type']
    _healthcheck_url = helpers['_healthcheck_url']
    _runtime_container_name = helpers['_runtime_container_name']
    _record_app_operation = helpers['_record_app_operation']
    _execute_step = helpers['_execute_step']
    _target_ssh_target = helpers['_target_ssh_target']
    _origin_health_wait_command = helpers['_origin_health_wait_command']
    _production_network_preflight = helpers['_production_network_preflight']
    
    op_id = next_operation_id("verify-app")
    local_backend = _local_backend_type()
    if execute and dry_run:
        raise ValueError("verify 不允许同时传 --dry-run 和 --execute")
    healthcheck_url = _healthcheck_url(contract, target=target)
    container_name = _runtime_container_name(str(contract["app_id"]), contract["runtime"], target=target)
    if target == "wsl":
        commands = [f"curl -fsS {healthcheck_url}"]
        if not execute:
            operation = _record_app_operation(
                repo_root,
                action="verify",
                target=target,
                dry_run=dry_run,
                operation={"op_id": op_id, "target": target, "result": "planned" if dry_run else "local-only"},
                details={"artifact_summary": container_name},
            )
            return {
                "container_name": container_name,
                "commands": commands,
                "operation": operation,
                "dry_run": dry_run,
            }
        result = _execute_step(
            argv=["curl", "-fsS", healthcheck_url],
            display=commands[0],
            cwd=repo_root,
            backend_type=local_backend,
            capabilities=("curl",),
        )
        ok = result["ok"]
        operation = _record_app_operation(
            repo_root,
            action="verify",
            target=target,
            dry_run=False,
            operation={"op_id": op_id, "target": target, "result": "verified" if ok else "failed"},
            details={"artifact_summary": container_name},
        )
        return {
            "container_name": container_name,
            "commands": commands,
            "results": [result],
            "operation": operation,
            "dry_run": False,
            "ok": ok,
            "backend_type": local_backend,
        }
    ssh_target = _target_ssh_target(repo_root, target)
    origin_health_wait = _origin_health_wait_command(contract, container_name=container_name)
    origin_health_command = ssh_target.display_ssh_command(origin_health_wait)
    commands = [
        ssh_target.display_ssh_command(f"docker inspect {container_name}"),
        origin_health_command,
    ]
    if has_public_ingress(contract):
        commands.append(f"curl -fsS {healthcheck_url}")
    if not execute:
        operation = _record_app_operation(
            repo_root,
            action="verify",
            target=target,
            dry_run=dry_run,
            operation={"op_id": op_id, "target": target, "artifact_summary": container_name, "result": "planned"},
            details={"artifact_summary": container_name},
        )
        return {
            "container_name": container_name,
            "commands": commands,
            "operation": operation,
            "dry_run": dry_run,
        }
    network_preflight = _production_network_preflight(repo_root, target)
    origin_checks = [
        _execute_step(
            argv=ssh_target.local_ssh_args_for_shell(f"docker inspect {container_name}"),
            display=ssh_target.display_ssh_command(f"docker inspect {container_name}"),
        ),
        _execute_step(
            argv=ssh_target.local_ssh_args_for_shell(origin_health_wait),
            display=ssh_target.display_ssh_command(origin_health_wait),
        ),
    ]
    public_checks: list[dict[str, Any]] = []
    if has_public_ingress(contract):
        public_root = str(public_sites(contract)[0]["public_url"]).rstrip("/")
        public_checks = [
            _execute_step(
                argv=["curl", "-fsS", f"{public_root}{contract['runtime']['healthcheck']['path']}"],
                display=f"curl -fsS {public_root}{contract['runtime']['healthcheck']['path']}",
                backend_type=local_backend,
                capabilities=("curl",),
            ),
            _execute_step(
                argv=["curl", "-fsSI", f"{public_root}/"],
                display=f"curl -fsSI {public_root}/",
                backend_type=local_backend,
                capabilities=("curl",),
            ),
        ]
    ok = all(item["ok"] for item in origin_checks + public_checks)
    operation = _record_app_operation(
        repo_root,
        action="verify",
        target=target,
        dry_run=False,
        operation={
            "op_id": op_id,
            "target": target,
            "artifact_summary": container_name,
            "result": "verified" if ok else "failed",
        },
        details={"artifact_summary": container_name},
    )
    return {
        "container_name": container_name,
        "network_preflight": network_preflight,
        "commands": [item["display"] for item in origin_checks + public_checks],
        "checks": {"origin": origin_checks, "public": public_checks},
        "operation": operation,
        "dry_run": False,
        "ok": ok,
    }
