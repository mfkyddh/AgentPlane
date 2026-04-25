from __future__ import annotations

import json
import shlex
from pathlib import Path
from typing import Any

from agentplane.adapters.service.common import copy_file_spec, remote_repo_root, run_shell_command, shell_command_spec
from agentplane.domain.service.models import ServiceDefinition
from agentplane.runtime.redaction import redact_execution_payload


def _container_name(definition: ServiceDefinition, declared: dict[str, Any] | None) -> str:
    key = str(definition.metadata.get("container_name_key", "container_name"))
    if declared and isinstance(declared.get(key), str):
        return str(declared[key])
    raise ValueError(f"{definition.name} 缺少 container_name")


def inspect_container(repo_root: Path, target: str, definition: ServiceDefinition, declared: dict[str, Any] | None) -> dict[str, Any]:
    container_name = _container_name(definition, declared)
    result = run_shell_command(
        repo_root,
        target,
        f"docker inspect {shlex.quote(container_name)} --format '{{{{json .}}}}'",
    )
    payload: dict[str, Any] = {"probe": redact_execution_payload(result), "container_name": container_name}
    if result["ok"]:
        stdout = str(result["stdout"]).strip()
        payload["live"] = json.loads(stdout) if stdout else {}
    return payload


def verify_container_service(repo_root: Path, target: str, definition: ServiceDefinition, declared: dict[str, Any] | None) -> dict[str, Any]:
    inspected = inspect_container(repo_root, target, definition, declared)
    probe = inspected["probe"]
    if not probe["ok"]:
        return {"ok": False, "checks": {"container_exists": {"ok": False}}, "evidence": [probe], "failures": ["container_missing"]}

    live = inspected.get("live", {})
    state = live.get("State", {}) if isinstance(live, dict) else {}
    config = live.get("Config", {}) if isinstance(live, dict) else {}
    host_config = live.get("HostConfig", {}) if isinstance(live, dict) else {}
    checks: dict[str, dict[str, object]] = {}

    running = bool(state.get("Running")) and state.get("Status") == "running"
    checks["running"] = {"ok": running, "actual": state.get("Status")}

    expected_image = declared.get("image") if isinstance(declared, dict) else None
    if isinstance(expected_image, str):
        actual_image = config.get("Image")
        checks["image"] = {"ok": actual_image == expected_image, "actual": actual_image, "expected": expected_image}

    expected_network_mode = declared.get("network_mode") if isinstance(declared, dict) else None
    if isinstance(expected_network_mode, str):
        actual_network_mode = host_config.get("NetworkMode")
        checks["network_mode"] = {"ok": actual_network_mode == expected_network_mode, "actual": actual_network_mode, "expected": expected_network_mode}

    host_network_mode = host_config.get("NetworkMode") == "infra"
    expected_host_binding = declared.get("host_binding") if isinstance(declared, dict) else None
    if isinstance(expected_host_binding, str) and expected_host_binding:
        actual_bindings: list[str] = []
        network_settings = live.get("NetworkSettings") if isinstance(live, dict) else {}
        if isinstance(network_settings, dict):
            ports = network_settings.get("Ports")
            if isinstance(ports, dict):
                for bindings in ports.values():
                    if isinstance(bindings, list):
                        for binding in bindings:
                            if isinstance(binding, dict):
                                host_ip = binding.get("HostIp")
                                host_port = binding.get("HostPort")
                                if isinstance(host_ip, str) and isinstance(host_port, str):
                                    actual_bindings.append(f"{host_ip}:{host_port}")
        host_binding_ok = expected_host_binding in actual_bindings
        if host_network_mode and not actual_bindings:
            host_binding_ok = True
        checks["host_binding"] = {
            "ok": host_binding_ok,
            "actual": actual_bindings,
            "expected": expected_host_binding,
        }

    failures = [name for name, item in checks.items() if not bool(item.get("ok"))]
    return {"ok": not failures, "checks": checks, "evidence": [probe], "failures": failures}


def plan_container_operation(repo_root: Path, target: str, definition: ServiceDefinition, declared: dict[str, Any] | None, operation: str) -> list[dict[str, object]]:
    container_name = _container_name(definition, declared)
    commands: list[str]
    if operation == "restart":
        commands = [f"docker restart {shlex.quote(container_name)}"]
    elif operation == "reconcile":
        repo_path = remote_repo_root(target, repo_root)
        target_alias = "wsl" if target == "wsl" else ("prod0" if target == "prod0-main" else "prod2")
        compose_filename = f"docker-compose.{target_alias}.yml"
        remote_compose_dir = f"{repo_path}/infra/compose/{definition.name}"
        remote_compose_path = f"{remote_compose_dir}/{compose_filename}"
        local_compose_path = repo_root / "infra" / "compose" / definition.name / compose_filename
        commands = [f"mkdir -p {shlex.quote(remote_compose_dir)}"]
        if target != "wsl":
            commands.append(
                f"if [ ! -e {shlex.quote(f'{repo_path}/secrets')} ] && [ -d /opt/env_ubuntu/secrets ]; then ln -s /opt/env_ubuntu/secrets {shlex.quote(f'{repo_path}/secrets')}; fi"
            )
        commands.append(f"cd {shlex.quote(remote_compose_dir)} && docker compose -f {shlex.quote(compose_filename)} up -d")
        specs = [shell_command_spec(repo_root, target, command) for command in commands[:-1]]
        if local_compose_path.is_file():
            specs.append(copy_file_spec(repo_root, target, local_compose_path, remote_compose_path))
        specs.append(shell_command_spec(repo_root, target, commands[-1]))
        return [{"argv": spec.argv, "display": spec.display} for spec in specs]
    elif operation == "reload" and definition.name == "onepanel_openresty":
        commands = [f"docker exec {shlex.quote(container_name)} nginx -t && docker exec {shlex.quote(container_name)} nginx -s reload"]
    else:
        raise ValueError(f"unsupported operation for {definition.name}: {operation}")
    return [{"argv": spec.argv, "display": spec.display} for spec in [shell_command_spec(repo_root, target, command) for command in commands]]
