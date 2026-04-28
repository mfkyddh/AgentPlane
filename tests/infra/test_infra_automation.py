from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from agentplane.cli import infra_automation
from agentplane.cli.audit import audit_filesystem
from agentplane.cli.preflight import (
    PreflightCheck,
    PreflightReport,
    _check_ssh_config_exists,
    _check_ssh_key_permissions,
    _check_ssh_reachable,
    _check_wsl_available,
    execute_remote_preflight,
)
from agentplane.runtime.host_profile import HostProfile
from agentplane.ssh import SshTarget, resolve_ssh_config_path, resolve_ssh_target

pytestmark = pytest.mark.e2e

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
            self.assertIn("infra automation apply wsl --name wsl-zzz-skills-sync --operation run --execute", payload["actions"][0]["body"]["script"])

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
            original = infra_automation.AUTOMATION_DEFINITIONS["wsl-zzz-skills-sync"]
            infra_automation.AUTOMATION_DEFINITIONS["wsl-zzz-skills-sync"] = infra_automation.InfraAutomationDefinition(
                name="wsl-zzz-skills-sync",
                runner=lambda repo_root, automation: {"status": "ok_no_changes", "repo_root": str(repo_root), "name": automation["name"]},
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
                infra_automation.AUTOMATION_DEFINITIONS["wsl-zzz-skills-sync"] = original

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
    @patch("agentplane.cli.preflight.subprocess.run")
    def test_wsl_ok(self, mock_run: MagicMock) -> None:
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = "ok\n"
        mock_run.return_value.stderr = ""
        check = _check_wsl_available()
        assert check.status == "ok"
        assert "WSL is running" in check.message

    @patch("agentplane.cli.preflight.subprocess.run")
    def test_wsl_failed(self, mock_run: MagicMock) -> None:
        mock_run.return_value.returncode = 1
        mock_run.return_value.stdout = ""
        mock_run.return_value.stderr = "Error"
        check = _check_wsl_available()
        assert check.status == "failed"

    @patch("agentplane.cli.preflight.subprocess.run", side_effect=FileNotFoundError)
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
    @patch("agentplane.cli.preflight.subprocess.run")
    def test_ssh_ok(self, mock_run: MagicMock) -> None:
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = "ok\n"
        mock_run.return_value.stderr = ""
        ssh_target = MagicMock()
        ssh_target.local_ssh_args_for_argv.return_value = ["ssh", "test"]
        ssh_target.connection_target = "test"
        check = _check_ssh_reachable(ssh_target)
        assert check.status == "ok"

    @patch("agentplane.cli.preflight.subprocess.run")
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

    @patch("agentplane.cli.preflight.subprocess.run")
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
    @patch("agentplane.cli.preflight.detect_host_profile")
    @patch("agentplane.cli.preflight.TargetResolver")
    def test_local_wsl_preflight(self, mock_resolver_cls: MagicMock, mock_detect: MagicMock) -> None:
        mock_detect.return_value = MagicMock()
        mock_resolver = MagicMock()
        mock_resolver.resolve.return_value = MagicMock(is_local=True, execution_backend="windows-wsl")
        mock_resolver_cls.return_value = mock_resolver

        with patch("agentplane.cli.preflight._check_wsl_available", return_value=PreflightCheck("wsl", "ok", "ok")):
            report = execute_remote_preflight("/fake/repo", "wsl")
        assert report.overall == "ok"
        assert report.target == "wsl"

    @patch("agentplane.cli.preflight.detect_host_profile")
    @patch("agentplane.cli.preflight.TargetResolver")
    @patch("agentplane.cli.preflight.resolve_ssh_target")
    def test_remote_preflight(self, mock_resolve_ssh: MagicMock, mock_resolver_cls: MagicMock, mock_detect: MagicMock) -> None:
        mock_detect.return_value = MagicMock()
        mock_resolver = MagicMock()
        mock_resolver.resolve.return_value = MagicMock(is_local=False, ssh_alias="prod0-main")
        mock_resolver_cls.return_value = mock_resolver
        ssh_target = MagicMock()
        ssh_target.config_path.exists.return_value = True
        mock_resolve_ssh.return_value = ssh_target

        with patch("agentplane.cli.preflight._check_ssh_config_exists", return_value=PreflightCheck("config", "ok", "ok")):
            with patch("agentplane.cli.preflight._check_ssh_key_permissions", return_value=PreflightCheck("key", "ok", "ok")):
                with patch("agentplane.cli.preflight._check_ssh_reachable", return_value=PreflightCheck("ssh", "ok", "ok")):
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

# ======================================================================
# From: test_ssh_targets.py
# ======================================================================

class SshTargetTests(unittest.TestCase):
    def test_root_direct_target_renders_root_destination_without_sudo(self) -> None:
        target = SshTarget(
            alias="prod0-main",
            config_path=Path("/tmp/ssh-config"),
            user="root",
            os_family="linux",
            environment="production",
        )

        command = target.display_ssh_command("docker inspect sub2api-prod")

        self.assertIn("root@prod0-main", command)
        self.assertNotIn("sudo ", command)
        self.assertIn("bash -lc", command)

    def test_non_root_linux_target_keeps_sudo_wrapper(self) -> None:
        target = SshTarget(
            alias="example-prod",
            config_path=Path("/tmp/ssh-config"),
            user="ubuntu",
            os_family="linux",
            environment="production",
        )

        command = target.display_ssh_command("docker ps")

        self.assertIn("ubuntu@example-prod", command)
        self.assertIn("sudo bash -lc", command)

    def test_root_target_wraps_remote_bash_stdin_without_sudo(self) -> None:
        target = SshTarget(
            alias="prod0-main",
            config_path=Path("/tmp/ssh-config"),
            user="root",
            os_family="linux",
            environment="production",
        )

        command = target.wrap_bash_stdin(["--flag", "value with spaces"])

        self.assertEqual("bash -s -- --flag 'value with spaces'", command)

    def test_local_ssh_args_route_windows_hosts_through_wsl(self) -> None:
        target = SshTarget(
            alias="prod0-main",
            config_path=Path("D:/Projects/AgentPlane/secrets/ssh/config"),
            user="root",
            os_family="linux",
            environment="production",
        )

        with patch("agentplane.ssh.os.name", "nt"), patch.dict("agentplane.ssh.os.environ", {}, clear=True):
            command = target.local_ssh_args_for_shell("hostname")

        self.assertEqual("wsl.exe", command[0])
        self.assertEqual("-e", command[1])
        self.assertEqual("ssh", command[2])
        self.assertIn("/mnt/d/Projects/AgentPlane/secrets/ssh/config", command)

    def test_non_root_target_wraps_remote_bash_stdin_with_sudo(self) -> None:
        target = SshTarget(
            alias="example-prod",
            config_path=Path("/tmp/ssh-config"),
            user="ubuntu",
            os_family="linux",
            environment="production",
        )

        command = target.wrap_bash_stdin(["check"])

        self.assertEqual("sudo bash -s -- check", command)

    def test_resolve_ssh_target_uses_inventory_user_for_alias(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            prod0 = repo_root / "inventory" / "servers" / "prod0-main" / "inventory.json"
            prod0.parent.mkdir(parents=True, exist_ok=True)
            prod0.write_text(
                json.dumps(
                    {
                        "ssh": {
                            "aliases": ["prod0-main", "zzzai.cloud"],
                            "user": "root",
                        }
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

            target = resolve_ssh_target(repo_root, "zzzai.cloud")

            self.assertEqual("root", target.user)
            self.assertEqual("zzzai.cloud", target.alias)
            self.assertEqual("root@zzzai.cloud", target.connection_target)

    def test_resolve_ssh_target_falls_back_when_alias_not_in_inventory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)

            target = resolve_ssh_target(repo_root, "unknown-host")

            self.assertIsNone(target.user)
            self.assertEqual("unknown-host", target.alias)
            self.assertEqual("unknown-host", target.connection_target)

    def test_resolve_ssh_config_path_uses_main_repo_for_git_worktree(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            main_root = tmp_root / "main"
            worktree_root = tmp_root / "worktree"
            git_worktree_dir = main_root / ".git" / "worktrees" / "demo"
            (main_root / "secrets" / "ssh").mkdir(parents=True, exist_ok=True)
            git_worktree_dir.mkdir(parents=True, exist_ok=True)
            worktree_root.mkdir(parents=True, exist_ok=True)
            (worktree_root / ".git").write_text(f"gitdir: {git_worktree_dir}\n", encoding="utf-8")

            config_path = resolve_ssh_config_path(worktree_root)

            self.assertEqual(main_root / "secrets" / "ssh" / "config", config_path)

    def test_resolve_ssh_target_keeps_worktree_inventory_and_shared_ssh_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            main_root = tmp_root / "main"
            worktree_root = tmp_root / "worktree"
            git_worktree_dir = main_root / ".git" / "worktrees" / "demo"
            inventory_file = worktree_root / "inventory" / "servers" / "prod0-main" / "inventory.json"

            (main_root / "secrets" / "ssh").mkdir(parents=True, exist_ok=True)
            git_worktree_dir.mkdir(parents=True, exist_ok=True)
            inventory_file.parent.mkdir(parents=True, exist_ok=True)
            worktree_root.mkdir(parents=True, exist_ok=True)
            (worktree_root / ".git").write_text(f"gitdir: {git_worktree_dir}\n", encoding="utf-8")
            inventory_file.write_text(
                json.dumps({"ssh": {"aliases": ["prod0-main"], "user": "root"}}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

            target = resolve_ssh_target(worktree_root, "prod0-main")

            self.assertEqual(main_root / "secrets" / "ssh" / "config", target.config_path)
            self.assertEqual("root@prod0-main", target.connection_target)

# ======================================================================
# From: test_wsl_audit.py
# ======================================================================

class WslAuditTests(unittest.TestCase):
    def test_windows_host_uses_backend_exec_for_wsl_path_checks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            class _FakeRunner:
                def __init__(self) -> None:
                    self.plan = None

                def execute(self, plan, *, bindings=None):
                    self.plan = plan
                    return SimpleNamespace(ok=True, stdout="[]", stderr="")

            runner = _FakeRunner()
            result = audit_filesystem(
                root,
                "wsl",
                host_profile=HostProfile(os_name="windows", linux_backend="windows-wsl", supports_docker=True),
                runner=runner,
            )

            self.assertEqual("backend-exec", result["path_check_mode"])
            self.assertEqual("windows-wsl", runner.plan.backend_type)

    def test_detects_legacy_compose_entrypoints_and_env_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            service_dir = root / "infra" / "compose" / "redis"
            service_dir.mkdir(parents=True, exist_ok=True)
            (service_dir / "docker-compose.yml").write_text("services: {}\n", encoding="utf-8")
            (service_dir / ".env").write_text("REDIS_PASSWORD=demo\n", encoding="utf-8")

            result = audit_filesystem(root, "wsl")
            codes = {item["id"] for item in result["violations"]}

            self.assertIn("wsl.legacy.compose_entrypoint", codes)
            self.assertIn("wsl.legacy.env_file", codes)

    def test_detects_compose_scoped_private_env_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            service_dir = root / "infra" / "compose" / "cliproxyapi"
            service_dir.mkdir(parents=True, exist_ok=True)
            (service_dir / "docker-compose.wsl.yml").write_text("services: {}\n", encoding="utf-8")
            (service_dir / "docker-compose.prod0.yml").write_text("services: {}\n", encoding="utf-8")
            (service_dir / ".env.wsl").write_text("FOO=bar\n", encoding="utf-8")
            (service_dir / ".env.prod0").write_text("FOO=bar\n", encoding="utf-8")

            result = audit_filesystem(root, "wsl")
            codes = {item["id"] for item in result["violations"]}

            self.assertIn("wsl.compose.private_env_file", codes)

    def test_allows_minimal_compliant_compose_layout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            service_dir = root / "infra" / "compose" / "minio"
            service_dir.mkdir(parents=True, exist_ok=True)
            (service_dir / "docker-compose.wsl.yml").write_text("services: {}\n", encoding="utf-8")
            (service_dir / "docker-compose.prod0.yml").write_text("services: {}\n", encoding="utf-8")

            result = audit_filesystem(root, "wsl")
            wsl_violations = [item for item in result["violations"] if item["scope"] == "wsl"]
            self.assertEqual([], wsl_violations, msg=json.dumps(result, ensure_ascii=False))

    def test_exempts_prod2_only_compose_directories_from_wsl_template_requirement(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            service_dir = root / "infra" / "compose" / "vmail"
            service_dir.mkdir(parents=True, exist_ok=True)
            (service_dir / "docker-compose.prod2.yml").write_text("services: {}\n", encoding="utf-8")

            prod2_inventory = root / "inventory" / "servers" / "prod2-main" / "inventory.json"
            prod2_inventory.parent.mkdir(parents=True, exist_ok=True)
            prod2_inventory.write_text(
                json.dumps(
                    {
                        "services": {
                            "vmail": {
                                "control_plane": "compose",
                            }
                        }
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

            result = audit_filesystem(root, "wsl")
            codes = {item["id"] for item in result["violations"]}

            self.assertNotIn("wsl.missing.compose_wsl", codes)
            self.assertNotIn("wsl.missing.compose_prod0", codes)

# ======================================================================
# From: test_wsl_first_docs.py
# ======================================================================

REPO_ROOT = Path(__file__).resolve().parents[2]
CORE_TEMPLATE_ENTRY_DOCS = (
    REPO_ROOT / "README.md",
    REPO_ROOT / "AGENTS.md",
    REPO_ROOT / "docs" / "architecture" / "linux-governance.md",
    REPO_ROOT / "docs" / "reference" / "app-repository-standard.md",
    REPO_ROOT / "docs" / "runbooks" / "control-plane-agent-execution-flow.md",
)
FORBIDDEN_WINDOWS_SHELL_TERMS = (
    "powershell.exe",
    "Windows PowerShell",
)
FORBIDDEN_WSL_FIRST_TERMS = (
    "WSL-first",
    "默认工作流仍然是先进入 WSL",
)

class WslFirstDocsTests(unittest.TestCase):
    def test_core_template_docs_standardize_on_pwsh_not_legacy_powershell(self) -> None:
        for path in CORE_TEMPLATE_ENTRY_DOCS:
            text = path.read_text(encoding="utf-8")
            for term in FORBIDDEN_WINDOWS_SHELL_TERMS:
                with self.subTest(path=str(path), term=term):
                    self.assertNotIn(term, text)

    def test_repo_agents_doc_declares_pwsh_entry_and_backend_aware_routing(self) -> None:
        text = (REPO_ROOT / "AGENTS.md").read_text(encoding="utf-8")

        self.assertIn("Windows 上默认用 PowerShell", text)
        self.assertIn("`wsl.exe -e <程序>`", text)
        self.assertIn("Windows 和 WSL 共用同一个仓库目录", text)
        self.assertIn("只使用根目录 `.venv`", text)
        self.assertIn("远程 Linux 走 `agentplane infra remote bash`", text)

    def test_linux_governance_declares_backend_role_not_wsl_first_entry(self) -> None:
        text = (REPO_ROOT / "docs" / "architecture" / "linux-governance.md").read_text(
            encoding="utf-8"
        )

        self.assertIn("本页只定义 Linux / WSL backend 约束，不改变宿主入口选择。", text)
        self.assertIn("host-entry-first, backend-aware", text)
        self.assertIn("`pwsh -> formal CLI -> WSL/SSH backend`", text)
        self.assertNotIn("默认在当前 WSL shell 中直接执行 Linux 命令", text)
        self.assertNotIn("如果当前不在 WSL，会先进入 WSL", text)

    def test_readme_and_flow_promote_backend_split_instead_of_wsl_first(self) -> None:
        # README is a thin entry; backend-aware routing details live in AGENTS.md + cross-platform.md
        agents_text = (REPO_ROOT / "AGENTS.md").read_text(encoding="utf-8")
        flow_text = (
            REPO_ROOT / "docs" / "runbooks" / "control-plane-agent-execution-flow.md"
        ).read_text(encoding="utf-8")

        self.assertIn("`pwsh`", agents_text)
        self.assertIn("`pwsh`", flow_text)
        self.assertIn("bootstrap inspect-local", flow_text)
        self.assertIn("resolver / backend", flow_text)
        self.assertIn("Windows 与 WSL 默认共享同一份源码 checkout", flow_text)

    def test_template_surface_docs_do_not_reintroduce_wsl_first_language(self) -> None:
        for path in CORE_TEMPLATE_ENTRY_DOCS:
            text = path.read_text(encoding="utf-8")
            for term in FORBIDDEN_WSL_FIRST_TERMS:
                with self.subTest(path=str(path), term=term):
                    self.assertNotIn(term, text)
