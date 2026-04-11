import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch


REPO_ROOT = Path(__file__).resolve().parents[1]


def common_repo_root(repo_root: Path) -> Path:
    git_entry = repo_root / ".git"
    if git_entry.is_dir():
        return repo_root
    if git_entry.is_file():
        content = git_entry.read_text(encoding="utf-8").strip()
        if content.startswith("gitdir:"):
            git_dir = Path(content.split(":", 1)[1].strip())
            if not git_dir.is_absolute():
                git_dir = (repo_root / git_dir).resolve()
            if len(git_dir.parts) >= 3 and git_dir.parent.name == "worktrees" and git_dir.parent.parent.name == ".git":
                return git_dir.parents[2]
    return repo_root


MAIN_REPO_ROOT = common_repo_root(REPO_ROOT)


def run_cli(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "agentplane.cli", *args],
        cwd=cwd or REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


class RemoteCliTests(unittest.TestCase):
    def test_execute_remote_bash_uses_explicit_stdin_text(self) -> None:
        from agentplane.cli.remote import execute_remote_bash

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            inventory_file = root / "inventory" / "servers" / "prod0-main" / "inventory.json"
            inventory_file.parent.mkdir(parents=True, exist_ok=True)
            inventory_file.write_text(
                json.dumps({"ssh": {"aliases": ["prod0-main"], "user": "root"}}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

            completed = subprocess.CompletedProcess(
                args=["ssh", "-T", "root@prod0-main", "bash -s -- echo"],
                returncode=0,
                stdout="ok\n",
                stderr="",
            )
            stdin_mock = Mock()
            stdin_mock.read.side_effect = AssertionError("sys.stdin.read should not be used when stdin_text is explicit")

            with (
                patch("agentplane.cli.remote.subprocess.run", return_value=completed) as run_mock,
                patch("agentplane.cli.remote.sys.stdin", stdin_mock),
            ):
                payload = execute_remote_bash(
                    repo_root=root,
                    target="prod0-main",
                    remote_args=["echo"],
                    stdin_text="echo ok\n",
                )

            self.assertTrue(payload["ok"])
            self.assertEqual("stdin", payload["transport"])
            run_mock.assert_called_once_with(
                [
                    "ssh",
                    "-T",
                    "-F",
                    str(root / "secrets" / "ssh" / "config"),
                    "root@prod0-main",
                    "bash -s -- echo",
                ],
                input="echo ok\n",
                text=True,
                capture_output=True,
                check=False,
            )

    def test_remote_bash_dry_run_writes_operation_ledger(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            inventory_file = root / "inventory" / "servers" / "prod0-main" / "inventory.json"
            inventory_file.parent.mkdir(parents=True, exist_ok=True)
            inventory_file.write_text(
                json.dumps({"ssh": {"aliases": ["prod0-main"], "user": "root"}}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            script_file = root / "example.sh"
            script_file.write_text("#!/usr/bin/env bash\nset -euo pipefail\necho ok\n", encoding="utf-8")

            result = run_cli(
                "host",
                "remote",
                "bash",
                "prod0-main",
                "--repo-root",
                str(root),
                "--dry-run",
                "--script-file",
                str(script_file),
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual("host", payload.get("command"))
            self.assertEqual("remote.bash", payload.get("action"))
            operation = payload.get("payload", {}).get("operation", {})
            ledger_file = Path(operation["ledger_file"])
            self.assertTrue(ledger_file.is_file())
            entry = json.loads(ledger_file.read_text(encoding="utf-8").strip().splitlines()[-1])
            self.assertEqual("remote", entry["command"])
            self.assertEqual("bash", entry["action"])
            self.assertEqual("prod0-main", entry["target"])
            self.assertEqual(operation["op_id"], entry["op_id"])
            self.assertEqual("planned", entry["result"])
            self.assertEqual("script-file", entry["transport"])

    def test_execute_remote_bash_non_dry_run_records_operation_with_preallocated_op_id(self) -> None:
        from agentplane.cli.remote import execute_remote_bash

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            inventory_file = root / "inventory" / "servers" / "prod0-main" / "inventory.json"
            inventory_file.parent.mkdir(parents=True, exist_ok=True)
            inventory_file.write_text(
                json.dumps({"ssh": {"aliases": ["prod0-main"], "user": "root"}}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

            resolved_root = root.resolve()
            ledger_file = resolved_root / "tmp" / "operation-ledger" / "2026-04-01.jsonl"
            completed = subprocess.CompletedProcess(
                args=["ssh", "-T", "root@prod0-main", "bash -s -- echo"],
                returncode=0,
                stdout="ok\n",
                stderr="",
            )
            state = {"op_id_generated": False}

            def fake_next_operation_id(prefix: str) -> str:
                self.assertEqual("remote-bash", prefix)
                state["op_id_generated"] = True
                return "remote-bash-fixed"

            def fake_run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
                self.assertTrue(state["op_id_generated"], "op_id should be allocated before remote execution")
                return completed

            with (
                patch("agentplane.cli.remote.next_operation_id", side_effect=fake_next_operation_id) as op_id_mock,
                patch(
                    "agentplane.cli.remote.append_operation_ledger",
                    return_value={"ledger_file": str(ledger_file)},
                ) as ledger_mock,
                patch("agentplane.cli.remote.subprocess.run", side_effect=fake_run) as run_mock,
            ):
                payload = execute_remote_bash(
                    repo_root=root,
                    target="prod0-main",
                    remote_args=["echo"],
                    stdin_text="echo ok\n",
                )

            self.assertTrue(payload["ok"])
            self.assertEqual(
                {
                    "op_id": "remote-bash-fixed",
                    "result": "succeeded",
                    "ledger_file": str(ledger_file),
                },
                payload["operation"],
            )
            op_id_mock.assert_called_once_with("remote-bash")
            run_mock.assert_called_once_with(
                [
                    "ssh",
                    "-T",
                    "-F",
                    str(resolved_root / "secrets" / "ssh" / "config"),
                    "root@prod0-main",
                    "bash -s -- echo",
                ],
                input="echo ok\n",
                text=True,
                capture_output=True,
                check=False,
            )
            ledger_mock.assert_called_once_with(
                resolved_root,
                command="remote",
                action="bash",
                target="prod0-main",
                op_id="remote-bash-fixed",
                dry_run=False,
                result="succeeded",
                details={
                    "transport": "stdin",
                    "connection_target": "root@prod0-main",
                    "remote_command": "bash -s -- echo",
                    "script_file": None,
                },
            )

    def test_remote_bash_dry_run_emits_structured_plan(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            script_file = Path(tmp) / "example.sh"
            script_file.write_text("#!/usr/bin/env bash\nset -euo pipefail\necho ok\n", encoding="utf-8")

            result = run_cli(
                "host",
                "remote",
                "bash",
                "prod0-main",
                "--dry-run",
                "--script-file",
                str(script_file),
                "--",
                "postgres18-prod",
                "value with spaces",
            )

        self.assertEqual(result.returncode, 0, msg=result.stderr)
        payload = json.loads(result.stdout)
        inner = payload.get("payload", {})
        self.assertEqual("host", payload.get("command"))
        self.assertEqual("remote.bash", payload.get("action"))
        self.assertTrue(inner.get("ok"))
        self.assertEqual("prod0-main", payload.get("target"))
        self.assertEqual("script-file", inner.get("transport"))
        self.assertEqual(str(script_file), inner.get("script_file"))
        self.assertEqual(
            str(MAIN_REPO_ROOT / "secrets" / "ssh" / "config"),
            inner.get("ssh_config"),
        )
        self.assertEqual("root@prod0-main", inner.get("connection_target"))
        self.assertEqual(
            "bash -s -- postgres18-prod 'value with spaces'",
            inner.get("remote_command"),
        )
        self.assertEqual(
            [
                "ssh",
                "-T",
                "-F",
                str(MAIN_REPO_ROOT / "secrets" / "ssh" / "config"),
                "root@prod0-main",
                "bash -s -- postgres18-prod 'value with spaces'",
            ],
            inner.get("ssh_argv"),
        )
        self.assertIn("ledger_file", inner.get("operation", {}))

    def test_host_remote_bash_rejects_non_formal_target(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            script_file = Path(tmp) / "example.sh"
            script_file.write_text("#!/usr/bin/env bash\nset -euo pipefail\necho ok\n", encoding="utf-8")

            result = run_cli(
                "host",
                "remote",
                "bash",
                "retired-target",
                "--dry-run",
                "--script-file",
                str(script_file),
                "--",
                "docker",
                "ps",
            )

        self.assertEqual(result.returncode, 2)
        self.assertIn("invalid choice: 'retired-target'", result.stderr)

    def test_remote_bash_requires_existing_script_file(self) -> None:
        missing = REPO_ROOT / "agentplane" / "scripts" / "remote" / "missing-example.sh"

        result = run_cli(
            "host",
            "remote",
            "bash",
            "prod0-main",
            "--dry-run",
            "--script-file",
            str(missing),
        )

        self.assertEqual(result.returncode, 1)
        self.assertIn("Script file not found", result.stderr)


if __name__ == "__main__":
    unittest.main()
