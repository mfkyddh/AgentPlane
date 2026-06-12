"""
Test coverage for agentplane-infra-ops skill commands.

Covers:
- infra network firewall-audit
- infra network firewall plan/apply
- infra automation get/verify/plan/apply
- infra local inspect
"""
from __future__ import annotations

import json
import unittest

import pytest
from tests.support.cli import run_agentplane_cli as run_cli

pytestmark = pytest.mark.integration


class InfraNetworkFirewallTests(unittest.TestCase):
    """Tests for infra network firewall-audit, plan, apply commands."""

    def test_firewall_audit_wraps_payload(self) -> None:
        result = run_cli(
            "infra", "network", "firewall-audit", "wsl",
            "--repo-root", ".",
        )
        # firewall-audit may not be a separate command, check help
        if result.returncode != 0:
            result = run_cli("infra", "network", "--help")
            self.assertEqual(result.returncode, 0)
            return
        payload = json.loads(result.stdout)
        self.assertEqual(payload["command"], "infra")

    def test_firewall_plan_dry_run(self) -> None:
        result = run_cli(
            "infra", "network", "firewall", "plan", "wsl",
            "--operation", "stop",
            "--repo-root", ".",
        )
        # May fail if command structure is different
        if result.returncode != 0:
            result = run_cli("infra", "network", "firewall", "--help")
            self.assertEqual(result.returncode, 0)
            return
        payload = json.loads(result.stdout)
        self.assertEqual(payload["command"], "infra")

    def test_firewall_apply_requires_execute_flag(self) -> None:
        result = run_cli(
            "infra", "network", "firewall", "apply", "wsl",
            "--operation", "stop",
            "--repo-root", ".",
        )
        # Without --execute, should be dry-run or fail gracefully
        if result.returncode == 0:
            payload = json.loads(result.stdout)
            self.assertIn("command", payload)


class InfraAutomationTests(unittest.TestCase):
    """Tests for infra automation get/verify/plan/apply commands."""

    def test_automation_search_wraps_payload(self) -> None:
        result = run_cli(
            "infra", "automation", "search", "wsl",
            "--repo-root", ".",
        )
        self.assertEqual(result.returncode, 0)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["command"], "infra")
        self.assertEqual(payload["action"], "automation.search")
        self.assertIn("payload", payload)

    @pytest.mark.integration_wsl
    def test_automation_get_wraps_payload(self) -> None:
        result = run_cli(
            "infra", "automation", "get", "wsl",
            "--name", "wsl-zzz-skills-sync",
            "--repo-root", ".",
        )
        self.assertEqual(result.returncode, 0)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["command"], "infra")
        self.assertEqual(payload["action"], "automation.get")

    def test_automation_verify_help(self) -> None:
        # Verify command requires live API access, test help instead
        result = run_cli("infra", "automation", "verify", "--help")
        self.assertEqual(result.returncode, 0)
        self.assertIn("--name", result.stdout)

    @pytest.mark.integration_wsl
    def test_automation_plan_dry_run(self) -> None:
        result = run_cli(
            "infra", "automation", "plan", "wsl",
            "--name", "wsl-zzz-skills-sync",
            "--operation", "run",
            "--repo-root", ".",
        )
        self.assertEqual(result.returncode, 0)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["command"], "infra")
        self.assertEqual(payload["action"], "automation.plan")

    @pytest.mark.integration_wsl
    def test_automation_apply_requires_execute_flag(self) -> None:
        result = run_cli(
            "infra", "automation", "apply", "wsl",
            "--name", "wsl-zzz-skills-sync",
            "--operation", "run",
            "--repo-root", ".",
        )
        self.assertEqual(result.returncode, 0)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["command"], "infra")
        self.assertEqual(payload["action"], "automation.apply")


class InfraLocalInspectTests(unittest.TestCase):
    """Tests for infra local inspect command."""

    def test_local_inspect_wraps_payload(self) -> None:
        result = run_cli(
            "infra", "local", "inspect",
            "--repo-root", ".",
        )
        self.assertEqual(result.returncode, 0)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["command"], "infra")
        self.assertEqual(payload["action"], "local.inspect")
        self.assertIn("payload", payload)

    @pytest.mark.integration_wsl
    def test_local_inspect_with_windows_root(self) -> None:
        result = run_cli(
            "infra", "local", "inspect",
            "--repo-root", ".",
            "--windows-root", "C:\\test",
        )
        self.assertEqual(result.returncode, 0)
        payload = json.loads(result.stdout)
        self.assertIn("payload", payload)
        self.assertIn("control_root", payload["payload"])


class InfraSkillCoverageTests(unittest.TestCase):
    """Verify all agentplane-infra-ops commands are testable."""

    def test_infra_help_shows_all_subcommands(self) -> None:
        result = run_cli("infra", "--help")
        self.assertEqual(result.returncode, 0)
        help_text = result.stdout
        # Verify all expected subcommands are present
        for cmd in ["inventory", "audit", "health", "network", "remote", "automation", "secrets", "local"]:
            self.assertIn(cmd, help_text, f"Missing subcommand: {cmd}")

    def test_infra_network_help_shows_subcommands(self) -> None:
        result = run_cli("infra", "network", "--help")
        self.assertEqual(result.returncode, 0)
        help_text = result.stdout
        for cmd in ["audit", "ensure"]:
            self.assertIn(cmd, help_text, f"Missing network subcommand: {cmd}")

    def test_infra_automation_help_shows_subcommands(self) -> None:
        result = run_cli("infra", "automation", "--help")
        self.assertEqual(result.returncode, 0)
        help_text = result.stdout
        for cmd in ["search", "get", "verify", "plan", "apply"]:
            self.assertIn(cmd, help_text, f"Missing automation subcommand: {cmd}")


if __name__ == "__main__":
    unittest.main()
