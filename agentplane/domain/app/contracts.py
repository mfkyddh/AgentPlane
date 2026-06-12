from __future__ import annotations

from pathlib import Path
from typing import Any

from agentplane.domain.app.artifacts import contract_image_tag_rule, resolve_delivery_contract_spec
from agentplane.domain.app.contracts_helpers import (
    APP_DELIVERY_CONTRACT_SCHEMA_V2,
    COMMON_REQUIRED_CONTRACT_FIELDS,
    ERROR_ID_APP_RESOURCE_REGISTRY_MISMATCH,
    ERROR_ID_APP_RESOURCE_RESOURCES_REQUIRED,
    ERROR_ID_APP_RESOURCE_SECRET_FILE_MISSING,
    ERROR_ID_APP_RESOURCE_SECRET_FILE_SCOPE,
    ERROR_ID_CONTRACT_INVALID_DATA_MOUNT,
    ERROR_ID_CONTRACT_INVALID_DEPENDENCY,
    ERROR_ID_CONTRACT_INVALID_IMAGE_TAG_RULE,
    ERROR_ID_CONTRACT_INVALID_INGRESS,
    ERROR_ID_CONTRACT_INVALID_PACKAGING_BACKEND,
    ERROR_ID_CONTRACT_INVALID_ROLLBACK,
    ERROR_ID_CONTRACT_MISSING_FIELDS,
    ERROR_ID_CONTRACT_UNSUPPORTED_RUNTIME,
    SUPPORTED_IMAGE_TAG_RULE,
    V1_REQUIRED_CONTRACT_FIELDS,
    V2_REQUIRED_CONTRACT_FIELDS,
    _contract_error,
    _validate_image_tag_rule,
    contract_app_root,
    contract_validation_target,
    has_public_ingress,
    ingress_mode,
    load_yaml,
    nested_get,
    public_sites,
)
from agentplane.domain.app.contracts_validation import (
    _inventory_container_names,
    _load_inventory,
    _registry_entry_for_declared_kinds,
    _required_tenant_resource_errors,
    _tenant_dependency_kinds,
    _validate_contract_registry_formal_gate,
    _validate_contract_tenant_registry_alignment,
    _validate_contract_tenant_secret_file,
    _validate_previous_control_plane,
)

__all__ = [
    "APP_DELIVERY_CONTRACT_SCHEMA_V2",
    "COMMON_REQUIRED_CONTRACT_FIELDS",
    "ERROR_ID_CONTRACT_INVALID_DATA_MOUNT",
    "ERROR_ID_CONTRACT_INVALID_DEPENDENCY",
    "ERROR_ID_CONTRACT_INVALID_IMAGE_TAG_RULE",
    "ERROR_ID_CONTRACT_INVALID_INGRESS",
    "ERROR_ID_CONTRACT_INVALID_PACKAGING_BACKEND",
    "ERROR_ID_CONTRACT_INVALID_ROLLBACK",
    "ERROR_ID_CONTRACT_MISSING_FIELDS",
    "ERROR_ID_CONTRACT_UNSUPPORTED_RUNTIME",
    "ERROR_ID_APP_RESOURCE_REGISTRY_MISMATCH",
    "ERROR_ID_APP_RESOURCE_RESOURCES_REQUIRED",
    "ERROR_ID_APP_RESOURCE_SECRET_FILE_MISSING",
    "ERROR_ID_APP_RESOURCE_SECRET_FILE_SCOPE",
    "SUPPORTED_IMAGE_TAG_RULE",
    "V1_REQUIRED_CONTRACT_FIELDS",
    "V2_REQUIRED_CONTRACT_FIELDS",
    "_contract_error",
    "_inventory_container_names",
    "_load_inventory",
    "_registry_entry_for_declared_kinds",
    "_required_tenant_resource_errors",
    "_tenant_dependency_kinds",
    "_validate_contract_registry_formal_gate",
    "_validate_contract_tenant_registry_alignment",
    "_validate_contract_tenant_secret_file",
    "_validate_image_tag_rule",
    "_validate_previous_control_plane",
    "contract_app_root",
    "contract_validation_target",
    "has_public_ingress",
    "ingress_mode",
    "load_yaml",
    "nested_get",
    "public_sites",
    "validate_contract",
    "validate_contract_standalone",
]


def _validate_contract_core(
    payload: dict[str, Any],
    contract_path: Path,
    contract_spec: Any,
    contract_mode: str,
    *,
    repo_root: Path | None = None,
    target: str | None = None,
) -> dict[str, Any]:
    """Core validation logic shared by validate_contract and validate_contract_standalone."""
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

    app_id = payload.get("app_id")
    if not isinstance(app_id, str) or not app_id:
        raise _contract_error(ERROR_ID_CONTRACT_MISSING_FIELDS, "合同缺少必填字段: app_id")

    # Inventory-dependent validation (optional in standalone mode)
    if repo_root is not None and target is not None:
        validation_target = contract_validation_target(target)
        _, inventory = _load_inventory(repo_root, validation_target)
        known_containers = _inventory_container_names(inventory)
        unknown_dependencies = [item for item in depends if item not in known_containers]
        if unknown_dependencies:
            raise _contract_error(
                ERROR_ID_CONTRACT_INVALID_DEPENDENCY,
                "depends_on_containers 引用了未登记容器: " + ", ".join(unknown_dependencies),
            )

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

    validation_target = contract_validation_target(target) if target else "standalone"
    payload["_meta"] = {
        "contract_file": str(contract_path.resolve()),
        "app_root": str(contract_app_root(contract_path)),
        "target": target or "standalone",
        "validation_target": validation_target,
        "contract_mode": contract_mode,
        "schema_version": contract_spec.schema_version,
        "schema_document": APP_DELIVERY_CONTRACT_SCHEMA_V2 if contract_mode == "v2" else None,
        "artifact_first": contract_mode == "v2",
    }
    return payload


def validate_contract_standalone(
    contract_path: Path,
    *,
    repo_root: Path | None = None,
    target: str | None = None,
) -> dict[str, Any]:
    """Standalone contract validation: does not require inventory.

    Args:
        contract_path: Path to contract.yaml file.
        repo_root: Optional repo root for inventory-dependent validation.
        target: Optional target for inventory-dependent validation.

    Returns:
        Validated contract payload with _meta section.
    """
    payload = load_yaml(contract_path)
    contract_spec = resolve_delivery_contract_spec(payload)
    contract_mode = contract_spec.contract_mode
    return _validate_contract_core(payload, contract_path, contract_spec, contract_mode, repo_root=repo_root, target=target)


def validate_contract(contract_path: Path, *, repo_root: Path, target: str) -> dict[str, Any]:
    """Full contract validation with inventory dependency."""
    payload = load_yaml(contract_path)
    contract_spec = resolve_delivery_contract_spec(payload)
    contract_mode = contract_spec.contract_mode
    return _validate_contract_core(payload, contract_path, contract_spec, contract_mode, repo_root=repo_root, target=target)
