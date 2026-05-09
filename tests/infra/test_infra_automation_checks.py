from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from agentplane.cli import infra_automation
from agentplane.cli.preflight import (
    PreflightCheck,
    PreflightReport,
    execute_remote_preflight,
)
from agentplane.domain.infra.automation import AUTOMATION_DEFINITIONS, InfraAutomationDefinition
from agentplane.domain.infra.preflight import (
    _check_ssh_config_exists,
    _check_ssh_key_permissions,
    _check_ssh_reachable,
    _check_wsl_available,
)

pytestmark = pytest.mark.e2e
def write_inventory(root: Path) -> None:
    inventory_file = root / "inventory" / "servers" / "wsl" / "inventory.json"
    inventory_file.parent.mkdir(parents=True, exist_ok=True)
    inventory_file.write_text(
        json.dumps(
            {
                "automations": [
                    {
                        "name": "wsl-zzz-skills-sync",
                        "controller": "1panel-cronjob",
                        "spec": "0 */2 * * *",
                        "cwd": "<repo-root>",
                        "command": "uv run python -m agentplane.cli infra automation apply wsl --name wsl-zzz-skills-sync --operation run --execute",
                        "source_root": "external/codex-skills",
                        "target_repo": "external/zzz-skills",
                        "target_branch": "main",
                    },
                    {
                        "name": "wsl-agentplane-secrets-backup",
                        "controller": "1panel-cronjob",
                        "spec": "0 */5 * * *",
                        "cwd": "<repo-root>",
                        "command": "uv run python -m agentplane.cli infra automation apply wsl --name wsl-agentplane-secrets-backup --operation run --execute",
                        "env_file": "secrets/services/secrets-backup.r2.wsl.env",
                    },
                ]
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )




class FakeExecutor:
    def __init__(self, cronjobs: list[dict[str, object]] | None = None) -> None:
        self.cronjobs = [dict(item) for item in (cronjobs or [])]
        self.calls: list[tuple[str, str, dict[str, object] | None]] = []
        self.handled_ids: list[int] = []

    def api_request(self, method: str, path: str, body: dict[str, object] | None = None) -> object:
        self.calls.append((method, path, body))
        if path == "/api/v2/cronjobs/search":
            assert body is not None
            info = str(body.get("info", ""))
            items = [item for item in self.cronjobs if not info or info in str(item.get("name", ""))]
            return {"items": items}
        if path == "/api/v2/cronjobs/load/info":
            assert body is not None
            cronjob_id = int(body["id"])
            for item in self.cronjobs:
                if int(item["id"]) == cronjob_id:
                    return dict(item)
            raise RuntimeError("cronjob not found")
        if path == "/api/v2/cronjobs":
            assert body is not None
            created = dict(body)
            created["id"] = max((int(item["id"]) for item in self.cronjobs), default=0) + 1
            created.setdefault("status", "Enable")
            self.cronjobs.append(created)
            return {"id": created["id"]}
        if path == "/api/v2/cronjobs/update":
            assert body is not None
            cronjob_id = int(body["id"])
            for item in self.cronjobs:
                if int(item["id"]) == cronjob_id:
                    item.update(body)
                    return {"id": cronjob_id}
            raise RuntimeError("cronjob not found")
        if path == "/api/v2/cronjobs/status":
            assert body is not None
            cronjob_id = int(body["id"])
            for item in self.cronjobs:
                if int(item["id"]) == cronjob_id:
                    item["status"] = body["status"]
                    return {"id": cronjob_id}
            raise RuntimeError("cronjob not found")
        if path == "/api/v2/cronjobs/handle":
            assert body is not None
            cronjob_id = int(body["id"])
            self.handled_ids.append(cronjob_id)
            return {"id": cronjob_id}
        raise AssertionError(f"unexpected path: {path}")


class InfraAutomationTests(unittest.TestCase):
    def test_search_rejects_unknown_target(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root)

            with self.assertRaisesRegex(ValueError, "unsupported automation target"):
                infra_automation.search_infra_automations(root, "prod9-unknown")

    def test_search_reads_inventory_automation_truth(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root)

            payload = infra_automation.search_infra_automations(root, "wsl")

            self.assertEqual(2, len(payload["items"]))
            self.assertEqual("wsl-zzz-skills-sync", payload["items"][0]["name"])
            self.assertIn("reconcile", payload["items"][0]["supported_operations"])
            self.assertIn("run", payload["items"][0]["supported_operations"])
            self.assertIn("trigger", payload["items"][0]["supported_operations"])

    def test_plan_reconcile_creates_formal_cronjob_script(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root)

            payload = infra_automation.plan_infra_automation(
                root,
                "wsl",
                "wsl-zzz-skills-sync",
                "reconcile",
                executor=FakeExecutor(),
            )

            self.assertTrue(payload["ok"])
            self.assertEqual("create", payload["actions"][0]["mode"])
            self.assertIn(
                "infra automation apply wsl --name wsl-zzz-skills-sync --operation run --execute",
                payload["actions"][0]["body"]["script"],
            )

    def test_verify_detects_legacy_cronjob_script_drift(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root)
            executor = FakeExecutor(
                [
                    {
                        "id": 1,
                        "name": "wsl-agentplane-secrets-backup",
                        "groupID": 0,
                        "spec": "0 */5 * * *",
                        "executor": "bash",
                        "scriptMode": "input",
                        "script": "cd <repo-root> && uv run python -m agentplane.cli automation backup-secrets-r2",
                        "type": "shell",
                        "user": "root",
                        "status": "Enable",
                    }
                ]
            )

            payload = infra_automation.verify_infra_automation(
                root,
                "wsl",
                "wsl-agentplane-secrets-backup",
                executor=executor,
            )

            self.assertFalse(payload["ok"])
            self.assertTrue(payload["checks"]["spec_match"])
            self.assertFalse(payload["checks"]["script_match"])

    def test_apply_reconcile_updates_drifted_cronjob(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root)
            executor = FakeExecutor(
                [
                    {
                        "id": 2,
                        "name": "wsl-agentplane-secrets-backup",
                        "groupID": 0,
                        "spec": "0 */5 * * *",
                        "executor": "bash",
                        "scriptMode": "input",
                        "script": "cd <repo-root> && uv run python -m agentplane.cli automation backup-secrets-r2",
                        "type": "shell",
                        "user": "root",
                        "status": "Disable",
                    }
                ]
            )

            payload = infra_automation.apply_infra_automation(
                root,
                "wsl",
                "wsl-agentplane-secrets-backup",
                "reconcile",
                execute=True,
                executor=executor,
            )

            self.assertTrue(payload["ok"])
            self.assertEqual(["update", "status"], [item["mode"] for item in payload["results"]])
            self.assertEqual("Enable", executor.cronjobs[0]["status"])
            self.assertIn(
                "infra automation apply wsl --name wsl-agentplane-secrets-backup --operation run --execute",
                str(executor.cronjobs[0]["script"]),
            )

    def test_apply_run_dispatches_registered_runner(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root)
            original = AUTOMATION_DEFINITIONS["wsl-zzz-skills-sync"]
            AUTOMATION_DEFINITIONS["wsl-zzz-skills-sync"] = InfraAutomationDefinition(
                name="wsl-zzz-skills-sync",
                runner=lambda repo_root, automation: {
                    "status": "ok_no_changes",
                    "repo_root": str(repo_root),
                    "name": automation["name"],
                },
            )
            try:
                payload = infra_automation.apply_infra_automation(
                    root,
                    "wsl",
                    "wsl-zzz-skills-sync",
                    "run",
                    execute=True,
                )
            finally:
                AUTOMATION_DEFINITIONS["wsl-zzz-skills-sync"] = original

            self.assertTrue(payload["ok"])
            self.assertEqual("run", payload["operation"])
            self.assertEqual("ok_no_changes", payload["result"]["status"])

    def test_plan_trigger_requires_existing_cronjob(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root)

            payload = infra_automation.plan_infra_automation(
                root,
                "wsl",
                "wsl-agentplane-secrets-backup",
                "trigger",
                executor=FakeExecutor(),
            )

            self.assertFalse(payload["ok"])
            self.assertEqual("cronjob missing", payload["reason"])



# ======================================================================
# From: test_preflight.py
# ======================================================================


class TestCheckWslAvailable:
    @patch("agentplane.domain.infra.preflight.subprocess.run")
    def test_wsl_ok(self, mock_run: MagicMock) -> None:
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = "ok\n"
        mock_run.return_value.stderr = ""
        check = _check_wsl_available()
        assert check.status == "ok"
        assert "WSL is running" in check.message

    @patch("agentplane.domain.infra.preflight.subprocess.run")
    def test_wsl_failed(self, mock_run: MagicMock) -> None:
        mock_run.return_value.returncode = 1
        mock_run.return_value.stdout = ""
        mock_run.return_value.stderr = "Error"
        check = _check_wsl_available()
        assert check.status == "failed"

    @patch("agentplane.domain.infra.preflight.subprocess.run", side_effect=FileNotFoundError)
    def test_wsl_not_found(self, _mock: MagicMock) -> None:
        check = _check_wsl_available()
        assert check.status == "failed"
        assert "wsl.exe not found" in check.message



class TestCheckSshConfigExists:
    def test_config_exists(self, tmp_path: pytest.TempPathFactory) -> None:
        config = tmp_path / "ssh" / "config"
        config.parent.mkdir(parents=True)
        config.write_text("Host test\n")
        ssh_target = MagicMock()
        ssh_target.config_path = config
        check = _check_ssh_config_exists(ssh_target)
        assert check.status == "ok"

    def test_config_missing(self, tmp_path: pytest.TempPathFactory) -> None:
        ssh_target = MagicMock()
        ssh_target.config_path = tmp_path / "missing"
        check = _check_ssh_config_exists(ssh_target)
        assert check.status == "failed"



class TestCheckSshKeyPermissions:
    def test_key_with_good_permissions(self, tmp_path: pytest.TempPathFactory) -> None:
        config = tmp_path / "ssh" / "config"
        config.parent.mkdir(parents=True)
        key = tmp_path / "ssh" / "id_rsa"
        key.write_text("secret")
        key.chmod(0o600)
        config.write_text(f"Host test\n  IdentityFile {key}\n")
        ssh_target = MagicMock()
        ssh_target.config_path = config
        ssh_target.alias = "test"
        check = _check_ssh_key_permissions(ssh_target)
        # On Windows chmod does not set Unix permission bits; accept ok or warning
        assert check.status in ("ok", "warning")

    def test_key_with_open_permissions(self, tmp_path: pytest.TempPathFactory) -> None:
        config = tmp_path / "ssh" / "config"
        config.parent.mkdir(parents=True)
        key = tmp_path / "ssh" / "id_rsa"
        key.write_text("secret")
        key.chmod(0o644)
        config.write_text(f"Host test\n  IdentityFile {key}\n")
        ssh_target = MagicMock()
        ssh_target.config_path = config
        ssh_target.alias = "test"
        check = _check_ssh_key_permissions(ssh_target)
        assert check.status == "warning"
        assert "too open" in check.message

    def test_missing_key(self, tmp_path: pytest.TempPathFactory) -> None:
        config = tmp_path / "ssh" / "config"
        config.parent.mkdir(parents=True)
        config.write_text("Host test\n  IdentityFile /nonexistent/key\n")
        ssh_target = MagicMock()
        ssh_target.config_path = config
        ssh_target.alias = "test"
        check = _check_ssh_key_permissions(ssh_target)
        assert check.status == "failed"



class TestCheckSshReachable:
    @patch("agentplane.domain.infra.preflight.subprocess.run")
    def test_ssh_ok(self, mock_run: MagicMock) -> None:
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = "ok\n"
        mock_run.return_value.stderr = ""
        ssh_target = MagicMock()
        ssh_target.local_ssh_args_for_argv.return_value = ["ssh", "test"]
        ssh_target.connection_target = "test"
        check = _check_ssh_reachable(ssh_target)
        assert check.status == "ok"

    @patch("agentplane.domain.infra.preflight.subprocess.run")
    def test_ssh_auth_failure(self, mock_run: MagicMock) -> None:
        mock_run.return_value.returncode = 255
        mock_run.return_value.stdout = ""
        mock_run.return_value.stderr = "Permission denied (publickey)"
        ssh_target = MagicMock()
        ssh_target.local_ssh_args_for_argv.return_value = ["ssh", "test"]
        ssh_target.connection_target = "test"
        check = _check_ssh_reachable(ssh_target)
        assert check.status == "failed"
        assert "authentication failed" in check.message.lower()

    @patch("agentplane.domain.infra.preflight.subprocess.run")
    def test_ssh_network_failure(self, mock_run: MagicMock) -> None:
        mock_run.return_value.returncode = 255
        mock_run.return_value.stdout = ""
        mock_run.return_value.stderr = "ssh: connect to host bad port 22: Connection refused"
        ssh_target = MagicMock()
        ssh_target.local_ssh_args_for_argv.return_value = ["ssh", "bad"]
        ssh_target.connection_target = "bad"
        check = _check_ssh_reachable(ssh_target)
        assert check.status == "failed"
        assert "network failure" in check.message.lower()



class TestExecuteRemotePreflight:
    @patch("agentplane.domain.infra.preflight.detect_host_profile")
    @patch("agentplane.domain.infra.preflight.TargetResolver")
    def test_local_wsl_preflight(self, mock_resolver_cls: MagicMock, mock_detect: MagicMock) -> None:
        mock_detect.return_value = MagicMock()
        mock_resolver = MagicMock()
        mock_resolver.resolve.return_value = MagicMock(is_local=True, execution_backend="windows-wsl")
        mock_resolver_cls.return_value = mock_resolver

        with patch("agentplane.domain.infra.preflight._check_wsl_available", return_value=PreflightCheck("wsl", "ok", "ok")):
            report = execute_remote_preflight("/fake/repo", "wsl")
        assert report.overall == "ok"
        assert report.target == "wsl"

    @patch("agentplane.domain.infra.preflight.detect_host_profile")
    @patch("agentplane.domain.infra.preflight.TargetResolver")
    @patch("agentplane.domain.infra.preflight.resolve_ssh_target")
    def test_remote_preflight(
        self, mock_resolve_ssh: MagicMock, mock_resolver_cls: MagicMock, mock_detect: MagicMock
    ) -> None:
        mock_detect.return_value = MagicMock()
        mock_resolver = MagicMock()
        mock_resolver.resolve.return_value = MagicMock(is_local=False, ssh_alias="prod0-main")
        mock_resolver_cls.return_value = mock_resolver
        ssh_target = MagicMock()
        ssh_target.config_path.exists.return_value = True
        mock_resolve_ssh.return_value = ssh_target

        with patch(
            "agentplane.domain.infra.preflight._check_ssh_config_exists", return_value=PreflightCheck("config", "ok", "ok")
        ):
            with patch(
                "agentplane.domain.infra.preflight._check_ssh_key_permissions", return_value=PreflightCheck("key", "ok", "ok")
            ):
                with patch(
                    "agentplane.domain.infra.preflight._check_ssh_reachable", return_value=PreflightCheck("ssh", "ok", "ok")
                ):
                    report = execute_remote_preflight("/fake/repo", "prod0-main")
        assert report.overall == "ok"

    def test_preflight_report_payload(self) -> None:
        report = PreflightReport(
            target="wsl",
            overall="warning",
            checks=[
                PreflightCheck("a", "ok", "fine"),
                PreflightCheck("b", "warning", "careful"),
            ],
        )
        payload = report.to_payload()
        assert payload["overall"] == "warning"
        assert len(payload["checks"]) == 2
