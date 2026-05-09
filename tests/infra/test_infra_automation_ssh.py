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
from agentplane.domain.infra.automation import AUTOMATION_DEFINITIONS, InfraAutomationDefinition
from agentplane.cli.preflight import (
    PreflightCheck,
    PreflightReport,
    execute_remote_preflight,
)
from agentplane.domain.infra.preflight import (
    _check_ssh_config_exists,
    _check_ssh_key_permissions,
    _check_ssh_reachable,
    _check_wsl_available,
)
from agentplane.runtime.host_profile import HostProfile
from agentplane.ssh import SshTarget, resolve_ssh_config_path, resolve_ssh_target
from tests.support.paths import REPO_ROOT

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
                            "aliases": ["prod0-main", "example.net"],
                            "user": "root",
                        }
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

            target = resolve_ssh_target(repo_root, "example.net")

            self.assertEqual("root", target.user)
            self.assertEqual("example.net", target.alias)
            self.assertEqual("root@example.net", target.connection_target)

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


# ======================================================================
# From: test_wsl_first_docs.py
# ======================================================================

CORE_TEMPLATE_ENTRY_DOCS = (
    REPO_ROOT / "README.md",
    REPO_ROOT / "AGENTS.md",
    REPO_ROOT / "docs" / "conventions.md",
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
        text = (REPO_ROOT / "docs" / "archive" / "architecture" / "linux-governance.md").read_text(encoding="utf-8")

        self.assertIn("本页只定义 Linux / WSL backend 约束，不改变宿主入口选择。", text)
        self.assertIn("host-entry-first, backend-aware", text)
        self.assertIn("`pwsh -> formal CLI -> WSL/SSH backend`", text)
        self.assertNotIn("默认在当前 WSL shell 中直接执行 Linux 命令", text)
        self.assertNotIn("如果当前不在 WSL，会先进入 WSL", text)

    def test_readme_and_flow_promote_backend_split_instead_of_wsl_first(self) -> None:
        # README is a thin entry; backend-aware routing details live in AGENTS.md + cross-platform.md
        agents_text = (REPO_ROOT / "AGENTS.md").read_text(encoding="utf-8")
        flow_text = (REPO_ROOT / "docs" / "archive" / "runbooks" / "control-plane-agent-execution-flow.md").read_text(
            encoding="utf-8"
        )

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
