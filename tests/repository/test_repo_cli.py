from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import pytest

pytestmark = pytest.mark.e2e

REPO_ROOT = Path(__file__).resolve().parents[2]

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
            expected={"infra", "onepanel", "ingress", "service", "app", "projection", "repo"},
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

        website_help = run_cli("ingress", "--help")
        self.assertEqual(website_help.returncode, 0, msg=website_help.stderr)
        _assert_help_commands(
            self,
            website_help.stdout,
            expected={"search", "get", "verify", "plan", "apply", "refresh-ledger", "publish"},
        )

        website_publish_help = run_cli("ingress", "publish", "--help")
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

        host_help = run_cli("infra", "--help")
        self.assertEqual(host_help.returncode, 0, msg=host_help.stderr)
        _assert_help_commands(
            self,
            host_help.stdout,
            expected={"inventory", "audit", "live-gate", "cleanup", "automation", "network", "remote", "secrets", "local"},
            absent={"secrets-layout"},
        )

        host_live_gate_help = run_cli("infra", "live-gate", "--help")
        self.assertEqual(host_live_gate_help.returncode, 0, msg=host_live_gate_help.stderr)
        _assert_help_commands(self, host_live_gate_help.stdout, expected={"plan", "run"})

        host_cleanup_help = run_cli("infra", "cleanup", "--help")
        self.assertEqual(host_cleanup_help.returncode, 0, msg=host_cleanup_help.stderr)
        _assert_help_commands(self, host_cleanup_help.stdout, expected={"plan", "apply"})

        host_automation_help = run_cli("infra", "automation", "--help")
        self.assertEqual(host_automation_help.returncode, 0, msg=host_automation_help.stderr)
        _assert_help_commands(
            self,
            host_automation_help.stdout,
            expected={"search", "get", "verify", "plan", "apply"},
        )

        host_secrets_help = run_cli("infra", "secrets", "--help")
        self.assertEqual(host_secrets_help.returncode, 0, msg=host_secrets_help.stderr)
        _assert_help_commands(
            self,
            host_secrets_help.stdout,
            expected={"init-data-services", "sync-layout"},
        )

        host_network_help = run_cli("infra", "network", "--help")
        self.assertEqual(host_network_help.returncode, 0, msg=host_network_help.stderr)
        _assert_help_commands(self, host_network_help.stdout, expected={"audit", "ensure"})

        onepanel_help = run_cli("onepanel", "--help")
        self.assertEqual(onepanel_help.returncode, 0, msg=onepanel_help.stderr)
        _assert_help_commands(
            self,
            onepanel_help.stdout,
            expected={"panel", "firewall", "cronjob", "task"},
            absent={"ingress", "container", "app", "project", "ledger", "suite", "fixture", "ingress"},
        )

        repo_help = run_cli("repo", "--help")
        self.assertEqual(repo_help.returncode, 0, msg=repo_help.stderr)
        _assert_help_commands(
            self,
            repo_help.stdout,
            expected={"health-check", "status", "docs-sanity", "secret-scan", "privacy-scan", "release-check", "skills"},
        )

        repo_skills_help = run_cli("repo", "skills", "--help")
        self.assertEqual(repo_skills_help.returncode, 0, msg=repo_skills_help.stderr)
        _assert_help_commands(
            self,
            repo_skills_help.stdout,
            expected={"check", "list", "export", "sync"},
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
            ("infra", "local", "inspect", "--repo-root", "C:/repos/agentplane"),
            ("infra", "inventory", "wsl", "--repo-root", str(REPO_ROOT)),
            ("infra", "inventory", "prod0-main", "--repo-root", str(REPO_ROOT)),
            ("infra", "audit", "wsl", "--repo-root", str(REPO_ROOT)),
            ("infra", "audit", "prod0-main", "--repo-root", str(REPO_ROOT)),
            ("infra", "live-gate", "plan", "--profile", "wsl", "--repo-root", str(REPO_ROOT)),
            ("infra", "cleanup", "plan", "wsl", "--repo-root", str(REPO_ROOT)),
            ("infra", "automation", "search", "wsl", "--repo-root", str(REPO_ROOT)),
            ("repo", "secret-scan", "--repo-root", str(REPO_ROOT)),
            ("repo", "privacy-scan", "--repo-root", str(REPO_ROOT)),
            ("repo", "docs-sanity", "--repo-root", str(REPO_ROOT)),
            ("repo", "status", "--repo-root", str(REPO_ROOT)),
            ("repo", "skills", "check", "--repo-root", str(REPO_ROOT)),
            ("repo", "skills", "list", "--repo-root", str(REPO_ROOT)),
            ("repo", "skills", "sync", "--repo-root", str(REPO_ROOT)),
            ("onepanel", "--env", "wsl", "--json"),
        ]
        for args in cases:
            with self.subTest(args=args):
                result = run_cli(*args)
                self.assertEqual(result.returncode, 0, msg=result.stderr)
                payload = json.loads(result.stdout)
                self.assertIsInstance(payload, dict)
                self.assertIn("command", payload)

    def test_repo_status_summarizes_control_plane_state(self) -> None:
        result = run_cli("repo", "status", "--repo-root", str(REPO_ROOT))

        self.assertEqual(result.returncode, 0, msg=result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual("repo", payload["command"])
        self.assertEqual("status", payload["action"])
        self.assertIn("summary", payload)
        self.assertIn("checks", payload)
        self.assertIn("skills", payload["checks"])
        self.assertIn("apps", payload)
        self.assertIn("targets", payload)
        self.assertGreaterEqual(payload["summary"]["public_skills"], 1)
        self.assertIsNone(payload["dashboard"]["html"])

    def test_repo_status_writes_static_html_dashboard(self) -> None:
        with tempfile.TemporaryDirectory(prefix="agentplane-status-") as tmp:
            output = Path(tmp) / "status.html"
            result = run_cli("repo", "status", "--repo-root", str(REPO_ROOT), "--html", str(output))
            html_text = output.read_text(encoding="utf-8")

        self.assertEqual(result.returncode, 0, msg=result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(str(output), payload["dashboard"]["html"])
        self.assertIn("<!doctype html>", html_text)
        self.assertIn("AgentPlane Status", html_text)
        self.assertIn("Public Skills", html_text)
        self.assertIn("Targets", html_text)

    def test_repo_skills_check_validates_public_skill_surface(self) -> None:
        result = run_cli("repo", "skills", "check", "--repo-root", str(REPO_ROOT))

        self.assertEqual(result.returncode, 0, msg=result.stderr)
        payload = json.loads(result.stdout)
        self.assertTrue(payload["ok"])
        self.assertEqual("skills.check", payload["action"])
        self.assertEqual([], payload["issues"])

    def test_repo_skills_list_and_export_report_catalog_entries(self) -> None:
        list_result = run_cli("repo", "skills", "list", "--repo-root", str(REPO_ROOT))
        self.assertEqual(list_result.returncode, 0, msg=list_result.stderr)
        list_payload = json.loads(list_result.stdout)
        names = {skill["name"] for skill in list_payload["skills"]}

        self.assertIn("agentplane-infra-ops", names)
        self.assertIn("app-delivery-ops", names)
        self.assertTrue(all(skill["exists"] for skill in list_payload["skills"]))

        with tempfile.TemporaryDirectory(prefix="agentplane-skills-export-") as tmp:
            output = Path(tmp) / "skills.json"
            export_result = run_cli(
                "repo",
                "skills",
                "export",
                "--repo-root",
                str(REPO_ROOT),
                "--output",
                str(output),
            )
            self.assertEqual(export_result.returncode, 0, msg=export_result.stderr)
            export_payload = json.loads(export_result.stdout)
            written = json.loads(output.read_text(encoding="utf-8"))

        self.assertEqual("skills.export", export_payload["action"])
        self.assertEqual(2, export_payload["payload"]["version"])
        self.assertEqual(export_payload["payload"], written)

    def test_repo_skills_sync_is_dry_run_report(self) -> None:
        result = run_cli("repo", "skills", "sync", "--repo-root", str(REPO_ROOT))

        self.assertEqual(result.returncode, 0, msg=result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual("skills.sync", payload["action"])
        self.assertTrue(payload["ok"])
        self.assertFalse(payload["would_write"])
        self.assertEqual([], payload["catalog_only"])
        self.assertEqual([], payload["tracked_only"])

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

    def test_infra_cleanup_apply_emits_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".playwright-cli").mkdir(parents=True)
            result = run_cli("infra", "cleanup", "apply", "wsl", "--repo-root", str(root), cwd=REPO_ROOT)
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual("infra", payload.get("command"))
            self.assertEqual("cleanup.apply", payload.get("action"))
            self.assertEqual("wsl", payload.get("target"))
            self.assertIn("removed", payload["payload"])

    def test_infra_automation_search_emits_json(self) -> None:
        result = run_cli("infra", "automation", "search", "wsl", "--repo-root", str(REPO_ROOT), cwd=REPO_ROOT)

        self.assertEqual(result.returncode, 0, msg=result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual("infra", payload.get("command"))
        self.assertEqual("automation.search", payload.get("action"))
        self.assertEqual("wsl", payload.get("target"))
        self.assertIn("items", payload["payload"])

    def test_infra_automation_help_lists_formal_targets(self) -> None:
        result = run_cli("infra", "automation", "search", "--help")

        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertTrue({"wsl", "prod0-main", "prod2-main"}.issubset(_listed_targets(result.stdout)))

    def test_top_level_automation_entry_is_removed(self) -> None:
        result = run_cli("automation", "--help")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("invalid choice", result.stderr)

    def test_infra_live_gate_run_without_execute_is_plan_only(self) -> None:
        result = run_cli(
            "infra",
            "live-gate",
            "run",
            "--profile",
            "wsl",
            "--repo-root",
            str(REPO_ROOT),
        )

        self.assertEqual(result.returncode, 0, msg=result.stderr)
        payload = json.loads(result.stdout)
        self.assertFalse(payload["payload"]["executed"])
        self.assertEqual("single-checkout", payload["payload"]["required_checkout"])

# ======================================================================
# From: test_repo_health_cli.py
# ======================================================================

class RepoHealthCliTests(unittest.TestCase):
    def test_repo_health_check_can_run_lightweight_checks(self) -> None:
        result = run_cli(
            "repo",
            "health-check",
            "--repo-root",
            str(REPO_ROOT),
            "--skip-ruff",
            "--skip-tests",
        )

        self.assertEqual(0, result.returncode, msg=result.stderr)
        payload = json.loads(result.stdout)
        self.assertTrue(payload["ok"])
        self.assertEqual(
            ["cli-help", "secret-scan", "privacy-scan", "docs-sanity", "skills-check"],
            [check["name"] for check in payload["checks"]],
        )

    def test_docs_sanity_reports_retired_entrypoints(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "docs").mkdir()
            (root / "docs" / "bad.md").write_text("Use `agentplane host audit`.\n", encoding="utf-8")

            result = run_cli("repo", "docs-sanity", "--repo-root", str(root))

        self.assertEqual(1, result.returncode)
        payload = json.loads(result.stdout)
        self.assertFalse(payload["ok"])
        self.assertEqual("retired-host-entrypoint", payload["issues"][0]["kind"])

    def test_docs_sanity_reports_isolated_active_docs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "README.md").write_text("# Entry\n", encoding="utf-8")
            (root / "docs").mkdir()
            (root / "docs" / "orphan.md").write_text("# Orphan\n", encoding="utf-8")

            result = run_cli("repo", "docs-sanity", "--repo-root", str(root))

        self.assertEqual(1, result.returncode)
        payload = json.loads(result.stdout)
        self.assertFalse(payload["ok"])
        self.assertEqual("isolated-active-doc", payload["issues"][0]["kind"])
        self.assertEqual("docs/orphan.md", payload["issues"][0]["path"])

    def test_docs_sanity_accepts_docs_linked_from_documentation_map(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "README.md").write_text("[Docs](docs/README.md)\n", encoding="utf-8")
            (root / "docs").mkdir()
            (root / "docs" / "README.md").write_text("[Guide](guide.md)\n", encoding="utf-8")
            (root / "docs" / "guide.md").write_text("[Docs](README.md)\n", encoding="utf-8")

            result = run_cli("repo", "docs-sanity", "--repo-root", str(root))

        self.assertEqual(0, result.returncode, msg=result.stderr)
        payload = json.loads(result.stdout)
        self.assertTrue(payload["ok"])

    def test_docs_sanity_reports_missing_frontmatter(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "README.md").write_text("# Entry\n", encoding="utf-8")
            (root / "docs").mkdir()
            (root / "docs" / "reference").mkdir()
            (root / "docs" / "reference" / "spec.md").write_text(
                "# Spec\n\nSome content without frontmatter.\n", encoding="utf-8"
            )

            result = run_cli("repo", "docs-sanity", "--repo-root", str(root))

        self.assertEqual(1, result.returncode)
        payload = json.loads(result.stdout)
        self.assertFalse(payload["ok"])
        kinds = [i["kind"] for i in payload["issues"]]
        self.assertIn("missing-frontmatter", kinds)

    def test_docs_sanity_warns_on_readme_length(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "README.md").write_text("\n".join([f"Line {i}" for i in range(250)]), encoding="utf-8")
            (root / "docs").mkdir()

            result = run_cli("repo", "docs-sanity", "--repo-root", str(root))

        payload = json.loads(result.stdout)
        # Warning should not cause failure
        self.assertTrue(payload["ok"])
        kinds = [i["kind"] for i in payload["issues"]]
        self.assertIn("readme-too-long", kinds)

    def test_docs_sanity_warns_on_missing_conclusion(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "README.md").write_text("[Docs](docs/README.md)\n", encoding="utf-8")
            (root / "docs").mkdir()
            (root / "docs" / "README.md").write_text("[Spec](reference/spec.md)\n", encoding="utf-8")
            (root / "docs" / "reference").mkdir()
            (root / "docs" / "reference" / "spec.md").write_text(
                "---\nstatus: active\nowner: test\nlast_verified: 2026-04-25\nsuperseded_by: null\naudience: agent\n---\n\n# Spec\n\nNo conclusion here.\n",
                encoding="utf-8",
            )

            result = run_cli("repo", "docs-sanity", "--repo-root", str(root))

        payload = json.loads(result.stdout)
        # Missing conclusion is a warning, not an error
        self.assertTrue(payload["ok"])
        kinds = [i["kind"] for i in payload["issues"]]
        self.assertIn("missing-conclusion", kinds)

    def test_docs_sanity_reports_broken_image_references(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "README.md").write_text("# Entry\n![missing](docs/assets/missing.png)\n", encoding="utf-8")
            (root / "docs").mkdir()

            result = run_cli("repo", "docs-sanity", "--repo-root", str(root))

        self.assertEqual(1, result.returncode)
        payload = json.loads(result.stdout)
        self.assertFalse(payload["ok"])
        kinds = [i["kind"] for i in payload["issues"]]
        self.assertIn("broken-image-reference", kinds)

    def test_docs_sanity_reports_archive_doc_active(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "README.md").write_text("# Entry\n", encoding="utf-8")
            (root / "docs").mkdir()
            (root / "docs" / "archive").mkdir()
            (root / "docs" / "archive" / "old.md").write_text(
                "---\nstatus: active\nowner: test\nlast_verified: 2026-04-25\nsuperseded_by: null\naudience: agent\n---\n\n# Old\n结论： archived.\n",
                encoding="utf-8",
            )

            result = run_cli("repo", "docs-sanity", "--repo-root", str(root))

        self.assertEqual(1, result.returncode)
        payload = json.loads(result.stdout)
        self.assertFalse(payload["ok"])
        kinds = [i["kind"] for i in payload["issues"]]
        self.assertIn("archive-doc-active", kinds)

    def test_secret_scan_reports_git_visible_secret_material(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subprocess.run(["git", "init"], cwd=root, text=True, capture_output=True, check=True)
            token = "sk-" + "thisvalueislongenoughtolooksecret"
            (root / "app.env").write_text(f"OPENAI_API_KEY={token}\n", encoding="utf-8")

            result = run_cli("repo", "secret-scan", "--repo-root", str(root))

        self.assertEqual(1, result.returncode)
        payload = json.loads(result.stdout)
        self.assertFalse(payload["ok"])
        self.assertEqual("app.env", payload["issues"][0]["path"])

    def test_secret_scan_allowlist_suppresses_explicit_exception(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subprocess.run(["git", "init"], cwd=root, text=True, capture_output=True, check=True)
            token = "sk-" + "thisvalueislongenoughtolooksecret"
            (root / "app.env").write_text(f"OPENAI_API_KEY={token}\n", encoding="utf-8")
            (root / ".secret-scan-allowlist").write_text("openai-token app.env 1\n", encoding="utf-8")

            result = run_cli("repo", "secret-scan", "--repo-root", str(root))

        self.assertEqual(0, result.returncode, msg=result.stderr)
        payload = json.loads(result.stdout)
        self.assertTrue(payload["ok"])

    def test_privacy_scan_reports_private_public_endpoint_material(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subprocess.run(["git", "init"], cwd=root, text=True, capture_output=True, check=True)
            private_domain = "token." + "zzzai" + ".cloud"
            (root / "README.md").write_text(f"Production endpoint: https://{private_domain}\n", encoding="utf-8")

            result = run_cli("repo", "privacy-scan", "--repo-root", str(root))

        self.assertEqual(1, result.returncode)
        payload = json.loads(result.stdout)
        self.assertFalse(payload["ok"])
        self.assertEqual("private-domain", payload["issues"][0]["kind"])

    def test_privacy_scan_reports_tracked_private_inventory_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subprocess.run(["git", "init"], cwd=root, text=True, capture_output=True, check=True)
            inventory = root / "inventory" / "servers" / "prod0-main" / "inventory.json"
            inventory.parent.mkdir(parents=True)
            inventory.write_text("{}\n", encoding="utf-8")

            result = run_cli("repo", "privacy-scan", "--repo-root", str(root))

        self.assertEqual(1, result.returncode)
        payload = json.loads(result.stdout)
        self.assertFalse(payload["ok"])
        self.assertEqual("private-inventory", payload["issues"][0]["kind"])

    def test_release_check_reports_dirty_worktree(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subprocess.run(["git", "init"], cwd=root, text=True, capture_output=True, check=True)
            (root / "README.md").write_text("dirty\n", encoding="utf-8")

            result = run_cli(
                "repo",
                "release-check",
                "--repo-root",
                str(root),
            )

        self.assertEqual(1, result.returncode)
        payload = json.loads(result.stdout)
        git_check = next(check for check in payload["checks"] if check["name"] == "git-clean")
        self.assertFalse(git_check["ok"])

# ======================================================================
# From: test_bootstrap_cli.py
# ======================================================================

def seed_bootstrap_templates(root: Path) -> None:
    (root / "templates" / "env").mkdir(parents=True, exist_ok=True)
    (root / "templates" / "ssh").mkdir(parents=True, exist_ok=True)
    (root / "templates" / "services").mkdir(parents=True, exist_ok=True)
    (root / "templates" / "secrets" / "local" / "control-plane").mkdir(parents=True, exist_ok=True)
    (root / "templates" / "secrets" / "targets" / "_template").mkdir(parents=True, exist_ok=True)
    (root / "inventory" / "servers" / "wsl").mkdir(parents=True, exist_ok=True)
    (root / "inventory" / "servers" / "prod0-main").mkdir(parents=True, exist_ok=True)
    (root / "inventory" / "servers" / "prod2-main").mkdir(parents=True, exist_ok=True)

    (root / "templates" / "env" / "prod-jump.env.example").write_text(
        "CLOUDFLARE_API_TOKEN=replace-with-api-token\n",
        encoding="utf-8",
    )
    (root / "templates" / "ssh" / "config.example").write_text(
        "Host prod0-main\n  HostName REPLACE_WITH_PRIMARY_IP\n",
        encoding="utf-8",
    )
    (root / "templates" / "services" / "onepanel-login.env.example").write_text(
        "ONEPANEL_USERNAME=replace-with-onepanel-username\n"
        "ONEPANEL_PASSWORD=replace-with-onepanel-password\n",
        encoding="utf-8",
    )
    (root / "templates" / "secrets" / "local" / "control-plane" / "README.md").write_text(
        "local control-plane\n",
        encoding="utf-8",
    )
    (root / "templates" / "secrets" / "targets" / "_template" / "README.md").write_text(
        "target <target>\n",
        encoding="utf-8",
    )
    for target in ("wsl", "prod0-main", "prod2-main"):
        (root / "inventory" / "servers" / target / "inventory.json").write_text(
            json.dumps({"target": target}, ensure_ascii=False),
            encoding="utf-8",
        )

def write_takeover_ready_ssh_contract(root: Path) -> None:
    (root / "secrets" / "ssh" / "keys").mkdir(parents=True, exist_ok=True)
    (root / "secrets" / "ssh" / "config").write_text(
        "Host prod0-main 1.2.3.4\n"
        "  HostName 1.2.3.4\n"
        "  User root\n"
        "  IdentityFile <repo-root>/secrets/ssh/keys/prod0-main.pem\n"
        "\n"
        "Host prod2-main 5.6.7.8\n"
        "  HostName 5.6.7.8\n"
        "  User root\n"
        "  IdentityFile <repo-root>/secrets/ssh/keys/prod2-main.pem\n",
        encoding="utf-8",
    )
    (root / "secrets" / "ssh" / "keys" / "prod0-main.pem").write_text("demo-prod0", encoding="utf-8")
    (root / "secrets" / "ssh" / "keys" / "prod2-main.pem").write_text("demo-prod2", encoding="utf-8")

class BootstrapCliTests(unittest.TestCase):
    def test_bootstrap_init_secrets_creates_only_takeover_truth_scaffold(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            seed_bootstrap_templates(root)

            result = run_cli("bootstrap", "init-secrets", "--repo-root", str(root))

            self.assertEqual(0, result.returncode, msg=result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual("bootstrap", payload["command"])
            self.assertEqual("init-secrets", payload["action"])
            self.assertTrue((root / "secrets" / "local" / "control-plane").is_dir())
            self.assertTrue((root / "secrets" / "targets" / "wsl").is_dir())
            self.assertTrue((root / "secrets" / "targets" / "prod0-main").is_dir())
            self.assertTrue((root / "secrets" / "targets" / "prod2-main").is_dir())
            self.assertTrue((root / "secrets" / "ssh" / "config").is_file())
            self.assertTrue((root / "secrets" / "ssh" / "keys").is_dir())
            self.assertFalse((root / "secrets" / "env" / "prod-jump.env").exists())
            self.assertFalse((root / "secrets" / "services" / "onepanel-login.prod0-main.env").exists())

    def test_bootstrap_verify_secrets_does_not_print_secret_values(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            seed_bootstrap_templates(root)
            write_takeover_ready_ssh_contract(root)

            result = run_cli("bootstrap", "verify-secrets", "--repo-root", str(root))

            self.assertEqual(0, result.returncode, msg=result.stderr)
            payload = json.loads(result.stdout)
            self.assertTrue(payload["payload"]["ok"])

    def test_bootstrap_inspect_local_reports_host_profile_and_path_policy(self) -> None:
        result = run_cli("bootstrap", "inspect-local", "--repo-root", str(REPO_ROOT))

        self.assertEqual(0, result.returncode, msg=result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual("bootstrap", payload["command"])
        self.assertEqual("inspect-local", payload["action"])
        self.assertEqual("canonical-ref-only", payload["payload"]["path_policy"]["truth"])
        self.assertIn("host_profile", payload["payload"])
        self.assertIn("required_truths", payload["payload"]["contract"])
        self.assertIn("projection_only", payload["payload"]["contract"])
        cli_entrypoint = payload["payload"]["cli_entrypoint"]
        self.assertEqual("agentplane", cli_entrypoint["command"])
        self.assertIn("uv run python -m agentplane.cli", cli_entrypoint["fallback_commands"])
        self.assertIn("uv tool install -e", cli_entrypoint["install_command"])

    def test_bootstrap_verify_secrets_requires_structured_ssh_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            seed_bootstrap_templates(root)
            (root / "secrets" / "ssh").mkdir(parents=True, exist_ok=True)
            (root / "secrets" / "ssh" / "config").write_text(
                "Host prod0-main\n"
                "  HostName 1.2.3.4\n"
                "  User root\n"
                "  IdentityFile <repo-root>/secrets/ssh/keys/prod0-main.pem\n",
                encoding="utf-8",
            )

            result = run_cli("bootstrap", "verify-secrets", "--repo-root", str(root))

            self.assertEqual(1, result.returncode, msg=result.stderr)
            payload = json.loads(result.stdout)
            self.assertFalse(payload["payload"]["ok"])
            issues = payload["payload"]["checks"][0]["issues"]
            self.assertIn("missing-ssh-host:prod2-main", issues)
            self.assertIn("missing-ssh-key:prod0-main.pem", issues)

    def test_bootstrap_doctor_reports_projection_warnings_without_blocking_takeover(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            seed_bootstrap_templates(root)
            write_takeover_ready_ssh_contract(root)
            (root / "secrets" / "env").mkdir(parents=True, exist_ok=True)
            (root / "secrets" / "env" / "prod-jump.env").write_text(
                "export PROJECT_SSH_CONFIG=<repo-root>/secrets/ssh/config\n",
                encoding="utf-8",
            )

            doctor = run_cli("bootstrap", "doctor", "--repo-root", str(root))

            self.assertEqual(0, doctor.returncode, msg=doctor.stderr)
            payload = json.loads(doctor.stdout)
            self.assertTrue(payload["payload"]["ok"])
            self.assertTrue(payload["payload"]["secrets"]["ok"])
            self.assertFalse(payload["payload"]["projections"]["ok"])
            readiness = {check["name"]: check for check in payload["payload"]["readiness_checks"]}
            self.assertEqual("warning", readiness["projection-compat"]["severity"])
            self.assertEqual("warning", readiness["global-cli-entrypoint"]["severity"])

# ======================================================================
# From: test_zzz_skills_sync.py
# ======================================================================

REPO_ROOT = Path(__file__).resolve().parents[2]

def git(command: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *command],
        cwd=cwd,
        text=True,
        capture_output=True,
        check=False,
    )

def init_git_repo(path: Path) -> None:
    result = git(["init", "--initial-branch=main"], cwd=path)
    if result.returncode != 0:
        raise AssertionError(result.stderr)
    for key, value in (("user.name", "Test User"), ("user.email", "test@example.com")):
        configured = git(["config", key, value], cwd=path)
        if configured.returncode != 0:
            raise AssertionError(configured.stderr)

def init_target_repo(path: Path, remote_path: Path) -> None:
    remote_created = git(["init", "--bare", str(remote_path)], cwd=path.parent)
    if remote_created.returncode != 0:
        raise AssertionError(remote_created.stderr)

    init_git_repo(path)
    added = git(["remote", "add", "origin", str(remote_path)], cwd=path)
    if added.returncode != 0:
        raise AssertionError(added.stderr)
    (path / ".gitignore").write_text("__pycache__/\n", encoding="utf-8")
    committed = git(["add", ".gitignore"], cwd=path)
    if committed.returncode != 0:
        raise AssertionError(committed.stderr)
    committed = git(["commit", "-m", "chore: init"], cwd=path)
    if committed.returncode != 0:
        raise AssertionError(committed.stderr)
    pushed = git(["push", "-u", "origin", "main"], cwd=path)
    if pushed.returncode != 0:
        raise AssertionError(pushed.stderr)

class ZzzSkillsSyncTests(unittest.TestCase):
    def test_sync_reports_no_changes_when_target_matches_source(self) -> None:
        from agentplane.scripts.automation.sync_zzz_skills import run_sync

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source_root = root / "source"
            target_repo = root / "target"
            remote_repo = root / "remote.git"
            source_root.mkdir(parents=True)
            target_repo.mkdir(parents=True)
            init_target_repo(target_repo, remote_repo)

            skill_dir = source_root / "zzz-alpha"
            skill_dir.mkdir()
            (skill_dir / "SKILL.md").write_text("alpha\n", encoding="utf-8")
            mirrored = target_repo / "zzz-alpha"
            mirrored.mkdir()
            (mirrored / "SKILL.md").write_text("alpha\n", encoding="utf-8")
            git(["add", "zzz-alpha/SKILL.md"], cwd=target_repo)
            git(["commit", "-m", "chore: seed"], cwd=target_repo)
            git(["push", "origin", "main"], cwd=target_repo)

            payload = run_sync(source_root=source_root, target_repo=target_repo)

            self.assertEqual("ok_no_changes", payload["status"])
            self.assertEqual(["zzz-alpha"], payload["skills"])

    def test_sync_removes_stale_zzz_directories(self) -> None:
        from agentplane.scripts.automation.sync_zzz_skills import run_sync

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source_root = root / "source"
            target_repo = root / "target"
            remote_repo = root / "remote.git"
            source_root.mkdir(parents=True)
            target_repo.mkdir(parents=True)
            init_target_repo(target_repo, remote_repo)

            skill_dir = source_root / "zzz-alpha"
            skill_dir.mkdir()
            (skill_dir / "SKILL.md").write_text("alpha\n", encoding="utf-8")
            stale_dir = target_repo / "zzz-stale"
            stale_dir.mkdir()
            (stale_dir / "SKILL.md").write_text("stale\n", encoding="utf-8")
            git(["add", "zzz-stale/SKILL.md"], cwd=target_repo)
            git(["commit", "-m", "chore: add stale"], cwd=target_repo)
            git(["push", "origin", "main"], cwd=target_repo)

            payload = run_sync(source_root=source_root, target_repo=target_repo)

            self.assertEqual("ok_pushed", payload["status"])
            self.assertFalse(stale_dir.exists())
            self.assertTrue((target_repo / "zzz-alpha" / "SKILL.md").exists())

    def test_sync_rejects_dirty_git_worktree(self) -> None:
        from agentplane.scripts.automation.sync_zzz_skills import run_sync

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source_root = root / "source"
            target_repo = root / "target"
            remote_repo = root / "remote.git"
            source_root.mkdir(parents=True)
            target_repo.mkdir(parents=True)
            init_target_repo(target_repo, remote_repo)

            skill_dir = source_root / "zzz-alpha"
            skill_dir.mkdir()
            (skill_dir / "SKILL.md").write_text("alpha\n", encoding="utf-8")
            (target_repo / "README.md").write_text("dirty\n", encoding="utf-8")

            payload = run_sync(source_root=source_root, target_repo=target_repo)

            self.assertEqual("failed_precheck", payload["status"])
            self.assertIn("dirty", payload["reason"])

    def test_sync_rejects_unknown_root_files_outside_allowlist(self) -> None:
        from agentplane.scripts.automation.sync_zzz_skills import run_sync

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source_root = root / "source"
            target_repo = root / "target"
            remote_repo = root / "remote.git"
            source_root.mkdir(parents=True)
            target_repo.mkdir(parents=True)
            init_target_repo(target_repo, remote_repo)

            skill_dir = source_root / "zzz-alpha"
            skill_dir.mkdir()
            (skill_dir / "SKILL.md").write_text("alpha\n", encoding="utf-8")
            (target_repo / "EXTRA.md").write_text("unexpected\n", encoding="utf-8")
            git(["add", "EXTRA.md"], cwd=target_repo)
            git(["commit", "-m", "chore: add extra"], cwd=target_repo)
            git(["push", "origin", "main"], cwd=target_repo)

            payload = run_sync(source_root=source_root, target_repo=target_repo)

            self.assertEqual("failed_precheck", payload["status"])
            self.assertIn("EXTRA.md", payload["reason"])
