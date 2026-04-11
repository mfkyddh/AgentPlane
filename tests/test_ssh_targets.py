import unittest
from pathlib import Path
import json
import tempfile

from agentplane.ssh import SshTarget, resolve_ssh_target, resolve_ssh_config_path


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


if __name__ == "__main__":
    unittest.main()
