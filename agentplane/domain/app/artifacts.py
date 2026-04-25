from __future__ import annotations

from pathlib import Path
from typing import Any

from agentplane.domain.app.models import DeliveryArtifactSpec, DeliveryContractSpec, DeliveryPackagingSpec

LATEST_SUPPORTED_CONTRACT_SCHEMA_VERSION = 2
SUPPORTED_CONTRACT_SCHEMA_VERSIONS = (1, LATEST_SUPPORTED_CONTRACT_SCHEMA_VERSION)
SUPPORTED_PACKAGING_BACKENDS = frozenset({"native-posix", "wsl-linux", "ssh-linux"})


def _read_mapping(payload: Any) -> dict[str, Any]:
    return payload if isinstance(payload, dict) else {}


def _read_str(payload: dict[str, Any], key: str) -> str | None:
    value = payload.get(key)
    if not isinstance(value, str):
        return None
    trimmed = value.strip()
    return trimmed or None


def detect_contract_mode(payload: dict[str, Any]) -> tuple[str, int | None]:
    schema_version = payload.get("schema_version")
    if schema_version is None:
        return "legacy", None
    if schema_version == 1:
        return "v1", 1
    if schema_version == LATEST_SUPPORTED_CONTRACT_SCHEMA_VERSION:
        return "v2", LATEST_SUPPORTED_CONTRACT_SCHEMA_VERSION
    raise ValueError(
        "schema_version="
        f"{schema_version} 不受支持；当前仅支持 schema_version: "
        f"{', '.join(str(item) for item in SUPPORTED_CONTRACT_SCHEMA_VERSIONS)}"
    )


def resolve_delivery_contract_spec(payload: dict[str, Any]) -> DeliveryContractSpec:
    contract_mode, schema_version = detect_contract_mode(payload)
    artifact_payload = _read_mapping(payload.get("artifact"))
    packaging_payload = _read_mapping(payload.get("packaging"))

    artifact = DeliveryArtifactSpec(
        build_command=_read_str(artifact_payload, "build_command"),
        output_path=_read_str(artifact_payload, "output_path"),
        runtime_os=_read_str(artifact_payload, "runtime_os"),
        runtime_arch=_read_str(artifact_payload, "runtime_arch"),
    )

    packaging: DeliveryPackagingSpec | None = None
    if contract_mode == "v2" or packaging_payload:
        packaging = DeliveryPackagingSpec(
            backend=_read_str(packaging_payload, "backend"),
            image_name=_read_str(packaging_payload, "image_name"),
            image_tag_rule=_read_str(packaging_payload, "image_tag_rule"),
            package_command=_read_str(packaging_payload, "package_command"),
        )
    elif artifact_payload:
        packaging = DeliveryPackagingSpec(
            backend=None,
            image_name=_read_str(artifact_payload, "image_name"),
            image_tag_rule=_read_str(artifact_payload, "image_tag_rule"),
            package_command=_read_str(artifact_payload, "build_command"),
        )

    return DeliveryContractSpec(
        contract_mode=contract_mode,
        schema_version=schema_version if schema_version is not None else "legacy",
        artifact=artifact,
        packaging=packaging,
    )


def contract_image_name(payload: dict[str, Any]) -> str | None:
    spec = resolve_delivery_contract_spec(payload)
    if spec.packaging is not None:
        return spec.packaging.image_name
    return None


def contract_image_tag_rule(payload: dict[str, Any]) -> str | None:
    spec = resolve_delivery_contract_spec(payload)
    if spec.packaging is not None:
        return spec.packaging.image_tag_rule
    return None


def artifact_output_path(app_root: Path, spec: DeliveryContractSpec) -> Path | None:
    if spec.artifact.output_path is None:
        return None
    return (app_root / spec.artifact.output_path).resolve()


def require_artifact_first_contract(payload: dict[str, Any]) -> DeliveryContractSpec:
    spec = resolve_delivery_contract_spec(payload)
    if spec.contract_mode != "v2":
        raise ValueError("build-artifact/package-runtime 仅支持 schema_version: 2 的 artifact-first 合同")
    if spec.packaging is None:
        raise ValueError("schema_version: 2 合同缺少 packaging 段")
    missing: list[str] = []
    if spec.artifact.build_command is None:
        missing.append("artifact.build_command")
    if spec.artifact.output_path is None:
        missing.append("artifact.output_path")
    if spec.artifact.runtime_os is None:
        missing.append("artifact.runtime_os")
    if spec.artifact.runtime_arch is None:
        missing.append("artifact.runtime_arch")
    if spec.packaging.backend is None:
        missing.append("packaging.backend")
    if spec.packaging.image_name is None:
        missing.append("packaging.image_name")
    if spec.packaging.image_tag_rule is None:
        missing.append("packaging.image_tag_rule")
    if spec.packaging.package_command is None:
        missing.append("packaging.package_command")
    if missing:
        raise ValueError("artifact-first 合同缺少必填字段: " + ", ".join(missing))
    if spec.packaging.backend not in SUPPORTED_PACKAGING_BACKENDS:
        raise ValueError("packaging.backend 只支持: " + ", ".join(sorted(SUPPORTED_PACKAGING_BACKENDS)))
    return spec
