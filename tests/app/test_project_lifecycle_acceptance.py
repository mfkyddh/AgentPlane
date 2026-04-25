import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from agentplane.domain.app.resource_paths import app_resource_secret_dir, app_resource_secret_relative

REPO_ROOT = Path(__file__).resolve().parents[2]


def run_cli(*args: str, cwd: Path | None = None, env_overrides: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
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
            existing = env.get("PYTHONPATH", "")
            # Ensure the real AgentPlane source tree is importable even when we run against a temp repo-root fixture.
            env["PYTHONPATH"] = str(REPO_ROOT) if not existing else f"{REPO_ROOT}:{existing}"
    if env_overrides:
        env = dict(env or os.environ.copy())
        env.update(env_overrides)
    return subprocess.run(
        [sys.executable, "-m", "agentplane.cli", *args],
        cwd=cwd or REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _target_contract_relpath(target: str) -> str:
    if target == "wsl":
        return "deploy/agentplane/contract.wsl.yaml"
    if target == "prod2-main":
        return "deploy/agentplane/contract.prod2.yaml"
    return "deploy/agentplane/contract.yaml"


def _target_fixture_profile(target: str) -> dict[str, str]:
    if target == "wsl":
        return {
            "compose_file": "docker-compose.wsl.yml",
            "container_suffix": "dev",
            "postgres_container": "postgres18-dev",
            "redis_container": "redis7-dev",
            "ssh_alias": "wsl",
            "data_suffix": "wsl",
            "public_url": "http://127.0.0.1:18080",
        }
    data_suffix = target.split("-", 1)[0]
    compose_suffix = data_suffix
    return {
        "compose_file": f"docker-compose.{compose_suffix}.yml",
        "container_suffix": "prod",
        "postgres_container": "postgres18-prod",
        "redis_container": "redis7-prod",
        "ssh_alias": target,
        "data_suffix": data_suffix,
        "public_url": "https://{app_id}.example.invalid:8443",
    }


def _fixture_contract(app_id: str, *, target: str) -> dict[str, object]:
    # Keep the contract minimal but still passing validate_contract() and runtime-env projection checks.
    # target=prod0-main is used so Phase 5 path can touch catalog/app-resource truth/service truth/website truth/projection/inventory/docs.
    profile = _target_fixture_profile(target)
    return {
        "schema_version": 1,
        "app_id": app_id,
        "artifact": {
            "build_command": "echo build",
            "image_name": f"{app_id}-image",
            "image_tag_rule": "<upstream>-zzz.<yyyymmdd>.v<n>.g<gitsha>",
        },
        "runtime": {
            "kind": "compose",
            "container_name": f"{app_id}-{profile['container_suffix']}",
            "container_port": 3000,
            "healthcheck": {"path": "/healthz"},
            "env_template": f"templates/services/{app_id}.{target}.env.example",
            "host_binding": "127.0.0.1:18080",
        },
        "infra": {
            "depends_on_containers": [profile["postgres_container"], profile["redis_container"]],
            "tenant_resources": {
                "postgres": {
                    "database": f"{app_id}_{profile['data_suffix']}",
                    "user": f"{app_id}_{profile['data_suffix']}",
                    "secret_file": app_resource_secret_relative(target, app_id, "postgres"),
                },
                "redis": {
                    "db": 1,
                    "key_prefix": f"{app_id}:",
                    "secret_file": app_resource_secret_relative(target, app_id, "redis"),
                },
            },
        },
        "data": {"mounts": [{"host_path": f"/data/{app_id}/data", "container_path": "/data"}]},
        "rollback": {"previous_control_plane": {"kind": "none"}},
        "docs": {"app_summary_file": "docs/AGENTPLANE_DEPLOYMENT.md"},
        "ingress": {
            "mode": "public",
            "public_sites": [{"alias": app_id, "public_url": profile["public_url"].format(app_id=app_id)}],
        },
    }


def _write_minimal_repo_fixture(root: Path, *, app_id: str, target: str) -> Path:
    profile = _target_fixture_profile(target)
    contract_relpath = _target_contract_relpath(target)
    app_root = root / "apps" / app_id
    contract_file = app_root / Path(contract_relpath)
    _write_json(contract_file, _fixture_contract(app_id, target=target))

    catalog_file = root / "inventory" / "apps" / "catalog.json"
    _write_json(
        catalog_file,
        {
            "apps": [
                {
                    "app": app_id,
                    "repo_name": app_id,
                    "repo_root": str(app_root),
                    "service_key": app_id,
                    "contracts": {target: contract_relpath},
                }
            ]
        },
    )

    # Compose template used by app delivery render/deploy planning.
    compose_file = root / "infra" / "compose" / app_id / profile["compose_file"]
    _write_text(
        compose_file,
        "\n".join(
            [
                "services:",
                f"  {app_id}:",
                "    image: placeholder",
                f"    container_name: {app_id}-{profile['container_suffix']}",
                "    ports:",
                "      - 127.0.0.1:18080:3000",
                "    networks:",
                "      - zqf_network",
                "",
                "networks:",
                "  zqf_network: {}",
                "",
            ]
        ),
    )

    inventory_file = root / "inventory" / "servers" / target / "inventory.json"
    _write_json(
        inventory_file,
        {
            "ssh": {"aliases": [profile["ssh_alias"]], "user": "root"},
            "services": {
                "postgres18": {"container_name": profile["postgres_container"]},
                "redis7": {"container_name": profile["redis_container"]},
                # Dynamic service definition for the app itself.
                app_id: {"control_plane": "compose", "container_name": f"{app_id}-{profile['container_suffix']}"},
                # Website truth lives under services.public_ingresses.
                "public_ingresses": [
                    {
                        "alias": app_id,
                        "primary_domain": f"{app_id}.example.invalid",
                        "public_url": profile["public_url"].format(app_id=app_id),
                        "proxy": "http://127.0.0.1:18080",
                        "config_file": f"/data/1panel/www/conf.d/{app_id}.conf",
                        "ssl_id": 1,
                        "status": "Running",
                    }
                ],
            }
        },
    )

    registry_file = root / "inventory" / "servers" / target / "app-resources.json"
    _write_json(
        registry_file,
        {
            app_id: {
                "owner_app": app_id,
                "postgres": {
                    "database": f"{app_id}_{profile['data_suffix']}",
                    "user": f"{app_id}_{profile['data_suffix']}",
                    "secret_file": app_resource_secret_relative(target, app_id, "postgres"),
                },
                "redis": {
                    "db": 1,
                    "key_prefix": f"{app_id}:",
                    "secret_file": app_resource_secret_relative(target, app_id, "redis"),
                },
                "secret_files": [
                    app_resource_secret_relative(target, app_id, "postgres"),
                    app_resource_secret_relative(target, app_id, "redis"),
                ],
            }
        },
    )

    # Minimal secret files required by validate_contract() and runtime-env projection planning.
    _write_text(
        app_resource_secret_dir(root, target, app_id) / "postgres.env",
        "\n".join(
            [
                f"PGHOST={profile['postgres_container']}",
                "PGPORT=5432",
                f"PGUSER={app_id}_{profile['data_suffix']}",
                "PGPASSWORD=dummy",
                f"PGDATABASE={app_id}_{profile['data_suffix']}",
                "PGSSLMODE=disable",
                "",
            ]
        ),
    )
    _write_text(
        app_resource_secret_dir(root, target, app_id) / "redis.env",
        "\n".join(
            [
                f"REDIS_HOST={profile['redis_container']}",
                "REDIS_PORT=6379",
                "REDIS_PASSWORD=dummy",
                "REDIS_DB=1",
                f"REDIS_KEY_PREFIX={app_id}:",
                "REDIS_ENABLE_TLS=false",
                "",
            ]
        ),
    )

    # Dry-run planning reads a repo-managed ssh config when shelling out through target-aware flows.
    _write_text(root / "secrets" / "ssh" / "config", f"Host {profile['ssh_alias']}\n  HostName 127.0.0.1\n")

    # Ensure ledgers dir exists because app delivery dry-run records operations.
    (root / "inventory" / "servers" / target / "ledgers").mkdir(parents=True, exist_ok=True)
    return contract_file


class ProjectLifecycleAcceptanceTests(unittest.TestCase):
    def test_onboarding_dry_run_acceptance_cross_domain(self) -> None:
        app_id = "sub2api"
        target = "prod0-main"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_minimal_repo_fixture(root, app_id=app_id, target=target)

            result = run_cli("app", "object", "search", "--target", target, "--repo-root", str(root))
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(target, payload["target"])
            self.assertIn(app_id, [item["app"] for item in payload["payload"]["items"]])

            result = run_cli("app", "resource", "get", "--target", target, "--app", app_id, "--repo-root", str(root))
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            resource_payload = json.loads(result.stdout)["payload"]
            declared = resource_payload.get("declared", {})
            self.assertIn("postgres", declared)
            self.assertIn("redis", declared)

            result = run_cli("ingress", "search", "--target", target, "--repo-root", str(root))
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            websites = json.loads(result.stdout)["payload"]["items"]
            self.assertEqual([app_id], [item["alias"] for item in websites])

            result = run_cli("service", "plan", "--target", target, "--name", app_id, "--operation", "reconcile", "--repo-root", str(root))
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            service_plan = json.loads(result.stdout)["payload"]
            handoff_steps = service_plan["projection_handoff"]["steps"]
            self.assertTrue(any(step.get("action") == "ledger.refresh" for step in handoff_steps))
            self.assertTrue(any(step.get("action") == "runtime-env.verify" for step in handoff_steps))

            result = run_cli("projection", "runtime-env", "plan", "--target", target, "--app", app_id, "--repo-root", str(root))
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            projection_payload = json.loads(result.stdout)
            self.assertTrue(projection_payload.get("ok"), msg=projection_payload)

            result = run_cli(
                "app",
                "delivery",
                "onboard",
                "--target",
                target,
                "--app",
                app_id,
                "--dry-run",
                "--repo-root",
                str(root),
            )
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            onboard_payload = json.loads(result.stdout)["payload"]
            self.assertTrue(onboard_payload.get("ok"), msg=onboard_payload)
            actions = [step["action"] for step in onboard_payload["sequence"]]
            self.assertIn("app.delivery.onboard.catalog", actions)
            self.assertIn("app.delivery.onboard.app-resource-truth", actions)
            self.assertIn("app.delivery.onboard.service-truth", actions)
            self.assertIn("app.delivery.onboard.website-truth", actions)
            self.assertIn("projection.runtime-env.plan", actions)
            self.assertIn("app.delivery.inventory-refresh", actions)
            self.assertIn("app.delivery.doc-sync", actions)
            doc_step = next(step for step in onboard_payload["sequence"] if step["action"] == "app.delivery.doc-sync")
            doc_payload = doc_step["payload"]
            self.assertIn("server_readme", doc_payload)
            self.assertTrue(doc_payload.get("planned"), msg=doc_payload)

    def test_offboarding_dry_run_acceptance_wsl(self) -> None:
        app_id = "sub2api"
        target = "wsl"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_minimal_repo_fixture(root, app_id=app_id, target=target)

            result = run_cli(
                "app",
                "delivery",
                "offboard",
                "--target",
                target,
                "--app",
                app_id,
                "--dry-run",
                "--repo-root",
                str(root),
            )
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            offboard_payload = json.loads(result.stdout)["payload"]
            self.assertTrue(offboard_payload.get("ok"), msg=offboard_payload)
            actions = [step["action"] for step in offboard_payload["steps"]]
            self.assertIn("app.delivery.offboard.website-truth", actions)
            self.assertIn("app.delivery.offboard.service-truth", actions)
            self.assertIn("app.delivery.offboard.app-resource-truth", actions)
            self.assertIn("app.delivery.offboard.secrets", actions)
            self.assertIn("app.delivery.offboard.catalog", actions)
            self.assertIn("app.delivery.offboard.runtime-env", actions)
            self.assertIn("app.delivery.offboard.doc-sync", actions)
            doc_step = next(step for step in offboard_payload["steps"] if step["action"] == "app.delivery.offboard.doc-sync")
            self.assertTrue(doc_step["payload"]["planned"])


if __name__ == "__main__":
    unittest.main()

