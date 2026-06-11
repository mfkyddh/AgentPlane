from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pytest
from agentplane.domain.service import lifecycle as service_lifecycle
from tests.support.service_cli import (
    run_cli,
    write_fake_service_ssh,
    write_inventory,
)

pytestmark = pytest.mark.integration


# ======================================================================
# From: test_service_apply_cli.py
# ======================================================================


class ServiceApplyCliTests(unittest.TestCase):
    def test_service_apply_restarts_systemd_service_and_verifies(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root)
            bin_dir = root / "bin"
            bin_dir.mkdir(parents=True, exist_ok=True)
            log_file = root / "service-apply-mihomo.log"
            write_fake_service_ssh(bin_dir)

            result = run_cli(
                "service",
                "apply",
                "--target",
                "prod0-main",
                "--name",
                "mihomo",
                "--operation",
                "restart",
                "--execute",
                "--repo-root",
                str(root),
                env_overrides={"PATH": f"{bin_dir}:{os.environ['PATH']}", "FAKE_CMD_LOG": str(log_file)},
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(result.stdout)
            plan = json.loads(
                run_cli(
                    "service",
                    "plan",
                    "--target",
                    "prod0-main",
                    "--name",
                    "mihomo",
                    "--operation",
                    "restart",
                    "--repo-root",
                    str(root),
                ).stdout
            )
            self.assertEqual("service", payload["command"])
            self.assertEqual("apply", payload["action"])
            self.assertTrue(payload["payload"]["ok"])
            self.assertTrue(payload["payload"]["verified"]["ok"])
            self.assertEqual(
                plan["payload"]["steps"][0]["argv"],
                payload["payload"]["results"][0]["argv"],
            )
            log_text = log_file.read_text(encoding="utf-8")
            self.assertIn("systemctl restart mihomo", log_text)
            self.assertIn("systemctl is-active mihomo", log_text)

    def test_service_apply_reconcile_uses_remote_compose_path_and_verifies(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root)
            bin_dir = root / "bin"
            bin_dir.mkdir(parents=True, exist_ok=True)
            log_file = root / "service-apply-postgres.log"
            write_fake_service_ssh(bin_dir)

            result = run_cli(
                "service",
                "apply",
                "--target",
                "prod0-main",
                "--name",
                "postgres",
                "--operation",
                "reconcile",
                "--execute",
                "--repo-root",
                str(root),
                env_overrides={"PATH": f"{bin_dir}:{os.environ['PATH']}", "FAKE_CMD_LOG": str(log_file)},
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(result.stdout)
            plan = json.loads(
                run_cli(
                    "service",
                    "plan",
                    "--target",
                    "prod0-main",
                    "--name",
                    "postgres",
                    "--operation",
                    "reconcile",
                    "--repo-root",
                    str(root),
                ).stdout
            )
            self.assertTrue(payload["payload"]["ok"])
            self.assertTrue(payload["payload"]["verified"]["ok"])
            self.assertEqual(
                plan["payload"]["steps"][0]["argv"],
                payload["payload"]["results"][0]["argv"],
            )
            self.assertTrue(plan["payload"]["projection_handoff"]["required"])
            self.assertTrue(payload["payload"]["projection_handoff"]["required"])
            self.assertEqual("projection", payload["payload"]["projection_handoff"]["steps"][0]["command"])
            self.assertEqual("ledger.refresh", payload["payload"]["projection_handoff"]["steps"][0]["action"])
            log_text = log_file.read_text(encoding="utf-8")
            self.assertIn(
                "cd /opt/agentplane/infra/compose/postgres && docker compose -f docker-compose.prod0.yml up -d",
                log_text,
            )
            self.assertIn("docker inspect postgres18-prod", log_text)



# ======================================================================
# From: test_service_lifecycle.py
# ======================================================================


class ServiceLifecycleTests(unittest.TestCase):
    def test_plan_onboard_and_offboard_cycles(self):
        base_services = {
            "postgres": {"container_name": "postgres18"},
        }
        next_services, evidence = service_lifecycle.plan_service_registry_onboard(
            base_services,
            service_key="sampleapi",
            entry={"container_name": "sampleapi-prod", "control_plane": "compose"},
        )
        self.assertIn("sampleapi", next_services)
        self.assertEqual(next_services["sampleapi"]["container_name"], "sampleapi-prod")
        self.assertFalse(evidence["replaced"])
        self.assertEqual(evidence["action"], "upsert")

        replaced_services, replaced_evidence = service_lifecycle.plan_service_registry_onboard(
            next_services,
            service_key="sampleapi",
            entry={"container_name": "sampleapi-prod", "control_plane": "compose"},
            allow_replace=True,
        )
        self.assertTrue(replaced_evidence["replaced"])
        self.assertEqual(replaced_services["sampleapi"]["container_name"], "sampleapi-prod")

        offboarded_services, remove_evidence = service_lifecycle.plan_service_registry_offboard(
            replaced_services,
            service_key="sampleapi",
        )
        self.assertNotIn("sampleapi", offboarded_services)
        self.assertEqual(remove_evidence["action"], "remove")
        self.assertEqual(remove_evidence["service_key"], "sampleapi")

        with self.assertRaises(ValueError):
            service_lifecycle.plan_service_registry_offboard(
                offboarded_services,
                service_key="sampleapi",
            )

    def test_plan_rejects_invalid_entries(self):
        base_services = {}
        with self.assertRaises(ValueError):
            service_lifecycle.plan_service_registry_onboard(
                base_services,
                service_key="docker",
                entry={"container_name": "ignored"},
            )
        with self.assertRaises(ValueError):
            service_lifecycle.plan_service_registry_onboard(
                base_services,
                service_key="sampleapi",
                entry={"container_name": " ", "control_plane": "compose"},
            )
        with self.assertRaises(ValueError):
            service_lifecycle.plan_service_registry_onboard(
                base_services,
                service_key="sampleapi",
                entry={"container_name": "foo", "control_plane": "invalid"},
            )

    def test_apply_round_trip_updates_inventory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            target = "wsl"
            inventory_file = self._write_inventory(repo_root, target, {"postgres": {"container_name": "postgres18"}})

            onboard_result = service_lifecycle.apply_service_onboard(
                repo_root=repo_root,
                target=target,
                service_key="sampleapi",
                entry={"container_name": " sampleapi-prod ", "control_plane": "compose"},
            )
            self.assertTrue(onboard_result.changed)
            payload = json.loads(inventory_file.read_text(encoding="utf-8").strip())
            self.assertIn("sampleapi", payload["services"])
            self.assertEqual(payload["services"]["sampleapi"]["container_name"], "sampleapi-prod")

            offboard_result = service_lifecycle.apply_service_offboard(
                repo_root=repo_root,
                target=target,
                service_key="sampleapi",
            )
            self.assertTrue(offboard_result.changed)
            payload_after = json.loads(inventory_file.read_text(encoding="utf-8").strip())
            self.assertNotIn("sampleapi", payload_after["services"])

    def test_service_verify_separates_ledger_fields_and_observation(self) -> None:
        from agentplane.domain.service.handlers import verify_service

        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            self._write_inventory(
                repo_root,
                "prod0-main",
                {
                    "postgres": {
                        "container_name": "postgres18-prod",
                        "control_plane": "compose",
                        "image": "postgres:18.3",
                    }
                },
            )

            with patch(
                "agentplane.domain.service.handlers.verify_container_service",
                return_value={
                    "ok": True,
                    "checks": {"running": {"ok": True, "actual": "running"}},
                    "evidence": [{"kind": "probe", "value": "docker inspect postgres18-prod"}],
                    "failures": [],
                },
            ):
                payload = verify_service(repo_root, "prod0-main", "postgres")

        self.assertTrue(payload["ok"])
        self.assertEqual("targets/prod0-main/services/postgres", payload["canonical_ref"])
        self.assertEqual("targets/prod0-main/services/postgres", payload["ledger_fields"]["canonical_ref"])
        self.assertEqual("postgres", payload["ledger_fields"]["name"])
        self.assertNotIn("evidence", payload["ledger_fields"])
        self.assertIn("live", payload["verification_fields"])
        self.assertEqual(
            [{"kind": "probe", "value": "docker inspect postgres18-prod"}],
            payload["verification_fields"]["live"]["evidence"],
        )

    def _write_inventory(self, repo_root: Path, target: str, services: dict[str, dict[str, str]]) -> Path:
        server_dir = repo_root / "inventory" / "servers" / target
        server_dir.mkdir(parents=True, exist_ok=True)
        inventory_file = server_dir / "inventory.json"
        payload = {"services": services}
        inventory_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return inventory_file
