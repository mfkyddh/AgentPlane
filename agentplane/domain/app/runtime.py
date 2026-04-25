from __future__ import annotations

import json
import os
import shlex
from pathlib import Path
from subprocess import CompletedProcess
from typing import Any

import yaml
from agentplane.domain.app.artifacts import (
    artifact_output_path,
    contract_image_name,
    contract_image_tag_rule,
    require_artifact_first_contract,
    resolve_delivery_contract_spec,
)
from agentplane.domain.app.contracts import contract_app_root, contract_validation_target
from agentplane.domain.app.resource_paths import (
    app_resource_secret_dir,
    resolve_secret_file_path,
)
from agentplane.domain.app.resource_paths import (
    secrets_root as shared_secrets_root,
)
from agentplane.domain.app.resource_state import (
    APP_RESOURCE_SUMMARY_FIELDS,
    build_app_resource_summary,
    load_registry,
    registry_secret_file,
)
from agentplane.domain.app.versioning import recommended_versions
from agentplane.domain.networks import ensure_managed_bridge_networks
from agentplane.domain.targets import PRODUCTION_TARGETS, is_production_target, remote_compose_filename, target_alias
from agentplane.providers.gateway import default_provider_gateway
from agentplane.runtime.backends import build_backend_runner
from agentplane.runtime.execution import CommandRunner, ExecutionBindings, ExecutionPlan
from agentplane.runtime.host_profile import detect_host_profile
from agentplane.runtime.operations import append_operation_ledger, next_operation_id
from agentplane.runtime.redaction import redact_execution_payload
from agentplane.ssh import SshTarget, resolve_ssh_target

PRODUCTION_APP_TARGETS = PRODUCTION_TARGETS
ONEPANEL_LEDGER_BEGIN = "<!-- BEGIN AGENTPLANE_ONEPANEL_LEDGER -->"
ONEPANEL_LEDGER_END = "<!-- END AGENTPLANE_ONEPANEL_LEDGER -->"
ERROR_ID_APP_RESOURCE_RESOURCES_REQUIRED = "app.resource.resources_required"
ERROR_ID_APP_RESOURCE_SECRET_FILE_SCOPE = "app.resource.secret_file_scope"
ERROR_ID_APP_RESOURCE_SECRET_FILE_MISSING = "app.resource.secret_file_missing"
ERROR_ID_APP_RESOURCE_REGISTRY_MISMATCH = "app.resource.registry_mismatch"
COMMON_REQUIRED_CONTRACT_FIELDS = (
    "app_id",
    "runtime.container_name",
    "runtime.container_port",
    "runtime.healthcheck.path",
    "runtime.env_template",
    "infra.depends_on_containers",
    "data.mounts",
    "rollback.previous_control_plane",
)
V1_REQUIRED_CONTRACT_FIELDS = (
    "artifact.build_command",
    "artifact.image_name",
    "artifact.image_tag_rule",
)
V2_REQUIRED_CONTRACT_FIELDS = (
    "artifact.build_command",
    "artifact.output_path",
    "artifact.runtime_os",
    "artifact.runtime_arch",
    "packaging.backend",
    "packaging.image_name",
    "packaging.image_tag_rule",
    "packaging.package_command",
)
SUPPORTED_IMAGE_TAG_RULE = "<upstream>-zzz.<yyyymmdd>.v<n>.g<gitsha>"


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
) -> CompletedProcess[str]:
    local_backend = _local_backend_type()
    if backend == "native-posix":
        execution_backend = local_backend
    elif backend == "wsl-linux":
        execution_backend = "windows-wsl" if local_backend == "windows-wsl" else "linux-native"
    else:
        raise ValueError(f"暂不支持本地执行 packaging.backend={backend!r}")
    runner = build_backend_runner()
    plan = ExecutionPlan(
        backend_type=execution_backend,  # type: ignore[arg-type]
        cwd_ref="app.cwd",
        argv=("bash", "-lc", command),
        env_refs=("app.env",),
        input_refs=(),
        expected_outputs=(),
        capabilities=("bash",),
        timeout=1800,
    )
    result = runner.execute(
        plan,
        bindings=ExecutionBindings(
            cwd_values={"app.cwd": cwd},
            env_values={"app.env": env},
        ),
    )
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


def _is_production_target(target: str) -> bool:
    return is_production_target(target)


def _target_alias(target: str) -> str:
    return target_alias(target)


def _remote_compose_filename(target: str) -> str:
    return remote_compose_filename(target)


def _prod0_data_env_path(app_id: str, *, candidate_suffix: str | None = None) -> str | None:
    if app_id != "sub2api":
        return None
    filename = f"{app_id}-prod"
    if candidate_suffix:
        filename = f"{filename}.candidate.{candidate_suffix}"
    return f"/data/{app_id}/config/{filename}.env"


def _remote_env_path(app_id: str, target: str, *, candidate_suffix: str | None = None) -> str:
    if target == "prod0-main":
        data_path = _prod0_data_env_path(app_id, candidate_suffix=candidate_suffix)
        if data_path:
            return data_path
    candidate_fragment = f".candidate.{candidate_suffix}" if candidate_suffix else ""
    return f"/opt/agentplane/secrets/services/{app_id}.{_target_alias(target)}{candidate_fragment}.env"


def _remote_env_parent(remote_env: str) -> str:
    return str(Path(remote_env).parent).replace("\\", "/")


def _load_yaml(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} 必须解析为对象")
    return payload


def _nested_get(payload: dict[str, Any], dotted_key: str) -> Any:
    current: Any = payload
    for item in dotted_key.split("."):
        if not isinstance(current, dict) or item not in current:
            return None
        current = current[item]
    return current


def _validate_image_tag_rule(rule: Any) -> None:
    if not isinstance(rule, str) or rule != SUPPORTED_IMAGE_TAG_RULE:
        raise ValueError(
            "image_tag_rule 必须使用当前二开版本规范: "
            f"{SUPPORTED_IMAGE_TAG_RULE}"
        )


def _ingress_mode(contract: dict[str, Any]) -> str:
    ingress = contract.get("ingress")
    if not isinstance(ingress, dict):
        return "public"
    raw_mode = ingress.get("mode")
    if raw_mode in (None, ""):
        return "public"
    return str(raw_mode)


def _public_sites(contract: dict[str, Any]) -> list[dict[str, Any]]:
    ingress = contract.get("ingress")
    if not isinstance(ingress, dict):
        return []
    public_sites = ingress.get("public_sites")
    if not isinstance(public_sites, list):
        return []
    return [item for item in public_sites if isinstance(item, dict)]


def _has_public_ingress(contract: dict[str, Any]) -> bool:
    return _ingress_mode(contract) != "internal"


def _recommended_versions(contract: dict[str, Any], *, repo_root: Path) -> dict[str, Any]:
    def run_in_app_root(command: list[str], app_root: Path) -> CompletedProcess[str]:
        return _run(command, cwd=app_root)

    return recommended_versions(
        contract,
        repo_root=repo_root,
        run_in_app_root=run_in_app_root,
    )


def _maybe_recommended_versions(contract: dict[str, Any], *, repo_root: Path) -> dict[str, Any] | None:
    try:
        return _recommended_versions(contract, repo_root=repo_root)
    except (FileNotFoundError, ValueError, json.JSONDecodeError):
        return None


def _load_inventory(repo_root: Path, target: str) -> tuple[Path, dict[str, Any]]:
    inventory_file = repo_root / "inventory" / "servers" / target / "inventory.json"
    if not inventory_file.exists():
        raise ValueError(f"缺少 inventory 文件: {inventory_file}")
    payload = json.loads(inventory_file.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"inventory 顶层必须是对象: {inventory_file}")
    return inventory_file, payload


def _secrets_root(repo_root: Path) -> Path:
    return shared_secrets_root(repo_root)


def _payload_path(path: Path | str) -> str:
    rendered = str(path)
    if len(rendered) >= 2 and rendered[0].isalpha() and rendered[1] == ":":
        return rendered
    return rendered.replace("\\", "/")


def _inventory_container_names(payload: dict[str, Any]) -> set[str]:
    services = payload.get("services", {})
    if not isinstance(services, dict):
        return set()
    names: set[str] = set()
    for service in services.values():
        if isinstance(service, dict):
            container_name = service.get("container_name")
            if isinstance(container_name, str) and container_name:
                names.add(container_name)
    return names


def _onepanel_lifecycle_command(repo_root: Path, *, target: str, operate: str, rollback_entry: dict[str, Any]) -> str:
    _argv, display = _onepanel_lifecycle_step(repo_root, target=target, operate=operate, rollback_entry=rollback_entry)
    return display


def _onepanel_lifecycle_step(repo_root: Path, *, target: str, operate: str, rollback_entry: dict[str, Any]) -> tuple[list[str], str]:
    return default_provider_gateway().onepanel_app_lifecycle_step(
        repo_root,
        target=target,
        operate=operate,
        rollback_entry=rollback_entry,
    )


def _onepanel_project_step(repo_root: Path, *, target: str, operate: str, rollback_entry: dict[str, Any]) -> tuple[list[str], str]:
    return default_provider_gateway().onepanel_project_lifecycle_step(
        repo_root,
        target=target,
        operate=operate,
        rollback_entry=rollback_entry,
    )


def _systemd_transition_step(repo_root: Path, *, target: str, operate: str, rollback_entry: dict[str, Any]) -> tuple[list[str], str]:
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


def _is_allowed_app_resource_secret_path(repo_root: Path, target: str, app_id: str, resolved: Path) -> bool:
    canonical_root = app_resource_secret_dir(repo_root, target, app_id).resolve(strict=False)
    return resolved.is_relative_to(canonical_root)


def _render_rollback_entry(rollback_entry: dict[str, Any]) -> str:
    kind = rollback_entry.get("kind")
    if kind == "none":
        note = rollback_entry.get("note")
        if isinstance(note, str) and note:
            return note
        return "无独立旧控制面"
    if kind == "systemd":
        return str(rollback_entry.get("service_name", "-"))
    if kind == "1panel-app":
        app_key = rollback_entry.get("app_key", "-")
        install_id = rollback_entry.get("install_id")
        container_name = rollback_entry.get("container_name")
        parts = [str(app_key)]
        if install_id is not None:
            parts.append(f"install_id={install_id}")
        if isinstance(container_name, str) and container_name:
            parts.append(f"container={container_name}")
        return f"1panel-app ({', '.join(parts)})"
    if kind == "1panel-compose":
        project_name = rollback_entry.get("project_name", "-")
        container_name = rollback_entry.get("container_name")
        project_path = rollback_entry.get("project_path")
        compose_file = rollback_entry.get("compose_file")
        parts = [str(project_name)]
        if isinstance(container_name, str) and container_name:
            parts.append(f"container={container_name}")
        if isinstance(project_path, str) and project_path:
            parts.append(f"path={project_path}")
        if isinstance(compose_file, str) and compose_file:
            parts.append(f"compose={compose_file}")
        return f"1panel-compose ({', '.join(parts)})"
    return json.dumps(rollback_entry, ensure_ascii=False, sort_keys=True)


def _validate_previous_control_plane(rollback_entry: Any) -> None:
    if not isinstance(rollback_entry, dict):
        raise ValueError("rollback.previous_control_plane 必须是对象")
    kind = rollback_entry.get("kind")
    if kind == "none":
        return
    if kind == "systemd":
        service_name = rollback_entry.get("service_name")
        if not isinstance(service_name, str) or not service_name:
            raise ValueError(f"rollback.previous_control_plane.kind=systemd 缺少 service_name: {rollback_entry}")
        return
    if kind == "1panel-app":
        install_id = rollback_entry.get("install_id")
        app_key = rollback_entry.get("app_key")
        if install_id is None and (not isinstance(app_key, str) or not app_key):
            raise ValueError(f"rollback.previous_control_plane.kind=1panel-app 缺少 install_id/app_key: {rollback_entry}")
        return
    if kind == "1panel-compose":
        project_name = rollback_entry.get("project_name")
        if not isinstance(project_name, str) or not project_name:
            raise ValueError(f"rollback.previous_control_plane.kind=1panel-compose 缺少 project_name: {rollback_entry}")
        for field in ("container_name", "project_path", "compose_file"):
            value = rollback_entry.get(field)
            if value is None:
                continue
            if not isinstance(value, str) or not value:
                raise ValueError(f"rollback.previous_control_plane.kind=1panel-compose {field} 必须是非空字符串: {rollback_entry}")
        return
    raise ValueError(f"不支持的 rollback.previous_control_plane.kind: {kind}")


def _tenant_dependency_kinds(depends: list[str], inventory: dict[str, Any]) -> set[str]:
    kinds: set[str] = set()
    services = inventory.get("services")
    container_to_kind: dict[str, str] = {}
    if isinstance(services, dict):
        for service_name, raw_service in services.items():
            if not isinstance(service_name, str) or not isinstance(raw_service, dict):
                continue
            container_name = raw_service.get("container_name")
            if not isinstance(container_name, str) or not container_name:
                continue
            lowered = service_name.lower()
            if "postgres" in lowered:
                container_to_kind[container_name] = "postgres"
            elif "redis" in lowered:
                container_to_kind[container_name] = "redis"
            elif "minio" in lowered:
                container_to_kind[container_name] = "minio"

    for dep in depends:
        inferred = container_to_kind.get(dep)
        if inferred is not None:
            kinds.add(inferred)
            continue
        lowered_dep = dep.lower()
        if "postgres" in lowered_dep:
            kinds.add("postgres")
        elif "redis" in lowered_dep:
            kinds.add("redis")
        elif "minio" in lowered_dep:
            kinds.add("minio")
    return kinds


def _required_tenant_resource_errors(
    app_id: str, required_kinds: set[str], tenant_resources: Any
) -> list[str]:
    if not required_kinds:
        return []
    if not isinstance(tenant_resources, dict):
        return [f"{ERROR_ID_APP_RESOURCE_RESOURCES_REQUIRED}: app={app_id} missing infra.tenant_resources"]

    missing = [
        kind
        for kind in sorted(required_kinds)
        if not isinstance(tenant_resources.get(kind), dict)
    ]
    if not missing:
        return []
    return [
        f"{ERROR_ID_APP_RESOURCE_RESOURCES_REQUIRED}: app={app_id} missing infra.tenant_resources for {', '.join(missing)}"
    ]


def _validate_contract_tenant_secret_file(
    repo_root: Path,
    target: str,
    app_id: str,
    resource_kind: str,
    resource_spec: dict[str, Any],
) -> None:
    secret_file = resource_spec.get("secret_file")
    if not isinstance(secret_file, str) or not secret_file.strip():
        raise ValueError(
            f"{ERROR_ID_APP_RESOURCE_SECRET_FILE_MISSING}: app={app_id} "
            f"infra.tenant_resources.{resource_kind}.secret_file is required"
        )

    resolved = resolve_secret_file_path(repo_root, secret_file)
    if not _is_allowed_app_resource_secret_path(repo_root, target, app_id, resolved):
        raise ValueError(
            f"{ERROR_ID_APP_RESOURCE_SECRET_FILE_SCOPE}: app={app_id} "
            f"secret_file={secret_file} must stay within secrets/hosts/{target}/apps/{app_id}/resources/"
        )
    if not resolved.is_file():
        raise ValueError(f"{ERROR_ID_APP_RESOURCE_SECRET_FILE_MISSING}: app={app_id} secret_file={secret_file}")


def _validate_contract_tenant_registry_alignment(
    repo_root: Path,
    target: str,
    app_id: str,
    kinds_to_check: set[str],
    tenant_resources: dict[str, Any],
) -> None:
    _, registry = load_registry(repo_root, target)
    registry_entry = registry.get(app_id)
    if not isinstance(registry_entry, dict):
        raise ValueError(f"{ERROR_ID_APP_RESOURCE_REGISTRY_MISMATCH}: app={app_id} missing in app resource registry")

    mismatches: list[str] = []
    for kind in sorted(kinds_to_check):
        fields = APP_RESOURCE_SUMMARY_FIELDS.get(kind, ())
        contract_spec = tenant_resources.get(kind)
        registry_spec = registry_entry.get(kind)
        if not isinstance(contract_spec, dict) or not isinstance(registry_spec, dict):
            mismatches.append(f"{kind} entry missing")
            continue
        for field in fields:
            if contract_spec.get(field) != registry_spec.get(field):
                mismatches.append(
                    f"{kind}.{field} contract={contract_spec.get(field)!r} registry={registry_spec.get(field)!r}"
                )
        registry_secret = registry_secret_file(registry_entry, kind)
        contract_secret = contract_spec.get("secret_file")
        if contract_secret != registry_secret:
            mismatches.append(f"{kind}.secret_file contract={contract_secret!r} registry={registry_secret!r}")

    if mismatches:
        raise ValueError(f"{ERROR_ID_APP_RESOURCE_REGISTRY_MISMATCH}: app={app_id} " + "; ".join(mismatches))


def _registry_entry_for_declared_kinds(
    registry_entry: dict[str, Any],
    *,
    kinds_to_check: set[str],
) -> dict[str, Any]:
    filtered: dict[str, Any] = {"owner_app": registry_entry.get("owner_app")}
    secret_files: list[str] = []
    for kind in sorted(kinds_to_check):
        spec = registry_entry.get(kind)
        if isinstance(spec, dict):
            filtered[kind] = spec
        secret_file = registry_secret_file(registry_entry, kind)
        if secret_file is not None:
            secret_files.append(secret_file)
    filtered["secret_files"] = secret_files
    return filtered


def _validate_contract_registry_secret_files(
    repo_root: Path,
    target: str,
    app_id: str,
    registry_entry: dict[str, Any],
) -> None:
    secret_files = registry_entry.get("secret_files")
    if not isinstance(secret_files, list):
        return

    for item in secret_files:
        if not isinstance(item, str) or not item.strip():
            continue
        resolved = resolve_secret_file_path(repo_root, item)
        if not _is_allowed_app_resource_secret_path(repo_root, target, app_id, resolved):
            raise ValueError(
                f"{ERROR_ID_APP_RESOURCE_SECRET_FILE_SCOPE}: app={app_id} "
                f"secret_file={item} must stay within secrets/hosts/{target}/apps/{app_id}/resources/"
            )
        if not resolved.is_file():
            raise ValueError(f"{ERROR_ID_APP_RESOURCE_SECRET_FILE_MISSING}: app={app_id} secret_file={item}")


def _validate_contract_registry_formal_gate(
    repo_root: Path,
    target: str,
    app_id: str,
    kinds_to_check: set[str],
) -> None:
    _, registry = load_registry(repo_root, target)
    registry_entry = registry.get(app_id)
    if not isinstance(registry_entry, dict):
        raise ValueError(f"{ERROR_ID_APP_RESOURCE_REGISTRY_MISMATCH}: app={app_id} missing in app resource registry")

    filtered_entry = _registry_entry_for_declared_kinds(registry_entry, kinds_to_check=kinds_to_check)
    _validate_contract_registry_secret_files(repo_root, target, app_id, filtered_entry)


def validate_contract(contract_path: Path, *, repo_root: Path, target: str) -> dict[str, Any]:
    payload = _load_yaml(contract_path)
    contract_spec = resolve_delivery_contract_spec(payload)
    contract_mode = contract_spec.contract_mode

    runtime_kind = _nested_get(payload, "runtime.kind")
    if runtime_kind != "compose":
        raise ValueError("当前 app 合同 v1 仅支持 Docker/Compose 路径，runtime.kind 必须为 compose")

    errors: list[str] = []
    required_fields = COMMON_REQUIRED_CONTRACT_FIELDS + (
        V2_REQUIRED_CONTRACT_FIELDS if contract_mode == "v2" else V1_REQUIRED_CONTRACT_FIELDS
    )
    for dotted_key in required_fields:
        value = _nested_get(payload, dotted_key)
        if value in (None, "", [], {}):
            errors.append(dotted_key)

    if errors:
        raise ValueError("合同缺少必填字段: " + ", ".join(errors))

    _validate_image_tag_rule(contract_image_tag_rule(payload))
    if contract_mode == "v2":
        packaging_backend = contract_spec.packaging.backend if contract_spec.packaging is not None else None
        if packaging_backend not in {"native-posix", "wsl-linux", "ssh-linux"}:
            raise ValueError("packaging.backend 只支持 native-posix / wsl-linux / ssh-linux")
    ingress_mode = _ingress_mode(payload)
    if ingress_mode not in {"public", "internal"}:
        raise ValueError("ingress.mode 只支持 public 或 internal")
    if _has_public_ingress(payload) and not _public_sites(payload):
        raise ValueError("合同缺少必填字段: ingress.public_sites")

    depends = _nested_get(payload, "infra.depends_on_containers")
    if not isinstance(depends, list) or any(not isinstance(item, str) or not item.strip() for item in depends):
        raise ValueError("infra.depends_on_containers 必须是非空字符串列表")

    validation_target = contract_validation_target(target)
    _, inventory = _load_inventory(repo_root, validation_target)
    known_containers = _inventory_container_names(inventory)
    unknown_dependencies = [item for item in depends if item not in known_containers]
    if unknown_dependencies:
        raise ValueError("depends_on_containers 引用了未登记容器: " + ", ".join(unknown_dependencies))

    app_id = payload.get("app_id")
    if not isinstance(app_id, str) or not app_id:
        raise ValueError("合同缺少必填字段: app_id")

    tenant_resources = _nested_get(payload, "infra.tenant_resources")
    required_kinds = _tenant_dependency_kinds(depends, inventory)
    tenant_resource_errors = _required_tenant_resource_errors(app_id, required_kinds, tenant_resources)
    if tenant_resource_errors:
        raise ValueError("; ".join(tenant_resource_errors))

    if isinstance(tenant_resources, dict):
        declared_kinds = {
            kind
            for kind in ("postgres", "redis", "minio")
            if isinstance(tenant_resources.get(kind), dict)
        }
        for resource_kind in sorted(declared_kinds):
            resource_spec = tenant_resources.get(resource_kind)
            if isinstance(resource_spec, dict):
                _validate_contract_tenant_secret_file(repo_root, validation_target, app_id, resource_kind, resource_spec)
        if declared_kinds:
            try:
                _validate_contract_registry_formal_gate(
                    repo_root,
                    validation_target,
                    app_id,
                    declared_kinds,
                )
                _validate_contract_tenant_registry_alignment(
                    repo_root,
                    validation_target,
                    app_id,
                    declared_kinds,
                    tenant_resources,
                )
            except FileNotFoundError:
                # App resource registry may be absent in bootstrap/incremental states.
                # Contract-side tenant_resources requirements are still enforced above.
                pass

    container_name = _nested_get(payload, "runtime.container_name")
    if validation_target == "prod0-main" and isinstance(container_name, str) and not container_name.endswith("-prod"):
        raise ValueError("runtime.container_name 必须使用稳定生产容器名并以 -prod 结尾")

    data_mounts = _nested_get(payload, "data.mounts")
    if not isinstance(data_mounts, list) or any(not isinstance(item, dict) for item in data_mounts):
        raise ValueError("data.mounts 必须是对象列表")
    for item in data_mounts:
        host_path = item.get("host_path")
        if not isinstance(host_path, str) or not host_path.startswith("/data/"):
            raise ValueError("data.mounts.host_path 必须收口到 /data/")
    _validate_previous_control_plane(_nested_get(payload, "rollback.previous_control_plane"))

    payload["_meta"] = {
        "contract_file": str(contract_path.resolve()),
        "app_root": str(contract_app_root(contract_path)),
        "target": target,
        "validation_target": validation_target,
        "contract_mode": contract_mode,
        "schema_version": contract_spec.schema_version,
        "artifact_first": contract_mode == "v2",
    }
    return payload


def _split_host_binding(host_binding: str) -> tuple[str, str]:
    host, sep, port = host_binding.rpartition(":")
    if not sep or not port:
        raise ValueError(f"runtime.host_binding 格式不合法: {host_binding}")
    return host or "127.0.0.1", port


def _port_mapping(runtime: dict[str, Any], *, target: str) -> str:
    _, host_port = _split_host_binding(str(runtime["host_binding"]))
    host_ip = "0.0.0.0" if target == "wsl" else "127.0.0.1"
    return f"{host_ip}:{host_port}:{runtime['container_port']}"


def _runtime_base_url(runtime: dict[str, Any], *, target: str) -> str:
    _, host_port = _split_host_binding(str(runtime["host_binding"]))
    host = "127.0.0.1"
    if _is_production_target(target):
        return ""
    return f"http://{host}:{host_port}"


def _healthcheck_url(contract: dict[str, Any], *, target: str) -> str:
    runtime = contract["runtime"]
    health_path = str(runtime["healthcheck"]["path"])
    if target == "wsl":
        return f"{_runtime_base_url(runtime, target=target)}{health_path}"
    public_sites = _public_sites(contract)
    if not public_sites:
        _, host_port = _split_host_binding(str(runtime["host_binding"]))
        return f"http://127.0.0.1:{host_port}{health_path}"
    public_url = str(public_sites[0]["public_url"]).rstrip("/")
    return f"{public_url}{health_path}"


def _origin_health_wait_command(contract: dict[str, Any], *, container_name: str) -> str:
    runtime = contract["runtime"]
    host_port = _split_host_binding(str(runtime["host_binding"]))[1]
    health_path = str(runtime["healthcheck"]["path"])
    health_command = f"curl -fsS http://127.0.0.1:{host_port}{health_path}"
    inspect_format = "{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}"
    return (
        "for i in $(seq 1 12); do "
        f"status=$(docker inspect {container_name} --format '{inspect_format}' 2>/dev/null || true); "
        f"if [ \"$status\" = healthy ]; then {health_command}; exit 0; fi; "
        f"if [ \"$status\" = running ] && {health_command} >/dev/null 2>&1; then {health_command}; exit 0; fi; "
        "sleep 5; "
        "done; "
        f"{health_command}"
    )


def _inventory_public_url(contract: dict[str, Any], *, target: str) -> str:
    if target == "wsl":
        return _runtime_base_url(contract["runtime"], target=target)
    if not _has_public_ingress(contract):
        _, host_port = _split_host_binding(str(contract["runtime"]["host_binding"]))
        return f"internal://127.0.0.1:{host_port}"
    return str(_public_sites(contract)[0]["public_url"])


def _runtime_container_name(app_id: str, runtime: dict[str, Any], *, target: str) -> str:
    return str(runtime["container_name"]) if _is_production_target(target) else f"{app_id}-dev"


def _inventory_host_binding(runtime: dict[str, Any], *, target: str) -> str:
    _, host_port = _split_host_binding(str(runtime["host_binding"]))
    host_ip = "0.0.0.0" if target == "wsl" else "127.0.0.1"
    return f"{host_ip}:{host_port}"


def _target_dependency_names(depends: list[str], *, target: str) -> list[str]:
    if target != "wsl":
        return depends
    target_names: list[str] = []
    for item in depends:
        if item.endswith("-prod"):
            target_names.append(f"{item[:-5]}-dev")
        else:
            target_names.append(item)
    return target_names


def _target_config_files(repo_root: Path, app_id: str, runtime: dict[str, Any], *, target: str) -> list[str]:
    if target == "wsl":
        return [str(_secrets_root(repo_root) / "services" / f"{app_id}.wsl.env")]
    prod0_data_env = _prod0_data_env_path(app_id) if target == "prod0-main" else None
    if prod0_data_env:
        return [prod0_data_env]
    config_files = runtime.get("config_files")
    if isinstance(config_files, list) and config_files:
        return config_files
    return [_remote_env_path(app_id, target)]


def _compose_template_path(repo_root: Path, app_id: str, *, target: str) -> Path:
    if target == "wsl":
        return repo_root / "infra" / "compose" / app_id / "docker-compose.wsl.yml"
    return repo_root / "infra" / "compose" / app_id / _remote_compose_filename(target)


def _target_docker_networks(repo_root: Path, app_id: str, *, target: str) -> list[str]:
    template_path = _compose_template_path(repo_root, app_id, target=target)
    if not template_path.is_file():
        return []
    compose = _load_yaml(template_path)
    service = compose.get("services", {}).get(app_id)
    if not isinstance(service, dict):
        return []
    networks = service.get("networks")
    if not isinstance(networks, list):
        return []
    return [str(item) for item in networks if isinstance(item, str) and item]


def _default_dependency_env(depends: list[str], contract: dict[str, Any], *, target: str) -> dict[str, str]:
    tenant_resources = _nested_get(contract, "infra.tenant_resources")
    if not isinstance(tenant_resources, dict):
        return {}

    target_depends = _target_dependency_names(depends, target=target)
    env: dict[str, str] = {}
    if "postgres" in tenant_resources:
        postgres_host = next((item for item in target_depends if "postgres" in item), "")
        if postgres_host:
            env["DATABASE_HOST"] = postgres_host
    if "redis" in tenant_resources:
        redis_host = next((item for item in target_depends if "redis" in item), "")
        if redis_host:
            env["REDIS_HOST"] = redis_host
    return env


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


def _output_app_resource_summary(app_resource_summary: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(app_resource_summary, dict):
        return {}

    summary: dict[str, dict[str, Any]] = {}
    for kind in ("postgres", "redis", "minio"):
        item = app_resource_summary.get(kind)
        if not isinstance(item, dict):
            continue
        normalized = {key: value for key, value in item.items() if value not in (None, "")}
        if kind == "redis":
            normalized.pop("user", None)
        if normalized:
            summary[kind] = normalized
    return summary


def render_runtime(contract: dict[str, Any], *, repo_root: Path, target: str, image_ref: str | None = None) -> dict[str, Any]:
    template_path = _compose_template_path(repo_root, str(contract["app_id"]), target=target)
    compose = _load_yaml(template_path)
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
            "test": ["CMD-SHELL", f"curl -fsS http://127.0.0.1:{runtime['container_port']}{runtime['healthcheck']['path']} >/dev/null"],
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
        service_key = _nested_get(contract, "inventory.service_key") or contract["app_id"]
        legacy_keys = _nested_get(contract, "inventory.remove_service_keys") or []
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
            "depends_on_containers": _target_dependency_names(contract["infra"]["depends_on_containers"], target=target),
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
            app_resource_summary = build_app_resource_summary(_nested_get(contract, "infra.tenant_resources"))
        if app_resource_summary:
            service_entry["app_resource_summary"] = app_resource_summary
        services[str(service_key)] = service_entry

    if write:
        inventory_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return payload


def _render_server_readme(target: str, inventory: dict[str, Any]) -> str:
    lines = [f"# {target} 摘要", "", "## 身份", ""]
    if "label" in inventory:
        lines.append(f"- 备注：`{inventory['label']}`")
    if "provider" in inventory:
        lines.append(f"- 云厂商：`{inventory['provider']}`")
    if "public_ip" in inventory:
        lines.append(f"- 公网 IPv4：`{inventory['public_ip']}`")
    if "public_domain" in inventory:
        lines.append(f"- 域名：`{inventory['public_domain']}`")
    aliases = inventory.get("ssh", {}).get("aliases", [])
    if aliases:
        lines.append(f"- SSH 别名：`{aliases[0]}`")

    lines.extend(["", "## 应用控制面", ""])
    services = inventory.get("services", {})
    has_app_resource_summary = False
    if isinstance(services, dict):
        for service_name, service in sorted(services.items()):
            if not isinstance(service, dict) or "control_plane" not in service:
                continue
            lines.append(f"- `{service_name}`：`{service.get('control_plane', 'unknown')}` / `{service.get('container_name', '-')}` / `{service.get('public_url', '-')}`")
            depends = service.get("depends_on_containers")
            if isinstance(depends, list) and depends:
                lines.append(f"- 依赖容器：`{', '.join(depends)}`")
            app_resource_summary = _output_app_resource_summary(service.get("app_resource_summary"))
            if app_resource_summary:
                has_app_resource_summary = True
                for kind in ("postgres", "redis", "minio"):
                    item = app_resource_summary.get(kind)
                    if isinstance(item, dict) and item:
                        lines.append(f"- app_resource_summary.{kind}：`{json.dumps(item, ensure_ascii=False, sort_keys=True)}`")

    if target == "prod0-main" and has_app_resource_summary:
        lines.extend(
            [
                "",
                "## App Resource 台账语义",
                "",
                "- `app_resource_summary` 供 prod0 台账与对账使用；只有 Redis 采用共享 runtime 凭据，PostgreSQL/MinIO 继续记录各自租户凭据标识，其中 MinIO 额外登记 bucket-scoped policy 元数据。",
                "- Redis 采用共享 runtime 凭据（shared runtime credential），并通过 DB 级逻辑分区 + key prefix 区分租户，不再把 per-app Redis user 视为活跃运行时依赖。",
                "- MinIO 当前按 bucket-scoped policy 收敛：`policy_name` / `policy_scope` / `isolation_level` 反映控制面登记的对象存储权限边界。",
                "- 这不是强隔离；它仅提供逻辑分区，真实 secret 仍需由受控 secrets 流程单独写入。",
            ]
        )

    lines.extend(
        [
            "",
            "## 资料入口",
            "",
            f"- 结构化清单：`inventory/servers/{target}/inventory.json`",
            f"- 机器真源：`inventory/servers/{target}/inventory.json`",
            f"- 本摘要：`inventory/servers/{target}/README.md`",
            "- README 只保留非敏感摘要，不承载第二真源；脚本消费和对象细节以 JSON 为准。",
        ]
    )
    return "\n".join(lines) + "\n"


def _render_app_summary(contract: dict[str, Any], target: str, inventory_entry: dict[str, Any]) -> str:
    contract_file = str(_nested_get(contract, "_meta.contract_file") or "deploy/agentplane/contract.yaml")
    app_root = Path(str(_nested_get(contract, "_meta.app_root") or "."))
    try:
        contract_label = Path(contract_file).resolve().relative_to(app_root.resolve()).as_posix()
    except ValueError:
        contract_label = _payload_path(contract_file)
    public_url = str(inventory_entry.get("public_url", "-"))
    access_label = "公网入口"
    if public_url.startswith("internal://"):
        access_label = "内网探针"
    lines = [
        f"# {contract['app_id']} AgentPlane 交接摘要",
        "",
        "本文件是应用仓库面向业务开发者的非敏感部署摘要。生产控制面真源在 `AgentPlane` 仓库，而不是当前应用仓库。",
        "",
        f"- 目标环境：`{target}`",
        f"- 控制面：`{inventory_entry.get('control_plane', '-')}`",
        f"- 容器名：`{inventory_entry.get('container_name', '-')}`",
        f"- {access_label}：`{public_url}`",
        f"- 回滚入口：`{_render_rollback_entry(inventory_entry.get('rollback_entry', {}))}`",
    ]
    depends = inventory_entry.get("depends_on_containers")
    if isinstance(depends, list) and depends:
        lines.append(f"- 依赖容器：`{', '.join(depends)}`")
    app_resource_summary = _output_app_resource_summary(inventory_entry.get("app_resource_summary"))
    lines.extend(["", "## App Resource 资源摘要（非敏感）", ""])
    if app_resource_summary:
        for kind in ("postgres", "redis", "minio"):
            item = app_resource_summary.get(kind)
            if isinstance(item, dict) and item:
                lines.append(f"- `{kind}`：`{json.dumps(item, ensure_ascii=False, sort_keys=True)}`")
    else:
        lines.append("- 未登记 app_resource_summary。")
    if target == "prod0-main" and app_resource_summary:
        lines.extend(
            [
                "",
                "## App Resource 语义说明",
                "",
                "- 当前文档中的 `app_resource_summary` 只保留租户识别所需的非敏感信息；PostgreSQL/MinIO 仍按各自租户凭据接入，其中 MinIO 额外记录 bucket-scoped policy 元数据。",
                "- Redis 采用共享 runtime 凭据（shared runtime credential），并通过 DB 级逻辑分区 + key prefix 区分租户；这不是强隔离，也不要求 per-app Redis user 作为活跃运行时依赖。",
                "- MinIO 的 `policy_name` / `policy_scope` / `isolation_level` 仅表达登记后的权限边界，不暴露真实 secret。",
            ]
        )
    lines.extend(["", "## 交付合同", "", f"- 合同文件：`{contract_label}`", "- 正式部署、网站对象、回滚与台账刷新统一在 `AgentPlane` 仓库执行。"])
    return "\n".join(lines) + "\n"


def _preserve_onepanel_ledger_section(existing: str, rendered: str) -> str:
    if ONEPANEL_LEDGER_BEGIN not in existing or ONEPANEL_LEDGER_END not in existing:
        return rendered
    if ONEPANEL_LEDGER_BEGIN in rendered and ONEPANEL_LEDGER_END in rendered:
        return rendered
    before, _, rest = existing.partition(ONEPANEL_LEDGER_BEGIN)
    section_body, _, _after = rest.partition(ONEPANEL_LEDGER_END)
    section = f"{ONEPANEL_LEDGER_BEGIN}{section_body}{ONEPANEL_LEDGER_END}\n"
    return rendered.rstrip() + "\n\n" + section


def _resolve_app_summary_path(contract: dict[str, Any], *, target: str) -> str | None:
    summary_paths = _nested_get(contract, "docs.app_summary_files")
    if isinstance(summary_paths, dict):
        target_path = summary_paths.get(target)
        if isinstance(target_path, str) and target_path:
            return target_path
    summary_path = _nested_get(contract, "docs.app_summary_file")
    if isinstance(summary_path, str) and summary_path:
        return summary_path
    return None


def doc_sync(*, repo_root: Path, target: str, contract_paths: list[Path], write: bool) -> dict[str, Any]:
    inventory_file, inventory = _load_inventory(repo_root, target)
    server_readme = inventory_file.with_name("README.md")
    app_docs: list[str] = []

    if write:
        current_readme = server_readme.read_text(encoding="utf-8") if server_readme.is_file() else ""
        rendered_readme = _preserve_onepanel_ledger_section(current_readme, _render_server_readme(target, inventory))
        server_readme.write_text(rendered_readme, encoding="utf-8")

    for contract_path in contract_paths:
        contract = validate_contract(contract_path, repo_root=repo_root, target=target)
        service_key = _nested_get(contract, "inventory.service_key") or contract["app_id"]
        entry = inventory.get("services", {}).get(service_key, {})
        if not isinstance(entry, dict):
            entry = {}
        summary_path = _resolve_app_summary_path(contract, target=target)
        if isinstance(summary_path, str) and summary_path:
            app_root = Path(contract["_meta"]["app_root"])
            output_file = app_root / summary_path
            app_docs.append(_payload_path(output_file))
            if write:
                output_file.parent.mkdir(parents=True, exist_ok=True)
                output_file.write_text(_render_app_summary(contract, target, entry), encoding="utf-8")

    return {"server_readme": _payload_path(server_readme), "app_docs": app_docs}


def _execute_step(
    *,
    argv: list[str],
    display: str,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    backend_type: str | None = None,
    capabilities: tuple[str, ...] | None = None,
    timeout: int = 300,
) -> dict[str, Any]:
    if backend_type is not None:
        runner = build_backend_runner()
        plan = ExecutionPlan(
            backend_type=backend_type,  # type: ignore[arg-type]
            cwd_ref="step.cwd" if cwd is not None else "",
            argv=tuple(str(item) for item in argv),
            env_refs=("step.env",) if env else (),
            input_refs=(),
            expected_outputs=(),
            capabilities=capabilities or ((str(argv[0]),) if argv else ()),
            timeout=timeout,
        )
        result = runner.execute(
            plan,
            bindings=ExecutionBindings(
                cwd_values={"step.cwd": cwd} if cwd is not None else {},
                env_values={"step.env": env or {}},
            ),
        )
        return redact_execution_payload(result.to_payload())
    result = _run(argv, cwd=cwd, env=env)
    return redact_execution_payload({
        "argv": argv,
        "display": display,
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "ok": result.returncode == 0,
    })


def _production_network_preflight(repo_root: Path, target: str) -> dict[str, Any] | None:
    if not _is_production_target(target):
        return None
    payload = ensure_managed_bridge_networks(repo_root, target)
    if not payload.get("ok", False):
        raise ValueError(f"network ensure failed for {target}")
    return payload


def build_artifact(
    contract: dict[str, Any],
    *,
    repo_root: Path,
    target: str,
    image_tag: str | None,
    auto_version: bool,
    dry_run: bool,
) -> dict[str, Any]:
    contract_spec = require_artifact_first_contract(contract)
    app_root = Path(contract["_meta"]["app_root"])
    output_path = artifact_output_path(app_root, contract_spec)
    if output_path is None:
        raise ValueError("artifact-first 合同缺少 artifact.output_path")
    recommended_versions = _maybe_recommended_versions(contract, repo_root=repo_root)
    if auto_version:
        if recommended_versions is None:
            raise ValueError("无法自动生成版本号；请确认 upstream version 与 git sha 可从应用仓库读取")
        effective_image_tag = str(recommended_versions["image_tag"])
    else:
        effective_image_tag = image_tag or "local"
    image_ref = f"{contract_spec.packaging.image_name}:{effective_image_tag}"
    command = contract_spec.artifact.build_command
    env = os.environ.copy()
    env["IMAGE_TAG"] = effective_image_tag
    env["ARTIFACT_OUTPUT_PATH"] = str(output_path)
    env["ARTIFACT_RUNTIME_OS"] = str(contract_spec.artifact.runtime_os)
    env["ARTIFACT_RUNTIME_ARCH"] = str(contract_spec.artifact.runtime_arch)
    if recommended_versions is not None:
        env["FORK_VERSION"] = str(recommended_versions["fork_version"])
        env["DELIVERY_VERSION"] = str(recommended_versions["delivery_version"])
    op_id = next_operation_id("build-artifact")
    artifact_payload = {
        "output_path": str(output_path),
        "runtime_os": contract_spec.artifact.runtime_os,
        "runtime_arch": contract_spec.artifact.runtime_arch,
    }
    packaging_payload = {
        "backend": contract_spec.packaging.backend,
        "image_ref": image_ref,
        "package_command": contract_spec.packaging.package_command,
    }
    details: dict[str, Any] = {
        "app_id": str(contract["app_id"]),
        "artifact_output_path": str(output_path),
        "image_ref": image_ref,
        "packaging_backend": contract_spec.packaging.backend,
    }
    if recommended_versions is not None:
        details.update(
            {
                "upstream_version": recommended_versions["upstream_version"],
                "fork_version_date": recommended_versions["build_date"],
                "fork_sequence": recommended_versions["fork_sequence"],
                "git_sha": recommended_versions["git_sha"],
                "fork_version": recommended_versions["fork_version"],
                "delivery_version": recommended_versions["delivery_version"],
                "image_tag": recommended_versions["image_tag"],
            }
        )
    if dry_run:
        operation = _record_app_operation(
            repo_root,
            action="build-artifact",
            target=target,
            dry_run=True,
            operation={"op_id": op_id, "target": target, "result": "planned"},
            details=details,
        )
        payload = {
            "artifact": artifact_payload,
            "packaging": packaging_payload,
            "cwd": str(app_root),
            "command": command,
            "dry_run": True,
            "operation": operation,
        }
        if recommended_versions is not None:
            payload["recommended_versions"] = recommended_versions
        return payload
    result = _run_linux_backend_command(
        command,
        cwd=app_root,
        env=env,
        backend=contract_spec.packaging.backend,
    )
    if result.returncode != 0:
        raise ValueError(result.stdout or result.stderr or "build-artifact 执行失败")
    if not output_path.exists():
        raise ValueError(f"build-artifact 未生成预期 artifact 输出: {output_path}")
    operation = _record_app_operation(
        repo_root,
        action="build-artifact",
        target=target,
        dry_run=False,
        operation={"op_id": op_id, "target": target, "result": "artifact-built"},
        details=details,
    )
    payload = {
        "artifact": artifact_payload,
        "packaging": packaging_payload,
        "cwd": str(app_root),
        "command": command,
        "operation": operation,
    }
    if recommended_versions is not None:
        payload["recommended_versions"] = recommended_versions
    return payload


def package_runtime(
    contract: dict[str, Any],
    *,
    repo_root: Path,
    target: str,
    image_tag: str | None,
    auto_version: bool,
    dry_run: bool,
) -> dict[str, Any]:
    contract_spec = require_artifact_first_contract(contract)
    app_root = Path(contract["_meta"]["app_root"])
    output_path = artifact_output_path(app_root, contract_spec)
    if output_path is None:
        raise ValueError("artifact-first 合同缺少 artifact.output_path")
    recommended_versions = _maybe_recommended_versions(contract, repo_root=repo_root)
    if auto_version:
        if recommended_versions is None:
            raise ValueError("无法自动生成版本号；请确认 upstream version 与 git sha 可从应用仓库读取")
        effective_image_tag = str(recommended_versions["image_tag"])
    else:
        effective_image_tag = image_tag or "local"
    image_ref = f"{contract_spec.packaging.image_name}:{effective_image_tag}"
    env = os.environ.copy()
    env["IMAGE_TAG"] = effective_image_tag
    env["IMAGE_REF"] = image_ref
    env["ARTIFACT_OUTPUT_PATH"] = str(output_path)
    env["ARTIFACT_RUNTIME_OS"] = str(contract_spec.artifact.runtime_os)
    env["ARTIFACT_RUNTIME_ARCH"] = str(contract_spec.artifact.runtime_arch)
    if recommended_versions is not None:
        env["FORK_VERSION"] = str(recommended_versions["fork_version"])
        env["DELIVERY_VERSION"] = str(recommended_versions["delivery_version"])
    op_id = next_operation_id("package-runtime")
    payload = {
        "artifact": {
            "output_path": str(output_path),
            "runtime_os": contract_spec.artifact.runtime_os,
            "runtime_arch": contract_spec.artifact.runtime_arch,
        },
        "image_ref": image_ref,
        "backend": contract_spec.packaging.backend,
        "cwd": str(app_root),
        "command": contract_spec.packaging.package_command,
    }
    details: dict[str, Any] = {
        "app_id": str(contract["app_id"]),
        "artifact_output_path": str(output_path),
        "image_ref": image_ref,
        "packaging_backend": contract_spec.packaging.backend,
    }
    if recommended_versions is not None:
        details["image_tag"] = recommended_versions["image_tag"]
    if dry_run:
        operation = _record_app_operation(
            repo_root,
            action="package-runtime",
            target=target,
            dry_run=True,
            operation={"op_id": op_id, "target": target, "result": "planned"},
            details=details,
        )
        payload["dry_run"] = True
        payload["operation"] = operation
        if recommended_versions is not None:
            payload["recommended_versions"] = recommended_versions
        return payload
    if not output_path.exists():
        raise ValueError(f"package-runtime 需要现成 artifact 输出: {output_path}")
    result = _run_linux_backend_command(
        contract_spec.packaging.package_command,
        cwd=app_root,
        env=env,
        backend=contract_spec.packaging.backend,
    )
    if result.returncode != 0:
        raise ValueError(result.stdout or result.stderr or "package-runtime 执行失败")
    operation = _record_app_operation(
        repo_root,
        action="package-runtime",
        target=target,
        dry_run=False,
        operation={"op_id": op_id, "target": target, "result": "packaged"},
        details=details,
    )
    payload["operation"] = operation
    if recommended_versions is not None:
        payload["recommended_versions"] = recommended_versions
    return payload


def _target_ssh_target(repo_root: Path, target: str) -> SshTarget:
    return resolve_ssh_target(repo_root, target)


def _service_env_path(repo_root: Path, app_id: str, target: str) -> Path:
    if target == "wsl":
        return _secrets_root(repo_root) / "services" / f"{app_id}.wsl.env"
    if _is_production_target(target):
        return _secrets_root(repo_root) / "services" / f"{app_id}.{_target_alias(target)}.env"
    raise ValueError(f"Unsupported target for env path: {target}")


def ship_image(contract: dict[str, Any], *, repo_root: Path, target: str, image_ref: str | None, archive_dir: Path, dry_run: bool) -> dict[str, Any]:
    op_id = next_operation_id("ship-image")
    if not image_ref:
        raise ValueError("ship-image 必须显式传入 image_ref")
    effective_image = image_ref
    archive_path = (repo_root / archive_dir / f"{effective_image.replace(':', '_')}.tar").resolve()
    if target == "wsl":
        operation = _record_app_operation(
            repo_root,
            action="ship-image",
            target=target,
            dry_run=dry_run,
            operation={"op_id": op_id, "target": target, "result": "planned" if dry_run else "local-only"},
            details={"artifact": archive_path.name, "image_ref": effective_image},
        )
        return {
            "image_ref": effective_image,
            "archive_path": str(archive_path),
            "target": target,
            "operation": operation,
            "dry_run": dry_run,
        }
    ssh_target = _target_ssh_target(repo_root, target)
    commands = {
        "save": f"docker save -o {shlex.quote(str(archive_path))} {shlex.quote(effective_image)}",
        "scp": ssh_target.display_scp_command(str(archive_path), f"/tmp/{archive_path.name}"),
        "load": ssh_target.display_ssh_command(f"docker load -i /tmp/{archive_path.name}"),
    }
    if dry_run:
        operation = _record_app_operation(
            repo_root,
            action="ship-image",
            target=target,
            dry_run=True,
            operation={"op_id": op_id, "target": target, "artifact": archive_path.name, "result": "planned"},
            details={"artifact": archive_path.name, "image_ref": effective_image},
        )
        return {
            "image_ref": effective_image,
            "archive_path": str(archive_path),
            "target": target,
            "commands": commands,
            "operation": operation,
            "dry_run": True,
        }

    archive_path.parent.mkdir(parents=True, exist_ok=True)
    result = _run(["docker", "save", "-o", str(archive_path), effective_image])
    if result.returncode != 0:
        raise ValueError(result.stdout or result.stderr or "docker save 失败")
    result = _run(ssh_target.local_scp_args(str(archive_path), f"/tmp/{archive_path.name}"))
    if result.returncode != 0:
        raise ValueError(result.stdout or result.stderr or "scp 镜像失败")
    result = _run(ssh_target.local_ssh_args_for_shell(f"docker load -i /tmp/{archive_path.name}"))
    if result.returncode != 0:
        raise ValueError(result.stdout or result.stderr or "远端 docker load 失败")
    operation = _record_app_operation(
        repo_root,
        action="ship-image",
        target=target,
        dry_run=False,
        operation={"op_id": op_id, "target": target, "artifact": archive_path.name, "result": "loaded"},
        details={"artifact": archive_path.name, "image_ref": effective_image},
    )
    return {
        "image_ref": effective_image,
        "archive_path": str(archive_path),
        "target": target,
        "commands": commands,
        "operation": operation,
    }


def deploy_app(
    contract: dict[str, Any], *, repo_root: Path, target: str, image_ref: str | None, dry_run: bool, execute: bool
) -> dict[str, Any]:
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
        wsl_service["env_file"] = [str(env_file_path)]
        rendered_compose = compose_path.parent / f".{compose_path.stem}.{op_id}.rendered.yml"
        rendered_compose.write_text(
            yaml.safe_dump(compose_payload, sort_keys=False, allow_unicode=False),
            encoding="utf-8",
        )
        step = _execute_step(
            argv=["docker", "compose", "-f", str(rendered_compose), "up", "-d", "--pull", "never"],
            display=f"docker compose -f {rendered_compose} up -d --pull never",
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
        ssh_target.display_ssh_command(f"install -Dm600 /tmp/{env_path.name} {remote_env} && rm -f /tmp/{env_path.name}"),
        ssh_target.display_ssh_command(
            f"cd /opt/agentplane/infra/compose/{contract['app_id']} && docker compose -f {remote_compose_name} up -d --pull never"
        ),
    ]
    transition_step = _control_plane_transition_step(repo_root, target=target, rollback_entry=rollback_entry, operate="stop")
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
            ssh_target.local_ssh_args_for_shell(f"install -Dm600 /tmp/{env_path.name} {remote_env} && rm -f /tmp/{env_path.name}"),
            ssh_target.display_ssh_command(f"install -Dm600 /tmp/{env_path.name} {remote_env} && rm -f /tmp/{env_path.name}"),
        ),
    ]
    transition_step = _control_plane_transition_step(repo_root, target=target, rollback_entry=rollback_entry, operate="stop")
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
        operation={"op_id": op_id, "target": target, "artifact_summary": f"{contract['app_id']} compose + {env_path.name}", "result": "executed" if ok else "failed"},
        details={"artifact_summary": f"{contract['app_id']} compose + {env_path.name}", "remote_env": remote_env, "remote_compose": remote_compose},
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


def verify_app(contract: dict[str, Any], *, repo_root: Path, target: str, dry_run: bool, execute: bool) -> dict[str, Any]:
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
    if _has_public_ingress(contract):
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
    if _has_public_ingress(contract):
        public_root = str(_public_sites(contract)[0]["public_url"]).rstrip("/")
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
        operation={"op_id": op_id, "target": target, "artifact_summary": container_name, "result": "verified" if ok else "failed"},
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


def rollback_app(contract: dict[str, Any], *, repo_root: Path, target: str, dry_run: bool, execute: bool) -> dict[str, Any]:
    op_id = next_operation_id("rollback-app")
    rollback_entry = contract["rollback"]["previous_control_plane"]
    local_backend = _local_backend_type()
    if target == "wsl":
        operation = _record_app_operation(
            repo_root,
            action="rollback",
            target=target,
            dry_run=dry_run,
            operation={"op_id": op_id, "target": target, "result": "planned" if dry_run else "local-only"},
            details={"artifact_summary": rollback_entry.get("kind", "unknown")},
        )
        return {
            "rollback_entry": rollback_entry,
            "operation": operation,
            "dry_run": dry_run,
        }
    if execute and dry_run:
        raise ValueError("rollback 不允许同时传 --dry-run 和 --execute")
    if rollback_entry.get("kind") == "none":
        operation = _record_app_operation(
            repo_root,
            action="rollback",
            target=target,
            dry_run=dry_run,
            operation={"op_id": op_id, "target": target, "result": "noop"},
            details={"artifact_summary": rollback_entry.get("kind", "none")},
        )
        return {
            "rollback_entry": rollback_entry,
            "commands": [],
            "warning": _render_rollback_entry(rollback_entry),
            "operation": operation,
            "dry_run": dry_run,
            "ok": True,
        }
    ssh_target = _target_ssh_target(repo_root, target)
    transition_step = _control_plane_transition_step(repo_root, target=target, rollback_entry=rollback_entry, operate="start")
    commands = [
        ssh_target.display_ssh_command(f"cd /opt/agentplane/infra/compose/{contract['app_id']} && docker compose -f {_remote_compose_filename(target)} down || true"),
        transition_step[1] if transition_step else None,
    ]
    commands = [command for command in commands if command]
    if not execute:
        operation = _record_app_operation(
            repo_root,
            action="rollback",
            target=target,
            dry_run=dry_run,
            operation={
                "op_id": op_id,
                "target": target,
                "artifact_summary": rollback_entry.get("kind", "unknown"),
                "result": "planned",
            },
            details={"artifact_summary": rollback_entry.get("kind", "unknown")},
        )
        return {
            "rollback_entry": rollback_entry,
            "commands": commands,
            "operation": operation,
            "dry_run": dry_run,
        }
    steps = [
        (
            ssh_target.local_ssh_args_for_shell(f"cd /opt/agentplane/infra/compose/{contract['app_id']} && docker compose -f {_remote_compose_filename(target)} down || true"),
            ssh_target.display_ssh_command(f"cd /opt/agentplane/infra/compose/{contract['app_id']} && docker compose -f {_remote_compose_filename(target)} down || true"),
        ),
    ]
    if transition_step:
        steps.append(transition_step)
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
        action="rollback",
        target=target,
        dry_run=False,
        operation={
            "op_id": op_id,
            "target": target,
            "artifact_summary": rollback_entry.get("kind", "unknown"),
            "result": "rolled-back" if ok else "failed",
        },
        details={"artifact_summary": rollback_entry.get("kind", "unknown")},
    )
    return {
        "rollback_entry": rollback_entry,
        "commands": [display for _, display in steps],
        "results": step_results,
        "operation": operation,
        "dry_run": False,
        "ok": ok,
    }
