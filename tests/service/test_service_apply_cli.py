import json
import os
import tempfile
import unittest
from pathlib import Path

from tests.support.service_cli import run_cli, write_fake_service_ssh, write_inventory


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
            self.assertIn("cd /opt/agentplane/infra/compose/postgres && docker compose -f docker-compose.prod0.yml up -d", log_text)
            self.assertIn("docker inspect postgres18-prod", log_text)


if __name__ == "__main__":
    unittest.main()
