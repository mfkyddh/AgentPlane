from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import pytest
from agentplane.domain.app.lifecycle_prod0_main import (
    ALLOWED_OFFBOARDING_OPERATIONS as PROD0_ALLOWED_OFFBOARDING_OPERATIONS,
)
from agentplane.domain.app.lifecycle_prod0_main import (
    ALLOWED_ONBOARDING_OPERATIONS as PROD0_ALLOWED_ONBOARDING_OPERATIONS,
)
from agentplane.domain.app.lifecycle_prod0_main import (
    Prod0MainLifecyclePlan,
    Prod0MainLifecyclePolicy,
)
from agentplane.domain.app.lifecycle_prod0_main import (
    lane2_policy_helper as prod0_lane2_policy_helper,
)
from agentplane.domain.app.lifecycle_wsl import (
    ALLOWED_OFFBOARDING_OPERATIONS as WSL_ALLOWED_OFFBOARDING_OPERATIONS,
)
from agentplane.domain.app.lifecycle_wsl import (
    ALLOWED_ONBOARDING_OPERATIONS as WSL_ALLOWED_ONBOARDING_OPERATIONS,
)
from agentplane.domain.app.lifecycle_wsl import (
    WslLifecyclePlan,
    WslLifecyclePolicy,
)
from agentplane.domain.app.lifecycle_wsl import (
    lane2_policy_helper as wsl_lane2_policy_helper,
)
from agentplane.domain.app.projection_lifecycle import (
    LifecycleIntent,
    LifecycleLayer,
    ProjectionLifecyclePlan,
    ProjectionLifecycleStage,
    default_offboarding_plan,
    default_onboarding_plan,
)
from agentplane.domain.app.resource_paths import app_resource_secret_dir, app_resource_secret_relative
from agentplane.domain.app.secrets_lifecycle import (
    apply_secret_allocation,
    apply_secret_retirement,
    plan_secret_allocation,
    plan_secret_retirement,
)
from tests.support.cli import run_agentplane_cli as run_cli

pytestmark = pytest.mark.integration


class AppLifecycleCliContractsTests(unittest.TestCase):
    def test_onboard_help_exposes_single_formal_entry_contract(self) -> None:
        result = run_cli("app", "delivery", "onboard", "--help")
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIn("single formal entry", result.stdout)
        self.assertIn("--dry-run", result.stdout)
        self.assertIn("--write", result.stdout)

    def test_offboard_help_exposes_single_formal_entry_contract(self) -> None:
        result = run_cli("app", "delivery", "offboard", "--help")
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIn("single formal entry", result.stdout)
        self.assertIn("--dry-run", result.stdout)
        self.assertIn("--write", result.stdout)

    def test_onboard_requires_dry_run_or_write(self) -> None:
        result = run_cli("app", "delivery", "onboard", "--target", "wsl", "--app", "sub2api")
        self.assertEqual(result.returncode, 2)
        self.assertIn("--dry-run", result.stderr)
        self.assertIn("--write", result.stderr)

    def test_onboard_rejects_dry_run_plus_write(self) -> None:
        result = run_cli(
            "app",
            "delivery",
            "onboard",
            "--target",
            "wsl",
            "--app",
            "sub2api",
            "--dry-run",
            "--write",
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("--dry-run", result.stderr)
        self.assertIn("--write", result.stderr)

    def test_offboard_requires_dry_run_or_write(self) -> None:
        result = run_cli("app", "delivery", "offboard", "--target", "wsl", "--app", "sub2api")
        self.assertEqual(result.returncode, 2)
        self.assertIn("--dry-run", result.stderr)
        self.assertIn("--write", result.stderr)

    def test_offboard_rejects_dry_run_plus_write(self) -> None:
        result = run_cli(
            "app",
            "delivery",
            "offboard",
            "--target",
            "wsl",
            "--app",
            "sub2api",
            "--dry-run",
            "--write",
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("--dry-run", result.stderr)
        self.assertIn("--write", result.stderr)


# ======================================================================
# From: test_app_lifecycle_prod0_main.py
# ======================================================================


def test_onboarding_plan_enforces_prod0_target() -> None:
    plan = Prod0MainLifecyclePlan(
        action="onboard",
        project="app",
        target="wsl",
        operations=(PROD0_ALLOWED_ONBOARDING_OPERATIONS[0],),
    )
    with pytest.raises(ValueError, match="prod0-main lifecycle policy only applies to target"):
        Prod0MainLifecyclePolicy.validate_onboarding_plan(plan)


def test_onboarding_plan_requires_safety_check() -> None:
    plan = Prod0MainLifecyclePlan(
        action="onboard",
        project="app",
        target="prod0-main",
        operations=("compose_candidate",),
    )
    with pytest.raises(ValueError, match="production safety check"):
        Prod0MainLifecyclePolicy.validate_onboarding_plan(plan)


def test_onboarding_plan_allows_required_operations() -> None:
    plan = Prod0MainLifecyclePlan(
        action="onboard",
        project="app",
        target="prod0-main",
        operations=("inventory_sync", "projection_verify"),
        networks=("zqf_network",),
        service_key="prod0-app",
    )
    Prod0MainLifecyclePolicy.validate_onboarding_plan(plan)


def test_offboarding_plan_must_dry_run() -> None:
    plan = Prod0MainLifecyclePlan(
        action="offboard",
        project="app",
        target="prod0-main",
        operations=(PROD0_ALLOWED_OFFBOARDING_OPERATIONS[1],),
    )
    with pytest.raises(ValueError, match="offboarding plans must declare requires_dry_run"):
        Prod0MainLifecyclePolicy.validate_offboarding_plan(plan)


def test_offboarding_plan_accepts_dry_run_flag() -> None:
    plan = Prod0MainLifecyclePlan(
        action="offboard",
        project="app",
        target="prod0-main",
        operations=("dry_run",),
        requires_dry_run=True,
    )
    Prod0MainLifecyclePolicy.validate_offboarding_plan(plan)


def test_policy_helper_lists_constraints() -> None:
    summary = prod0_lane2_policy_helper()
    assert summary["target"] == "prod0-main"
    assert "zqf_network" in summary["allowed_networks"]
    assert "dry_run" in summary["offboarding_operations"]


# ======================================================================
# From: test_app_lifecycle_wsl.py
# ======================================================================


def test_onboarding_plan_requires_wsl_target() -> None:
    plan = WslLifecyclePlan(
        action="onboard",
        project="wsl-app",
        target="prod0-main",
        operations=(WSL_ALLOWED_ONBOARDING_OPERATIONS[0],),
    )
    with pytest.raises(ValueError, match="WSL lifecycle policy only applies to the 'wsl' target"):
        WslLifecyclePolicy.validate_onboarding_plan(plan)


def test_onboarding_plan_disallows_production_networks() -> None:
    plan = WslLifecyclePlan(
        action="onboard",
        project="wsl-app",
        target="wsl",
        operations=(WSL_ALLOWED_ONBOARDING_OPERATIONS[0],),
        networks=("zqf_network",),
    )
    with pytest.raises(ValueError, match="production networks"):
        WslLifecyclePolicy.validate_onboarding_plan(plan)


def test_onboarding_plan_requires_local_service_key_prefix() -> None:
    plan = WslLifecyclePlan(
        action="onboard",
        project="wsl-app",
        target="wsl",
        service_key="prod-service",
        operations=(WSL_ALLOWED_ONBOARDING_OPERATIONS[0],),
    )
    with pytest.raises(ValueError, match="service_key"):
        WslLifecyclePolicy.validate_onboarding_plan(plan)


def test_offboarding_plan_requires_explicit_dry_run() -> None:
    plan = WslLifecyclePlan(
        action="offboard",
        project="wsl-app",
        target="wsl",
        operations=(
            WSL_ALLOWED_OFFBOARDING_OPERATIONS[1],
            WSL_ALLOWED_OFFBOARDING_OPERATIONS[2],
        ),
    )
    with pytest.raises(ValueError, match="dry_run"):
        WslLifecyclePolicy.validate_offboarding_plan(plan)


def test_lane2_policy_helper_describes_detailed_constraints() -> None:
    summary = wsl_lane2_policy_helper()
    assert summary["target"] == "wsl"
    assert "dry_run" in summary["offboarding_operations"]
    assert "zqf_network" in summary["forbidden_networks"]


# ======================================================================
# From: test_app_lifecycle_secrets.py
# ======================================================================

TARGET = "prod0-main"
APP = "phase5"


def _write_catalog(root: Path) -> None:
    catalog_dir = root / "inventory" / "apps"
    catalog_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "apps": [
            {
                "app": APP,
                "repo_name": "phase5-app",
                "repo_root": str(root),
                "service_key": APP,
                "contracts": {TARGET: "deploy/agentplane/contract.yaml"},
            }
        ]
    }
    (catalog_dir / "catalog.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def _write_registry(root: Path) -> None:
    server_dir = root / "inventory" / "servers" / TARGET
    server_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        APP: {
            "owner_app": APP,
            "ledger_status": {
                "intent": "live-db-partition-ledger",
                "runtime_credential_model": "shared-runtime-credentials",
                "tenant_isolation": "logical-db-partition-not-strong-isolation",
                "local_secret_presence": "not-materialized-by-repo",
            },
            "postgres": {"database": "phase5_db", "user": "phase5_user"},
            "redis": {"db": 1, "key_prefix": "phase5:"},
            "secret_files": [],
        }
    }
    (server_dir / "app-resources.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


class SecretLifecycleTests(unittest.TestCase):
    def test_allocate_and_retire_lifecycle(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_catalog(root)
            _write_registry(root)

            plan = plan_secret_allocation(root, TARGET, APP)
            self.assertEqual("allocate", plan["operation"])
            self.assertFalse(plan["guarded"])
            self.assertEqual({"postgres.env", "redis.env"}, {Path(item["relative"]).name for item in plan["files"]})
            self.assertSetEqual(
                {
                    app_resource_secret_relative(TARGET, APP, "postgres"),
                    app_resource_secret_relative(TARGET, APP, "redis"),
                },
                set(plan["missing_files"]),
            )

            allocation = apply_secret_allocation(root, TARGET, APP, execute=True)
            self.assertTrue(all(Path(path).is_file() for path in allocation["created_files"]))
            self.assertEqual(2, len(allocation["created_files"]))
            registry_path = root / "inventory" / "servers" / TARGET / "app-resources.json"
            updated = json.loads(registry_path.read_text(encoding="utf-8"))[APP]
            self.assertEqual("materialized-in-agentplane", updated["ledger_status"]["local_secret_presence"])
            self.assertEqual(
                [
                    app_resource_secret_relative(TARGET, APP, "postgres"),
                    app_resource_secret_relative(TARGET, APP, "redis"),
                ],
                updated["secret_files"],
            )

            plan_after = plan_secret_allocation(root, TARGET, APP)
            self.assertEqual([], plan_after["missing_files"])
            self.assertTrue(all(item["exists"] for item in plan_after["files"]))

            retirement_plan = plan_secret_retirement(root, TARGET, APP)
            self.assertTrue(retirement_plan["guarded"])
            self.assertFalse(retirement_plan["missing_files"])
            self.assertTrue(all(item["exists"] for item in retirement_plan["files"]))

            retired = apply_secret_retirement(root, TARGET, APP, execute=True)
            self.assertEqual(set(allocation["created_files"]), set(retired["removed_files"]))
            self.assertFalse((app_resource_secret_dir(root, TARGET, APP) / "postgres.env").exists())
            registry_final = json.loads(registry_path.read_text(encoding="utf-8"))[APP]
            self.assertEqual("retired", registry_final["ledger_status"]["local_secret_presence"])

            plan_after_retirement = plan_secret_retirement(root, TARGET, APP)
            self.assertTrue(plan_after_retirement["missing_files"])
            self.assertEqual(
                plan_after_retirement["missing_files"],
                [
                    app_resource_secret_relative(TARGET, APP, "postgres"),
                    app_resource_secret_relative(TARGET, APP, "redis"),
                ],
            )


# ======================================================================
# From: test_app_lifecycle_projection.py
# ======================================================================


class ProjectionLifecyclePlanTests(unittest.TestCase):
    def test_onboarding_default_plan_sequence(self) -> None:
        plan = default_onboarding_plan(dry_run=False)
        plan.validate()
        summary = plan.summary()

        self.assertEqual(summary["intent"], "onboarding")
        self.assertTrue(summary["write_expected"])
        self.assertEqual(
            summary["layers"],
            ["projection", "runtime-env", "ledger", "doc-sync"],
        )
        self.assertEqual(summary["sequence"][-1], "doc sync confirmation")

    def test_offboarding_default_plan_summary(self) -> None:
        plan = default_offboarding_plan(dry_run=False)
        plan.validate()
        summary = plan.summary()

        self.assertEqual(summary["intent"], "offboarding")
        self.assertEqual(summary["sequence"][0], "projection retirement")
        self.assertIn("ledger retirement", summary["sequence"])
        self.assertEqual(summary["layers"][-1], "doc-sync")

    def test_dry_run_blocks_write_stage(self) -> None:
        plan = ProjectionLifecyclePlan(LifecycleIntent.ONBOARDING, dry_run=True)
        stage = ProjectionLifecycleStage(
            layer=LifecycleLayer.PROJECTION,
            name="projection",
            description="dry-run stub",
            write_mode=True,
        )

        with self.assertRaises(ValueError):
            plan.add_stage(stage)

    def test_missing_doc_sync_fails_validation(self) -> None:
        plan = ProjectionLifecyclePlan(LifecycleIntent.ONBOARDING, dry_run=False)
        plan.add_stage(
            ProjectionLifecycleStage(
                layer=LifecycleLayer.PROJECTION,
                name="inventory projection",
                description="capture inventory",
                write_mode=True,
            )
        )

        with self.assertRaises(ValueError):
            plan.validate()

    def test_out_of_order_stages_rejected(self) -> None:
        plan = ProjectionLifecyclePlan(LifecycleIntent.OFFBOARDING, dry_run=False)
        plan.add_stage(
            ProjectionLifecycleStage(
                layer=LifecycleLayer.RUNTIME_ENV,
                name="runtime cleanup",
                description="capture state",
                write_mode=False,
            )
        )

        with self.assertRaises(ValueError):
            plan.add_stage(
                ProjectionLifecycleStage(
                    layer=LifecycleLayer.PROJECTION,
                    name="projection retirement",
                    description="must not run after runtime stage",
                    write_mode=False,
                )
            )
