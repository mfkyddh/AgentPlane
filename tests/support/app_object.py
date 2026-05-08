from __future__ import annotations

import json
from pathlib import Path

from agentplane.domain.app.resource_paths import contract_relpath_for_target, resolve_catalog_repo_root
from tests.support.cli import run_agentplane_cli
from tests.support.constants import (
    APP_ID_SUB2API,
    CONTAINER_SUB2API,
    DOMAIN_TOKEN,
    FAKE_HOST_BINDING,
    PG_DATABASE_PROD,
    PG_USER_PROD,
    REDIS_DB,
    REDIS_KEY_PREFIX,
    TARGET_PROD,
)
from tests.support.paths import REPO_ROOT

run_cli = run_agentplane_cli


def expected_real_contract_path(target: str) -> str:
    return str(resolve_catalog_repo_root(REPO_ROOT, repo_name=APP_ID_SUB2API) / contract_relpath_for_target(target))


def write_inventory_with_app(root: Path) -> None:
    server_root = root / "inventory" / "servers" / TARGET_PROD
    server_root.mkdir(parents=True, exist_ok=True)
    app_payload = {
        "app": APP_ID_SUB2API,
        "control_plane": "compose",
        "container_name": CONTAINER_SUB2API,
        "host_binding": FAKE_HOST_BINDING,
        "public_url": f"https://{DOMAIN_TOKEN}:8443",
        "app_resource_summary": {
            "postgres": {
                "database": PG_DATABASE_PROD,
                "user": PG_USER_PROD,
                "secret_file": f"secrets/hosts/{TARGET_PROD}/apps/{APP_ID_SUB2API}/resources/postgres.env",
            },
            "redis": {
                "db": REDIS_DB,
                "key_prefix": REDIS_KEY_PREFIX,
                "secret_file": f"secrets/hosts/{TARGET_PROD}/apps/{APP_ID_SUB2API}/resources/redis.env",
            },
        },
    }
    (server_root / "inventory.json").write_text(
        json.dumps(
            {
                "services": {APP_ID_SUB2API: app_payload},
                "object_ledgers": {"counts": {"apps": 1}},
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    ledger_root = server_root / "ledgers"
    ledger_root.mkdir(parents=True, exist_ok=True)
    (ledger_root / "apps.json").write_text(
        json.dumps({"items": [app_payload], "count": 1}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    catalog_root = root / "inventory" / "apps"
    catalog_root.mkdir(parents=True, exist_ok=True)
    (catalog_root / "catalog.json").write_text(
        json.dumps(
            {
                "apps": [
                    {
                        "app": APP_ID_SUB2API,
                        "repo_name": APP_ID_SUB2API,
                        "repo_root": str(root / APP_ID_SUB2API),
                        "service_key": APP_ID_SUB2API,
                        "contracts": {TARGET_PROD: "deploy/agentplane/contract.yaml"},
                    }
                ]
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
