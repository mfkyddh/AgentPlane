import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _listed_help_commands(help_text: str) -> set[str]:
    return set(re.findall(r"(?m)^\s{2,}([a-z][a-z0-9-]*)\b(?:\s{2,}|\s*$)", help_text))


def _listed_targets(help_text: str) -> set[str]:
    targets: set[str] = set()
    for choice_group in re.findall(r"\{([^}]+)\}", help_text):
        for token in choice_group.split(","):
            candidate = token.strip()
            if candidate in {"wsl", "prod0-main", "prod2-main"}:
                targets.add(candidate)
    return targets


def _assert_help_commands(
    testcase: unittest.TestCase,
    help_text: str,
    *,
    expected: set[str] | None = None,
    absent: set[str] | None = None,
) -> set[str]:
    commands = _listed_help_commands(help_text)
    if expected is not None:
        testcase.assertTrue(expected.issubset(commands), msg=f"missing commands: {sorted(expected - commands)}")
    if absent is not None:
        testcase.assertTrue(absent.isdisjoint(commands), msg=f"unexpected commands: {sorted(absent & commands)}")
    return commands


def run_cli(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "agentplane.cli", *args],
        cwd=cwd or REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


class CliEntrypointsTests(unittest.TestCase):
    def test_module_help_lists_required_subcommands_with_app_resource(self) -> None:
        result = run_cli("--help")
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        _assert_help_commands(
            self,
            result.stdout,
            expected={"host", "onepanel", "website", "service", "app", "projection"},
            absent={"network", "tenant", "automation", "cleanup", "inventory", "audit", "remote", "secrets"},
        )

        projection_help = run_cli("projection", "--help")
        self.assertEqual(projection_help.returncode, 0, msg=projection_help.stderr)
        _assert_help_commands(
            self,
            projection_help.stdout,
            expected={"runtime-env", "verification", "fixture", "ledger"},
        )

        projection_runtime_env_help = run_cli("projection", "runtime-env", "--help")
        self.assertEqual(projection_runtime_env_help.returncode, 0, msg=projection_runtime_env_help.stderr)
        _assert_help_commands(
            self,
            projection_runtime_env_help.stdout,
            expected={"plan", "apply", "verify"},
        )

        projection_verification_help = run_cli("projection", "verification", "--help")
        self.assertEqual(projection_verification_help.returncode, 0, msg=projection_verification_help.stderr)
        _assert_help_commands(self, projection_verification_help.stdout, expected={"run"})

        projection_fixture_help = run_cli("projection", "fixture", "--help")
        self.assertEqual(projection_fixture_help.returncode, 0, msg=projection_fixture_help.stderr)
        _assert_help_commands(
            self,
            projection_fixture_help.stdout,
            expected={"plan", "apply", "cleanup"},
        )

        projection_ledger_help = run_cli("projection", "ledger", "--help")
        self.assertEqual(projection_ledger_help.returncode, 0, msg=projection_ledger_help.stderr)
        _assert_help_commands(self, projection_ledger_help.stdout, expected={"refresh"})

        service_help = run_cli("service", "--help")
        self.assertEqual(service_help.returncode, 0, msg=service_help.stderr)
        _assert_help_commands(
            self,
            service_help.stdout,
            expected={"search", "get", "verify", "plan", "apply"},
        )

        website_help = run_cli("website", "--help")
        self.assertEqual(website_help.returncode, 0, msg=website_help.stderr)
        _assert_help_commands(
            self,
            website_help.stdout,
            expected={"search", "get", "verify", "plan", "apply", "refresh-ledger", "publish"},
        )

        website_publish_help = run_cli("website", "publish", "--help")
        self.assertEqual(website_publish_help.returncode, 0, msg=website_publish_help.stderr)
        _assert_help_commands(
            self,
            website_publish_help.stdout,
            expected={"plan", "apply", "verify"},
        )

        app_help = run_cli("app", "--help")
        self.assertEqual(app_help.returncode, 0, msg=app_help.stderr)
        _assert_help_commands(self, app_help.stdout, expected={"object", "resource", "delivery"})

        app_object_help = run_cli("app", "object", "--help")
        self.assertEqual(app_object_help.returncode, 0, msg=app_object_help.stderr)
        _assert_help_commands(
            self,
            app_object_help.stdout,
            expected={"search", "get", "verify", "refresh-ledger"},
        )

        app_resource_help = run_cli("app", "resource", "--help")
        self.assertEqual(app_resource_help.returncode, 0, msg=app_resource_help.stderr)
        _assert_help_commands(
            self,
            app_resource_help.stdout,
            expected={"search", "get", "verify", "refresh-ledger"},
        )

        app_delivery_help = run_cli("app", "delivery", "--help")
        self.assertEqual(app_delivery_help.returncode, 0, msg=app_delivery_help.stderr)
        _assert_help_commands(
            self,
            app_delivery_help.stdout,
            expected={
                "validate-contract",
                "onboard",
                "offboard",
                "build-artifact",
                "ship-image",
                "render-runtime",
                "deploy",
                "rollback",
                "verify",
                "inventory-refresh",
                "doc-sync",
            },
        )

        host_help = run_cli("host", "--help")
        self.assertEqual(host_help.returncode, 0, msg=host_help.stderr)
        _assert_help_commands(
            self,
            host_help.stdout,
            expected={"inventory", "audit", "cleanup", "automation", "network", "remote", "secrets", "local"},
            absent={"secrets-layout"},
        )

        host_cleanup_help = run_cli("host", "cleanup", "--help")
        self.assertEqual(host_cleanup_help.returncode, 0, msg=host_cleanup_help.stderr)
        _assert_help_commands(self, host_cleanup_help.stdout, expected={"plan", "apply"})

        host_automation_help = run_cli("host", "automation", "--help")
        self.assertEqual(host_automation_help.returncode, 0, msg=host_automation_help.stderr)
        _assert_help_commands(
            self,
            host_automation_help.stdout,
            expected={"search", "get", "verify", "plan", "apply"},
        )

        host_secrets_help = run_cli("host", "secrets", "--help")
        self.assertEqual(host_secrets_help.returncode, 0, msg=host_secrets_help.stderr)
        _assert_help_commands(
            self,
            host_secrets_help.stdout,
            expected={"init-data-services", "sync-layout"},
        )

        host_network_help = run_cli("host", "network", "--help")
        self.assertEqual(host_network_help.returncode, 0, msg=host_network_help.stderr)
        _assert_help_commands(self, host_network_help.stdout, expected={"audit", "ensure"})

        onepanel_help = run_cli("onepanel", "--help")
        self.assertEqual(onepanel_help.returncode, 0, msg=onepanel_help.stderr)
        _assert_help_commands(
            self,
            onepanel_help.stdout,
            expected={"panel", "firewall", "cronjob", "task"},
            absent={"website", "container", "app", "project", "ledger", "suite", "fixture", "ingress"},
        )

    def test_app_help_hides_legacy_flat_entrypoints(self) -> None:
        app_help = run_cli("app", "--help")

        self.assertEqual(app_help.returncode, 0, msg=app_help.stderr)
        _assert_help_commands(
            self,
            app_help.stdout,
            absent={
                "validate-contract",
                "render-runtime",
                "inventory-refresh",
                "doc-sync",
                "build-artifact",
                "ship-image",
                "deploy",
                "verify",
                "rollback",
                "onboard",
                "offboard",
            },
        )

    def test_required_subcommands_emit_json(self) -> None:
        cases = [
            ("host", "local", "inspect", "--repo-root", "D:/Projects/AgentPlane"),
            ("host", "inventory", "wsl", "--repo-root", str(REPO_ROOT)),
            ("host", "inventory", "prod0-main", "--repo-root", str(REPO_ROOT)),
            ("host", "audit", "wsl", "--repo-root", str(REPO_ROOT)),
            ("host", "audit", "prod0-main", "--repo-root", str(REPO_ROOT)),
            ("host", "cleanup", "plan", "wsl", "--repo-root", str(REPO_ROOT)),
            ("host", "automation", "search", "wsl", "--repo-root", str(REPO_ROOT)),
            ("onepanel", "--env", "wsl", "--json"),
        ]
        for args in cases:
            with self.subTest(args=args):
                result = run_cli(*args)
                self.assertEqual(result.returncode, 0, msg=result.stderr)
                payload = json.loads(result.stdout)
                self.assertIsInstance(payload, dict)
                self.assertIn("command", payload)

    def test_onepanel_defaults_to_human_text_but_can_emit_json(self) -> None:
        text_result = run_cli("onepanel", "--env", "wsl")
        self.assertEqual(text_result.returncode, 0, msg=text_result.stderr)
        self.assertIn("onepanel", text_result.stdout)
        with self.assertRaises(json.JSONDecodeError):
            json.loads(text_result.stdout)

        json_result = run_cli("onepanel", "--env", "wsl", "--json")
        self.assertEqual(json_result.returncode, 0, msg=json_result.stderr)
        payload = json.loads(json_result.stdout)
        self.assertEqual("onepanel", payload.get("command"))

    def test_onepanel_invalid_json_body_returns_stable_error_code(self) -> None:
        result = run_cli(
            "onepanel",
            "--env",
            "wsl",
            "--json",
            "cronjob",
            "plan",
            "--mode",
            "handle",
            "--body-json",
            "not-json",
        )
        self.assertEqual(result.returncode, 1)
        payload = json.loads(result.stdout)
        self.assertEqual("onepanel.invalid_json", payload["error"]["code"])

    def test_host_cleanup_apply_emits_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".playwright-cli").mkdir(parents=True)
            result = run_cli("host", "cleanup", "apply", "wsl", "--repo-root", str(root), cwd=REPO_ROOT)
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual("host", payload.get("command"))
            self.assertEqual("cleanup.apply", payload.get("action"))
            self.assertEqual("wsl", payload.get("target"))
            self.assertIn("removed", payload["payload"])

    def test_host_automation_search_emits_json(self) -> None:
        result = run_cli("host", "automation", "search", "wsl", "--repo-root", str(REPO_ROOT), cwd=REPO_ROOT)

        self.assertEqual(result.returncode, 0, msg=result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual("host", payload.get("command"))
        self.assertEqual("automation.search", payload.get("action"))
        self.assertEqual("wsl", payload.get("target"))
        self.assertIn("items", payload["payload"])

    def test_host_automation_help_lists_formal_targets(self) -> None:
        result = run_cli("host", "automation", "search", "--help")

        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertTrue({"wsl", "prod0-main", "prod2-main"}.issubset(_listed_targets(result.stdout)))

    def test_top_level_automation_entry_is_removed(self) -> None:
        result = run_cli("automation", "--help")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("invalid choice", result.stderr)


if __name__ == "__main__":
    unittest.main()
