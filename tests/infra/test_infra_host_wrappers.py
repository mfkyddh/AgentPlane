from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import pytest
from agentplane.cli.inventory import generate_inventory_snapshot
from agentplane.runtime.host_profile import HostProfile
from tests.support.cli import run_agentplane_cli as run_cli
from tests.support.paths import REPO_ROOT

pytestmark = pytest.mark.e2e


class HostCliTests(unittest.TestCase):
    def test_infra_help_lists_network(self) -> None:
        result = run_cli("infra", "--help")
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIn("local", result.stdout)
        self.assertIn("network", result.stdout)
        self.assertIn("inventory", result.stdout)
        self.assertIn("audit", result.stdout)
        self.assertIn("cleanup", result.stdout)
        self.assertIn("automation", result.stdout)
        self.assertIn("remote", result.stdout)
        self.assertIn("secrets", result.stdout)
        self.assertIn("health", result.stdout)
        self.assertNotIn("secrets-layout", result.stdout)

    def test_legacy_top_level_host_entrypoints_are_rejected(self) -> None:
        for argv in (
            ("cleanup", "plan", "--env", "wsl"),
            ("automation", "search", "wsl"),
            ("inventory", "wsl"),
            ("audit", "filesystem", "--env", "wsl"),
            ("remote", "bash", "prod0-main", "--dry-run"),
            ("secrets", "init-data-services", "--target", "wsl"),
            ("infra", "secrets-layout", "wsl", "--repo-root", str(REPO_ROOT)),
        ):
            with self.subTest(argv=argv):
                result = run_cli(*argv)
                self.assertNotEqual(0, result.returncode)
                self.assertIn("invalid choice", result.stderr)

    def test_infra_inventory_wraps_inventory_payload(self) -> None:
        result = run_cli("infra", "inventory", "wsl", "--repo-root", str(REPO_ROOT))
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual({"command", "action", "target", "payload"}, set(payload))
        self.assertEqual("infra", payload["command"])
        self.assertEqual("inventory", payload["action"])
        self.assertEqual("wsl", payload["target"])
        self.assertIsInstance(payload["payload"], dict)

    def test_infra_inventory_wsl_uses_backend_runner_contract_on_windows_host(self) -> None:
        fake_snapshot = {"label": "WSL jump host", "target": "wsl"}

        class _FakeRunner:
            def __init__(self) -> None:
                self.plan = None

            def execute(self, plan, *, bindings=None):
                self.plan = plan
                return SimpleNamespace(ok=True, stdout=json.dumps(fake_snapshot), stderr="")

        runner = _FakeRunner()
        payload = generate_inventory_snapshot(
            REPO_ROOT,
            "wsl",
            host_profile=HostProfile(os_name="windows", linux_backend="windows-wsl", supports_docker=True),
            runner=runner,
        )

        self.assertEqual("windows-wsl", payload["backend_type"])
        self.assertEqual("windows-wsl", runner.plan.backend_type)
        self.assertEqual(fake_snapshot, payload["payload"])

    def test_infra_local_inspect_wraps_payload(self) -> None:
        result = run_cli("infra", "local", "inspect", "--repo-root", "C:/repos/agentplane")
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual({"command", "action", "target", "payload"}, set(payload))
        self.assertEqual("infra", payload["command"])
        self.assertEqual("local.inspect", payload["action"])
        self.assertEqual("local", payload["target"])
        self.assertEqual("wsl-linux", payload["payload"]["linux_backend"]["backend_type"])

    def test_infra_audit_wraps_filesystem_audit_payload(self) -> None:
        result = run_cli("infra", "audit", "wsl", "--repo-root", str(REPO_ROOT))
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual({"command", "action", "target", "payload"}, set(payload))
        self.assertEqual("infra", payload["command"])
        self.assertEqual("audit", payload["action"])
        self.assertEqual("wsl", payload["target"])
        self.assertIsInstance(payload["payload"], dict)

    def test_infra_cleanup_plan_wraps_cleanup_payload(self) -> None:
        result = run_cli("infra", "cleanup", "plan", "wsl", "--repo-root", str(REPO_ROOT))
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual({"command", "action", "target", "payload"}, set(payload))
        self.assertEqual("infra", payload["command"])
        self.assertEqual("cleanup.plan", payload["action"])
        self.assertEqual("wsl", payload["target"])
        self.assertIn("actions", payload["payload"])

    def test_infra_cleanup_apply_wraps_cleanup_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / ".playwright-cli"
            target.mkdir(parents=True)
            (target / "page.yml").write_text("snapshot", encoding="utf-8")

            result = run_cli("infra", "cleanup", "apply", "wsl", "--repo-root", str(root))
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual({"command", "action", "target", "payload"}, set(payload))
            self.assertEqual("infra", payload["command"])
            self.assertEqual("cleanup.apply", payload["action"])
            self.assertEqual("wsl", payload["target"])
            self.assertEqual(1, payload["payload"]["removed_count"])

    def test_infra_automation_search_wraps_payload(self) -> None:
        result = run_cli("infra", "automation", "search", "wsl", "--repo-root", str(REPO_ROOT))
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual({"command", "action", "target", "payload"}, set(payload))
        self.assertEqual("infra", payload["command"])
        self.assertEqual("automation.search", payload["action"])
        self.assertEqual("wsl", payload["target"])
        self.assertIn("items", payload["payload"])

    def test_infra_remote_bash_wraps_dry_run_payload(self) -> None:
        script = REPO_ROOT / "agentplane" / "scripts" / "internal" / "remote" / "example.sh"
        result = run_cli(
            "infra",
            "remote",
            "bash",
            "prod0-main",
            "--repo-root",
            str(REPO_ROOT),
            "--dry-run",
            "--script-file",
            str(script),
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual({"command", "action", "target", "payload"}, set(payload))
        self.assertEqual("infra", payload["command"])
        self.assertEqual("remote.bash", payload["action"])
        self.assertEqual("prod0-main", payload["target"])
        self.assertTrue(payload["payload"]["dry_run"])

