from __future__ import annotations

import json
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

import pytest
from tests.support.app_delivery_cli import run_app_delivery_cli, run_cli
from tests.support.app_delivery_contracts import (
    init_git_repo,
    write_app_catalog_entry,
    write_contract,
    write_target_contract,
)
from tests.support.app_delivery_targets import (
    baseline_app_resource_registry_payload,
    baseline_tenant_resources,
    write_app_resource_registry,
    write_inventory,
    write_tenant_secret_files,
)

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
                        f'printf \'{{"image_tag":"%s","output_path":"%s"}}\' "$IMAGE_TAG" "$ARTIFACT_OUTPUT_PATH" > "{output_file}"',
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
                        f'printf "%s" "$IMAGE_TAG" > "{output_file}"',
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
                        f'printf \'{{"image_tag":"%s","fork_version":"%s","delivery_version":"%s"}}\' "$IMAGE_TAG" "${{FORK_VERSION:-}}" "${{DELIVERY_VERSION:-}}" > "{output_file}"',
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
                        f'printf \'{{"image_ref":"%s","artifact_output_path":"%s"}}\' "$IMAGE_REF" "$ARTIFACT_OUTPUT_PATH" > "{package_output}"',
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
                        f'printf "%s" "$IMAGE_TAG" > "{output_file}"',
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


