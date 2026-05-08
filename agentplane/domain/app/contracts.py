from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml
from agentplane.domain.app.artifacts import contract_image_tag_rule, resolve_delivery_contract_spec
from agentplane.domain.app.resource_paths import app_resource_secret_dir, resolve_secret_file_path
from agentplane.domain.app.resource_state import APP_RESOURCE_SUMMARY_FIELDS, load_registry, registry_secret_file

ERROR_ID_APP_RESOURCE_RESOURCES_REQUIRED = "app.resource.resources_required"
ERROR_ID_APP_RESOURCE_SECRET_FILE_SCOPE = "app.resource.secret_file_scope"
ERROR_ID_APP_RESOURCE_SECRET_FILE_MISSING = "app.resource.secret_file_missing"
ERROR_ID_APP_RESOURCE_REGISTRY_MISMATCH = "app.resource.registry_mismatch"
ERROR_ID_CONTRACT_MISSING_FIELDS = "app.delivery.contract.missing_fields"
ERROR_ID_CONTRACT_UNSUPPORTED_RUNTIME = "app.delivery.contract.unsupported_runtime"
ERROR_ID_CONTRACT_INVALID_IMAGE_TAG_RULE = "app.delivery.contract.invalid_image_tag_rule"
ERROR_ID_CONTRACT_INVALID_PACKAGING_BACKEND = "app.delivery.contract.invalid_packaging_backend"
ERROR_ID_CONTRACT_INVALID_INGRESS = "app.delivery.contract.invalid_ingress"
ERROR_ID_CONTRACT_INVALID_DEPENDENCY = "app.delivery.contract.invalid_dependency"
ERROR_ID_CONTRACT_INVALID_ROLLBACK = "app.delivery.contract.invalid_rollback"
ERROR_ID_CONTRACT_INVALID_DATA_MOUNT = "app.delivery.contract.invalid_data_mount"
APP_DELIVERY_CONTRACT_SCHEMA_V2 = "docs/archive/reference/schemas/app-delivery-contract-v2.schema.json"
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


def _contract_error(error_id: str, message: str) -> ValueError:
    return ValueError(f"{error_id}: {message}")


def contract_app_root(contract_path: Path) -> Path:
    resolved = contract_path.resolve()
    if resolved.parent.name in {"op", "agentplane"} and resolved.parent.parent.name == "deploy":
        return resolved.parents[2]
    return resolved.parent


def contract_validation_target(target: str) -> str:
    return target


def load_yaml(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} 必须解析为对象")
    return payload


def nested_get(payload: dict[str, Any], dotted_key: str) -> Any:
    current: Any = payload
    for item in dotted_key.split("."):
        if not isinstance(current, dict) or item not in current:
            return None
        current = current[item]
    return current


def ingress_mode(contract: dict[str, Any]) -> str:
    ingress = contract.get("ingress")
    if not isinstance(ingress, dict):
        return "public"
    raw_mode = ingress.get("mode")
    if raw_mode in (None, ""):
        return "public"
    return str(raw_mode)


def public_sites(contract: dict[str, Any]) -> list[dict[str, Any]]:
    ingress = contract.get("ingress")
    if not isinstance(ingress, dict):
        return []
    raw_public_sites = ingress.get("public_sites")
    if not isinstance(raw_public_sites, list):
        return []
    return [item for item in raw_public_sites if isinstance(item, dict)]


def has_public_ingress(contract: dict[str, Any]) -> bool:
    return ingress_mode(contract) != "internal"


def _validate_image_tag_rule(rule: Any) -> None:
    if not isinstance(rule, str) or rule != SUPPORTED_IMAGE_TAG_RULE:
        raise _contract_error(
            ERROR_ID_CONTRACT_INVALID_IMAGE_TAG_RULE,
            f"image_tag_rule 必须使用当前二开版本规范: {SUPPORTED_IMAGE_TAG_RULE}",
        )


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


def validate_contract(contract_path: Path, *, repo_root: Path, target: str) -> dict[str, Any]:
    payload = load_yaml(contract_path)
    contract_spec = resolve_delivery_contract_spec(payload)
    contract_mode = contract_spec.contract_mode

    runtime_kind = nested_get(payload, "runtime.kind")
    if runtime_kind != "compose":
        raise _contract_error(
            ERROR_ID_CONTRACT_UNSUPPORTED_RUNTIME,
            "当前 app 合同 v2 仅支持 Docker/Compose 路径，runtime.kind 必须为 compose",
        )

    errors: list[str] = []
    required_fields = COMMON_REQUIRED_CONTRACT_FIELDS + (
        V2_REQUIRED_CONTRACT_FIELDS if contract_mode == "v2" else V1_REQUIRED_CONTRACT_FIELDS
    )
    for dotted_key in required_fields:
        value = nested_get(payload, dotted_key)
        if value in (None, "", [], {}):
            errors.append(dotted_key)

    if errors:
        raise _contract_error(ERROR_ID_CONTRACT_MISSING_FIELDS, "合同缺少必填字段: " + ", ".join(errors))

    _validate_image_tag_rule(contract_image_tag_rule(payload))
    if contract_mode == "v2":
        packaging_backend = contract_spec.packaging.backend if contract_spec.packaging is not None else None
        if packaging_backend not in {"native-posix", "wsl-linux", "ssh-linux"}:
            raise _contract_error(
                ERROR_ID_CONTRACT_INVALID_PACKAGING_BACKEND,
                "packaging.backend 只支持 native-posix / wsl-linux / ssh-linux",
            )
    raw_ingress_mode = ingress_mode(payload)
    if raw_ingress_mode not in {"public", "internal"}:
        raise _contract_error(ERROR_ID_CONTRACT_INVALID_INGRESS, "ingress.mode 只支持 public 或 internal")
    if has_public_ingress(payload) and not public_sites(payload):
        raise _contract_error(ERROR_ID_CONTRACT_MISSING_FIELDS, "合同缺少必填字段: ingress.public_sites")

    depends = nested_get(payload, "infra.depends_on_containers")
    if not isinstance(depends, list) or any(not isinstance(item, str) or not item.strip() for item in depends):
        raise _contract_error(
            ERROR_ID_CONTRACT_INVALID_DEPENDENCY,
            "infra.depends_on_containers 必须是非空字符串列表",
        )

    validation_target = contract_validation_target(target)
    _, inventory = _load_inventory(repo_root, validation_target)
    known_containers = _inventory_container_names(inventory)
    unknown_dependencies = [item for item in depends if item not in known_containers]
    if unknown_dependencies:
        raise _contract_error(
            ERROR_ID_CONTRACT_INVALID_DEPENDENCY,
            "depends_on_containers 引用了未登记容器: " + ", ".join(unknown_dependencies),
        )

    app_id = payload.get("app_id")
    if not isinstance(app_id, str) or not app_id:
        raise _contract_error(ERROR_ID_CONTRACT_MISSING_FIELDS, "合同缺少必填字段: app_id")

    tenant_resources = nested_get(payload, "infra.tenant_resources")
    required_kinds = _tenant_dependency_kinds(depends, inventory)
    tenant_resource_errors = _required_tenant_resource_errors(app_id, required_kinds, tenant_resources)
    if tenant_resource_errors:
        raise ValueError("; ".join(tenant_resource_errors))

    if isinstance(tenant_resources, dict):
        declared_kinds = {
            kind for kind in ("postgres", "redis", "minio") if isinstance(tenant_resources.get(kind), dict)
        }
        for resource_kind in sorted(declared_kinds):
            resource_spec = tenant_resources.get(resource_kind)
            if isinstance(resource_spec, dict):
                _validate_contract_tenant_secret_file(
                    repo_root, validation_target, app_id, resource_kind, resource_spec
                )
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

    container_name = nested_get(payload, "runtime.container_name")
    if validation_target == "prod0-main" and isinstance(container_name, str) and not container_name.endswith("-prod"):
        raise _contract_error(
            ERROR_ID_CONTRACT_UNSUPPORTED_RUNTIME,
            "runtime.container_name 必须使用稳定生产容器名并以 -prod 结尾",
        )

    data_mounts = nested_get(payload, "data.mounts")
    if not isinstance(data_mounts, list) or any(not isinstance(item, dict) for item in data_mounts):
        raise _contract_error(ERROR_ID_CONTRACT_INVALID_DATA_MOUNT, "data.mounts 必须是对象列表")
    for item in data_mounts:
        host_path = item.get("host_path")
        if not isinstance(host_path, str) or not host_path.startswith("/data/"):
            raise _contract_error(ERROR_ID_CONTRACT_INVALID_DATA_MOUNT, "data.mounts.host_path 必须收口到 /data/")
    _validate_previous_control_plane(nested_get(payload, "rollback.previous_control_plane"))

    payload["_meta"] = {
        "contract_file": str(contract_path.resolve()),
        "app_root": str(contract_app_root(contract_path)),
        "target": target,
        "validation_target": validation_target,
        "contract_mode": contract_mode,
        "schema_version": contract_spec.schema_version,
        "schema_document": APP_DELIVERY_CONTRACT_SCHEMA_V2 if contract_mode == "v2" else None,
        "artifact_first": contract_mode == "v2",
    }
    return payload
