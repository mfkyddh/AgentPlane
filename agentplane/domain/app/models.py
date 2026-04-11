from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AppCatalogEntry:
    app: str
    repo_name: str
    repo_root: Path
    service_key: str
    contracts: dict[str, str]


@dataclass(frozen=True)
class AppObject:
    app: str
    target: str
    repo_name: str
    repo_root: Path
    service_key: str
    contract_file: Path


@dataclass(frozen=True)
class DeliveryArtifactSpec:
    build_command: str | None
    output_path: str | None
    runtime_os: str | None
    runtime_arch: str | None


@dataclass(frozen=True)
class DeliveryPackagingSpec:
    backend: str | None
    image_name: str | None
    image_tag_rule: str | None
    package_command: str | None


@dataclass(frozen=True)
class DeliveryContractSpec:
    contract_mode: str
    schema_version: int | str | None
    artifact: DeliveryArtifactSpec
    packaging: DeliveryPackagingSpec | None
