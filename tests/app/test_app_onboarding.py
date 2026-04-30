from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import pytest
from agentplane.domain.app.resource_paths import app_resource_secret_dir, app_resource_secret_relative
from tests.support.paths import REPO_ROOT

pytestmark = pytest.mark.e2e

class AppOnboardingStandardTests(unittest.TestCase):
    def test_reference_docs_for_app_onboarding_governance_exist(self) -> None:
        expected_paths = [
            "docs/reference/repository-structure.md",
            "docs/reference/app-repository-standard.md",
            "docs/reference/control-plane-naming-registry.md",
        ]

        for relative_path in expected_paths:
            with self.subTest(path=relative_path):
                self.assertTrue((REPO_ROOT / relative_path).is_file(), f"missing reference doc: {relative_path}")

    def test_readme_and_architecture_index_link_new_reference_docs(self) -> None:
        # README delegates to docs/README.md for detailed doc links
        architecture_index_text = (REPO_ROOT / "docs" / "architecture" / "README.md").read_text(encoding="utf-8")

        self.assertIn("[repository-structure.md](../reference/repository-structure.md)", architecture_index_text)
        self.assertIn("[app-repository-standard.md](../reference/app-repository-standard.md)", architecture_index_text)
        self.assertIn("[control-plane-naming-registry.md](../reference/control-plane-naming-registry.md)", architecture_index_text)

    def test_readme_prefers_bootstrap_first_startup_path(self) -> None:
        text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")

        self.assertIn("bootstrap inspect-local", text)
        self.assertIn("bootstrap init-secrets", text)
        self.assertIn("bootstrap verify-secrets", text)
        self.assertNotIn("onepanel-login.<target>.env", text)

    def test_bootstrap_runbook_uses_bootstrap_surface_as_day_zero_entry(self) -> None:
        text = (REPO_ROOT / "docs" / "runbooks" / "bootstrap-secrets.md").read_text(encoding="utf-8")

        self.assertIn("bootstrap inspect-local", text)
        self.assertIn("bootstrap init-secrets", text)
        self.assertIn("bootstrap verify-secrets", text)
        self.assertIn("bootstrap doctor", text)
        self.assertIn("onepanel-login.<target>.env", text)
        self.assertIn("不参与 bootstrap contract", text)
        self.assertIn("projection", text)

    def test_historical_superpowers_workspace_docs_are_removed_from_active_tree(self) -> None:
        self.assertFalse((REPO_ROOT / "docs" / "superpowers").exists())

    def test_repo_self_check_script_exists_and_runs_documented_checks(self) -> None:
        script_path = REPO_ROOT / "agentplane" / "scripts" / "internal" / "repo" / "self_check.sh"
        self.assertTrue(script_path.is_file(), msg=f"missing {script_path}")
        text = script_path.read_text(encoding="utf-8")

        self.assertIn("uv run python -m pytest", text)
        self.assertIn("-m \"unit or integration\"", text)
        self.assertNotIn("UV_PROJECT_ENVIRONMENT", text)

    def test_repo_ignores_only_the_single_default_venv(self) -> None:
        text = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8")

        self.assertIn(".venv/", text)
        self.assertNotIn(".venv-*/", text)

    def test_agents_doc_uses_compact_contract_sections(self) -> None:
        text = (REPO_ROOT / "AGENTS.md").read_text(encoding="utf-8")
        required_headings = (
            "## 必读摘要",
            "## 项目概述",
            "## 跨平台约束",
            "## 安全约束",
            "## Git 约束",
            "## 编码行为准则",
            "## 文档索引",
        )
        for heading in required_headings:
            with self.subTest(heading=heading):
                self.assertIn(heading, text)

    def test_app_collaboration_doc_calls_out_upstream_and_rollback_state(self) -> None:
        text = (REPO_ROOT / "docs" / "architecture" / "agentplane-app-collaboration.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("`origin` 指向你自己的可写仓库", text)
        self.assertIn("`upstream` 指向官方只读源", text)
        self.assertIn("发布前先创建回滚态", text)
        self.assertIn("回滚态", text)

    def test_app_delivery_runbook_makes_validate_contract_the_pre_deploy_gate(self) -> None:
        text = (REPO_ROOT / "docs" / "runbooks" / "app-project-delivery-workflow.md").read_text(
            encoding="utf-8"
        )

        self.assertIn("这是应用接入不变量的最早正式门禁", text)
        self.assertIn(
            "未通过前不进入 `build-artifact`、`ship-image`、`render-runtime`、`deploy`、`rollback` 或 `verify`",
            text,
        )
        self.assertIn("合同问题必须在这一步暴露", text)
        self.assertIn("`deploy --dry-run` 是部署计划入口，不是合同校验入口。", text)

        validation_section = text.split("### 4.4 最小本地验证", 1)[1].split("### 4.5", 1)[0]
        self.assertLess(
            validation_section.index("app delivery validate-contract"),
            validation_section.index("app delivery build-artifact"),
        )

    def test_app_repository_standard_keeps_second_app_fast_path_rules(self) -> None:
        text = (REPO_ROOT / "docs" / "reference" / "app-repository-standard.md").read_text(encoding="utf-8")

        self.assertIn("如果 target 之间入口、依赖或回退面不同，一开始就提供 target-aware 合同与摘要文件", text)
        self.assertIn("真实 app resource secrets 从首轮接入开始就固定放在 `secrets/hosts/<target>/apps/<app>/resources/`", text)
        self.assertIn("不为新接入项目再落一份 `secrets/app-resources/<target>/<app>/` 实体文件", text)
        self.assertIn("最终验收必须回到 catalog 指向的正式仓库根执行", text)

    def test_app_delivery_workflow_records_second_app_preflight_checks(self) -> None:
        text = (REPO_ROOT / "docs" / "runbooks" / "app-project-delivery-workflow.md").read_text(
            encoding="utf-8"
        )

        self.assertIn("### 4.6 第二个应用接入前的预检", text)
        self.assertIn("`--app-repo-root` 只用于临时 worktree 验证", text)
        self.assertIn("最终验收必须回到 catalog 指向的正式仓库根", text)
        self.assertIn("`deploy/agentplane/contract*.yaml`、`docs/AGENTPLANE_DEPLOYMENT.*.md`、`inventory/servers/<target>/...` 与 `secrets/hosts/<target>/...` 必须在同一轮变更里收口", text)
        self.assertIn("退役旧控制面时，不只删脚本和文案，还要删除 `secrets/app-resources/<target>/<app>/*.env` 实体旧文件", text)

    def test_authoring_rules_prefer_active_docs_over_historical_specs(self) -> None:
        text = (REPO_ROOT / "docs" / "maintainers" / "control-plane-authoring.md").read_text(
            encoding="utf-8"
        )

        self.assertIn("active docs 与现行 code/test 优先于历史 spec、plan、handoff", text)
        self.assertIn("不要把历史设计稿中的旧路径、旧文案、旧 rollback 形态重新抄回 active docs", text)

# ======================================================================
# From: test_project_lifecycle_acceptance.py
# ======================================================================

from tests.support.cli import run_agentplane_cli as run_cli

def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")

def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

def _target_contract_relpath(target: str) -> str:
    if target == "wsl":
        return "deploy/agentplane/contract.wsl.yaml"
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
