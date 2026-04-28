from __future__ import annotations

import re
import subprocess
import unittest
from pathlib import Path

import pytest
import yaml
from agentplane.domain.app.resource_paths import git_common_root

pytestmark = pytest.mark.e2e

REPO_ROOT = Path(__file__).resolve().parents[2]
EXPECTED_MANAGED_SERVICES = {
    "sub2api": {
        "wsl": "infra/compose/sub2api/docker-compose.wsl.yml",
    },
}

def load_compose(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))

def image_family(image_ref: str) -> str:
    match = re.fullmatch(r"\$\{[^:}]+:-([^}]+)\}", image_ref)
    resolved = match.group(1) if match else image_ref
    resolved = resolved.split("@", 1)[0]
    return resolved.split(":", 1)[0]


def tracked_files() -> set[str]:
    result = subprocess.run(["git", "ls-files"], cwd=REPO_ROOT, text=True, capture_output=True, check=True)
    return set(result.stdout.splitlines())

class RepoSnapshotContractsTests(unittest.TestCase):
    def test_sub2api_legacy_app_resource_secret_files_are_absent(self) -> None:
        secret_root = (git_common_root(REPO_ROOT) or REPO_ROOT) / "secrets"
        legacy_paths = [
            "secrets/app-resources/wsl/sub2api/postgres.env",
            "secrets/app-resources/wsl/sub2api/redis.env",
            "secrets/app-resources/prod0-main/sub2api/postgres.env",
            "secrets/app-resources/prod0-main/sub2api/redis.env",
            "secrets/app-resources/prod0-main/sub2api/minio.env",
            "secrets/app-resources/prod2-main/sub2api/postgres.env",
            "secrets/app-resources/prod2-main/sub2api/redis.env",
            "secrets/app-resources/prod2-main/sub2api/minio.env",
        ]

        for relative_path in legacy_paths:
            with self.subTest(path=relative_path):
                candidate = secret_root / Path(relative_path).relative_to("secrets")
                self.assertFalse(candidate.exists(), f"legacy sub2api secret file still present: {candidate}")

    def test_expected_compose_snapshots_and_examples_still_exist(self) -> None:
        expected_compose_dirs = [
            "infra/compose/sub2api",
        ]
        tracked_examples_by_service = {
            "sub2api": [
                "templates/services/sub2api.wsl.env.example",
            ],
        }

        for relative_path in expected_compose_dirs:
            with self.subTest(path=relative_path):
                self.assertTrue((REPO_ROOT / relative_path).is_dir(), f"missing compose snapshot: {relative_path}")

        for service, paths in tracked_examples_by_service.items():
            for relative_path in paths:
                with self.subTest(service=service, path=relative_path):
                    self.assertTrue((REPO_ROOT / relative_path).is_file(), f"missing tracked example: {relative_path}")

        retired_helpers = [
            "agentplane/scripts/onepanel/app_lifecycle.py",
            "agentplane/scripts/onepanel/project_lifecycle.py",
        ]
        for relative_path in retired_helpers:
            with self.subTest(path=relative_path):
                self.assertFalse((REPO_ROOT / relative_path).exists(), f"retired helper still present: {relative_path}")

    def test_legacy_snapshots_still_absent(self) -> None:
        unexpected_paths = [
            "infra/compose/chatgpt-register-wsl",
            "infra/compose/chatgpt-register-v2",
            "infra/compose/chatgpt-register-v2-prod2",
            "infra/compose/newapi",
            "infra/compose/sub2apipay",
            "templates/services/chatgpt-register-wsl.env.example",
            "templates/services/chatgpt-register-v2.env.example",
            "templates/services/chatgpt-register-v2-prod2.prod2.env.example",
            "templates/services/newapi.wsl.env.example",
            "templates/services/newapi.prod0.env.example",
            "templates/services/newapi.prod2.env.example",
            "templates/services/sub2apipay.wsl.env.example",
            "templates/services/sub2apipay.prod0.env.example",
            "agentplane/scripts/remote/deploy_nginx_ui_to_host.sh",
            "agentplane/scripts/remote/remote_deploy_nginx_ui.sh",
            "agentplane/scripts/remote/remote_deploy_nginxwebui.sh",
            "agentplane/scripts/remote/remote_fix_nginxwebui_public_access.sh",
            "agentplane/scripts/remote/remote_restore_nginxwebui_proxy_workaround.sh",
            "agentplane/scripts/remote/remote_convert_nginxwebui_single_nginx.sh",
            "agentplane/scripts/remote/remote_rollback_prod0_8443_to_nginx_ui.sh",
        ]

        for relative_path in unexpected_paths:
            with self.subTest(path=relative_path):
                self.assertFalse((REPO_ROOT / relative_path).exists(), f"unexpected legacy snapshot present: {relative_path}")

    def test_remote_script_directory_contract(self) -> None:
        expected_paths = [
            "agentplane/scripts/internal/remote/example.sh",
            "agentplane/scripts/internal/remote/example-arg.sh",
            "agentplane/scripts/onepanel/signed_request.py",
        ]
        unexpected_paths = [
            "agentplane/scripts/remote/example.sh",
            "agentplane/scripts/remote/example-arg.sh",
            "agentplane/scripts/remote/run_remote_bash.sh",
            "agentplane/scripts/onepanel/api_request.py",
        ]

        for relative_path in expected_paths:
            with self.subTest(path=relative_path):
                self.assertTrue((REPO_ROOT / relative_path).is_file(), f"missing remote script contract: {relative_path}")

        for relative_path in unexpected_paths:
            with self.subTest(path=relative_path):
                self.assertFalse((REPO_ROOT / relative_path).exists(), f"unexpected remote script contract present: {relative_path}")

    def test_active_runbooks_use_internal_remote_example_paths(self) -> None:
        active_runbooks = [
            "docs/runbooks/powershell-wsl-remote-bash.md",
        ]

        for relative_path in active_runbooks:
            text = (REPO_ROOT / relative_path).read_text(encoding="utf-8")
            with self.subTest(path=relative_path):
                self.assertIn("agentplane/scripts/internal/remote/example.sh", text)
                self.assertNotIn("agentplane/scripts/remote/example.sh", text)

        powershell_runbook = (REPO_ROOT / "docs/runbooks/powershell-wsl-remote-bash.md").read_text(encoding="utf-8")
        self.assertIn("agentplane/scripts/internal/remote/example-arg.sh", powershell_runbook)
        self.assertNotIn("agentplane/scripts/remote/example-arg.sh", powershell_runbook)

    def test_naming_registry_declares_phase1_hard_contract(self) -> None:
        text = (REPO_ROOT / "docs/reference/control-plane-naming-registry.md").read_text(encoding="utf-8")

        self.assertIn("仅适用于正式 app contract 对象", text)
        self.assertIn("`^[a-z0-9]+(?:-[a-z0-9]+)*$`", text)
        self.assertIn("`inventory.service_key`", text)
        self.assertIn("必须与 `app_id` 完全相等", text)
        self.assertIn("`image_family`", text)
        self.assertIn("默认正式 app 交付镜像 family 固定为 `<app_id>-prod`", text)
        self.assertIn("必须等于 `<app_id>-prod`", text)
        self.assertIn("必须等于 `<app_id>-dev`", text)
        self.assertIn("| `sub2api` | `infra/compose/sub2api` | `wsl/prod0-main: ghcr.io/wei-shaw/sub2api`; `prod2-main: sub2api-prod` | `sub2api-prod` | `sub2api-dev` | `sub2api` |", text)
        self.assertNotIn("| `newapi` | `infra/compose/newapi` | `newapi-prod` | `newapi-prod` | `newapi-dev` | `newapi` |", text)
        self.assertNotIn(
            "| `sub2apipay` | `infra/compose/sub2apipay` | `sub2apipay-prod` | `sub2apipay-prod` | `sub2apipay-dev` | `sub2apipay` |",
            text,
        )
        self.assertNotIn("| 示例应用 |", text)
        self.assertNotIn("与生产容器同族", text)
        self.assertNotIn("与应用或运行服务主名一致", text)

    def test_catalog_has_no_local_app_repo_delivery_objects(self) -> None:
        catalog = (REPO_ROOT / "inventory/apps/catalog.json").read_text(encoding="utf-8")
        self.assertIn('"apps": []', catalog)

    def test_managed_service_compose_snapshots_match_naming_contract(self) -> None:
        for app_id, paths in EXPECTED_MANAGED_SERVICES.items():
            wsl_compose = load_compose(REPO_ROOT / paths["wsl"])
            wsl_service = wsl_compose["services"][app_id]
            with self.subTest(app_id=app_id, target="wsl-container"):
                self.assertEqual(f"{app_id}-dev", wsl_service["container_name"])
            with self.subTest(app_id=app_id, target="wsl-official-image"):
                self.assertEqual("ghcr.io/wei-shaw/sub2api", image_family(wsl_service["image"]))
                self.assertEqual("always", wsl_service["pull_policy"])

    def test_private_control_plane_files_are_not_tracked(self) -> None:
        tracked = tracked_files()
        private_paths = [
            "inventory/servers/prod0-main/inventory.json",
            "inventory/servers/prod2-main/inventory.json",
            "inventory/servers/wsl/inventory.json",
            "inventory/state-snapshot.md",
            "docs/runbooks/prod0-main-governance.md",
            "docs/runbooks/prod2-main-relay-trojan.md",
            "infra/compose/sub2api/docker-compose.prod0.yml",
            "infra/compose/sub2api/docker-compose.prod2.yml",
            "templates/services/sub2api.prod0.env.example",
            "templates/services/sub2api.prod2.env.example",
        ]
        for relative_path in private_paths:
            with self.subTest(path=relative_path):
                self.assertNotIn(relative_path, tracked)

    def test_removed_compatibility_entrypoints_stay_absent(self) -> None:
        removed_paths = [
            "docs/reference/compat-retirement-ledger.md",
            "scripts/check_commit_message.py",
            "scripts/batch_rename.py",
            "scripts/batch_rename_docs.py",
            "scripts/batch_rename_inventory.py",
            "scripts/batch_rename_tests.py",
            "scripts/fix_remaining_refs.py",
            "agentplane/scripts/remote/run_remote_bash.sh",
            "agentplane/scripts/onepanel/api_request.py",
        ]

        for relative_path in removed_paths:
            with self.subTest(path=relative_path):
                self.assertFalse((REPO_ROOT / relative_path).exists(), f"removed entrypoint still present: {relative_path}")
