from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agentplane.domain.app.contracts_helpers import (
    ERROR_ID_APP_RESOURCE_REGISTRY_MISMATCH,
    ERROR_ID_APP_RESOURCE_RESOURCES_REQUIRED,
    ERROR_ID_APP_RESOURCE_SECRET_FILE_MISSING,
    ERROR_ID_APP_RESOURCE_SECRET_FILE_SCOPE,
    ERROR_ID_CONTRACT_INVALID_ROLLBACK,
    _contract_error,
)
from agentplane.domain.app.resource_paths import app_resource_secret_dir, resolve_secret_file_path
from agentplane.domain.app.resource_state import APP_RESOURCE_SUMMARY_FIELDS, load_registry, registry_secret_file


def _load_inventory(repo_root: Path, target: str) -> tuple[Path, dict[str, Any]]:
    inventory_file = repo_root / "inventory" / "servers" / target / "inventory.json"
    if not inventory_file.exists():
        raise ValueError(f"缺少 inventory 文件: {inventory_file}")
    payload = json.loads(inventory_file.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"inventory 顶层必须是对象: {inventory_file}")
    return inventory_file, payload


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


def _is_allowed_app_resource_secret_path(repo_root: Path, target: str, app_id: str, resolved: Path) -> bool:
    canonical_root = app_resource_secret_dir(repo_root, target, app_id).resolve(strict=False)
    return resolved.is_relative_to(canonical_root)


def _validate_previous_control_plane(rollback_entry: Any) -> None:
    if not isinstance(rollback_entry, dict):
        raise _contract_error(ERROR_ID_CONTRACT_INVALID_ROLLBACK, "rollback.previous_control_plane 必须是对象")
    kind = rollback_entry.get("kind")
    if kind == "none":
        return
    if kind == "systemd":
        service_name = rollback_entry.get("service_name")
        if not isinstance(service_name, str) or not service_name:
            raise _contract_error(
                ERROR_ID_CONTRACT_INVALID_ROLLBACK,
                f"rollback.previous_control_plane.kind=systemd 缺少 service_name: {rollback_entry}",
            )
        return
    if kind == "1panel-app":
        install_id = rollback_entry.get("install_id")
        app_key = rollback_entry.get("app_key")
        if install_id is None and (not isinstance(app_key, str) or not app_key):
            raise _contract_error(
                ERROR_ID_CONTRACT_INVALID_ROLLBACK,
                f"rollback.previous_control_plane.kind=1panel-app 缺少 install_id/app_key: {rollback_entry}",
            )
        return
    if kind == "1panel-compose":
        project_name = rollback_entry.get("project_name")
        if not isinstance(project_name, str) or not project_name:
            raise _contract_error(
                ERROR_ID_CONTRACT_INVALID_ROLLBACK,
                f"rollback.previous_control_plane.kind=1panel-compose 缺少 project_name: {rollback_entry}",
            )
        for field in ("container_name", "project_path", "compose_file"):
            value = rollback_entry.get(field)
            if value is None:
                continue
            if not isinstance(value, str) or not value:
                raise _contract_error(
                    ERROR_ID_CONTRACT_INVALID_ROLLBACK,
                    f"rollback.previous_control_plane.kind=1panel-compose {field} 必须是非空字符串: {rollback_entry}",
                )
        return
    raise _contract_error(ERROR_ID_CONTRACT_INVALID_ROLLBACK, f"不支持的 rollback.previous_control_plane.kind: {kind}")


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


def _required_tenant_resource_errors(app_id: str, required_kinds: set[str], tenant_resources: Any) -> list[str]:
    if not required_kinds:
        return []
    if not isinstance(tenant_resources, dict):
        return [f"{ERROR_ID_APP_RESOURCE_RESOURCES_REQUIRED}: app={app_id} missing infra.tenant_resources"]

    missing = [kind for kind in sorted(required_kinds) if not isinstance(tenant_resources.get(kind), dict)]
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
