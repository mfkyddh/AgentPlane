from __future__ import annotations

from tests.support.app_delivery import *  # noqa: F403


class TestAppDeliveryValidateCliTests(unittest.TestCase):
    def test_secrets_root_prefers_repo_local_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            secrets_dir = root / "secrets"
            secrets_dir.mkdir(parents=True, exist_ok=True)

            self.assertEqual(secrets_dir, _secrets_root(root))

    def test_secrets_root_falls_back_to_git_common_dir_for_worktree(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            main_root = tmp_root / "main"
            worktree_root = tmp_root / "worktree"
            git_worktree_dir = main_root / ".git" / "worktrees" / "demo"
            main_secrets = main_root / "secrets"

            main_secrets.mkdir(parents=True, exist_ok=True)
            git_worktree_dir.mkdir(parents=True, exist_ok=True)
            worktree_root.mkdir(parents=True, exist_ok=True)
            (worktree_root / ".git").write_text(f"gitdir: {git_worktree_dir}\n", encoding="utf-8")

            self.assertEqual(main_secrets, _secrets_root(worktree_root))

    def test_secrets_root_prefers_git_common_dir_over_worktree_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            main_root = tmp_root / "main"
            worktree_root = tmp_root / "worktree"
            git_worktree_dir = main_root / ".git" / "worktrees" / "demo"
            main_secrets = main_root / "secrets"

            main_secrets.mkdir(parents=True, exist_ok=True)
            git_worktree_dir.mkdir(parents=True, exist_ok=True)
            worktree_root.mkdir(parents=True, exist_ok=True)
            (worktree_root / ".git").write_text(f"gitdir: {git_worktree_dir}\n", encoding="utf-8")
            (worktree_root / "secrets").symlink_to(main_secrets)

            self.assertEqual(main_secrets, _secrets_root(worktree_root))

    def test_validate_contract_accepts_known_dependency_containers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root)
            write_tenant_secret_files(root)
            contract_file = write_contract(root, tenant_resources=baseline_tenant_resources())

            result = run_cli(
                "app",
                "delivery",
                "validate-contract",
                "--target",
                "prod0-main",
                "--app",
                "sub2api",
                "--repo-root",
                str(root),
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual("app", payload["command"])
            self.assertEqual("validate-contract", payload["action"])
            self.assertTrue(payload["valid"])

    def test_validate_contract_requires_project_name_for_1panel_compose_rollback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root)
            write_newapi_tenant_files(root)
            contract_file = write_newapi_contract(
                root,
                rollback_entry={
                    "kind": "1panel-compose",
                    "container_name": "sub2apipay-prod",
                    "project_path": "/data/1panel/docker/compose/sub2apipay-prod/docker-compose.yml",
                },
            )

            result = run_app_delivery_cli("validate-contract", repo_root=root, app="newapi")

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("rollback.previous_control_plane.kind=1panel-compose 缺少 project_name", result.stderr)

    def test_validate_contract_accepts_1panel_compose_with_compose_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root)
            write_newapi_tenant_files(root)
            contract_file = write_newapi_contract(
                root,
                rollback_entry={
                    "kind": "1panel-compose",
                    "project_name": "sub2apipay-prod",
                    "container_name": "sub2apipay-prod",
                    "project_path": "/data/1panel/docker/compose/sub2apipay-prod",
                    "compose_file": "/data/1panel/docker/compose/sub2apipay-prod/docker-compose.yml",
                },
            )

            result = run_app_delivery_cli("validate-contract", repo_root=root, app="newapi")

            self.assertEqual(result.returncode, 0, msg=result.stderr)

    def test_validate_contract_accepts_legacy_contract_without_schema_version(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root)
            write_tenant_secret_files(root)
            contract_file = write_contract(root, schema_version=None, tenant_resources=baseline_tenant_resources())

            result = run_app_delivery_cli("validate-contract", repo_root=root, app="sub2api")

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual("legacy", payload["payload"]["_meta"]["contract_mode"])
            self.assertEqual("legacy", payload["payload"]["_meta"]["schema_version"])

    def test_validate_contract_rejects_unsupported_schema_version(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root)
            write_contract(root, schema_version=3)

            result = run_app_delivery_cli("validate-contract", repo_root=root, app="sub2api")

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("schema_version", result.stderr)

    def test_validate_contract_rejects_non_compose_runtime_kind(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root)
            contract_file = write_contract(root, runtime_kind="binary")

            result = run_app_delivery_cli("validate-contract", repo_root=root, app="sub2api")

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("runtime.kind", result.stderr)

    def test_validate_contract_rejects_unknown_dependency_container(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root)
            contract_file = write_contract(root, dependency="mysql-prod")

            result = run_app_delivery_cli("validate-contract", repo_root=root, app="sub2api")

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("depends_on_containers", result.stderr)

    def test_validate_contract_rejects_missing_container_name(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root)
            contract_file = write_contract(root, include_container_name=False)

            result = run_app_delivery_cli("validate-contract", repo_root=root, app="sub2api")

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("runtime.container_name", result.stderr)

    def test_validate_contract_accepts_internal_worker_without_public_sites(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            inventory_file = root / "inventory" / "servers" / "prod0-main" / "inventory.json"
            inventory_file.parent.mkdir(parents=True, exist_ok=True)
            inventory_file.write_text(
                json.dumps(
                    {
                        "ssh": {"aliases": ["prod0-main"], "user": "root"},
                        "services": {"sub2api": {"container_name": "sub2api-prod"}},
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            wsl_inventory_file = root / "inventory" / "servers" / "wsl" / "inventory.json"
            wsl_inventory_file.parent.mkdir(parents=True, exist_ok=True)
            wsl_inventory_file.write_text(inventory_file.read_text(encoding="utf-8"), encoding="utf-8")
            contract_file = write_contract(
                root,
                dependency="sub2api-prod",
                dependencies=["sub2api-prod"],
                tenant_resources={},
                ingress_mode="internal",
                public_sites=[],
            )
            payload = yaml.safe_load(contract_file.read_text(encoding="utf-8"))
            payload["app_id"] = "chatgpt-register-v2"
            payload["artifact"]["image_name"] = "chatgpt-register-v2-prod"
            payload["runtime"]["container_name"] = "chatgpt-register-v2-prod"
            payload["runtime"]["container_port"] = 18081
            payload["runtime"]["host_binding"] = "127.0.0.1:18081"
            payload["runtime"]["healthcheck"] = {"path": "/healthz", "expected_status": 200}
            payload["data"]["mounts"] = [{"host_path": "/data/chatgpt-register-v2/data", "container_path": "/data"}]
            payload["inventory"]["service_key"] = "chatgpt-register-v2"
            contract_file.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=False), encoding="utf-8")
            sync_app_catalog_for_contract(root, contract_file=contract_file, app="chatgpt-register-v2", service_key="chatgpt-register-v2")

            result = run_app_delivery_cli("validate-contract", repo_root=root, app="chatgpt-register-v2")

            self.assertEqual(result.returncode, 0, msg=result.stderr)

    def test_validate_contract_wsl_uses_wsl_inventory_and_registry_truth(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prod0_inventory = root / "inventory" / "servers" / "prod0-main" / "inventory.json"
            prod0_inventory.parent.mkdir(parents=True, exist_ok=True)
            prod0_inventory.write_text(
                json.dumps(
                    {
                        "ssh": {"aliases": ["prod0-main"], "user": "root"},
                        "services": {
                            "postgres": {"container_name": "postgres18-prod"},
                        },
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            wsl_inventory = root / "inventory" / "servers" / "wsl" / "inventory.json"
            wsl_inventory.parent.mkdir(parents=True, exist_ok=True)
            wsl_inventory.write_text(
                json.dumps(
                    {
                        "ssh": {"aliases": ["wsl"], "user": "root"},
                        "services": {
                            "postgres": {"container_name": "postgres18-dev"},
                        },
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            write_app_resource_registry(
                root,
                {
                    "codexconsole": {
                        "owner_app": "codexconsole",
                        "postgres": {"database": "codexconsole_wsl", "user": "codexconsole_wsl"},
                        "secret_files": ["secrets/hosts/wsl/apps/codexconsole/resources/postgres.env"],
                    }
                },
                target="wsl",
            )
            tenant_root = app_resource_secret_dir(root, "wsl", "codexconsole")
            tenant_root.mkdir(parents=True, exist_ok=True)
            (tenant_root / "postgres.env").write_text(
                "PGDATABASE=codexconsole_wsl\nPGUSER=codexconsole_wsl\n",
                encoding="utf-8",
            )
            contract_file = root / "contract.yaml"
            contract_file.write_text(
                yaml.safe_dump(
                    {
                        "schema_version": 1,
                        "app_id": "codexconsole",
                        "artifact": {
                            "build_command": "bash deploy/package-runtime-image.sh",
                            "image_name": "codexconsole-prod",
                            "image_tag_rule": "<upstream>-zzz.<yyyymmdd>.v<n>.g<gitsha>",
                        },
                        "runtime": {
                            "kind": "compose",
                            "container_name": "codexconsole-dev",
                            "container_port": 1455,
                            "host_binding": "0.0.0.0:1455",
                            "healthcheck": {"path": "/health", "expected_status": 200},
                            "env_template": "deploy/codexconsole.wsl.env.example",
                        },
                        "infra": {
                            "depends_on_containers": ["postgres18-dev"],
                            "tenant_resources": {
                                "postgres": {
                                    "required": True,
                                    "database": "codexconsole_wsl",
                                    "user": "codexconsole_wsl",
                                    "secret_file": "secrets/hosts/wsl/apps/codexconsole/resources/postgres.env",
                                }
                            },
                        },
                        "ingress": {"mode": "internal", "public_sites": []},
                        "data": {"mounts": [{"host_path": "/data/codexconsole/data", "container_path": "/app/data"}]},
                        "rollback": {"previous_control_plane": {"kind": "none", "note": "wsl only"}},
                        "docs": {"app_summary_file": "docs/AGENTPLANE_DEPLOYMENT.wsl.md"},
                        "inventory": {"service_key": "codexconsole"},
                    },
                    sort_keys=False,
                    allow_unicode=False,
                ),
                encoding="utf-8",
            )
            write_app_catalog_entry(
                root,
                app="codexconsole",
                repo_name=root.name,
                app_root=root,
                service_key="codexconsole",
                contracts={"wsl": contract_file.name},
            )

            result = run_app_delivery_cli("validate-contract", repo_root=root, app="codexconsole", target="wsl")

            self.assertEqual(result.returncode, 0, msg=result.stderr)

    def test_validate_contract_rejects_legacy_image_tag_rule(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root)
            write_tenant_secret_files(root)
            contract_file = write_contract(root, tenant_resources=baseline_tenant_resources())
            payload = yaml.safe_load(contract_file.read_text(encoding="utf-8"))
            payload["artifact"]["image_tag_rule"] = "sub2api-prod_<version>_<gitsha>"
            contract_file.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=False), encoding="utf-8")

            result = run_app_delivery_cli("validate-contract", repo_root=root, app="sub2api")

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("image_tag_rule", result.stdout + result.stderr)

    def test_validate_contract_tenant_requires_tenant_resources_for_infra_dependencies(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root)
            write_app_resource_registry(root, baseline_app_resource_registry_payload())
            contract_file = write_contract(root)

            result = run_app_delivery_cli("validate-contract", repo_root=root, app="sub2api")

            self.assertNotEqual(result.returncode, 0)
            self.assertIn(ERROR_ID_TENANT_RESOURCES_REQUIRED, result.stdout + result.stderr)

    def test_validate_contract_tenant_requires_tenant_resources_even_when_registry_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root)
            # Intentionally do NOT write inventory/servers/<target>/app-resources.json.
            # Even without a tenant registry, contracts that depend on shared infra
            # (PG/Redis/MinIO) must still declare infra.tenant_resources.
            contract_file = write_contract(root)

            result = run_app_delivery_cli("validate-contract", repo_root=root, app="sub2api")

            self.assertNotEqual(result.returncode, 0)
            self.assertIn(ERROR_ID_TENANT_RESOURCES_REQUIRED, result.stdout + result.stderr)

    def test_validate_contract_tenant_rejects_cross_app_secret_file_reference(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root)
            write_app_resource_registry(root, baseline_app_resource_registry_payload())
            # Ensure the referenced secret files exist so the test is stable against
            # future validation ordering (we want to lock in the scope error).
            bad_pg = resource_root(root, "prod0-main", "newapi") / "postgres.env"
            bad_pg.parent.mkdir(parents=True, exist_ok=True)
            bad_pg.write_text("PGDATABASE=sub2api_prod0\nPGUSER=sub2api_prod0\n", encoding="utf-8")
            bad_redis = resource_root(root, "prod0-main", "newapi") / "redis.env"
            bad_redis.parent.mkdir(parents=True, exist_ok=True)
            bad_redis.write_text("REDIS_USER=sub2api_prod0\nREDIS_DB=1\nREDIS_KEY_PREFIX=sub2api:\n", encoding="utf-8")
            contract_file = write_contract(
                root,
                tenant_resources={
                    "postgres": {
                        "required": True,
                        "database": "sub2api_prod0",
                        "user": "sub2api_prod0",
                        "secret_file": resource_relative("prod0-main", "newapi", "postgres"),
                    },
                    "redis": {
                        "required": True,
                        "user": "sub2api_prod0",
                        "db": 1,
                        "key_prefix": "sub2api:",
                        "secret_file": resource_relative("prod0-main", "newapi", "redis"),
                    },
                },
            )

            result = run_app_delivery_cli("validate-contract", repo_root=root, app="sub2api")

            self.assertNotEqual(result.returncode, 0)
            self.assertIn(ERROR_ID_TENANT_SECRET_FILE_SCOPE, result.stdout + result.stderr)

    def test_validate_contract_rejects_registry_secret_file_scope_before_deploy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root)
            registry_payload = baseline_app_resource_registry_payload()
            registry_payload["sub2api"]["secret_files"] = [
                resource_relative("prod0-main", "newapi", "postgres"),
                resource_relative("prod0-main", "newapi", "redis"),
            ]
            write_app_resource_registry(root, registry_payload)
            write_tenant_secret_files(root)
            write_contract(root, tenant_resources=baseline_tenant_resources())

            result = run_app_delivery_cli("validate-contract", repo_root=root, app="sub2api")

            self.assertNotEqual(result.returncode, 0)
            self.assertIn(ERROR_ID_TENANT_SECRET_FILE_SCOPE, result.stdout + result.stderr)

    def test_validate_contract_tenant_rejects_missing_tenant_secret_file_reference(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root)
            write_app_resource_registry(root, baseline_app_resource_registry_payload())
            # The secret_file path is in-scope but the file is intentionally missing.
            # This must fail on the contract side (app validate-contract), not only on
            # app resource verify / host audit.
            contract_file = write_contract(
                root,
                tenant_resources={
                    "postgres": {
                        "required": True,
                        "database": "sub2api_prod0",
                        "user": "sub2api_prod0",
                        "secret_file": resource_relative("prod0-main", "sub2api", "postgres"),
                    },
                    "redis": {
                        "required": True,
                        "user": "sub2api_prod0",
                        "db": 1,
                        "key_prefix": "sub2api:",
                        "secret_file": resource_relative("prod0-main", "sub2api", "redis"),
                    },
                },
            )

            result = run_app_delivery_cli("validate-contract", repo_root=root, app="sub2api")

            self.assertNotEqual(result.returncode, 0)
            combined = result.stdout + result.stderr
            # Lock on stable error ids instead of brittle message fragments.
            self.assertIn(ERROR_ID_TENANT_SECRET_FILE_MISSING, combined)
            self.assertIn(resource_relative("prod0-main", "sub2api", "postgres"), combined)
            # When validate emits JSON, prefer schema-level assertions.
            try:
                payload = json.loads(result.stdout)
            except json.JSONDecodeError:
                payload = None
            if isinstance(payload, dict):
                items = payload.get("errors") or payload.get("violations") or payload.get("findings") or []
                if isinstance(items, list):
                    ids = {item.get("id") for item in items if isinstance(item, dict)}
                    self.assertIn(ERROR_ID_TENANT_SECRET_FILE_MISSING, ids)

    def test_validate_contract_tenant_rejects_secret_file_path_traversal_outside_scoped_app_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root)
            write_app_resource_registry(root, baseline_app_resource_registry_payload())
            # Ensure referenced secret files exist so the test is stable against future
            # validation ordering (we want to lock in the scope error, not missing-file
            # preconditions).
            redis = resource_root(root, "prod0-main", "sub2api") / "redis.env"
            redis.parent.mkdir(parents=True, exist_ok=True)
            redis.write_text("REDIS_USER=sub2api_prod0\nREDIS_DB=1\nREDIS_KEY_PREFIX=sub2api:\n", encoding="utf-8")
            # Create the file that the traversal path would resolve to, so the check
            # cannot be a naive startswith(prefix) + exists(path) against the raw string.
            escaped_pg = resource_root(root, "prod0-main", "newapi") / "postgres.env"
            escaped_pg.parent.mkdir(parents=True, exist_ok=True)
            escaped_pg.write_text("PGDATABASE=sub2api_prod0\nPGUSER=sub2api_prod0\n", encoding="utf-8")
            contract_file = write_contract(
                root,
                tenant_resources={
                    "postgres": {
                        "required": True,
                        "database": "sub2api_prod0",
                        "user": "sub2api_prod0",
                        # Looks in-scope by prefix, but escapes the app directory after normalization.
                        "secret_file": resource_relative("prod0-main", "sub2api", "postgres").replace(
                            "/postgres.env", "/../newapi/postgres.env"
                        ),
                    },
                    "redis": {
                        "required": True,
                        "user": "sub2api_prod0",
                        "db": 1,
                        "key_prefix": "sub2api:",
                        "secret_file": resource_relative("prod0-main", "sub2api", "redis"),
                    },
                },
            )

            result = run_app_delivery_cli("validate-contract", repo_root=root, app="sub2api")

            self.assertNotEqual(result.returncode, 0)
            combined = result.stdout + result.stderr
            # Keep the existing scope error id contract-side as well.
            self.assertIn(ERROR_ID_TENANT_SECRET_FILE_SCOPE, combined)
            self.assertIn(
                resource_relative("prod0-main", "sub2api", "postgres").replace(
                    "/postgres.env", "/../newapi/postgres.env"
                ),
                combined,
            )
            # When validate emits JSON, prefer schema-level assertions.
            try:
                payload = json.loads(result.stdout)
            except json.JSONDecodeError:
                payload = None
            if isinstance(payload, dict):
                items = payload.get("errors") or payload.get("violations") or payload.get("findings") or []
                if isinstance(items, list):
                    ids = {item.get("id") for item in items if isinstance(item, dict)}
                    self.assertIn(ERROR_ID_TENANT_SECRET_FILE_SCOPE, ids)

    def test_validate_contract_tenant_requires_minio_tenant_resource_when_contract_declares_minio_dependency(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root)
            write_app_resource_registry(root, baseline_app_resource_registry_payload())
            # Ensure tenant secret files exist so the failure is stable and about missing
            # tenant_resources.minio (not secret-file preconditions).
            pg = resource_root(root, "prod0-main", "sub2api") / "postgres.env"
            pg.parent.mkdir(parents=True, exist_ok=True)
            pg.write_text("PGDATABASE=sub2api_prod0\nPGUSER=sub2api_prod0\n", encoding="utf-8")
            redis = resource_root(root, "prod0-main", "sub2api") / "redis.env"
            redis.parent.mkdir(parents=True, exist_ok=True)
            redis.write_text("REDIS_USER=sub2api_prod0\nREDIS_DB=1\nREDIS_KEY_PREFIX=sub2api:\n", encoding="utf-8")
            contract_file = write_contract(
                root,
                dependencies=["postgres18-prod", "redis7-prod", "minio-prod"],
                tenant_resources={
                    "postgres": {
                        "required": True,
                        "database": "sub2api_prod0",
                        "user": "sub2api_prod0",
                        "secret_file": resource_relative("prod0-main", "sub2api", "postgres"),
                    },
                    "redis": {
                        "required": True,
                        "user": "sub2api_prod0",
                        "db": 1,
                        "key_prefix": "sub2api:",
                        "secret_file": resource_relative("prod0-main", "sub2api", "redis"),
                    },
                },
            )

            result = run_app_delivery_cli("validate-contract", repo_root=root, app="sub2api")

            self.assertNotEqual(result.returncode, 0)
            self.assertIn(ERROR_ID_TENANT_RESOURCES_REQUIRED, result.stdout + result.stderr)

    def test_validate_contract_tenant_rejects_cross_app_minio_secret_file_reference(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root)
            write_app_resource_registry(root, baseline_app_resource_registry_payload())
            # Ensure the referenced secret files exist so the test is stable against
            # future validation ordering (we want to lock in the scope error).
            pg = resource_root(root, "prod0-main", "sub2api") / "postgres.env"
            pg.parent.mkdir(parents=True, exist_ok=True)
            pg.write_text("PGDATABASE=sub2api_prod0\nPGUSER=sub2api_prod0\n", encoding="utf-8")
            redis = resource_root(root, "prod0-main", "sub2api") / "redis.env"
            redis.parent.mkdir(parents=True, exist_ok=True)
            redis.write_text("REDIS_USER=sub2api_prod0\nREDIS_DB=1\nREDIS_KEY_PREFIX=sub2api:\n", encoding="utf-8")
            bad_minio = root / "secrets" / "app-resources" / "prod0-main" / "newapi" / "minio.env"
            bad_minio.parent.mkdir(parents=True, exist_ok=True)
            bad_minio.write_text("S3_BUCKET=prod0-sub2api\nS3_ACCESS_KEY=sub2api_prod0\nS3_SECRET_KEY=sub2api-s3-secret\n", encoding="utf-8")
            contract_file = write_contract(
                root,
                tenant_resources={
                    "postgres": {
                        "required": True,
                        "database": "sub2api_prod0",
                        "user": "sub2api_prod0",
                        "secret_file": resource_relative("prod0-main", "sub2api", "postgres"),
                    },
                    "redis": {
                        "required": True,
                        "user": "sub2api_prod0",
                        "db": 1,
                        "key_prefix": "sub2api:",
                        "secret_file": resource_relative("prod0-main", "sub2api", "redis"),
                    },
                    "minio": {
                        "required": True,
                        "bucket": "prod0-sub2api",
                        "access_key": "sub2api_prod0",
                        "secret_file": resource_relative("prod0-main", "newapi", "minio"),
                    },
                },
            )

            result = run_app_delivery_cli("validate-contract", repo_root=root, app="sub2api")

            self.assertNotEqual(result.returncode, 0)
            self.assertIn(ERROR_ID_TENANT_SECRET_FILE_SCOPE, result.stdout + result.stderr)

    def test_validate_contract_tenant_rejects_minio_names_mismatched_with_registry(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root)
            write_app_resource_registry(root, baseline_app_resource_registry_payload())
            # Ensure the referenced secret files exist so the test is stable against
            # future validation ordering (we want to lock in the registry mismatch error).
            pg = resource_root(root, "prod0-main", "sub2api") / "postgres.env"
            pg.parent.mkdir(parents=True, exist_ok=True)
            pg.write_text("PGDATABASE=sub2api_prod0\nPGUSER=sub2api_prod0\n", encoding="utf-8")
            redis = resource_root(root, "prod0-main", "sub2api") / "redis.env"
            redis.parent.mkdir(parents=True, exist_ok=True)
            redis.write_text("REDIS_USER=sub2api_prod0\nREDIS_DB=1\nREDIS_KEY_PREFIX=sub2api:\n", encoding="utf-8")
            minio = resource_root(root, "prod0-main", "sub2api") / "minio.env"
            minio.parent.mkdir(parents=True, exist_ok=True)
            minio.write_text("S3_BUCKET=prod0-sub2api\nS3_ACCESS_KEY=sub2api_prod0\nS3_SECRET_KEY=sub2api-s3-secret\n", encoding="utf-8")
            contract_file = write_contract(
                root,
                tenant_resources={
                    "postgres": {
                        "required": True,
                        "database": "sub2api_prod0",
                        "user": "sub2api_prod0",
                        "secret_file": resource_relative("prod0-main", "sub2api", "postgres"),
                    },
                    "redis": {
                        "required": True,
                        "user": "sub2api_prod0",
                        "db": 1,
                        "key_prefix": "sub2api:",
                        "secret_file": resource_relative("prod0-main", "sub2api", "redis"),
                    },
                    "minio": {
                        "required": True,
                        "bucket": "prod0-sub2api-wrong",
                        "access_key": "sub2api_prod0",
                        "secret_file": resource_relative("prod0-main", "sub2api", "minio"),
                    },
                },
            )

            result = run_app_delivery_cli("validate-contract", repo_root=root, app="sub2api")

            self.assertNotEqual(result.returncode, 0)
            self.assertIn(ERROR_ID_TENANT_REGISTRY_MISMATCH, result.stdout + result.stderr)

    def test_validate_contract_tenant_rejects_names_mismatched_with_registry(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root)
            write_app_resource_registry(root, baseline_app_resource_registry_payload())
            # Ensure the referenced secret files exist so the test is stable against
            # future validation ordering (we want to lock in the registry mismatch error).
            pg = resource_root(root, "prod0-main", "sub2api") / "postgres.env"
            pg.parent.mkdir(parents=True, exist_ok=True)
            pg.write_text("PGDATABASE=sub2api_prod0\nPGUSER=sub2api_prod0\n", encoding="utf-8")
            redis = resource_root(root, "prod0-main", "sub2api") / "redis.env"
            redis.parent.mkdir(parents=True, exist_ok=True)
            redis.write_text("REDIS_USER=sub2api_prod0\nREDIS_DB=1\nREDIS_KEY_PREFIX=sub2api:\n", encoding="utf-8")
            contract_file = write_contract(
                root,
                tenant_resources={
                    "postgres": {
                        "required": True,
                        "database": "sub2api_wrong_db",
                        "user": "sub2api_prod0",
                        "secret_file": resource_relative("prod0-main", "sub2api", "postgres"),
                    },
                    "redis": {
                        "required": True,
                        "user": "sub2api_wrong_user",
                        "db": 1,
                        "key_prefix": "sub2api:",
                        "secret_file": resource_relative("prod0-main", "sub2api", "redis"),
                    },
                },
            )

            result = run_app_delivery_cli("validate-contract", repo_root=root, app="sub2api")

            self.assertNotEqual(result.returncode, 0)
            self.assertIn(ERROR_ID_TENANT_REGISTRY_MISMATCH, result.stdout + result.stderr)

    def test_delivery_actions_fail_on_registry_truth_drift_before_side_effects(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root)
            write_tenant_secret_files(root)
            registry_payload = baseline_app_resource_registry_payload()
            registry_payload["sub2api"]["postgres"]["database"] = "sub2api_wrong"
            write_app_resource_registry(root, registry_payload)
            write_contract(root, tenant_resources=baseline_tenant_resources())

            inventory_file = root / "inventory" / "servers" / "prod0-main" / "inventory.json"
            inventory_before = inventory_file.read_text(encoding="utf-8")
            server_readme = root / "inventory" / "servers" / "prod0-main" / "README.md"
            app_summary = root / "docs" / "AGENTPLANE_DEPLOYMENT.md"
            ledger_root = root / "tmp" / "operation-ledger"
            actions = {
                "validate-contract": (),
                "render-runtime": (),
                "deploy": ("--image-ref", "sub2api-prod:test", "--dry-run"),
                "verify": ("--dry-run",),
                "rollback": ("--dry-run",),
                "inventory-refresh": ("--write",),
            }

            for action, extra_args in actions.items():
                with self.subTest(action=action):
                    result = run_app_delivery_cli(action, repo_root=root, app="sub2api", extra_args=extra_args)

                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn(ERROR_ID_TENANT_REGISTRY_MISMATCH, result.stdout + result.stderr)
                    self.assertEqual(inventory_before, inventory_file.read_text(encoding="utf-8"))
                    self.assertFalse(server_readme.exists())
                    self.assertFalse(app_summary.exists())
                    self.assertFalse(ledger_root.exists())

    def test_deploy_rejects_secret_scope_before_planning_steps(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root)
            write_app_resource_registry(root, baseline_app_resource_registry_payload())
            bad_pg = resource_root(root, "prod0-main", "newapi") / "postgres.env"
            bad_pg.parent.mkdir(parents=True, exist_ok=True)
            bad_pg.write_text("PGDATABASE=sub2api_prod0\nPGUSER=sub2api_prod0\n", encoding="utf-8")
            bad_redis = resource_root(root, "prod0-main", "newapi") / "redis.env"
            bad_redis.write_text("REDIS_DB=1\nREDIS_KEY_PREFIX=sub2api:\n", encoding="utf-8")
            write_contract(
                root,
                tenant_resources={
                    "postgres": {
                        "required": True,
                        "database": "sub2api_prod0",
                        "user": "sub2api_prod0",
                        "secret_file": resource_relative("prod0-main", "newapi", "postgres"),
                    },
                    "redis": {
                        "required": True,
                        "db": 1,
                        "key_prefix": "sub2api:",
                        "secret_file": resource_relative("prod0-main", "newapi", "redis"),
                    },
                },
            )

            result = run_app_delivery_cli(
                "deploy",
                repo_root=root,
                app="sub2api",
                extra_args=("--image-ref", "sub2api-prod:test", "--dry-run"),
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn(ERROR_ID_TENANT_SECRET_FILE_SCOPE, result.stdout + result.stderr)
            self.assertFalse((root / "tmp" / "operation-ledger").exists())

    def test_validate_contract_tenant_accepts_secret_file_resolution_from_common_secrets_root_in_worktree(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            main_root = tmp_root / "main"
            worktree_root = tmp_root / "worktree"
            git_worktree_dir = main_root / ".git" / "worktrees" / "demo"
            git_worktree_dir.mkdir(parents=True, exist_ok=True)
            worktree_root.mkdir(parents=True, exist_ok=True)
            (worktree_root / ".git").write_text(f"gitdir: {git_worktree_dir}\n", encoding="utf-8")

            write_inventory(worktree_root)
            write_app_resource_registry(worktree_root, baseline_app_resource_registry_payload())
            pg = resource_root(main_root, "prod0-main", "sub2api") / "postgres.env"
            pg.parent.mkdir(parents=True, exist_ok=True)
            pg.write_text("PGDATABASE=sub2api_prod0\nPGUSER=sub2api_prod0\n", encoding="utf-8")
            redis = resource_root(main_root, "prod0-main", "sub2api") / "redis.env"
            redis.parent.mkdir(parents=True, exist_ok=True)
            redis.write_text("REDIS_DB=1\nREDIS_KEY_PREFIX=sub2api:\n", encoding="utf-8")
            contract_file = write_contract(
                worktree_root,
                tenant_resources={
                    "postgres": {
                        "required": True,
                        "database": "sub2api_prod0",
                        "user": "sub2api_prod0",
                        "secret_file": resource_relative("prod0-main", "sub2api", "postgres"),
                    },
                    "redis": {
                        "required": True,
                        "db": 1,
                        "key_prefix": "sub2api:",
                        "secret_file": resource_relative("prod0-main", "sub2api", "redis"),
                    },
                },
            )

            result = run_app_delivery_cli("validate-contract", repo_root=worktree_root, app="sub2api")

            self.assertEqual(result.returncode, 0, msg=result.stderr)

    def test_validate_contract_prefers_explicit_app_repo_root_over_catalog_repo_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            repo_root = tmp_root / "oplinux"
            canonical_root = tmp_root / "sub2api"
            worktree_root = tmp_root / "sub2api.worktree"
            repo_root.mkdir(parents=True, exist_ok=True)
            canonical_root.mkdir(parents=True, exist_ok=True)
            worktree_root.mkdir(parents=True, exist_ok=True)

            write_inventory(repo_root)
            write_app_resource_registry(repo_root, baseline_app_resource_registry_payload())
            write_tenant_secret_files(repo_root)
            write_target_contract(
                canonical_root,
                tenant_resources=baseline_tenant_resources(),
                env_template="deploy/canonical.env.example",
            )
            write_target_contract(
                worktree_root,
                tenant_resources=baseline_tenant_resources(),
                env_template="deploy/worktree.env.example",
            )
            write_app_catalog_entry(
                repo_root,
                app="sub2api",
                repo_name="sub2api",
                app_root=canonical_root,
                service_key="sub2api",
                contracts={"prod0-main": "deploy/agentplane/contract.yaml"},
            )

            result = run_app_delivery_cli(
                "validate-contract",
                repo_root=repo_root,
                app="sub2api",
                extra_args=("--app-repo-root", str(worktree_root)),
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(result.stdout)["payload"]
            self.assertEqual("deploy/worktree.env.example", payload["runtime"]["env_template"])
            self.assertEqual(str(worktree_root.resolve()), payload["_meta"]["app_root"])
            self.assertEqual(str((worktree_root / "deploy" / "agentplane" / "contract.yaml").resolve()), payload["_meta"]["contract_file"])

    def test_validate_contract_skips_registry_alignment_when_tenant_resources_declares_no_supported_kinds(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            inventory_file = root / "inventory" / "servers" / "prod0-main" / "inventory.json"
            inventory_file.parent.mkdir(parents=True, exist_ok=True)
            inventory_file.write_text(
                json.dumps(
                    {
                        "ssh": {"aliases": ["prod0-main"]},
                        "services": {"edgeproxy": {"container_name": "edgeproxy-prod"}},
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            write_app_resource_registry(root, {"otherapp": {"owner_app": "otherapp"}})
            contract_file = write_contract(
                root,
                dependencies=["edgeproxy-prod"],
                tenant_resources={},
            )

            result = run_app_delivery_cli("validate-contract", repo_root=root, app="sub2api")

            self.assertEqual(result.returncode, 0, msg=result.stderr)


if __name__ == "__main__":
    unittest.main()

