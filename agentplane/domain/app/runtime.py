from __future__ import annotations

import json
from pathlib import Path
from subprocess import CompletedProcess
from typing import Any

import yaml
from agentplane.domain.app.artifacts import contract_image_name
from agentplane.domain.app.contracts import load_yaml, nested_get, validate_contract
from agentplane.domain.app.doc_sync import doc_sync as doc_sync
from agentplane.domain.app.resource_state import (
    APP_RESOURCE_SUMMARY_FIELDS,
    build_app_resource_summary,
    load_registry,
    registry_secret_file,
)
from agentplane.domain.infra.networks import ensure_managed_bridge_networks
from agentplane.domain.targets import PRODUCTION_TARGETS
from agentplane.providers import get_provider
from agentplane.runtime.backends import build_backend_runner
from agentplane.runtime.execution import CommandRunner, CommandSpec
from agentplane.runtime.host_profile import detect_host_profile
from agentplane.runtime.operations import append_operation_ledger
from agentplane.runtime.redaction import redact_execution_payload
from agentplane.ssh import SshTarget, resolve_ssh_target

PRODUCTION_APP_TARGETS = PRODUCTION_TARGETS


def _run(command: list[str], *, cwd: Path | None = None, env: dict[str, str] | None = None) -> CompletedProcess[str]:
    return CommandRunner().run(command, cwd=cwd, env=env)


def _local_backend_type() -> str:
    return str(detect_host_profile().linux_backend)


def _run_linux_backend_command(
    command: str,
    *,
    cwd: Path,
    env: dict[str, str],
    backend: str,
    _runner=None,
) -> CompletedProcess[str]:
    local_backend = _local_backend_type()
    if backend == "native-posix":
        execution_backend = local_backend
    elif backend == "wsl-linux":
        execution_backend = "windows-wsl" if local_backend == "windows-wsl" else "linux-native"
    else:
        raise ValueError(f"暂不支持本地执行 packaging.backend={backend!r}")
    runner = _runner or build_backend_runner()
    spec = CommandSpec(
        backend_type=execution_backend,  # type: ignore[arg-type]
        argv=("bash", "-lc", command),
        cwd=cwd,
        env=env,
        capabilities=("bash",),
        timeout=1800,
    )
    result = runner.execute_spec(spec)
    return CompletedProcess(
        args=list(result.argv),
        returncode=result.returncode,
        stdout=result.stdout,
        stderr=result.stderr,
    )


def _record_app_operation(
    repo_root: Path,
    *,
    action: str,
    target: str,
    dry_run: bool,
    operation: dict[str, Any],
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    ledger = append_operation_ledger(
        repo_root,
        command="app",
        action=action,
        target=target,
        op_id=str(operation["op_id"]),
        dry_run=dry_run,
        result=str(operation["result"]),
        details=details,
    )
    enriched = dict(operation)
    enriched["ledger_file"] = ledger["ledger_file"]
    return enriched


def _load_inventory(repo_root: Path, target: str) -> tuple[Path, dict[str, Any]]:
    inventory_file = repo_root / "inventory" / "servers" / target / "inventory.json"
    if not inventory_file.exists():
        raise ValueError(f"缺少 inventory 文件: {inventory_file}")
    payload = json.loads(inventory_file.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"inventory 顶层必须是对象: {inventory_file}")
    return inventory_file, payload


def _onepanel_lifecycle_command(repo_root: Path, *, target: str, operate: str, rollback_entry: dict[str, Any]) -> str:
    _argv, display = _onepanel_lifecycle_step(repo_root, target=target, operate=operate, rollback_entry=rollback_entry)
    return display


def _onepanel_lifecycle_step(
    repo_root: Path, *, target: str, operate: str, rollback_entry: dict[str, Any]
) -> tuple[list[str], str]:
    return get_provider().app_lifecycle_step(
        repo_root,
        target=target,
        operate=operate,
        rollback_entry=rollback_entry,
    )


def _onepanel_project_step(
    repo_root: Path, *, target: str, operate: str, rollback_entry: dict[str, Any]
) -> tuple[list[str], str]:
    return get_provider().project_lifecycle_step(
        repo_root,
        target=target,
        operate=operate,
        rollback_entry=rollback_entry,
    )


def _systemd_transition_step(
    repo_root: Path, *, target: str, operate: str, rollback_entry: dict[str, Any]
) -> tuple[list[str], str]:
    service_name = rollback_entry.get("service_name")
    if not isinstance(service_name, str) or not service_name:
        raise ValueError(f"rollback.previous_control_plane.kind=systemd 缺少 service_name: {rollback_entry}")
    ssh_target = _target_ssh_target(repo_root, target)
    if operate == "stop":
        command = f"systemctl disable --now {service_name} || true"
    elif operate == "start":
        command = f"systemctl enable --now {service_name} || true"
    else:
        raise ValueError(f"不支持的 systemd 过渡动作: {operate}")
    return ssh_target.local_ssh_args_for_shell(command), ssh_target.display_ssh_command(command)


def _control_plane_transition_step(
    repo_root: Path, *, target: str, rollback_entry: dict[str, Any], operate: str
) -> tuple[list[str], str] | None:
    kind = rollback_entry.get("kind")
    if kind == "none":
        return None
    if kind == "systemd":
        return _systemd_transition_step(repo_root, target=target, operate=operate, rollback_entry=rollback_entry)
    if kind == "1panel-app":
        return _onepanel_lifecycle_step(repo_root, target=target, operate=operate, rollback_entry=rollback_entry)
    if kind == "1panel-compose":
        return _onepanel_project_step(
            repo_root,
            target=target,
            operate="up" if operate == "start" else "stop",
            rollback_entry=rollback_entry,
        )
    raise ValueError(f"不支持的 rollback.previous_control_plane.kind: {kind}")


def _registry_app_resource_summary(repo_root: Path, target: str, app_id: str) -> dict[str, dict[str, Any]] | None:
    try:
        _, registry = load_registry(repo_root, target)
    except FileNotFoundError:
        return None
    entry = registry.get(app_id)
    if not isinstance(entry, dict):
        return None

    summary: dict[str, dict[str, Any]] = {}
    for kind, fields in APP_RESOURCE_SUMMARY_FIELDS.items():
        spec = entry.get(kind)
        if not isinstance(spec, dict):
            continue
        item = {field: spec[field] for field in fields if spec.get(field) not in (None, "")}
        if kind == "redis":
            item.pop("user", None)
        secret_file = registry_secret_file(entry, kind)
        if isinstance(secret_file, str) and secret_file:
            item["secret_file"] = secret_file
        if item:
            summary[kind] = item
    return summary or None


def render_runtime(
    contract: dict[str, Any], *, repo_root: Path, target: str, image_ref: str | None = None
) -> dict[str, Any]:
    template_path = _compose_template_path(repo_root, str(contract["app_id"]), target=target)
    compose = load_yaml(template_path)
    service_name = str(contract["app_id"])
    service = compose.get("services", {}).get(service_name)
    if not isinstance(service, dict):
        raise ValueError(f"{template_path} 缺少 services.{service_name}")

    runtime = contract["runtime"]
    depends = contract["infra"]["depends_on_containers"]
    contract_image = contract_image_name(contract)
    if contract_image is None:
        raise ValueError("合同缺少镜像名")
    build_image_ref = image_ref or f"{contract_image}:latest"
    service["image"] = build_image_ref
    service["container_name"] = _runtime_container_name(str(contract["app_id"]), runtime, target=target)
    service["ports"] = [_port_mapping(runtime, target=target)]
    prod0_data_env = _prod0_data_env_path(str(contract["app_id"])) if target == "prod0-main" else None
    if prod0_data_env:
        service["env_file"] = [prod0_data_env]
    dependency_env = _default_dependency_env(depends, contract, target=target)
    if dependency_env:
        existing_env = service.get("environment")
        if not isinstance(existing_env, dict):
            existing_env = {}
        existing_env.update(dependency_env)
        service["environment"] = existing_env
    existing_healthcheck = service.get("healthcheck")
    if not isinstance(existing_healthcheck, dict) or not existing_healthcheck:
        service["healthcheck"] = {
            "test": [
                "CMD-SHELL",
                f"curl -fsS http://127.0.0.1:{runtime['container_port']}{runtime['healthcheck']['path']} >/dev/null",
            ],
            "interval": "30s",
            "timeout": "10s",
            "retries": 5,
            "start_period": "30s",
        }
    compose_text = yaml.safe_dump(compose, sort_keys=False, allow_unicode=False)
    return {
        "app_id": contract["app_id"],
        "target": target,
        "container_name": service["container_name"],
        "compose_file": str(template_path),
        "image_ref": build_image_ref,
        "compose": compose_text,
    }


def inventory_refresh(*, repo_root: Path, target: str, contract_paths: list[Path], write: bool) -> dict[str, Any]:
    inventory_file, payload = _load_inventory(repo_root, target)
    services = payload.setdefault("services", {})
    if not isinstance(services, dict):
        raise ValueError("inventory.services 必须是对象")

    for contract_path in contract_paths:
        contract = validate_contract(contract_path, repo_root=repo_root, target=target)
        service_key = nested_get(contract, "inventory.service_key") or contract["app_id"]
        legacy_keys = nested_get(contract, "inventory.remove_service_keys") or []
        if isinstance(legacy_keys, list):
            for legacy_key in legacy_keys:
                if isinstance(legacy_key, str) and legacy_key and legacy_key != service_key:
                    services.pop(legacy_key, None)
        data_mounts = contract["data"]["mounts"]
        data_dir = data_mounts[0]["host_path"] if data_mounts else ""
        runtime_root = f"/data/{contract['app_id']}/app/current"
        runtime = contract["runtime"]
        config_files = _target_config_files(repo_root, str(contract["app_id"]), runtime, target=target)
        service_entry = {
            "control_plane": runtime["kind"],
            "container_name": _runtime_container_name(str(contract["app_id"]), runtime, target=target),
            "depends_on_containers": _target_dependency_names(
                contract["infra"]["depends_on_containers"], target=target
            ),
            "runtime_root": runtime_root,
            "config_files": config_files,
            "data_dir": data_dir,
            "host_binding": _inventory_host_binding(runtime, target=target),
            "container_port": runtime["container_port"],
            "public_url": _inventory_public_url(contract, target=target),
            "rollback_entry": contract["rollback"]["previous_control_plane"],
        }
        docker_networks = _target_docker_networks(repo_root, str(contract["app_id"]), target=target)
        if docker_networks:
            service_entry["docker_networks"] = docker_networks
        app_resource_summary = _registry_app_resource_summary(repo_root, target, str(contract["app_id"]))
        if app_resource_summary is None:
            app_resource_summary = build_app_resource_summary(nested_get(contract, "infra.tenant_resources"))
        if app_resource_summary:
            service_entry["app_resource_summary"] = app_resource_summary
        services[str(service_key)] = service_entry

    if write:
        inventory_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return payload


def _execute_step(
    *,
    argv: list[str],
    display: str,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    backend_type: str | None = None,
    capabilities: tuple[str, ...] | None = None,
    timeout: int = 300,
    _runner=None,
) -> dict[str, Any]:
    if backend_type is not None:
        runner = _runner or build_backend_runner()
        spec = CommandSpec(
            backend_type=backend_type,  # type: ignore[arg-type]
            argv=tuple(str(item) for item in argv),
            cwd=cwd,
            env=env or {},
            capabilities=capabilities or ((str(argv[0]),) if argv else ()),
            timeout=timeout,
        )
        result = runner.execute_spec(spec)
        return redact_execution_payload(result.to_payload())
    result = _run(argv, cwd=cwd, env=env)
    return redact_execution_payload(
        {
            "argv": argv,
            "display": display,
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "ok": result.returncode == 0,
        }
    )


def _production_network_preflight(repo_root: Path, target: str) -> dict[str, Any] | None:
    if not _is_production_target(target):
        return None
    payload = ensure_managed_bridge_networks(repo_root, target)
    if not payload.get("ok", False):
        raise ValueError(f"network ensure failed for {target}")
    return payload


def _target_ssh_target(repo_root: Path, target: str) -> SshTarget:
    return resolve_ssh_target(repo_root, target)


# Re-exports for backward compatibility
# (delivery_handlers.py, tests, and other modules import via app_runtime.xxx)
from agentplane.domain.app.contracts import has_public_ingress as has_public_ingress  # noqa: E402, F401
from agentplane.domain.app.contracts import public_sites as public_sites  # noqa: E402, F401
from agentplane.domain.app.doc_sync import render_rollback_entry as render_rollback_entry  # noqa: E402, F401
from agentplane.domain.app.runtime_build import (  # noqa: E402, F401
    _maybe_recommended_versions,
    _recommended_versions,
    build_artifact,
    package_runtime,
    ship_image,
)
from agentplane.domain.app.runtime_deploy import (  # noqa: E402, F401
    deploy_app,
    verify_app,
)
from agentplane.domain.app.runtime_helpers import (  # noqa: E402, F401
    _compose_template_path,
    _default_dependency_env,
    _healthcheck_url,
    _inventory_host_binding,
    _inventory_public_url,
    _is_production_target,
    _origin_health_wait_command,
    _payload_path,
    _port_mapping,
    _prod0_data_env_path,
    _remote_compose_filename,
    _remote_env_parent,
    _remote_env_path,
    _runtime_base_url,
    _runtime_container_name,
    _secrets_root,
    _service_env_path,
    _split_host_binding,
    _target_alias,
    _target_config_files,
    _target_dependency_names,
    _target_docker_networks,
)
from agentplane.domain.app.runtime_rollback import (  # noqa: E402, F401
    rollback_app,
)
from agentplane.runtime.operations import next_operation_id as next_operation_id  # noqa: E402, F401
