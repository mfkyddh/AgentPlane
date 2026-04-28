from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from agentplane.domain.app.resource_paths import contract_relpath_for_target, resolve_catalog_repo_root
from tests.support.paths import REPO_ROOT


def expected_real_contract_path(target: str) -> str:
    return str(resolve_catalog_repo_root(REPO_ROOT, repo_name="sub2api") / contract_relpath_for_target(target))


def run_cli(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    env = None
    if cwd is None:
        repo_root: Path | None = None
        for idx, token in enumerate(args):
            if token == "--repo-root" and idx + 1 < len(args):
                repo_root = Path(args[idx + 1])
                break
            if token.startswith("--repo-root="):
                repo_root = Path(token.split("=", 1)[1])
                break
        if repo_root is not None:
            cwd = repo_root
            env = os.environ.copy()
            repo_path = str(REPO_ROOT)
            existing = env.get("PYTHONPATH", "")
            env["PYTHONPATH"] = repo_path if not existing else f"{repo_path}{os.pathsep}{existing}"
    return subprocess.run(
        [sys.executable, "-m", "agentplane.cli", *args],
        cwd=cwd or REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


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
