from __future__ import annotations

import json
import os
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml
from agentplane.domain.app.resource_paths import app_resource_secret_dir
from agentplane.domain.app.runtime import _secrets_root
from agentplane.runtime.host_profile import HostProfile
from tests.support.app_delivery_cli import run_app_delivery_cli, run_cli
from tests.support.app_delivery_contracts import (
    ERROR_ID_TENANT_REGISTRY_MISMATCH,
    ERROR_ID_TENANT_RESOURCES_REQUIRED,
    ERROR_ID_TENANT_SECRET_FILE_MISSING,
    ERROR_ID_TENANT_SECRET_FILE_SCOPE,
    init_git_repo,
    init_git_repo_with_tag,
    sync_app_catalog_for_contract,
    write_app_catalog_entry,
    write_contract,
    write_prod2_contract,
    write_sampleapi_contract,
    write_target_contract,
)
from tests.support.app_delivery_targets import (
    assert_live_db_partition_markers,
    baseline_app_resource_registry_payload,
    baseline_tenant_resources,
    write_app_resource_registry,
    write_compose_template,
    write_fake_bridge_network_ssh,
    write_fake_command,
    write_internal_worker_compose_template,
    write_inventory,
    write_prod2_compose_template,
    write_prod2_inventory,
    write_prod2_tenant_registry,
    write_prod2_tenant_secret_files,
    write_sampleapi_compose_templates,
    write_sampleapi_tenant_files,
    write_tenant_secret_files,
)
from tests.support.app_resources import resource_relative, resource_root
from tests.support.paths import REPO_ROOT

pytestmark = pytest.mark.e2e

class TestAppDeliveryBuildCliTests(unittest.TestCase):
    def test_build_artifact_executes_script_build_command_with_image_tag(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root)
            write_tenant_secret_files(root)
            deploy_dir = root / "deploy"
            deploy_dir.mkdir(parents=True, exist_ok=True)
            script_file = deploy_dir / "build-runtime-artifacts.sh"
            output_dir = root / "dist" / "oplinux"
            output_file = root / ".artifact-build.json"
            script_file.write_text(
                "\n".join(
                    [
                        "#!/usr/bin/env bash",
                        "set -euo pipefail",
                        f'mkdir -p "{output_dir}"',
                        f'printf \'{{\"image_tag\":\"%s\",\"output_path\":\"%s\"}}\' \"$IMAGE_TAG\" \"$ARTIFACT_OUTPUT_PATH\" > "{output_file}"',
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            script_file.chmod(0o755)
            write_contract(
                root,
                schema_version=2,
                tenant_resources=baseline_tenant_resources(),
                build_command="bash deploy/build-runtime-artifacts.sh",
                package_command="bash deploy/package-runtime-image.sh",
            )

            result = run_cli(
                "app",
                "delivery",
                "build-artifact",
                "--target",
                "prod0-main",
                "--app",
                "sub2api",
                "--repo-root",
                str(root),
                "--image-tag",
                "verify-tag",
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual("build-artifact", payload["action"])
            self.assertEqual("sub2api-prod:verify-tag", payload["payload"]["packaging"]["image_ref"])
            self.assertEqual("bash deploy/build-runtime-artifacts.sh", payload["payload"]["command"])
            self.assertEqual(str(output_dir.resolve()), payload["payload"]["artifact"]["output_path"])
            build_manifest = json.loads(output_file.read_text(encoding="utf-8"))
            self.assertEqual("verify-tag", build_manifest["image_tag"])
            self.assertEqual(str(output_dir.resolve()), build_manifest["output_path"])

    def test_build_artifact_dry_run_emits_recommended_versions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root)
            write_tenant_secret_files(root)
            (root / "backend" / "cmd" / "server").mkdir(parents=True, exist_ok=True)
            (root / "backend" / "cmd" / "server" / "VERSION").write_text("0.1.104\n", encoding="utf-8")
            sha = init_git_repo(root)
            write_contract(
                root,
                schema_version=2,
                tenant_resources=baseline_tenant_resources(),
                build_command="bash deploy/build-runtime-artifacts.sh",
                package_command="bash deploy/package-runtime-image.sh",
            )

            result = run_app_delivery_cli(
                "build-artifact",
                repo_root=root,
                app="sub2api",
                extra_args=("--dry-run",),
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(result.stdout)["payload"]
            versioning = payload["recommended_versions"]
            today = datetime.now(UTC).strftime("%Y%m%d")
            self.assertEqual(f"zzz.{today}.v1.g{sha}", versioning["fork_version"])
            self.assertEqual(f"0.1.104+zzz.{today}.v1.g{sha}", versioning["delivery_version"])
            self.assertEqual(f"0.1.104-zzz.{today}.v1.g{sha}", versioning["image_tag"])
            self.assertEqual("sub2api-prod:local", payload["packaging"]["image_ref"])

    def test_build_artifact_auto_version_executes_with_recommended_image_tag(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root)
            write_tenant_secret_files(root)
            (root / "backend" / "cmd" / "server").mkdir(parents=True, exist_ok=True)
            (root / "backend" / "cmd" / "server" / "VERSION").write_text("0.1.104\n", encoding="utf-8")
            sha = init_git_repo(root)
            deploy_dir = root / "deploy"
            deploy_dir.mkdir(parents=True, exist_ok=True)
            script_file = deploy_dir / "build-runtime-artifacts.sh"
            output_file = root / ".built-image-tag"
            script_file.write_text(
                "\n".join(
                    [
                        "#!/usr/bin/env bash",
                        "set -euo pipefail",
                        'mkdir -p "$ARTIFACT_OUTPUT_PATH"',
                        f'printf \"%s\" \"$IMAGE_TAG\" > \"{output_file}\"',
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            script_file.chmod(0o755)
            write_contract(
                root,
                schema_version=2,
                tenant_resources=baseline_tenant_resources(),
                build_command="bash deploy/build-runtime-artifacts.sh",
                package_command="bash deploy/package-runtime-image.sh",
            )

            result = run_app_delivery_cli(
                "build-artifact",
                repo_root=root,
                app="sub2api",
                extra_args=("--auto-version",),
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(result.stdout)["payload"]
            today = datetime.now(UTC).strftime("%Y%m%d")
            expected_tag = f"0.1.104-zzz.{today}.v1.g{sha}"
            self.assertEqual(f"sub2api-prod:{expected_tag}", payload["packaging"]["image_ref"])
            self.assertEqual(expected_tag, output_file.read_text(encoding="utf-8"))

    def test_build_artifact_auto_version_exposes_recommended_version_env_vars(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root)
            write_tenant_secret_files(root)
            (root / "backend" / "cmd" / "server").mkdir(parents=True, exist_ok=True)
            (root / "backend" / "cmd" / "server" / "VERSION").write_text("0.1.104\n", encoding="utf-8")
            sha = init_git_repo(root)
            deploy_dir = root / "deploy"
            deploy_dir.mkdir(parents=True, exist_ok=True)
            script_file = deploy_dir / "build-runtime-artifacts.sh"
            output_file = root / ".build-env.json"
            script_file.write_text(
                "\n".join(
                    [
                        "#!/usr/bin/env bash",
                        "set -euo pipefail",
                        'mkdir -p "$ARTIFACT_OUTPUT_PATH"',
                        f'printf \'{{\"image_tag\":\"%s\",\"fork_version\":\"%s\",\"delivery_version\":\"%s\"}}\' "$IMAGE_TAG" "${{FORK_VERSION:-}}" "${{DELIVERY_VERSION:-}}" > "{output_file}"',
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            script_file.chmod(0o755)
            write_contract(
                root,
                schema_version=2,
                tenant_resources=baseline_tenant_resources(),
                build_command="bash deploy/build-runtime-artifacts.sh",
                package_command="bash deploy/package-runtime-image.sh",
            )

            result = run_app_delivery_cli(
                "build-artifact",
                repo_root=root,
                app="sub2api",
                extra_args=("--auto-version",),
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            build_env = json.loads(output_file.read_text(encoding="utf-8"))
            today = datetime.now(UTC).strftime("%Y%m%d")
            fork_version = f"zzz.{today}.v1.g{sha}"
            self.assertEqual(f"0.1.104-{fork_version}", build_env["image_tag"])
            self.assertEqual(fork_version, build_env["fork_version"])
            self.assertEqual(f"0.1.104+{fork_version}", build_env["delivery_version"])

    def test_build_artifact_auto_version_uses_git_tag_when_version_file_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_prod2_inventory(root)
            write_app_resource_registry(
                root,
                {
                    "sampleapi": {
                        "owner_app": "sampleapi",
                        "postgres": {"database": "sampleapi_prod2", "user": "sampleapi_prod2"},
                        "redis": {"db": 2, "key_prefix": "sampleapi:"},
                        "minio": {
                            "bucket": "prod2-sampleapi",
                            "access_key": "sampleapi_prod2",
                            "policy_name": "prod2-sampleapi-rw",
                            "policy_scope": "bucket-only",
                            "isolation_level": "bucket-scoped-rw",
                        },
                        "secret_files": [
                            resource_relative("prod2-main", "sampleapi", "postgres"),
                            resource_relative("prod2-main", "sampleapi", "redis"),
                            resource_relative("prod2-main", "sampleapi", "minio"),
                        ],
                    }
                },
                target="prod2-main",
            )
            write_sampleapi_tenant_files(root, target="prod2-main", include_minio=True)
            sha = init_git_repo_with_tag(root, "v0.11.9-alpha.2")
            deploy_dir = root / "deploy"
            deploy_dir.mkdir(parents=True, exist_ok=True)
            script_file = deploy_dir / "build-runtime-artifacts.sh"
            output_file = root / ".built-image-tag"
            script_file.write_text(
                "\n".join(
                    [
                        "#!/usr/bin/env bash",
                        "set -euo pipefail",
                        'mkdir -p "$ARTIFACT_OUTPUT_PATH"',
                        f'printf \"%s\" \"$IMAGE_TAG\" > \"{output_file}\"',
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            script_file.chmod(0o755)
            write_sampleapi_contract(
                root,
                target="prod2-main",
                include_minio=True,
                schema_version=2,
                build_command="bash deploy/build-runtime-artifacts.sh",
                package_command="bash deploy/package-runtime-image.sh",
            )

            result = run_app_delivery_cli(
                "build-artifact",
                repo_root=root,
                app="sampleapi",
                target="prod2-main",
                extra_args=("--auto-version",),
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(result.stdout)["payload"]
            today = datetime.now(UTC).strftime("%Y%m%d")
            expected_tag = f"v0.11.9-alpha.2-zzz.{today}.v1.g{sha}"
            self.assertEqual(f"sampleapi-prod:{expected_tag}", payload["packaging"]["image_ref"])
            self.assertEqual(expected_tag, output_file.read_text(encoding="utf-8"))

    def test_build_artifact_dry_run_does_not_consume_fork_sequence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root)
            write_tenant_secret_files(root)
            (root / "backend" / "cmd" / "server").mkdir(parents=True, exist_ok=True)
            (root / "backend" / "cmd" / "server" / "VERSION").write_text("0.1.104\n", encoding="utf-8")
            sha = init_git_repo(root)
            write_contract(
                root,
                schema_version=2,
                tenant_resources=baseline_tenant_resources(),
                build_command="bash deploy/build-runtime-artifacts.sh",
                package_command="bash deploy/package-runtime-image.sh",
            )

            first = run_app_delivery_cli(
                "build-artifact",
                repo_root=root,
                app="sub2api",
                extra_args=("--dry-run", "--auto-version"),
            )
            second = run_app_delivery_cli(
                "build-artifact",
                repo_root=root,
                app="sub2api",
                extra_args=("--dry-run", "--auto-version"),
            )

            self.assertEqual(first.returncode, 0, msg=first.stderr)
            self.assertEqual(second.returncode, 0, msg=second.stderr)
            today = datetime.now(UTC).strftime("%Y%m%d")
            expected_tag = f"0.1.104-zzz.{today}.v1.g{sha}"
            self.assertEqual(expected_tag, json.loads(first.stdout)["payload"]["recommended_versions"]["image_tag"])
            self.assertEqual(expected_tag, json.loads(second.stdout)["payload"]["recommended_versions"]["image_tag"])

    def test_package_runtime_executes_packaging_command_with_explicit_artifact_output_and_image_ref(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root)
            write_tenant_secret_files(root)
            deploy_dir = root / "deploy"
            deploy_dir.mkdir(parents=True, exist_ok=True)
            build_script = deploy_dir / "build-runtime-artifacts.sh"
            package_script = deploy_dir / "package-runtime-image.sh"
            package_output = root / ".package-runtime.json"
            build_script.write_text(
                "\n".join(
                    [
                        "#!/usr/bin/env bash",
                        "set -euo pipefail",
                        'mkdir -p "$ARTIFACT_OUTPUT_PATH"',
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            package_script.write_text(
                "\n".join(
                    [
                        "#!/usr/bin/env bash",
                        "set -euo pipefail",
                        f'printf \'{{\"image_ref\":\"%s\",\"artifact_output_path\":\"%s\"}}\' \"$IMAGE_REF\" \"$ARTIFACT_OUTPUT_PATH\" > "{package_output}"',
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            build_script.chmod(0o755)
            package_script.chmod(0o755)
            write_contract(
                root,
                schema_version=2,
                tenant_resources=baseline_tenant_resources(),
                build_command="bash deploy/build-runtime-artifacts.sh",
                package_command="bash deploy/package-runtime-image.sh",
            )

            build_result = run_app_delivery_cli(
                "build-artifact",
                repo_root=root,
                app="sub2api",
                extra_args=("--image-tag", "verify-tag"),
            )
            self.assertEqual(build_result.returncode, 0, msg=build_result.stderr)

            package_result = run_app_delivery_cli(
                "package-runtime",
                repo_root=root,
                app="sub2api",
                extra_args=("--image-tag", "verify-tag"),
            )

            self.assertEqual(package_result.returncode, 0, msg=package_result.stderr)
            payload = json.loads(package_result.stdout)["payload"]
            self.assertEqual("sub2api-prod:verify-tag", payload["image_ref"])
            self.assertEqual("native-posix", payload["backend"])
            package_manifest = json.loads(package_output.read_text(encoding="utf-8"))
            self.assertEqual("sub2api-prod:verify-tag", package_manifest["image_ref"])
            self.assertEqual(str((root / "dist" / "oplinux").resolve()), package_manifest["artifact_output_path"])

    def test_ship_image_requires_explicit_image_ref(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root)
            write_tenant_secret_files(root)
            write_contract(root, tenant_resources=baseline_tenant_resources())

            result = run_cli(
                "app",
                "delivery",
                "ship-image",
                "--target",
                "prod0-main",
                "--app",
                "sub2api",
                "--repo-root",
                str(root),
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("--image-ref", result.stderr)

    def test_build_artifact_prefers_explicit_app_repo_root_over_catalog_repo_root(self) -> None:
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
            write_target_contract(canonical_root, tenant_resources=baseline_tenant_resources(), schema_version=2)
            write_target_contract(
                worktree_root,
                tenant_resources=baseline_tenant_resources(),
                schema_version=2,
                build_command="bash deploy/build-runtime-artifacts.sh",
                package_command="bash deploy/package-runtime-image.sh",
            )
            write_app_catalog_entry(
                repo_root,
                app="sub2api",
                repo_name="sub2api",
                app_root=canonical_root,
                service_key="sub2api",
                contracts={"prod0-main": "deploy/agentplane/contract.yaml"},
            )

            deploy_dir = worktree_root / "deploy"
            deploy_dir.mkdir(parents=True, exist_ok=True)
            output_file = worktree_root / ".built-image-tag"
            script_file = deploy_dir / "build-runtime-artifacts.sh"
            script_file.write_text(
                "\n".join(
                    [
                        "#!/usr/bin/env bash",
                        "set -euo pipefail",
                        'mkdir -p "$ARTIFACT_OUTPUT_PATH"',
                        f'printf \"%s\" \"$IMAGE_TAG\" > \"{output_file}\"',
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            script_file.chmod(0o755)

            result = run_app_delivery_cli(
                "build-artifact",
                repo_root=repo_root,
                app="sub2api",
                extra_args=("--image-tag", "worktree-tag", "--app-repo-root", str(worktree_root)),
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(result.stdout)["payload"]
            self.assertEqual(str(worktree_root.resolve()), payload["cwd"])
            self.assertEqual("worktree-tag", output_file.read_text(encoding="utf-8"))

# ======================================================================
# From: test_app_delivery_deploy_rollback_cli.py
# ======================================================================

class TestAppDeliveryDeployRollbackCliTests(unittest.TestCase):
    def test_deploy_post_actions_prefers_explicit_app_repo_root_over_catalog_repo_root(self) -> None:
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
            write_compose_template(repo_root)
            write_target_contract(
                canonical_root,
                tenant_resources=baseline_tenant_resources(include_minio=True),
                docs_config={"app_summary_file": "docs/CANONICAL.md"},
            )
            write_target_contract(
                worktree_root,
                tenant_resources=baseline_tenant_resources(include_minio=True),
                docs_config={"app_summary_file": "docs/WORKTREE.md"},
            )
            write_app_catalog_entry(
                repo_root,
                app="sub2api",
                repo_name="sub2api",
                app_root=canonical_root,
                service_key="sub2api",
                contracts={"prod0-main": "deploy/agentplane/contract.yaml"},
            )
            tenant_root = app_resource_secret_dir(repo_root, "prod0-main", "sub2api")
            tenant_root.mkdir(parents=True, exist_ok=True)
            (tenant_root / "postgres.env").write_text(
                "PGHOST=postgres18-prod\nPGPORT=5432\nPGDATABASE=sub2api_prod0\nPGUSER=sub2api_prod0\nPGPASSWORD=secret\n",
                encoding="utf-8",
            )
            (tenant_root / "redis.env").write_text(
                "REDIS_HOST=redis7-prod\nREDIS_PORT=6379\nREDIS_DB=1\nREDIS_KEY_PREFIX=sub2api:\nREDIS_PASSWORD=redis-secret\nREDIS_ENABLE_TLS=false\n",
                encoding="utf-8",
            )
            (tenant_root / "minio.env").write_text(
                "S3_BUCKET=prod0-sub2api\nS3_ACCESS_KEY=sub2api_prod0\nS3_SECRET_KEY=sub2api-s3-secret\n",
                encoding="utf-8",
            )

            result = run_app_delivery_cli(
                "deploy",
                repo_root=repo_root,
                app="sub2api",
                extra_args=("--image-ref", "sub2api-prod:test", "--dry-run", "--app-repo-root", str(worktree_root)),
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(result.stdout)["payload"]
            post_actions = payload["post_actions"]["steps"]
            doc_sync_step = next(item for item in post_actions if item["action"] == "app.delivery.doc-sync")
            self.assertIn(str((worktree_root / "docs" / "WORKTREE.md").resolve()), doc_sync_step["payload"]["app_docs"])
            self.assertNotIn(str((canonical_root / "docs" / "CANONICAL.md").resolve()), doc_sync_step["payload"]["app_docs"])

    def test_deploy_dry_run_includes_env_sync(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root)
            write_tenant_secret_files(root)
            write_contract(root, tenant_resources=baseline_tenant_resources())
            write_compose_template(root)

            result = run_cli(
                "app",
                "delivery",
                "deploy",
                "--target",
                "prod0-main",
                "--app",
                "sub2api",
                "--repo-root",
                str(root),
                "--dry-run",
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual("/data/sub2api/config/sub2api-prod.env", payload["payload"]["remote_env"])
            self.assertTrue(payload["payload"]["local_env"].replace("\\", "/").endswith("secrets/services/sub2api.prod0.env"))
            commands = "\n".join(payload["payload"]["commands"])
            self.assertIn("root@prod0-main", commands)
            self.assertNotIn("sudo ", commands)
            self.assertIn("install -Dm600 /tmp/sub2api.prod0.env /data/sub2api/config/sub2api-prod.env", commands)
            operation = payload["payload"]["operation"]
            ledger_file = Path(operation["ledger_file"])
            self.assertTrue(ledger_file.is_file())
            entry = json.loads(ledger_file.read_text(encoding="utf-8").strip().splitlines()[-1])
            self.assertEqual(operation["op_id"], entry["op_id"])
            self.assertEqual("app", entry["command"])
            self.assertEqual("deploy", entry["action"])
            self.assertEqual("prod0-main", entry["target"])
            self.assertEqual("planned", entry["result"])

    def test_deploy_rejects_dry_run_with_execute(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root)
            write_tenant_secret_files(root)
            write_contract(root, tenant_resources=baseline_tenant_resources())
            write_compose_template(root)

            result = run_app_delivery_cli(
                "deploy",
                repo_root=root,
                app="sub2api",
                extra_args=("--dry-run", "--execute"),
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("not allowed with argument", result.stderr)

    def test_deploy_execute_runs_remote_sync_and_cutover_commands(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root, include_managed_bridge_networks=True)
            write_tenant_secret_files(root)
            write_app_resource_registry(root, baseline_app_resource_registry_payload())
            write_compose_template(root)
            write_contract(root, tenant_resources=baseline_tenant_resources())
            tenant_root = app_resource_secret_dir(root, "prod0-main", "sub2api")
            (tenant_root / "redis.env").write_text(
                "REDIS_HOST=redis7-prod\nREDIS_PORT=6379\nREDIS_DB=1\nREDIS_KEY_PREFIX=sub2api:\nREDIS_PASSWORD=redis-secret\nREDIS_ENABLE_TLS=false\n",
                encoding="utf-8",
            )
            (tenant_root / "minio.env").write_text(
                "S3_BUCKET=prod0-sub2api\nS3_ACCESS_KEY=sub2api_prod0\nS3_SECRET_KEY=sub2api-s3-secret\n",
                encoding="utf-8",
            )
            (root / "secrets" / "services").mkdir(parents=True, exist_ok=True)
            (root / "secrets" / "services" / "sub2api.prod0.env").write_text("SERVER_PORT=8080\n", encoding="utf-8")
            (root / "secrets" / "ssh").mkdir(parents=True, exist_ok=True)
            (root / "secrets" / "ssh" / "config").write_text("Host prod0-main\n", encoding="utf-8")
            bin_dir = root / "bin"
            bin_dir.mkdir(parents=True, exist_ok=True)
            log_file = root / "command.log"
            state_dir = root / "fake-network-state"
            state_dir.mkdir(parents=True, exist_ok=True)
            write_fake_command(
                bin_dir,
                "scp",
                "#!/usr/bin/env bash\nset -euo pipefail\nprintf 'scp %s\\n' \"$*\" >> \"$FAKE_CMD_LOG\"\n",
            )
            write_fake_bridge_network_ssh(bin_dir)

            result = run_app_delivery_cli(
                "deploy",
                repo_root=root,
                app="sub2api",
                extra_args=("--image-ref", "sub2api-prod:test", "--execute"),
                env_overrides={
                    "PATH": f"{bin_dir}:{os.environ['PATH']}",
                    "FAKE_CMD_LOG": str(log_file),
                    "FAKE_NETWORK_STATE_DIR": str(state_dir),
                },
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(result.stdout)["payload"]
            self.assertTrue(payload["ok"])
            log_text = log_file.read_text(encoding="utf-8")
            self.assertIn("docker network inspect zqf_network", log_text)
            self.assertIn("ip addr add 172.19.0.1/16 dev br-66f7da1be943", log_text)
            self.assertIn("scp -F", log_text)
            self.assertIn("/opt/agentplane/infra/compose/sub2api/docker-compose.prod0.yml", log_text)
            self.assertIn("/data/sub2api/config/sub2api-prod.env", log_text)
            self.assertIn("systemctl disable --now sub2api || true", log_text)
            self.assertIn("docker compose -f docker-compose.prod0.yml up -d --pull never", log_text)

    def test_deploy_dry_run_uses_prod2_specific_remote_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_prod2_inventory(root)
            write_prod2_tenant_secret_files(root)
            write_prod2_tenant_registry(root)
            write_prod2_contract(root)
            write_prod2_compose_template(root)

            result = run_app_delivery_cli(
                "deploy",
                repo_root=root,
                app="sub2api",
                target="prod2-main",
                extra_args=("--image-ref", "sub2api-prod:test", "--dry-run"),
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual("/opt/agentplane/secrets/services/sub2api.prod2.env", payload["payload"]["remote_env"])
            self.assertEqual("/opt/agentplane/infra/compose/sub2api/docker-compose.prod2.yml", payload["payload"]["remote_compose"])
            self.assertTrue(payload["payload"]["local_env"].replace("\\", "/").endswith("secrets/services/sub2api.prod2.env"))
            commands = "\n".join(payload["payload"]["commands"])
            self.assertIn("root@prod2-main", commands)
            self.assertIn("install -Dm600 /tmp/sub2api.prod2.env /opt/agentplane/secrets/services/sub2api.prod2.env", commands)
            self.assertIn("docker compose -f docker-compose.prod2.yml up -d --pull never", commands)

    def test_verify_execute_returns_origin_and_public_results(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root, include_managed_bridge_networks=True)
            write_tenant_secret_files(root)
            write_app_resource_registry(root, baseline_app_resource_registry_payload())
            write_contract(root, tenant_resources=baseline_tenant_resources())
            (root / "secrets" / "ssh").mkdir(parents=True, exist_ok=True)
            (root / "secrets" / "ssh" / "config").write_text("Host prod0-main\n", encoding="utf-8")
            bin_dir = root / "bin"
            bin_dir.mkdir(parents=True, exist_ok=True)
            log_file = root / "verify.log"
            state_dir = root / "fake-network-state"
            state_dir.mkdir(parents=True, exist_ok=True)
            write_fake_bridge_network_ssh(bin_dir)
            write_fake_command(
                bin_dir,
                "curl",
                "#!/usr/bin/env bash\nset -euo pipefail\nprintf 'curl %s\\n' \"$*\" >> \"$FAKE_CMD_LOG\"\n",
            )

            result = run_app_delivery_cli(
                "verify",
                repo_root=root,
                app="sub2api",
                extra_args=("--execute",),
                env_overrides={
                    "PATH": f"{bin_dir}:{os.environ['PATH']}",
                    "FAKE_CMD_LOG": str(log_file),
                    "FAKE_NETWORK_STATE_DIR": str(state_dir),
                },
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(result.stdout)["payload"]
            self.assertTrue(payload["ok"])
            self.assertIn("origin", payload["checks"])
            self.assertIn("public", payload["checks"])
            self.assertEqual(2, len(payload["checks"]["origin"]))
            self.assertEqual(2, len(payload["checks"]["public"]))
            inspect_stdout = payload["checks"]["origin"][0]["stdout"]
            self.assertIn("DATABASE_PASSWORD=<redacted>", inspect_stdout)
            self.assertIn("REDIS_PASSWORD=<redacted>", inspect_stdout)
            self.assertNotIn("db-secret", inspect_stdout)
            self.assertNotIn("redis-secret", inspect_stdout)
            log_text = log_file.read_text(encoding="utf-8")
            self.assertIn("docker network inspect zqf_network", log_text)
            self.assertIn("docker inspect sub2api-prod", log_text)
            self.assertIn("http://127.0.0.1:18080/health", log_text)
            self.assertIn("https://token.zzzai.cloud:8443/health", log_text)
            self.assertIn("https://token.zzzai.cloud:8443/", log_text)

    def test_verify_execute_propagates_public_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root, include_managed_bridge_networks=True)
            write_tenant_secret_files(root)
            write_app_resource_registry(root, baseline_app_resource_registry_payload())
            write_contract(root, tenant_resources=baseline_tenant_resources())
            (root / "secrets" / "ssh").mkdir(parents=True, exist_ok=True)
            (root / "secrets" / "ssh" / "config").write_text("Host prod0-main\n", encoding="utf-8")
            bin_dir = root / "bin"
            bin_dir.mkdir(parents=True, exist_ok=True)
            log_file = root / "verify-failure.log"
            state_dir = root / "fake-network-state"
            state_dir.mkdir(parents=True, exist_ok=True)
            write_fake_bridge_network_ssh(bin_dir)
            write_fake_command(
                bin_dir,
                "curl",
                "#!/usr/bin/env bash\nset -euo pipefail\nif printf '%s' \"$*\" | grep -q '/health'; then exit 7; fi\nexit 0\n",
            )

            result = run_app_delivery_cli(
                "verify",
                repo_root=root,
                app="sub2api",
                extra_args=("--execute",),
                env_overrides={
                    "PATH": f"{bin_dir}:{os.environ['PATH']}",
                    "FAKE_CMD_LOG": str(log_file),
                    "FAKE_NETWORK_STATE_DIR": str(state_dir),
                },
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertNotIn("invalid choice: 'delivery'", result.stderr)
            payload = json.loads(result.stdout)["payload"]
            self.assertFalse(payload["ok"])
            self.assertFalse(payload["checks"]["public"][0]["ok"])

    def test_deploy_dry_run_uses_main_repo_secrets_when_repo_root_is_worktree(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            main_root = tmp_root / "main"
            worktree_root = tmp_root / "worktree"
            git_worktree_dir = main_root / ".git" / "worktrees" / "demo"
            (main_root / "secrets" / "services").mkdir(parents=True, exist_ok=True)
            (main_root / "secrets" / "ssh").mkdir(parents=True, exist_ok=True)
            (main_root / "secrets" / "services" / "sub2api.prod0.env").write_text("SERVER_PORT=8080\n", encoding="utf-8")
            git_worktree_dir.mkdir(parents=True, exist_ok=True)
            worktree_root.mkdir(parents=True, exist_ok=True)
            (worktree_root / ".git").write_text(f"gitdir: {git_worktree_dir}\n", encoding="utf-8")
            compose_dir = worktree_root / "infra" / "compose" / "sub2api"
            compose_dir.mkdir(parents=True, exist_ok=True)
            (compose_dir / "docker-compose.prod0.yml").write_text(
                yaml.safe_dump(
                    {
                        "services": {
                            "sub2api": {
                                "image": "sub2api-prod:latest",
                                "container_name": "sub2api-prod",
                                "ports": ["127.0.0.1:18080:8080"],
                                "environment": {},
                            }
                        }
                    },
                    sort_keys=False,
                    allow_unicode=False,
                ),
                encoding="utf-8",
            )
            write_inventory(worktree_root)
            write_tenant_secret_files(main_root)
            write_contract(worktree_root, tenant_resources=baseline_tenant_resources())

            result = run_app_delivery_cli(
                "deploy",
                repo_root=worktree_root,
                app="sub2api",
                extra_args=("--image-ref", "sub2api-prod:test", "--dry-run"),
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(
                str(main_root / "secrets" / "services" / "sub2api.prod0.env"),
                payload["payload"]["local_env"],
            )
            commands = "\n".join(payload["payload"]["commands"])
            self.assertIn(str(main_root / "secrets" / "ssh" / "config"), commands)
            self.assertIn("root@prod0-main", commands)

    def test_deploy_dry_run_keeps_sudo_when_inventory_user_is_not_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root)
            inventory_file = root / "inventory" / "servers" / "prod0-main" / "inventory.json"
            payload = json.loads(inventory_file.read_text(encoding="utf-8"))
            payload["ssh"]["user"] = "ubuntu"
            inventory_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            write_tenant_secret_files(root)
            write_contract(root, tenant_resources=baseline_tenant_resources())
            write_compose_template(root)

            result = run_app_delivery_cli(
                "deploy",
                repo_root=root,
                app="sub2api",
                extra_args=("--image-ref", "sub2api-prod:test", "--dry-run"),
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            commands = "\n".join(json.loads(result.stdout)["payload"]["commands"])
            self.assertIn("ubuntu@prod0-main", commands)
            self.assertIn("sudo bash -lc", commands)

    def test_deploy_dry_run_stops_1panel_app_control_plane_for_sampleapi(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root)
            write_sampleapi_tenant_files(root)
            write_sampleapi_contract(root)
            write_sampleapi_compose_templates(root)

            result = run_app_delivery_cli(
                "deploy",
                repo_root=root,
                app="sampleapi",
                extra_args=("--image-ref", "sampleapi-prod:test", "--dry-run"),
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(result.stdout)
            commands = "\n".join(payload["payload"]["commands"])
            self.assertIn("uv run python -m agentplane.providers.onepanel_transition --target prod0-main app --operate stop --install-id 3", commands)
            self.assertNotIn("systemctl stop", commands)

    def test_rollback_dry_run_starts_1panel_app_control_plane_for_sampleapi(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root)
            write_sampleapi_tenant_files(root)
            write_sampleapi_contract(root)
            write_sampleapi_compose_templates(root)

            result = run_app_delivery_cli(
                "rollback",
                repo_root=root,
                app="sampleapi",
                extra_args=("--dry-run",),
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(result.stdout)
            commands = "\n".join(payload["payload"]["commands"])
            self.assertIn("uv run python -m agentplane.providers.onepanel_transition --target prod0-main app --operate start --install-id 3", commands)
            self.assertNotIn("systemctl start", commands)

    def test_deploy_dry_run_stops_1panel_compose_control_plane(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root)
            write_sampleapi_tenant_files(root)
            write_sampleapi_contract(
                root,
                rollback_entry={
                    "kind": "1panel-compose",
                    "project_name": "samplepay-prod",
                    "container_name": "samplepay-prod",
                    "project_path": "/data/1panel/docker/compose/samplepay-prod",
                    "compose_file": "/data/1panel/docker/compose/samplepay-prod/docker-compose.yml",
                },
            )
            write_sampleapi_compose_templates(root)

            result = run_app_delivery_cli(
                "deploy",
                repo_root=root,
                app="sampleapi",
                extra_args=("--image-ref", "sampleapi-prod:test", "--dry-run"),
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            commands = "\n".join(json.loads(result.stdout)["payload"]["commands"])
            self.assertIn(
                "uv run python -m agentplane.providers.onepanel_transition --target prod0-main project --name samplepay-prod --operate stop",
                commands,
            )
            self.assertNotIn("systemctl stop", commands)

    def test_rollback_dry_run_starts_1panel_compose_control_plane(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root)
            write_sampleapi_tenant_files(root)
            write_sampleapi_contract(
                root,
                rollback_entry={
                    "kind": "1panel-compose",
                    "project_name": "samplepay-prod",
                    "container_name": "samplepay-prod",
                    "project_path": "/data/1panel/docker/compose/samplepay-prod",
                    "compose_file": "/data/1panel/docker/compose/samplepay-prod/docker-compose.yml",
                },
            )
            write_sampleapi_compose_templates(root)

            result = run_app_delivery_cli(
                "rollback",
                repo_root=root,
                app="sampleapi",
                extra_args=("--dry-run",),
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            commands = "\n".join(json.loads(result.stdout)["payload"]["commands"])
            self.assertIn(
                "uv run python -m agentplane.providers.onepanel_transition --target prod0-main project --name samplepay-prod --operate up",
                commands,
            )
            self.assertNotIn("systemctl start", commands)

    def test_deploy_execute_runs_onepanel_compose_stop_instead_of_systemd(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root, include_managed_bridge_networks=True)
            write_sampleapi_tenant_files(root)
            write_sampleapi_compose_templates(root)
            write_sampleapi_contract(
                root,
                rollback_entry={
                    "kind": "1panel-compose",
                    "project_name": "samplepay-prod",
                    "container_name": "samplepay-prod",
                    "project_path": "/data/1panel/docker/compose/samplepay-prod",
                    "compose_file": "/data/1panel/docker/compose/samplepay-prod/docker-compose.yml",
                },
            )
            (root / "secrets" / "services").mkdir(parents=True, exist_ok=True)
            (root / "secrets" / "services" / "sampleapi.prod0.env").write_text("PORT=3000\n", encoding="utf-8")
            (root / "secrets" / "ssh").mkdir(parents=True, exist_ok=True)
            (root / "secrets" / "ssh" / "config").write_text("Host prod0-main\n", encoding="utf-8")
            bin_dir = root / "bin"
            bin_dir.mkdir(parents=True, exist_ok=True)
            log_file = root / "onepanel-compose-deploy.log"
            state_dir = root / "fake-network-state"
            state_dir.mkdir(parents=True, exist_ok=True)
            write_fake_bridge_network_ssh(bin_dir)
            write_fake_command(
                bin_dir,
                "scp",
                "#!/usr/bin/env bash\nset -euo pipefail\nprintf 'scp %s\\n' \"$*\" >> \"$FAKE_CMD_LOG\"\n",
            )
            write_fake_command(
                bin_dir,
                "uv",
                "#!/usr/bin/env bash\nset -euo pipefail\nprintf 'uv %s\\n' \"$*\" >> \"$FAKE_CMD_LOG\"\n",
            )

            result = run_app_delivery_cli(
                "deploy",
                repo_root=root,
                app="sampleapi",
                extra_args=("--image-ref", "sampleapi-prod:test", "--execute"),
                env_overrides={
                    "PATH": f"{bin_dir}:{os.environ['PATH']}",
                    "FAKE_CMD_LOG": str(log_file),
                    "FAKE_NETWORK_STATE_DIR": str(state_dir),
                },
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(result.stdout)["payload"]
            self.assertTrue(payload["ok"])
            log_text = log_file.read_text(encoding="utf-8")
            self.assertIn(
                "uv run python -m agentplane.providers.onepanel_transition --target prod0-main project --name samplepay-prod --operate stop",
                log_text,
            )
            self.assertNotIn("systemctl stop", log_text)

    def test_rollback_execute_runs_onepanel_compose_up_instead_of_systemd(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root)
            write_sampleapi_tenant_files(root)
            write_sampleapi_compose_templates(root)
            write_sampleapi_contract(
                root,
                rollback_entry={
                    "kind": "1panel-compose",
                    "project_name": "samplepay-prod",
                    "container_name": "samplepay-prod",
                    "project_path": "/data/1panel/docker/compose/samplepay-prod",
                    "compose_file": "/data/1panel/docker/compose/samplepay-prod/docker-compose.yml",
                },
            )
            (root / "secrets" / "ssh").mkdir(parents=True, exist_ok=True)
            (root / "secrets" / "ssh" / "config").write_text("Host prod0-main\n", encoding="utf-8")
            bin_dir = root / "bin"
            bin_dir.mkdir(parents=True, exist_ok=True)
            log_file = root / "onepanel-compose-rollback.log"
            write_fake_command(
                bin_dir,
                "ssh",
                "#!/usr/bin/env bash\nset -euo pipefail\nprintf 'ssh %s\\n' \"$*\" >> \"$FAKE_CMD_LOG\"\n",
            )
            write_fake_command(
                bin_dir,
                "uv",
                "#!/usr/bin/env bash\nset -euo pipefail\nprintf 'uv %s\\n' \"$*\" >> \"$FAKE_CMD_LOG\"\n",
            )

            result = run_app_delivery_cli(
                "rollback",
                repo_root=root,
                app="sampleapi",
                extra_args=("--execute",),
                env_overrides={
                    "PATH": f"{bin_dir}:{os.environ['PATH']}",
                    "FAKE_CMD_LOG": str(log_file),
                },
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(result.stdout)["payload"]
            self.assertTrue(payload["ok"])
            log_text = log_file.read_text(encoding="utf-8")
            self.assertIn(
                "uv run python -m agentplane.providers.onepanel_transition --target prod0-main project --name samplepay-prod --operate up",
                log_text,
            )
            self.assertNotIn("systemctl start", log_text)

    def test_rollback_execute_runs_compose_down_and_systemd_start(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root)
            write_tenant_secret_files(root)
            write_app_resource_registry(root, baseline_app_resource_registry_payload())
            write_contract(root, tenant_resources=baseline_tenant_resources())
            (root / "secrets" / "ssh").mkdir(parents=True, exist_ok=True)
            (root / "secrets" / "ssh" / "config").write_text("Host prod0-main\n", encoding="utf-8")
            bin_dir = root / "bin"
            bin_dir.mkdir(parents=True, exist_ok=True)
            log_file = root / "rollback.log"
            write_fake_command(
                bin_dir,
                "ssh",
                "#!/usr/bin/env bash\nset -euo pipefail\nprintf 'ssh %s\\n' \"$*\" >> \"$FAKE_CMD_LOG\"\n",
            )

            result = run_app_delivery_cli(
                "rollback",
                repo_root=root,
                app="sub2api",
                extra_args=("--execute",),
                env_overrides={
                    "PATH": f"{bin_dir}:{os.environ['PATH']}",
                    "FAKE_CMD_LOG": str(log_file),
                },
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(result.stdout)["payload"]
            self.assertTrue(payload["ok"])
            log_text = log_file.read_text(encoding="utf-8")
            self.assertIn("docker compose -f docker-compose.prod0.yml down || true", log_text)
            self.assertIn("systemctl enable --now sub2api || true", log_text)

    def test_deploy_dry_run_skips_transition_when_no_previous_control_plane(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root)
            write_sampleapi_tenant_files(root)
            write_sampleapi_contract(
                root,
                rollback_entry={
                    "kind": "none",
                    "note": "no previous control plane retained; rollback requires manual image restore",
                },
            )
            write_sampleapi_compose_templates(root)

            result = run_app_delivery_cli(
                "deploy",
                repo_root=root,
                app="sampleapi",
                extra_args=("--image-ref", "sampleapi-prod:test", "--dry-run"),
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(result.stdout)
            commands = "\n".join(payload["payload"]["commands"])
            self.assertNotIn("agentplane/scripts/onepanel/app_lifecycle.py", commands)
            self.assertNotIn("agentplane/scripts/onepanel/project_lifecycle.py", commands)
            self.assertNotIn("systemctl stop", commands)
            self.assertIn("docker compose -f docker-compose.prod0.yml up -d", commands)

    def test_rollback_dry_run_warns_when_no_previous_control_plane(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root)
            write_sampleapi_tenant_files(root)
            write_sampleapi_contract(
                root,
                rollback_entry={
                    "kind": "none",
                    "note": "no previous control plane retained; rollback requires manual image restore",
                },
            )
            write_sampleapi_compose_templates(root)

            result = run_app_delivery_cli(
                "rollback",
                repo_root=root,
                app="sampleapi",
                extra_args=("--dry-run",),
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual([], payload["payload"]["commands"])
            self.assertIn("manual image restore", payload["payload"]["warning"])

# ======================================================================
# From: test_app_delivery_render_verify_cli.py
# ======================================================================

class TestAppDeliveryRenderVerifyCliTests(unittest.TestCase):
    def test_render_runtime_outputs_sub2api_prod_compose(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root)
            write_tenant_secret_files(root)
            write_contract(root, tenant_resources=baseline_tenant_resources())
            write_compose_template(root)

            result = run_app_delivery_cli(
                "render-runtime",
                repo_root=root,
                app="sub2api",
                extra_args=("--image-ref", "sub2api-prod:test"),
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual("render-runtime", payload["action"])
            self.assertEqual("sub2api-prod", payload["payload"]["container_name"])
            content = payload["payload"]["compose"]
            self.assertIn("image: sub2api-prod:test", content)
            self.assertIn("container_name: sub2api-prod", content)
            self.assertIn("127.0.0.1:18080:8080", content)
            self.assertIn("postgres18-prod", content)
            self.assertIn("redis7-prod", content)
            self.assertIn("zqf_network", content)
            self.assertIn("/data/sub2api/config/sub2api-prod.env", content)

    def test_render_runtime_outputs_sub2api_prod2_compose(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_prod2_inventory(root)
            write_prod2_tenant_secret_files(root)
            write_prod2_tenant_registry(root)
            write_prod2_contract(root)
            write_prod2_compose_template(root)

            result = run_app_delivery_cli(
                "render-runtime",
                repo_root=root,
                app="sub2api",
                target="prod2-main",
                extra_args=("--image-ref", "sub2api-prod:test"),
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual("sub2api-prod", payload["payload"]["container_name"])
            self.assertTrue(payload["payload"]["compose_file"].endswith("docker-compose.prod2.yml"))
            content = payload["payload"]["compose"]
            self.assertIn("image: sub2api-prod:test", content)
            self.assertIn("container_name: sub2api-prod", content)
            self.assertIn("127.0.0.1:18080:8080", content)
            self.assertIn("postgres18-prod", content)
            self.assertIn("redis7-prod", content)

    def test_render_runtime_outputs_sampleapi_wsl_compose_with_public_binding(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root)
            write_app_resource_registry(
                root,
                {
                    "sampleapi": {
                        "owner_app": "sampleapi",
                        "postgres": {"database": "sampleapi_wsl", "user": "sampleapi_wsl"},
                        "redis": {"db": 2, "key_prefix": "sampleapi:wsl:"},
                        "secret_files": [
                            resource_relative("wsl", "sampleapi", "postgres"),
                            resource_relative("wsl", "sampleapi", "redis"),
                        ],
                    }
                },
                target="wsl",
            )
            write_sampleapi_tenant_files(root, target="wsl")
            write_sampleapi_contract(root, target="wsl")
            write_sampleapi_compose_templates(root)

            result = run_app_delivery_cli(
                "render-runtime",
                repo_root=root,
                app="sampleapi",
                target="wsl",
                extra_args=("--image-ref", "sampleapi-dev:test"),
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual("sampleapi-dev", payload["payload"]["container_name"])
            compose = payload["payload"]["compose"]
            self.assertIn("image: sampleapi-dev:test", compose)
            self.assertIn("container_name: sampleapi-dev", compose)
            self.assertIn("0.0.0.0:3000:3000", compose)
            self.assertIn("DATABASE_HOST: postgres18-dev", compose)
            self.assertIn("REDIS_HOST: redis7-dev", compose)

    def test_render_runtime_outputs_sampleapi_prod2_compose_with_prod2_env(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_prod2_inventory(root)
            write_app_resource_registry(
                root,
                {
                    "sampleapi": {
                        "owner_app": "sampleapi",
                        "postgres": {"database": "sampleapi_prod2", "user": "sampleapi_prod2"},
                        "redis": {"db": 2, "key_prefix": "sampleapi:"},
                        "minio": {
                            "bucket": "prod2-sampleapi",
                            "access_key": "sampleapi_prod2",
                            "policy_name": "prod2-sampleapi-rw",
                            "policy_scope": "bucket-only",
                            "isolation_level": "bucket-scoped-rw",
                        },
                        "secret_files": [
                            resource_relative("prod2-main", "sampleapi", "postgres"),
                            resource_relative("prod2-main", "sampleapi", "redis"),
                            resource_relative("prod2-main", "sampleapi", "minio"),
                        ],
                    }
                },
                target="prod2-main",
            )
            write_sampleapi_tenant_files(root, target="prod2-main", include_minio=True)
            write_sampleapi_contract(root, target="prod2-main", include_minio=True)
            write_sampleapi_compose_templates(root, include_prod2=True)

            result = run_app_delivery_cli(
                "render-runtime",
                repo_root=root,
                app="sampleapi",
                target="prod2-main",
                extra_args=("--image-ref", "sampleapi-prod:test"),
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual("sampleapi-prod", payload["payload"]["container_name"])
            self.assertTrue(payload["payload"]["compose_file"].endswith("docker-compose.prod2.yml"))
            compose = payload["payload"]["compose"]
            self.assertIn("image: sampleapi-prod:test", compose)
            self.assertIn("container_name: sampleapi-prod", compose)
            self.assertIn("../../../secrets/services/sampleapi.prod2.env", compose)
            self.assertIn("127.0.0.1:3000:3000", compose)

    def test_render_runtime_keeps_internal_worker_without_default_db_env(self) -> None:
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
            payload["app_id"] = "sample-register-v2"
            payload["artifact"]["image_name"] = "sample-register-v2-prod"
            payload["runtime"]["container_name"] = "sample-register-v2-prod"
            payload["runtime"]["container_port"] = 18081
            payload["runtime"]["host_binding"] = "127.0.0.1:18081"
            payload["runtime"]["healthcheck"] = {"path": "/healthz", "expected_status": 200}
            payload["data"]["mounts"] = [{"host_path": "/data/sample-register-v2/data", "container_path": "/data"}]
            payload["inventory"]["service_key"] = "sample-register-v2"
            contract_file.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=False), encoding="utf-8")
            sync_app_catalog_for_contract(root, contract_file=contract_file, app="sample-register-v2", service_key="sample-register-v2")
            write_internal_worker_compose_template(root)

            result = run_app_delivery_cli(
                "render-runtime",
                repo_root=root,
                app="sample-register-v2",
                extra_args=("--image-ref", "sample-register-v2-prod:test"),
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            compose = json.loads(result.stdout)["payload"]["compose"]
            self.assertIn("image: sample-register-v2-prod:test", compose)
            self.assertIn("127.0.0.1:18081:18081", compose)
            self.assertNotIn("DATABASE_HOST", compose)
            self.assertNotIn("REDIS_HOST", compose)

    def test_verify_app_uses_local_host_binding_for_wsl_target(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root)
            write_app_resource_registry(
                root,
                {
                    "sampleapi": {
                        "owner_app": "sampleapi",
                        "postgres": {"database": "sampleapi_wsl", "user": "sampleapi_wsl"},
                        "redis": {"db": 2, "key_prefix": "sampleapi:wsl:"},
                        "secret_files": [
                            resource_relative("wsl", "sampleapi", "postgres"),
                            resource_relative("wsl", "sampleapi", "redis"),
                        ],
                    }
                },
                target="wsl",
            )
            write_sampleapi_tenant_files(root, target="wsl")
            write_sampleapi_contract(root, target="wsl")

            result = run_app_delivery_cli(
                "verify",
                repo_root=root,
                app="sampleapi",
                target="wsl",
                extra_args=("--dry-run",),
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual("sampleapi-dev", payload["payload"]["container_name"])
            commands = payload["payload"]["commands"]
            self.assertEqual(["curl -fsS http://127.0.0.1:3000/api/status"], commands)

    def test_verify_app_execute_waits_for_container_health_before_origin_healthcheck(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root, include_managed_bridge_networks=True)
            write_tenant_secret_files(root)
            write_app_resource_registry(root, baseline_app_resource_registry_payload())
            write_contract(root, tenant_resources=baseline_tenant_resources())
            (root / "secrets" / "ssh").mkdir(parents=True, exist_ok=True)
            (root / "secrets" / "ssh" / "config").write_text("Host prod0-main\n", encoding="utf-8")
            bin_dir = root / "bin"
            bin_dir.mkdir(parents=True, exist_ok=True)
            log_file = root / "verify-wait.log"
            state_dir = root / "fake-network-state"
            state_dir.mkdir(parents=True, exist_ok=True)
            write_fake_bridge_network_ssh(bin_dir)
            write_fake_command(
                bin_dir,
                "curl",
                "#!/usr/bin/env bash\nset -euo pipefail\nprintf 'curl %s\\n' \"$*\" >> \"$FAKE_CMD_LOG\"\n",
            )

            result = run_app_delivery_cli(
                "verify",
                repo_root=root,
                app="sub2api",
                extra_args=("--execute",),
                env_overrides={
                    "PATH": f"{bin_dir}:{os.environ['PATH']}",
                    "FAKE_CMD_LOG": str(log_file),
                    "FAKE_NETWORK_STATE_DIR": str(state_dir),
                },
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(result.stdout)["payload"]
            self.assertTrue(payload["ok"])
            commands = payload["commands"]
            self.assertEqual(4, len(commands))
            self.assertIn("docker inspect sub2api-prod", commands[0])
            self.assertIn("for i in $(seq 1 12)", commands[1])
            self.assertIn("curl -fsS http://127.0.0.1:18080/health", commands[1])
            self.assertEqual(commands[1], payload["checks"]["origin"][1]["display"])
            self.assertIn("curl -fsS https://token.zzzai.cloud:8443/health", commands[2])
            self.assertIn("curl -fsSI https://token.zzzai.cloud:8443/", commands[3])
            ssh_log = log_file.read_text(encoding="utf-8")
            self.assertIn("docker inspect sub2api-prod", ssh_log)
            self.assertIn("for i in $(seq 1 12)", ssh_log)

    def test_deploy_app_execute_runs_local_compose_for_wsl_target(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root)
            write_app_resource_registry(
                root,
                {
                    "sampleapi": {
                        "owner_app": "sampleapi",
                        "postgres": {"database": "sampleapi_wsl", "user": "sampleapi_wsl"},
                        "redis": {"user": "", "db": 2, "key_prefix": "sampleapi:wsl:"},
                        "secret_files": [
                            resource_relative("wsl", "sampleapi", "postgres"),
                            resource_relative("wsl", "sampleapi", "redis"),
                        ],
                    }
                },
                target="wsl",
            )
            write_sampleapi_tenant_files(root, target="wsl")
            write_sampleapi_compose_templates(root)
            service_env = root / "secrets" / "services" / "sampleapi.wsl.env"
            service_env.parent.mkdir(parents=True, exist_ok=True)
            service_env.write_text("APP_DATABASE_URL=postgresql://sampleapi_wsl:secret@postgres18-dev:5432/sampleapi_wsl\n", encoding="utf-8")
            write_sampleapi_contract(root, target="wsl")
            bin_dir = root / "bin"
            bin_dir.mkdir(parents=True, exist_ok=True)
            log_file = root / "wsl-deploy.log"
            write_fake_command(
                bin_dir,
                "docker",
                "#!/usr/bin/env bash\nset -euo pipefail\nprintf 'docker %s\\n' \"$*\" >> \"$FAKE_CMD_LOG\"\n",
            )

            result = run_app_delivery_cli(
                "deploy",
                repo_root=root,
                app="sampleapi",
                target="wsl",
                extra_args=("--image-ref", "sampleapi-dev:test", "--execute"),
                env_overrides={
                    "PATH": f"{bin_dir}:{os.environ['PATH']}",
                    "FAKE_CMD_LOG": str(log_file),
                },
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(result.stdout)["payload"]
            self.assertEqual("sampleapi-dev", payload["container_name"])
            self.assertTrue(payload["ok"])
            self.assertIn("docker compose -f", payload["commands"][0])
            self.assertIn("docker compose -f", log_file.read_text(encoding="utf-8"))

    def test_deploy_app_execute_uses_backend_runner_for_wsl_target_on_windows_host(self) -> None:
        import agentplane.domain.app.runtime as app_runtime

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root)
            write_app_resource_registry(
                root,
                {
                    "sampleapi": {
                        "owner_app": "sampleapi",
                        "postgres": {"database": "sampleapi_wsl", "user": "sampleapi_wsl"},
                        "redis": {"user": "", "db": 2, "key_prefix": "sampleapi:wsl:"},
                        "secret_files": [
                            resource_relative("wsl", "sampleapi", "postgres"),
                            resource_relative("wsl", "sampleapi", "redis"),
                        ],
                    }
                },
                target="wsl",
            )
            write_sampleapi_tenant_files(root, target="wsl")
            write_sampleapi_compose_templates(root)
            service_env = root / "secrets" / "services" / "sampleapi.wsl.env"
            service_env.parent.mkdir(parents=True, exist_ok=True)
            service_env.write_text("APP_DATABASE_URL=postgresql://sampleapi_wsl:secret@postgres18-dev:5432/sampleapi_wsl\n", encoding="utf-8")
            contract_file = write_sampleapi_contract(root, target="wsl")
            contract = app_runtime.validate_contract(contract_file, repo_root=root, target="wsl")

            class _FakeExecutionResult:
                def __init__(self, plan) -> None:
                    self.plan = plan
                    self.ok = True

                def to_payload(self) -> dict[str, object]:
                    return {
                        "backend_type": self.plan.backend_type,
                        "argv": list(self.plan.argv),
                        "display": "wsl.exe -e bash -lc docker compose",
                        "cwd": None,
                        "returncode": 0,
                        "stdout": "",
                        "stderr": "",
                        "ok": True,
                    }

            class _FakeRunner:
                def __init__(self) -> None:
                    self.plan = None

                def execute(self, plan, *, bindings=None):
                    self.plan = plan
                    return _FakeExecutionResult(plan)

            runner = _FakeRunner()
            with patch(
                "agentplane.domain.app.runtime.detect_host_profile",
                return_value=HostProfile(os_name="windows", linux_backend="windows-wsl", supports_docker=True),
            ), patch("agentplane.domain.app.runtime.build_backend_runner", return_value=runner):
                payload = app_runtime.deploy_app(
                    contract,
                    repo_root=root,
                    target="wsl",
                    image_ref="sampleapi-dev:test",
                    dry_run=False,
                    execute=True,
                )

            self.assertEqual("windows-wsl", runner.plan.backend_type)
            self.assertEqual("windows-wsl", payload["backend_type"])
            self.assertEqual("windows-wsl", payload["results"][0]["backend_type"])
            self.assertEqual(["docker", "compose"], payload["results"][0]["argv"][:2])

    def test_deploy_app_execute_uses_canonical_service_env_for_wsl_worktree(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            outer_root = Path(tmp) / "repo-root"
            worktree_root = outer_root / ".worktrees" / "codex" / "release"
            worktree_root.mkdir(parents=True, exist_ok=True)
            git_worktree_dir = outer_root / ".git" / "worktrees" / "release"
            git_worktree_dir.mkdir(parents=True, exist_ok=True)
            (worktree_root / ".git").write_text(f"gitdir: {git_worktree_dir}\n", encoding="utf-8")
            (worktree_root / "secrets").symlink_to(outer_root / "secrets")
            write_inventory(worktree_root)
            write_sampleapi_tenant_files(outer_root, target="wsl")
            write_app_resource_registry(
                worktree_root,
                {
                    "sampleapi": {
                        "owner_app": "sampleapi",
                        "postgres": {"database": "sampleapi_wsl", "user": "sampleapi_wsl"},
                        "redis": {"user": "", "db": 2, "key_prefix": "sampleapi:wsl:"},
                        "secret_files": [
                            resource_relative("wsl", "sampleapi", "postgres"),
                            resource_relative("wsl", "sampleapi", "redis"),
                        ],
                    }
                },
                target="wsl",
            )
            write_sampleapi_compose_templates(worktree_root)
            service_env = outer_root / "secrets" / "services" / "sampleapi.wsl.env"
            service_env.parent.mkdir(parents=True, exist_ok=True)
            service_env.write_text("APP_DATABASE_URL=postgresql://sampleapi_wsl:secret@postgres18-dev:5432/sampleapi_wsl\n", encoding="utf-8")
            write_sampleapi_contract(worktree_root, target="wsl")
            bin_dir = worktree_root / "bin"
            bin_dir.mkdir(parents=True, exist_ok=True)
            log_file = worktree_root / "wsl-deploy.log"
            write_fake_command(
                bin_dir,
                "docker",
                "#!/usr/bin/env bash\nset -euo pipefail\nprintf 'docker %s\\n' \"$*\" >> \"$FAKE_CMD_LOG\"\n",
            )

            result = run_app_delivery_cli(
                "deploy",
                repo_root=worktree_root,
                app="sampleapi",
                target="wsl",
                extra_args=("--image-ref", "sampleapi-dev:test", "--execute"),
                env_overrides={
                    "PATH": f"{bin_dir}:{os.environ['PATH']}",
                    "FAKE_CMD_LOG": str(log_file),
                },
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(result.stdout)["payload"]
            rendered_compose = Path(payload["compose_file"])
            compose_text = rendered_compose.read_text(encoding="utf-8")
            self.assertIn(str(service_env), compose_text)
            self.assertIn("DATABASE_HOST: postgres18-dev", compose_text)
            self.assertIn("REDIS_HOST: redis7-dev", compose_text)

    def test_verify_app_execute_runs_local_healthcheck_for_wsl_target(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root)
            write_app_resource_registry(
                root,
                {
                    "sampleapi": {
                        "owner_app": "sampleapi",
                        "postgres": {"database": "sampleapi_wsl", "user": "sampleapi_wsl"},
                        "redis": {"user": "", "db": 2, "key_prefix": "sampleapi:wsl:"},
                        "secret_files": [
                            resource_relative("wsl", "sampleapi", "postgres"),
                            resource_relative("wsl", "sampleapi", "redis"),
                        ],
                    }
                },
                target="wsl",
            )
            write_sampleapi_tenant_files(root, target="wsl")
            write_sampleapi_contract(root, target="wsl")
            bin_dir = root / "bin"
            bin_dir.mkdir(parents=True, exist_ok=True)
            log_file = root / "wsl-verify.log"
            write_fake_command(
                bin_dir,
                "curl",
                "#!/usr/bin/env bash\nset -euo pipefail\nprintf 'curl %s\\n' \"$*\" >> \"$FAKE_CMD_LOG\"\necho '{\"status\":\"ok\"}'\n",
            )

            result = run_app_delivery_cli(
                "verify",
                repo_root=root,
                app="sampleapi",
                target="wsl",
                extra_args=("--execute",),
                env_overrides={
                    "PATH": f"{bin_dir}:{os.environ['PATH']}",
                    "FAKE_CMD_LOG": str(log_file),
                },
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(result.stdout)["payload"]
            self.assertEqual("sampleapi-dev", payload["container_name"])
            self.assertTrue(payload["ok"])
            self.assertEqual(["curl -fsS http://127.0.0.1:3000/api/status"], payload["commands"])
            self.assertIn("curl -fsS http://127.0.0.1:3000/api/status", log_file.read_text(encoding="utf-8"))

    def test_network_audit_reports_missing_gateway_and_route(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_prod2_inventory(root, include_managed_bridge_networks=True)
            (root / "secrets" / "ssh").mkdir(parents=True, exist_ok=True)
            (root / "secrets" / "ssh" / "config").write_text("Host prod2-main\n", encoding="utf-8")
            bin_dir = root / "bin"
            bin_dir.mkdir(parents=True, exist_ok=True)
            log_file = root / "network-audit.log"
            state_dir = root / "fake-network-state"
            state_dir.mkdir(parents=True, exist_ok=True)
            write_fake_bridge_network_ssh(bin_dir)

            result = run_cli(
                "infra",
                "network",
                "audit",
                "prod2-main",
                "--repo-root",
                str(root),
                env_overrides={
                    "PATH": f"{bin_dir}:{os.environ['PATH']}",
                    "FAKE_CMD_LOG": str(log_file),
                    "FAKE_NETWORK_STATE_DIR": str(state_dir),
                },
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual("infra", payload["command"])
            self.assertEqual("network.audit", payload["action"])
            self.assertFalse(payload["payload"]["ok"])
            network = payload["payload"]["networks"][0]
            self.assertEqual("zqf_network", network["name"])
            self.assertFalse(network["checks"]["gateway_ip_present"])
            self.assertFalse(network["checks"]["route_present"])
            self.assertEqual("br-66f7da1be943", network["bridge_interface"])

    def test_network_ensure_repairs_missing_gateway_and_route(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_prod2_inventory(root, include_managed_bridge_networks=True)
            (root / "secrets" / "ssh").mkdir(parents=True, exist_ok=True)
            (root / "secrets" / "ssh" / "config").write_text("Host prod2-main\n", encoding="utf-8")
            bin_dir = root / "bin"
            bin_dir.mkdir(parents=True, exist_ok=True)
            log_file = root / "network-ensure.log"
            state_dir = root / "fake-network-state"
            state_dir.mkdir(parents=True, exist_ok=True)
            write_fake_bridge_network_ssh(bin_dir)

            result = run_cli(
                "infra",
                "network",
                "ensure",
                "prod2-main",
                "--repo-root",
                str(root),
                env_overrides={
                    "PATH": f"{bin_dir}:{os.environ['PATH']}",
                    "FAKE_CMD_LOG": str(log_file),
                    "FAKE_NETWORK_STATE_DIR": str(state_dir),
                },
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual("infra", payload["command"])
            self.assertEqual("network.ensure", payload["action"])
            self.assertTrue(payload["payload"]["ok"])
            self.assertEqual(2, len(payload["payload"]["repairs"]))
            self.assertTrue((state_dir / "gateway_present").exists())
            self.assertTrue((state_dir / "route_present").exists())
            network = payload["payload"]["networks"][0]
            self.assertTrue(network["checks"]["gateway_ip_present"])
            self.assertTrue(network["checks"]["route_present"])
            log_text = log_file.read_text(encoding="utf-8")
            self.assertIn("docker network inspect zqf_network", log_text)
            self.assertIn("ip addr add 172.19.0.1/16 dev br-66f7da1be943", log_text)
            self.assertIn("ip route replace 172.19.0.0/16 dev br-66f7da1be943 src 172.19.0.1", log_text)

# ======================================================================
# From: test_app_delivery_validate_cli.py
# ======================================================================

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
            write_contract(root, tenant_resources=baseline_tenant_resources())

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
            write_sampleapi_tenant_files(root)
            write_sampleapi_contract(
                root,
                rollback_entry={
                    "kind": "1panel-compose",
                    "container_name": "samplepay-prod",
                    "project_path": "/data/1panel/docker/compose/samplepay-prod/docker-compose.yml",
                },
            )

            result = run_app_delivery_cli("validate-contract", repo_root=root, app="sampleapi")

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("rollback.previous_control_plane.kind=1panel-compose 缺少 project_name", result.stderr)

    def test_validate_contract_accepts_1panel_compose_with_compose_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root)
            write_sampleapi_tenant_files(root)
            write_sampleapi_contract(
                root,
                rollback_entry={
                    "kind": "1panel-compose",
                    "project_name": "samplepay-prod",
                    "container_name": "samplepay-prod",
                    "project_path": "/data/1panel/docker/compose/samplepay-prod",
                    "compose_file": "/data/1panel/docker/compose/samplepay-prod/docker-compose.yml",
                },
            )

            result = run_app_delivery_cli("validate-contract", repo_root=root, app="sampleapi")

            self.assertEqual(result.returncode, 0, msg=result.stderr)

    def test_validate_contract_accepts_legacy_contract_without_schema_version(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root)
            write_tenant_secret_files(root)
            write_contract(root, schema_version=None, tenant_resources=baseline_tenant_resources())

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
            write_contract(root, runtime_kind="binary")

            result = run_app_delivery_cli("validate-contract", repo_root=root, app="sub2api")

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("runtime.kind", result.stderr)

    def test_validate_contract_rejects_unknown_dependency_container(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root)
            write_contract(root, dependency="mysql-prod")

            result = run_app_delivery_cli("validate-contract", repo_root=root, app="sub2api")

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("depends_on_containers", result.stderr)

    def test_validate_contract_rejects_missing_container_name(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root)
            write_contract(root, include_container_name=False)

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
            payload["app_id"] = "sample-register-v2"
            payload["artifact"]["image_name"] = "sample-register-v2-prod"
            payload["runtime"]["container_name"] = "sample-register-v2-prod"
            payload["runtime"]["container_port"] = 18081
            payload["runtime"]["host_binding"] = "127.0.0.1:18081"
            payload["runtime"]["healthcheck"] = {"path": "/healthz", "expected_status": 200}
            payload["data"]["mounts"] = [{"host_path": "/data/sample-register-v2/data", "container_path": "/data"}]
            payload["inventory"]["service_key"] = "sample-register-v2"
            contract_file.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=False), encoding="utf-8")
            sync_app_catalog_for_contract(root, contract_file=contract_file, app="sample-register-v2", service_key="sample-register-v2")

            result = run_app_delivery_cli("validate-contract", repo_root=root, app="sample-register-v2")

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
            write_contract(
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
            write_contract(
                root,
                dependencies=["edgeproxy-prod"],
                tenant_resources={},
            )

            result = run_app_delivery_cli("validate-contract", repo_root=root, app="sub2api")

            self.assertEqual(result.returncode, 0, msg=result.stderr)

# ======================================================================
# From: test_app_delivery_validate_resources_cli.py
# ======================================================================

class TestAppDeliveryValidateResourcesCliTests(unittest.TestCase):
    def test_validate_contract_tenant_requires_tenant_resources_for_infra_dependencies(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root)
            write_app_resource_registry(root, baseline_app_resource_registry_payload())
            write_contract(root)

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
            write_contract(root)

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
            bad_pg = resource_root(root, "prod0-main", "sampleapi") / "postgres.env"
            bad_pg.parent.mkdir(parents=True, exist_ok=True)
            bad_pg.write_text("PGDATABASE=sub2api_prod0\nPGUSER=sub2api_prod0\n", encoding="utf-8")
            bad_redis = resource_root(root, "prod0-main", "sampleapi") / "redis.env"
            bad_redis.parent.mkdir(parents=True, exist_ok=True)
            bad_redis.write_text("REDIS_USER=sub2api_prod0\nREDIS_DB=1\nREDIS_KEY_PREFIX=sub2api:\n", encoding="utf-8")
            write_contract(
                root,
                tenant_resources={
                    "postgres": {
                        "required": True,
                        "database": "sub2api_prod0",
                        "user": "sub2api_prod0",
                        "secret_file": resource_relative("prod0-main", "sampleapi", "postgres"),
                    },
                    "redis": {
                        "required": True,
                        "user": "sub2api_prod0",
                        "db": 1,
                        "key_prefix": "sub2api:",
                        "secret_file": resource_relative("prod0-main", "sampleapi", "redis"),
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
                resource_relative("prod0-main", "sampleapi", "postgres"),
                resource_relative("prod0-main", "sampleapi", "redis"),
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
            write_contract(
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
            escaped_pg = resource_root(root, "prod0-main", "sampleapi") / "postgres.env"
            escaped_pg.parent.mkdir(parents=True, exist_ok=True)
            escaped_pg.write_text("PGDATABASE=sub2api_prod0\nPGUSER=sub2api_prod0\n", encoding="utf-8")
            write_contract(
                root,
                tenant_resources={
                    "postgres": {
                        "required": True,
                        "database": "sub2api_prod0",
                        "user": "sub2api_prod0",
                        # Looks in-scope by prefix, but escapes the app directory after normalization.
                        "secret_file": resource_relative("prod0-main", "sub2api", "postgres").replace(
                            "/postgres.env", "/../sampleapi/postgres.env"
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
                    "/postgres.env", "/../sampleapi/postgres.env"
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
            write_contract(
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
            bad_minio = root / "secrets" / "app-resources" / "prod0-main" / "sampleapi" / "minio.env"
            bad_minio.parent.mkdir(parents=True, exist_ok=True)
            bad_minio.write_text("S3_BUCKET=prod0-sub2api\nS3_ACCESS_KEY=sub2api_prod0\nS3_SECRET_KEY=sub2api-s3-secret\n", encoding="utf-8")
            write_contract(
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
                        "secret_file": resource_relative("prod0-main", "sampleapi", "minio"),
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
            write_contract(
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
            write_contract(
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
            bad_pg = resource_root(root, "prod0-main", "sampleapi") / "postgres.env"
            bad_pg.parent.mkdir(parents=True, exist_ok=True)
            bad_pg.write_text("PGDATABASE=sub2api_prod0\nPGUSER=sub2api_prod0\n", encoding="utf-8")
            bad_redis = resource_root(root, "prod0-main", "sampleapi") / "redis.env"
            bad_redis.write_text("REDIS_DB=1\nREDIS_KEY_PREFIX=sub2api:\n", encoding="utf-8")
            write_contract(
                root,
                tenant_resources={
                    "postgres": {
                        "required": True,
                        "database": "sub2api_prod0",
                        "user": "sub2api_prod0",
                        "secret_file": resource_relative("prod0-main", "sampleapi", "postgres"),
                    },
                    "redis": {
                        "required": True,
                        "db": 1,
                        "key_prefix": "sub2api:",
                        "secret_file": resource_relative("prod0-main", "sampleapi", "redis"),
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

# ======================================================================
# From: test_app_delivery_doc_sync_cli.py
# ======================================================================

class TestAppDeliveryDocSyncCliTests(unittest.TestCase):
    def test_doc_sync_should_fail_on_registry_truth_drift_before_writing_server_readme(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root)
            write_tenant_secret_files(root)
            registry_payload = baseline_app_resource_registry_payload()
            registry_payload["sub2api"]["postgres"]["database"] = "sub2api_wrong"
            write_app_resource_registry(root, registry_payload)
            write_contract(root, tenant_resources=baseline_tenant_resources())

            server_readme = root / "inventory" / "servers" / "prod0-main" / "README.md"
            app_summary = root / "docs" / "AGENTPLANE_DEPLOYMENT.md"

            result = run_app_delivery_cli("doc-sync", repo_root=root, app="sub2api", extra_args=("--write",))

            self.assertNotEqual(result.returncode, 0)
            self.assertIn(ERROR_ID_TENANT_REGISTRY_MISMATCH, result.stdout + result.stderr)
            self.assertFalse(server_readme.exists())
            self.assertFalse(app_summary.exists())

    def test_doc_sync_prefers_explicit_app_repo_root_over_catalog_repo_root(self) -> None:
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
                docs_config={"app_summary_file": "docs/CANONICAL.md"},
            )
            write_target_contract(
                worktree_root,
                tenant_resources=baseline_tenant_resources(),
                docs_config={"app_summary_file": "docs/WORKTREE.md"},
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
                "doc-sync",
                repo_root=repo_root,
                app="sub2api",
                extra_args=("--write", "--app-repo-root", str(worktree_root)),
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(result.stdout)
            worktree_summary = worktree_root / "docs" / "WORKTREE.md"
            canonical_summary = canonical_root / "docs" / "CANONICAL.md"
            self.assertTrue(worktree_summary.exists())
            self.assertFalse(canonical_summary.exists())
            self.assertIn(str(worktree_summary), payload["app_docs"])

    def test_doc_sync_writes_server_summary_and_app_handoff(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            app_root = root / "sub2api"
            app_root.mkdir(parents=True, exist_ok=True)
            write_inventory(root)
            write_tenant_secret_files(root, include_minio=True)
            write_contract(app_root, tenant_resources=baseline_tenant_resources(include_minio=True))
            inventory_file = root / "inventory" / "servers" / "prod0-main" / "inventory.json"
            server_readme = root / "inventory" / "servers" / "prod0-main" / "README.md"
            server_readme.write_text(
                "\n".join(
                    [
                        "# prod0-main 摘要",
                        "",
                        "<!-- BEGIN AGENTPLANE_ONEPANEL_LEDGER -->",
                        "## 1Panel 对象台帐投影",
                        "",
                        "- 刷新命令：`uv run python -m agentplane.cli projection ledger refresh --target prod0-main --repo-root <repo-root> --write`",
                        "<!-- END AGENTPLANE_ONEPANEL_LEDGER -->",
                        "",
                    ]
                ),
                encoding="utf-8",
            )
            payload = json.loads(inventory_file.read_text(encoding="utf-8"))
            payload["services"]["sub2api"] = {
                "control_plane": "compose",
                "container_name": "sub2api-prod",
                "depends_on_containers": ["postgres18-prod", "redis7-prod"],
                "host_binding": "127.0.0.1:18080",
                "public_url": "https://token.zzzai.cloud:8443",
                "rollback_entry": {"kind": "systemd", "service_name": "sub2api"},
                "app_resource_summary": {
                    "postgres": {
                        "database": "sub2api_prod0",
                        "user": "sub2api_prod0",
                        "secret_file": resource_relative("prod0-main", "sub2api", "postgres"),
                    },
                    "redis": {
                        "user": "sub2api_legacy_runtime",
                        "db": 1,
                        "key_prefix": "sub2api:",
                        "secret_file": resource_relative("prod0-main", "sub2api", "redis"),
                    },
                    "minio": {
                        "bucket": "prod0-sub2api",
                        "access_key": "sub2api_prod0",
                        "policy_name": "prod0-sub2api-rw",
                        "policy_scope": "bucket-only",
                        "isolation_level": "bucket-scoped-rw",
                        "secret_file": resource_relative("prod0-main", "sub2api", "minio"),
                    },
                },
            }
            inventory_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

            result = run_app_delivery_cli(
                "doc-sync",
                repo_root=root,
                app="sub2api",
                extra_args=("--write",),
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            app_summary = app_root / "docs" / "AGENTPLANE_DEPLOYMENT.md"
            self.assertTrue(server_readme.exists())
            self.assertTrue(app_summary.exists())
            server_readme_text = server_readme.read_text(encoding="utf-8")
            app_summary_text = app_summary.read_text(encoding="utf-8")
            self.assertIn("sub2api-prod", server_readme_text)
            self.assertIn("postgres18-prod", app_summary_text)
            self.assertIn("app_resource_summary", server_readme_text)
            assert_live_db_partition_markers(self, server_readme_text)
            assert_live_db_partition_markers(self, app_summary_text)
            self.assertIn("PostgreSQL/MinIO", server_readme_text)
            self.assertIn("shared runtime credential", server_readme_text)
            self.assertIn("PostgreSQL/MinIO", app_summary_text)
            self.assertIn("shared runtime credential", app_summary_text)
            self.assertIn("bucket-scoped", server_readme_text)
            self.assertIn('"policy_name": "prod0-sub2api-rw"', server_readme_text)
            self.assertIn('"policy_scope": "bucket-only"', server_readme_text)
            self.assertIn('"isolation_level": "bucket-scoped-rw"', server_readme_text)
            self.assertIn('"policy_name": "prod0-sub2api-rw"', app_summary_text)
            self.assertIn('"policy_scope": "bucket-only"', app_summary_text)
            self.assertIn('"isolation_level": "bucket-scoped-rw"', app_summary_text)
            self.assertIn("合同文件：`contract.yaml`", app_summary_text)
            self.assertIn("<!-- BEGIN AGENTPLANE_ONEPANEL_LEDGER -->", server_readme_text)
            self.assertIn("--repo-root <repo-root> --write", server_readme_text)
            server_redis_line = next(line for line in server_readme_text.splitlines() if line.startswith("- app_resource_summary.redis"))
            redis_line = next(line for line in app_summary_text.splitlines() if line.startswith("- `redis`："))
            self.assertIn('"db": 1', server_redis_line)
            self.assertIn('"key_prefix": "sub2api:"', server_redis_line)
            self.assertNotIn('"user":', server_redis_line)
            self.assertIn('"db": 1', redis_line)
            self.assertIn('"key_prefix": "sub2api:"', redis_line)
            self.assertNotIn('"user":', redis_line)
            self.assertIn(resource_relative("prod0-main", "sub2api", "minio"), app_summary_text)

    def test_doc_sync_wsl_does_not_emit_prod0_live_db_partition_language(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            app_root = root / "sampleapi"
            app_root.mkdir(parents=True, exist_ok=True)
            write_inventory(root)
            write_sampleapi_contract(app_root, target="wsl")
            write_sampleapi_tenant_files(root, target="wsl")
            inventory_file = root / "inventory" / "servers" / "wsl" / "inventory.json"
            payload = json.loads(inventory_file.read_text(encoding="utf-8"))
            payload["services"]["sampleapi"] = {
                "control_plane": "compose",
                "container_name": "sampleapi-dev",
                "depends_on_containers": ["postgres18-dev", "redis7-dev"],
                "host_binding": "0.0.0.0:3000",
                "public_url": "http://127.0.0.1:3000",
                "rollback_entry": {"kind": "none", "note": "dev only"},
                "app_resource_summary": {
                    "postgres": {
                        "database": "sampleapi_wsl",
                        "user": "sampleapi_wsl",
                        "secret_file": resource_relative("wsl", "sampleapi", "postgres"),
                    },
                    "redis": {
                        "user": "sampleapi_wsl_legacy",
                        "db": 2,
                        "key_prefix": "sampleapi:wsl:",
                        "secret_file": resource_relative("wsl", "sampleapi", "redis"),
                    },
                },
            }
            inventory_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

            result = run_app_delivery_cli(
                "doc-sync",
                repo_root=root,
                app="sampleapi",
                target="wsl",
                extra_args=("--write",),
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            server_readme_text = (root / "inventory" / "servers" / "wsl" / "README.md").read_text(encoding="utf-8")
            app_summary_text = (app_root / "docs" / "AGENTPLANE_DEPLOYMENT.wsl.md").read_text(encoding="utf-8")
            self.assertNotIn("shared runtime credential", server_readme_text)
            self.assertNotIn("DB 级逻辑分区", server_readme_text)
            self.assertNotIn("强隔离", server_readme_text)
            self.assertNotIn("shared runtime credential", app_summary_text)
            self.assertNotIn("DB 级逻辑分区", app_summary_text)
            self.assertNotIn("强隔离", app_summary_text)
            self.assertNotIn('"user": "sampleapi_wsl_legacy"', server_readme_text)
            self.assertNotIn('"user": "sampleapi_wsl_legacy"', app_summary_text)

    def test_doc_sync_renders_1panel_compose_transition_entry(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            app_root = root / "sampleapi"
            app_root.mkdir(parents=True, exist_ok=True)
            write_inventory(root)
            write_sampleapi_tenant_files(root)
            write_sampleapi_contract(
                app_root,
                rollback_entry={
                    "kind": "1panel-compose",
                    "project_name": "samplepay-prod",
                    "container_name": "samplepay-prod",
                    "project_path": "/data/1panel/docker/compose/samplepay-prod",
                    "compose_file": "/data/1panel/docker/compose/samplepay-prod/docker-compose.yml",
                },
            )
            inventory_file = root / "inventory" / "servers" / "prod0-main" / "inventory.json"
            payload = json.loads(inventory_file.read_text(encoding="utf-8"))
            payload["services"]["sampleapi"] = {
                "control_plane": "compose",
                "container_name": "sampleapi-prod",
                "depends_on_containers": ["postgres18-prod", "redis7-prod"],
                "host_binding": "127.0.0.1:3000",
                "public_url": "https://sampleapi.zzzai.cloud:8443",
                "rollback_entry": {
                    "kind": "1panel-compose",
                    "project_name": "samplepay-prod",
                    "container_name": "samplepay-prod",
                    "project_path": "/data/1panel/docker/compose/samplepay-prod",
                    "compose_file": "/data/1panel/docker/compose/samplepay-prod/docker-compose.yml",
                },
            }
            inventory_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

            result = run_app_delivery_cli(
                "doc-sync",
                repo_root=root,
                app="sampleapi",
                extra_args=("--write",),
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            app_summary_text = (app_root / "docs" / "AGENTPLANE_DEPLOYMENT.md").read_text(encoding="utf-8")
            self.assertIn("1panel-compose", app_summary_text)
            self.assertIn("path=/data/1panel/docker/compose/samplepay-prod", app_summary_text)
            self.assertIn("compose=/data/1panel/docker/compose/samplepay-prod/docker-compose.yml", app_summary_text)

    def test_doc_sync_writes_target_specific_app_summary_files_when_configured(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            app_root = root / "sub2api"
            app_root.mkdir(parents=True, exist_ok=True)
            write_inventory(root)
            write_tenant_secret_files(root, include_minio=True)
            write_tenant_secret_files(root, target="wsl")
            contract_file = write_contract(
                app_root,
                tenant_resources=baseline_tenant_resources(include_minio=True),
                docs_config={
                    "app_summary_files": {
                        "prod0-main": "docs/AGENTPLANE_DEPLOYMENT.prod0-main.md",
                        "wsl": "docs/AGENTPLANE_DEPLOYMENT.wsl.md",
                    }
                },
            )
            wsl_contract_file = app_root / "contract.wsl.yaml"
            wsl_contract_payload = yaml.safe_load(contract_file.read_text(encoding="utf-8"))
            wsl_contract_payload["infra"]["tenant_resources"] = baseline_tenant_resources(target="wsl")
            wsl_contract_payload["runtime"]["container_name"] = "sub2api-dev"
            wsl_contract_payload["runtime"]["host_binding"] = "0.0.0.0:18080"
            wsl_contract_file.write_text(
                yaml.safe_dump(wsl_contract_payload, sort_keys=False, allow_unicode=False),
                encoding="utf-8",
            )
            write_app_catalog_entry(
                root,
                app="sub2api",
                repo_name=app_root.name,
                app_root=app_root,
                service_key="sub2api",
                contracts={
                    "prod0-main": contract_file.relative_to(app_root).as_posix(),
                    "wsl": wsl_contract_file.relative_to(app_root).as_posix(),
                },
            )

            prod_inventory_file = root / "inventory" / "servers" / "prod0-main" / "inventory.json"
            prod_payload = json.loads(prod_inventory_file.read_text(encoding="utf-8"))
            prod_payload["services"]["sub2api"] = {
                "control_plane": "compose",
                "container_name": "sub2api-prod",
                "depends_on_containers": ["postgres18-prod", "redis7-prod"],
                "host_binding": "127.0.0.1:18080",
                "public_url": "https://token.zzzai.cloud:8443",
                "rollback_entry": {"kind": "systemd", "service_name": "sub2api"},
                "app_resource_summary": {
                    "postgres": {
                        "database": "sub2api_prod0",
                        "user": "sub2api_prod0",
                        "secret_file": resource_relative("prod0-main", "sub2api", "postgres"),
                    },
                    "redis": {
                        "db": 1,
                        "key_prefix": "sub2api:",
                        "secret_file": resource_relative("prod0-main", "sub2api", "redis"),
                    },
                    "minio": {
                        "bucket": "prod0-sub2api",
                        "access_key": "sub2api_prod0",
                        "policy_name": "prod0-sub2api-rw",
                        "policy_scope": "bucket-only",
                        "isolation_level": "bucket-scoped-rw",
                        "secret_file": resource_relative("prod0-main", "sub2api", "minio"),
                    },
                },
            }
            prod_inventory_file.write_text(json.dumps(prod_payload, ensure_ascii=False, indent=2), encoding="utf-8")

            wsl_inventory_file = root / "inventory" / "servers" / "wsl" / "inventory.json"
            wsl_payload = json.loads(wsl_inventory_file.read_text(encoding="utf-8"))
            wsl_payload["services"]["sub2api"] = {
                "control_plane": "compose",
                "container_name": "sub2api-dev",
                "depends_on_containers": ["postgres18-dev", "redis7-dev"],
                "host_binding": "0.0.0.0:18080",
                "public_url": "http://127.0.0.1:18080",
                "rollback_entry": {"kind": "systemd", "service_name": "sub2api"},
                "app_resource_summary": {
                    "postgres": {
                        "database": "sub2api_wsl",
                        "user": "sub2api_wsl",
                        "secret_file": resource_relative("wsl", "sub2api", "postgres"),
                    },
                    "redis": {
                        "db": 1,
                        "key_prefix": "sub2api:wsl:",
                        "secret_file": resource_relative("wsl", "sub2api", "redis"),
                    },
                },
            }
            wsl_inventory_file.write_text(json.dumps(wsl_payload, ensure_ascii=False, indent=2), encoding="utf-8")

            prod_result = run_app_delivery_cli(
                "doc-sync",
                repo_root=root,
                app="sub2api",
                extra_args=("--write",),
            )
            self.assertEqual(prod_result.returncode, 0, msg=prod_result.stderr)

            wsl_result = run_app_delivery_cli(
                "doc-sync",
                repo_root=root,
                app="sub2api",
                target="wsl",
                extra_args=("--write",),
            )
            self.assertEqual(wsl_result.returncode, 0, msg=wsl_result.stderr)

            prod_summary = app_root / "docs" / "AGENTPLANE_DEPLOYMENT.prod0-main.md"
            wsl_summary = app_root / "docs" / "AGENTPLANE_DEPLOYMENT.wsl.md"
            self.assertTrue(prod_summary.exists())
            self.assertTrue(wsl_summary.exists())

            prod_text = prod_summary.read_text(encoding="utf-8")
            wsl_text = wsl_summary.read_text(encoding="utf-8")
            self.assertIn("目标环境：`prod0-main`", prod_text)
            self.assertIn("postgres18-prod", prod_text)
            self.assertIn("合同文件：`contract.yaml`", prod_text)
            self.assertIn("目标环境：`wsl`", wsl_text)
            self.assertIn("postgres18-dev", wsl_text)
            self.assertNotEqual(prod_text, wsl_text)

    def test_doc_sync_uses_actual_contract_path_in_app_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            app_root = root / "sub2api"
            contract_dir = app_root / "deploy" / "agentplane"
            contract_dir.mkdir(parents=True, exist_ok=True)
            write_inventory(root)
            write_tenant_secret_files(root, include_minio=True)
            contract_file = write_contract(
                app_root,
                tenant_resources=baseline_tenant_resources(include_minio=True),
                docs_config={"app_summary_file": "docs/AGENTPLANE_DEPLOYMENT.prod2-main.md"},
            )
            renamed_contract = contract_dir / "contract.prod2.yaml"
            contract_file.rename(renamed_contract)
            sync_app_catalog_for_contract(
                root,
                contract_file=renamed_contract,
                app="sub2api",
                service_key="sub2api",
                app_root=app_root,
            )

            inventory_file = root / "inventory" / "servers" / "prod0-main" / "inventory.json"
            payload = json.loads(inventory_file.read_text(encoding="utf-8"))
            payload["services"]["sub2api"] = {
                "control_plane": "compose",
                "container_name": "sub2api-prod",
                "depends_on_containers": ["postgres18-prod", "redis7-prod"],
                "host_binding": "127.0.0.1:18080",
                "public_url": "https://token.zzzai.fun",
                "rollback_entry": {"kind": "none", "note": "prod2-main 首次上线无旧控制面"},
                "app_resource_summary": {
                    "postgres": {
                        "database": "sub2api_prod2",
                        "user": "sub2api_prod2",
                        "secret_file": resource_relative("prod2-main", "sub2api", "postgres"),
                    },
                    "redis": {
                        "db": 1,
                        "key_prefix": "sub2api:",
                        "secret_file": resource_relative("prod2-main", "sub2api", "redis"),
                    },
                    "minio": {
                        "bucket": "prod2-sub2api",
                        "access_key": "sub2api_prod2",
                        "policy_name": "prod2-sub2api-rw",
                        "policy_scope": "bucket-only",
                        "isolation_level": "bucket-scoped-rw",
                        "secret_file": resource_relative("prod2-main", "sub2api", "minio"),
                    },
                },
            }
            inventory_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

            result = run_app_delivery_cli(
                "doc-sync",
                repo_root=root,
                app="sub2api",
                extra_args=("--write",),
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            app_summary = app_root / "docs" / "AGENTPLANE_DEPLOYMENT.prod2-main.md"
            self.assertIn("deploy/agentplane/contract.prod2.yaml", app_summary.read_text(encoding="utf-8"))

    def test_doc_sync_marks_missing_app_resource_summary_instead_of_falling_back_to_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            app_root = root / "sub2api"
            app_root.mkdir(parents=True, exist_ok=True)
            write_inventory(root)
            write_tenant_secret_files(root, include_minio=True)
            write_contract(app_root, tenant_resources=baseline_tenant_resources(include_minio=True))
            inventory_file = root / "inventory" / "servers" / "prod0-main" / "inventory.json"
            payload = json.loads(inventory_file.read_text(encoding="utf-8"))
            payload["services"]["sub2api"] = {
                "control_plane": "compose",
                "container_name": "sub2api-prod",
                "depends_on_containers": ["postgres18-prod", "redis7-prod"],
                "host_binding": "127.0.0.1:18080",
                "public_url": "https://token.zzzai.cloud:8443",
                "rollback_entry": {"kind": "systemd", "service_name": "sub2api"},
            }
            inventory_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

            result = run_app_delivery_cli(
                "doc-sync",
                repo_root=root,
                app="sub2api",
                extra_args=("--write",),
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            app_summary = app_root / "docs" / "AGENTPLANE_DEPLOYMENT.md"
            content = app_summary.read_text(encoding="utf-8")
            self.assertIn("未登记 app_resource_summary", content)
            self.assertNotIn(resource_relative("prod0-main", "sub2api", "postgres"), content)

    def test_deploy_execute_runs_post_actions_in_projection_inventory_doc_sync_order(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root, include_managed_bridge_networks=True)
            write_tenant_secret_files(root)
            write_app_resource_registry(root, baseline_app_resource_registry_payload())
            write_compose_template(root)
            write_contract(root, tenant_resources=baseline_tenant_resources())
            tenant_root = app_resource_secret_dir(root, "prod0-main", "sub2api")
            (tenant_root / "postgres.env").write_text(
                "PGHOST=postgres18-prod\nPGPORT=5432\nPGDATABASE=sub2api_prod0\nPGUSER=sub2api_prod0\nPGPASSWORD=secret\n",
                encoding="utf-8",
            )
            (tenant_root / "redis.env").write_text(
                "REDIS_HOST=redis7-prod\nREDIS_PORT=6379\nREDIS_DB=1\nREDIS_KEY_PREFIX=sub2api:\nREDIS_PASSWORD=redis-secret\nREDIS_ENABLE_TLS=false\n",
                encoding="utf-8",
            )
            (tenant_root / "minio.env").write_text(
                "S3_BUCKET=prod0-sub2api\nS3_ACCESS_KEY=sub2api_prod0\nS3_SECRET_KEY=sub2api-s3-secret\n",
                encoding="utf-8",
            )
            (root / "secrets" / "services").mkdir(parents=True, exist_ok=True)
            (root / "secrets" / "services" / "sub2api.prod0.env").write_text("SERVER_PORT=8080\n", encoding="utf-8")
            (root / "secrets" / "ssh").mkdir(parents=True, exist_ok=True)
            (root / "secrets" / "ssh" / "config").write_text("Host prod0-main\n", encoding="utf-8")
            bin_dir = root / "bin"
            bin_dir.mkdir(parents=True, exist_ok=True)
            log_file = root / "post-actions-command.log"
            state_dir = root / "fake-network-state"
            state_dir.mkdir(parents=True, exist_ok=True)
            write_fake_command(
                bin_dir,
                "scp",
                "#!/usr/bin/env bash\nset -euo pipefail\nprintf 'scp %s\\n' \"$*\" >> \"$FAKE_CMD_LOG\"\n",
            )
            write_fake_bridge_network_ssh(bin_dir)

            result = run_app_delivery_cli(
                "deploy",
                repo_root=root,
                app="sub2api",
                extra_args=("--image-ref", "sub2api-prod:test", "--execute"),
                env_overrides={
                    "PATH": f"{bin_dir}:{os.environ['PATH']}",
                    "FAKE_CMD_LOG": str(log_file),
                    "FAKE_NETWORK_STATE_DIR": str(state_dir),
                },
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(result.stdout)["payload"]
            post_actions = payload["post_actions"]
            self.assertTrue(post_actions["ok"])
            self.assertEqual(
                [
                    "projection.runtime-env.apply",
                    "app.delivery.inventory-refresh",
                    "app.delivery.doc-sync",
                ],
                [item["action"] for item in post_actions["steps"]],
            )
            evidence = post_actions["evidence"]
            ledger_file = Path(evidence["ledger_file"])
            self.assertTrue(ledger_file.is_file())
            entries = [json.loads(line) for line in ledger_file.read_text(encoding="utf-8").splitlines() if line.strip()]
            post_action_entries = [
                entry
                for entry in entries
                if entry.get("command") == "app"
                and entry.get("action") == "deploy"
                and entry.get("result") == "post-actions-synced"
            ]
            self.assertEqual(1, len(post_action_entries))
            self.assertEqual(evidence["operation"]["op_id"], post_action_entries[0]["op_id"])

# ======================================================================
# From: test_app_delivery_inventory_cli.py
# ======================================================================

class TestAppDeliveryInventoryCliTests(unittest.TestCase):
    def test_inventory_refresh_writes_app_entry(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root)
            write_tenant_secret_files(root, include_minio=True)
            write_contract(root, tenant_resources=baseline_tenant_resources(include_minio=True))
            inventory_file = root / "inventory" / "servers" / "prod0-main" / "inventory.json"

            result = run_app_delivery_cli(
                "inventory-refresh",
                repo_root=root,
                app="sub2api",
                extra_args=("--write",),
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(result.stdout)
            app_entry = payload["payload"]["services"]["sub2api"]
            self.assertEqual("compose", app_entry["control_plane"])
            self.assertEqual("sub2api-prod", app_entry["container_name"])
            self.assertEqual(["postgres18-prod", "redis7-prod"], app_entry["depends_on_containers"])
            self.assertEqual("https://token.zzzai.cloud:8443", app_entry["public_url"])
            self.assertEqual(["/data/sub2api/config/sub2api-prod.env"], app_entry["config_files"])
            self.assertEqual("sub2api_prod0", app_entry["app_resource_summary"]["postgres"]["database"])
            self.assertEqual("sub2api:", app_entry["app_resource_summary"]["redis"]["key_prefix"])
            self.assertNotIn("user", app_entry["app_resource_summary"]["redis"])
            self.assertEqual("prod0-sub2api", app_entry["app_resource_summary"]["minio"]["bucket"])
            self.assertEqual(
                resource_relative("prod0-main", "sub2api", "minio"),
                app_entry["app_resource_summary"]["minio"]["secret_file"],
            )
            written_payload = json.loads(inventory_file.read_text(encoding="utf-8"))
            self.assertEqual(
                ["/data/sub2api/config/sub2api-prod.env"],
                written_payload["services"]["sub2api"]["config_files"],
            )
            self.assertNotIn("user", written_payload["services"]["sub2api"]["app_resource_summary"]["redis"])

    def test_inventory_refresh_writes_wsl_target_specific_sampleapi_entry(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root)
            write_sampleapi_tenant_files(root, target="wsl")
            write_app_resource_registry(
                root,
                {
                    "sampleapi": {
                        "owner_app": "sampleapi",
                        "postgres": {"database": "sampleapi_wsl", "user": "sampleapi_wsl"},
                        "redis": {"user": "", "db": 2, "key_prefix": "sampleapi:wsl:"},
                        "secret_files": [
                            resource_relative("wsl", "sampleapi", "postgres"),
                            resource_relative("wsl", "sampleapi", "redis"),
                        ],
                    }
                },
                target="wsl",
            )
            write_sampleapi_contract(root, target="wsl")
            write_sampleapi_compose_templates(root)

            result = run_app_delivery_cli(
                "inventory-refresh",
                repo_root=root,
                app="sampleapi",
                target="wsl",
                extra_args=("--write",),
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(result.stdout)
            app_entry = payload["payload"]["services"]["sampleapi"]
            self.assertEqual("sampleapi-dev", app_entry["container_name"])
            self.assertEqual(["postgres18-dev", "redis7-dev"], app_entry["depends_on_containers"])
            self.assertEqual([str(root / "secrets" / "services" / "sampleapi.wsl.env")], app_entry["config_files"])
            self.assertEqual("0.0.0.0:3000", app_entry["host_binding"])
            self.assertEqual("http://127.0.0.1:3000", app_entry["public_url"])
            self.assertEqual(["zqf_network"], app_entry["docker_networks"])
            self.assertEqual("sampleapi_wsl", app_entry["app_resource_summary"]["postgres"]["database"])
            self.assertEqual("sampleapi:wsl:", app_entry["app_resource_summary"]["redis"]["key_prefix"])
            self.assertNotIn("user", app_entry["app_resource_summary"]["redis"])
            written_payload = json.loads((root / "inventory" / "servers" / "wsl" / "inventory.json").read_text(encoding="utf-8"))
            self.assertEqual(["zqf_network"], written_payload["services"]["sampleapi"]["docker_networks"])
            self.assertNotIn("user", written_payload["services"]["sampleapi"]["app_resource_summary"]["redis"])

    def test_inventory_refresh_wsl_uses_canonical_secrets_path_outside_worktree_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            outer_root = Path(tmp) / "repo-root"
            worktree_root = outer_root / ".worktrees" / "codex" / "release"
            worktree_root.mkdir(parents=True, exist_ok=True)
            git_worktree_dir = outer_root / ".git" / "worktrees" / "release"
            git_worktree_dir.mkdir(parents=True, exist_ok=True)
            (worktree_root / ".git").write_text(f"gitdir: {git_worktree_dir}\n", encoding="utf-8")
            canonical_secrets = outer_root / "secrets" / "services"
            canonical_secrets.mkdir(parents=True, exist_ok=True)
            (worktree_root / "secrets").symlink_to(outer_root / "secrets")
            write_inventory(worktree_root)
            write_sampleapi_tenant_files(outer_root, target="wsl")
            write_app_resource_registry(
                worktree_root,
                {
                    "sampleapi": {
                        "owner_app": "sampleapi",
                        "postgres": {"database": "sampleapi_wsl", "user": "sampleapi_wsl"},
                        "redis": {"user": "", "db": 2, "key_prefix": "sampleapi:wsl:"},
                        "secret_files": [
                            resource_relative("wsl", "sampleapi", "postgres"),
                            resource_relative("wsl", "sampleapi", "redis"),
                        ],
                    }
                },
                target="wsl",
            )
            write_sampleapi_contract(worktree_root, target="wsl")
            write_sampleapi_compose_templates(worktree_root)

            result = run_app_delivery_cli(
                "inventory-refresh",
                repo_root=worktree_root,
                app="sampleapi",
                target="wsl",
                extra_args=("--write",),
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(result.stdout)
            expected = str(outer_root / "secrets" / "services" / "sampleapi.wsl.env")
            self.assertEqual([expected], payload["payload"]["services"]["sampleapi"]["config_files"])
            written_payload = json.loads((worktree_root / "inventory" / "servers" / "wsl" / "inventory.json").read_text(encoding="utf-8"))
            self.assertEqual([expected], written_payload["services"]["sampleapi"]["config_files"])

    def test_inventory_refresh_keeps_1panel_compose_project_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root)
            write_sampleapi_tenant_files(root)
            write_sampleapi_compose_templates(root)
            write_sampleapi_contract(
                root,
                rollback_entry={
                    "kind": "1panel-compose",
                    "project_name": "samplepay-prod",
                    "container_name": "samplepay-prod",
                    "project_path": "/data/1panel/docker/compose/samplepay-prod",
                    "compose_file": "/data/1panel/docker/compose/samplepay-prod/docker-compose.yml",
                },
            )

            result = run_app_delivery_cli(
                "inventory-refresh",
                repo_root=root,
                app="sampleapi",
                extra_args=("--write",),
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            rollback_entry = json.loads(result.stdout)["payload"]["services"]["sampleapi"]["rollback_entry"]
            self.assertEqual("1panel-compose", rollback_entry["kind"])
            self.assertEqual("/data/1panel/docker/compose/samplepay-prod", rollback_entry["project_path"])
            self.assertEqual(
                "/data/1panel/docker/compose/samplepay-prod/docker-compose.yml",
                rollback_entry["compose_file"],
            )

    def test_inventory_refresh_writes_prod2_target_specific_sampleapi_entry(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_prod2_inventory(root)
            write_app_resource_registry(
                root,
                {
                    "sampleapi": {
                        "owner_app": "sampleapi",
                        "postgres": {"database": "sampleapi_prod2", "user": "sampleapi_prod2"},
                        "redis": {"db": 2, "key_prefix": "sampleapi:"},
                        "minio": {
                            "bucket": "prod2-sampleapi",
                            "access_key": "sampleapi_prod2",
                            "policy_name": "prod2-sampleapi-rw",
                            "policy_scope": "bucket-only",
                            "isolation_level": "bucket-scoped-rw",
                        },
                        "secret_files": [
                            resource_relative("prod2-main", "sampleapi", "postgres"),
                            resource_relative("prod2-main", "sampleapi", "redis"),
                            resource_relative("prod2-main", "sampleapi", "minio"),
                        ],
                    }
                },
                target="prod2-main",
            )
            write_sampleapi_tenant_files(root, target="prod2-main", include_minio=True)
            write_sampleapi_contract(root, target="prod2-main", include_minio=True)
            write_sampleapi_compose_templates(root, include_prod2=True)
            inventory_file = root / "inventory" / "servers" / "prod2-main" / "inventory.json"

            result = run_app_delivery_cli(
                "inventory-refresh",
                repo_root=root,
                app="sampleapi",
                target="prod2-main",
                extra_args=("--write",),
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(result.stdout)
            app_entry = payload["payload"]["services"]["sampleapi"]
            self.assertEqual("sampleapi-prod", app_entry["container_name"])
            self.assertEqual("https://sampleapi.zzzai.fun", app_entry["public_url"])
            self.assertEqual(["postgres18-prod", "redis7-prod", "minio-prod"], app_entry["depends_on_containers"])
            self.assertEqual(["/opt/agentplane/secrets/services/sampleapi.prod2.env"], app_entry["config_files"])
            self.assertEqual("sampleapi_prod2", app_entry["app_resource_summary"]["postgres"]["database"])
            self.assertEqual("prod2-sampleapi", app_entry["app_resource_summary"]["minio"]["bucket"])
            self.assertEqual(
                resource_relative("prod2-main", "sampleapi", "minio"),
                app_entry["app_resource_summary"]["minio"]["secret_file"],
            )
            written_payload = json.loads(inventory_file.read_text(encoding="utf-8"))
            self.assertEqual("https://sampleapi.zzzai.fun", written_payload["services"]["sampleapi"]["public_url"])
            self.assertEqual(
                ["/opt/agentplane/secrets/services/sampleapi.prod2.env"],
                written_payload["services"]["sampleapi"]["config_files"],
            )

    def test_inventory_refresh_internal_worker_uses_internal_probe_url(self) -> None:
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
            payload["app_id"] = "sample-register-v2"
            payload["artifact"]["image_name"] = "sample-register-v2-prod"
            payload["runtime"]["container_name"] = "sample-register-v2-prod"
            payload["runtime"]["container_port"] = 18081
            payload["runtime"]["host_binding"] = "127.0.0.1:18081"
            payload["runtime"]["config_files"] = ["/opt/agentplane/secrets/services/sample-register-v2.prod0.env"]
            payload["runtime"]["healthcheck"] = {"path": "/healthz", "expected_status": 200}
            payload["data"]["mounts"] = [{"host_path": "/data/sample-register-v2/data", "container_path": "/data"}]
            payload["inventory"]["service_key"] = "sample-register-v2"
            payload["inventory"]["remove_service_keys"] = ["chatgpt-register-wsl"]
            contract_file.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=False), encoding="utf-8")
            sync_app_catalog_for_contract(root, contract_file=contract_file, app="sample-register-v2", service_key="sample-register-v2")
            write_internal_worker_compose_template(root)
            inventory_payload = json.loads(inventory_file.read_text(encoding="utf-8"))
            inventory_payload["services"]["chatgpt-register-wsl"] = {
                "control_plane": "compose",
                "container_name": "sample-register-v2-wsl",
                "public_url": "http://127.0.0.1:18081",
            }
            inventory_file.write_text(json.dumps(inventory_payload, ensure_ascii=False, indent=2), encoding="utf-8")

            result = run_app_delivery_cli(
                "inventory-refresh",
                repo_root=root,
                app="sample-register-v2",
                extra_args=("--write",),
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            app_entry = json.loads(result.stdout)["payload"]["services"]["sample-register-v2"]
            self.assertEqual("internal://127.0.0.1:18081", app_entry["public_url"])
            self.assertEqual(["sub2api-prod"], app_entry["depends_on_containers"])
            self.assertEqual(["/opt/agentplane/secrets/services/sample-register-v2.prod0.env"], app_entry["config_files"])
            refreshed_services = json.loads(result.stdout)["payload"]["services"]
            self.assertNotIn("chatgpt-register-wsl", refreshed_services)

    def test_repo_internal_worker_assets_no_legacy_wsl_compose_path(self) -> None:
        self.assertFalse((REPO_ROOT / "infra" / "compose" / "chatgpt-register-wsl").exists())
        self.assertFalse((REPO_ROOT / "templates" / "services" / "chatgpt-register-wsl.env.example").exists())
        wsl_inventory = json.loads((REPO_ROOT / "inventory" / "servers" / "wsl" / "inventory.json").read_text(encoding="utf-8"))
        compose_services = wsl_inventory.get("compose_services") or []
        self.assertIn("sub2api", compose_services)
        self.assertNotIn("sample-register-v2", compose_services)
        self.assertNotIn("chatgpt-register-wsl", compose_services)

    def test_repo_prod0_internal_worker_inventory_and_readme_are_offboarded(self) -> None:
        prod0_inventory = json.loads((REPO_ROOT / "inventory" / "servers" / "prod0-main" / "inventory.json").read_text(encoding="utf-8"))
        self.assertNotIn("sample-register-v2", prod0_inventory["services"])
        readme_text = (REPO_ROOT / "inventory" / "servers" / "prod0-main" / "README.md").read_text(encoding="utf-8")
        self.assertNotIn("sample-register-v2", readme_text)

    def test_inventory_refresh_writes_prod2_target_specific_sub2api_entry(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_prod2_inventory(root)
            write_prod2_tenant_secret_files(root, include_minio=True)
            write_prod2_tenant_registry(root, include_minio=True)
            write_prod2_contract(root, include_minio=True)
            inventory_file = root / "inventory" / "servers" / "prod2-main" / "inventory.json"

            result = run_app_delivery_cli(
                "inventory-refresh",
                repo_root=root,
                app="sub2api",
                target="prod2-main",
                extra_args=("--write",),
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(result.stdout)
            app_entry = payload["payload"]["services"]["sub2api"]
            self.assertEqual("sub2api-prod", app_entry["container_name"])
            self.assertEqual("https://token.zzzai.fun", app_entry["public_url"])
            self.assertEqual(["postgres18-prod", "redis7-prod"], app_entry["depends_on_containers"])
            self.assertEqual("sub2api_prod2", app_entry["app_resource_summary"]["postgres"]["database"])
            self.assertEqual("prod2-sub2api", app_entry["app_resource_summary"]["minio"]["bucket"])
            self.assertEqual(
                resource_relative("prod2-main", "sub2api", "minio"),
                app_entry["app_resource_summary"]["minio"]["secret_file"],
            )
            written_payload = json.loads(inventory_file.read_text(encoding="utf-8"))
            self.assertEqual("https://token.zzzai.fun", written_payload["services"]["sub2api"]["public_url"])
