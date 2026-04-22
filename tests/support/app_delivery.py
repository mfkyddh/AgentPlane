from __future__ import annotations

import json
import subprocess
from pathlib import Path

import yaml

from tests.support.app_resources import resource_relative, resource_root
from tests.support.cli import run_agentplane_cli


def run_app_delivery_cli(
    action: str,
    *,
    repo_root: Path,
    app: str,
    target: str = "prod0-main",
    extra_args: tuple[str, ...] = (),
) -> subprocess.CompletedProcess[str]:
    return run_agentplane_cli(
        "app",
        "delivery",
        action,
        "--target",
        target,
        "--app",
        app,
        "--repo-root",
        str(repo_root),
        *extra_args,
    )


def write_inventory(root: Path) -> Path:
    payload = {
        "ssh": {"aliases": ["prod0-main"], "user": "root"},
        "services": {
            "postgres": {"container_name": "postgres18-prod"},
            "redis": {"container_name": "redis7-prod"},
            "minio": {"container_name": "minio-prod"},
        },
    }
    inventory_file = root / "inventory" / "servers" / "prod0-main" / "inventory.json"
    inventory_file.parent.mkdir(parents=True, exist_ok=True)
    inventory_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    wsl_inventory_file = root / "inventory" / "servers" / "wsl" / "inventory.json"
    wsl_inventory_file.parent.mkdir(parents=True, exist_ok=True)
    wsl_inventory_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return inventory_file


def baseline_tenant_resources(*, target: str = "prod0-main", include_minio: bool = False) -> dict[str, object]:
    if target == "wsl":
        postgres_database = "sub2api_wsl"
        postgres_user = "sub2api_wsl"
        redis_key_prefix = "sub2api:wsl:"
        minio_bucket = "wsl-sub2api"
        minio_access_key = "sub2api_wsl"
        minio_policy_name = "wsl-sub2api-rw"
        secret_target = "wsl"
    else:
        postgres_database = "sub2api_prod0"
        postgres_user = "sub2api_prod0"
        redis_key_prefix = "sub2api:"
        minio_bucket = "prod0-sub2api"
        minio_access_key = "sub2api_prod0"
        minio_policy_name = "prod0-sub2api-rw"
        secret_target = "prod0-main"
    resources: dict[str, object] = {
        "postgres": {
            "required": True,
            "database": postgres_database,
            "user": postgres_user,
            "secret_file": resource_relative(secret_target, "sub2api", "postgres"),
        },
        "redis": {
            "required": True,
            "db": 1,
            "key_prefix": redis_key_prefix,
            "secret_file": resource_relative(secret_target, "sub2api", "redis"),
        },
    }
    if include_minio:
        resources["minio"] = {
            "required": True,
            "bucket": minio_bucket,
            "access_key": minio_access_key,
            "policy_name": minio_policy_name,
            "policy_scope": "bucket-only",
            "isolation_level": "bucket-scoped-rw",
            "secret_file": resource_relative(secret_target, "sub2api", "minio"),
        }
    return resources


def write_tenant_secret_files(root: Path, *, target: str = "prod0-main", include_minio: bool = False) -> None:
    tenant_root = resource_root(root, target, "sub2api")
    tenant_root.mkdir(parents=True, exist_ok=True)
    if target == "wsl":
        postgres_database = "sub2api_wsl"
        postgres_user = "sub2api_wsl"
        redis_key_prefix = "sub2api:wsl:"
        minio_bucket = "wsl-sub2api"
        minio_access_key = "sub2api_wsl"
    else:
        postgres_database = "sub2api_prod0"
        postgres_user = "sub2api_prod0"
        redis_key_prefix = "sub2api:"
        minio_bucket = "prod0-sub2api"
        minio_access_key = "sub2api_prod0"
    (tenant_root / "postgres.env").write_text(
        f"PGDATABASE={postgres_database}\nPGUSER={postgres_user}\n",
        encoding="utf-8",
    )
    (tenant_root / "redis.env").write_text(
        f"REDIS_DB=1\nREDIS_KEY_PREFIX={redis_key_prefix}\n",
        encoding="utf-8",
    )
    if include_minio:
        (tenant_root / "minio.env").write_text(
            f"S3_BUCKET={minio_bucket}\nS3_ACCESS_KEY={minio_access_key}\nS3_SECRET_KEY=sub2api-s3-secret\n",
            encoding="utf-8",
        )


def _write_app_catalog_entry(root: Path, contract_file: Path) -> None:
    catalog_file = root / "inventory" / "apps" / "catalog.json"
    catalog_file.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "apps": [
            {
                "app": "sub2api",
                "repo_name": root.name,
                "repo_root": str(root),
                "service_key": "sub2api",
                "contracts": {"prod0-main": contract_file.name, "wsl": contract_file.name},
            }
        ]
    }
    catalog_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_contract(
    root: Path,
    *,
    schema_version: int | None = 1,
    tenant_resources: dict[str, object] | None = None,
    build_command: str = "bash deploy/package-runtime-image.sh",
    package_command: str | None = None,
    packaging_backend: str = "native-posix",
) -> Path:
    contract_file = root / "contract.yaml"
    contract: dict[str, object] = {
        "app_id": "sub2api",
        "schema_version": schema_version,
        "runtime": {
            "kind": "compose",
            "container_name": "sub2api-prod",
            "container_port": 8080,
            "host_binding": "127.0.0.1:18080",
            "healthcheck": {"path": "/health", "expected_status": 200},
            "env_template": "deploy/.env.example",
        },
        "infra": {
            "depends_on_containers": ["postgres18-prod", "redis7-prod"],
            "tenant_resources": tenant_resources or {},
        },
        "ingress": {
            "mode": "public",
            "public_sites": [
                {
                    "alias": "token",
                    "domain": "token.zzzai.cloud",
                    "public_url": "https://token.zzzai.cloud:8443",
                    "website_object": "token",
                }
            ],
        },
        "data": {"mounts": [{"host_path": "/data/sub2api/data", "container_path": "/app/data"}]},
        "rollback": {"previous_control_plane": {"kind": "systemd", "service_name": "sub2api"}},
        "docs": {"app_summary_file": "docs/AGENTPLANE_DEPLOYMENT.md"},
        "inventory": {"service_key": "sub2api"},
        "artifact": {
            "build_command": build_command,
            "output_path": "dist/oplinux",
            "runtime_os": "linux",
            "runtime_arch": "amd64",
        },
        "packaging": {
            "backend": packaging_backend,
            "image_name": "sub2api-prod",
            "image_tag_rule": "<upstream>-zzz.<yyyymmdd>.v<n>.g<gitsha>",
            "package_command": package_command or build_command,
        },
    }
    if schema_version is None:
        contract.pop("schema_version")
    contract_file.write_text(yaml.safe_dump(contract, sort_keys=False, allow_unicode=False), encoding="utf-8")
    _write_app_catalog_entry(root, contract_file)
    return contract_file
