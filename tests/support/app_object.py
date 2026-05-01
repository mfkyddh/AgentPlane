from __future__ import annotations

import json
from pathlib import Path

from agentplane.domain.app.resource_paths import contract_relpath_for_target, resolve_catalog_repo_root
from tests.support.cli import run_agentplane_cli
from tests.support.paths import REPO_ROOT

run_cli = run_agentplane_cli


def expected_real_contract_path(target: str) -> str:
    return str(resolve_catalog_repo_root(REPO_ROOT, repo_name="sub2api") / contract_relpath_for_target(target))


def write_inventory_with_app(root: Path) -> None:
    server_root = root / "inventory" / "servers" / "prod0-main"
    server_root.mkdir(parents=True, exist_ok=True)
    app_payload = {
        "app": "sub2api",
        "control_plane": "compose",
        "container_name": "sub2api-prod",
        "host_binding": "127.0.0.1:18080",
        "public_url": "https://token.example.net:8443",
        "app_resource_summary": {
            "postgres": {
                "database": "sub2api_prod0",
                "user": "sub2api_prod0",
                "secret_file": "secrets/hosts/prod0-main/apps/sub2api/resources/postgres.env",
            },
            "redis": {
                "db": 1,
                "key_prefix": "sub2api:",
                "secret_file": "secrets/hosts/prod0-main/apps/sub2api/resources/redis.env",
            },
        },
    }
    (server_root / "inventory.json").write_text(
        json.dumps(
            {
                "services": {"sub2api": app_payload},
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
                        "app": "sub2api",
                        "repo_name": "sub2api",
                        "repo_root": str(root / "sub2api"),
                        "service_key": "sub2api",
                        "contracts": {"prod0-main": "deploy/agentplane/contract.yaml"},
                    }
                ]
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
