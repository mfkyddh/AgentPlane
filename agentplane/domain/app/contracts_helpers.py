from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

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
APP_DELIVERY_CONTRACT_SCHEMA_V2 = "docs/schemas/app-delivery-contract-v2.schema.json"
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
