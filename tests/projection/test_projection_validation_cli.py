import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[2]


class ProjectionValidationCliTests(unittest.TestCase):
    def test_projection_verification_run_wraps_suite_payload(self) -> None:
        from agentplane.cli.projection import handle_projection_command

        args = SimpleNamespace(
            projection_surface="verification",
            projection_verification_action="run",
            target="wsl",
            profile="wsl-fixture",
            repo_root=str(REPO_ROOT),
            write_report=False,
            website_alias="",
            container_name="",
            project_name="",
            cronjob_id=None,
            cronjob_name="",
            app_name="",
            firewall_tab="port",
        )

        with patch("agentplane.cli.projection._executor_for_target", return_value=object()), patch(
            "agentplane.cli.projection.run_onepanel_verification_suite",
            return_value={"ok": True, "checks": []},
        ) as run_suite:
            payload = handle_projection_command(args)

        self.assertEqual("projection", payload["command"])
        self.assertEqual("verification.run", payload["action"])
        self.assertTrue(payload["ok"])
        self.assertEqual("wsl-fixture", run_suite.call_args.kwargs["profile"])
        self.assertEqual("wsl", run_suite.call_args.kwargs["env"])

    def test_projection_verification_run_redacts_sensitive_payload(self) -> None:
        from agentplane.cli.projection import handle_projection_command

        args = SimpleNamespace(
            projection_surface="verification",
            projection_verification_action="run",
            target="wsl",
            profile="wsl-fixture",
            repo_root=str(REPO_ROOT),
            write_report=False,
            website_alias="",
            container_name="",
            project_name="",
            cronjob_id=None,
            cronjob_name="",
            app_name="",
            firewall_tab="port",
        )

        with patch("agentplane.cli.projection._executor_for_target", return_value=object()), patch(
            "agentplane.cli.projection.run_onepanel_verification_suite",
            return_value={"ok": True, "checks": [{"scope": "panel", "ok": True, "payload": {"apiKey": "secret"}}]},
        ):
            payload = handle_projection_command(args)

        self.assertEqual("<redacted>", payload["checks"][0]["payload"]["apiKey"])

    def test_projection_fixture_apply_requires_execute(self) -> None:
        from agentplane.cli.projection import handle_projection_command

        args = SimpleNamespace(
            projection_surface="fixture",
            projection_fixture_action="apply",
            target="wsl",
            profile="wsl-fixture",
            repo_root=str(REPO_ROOT),
            website_alias="",
            container_name="",
            project_name="",
            cronjob_name="",
            firewall_tab="",
            execute=False,
        )

        with self.assertRaisesRegex(ValueError, "--execute"):
            handle_projection_command(args)

    def test_projection_fixture_cleanup_wraps_underlying_payload(self) -> None:
        from agentplane.cli.projection import handle_projection_command

        args = SimpleNamespace(
            projection_surface="fixture",
            projection_fixture_action="cleanup",
            target="wsl",
            profile="wsl-fixture",
            repo_root=str(REPO_ROOT),
            website_alias="",
            container_name="",
            project_name="",
            cronjob_name="",
            firewall_tab="",
            execute=True,
        )

        with patch("agentplane.cli.projection.resolve_fixture_spec", return_value=object()) as resolve_spec, patch(
            "agentplane.cli.projection._executor_for_target",
            return_value=object(),
        ), patch(
            "agentplane.cli.projection.cleanup_fixture",
            return_value={"ok": True, "items": [{"object": "project", "action": "down-project"}]},
        ) as cleanup_fixture:
            payload = handle_projection_command(args)

        resolve_spec.assert_called_once_with(
            "wsl-fixture",
            env="wsl",
            website_alias="",
            container_name="",
            project_name="",
            cronjob_name="",
            firewall_tab="",
        )
        cleanup_fixture.assert_called_once()
        self.assertEqual("projection", payload["command"])
        self.assertEqual("fixture.cleanup", payload["action"])
        self.assertTrue(payload["ok"])

    def test_projection_ledger_refresh_wraps_formal_envelope(self) -> None:
        from agentplane.cli.projection import handle_projection_command

        args = SimpleNamespace(
            projection_surface="ledger",
            projection_ledger_action="refresh",
            target="prod0-main",
            repo_root=str(REPO_ROOT),
            write=True,
        )

        with patch(
            "agentplane.cli.projection.refresh_onepanel_ledgers",
            return_value={"counts": {"websites": 1}, "written": True},
        ) as refresh_ledgers:
            payload = handle_projection_command(args)

        refresh_ledgers.assert_called_once_with(REPO_ROOT.resolve(), "prod0-main", write=True)
        self.assertEqual("projection", payload["command"])
        self.assertEqual("ledger.refresh", payload["action"])
        self.assertEqual({"websites": 1}, payload["counts"])

    def test_repo_self_check_keeps_projection_scenario_workflows_out_of_daily_gate(self) -> None:
        self_check = (REPO_ROOT / "agentplane" / "scripts" / "internal" / "repo" / "self_check.sh").read_text(
            encoding="utf-8"
        )

        self.assertIn("projection verification / fixture / ledger remain scenario-specific workflows", self_check)
        self.assertIn("do not move them into the daily thin gate", self_check)
        self.assertNotIn("tests/test_projection_validation_cli.py", self_check)
        self.assertNotIn("tests/test_projection_runtime_env_cli.py", self_check)
        self.assertNotIn("tests/test_onepanel_fixture_manager.py", self_check)
        self.assertNotIn("tests/test_onepanel_verification_suite.py", self_check)
        self.assertNotIn("projection verification run", self_check)
        self.assertNotIn("projection fixture", self_check)
        self.assertNotIn("projection ledger refresh", self_check)


if __name__ == "__main__":
    unittest.main()

