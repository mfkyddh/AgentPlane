import json
import re
import subprocess
import tempfile  # noqa: F401
import unittest
from datetime import UTC, datetime  # noqa: F401
from pathlib import Path
from types import SimpleNamespace  # noqa: F401
from unittest.mock import patch  # noqa: F401

import yaml
from agentplane.domain.app.resource_paths import app_resource_secret_dir  # noqa: F401
from agentplane.domain.app.runtime import _secrets_root  # noqa: F401
from agentplane.runtime.host_profile import HostProfile  # noqa: F401
from tests.support.app_delivery_cli import run_app_delivery_cli, run_cli  # noqa: F401
from tests.support.app_resources import resource_relative, resource_root
from tests.support.fake_scripts import (  # noqa: F401
    write_fake_bridge_network_ssh as _write_fake_bridge_network_ssh,
    write_fake_command as _write_fake_command,
)
from tests.support.constants import (
    APP_ID_SUB2API,
    CONTAINER_MINIO,
    CONTAINER_POSTGRES,
    CONTAINER_REDIS,
    CONTAINER_SUB2API,
    DOMAIN_SAMPLEAPI,
    DOMAIN_TOKEN,
    FAKE_BINDING_3000,
    FAKE_CONTAINER_PORT,
    FAKE_HEALTHCHECK_PATH,
    FAKE_HOST_BINDING,
    FAKE_PROXY_3000,
    PG_DATABASE_PROD,
    PG_USER_PROD,
    REDIS_DB,
    REDIS_KEY_PREFIX,
    TARGET_PROD,
    TARGET_WSL,
)
from tests.support.paths import REPO_ROOT  # noqa: F401

ERROR_ID_TENANT_RESOURCES_REQUIRED = "app.resource.resources_required"
ERROR_ID_TENANT_SECRET_FILE_SCOPE = "app.resource.secret_file_scope"
ERROR_ID_TENANT_SECRET_FILE_MISSING = "app.resource.secret_file_missing"
ERROR_ID_TENANT_REGISTRY_MISMATCH = "app.resource.registry_mismatch"


def _catalog_repo_root(contract_root: Path) -> Path:
    if (contract_root / "inventory").exists():
        return contract_root
    if (contract_root.parent / "inventory").exists():
        return contract_root.parent
    return contract_root


def write_app_catalog_entry(
    repo_root: Path,
    *,
    app: str,
    repo_name: str,
    app_root: Path,
    service_key: str,
    contracts: dict[str, str],
) -> Path:
    catalog_file = repo_root / "inventory" / "apps" / "catalog.json"
    catalog_file.parent.mkdir(parents=True, exist_ok=True)
    payload = {"apps": []}
    if catalog_file.exists():
        payload = json.loads(catalog_file.read_text(encoding="utf-8"))
    items = [item for item in payload.get("apps", []) if isinstance(item, dict) and item.get("app") != app]
    items.append(
        {
            "app": app,
            "repo_name": repo_name,
            "repo_root": str(app_root),
            "service_key": service_key,
            "contracts": contracts,
        }
    )
    payload["apps"] = items
    catalog_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return catalog_file


def sync_app_catalog_for_contract(
    repo_root: Path,
    *,
    contract_file: Path,
    app: str,
    service_key: str,
    app_root: Path | None = None,
    targets: tuple[str, ...] = ("prod0-main", "wsl"),
) -> Path:
    resolved_app_root = app_root or contract_file.parent
    contract_rel = contract_file.relative_to(resolved_app_root).as_posix()
    return write_app_catalog_entry(
        _catalog_repo_root(repo_root),
        app=app,
        repo_name=resolved_app_root.name,
        app_root=resolved_app_root,
        service_key=service_key,
        contracts={target: contract_rel for target in targets},
    )


def managed_bridge_networks_payload(*, required_for: list[str] | None = None) -> list[dict[str, object]]:
    return [
        {
            "name": "zqf_network",
            "driver": "bridge",
            "subnet": "172.19.0.0/16",
            "gateway_ip": "172.19.0.1/16",
            "required_for": required_for or [CONTAINER_SUB2API],
        }
    ]


def write_inventory(root: Path, *, include_managed_bridge_networks: bool = False) -> Path:
    payload = {
        "ssh": {"aliases": ["prod0-main"], "user": "root"},
        "services": {
            "postgres": {"container_name": CONTAINER_POSTGRES},
            "redis": {"container_name": CONTAINER_REDIS},
            "minio": {"container_name": CONTAINER_MINIO},
        },
    }
    if include_managed_bridge_networks:
        payload["managed_bridge_networks"] = managed_bridge_networks_payload()
    inventory_file = root / "inventory" / "servers" / "prod0-main" / "inventory.json"
    inventory_file.parent.mkdir(parents=True, exist_ok=True)
    inventory_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    wsl_inventory_file = root / "inventory" / "servers" / "wsl" / "inventory.json"
    wsl_inventory_file.parent.mkdir(parents=True, exist_ok=True)
    wsl_inventory_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return inventory_file


def delivery_contract_sections(
    *,
    schema_version: int | None,
    build_command: str,
    image_name: str,
    package_command: str | None = None,
    packaging_backend: str = "native-posix",
    artifact_output_path: str = "dist/oplinux",
) -> dict[str, object]:
    if schema_version == 2:
        return {
            "artifact": {
                "build_command": build_command,
                "output_path": artifact_output_path,
                "runtime_os": "linux",
                "runtime_arch": "amd64",
            },
            "packaging": {
                "backend": packaging_backend,
                "image_name": image_name,
                "image_tag_rule": "<upstream>-zzz.<yyyymmdd>.v<n>.g<gitsha>",
                "package_command": package_command or build_command,
            },
        }
    return {
        "artifact": {
            "build_command": build_command,
            "image_name": image_name,
            "image_tag_rule": "<upstream>-zzz.<yyyymmdd>.v<n>.g<gitsha>",
        }
    }


def write_contract(
    root: Path,
    *,
    dependency: str = CONTAINER_REDIS,
    dependencies: list[str] | None = None,
    include_container_name: bool = True,
    schema_version: int | None = 1,
    runtime_kind: str = "compose",
    tenant_resources: dict[str, object] | None = None,
    build_command: str = "bash deploy/package-runtime-image.sh",
    package_command: str | None = None,
    packaging_backend: str = "native-posix",
    artifact_output_path: str = "dist/oplinux",
    docs_config: dict[str, object] | None = None,
    ingress_mode: str = "public",
    public_sites: list[dict[str, object]] | None = None,
) -> Path:
    contract_file = root / "contract.yaml"
    runtime: dict[str, object] = {
        "kind": runtime_kind,
        "container_port": FAKE_CONTAINER_PORT,
        "host_binding": FAKE_HOST_BINDING,
        "healthcheck": {"path": FAKE_HEALTHCHECK_PATH, "expected_status": 200},
        "env_template": "deploy/.env.example",
    }
    if include_container_name:
        runtime["container_name"] = CONTAINER_SUB2API

    resolved_dependencies: list[str]
    if dependencies is None:
        resolved_dependencies = [CONTAINER_POSTGRES, dependency]
    else:
        resolved_dependencies = list(dependencies)
    infra: dict[str, object] = {"depends_on_containers": resolved_dependencies}
    if tenant_resources is not None:
        infra["tenant_resources"] = tenant_resources

    contract: dict[str, object] = {
        "app_id": APP_ID_SUB2API,
        "runtime": runtime,
        "infra": infra,
        "ingress": {
            "mode": ingress_mode,
            "public_sites": public_sites
            if public_sites is not None
            else [
                {
                    "alias": "token",
                    "domain": DOMAIN_TOKEN,
                    "public_url": f"https://{DOMAIN_TOKEN}:8443",
                    "website_object": "token",
                }
            ],
        },
        "data": {"mounts": [{"host_path": "/data/sub2api/data", "container_path": "/app/data"}]},
        "rollback": {"previous_control_plane": {"kind": "systemd", "service_name": APP_ID_SUB2API}},
        "docs": docs_config or {"app_summary_file": "docs/AGENTPLANE_DEPLOYMENT.md"},
        "inventory": {"service_key": APP_ID_SUB2API},
    }
    contract.update(
        delivery_contract_sections(
            schema_version=schema_version,
            build_command=build_command,
            image_name=CONTAINER_SUB2API,
            package_command=package_command,
            packaging_backend=packaging_backend,
            artifact_output_path=artifact_output_path,
        )
    )
    if schema_version is not None:
        contract["schema_version"] = schema_version
    contract_file.write_text(yaml.safe_dump(contract, sort_keys=False, allow_unicode=False), encoding="utf-8")
    write_app_catalog_entry(
        _catalog_repo_root(root),
        app=APP_ID_SUB2API,
        repo_name=root.name,
        app_root=root,
        service_key=APP_ID_SUB2API,
        contracts={TARGET_PROD: contract_file.name, TARGET_WSL: contract_file.name},
    )
    return contract_file


def _target_contract_relpath(target: str) -> str:
    if target == "wsl":
        return "deploy/agentplane/contract.wsl.yaml"
    return "deploy/agentplane/contract.yaml"


def write_target_contract(
    app_root: Path,
    *,
    target: str = TARGET_PROD,
    schema_version: int | None = 1,
    tenant_resources: dict[str, object] | None = None,
    env_template: str = "deploy/.env.example",
    docs_config: dict[str, object] | None = None,
    build_command: str = "bash deploy/package-runtime-image.sh",
    package_command: str | None = None,
    packaging_backend: str = "native-posix",
    artifact_output_path: str = "dist/oplinux",
) -> Path:
    contract_file = app_root / _target_contract_relpath(target)
    contract_file.parent.mkdir(parents=True, exist_ok=True)
    runtime: dict[str, object] = {
        "kind": "compose",
        "container_port": FAKE_CONTAINER_PORT,
        "host_binding": FAKE_HOST_BINDING,
        "healthcheck": {"path": FAKE_HEALTHCHECK_PATH, "expected_status": 200},
        "env_template": env_template,
    }
    if target == TARGET_WSL:
        runtime["container_name"] = "sub2api-dev"
    else:
        runtime["container_name"] = CONTAINER_SUB2API

    depends = ["postgres18-dev"] if target == TARGET_WSL else [CONTAINER_POSTGRES, CONTAINER_REDIS]
    infra: dict[str, object] = {"depends_on_containers": depends}
    if tenant_resources is not None:
        infra["tenant_resources"] = tenant_resources

    contract: dict[str, object] = {
        "app_id": APP_ID_SUB2API,
        "runtime": runtime,
        "infra": infra,
        "ingress": {
            "mode": "internal" if target == TARGET_WSL else "public",
            "public_sites": []
            if target == TARGET_WSL
            else [
                {
                    "alias": "token",
                    "domain": DOMAIN_TOKEN,
                    "public_url": f"https://{DOMAIN_TOKEN}:8443",
                    "website_object": "token",
                }
            ],
        },
        "data": {"mounts": [{"host_path": "/data/sub2api/data", "container_path": "/app/data"}]},
        "rollback": {"previous_control_plane": {"kind": "none", "note": "worktree override test"}},
        "docs": docs_config or {"app_summary_file": "docs/AGENTPLANE_DEPLOYMENT.md"},
        "inventory": {"service_key": APP_ID_SUB2API},
    }
    contract.update(
        delivery_contract_sections(
            schema_version=schema_version,
            build_command=build_command,
            image_name=CONTAINER_SUB2API,
            package_command=package_command,
            packaging_backend=packaging_backend,
            artifact_output_path=artifact_output_path,
        )
    )
    if schema_version is not None:
        contract["schema_version"] = schema_version
    contract_file.write_text(yaml.safe_dump(contract, sort_keys=False, allow_unicode=False), encoding="utf-8")
    return contract_file


def write_app_resource_registry(root: Path, payload: dict[str, object], target: str = TARGET_PROD) -> Path:
    registry_file = root / "inventory" / "servers" / target / "app-resources.json"
    registry_file.parent.mkdir(parents=True, exist_ok=True)
    registry_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return registry_file


def write_compose_template(root: Path) -> Path:
    compose_file = root / "infra" / "compose" / "sub2api" / "docker-compose.prod0.yml"
    compose_file.parent.mkdir(parents=True, exist_ok=True)
    compose_file.write_text(
        yaml.safe_dump(
            {
                "services": {
                    "sub2api": {
                        "image": f"{CONTAINER_SUB2API}:latest",
                        "container_name": CONTAINER_SUB2API,
                        "ports": [f"{FAKE_HOST_BINDING}:{FAKE_CONTAINER_PORT}"],
                        "environment": {},
                        "networks": ["zqf_network"],
                    }
                },
                "networks": {"zqf_network": {"external": True}},
            },
            sort_keys=False,
            allow_unicode=False,
        ),
        encoding="utf-8",
    )
    return compose_file


def write_internal_worker_compose_template(root: Path) -> Path:
    compose_file = root / "infra" / "compose" / "sample-register-v2" / "docker-compose.prod0.yml"
    compose_file.parent.mkdir(parents=True, exist_ok=True)
    compose_file.write_text(
        yaml.safe_dump(
            {
                "services": {
                    "sample-register-v2": {
                        "image": "sample-register-v2-prod:latest",
                        "container_name": "sample-register-v2-prod",
                        "command": ["/app/.venv/bin/python", "chatgpt_register_v2.py", "--import-sub2api"],
                        "env_file": ["../../../secrets/services/sample-register-v2.prod0.env"],
                        "volumes": ["/data/sample-register-v2/data:/data"],
                        "networks": ["zqf_network"],
                    }
                },
                "networks": {"zqf_network": {"external": True}},
            },
            sort_keys=False,
            allow_unicode=False,
        ),
        encoding="utf-8",
    )
    return compose_file


def write_sampleapi_contract(
    root: Path,
    *,
    target: str = TARGET_PROD,
    include_minio: bool = False,
    rollback_entry: dict[str, object] | None = None,
    schema_version: int | None = 1,
    build_command: str = "bash deploy/package-runtime-image.sh",
    package_command: str | None = None,
    packaging_backend: str = "native-posix",
    artifact_output_path: str = "dist/oplinux",
) -> Path:
    contract_file = root / "sampleapi-contract.yaml"
    if target == TARGET_WSL:
        target_alias = TARGET_WSL
        postgres_database = "sampleapi_wsl"
        postgres_user = "sampleapi_wsl"
        minio_bucket = "wsl-sampleapi"
        minio_access_key = "sampleapi_wsl"
        minio_policy_name = "wsl-sampleapi-rw"
        domain = "sampleapi.local"
        public_url = FAKE_PROXY_3000
        docs_path = "docs/AGENTPLANE_DEPLOYMENT.wsl.md"
        previous_control_plane = rollback_entry or {
            "kind": "none",
            "note": "wsl local runtime",
        }
    else:
        target_alias = "prod0"
        postgres_database = "sampleapi_prod0"
        postgres_user = "sampleapi_prod0"
        minio_bucket = "prod0-sampleapi"
        minio_access_key = "sampleapi_prod0"
        minio_policy_name = "prod0-sampleapi-rw"
        domain = DOMAIN_SAMPLEAPI
        public_url = f"https://{DOMAIN_SAMPLEAPI}:8443"
        docs_path = "docs/AGENTPLANE_DEPLOYMENT.md"
        previous_control_plane = rollback_entry or {
            "kind": "1panel-app",
            "app_key": "new-api",
            "install_id": 3,
            "container_name": "sampleapi-prod",
        }

    tenant_resources: dict[str, object] = {
        "postgres": {
            "required": True,
            "database": postgres_database,
            "user": postgres_user,
            "secret_file": resource_relative(target, "sampleapi", "postgres"),
        },
        "redis": {
            "required": True,
            "db": 2,
            "key_prefix": "sampleapi:wsl:" if target == "wsl" else "sampleapi:",
            "secret_file": resource_relative(target, "sampleapi", "redis"),
        },
    }
    if include_minio:
        tenant_resources["minio"] = {
            "required": True,
            "bucket": minio_bucket,
            "access_key": minio_access_key,
            "policy_name": minio_policy_name,
            "policy_scope": "bucket-only",
            "isolation_level": "bucket-scoped-rw",
            "secret_file": resource_relative(target, "sampleapi", "minio"),
        }

    depends_on_containers = [CONTAINER_POSTGRES, CONTAINER_REDIS]
    if include_minio:
        depends_on_containers.append(CONTAINER_MINIO)

    contract = {
        "app_id": "sampleapi",
        "runtime": {
            "kind": "compose",
            "container_name": "sampleapi-prod",
            "container_port": 3000,
            "host_binding": "0.0.0.0:3000" if target == "wsl" else FAKE_BINDING_3000,
            "healthcheck": {"path": "/api/status", "expected_status": 200},
            "env_template": f"deploy/prod/sampleapi-{target_alias}.env.example",
        },
        "infra": {
            "depends_on_containers": depends_on_containers,
            "tenant_resources": tenant_resources,
        },
        "ingress": {
            "public_sites": [
                {
                    "alias": "sampleapi",
                    "domain": domain,
                    "public_url": public_url,
                    "website_object": "sampleapi",
                }
            ]
        },
        "data": {
            "mounts": [
                {"host_path": "/data/sampleapi/data", "container_path": "/data"},
                {"host_path": "/data/sampleapi/logs", "container_path": "/app/logs"},
            ]
        },
        "rollback": {"previous_control_plane": previous_control_plane},
        "docs": {"app_summary_file": docs_path},
        "inventory": {"service_key": "sampleapi"},
    }
    contract.update(
        delivery_contract_sections(
            schema_version=schema_version,
            build_command=build_command,
            image_name="sampleapi-prod",
            package_command=package_command,
            packaging_backend=packaging_backend,
            artifact_output_path=artifact_output_path,
        )
    )
    if schema_version is not None:
        contract["schema_version"] = schema_version
    contract_file.write_text(yaml.safe_dump(contract, sort_keys=False, allow_unicode=False), encoding="utf-8")
    contracts = {TARGET_PROD: contract_file.name, TARGET_WSL: contract_file.name}
    write_app_catalog_entry(
        _catalog_repo_root(root),
        app="sampleapi",
        repo_name=root.name,
        app_root=root,
        service_key="sampleapi",
        contracts=contracts,
    )
    return contract_file


def write_sampleapi_tenant_files(root: Path, *, target: str = TARGET_PROD, include_minio: bool = False) -> None:
    tenant_root = resource_root(root, target, "sampleapi")
    tenant_root.mkdir(parents=True, exist_ok=True)
    if target == TARGET_WSL:
        postgres_database = "sampleapi_wsl"
        postgres_user = "sampleapi_wsl"
        minio_bucket = "wsl-sampleapi"
        minio_access_key = "sampleapi_wsl"
        redis_key_prefix = "sampleapi:wsl:"
    else:
        postgres_database = "sampleapi_prod0"
        postgres_user = "sampleapi_prod0"
        minio_bucket = "prod0-sampleapi"
        minio_access_key = "sampleapi_prod0"
        redis_key_prefix = "sampleapi:"
    (tenant_root / "postgres.env").write_text(
        f"PGDATABASE={postgres_database}\nPGUSER={postgres_user}\n",
        encoding="utf-8",
    )
    (tenant_root / "redis.env").write_text(
        f"REDIS_DB=2\nREDIS_KEY_PREFIX={redis_key_prefix}\n",
        encoding="utf-8",
    )
    if include_minio:
        (tenant_root / "minio.env").write_text(
            f"S3_BUCKET={minio_bucket}\nS3_ACCESS_KEY={minio_access_key}\nS3_SECRET_KEY=sampleapi-s3-secret\n",
            encoding="utf-8",
        )


def write_sampleapi_compose_templates(root: Path) -> None:
    compose_root = root / "infra" / "compose" / "sampleapi"
    compose_root.mkdir(parents=True, exist_ok=True)
    wsl_file = compose_root / "docker-compose.wsl.yml"
    prod_file = compose_root / "docker-compose.prod0.yml"
    prod_payload = {
        "services": {
            "sampleapi": {
                "image": "sampleapi-prod:latest",
                "container_name": "sampleapi-prod",
                "command": ["--log-dir", "/app/logs"],
                "env_file": ["../../../secrets/services/sampleapi.prod0.env"],
                "ports": [f"{FAKE_BINDING_3000}:3000"],
                "volumes": ["/data/sampleapi/data:/data", "/data/sampleapi/logs:/app/logs"],
                "networks": ["zqf_network"],
            }
        },
        "networks": {"zqf_network": {"external": True}},
    }
    wsl_payload = {
        "services": {
            "sampleapi": {
                "image": "sampleapi-prod:latest",
                "container_name": "sampleapi-dev",
                "command": ["--log-dir", "/app/logs"],
                "env_file": ["../../../secrets/services/sampleapi.wsl.env"],
                "ports": ["0.0.0.0:3000:3000"],
                "volumes": ["/data/sampleapi/data:/data", "/data/sampleapi/logs:/app/logs"],
                "networks": ["zqf_network"],
            }
        },
        "networks": {"zqf_network": {"external": True}},
    }
    prod_file.write_text(yaml.safe_dump(prod_payload, sort_keys=False, allow_unicode=False), encoding="utf-8")
    wsl_file.write_text(yaml.safe_dump(wsl_payload, sort_keys=False, allow_unicode=False), encoding="utf-8")


def baseline_app_resource_registry_payload() -> dict[str, object]:
    return {
        APP_ID_SUB2API: {
            "owner_app": APP_ID_SUB2API,
            "postgres": {"database": PG_DATABASE_PROD, "user": PG_USER_PROD},
            "redis": {"db": REDIS_DB, "key_prefix": REDIS_KEY_PREFIX},
            "minio": {
                "bucket": "prod0-sub2api",
                "access_key": "sub2api_prod0",
                "policy_name": "prod0-sub2api-rw",
                "policy_scope": "bucket-only",
                "isolation_level": "bucket-scoped-rw",
            },
            "secret_files": [
                resource_relative("prod0-main", "sub2api", "postgres"),
                resource_relative("prod0-main", "sub2api", "redis"),
                resource_relative("prod0-main", "sub2api", "minio"),
            ],
        }
    }


def baseline_tenant_resources(*, target: str = TARGET_PROD, include_minio: bool = False) -> dict[str, object]:
    if target == TARGET_WSL:
        postgres_database = "sub2api_wsl"
        postgres_user = "sub2api_wsl"
        redis_key_prefix = "sub2api:wsl:"
        minio_bucket = "wsl-sub2api"
        minio_access_key = "sub2api_wsl"
        minio_policy_name = "wsl-sub2api-rw"
        secret_target = TARGET_WSL
    else:
        postgres_database = PG_DATABASE_PROD
        postgres_user = PG_USER_PROD
        redis_key_prefix = REDIS_KEY_PREFIX
        minio_bucket = "prod0-sub2api"
        minio_access_key = PG_USER_PROD
        minio_policy_name = "prod0-sub2api-rw"
        secret_target = TARGET_PROD
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


def write_tenant_secret_files(root: Path, *, target: str = TARGET_PROD, include_minio: bool = False) -> None:
    tenant_root = resource_root(root, target, APP_ID_SUB2API)
    tenant_root.mkdir(parents=True, exist_ok=True)
    if target == TARGET_WSL:
        postgres_database = "sub2api_wsl"
        postgres_user = "sub2api_wsl"
        redis_key_prefix = "sub2api:wsl:"
        minio_bucket = "wsl-sub2api"
        minio_access_key = "sub2api_wsl"
    else:
        postgres_database = PG_DATABASE_PROD
        postgres_user = PG_USER_PROD
        redis_key_prefix = REDIS_KEY_PREFIX
        minio_bucket = "prod0-sub2api"
        minio_access_key = PG_USER_PROD
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


def assert_live_db_partition_markers(test_case: unittest.TestCase, text: str) -> None:
    test_case.assertRegex(text, re.compile(r"(DB.?级|数据库级).*(逻辑分区|分区)|逻辑分区.*(DB.?级|数据库级)"))
    test_case.assertRegex(
        text,
        re.compile(r"共享.*(?:runtime|运行时).*(凭据|密码|口令)|共享.*(凭据|密码|口令).*(?:runtime|运行时)"),
    )
    test_case.assertRegex(text, re.compile(r"(不|非).*(强|安全).*隔离"))
    test_case.assertNotIn("remediation-target", text)
    test_case.assertNotIn("pending-realization", text)


def init_git_repo(root: Path) -> str:
    subprocess.run(["git", "init"], cwd=root, text=True, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Codex"], cwd=root, text=True, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "codex@example.com"], cwd=root, text=True, check=True, capture_output=True
    )
    marker = root / ".gitkeep"
    marker.write_text("ok\n", encoding="utf-8")
    subprocess.run(["git", "add", ".gitkeep"], cwd=root, text=True, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=root, text=True, check=True, capture_output=True)
    sha = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"], cwd=root, text=True, check=True, capture_output=True
    ).stdout.strip()
    return sha


def init_git_repo_with_tag(root: Path, tag: str) -> str:
    sha = init_git_repo(root)
    subprocess.run(["git", "tag", tag], cwd=root, text=True, check=True, capture_output=True)
    return sha


# Re-export from shared module for backward compatibility
write_fake_command = _write_fake_command
write_fake_bridge_network_ssh = _write_fake_bridge_network_ssh


__all__ = [name for name in globals() if not name.startswith("__")]
