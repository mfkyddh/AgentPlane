from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
from agentplane.cli.inventory import generate_inventory_snapshot
from agentplane.domain import networks as network_domain
from agentplane.runtime.host_profile import HostProfile
from agentplane.runtime.platform import HostPlatform
from agentplane.runtime.wsl_bridge import inspect_local_host

pytestmark = pytest.mark.e2e

REPO_ROOT = Path(__file__).resolve().parents[2]

def run_cli(
    *args: str,
    cwd: Path | None = None,
    env_overrides: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    env = None
    if env_overrides:
        env = os.environ.copy()
        env.update(env_overrides)
        if "FAKE_CMD_LOG" in env_overrides:
            env.setdefault("AGENTPLANE_DISABLE_WSL_SSH", "1")
    return subprocess.run(
        [sys.executable, "-m", "agentplane.cli", *args],
        cwd=cwd or REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

def write_fake_command(bin_dir: Path, name: str, body: str) -> None:
    script = bin_dir / name
    script.write_text(body, encoding="utf-8")
    script.chmod(0o755)

def write_fake_bridge_network_ssh(bin_dir: Path) -> None:
    write_fake_command(
        bin_dir,
        "ssh",
        """#!/usr/bin/env bash
set -euo pipefail
printf 'ssh %s\\n' "$*" >> "$FAKE_CMD_LOG"
cmd="$*"
state_dir="${FAKE_NETWORK_STATE_DIR:?}"
bridge="br-66f7da1be943"
if [[ "$cmd" == *"docker network inspect zqf_network --format"* ]]; then
  cat <<'JSON'
{"Name":"zqf_network","Id":"66f7da1be943bc160d7df638561fe15ccc1ceea6912e9c753dd40d087e23d8b3","Driver":"bridge","IPAM":{"Config":[{"Subnet":"172.19.0.0/16","Gateway":"172.19.0.1"}]},"Containers":{"sub2api":{"Name":"sub2api-prod"}}}
JSON
  exit 0
fi
if [[ "$cmd" == *"ip -json -4 addr show dev ${bridge}"* ]]; then
  if [[ -f "${state_dir}/gateway_present" ]]; then
    echo '[{"ifname":"br-66f7da1be943","addr_info":[{"local":"172.19.0.1","prefixlen":16}]}]'
  else
    echo '[{"ifname":"br-66f7da1be943","addr_info":[]}]'
  fi
  exit 0
fi
if [[ "$cmd" == *"ip -json route show 172.19.0.0/16"* ]]; then
  if [[ -f "${state_dir}/route_present" ]]; then
    echo '[{"dst":"172.19.0.0/16","dev":"br-66f7da1be943","prefsrc":"172.19.0.1"}]'
  else
    echo '[]'
  fi
  exit 0
fi
if [[ "$cmd" == *"ip addr add 172.19.0.1/16 dev ${bridge}"* ]]; then
  touch "${state_dir}/gateway_present"
  exit 0
fi
if [[ "$cmd" == *"ip route replace 172.19.0.0/16 dev ${bridge} src 172.19.0.1"* ]]; then
  touch "${state_dir}/route_present"
  exit 0
fi
exit 0
""",
    )

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

    def test_infra_secrets_init_data_services_wraps_formal_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = run_cli(
                "infra",
                "secrets",
                "init-data-services",
                "prod0-main",
                "--repo-root",
                str(root),
            )
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual({"command", "action", "target", "payload"}, set(payload))
            self.assertEqual("infra", payload["command"])
            self.assertEqual("secrets.init-data-services", payload["action"])
            self.assertEqual("prod0-main", payload["target"])
            self.assertIn("files", payload["payload"])

    def test_infra_secrets_sync_layout_wraps_sync_host_layout_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            host_root = root / "secrets" / "hosts" / "prod0-main" / "onepanel"
            host_root.mkdir(parents=True, exist_ok=True)
            (host_root / "api.env").write_text("ONEPANEL_API_KEY=demo\n", encoding="utf-8")

            result = run_cli(
                "infra",
                "secrets",
                "sync-layout",
                "prod0-main",
                "--repo-root",
                str(root),
            )
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual({"command", "action", "target", "payload"}, set(payload))
            self.assertEqual("infra", payload["command"])
            self.assertEqual("secrets.sync-layout", payload["action"])
            self.assertEqual("prod0-main", payload["target"])
            self.assertEqual("planned", payload["payload"]["projections"][0]["status"])

    def test_infra_network_audit_uses_formal_host_shape_without_compat_source(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            inventory_dir = root / "inventory" / "servers" / "prod0-main"
            inventory_dir.mkdir(parents=True, exist_ok=True)
            inventory_dir.joinpath("inventory.json").write_text(
                json.dumps(
                    {
                        "ssh": {"aliases": ["prod0-main"], "user": "root"},
                        "managed_bridge_networks": [
                            {
                                "name": "zqf_network",
                                "driver": "bridge",
                                "subnet": "172.19.0.0/16",
                                "gateway_ip": "172.19.0.1/16",
                                "required_for": ["sub2api-prod"],
                            }
                        ],
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            (root / "secrets" / "ssh").mkdir(parents=True, exist_ok=True)
            (root / "secrets" / "ssh" / "config").write_text("Host prod0-main\n", encoding="utf-8")
            bin_dir = root / "bin"
            bin_dir.mkdir(parents=True, exist_ok=True)
            log_file = root / "network-audit.log"
            state_dir = root / "fake-network-state"
            state_dir.mkdir(parents=True, exist_ok=True)
            write_fake_bridge_network_ssh(bin_dir)

            result = run_cli(
                "infra",
                "network",
                "audit",
                "prod0-main",
                "--repo-root",
                str(root),
                env_overrides={
                    "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
                    "FAKE_CMD_LOG": str(log_file),
                    "FAKE_NETWORK_STATE_DIR": str(state_dir),
                },
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual({"command", "action", "target", "payload"}, set(payload))
            self.assertEqual("infra", payload["command"])
            self.assertEqual("network.audit", payload["action"])
            self.assertEqual("prod0-main", payload["target"])
            self.assertFalse(payload["payload"]["ok"])

    def test_network_audit_fails_when_required_container_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            inventory_dir = root / "inventory" / "servers" / "prod0-main"
            inventory_dir.mkdir(parents=True, exist_ok=True)
            inventory_dir.joinpath("inventory.json").write_text(
                json.dumps(
                    {
                        "ssh": {"aliases": ["prod0-main"], "user": "root"},
                        "managed_bridge_networks": [
                            {
                                "name": "zqf_network",
                                "driver": "bridge",
                                "subnet": "172.19.0.0/16",
                                "gateway_ip": "172.19.0.1/16",
                                "required_for": ["missing-prod"],
                            }
                        ],
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

            def fake_remote_step(repo_root: Path, target: str, command: str) -> dict[str, object]:
                if "docker network inspect zqf_network --format" in command:
                    return {
                        "ok": True,
                        "stdout": json.dumps(
                            {
                                "Name": "zqf_network",
                                "Id": "66f7da1be943bc160d7df638561fe15ccc1ceea6912e9c753dd40d087e23d8b3",
                                "Driver": "bridge",
                                "IPAM": {"Config": [{"Subnet": "172.19.0.0/16", "Gateway": "172.19.0.1"}]},
                                "Containers": {"sub2api": {"Name": "sub2api-prod"}},
                            }
                        ),
                    }
                if "ip -json -4 addr show dev br-66f7da1be943" in command:
                    return {
                        "ok": True,
                        "stdout": '[{"ifname":"br-66f7da1be943","addr_info":[{"local":"172.19.0.1","prefixlen":16}]}]',
                    }
                if "ip -json route show 172.19.0.0/16" in command:
                    return {
                        "ok": True,
                        "stdout": '[{"dst":"172.19.0.0/16","dev":"br-66f7da1be943","prefsrc":"172.19.0.1"}]',
                    }
                return {"ok": False, "stdout": ""}

            with patch("agentplane.domain.networks._remote_step", side_effect=fake_remote_step):
                payload = network_domain.audit_managed_bridge_networks(root, "prod0-main")

            network = payload["networks"][0]
            self.assertFalse(payload["ok"])
            self.assertEqual(["missing-prod"], network["missing_required_containers"])
            self.assertIn("required_containers_missing", network["problems"])

    def test_infra_network_ensure_uses_formal_host_shape_without_compat_source(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            inventory_dir = root / "inventory" / "servers" / "prod0-main"
            inventory_dir.mkdir(parents=True, exist_ok=True)
            inventory_dir.joinpath("inventory.json").write_text(
                json.dumps(
                    {
                        "ssh": {"aliases": ["prod0-main"], "user": "root"},
                        "managed_bridge_networks": [
                            {
                                "name": "zqf_network",
                                "driver": "bridge",
                                "subnet": "172.19.0.0/16",
                                "gateway_ip": "172.19.0.1/16",
                                "required_for": ["sub2api-prod"],
                            }
                        ],
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            (root / "secrets" / "ssh").mkdir(parents=True, exist_ok=True)
            (root / "secrets" / "ssh" / "config").write_text("Host prod0-main\n", encoding="utf-8")
            state = {"gateway_present": False, "route_present": False}

            def fake_remote_step(repo_root: Path, target: str, command: str) -> dict[str, object]:
                if "docker network inspect zqf_network --format" in command:
                    return {
                        "ok": True,
                        "stdout": json.dumps(
                            {
                                "Name": "zqf_network",
                                "Id": "66f7da1be943bc160d7df638561fe15ccc1ceea6912e9c753dd40d087e23d8b3",
                                "Driver": "bridge",
                                "IPAM": {"Config": [{"Subnet": "172.19.0.0/16", "Gateway": "172.19.0.1"}]},
                                "Containers": {"sub2api": {"Name": "sub2api-prod"}},
                            }
                        ),
                    }
                if "ip -json -4 addr show dev br-66f7da1be943" in command:
                    stdout = '[{"ifname":"br-66f7da1be943","addr_info":[{"local":"172.19.0.1","prefixlen":16}]}]' if state["gateway_present"] else '[{"ifname":"br-66f7da1be943","addr_info":[]}]'
                    return {"ok": True, "stdout": stdout}
                if "ip -json route show 172.19.0.0/16" in command:
                    stdout = '[{"dst":"172.19.0.0/16","dev":"br-66f7da1be943","prefsrc":"172.19.0.1"}]' if state["route_present"] else "[]"
                    return {"ok": True, "stdout": stdout}
                if "ip addr add 172.19.0.1/16 dev br-66f7da1be943" in command:
                    state["gateway_present"] = True
                    return {"ok": True, "stdout": ""}
                if "ip route replace 172.19.0.0/16 dev br-66f7da1be943 src 172.19.0.1" in command:
                    state["route_present"] = True
                    return {"ok": True, "stdout": ""}
                return {"ok": False, "stdout": ""}

            from agentplane.cli.infra import handle_infra_command

            args = SimpleNamespace(
                infra_action="network",
                infra_network_action="ensure",
                target="prod0-main",
                repo_root=str(root),
            )
            with patch("agentplane.domain.networks._remote_step", side_effect=fake_remote_step):
                payload = handle_infra_command(args)

            self.assertEqual({"command", "action", "target", "payload"}, set(payload))
            self.assertEqual("infra", payload["command"])
            self.assertEqual("network.ensure", payload["action"])
            self.assertEqual("prod0-main", payload["target"])
            self.assertTrue(payload["payload"]["ok"])

# ======================================================================
# From: test_local_host_cli.py
# ======================================================================

REPO_ROOT = Path(__file__).resolve().parents[2]

def run_cli_json(*args: str) -> dict:
    result = subprocess.run(
        [sys.executable, "-m", "agentplane.cli", *args],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise AssertionError(result.stderr)
    return json.loads(result.stdout)

class LocalHostCliTests(unittest.TestCase):
    def test_windows_host_binds_wsl_to_same_checkout(self) -> None:
        payload = inspect_local_host(
            "C:/repos/agentplane",
            host_platform=HostPlatform(os_name="windows", has_wsl=True, is_wsl=False),
        )

        self.assertIsNone(payload["legacy_control_root"])
        self.assertEqual("/mnt/c/repos/agentplane", payload["linux_backend_root"])
        self.assertEqual("windows-wsl", payload["host_profile"]["linux_backend"])
        self.assertEqual("/mnt/c/repos/agentplane/.agentplane/staging", payload["workspace"]["artifact_staging_root"])
        self.assertTrue(payload["workspace"]["source_root"].endswith("C:\\repos\\agentplane"))
        self.assertTrue(payload["workspace"]["local_command_root"].endswith("C:\\repos\\agentplane"))

    def test_windows_host_keeps_unc_repo_roots_on_linux_backend_side(self) -> None:
        payload = inspect_local_host(
            r"\\wsl.localhost\Ubuntu\srv\control-plane\agentplane",
            host_platform=HostPlatform(os_name="windows", has_wsl=True, is_wsl=False),
        )

        self.assertTrue(payload["control_root"].startswith("\\\\wsl.localhost\\Ubuntu\\srv\\control-plane\\agentplane"))
        self.assertEqual("/srv/control-plane/agentplane", payload["legacy_control_root"])
        self.assertEqual("/srv/control-plane/agentplane", payload["linux_backend_root"])
        self.assertEqual("/srv/control-plane/agentplane", payload["workspace"]["source_root"])
        self.assertEqual("/srv/control-plane/agentplane", payload["workspace"]["local_command_root"])
        self.assertEqual(
            "/srv/control-plane/agentplane/.agentplane/staging",
            payload["workspace"]["artifact_staging_root"],
        )

    def test_infra_local_inspect_reports_windows_control_root(self) -> None:
        payload = run_cli_json("infra", "local", "inspect", "--repo-root", "C:/repos/agentplane")

        self.assertEqual("infra", payload["command"])
        self.assertEqual("local.inspect", payload["action"])
        self.assertEqual("local", payload["target"])
        self.assertTrue(payload["payload"]["control_root"].endswith("C:\\repos\\agentplane"))
        self.assertEqual("wsl-linux", payload["payload"]["linux_backend"]["backend_type"])
        self.assertEqual("windows", payload["payload"]["host_profile"]["os_name"])
        self.assertEqual("windows-wsl", payload["payload"]["host_profile"]["linux_backend"])
        self.assertEqual("/mnt/c/repos/agentplane/.agentplane/staging", payload["payload"]["workspace"]["artifact_staging_root"])
        self.assertTrue(payload["payload"]["workspace"]["source_root"].endswith("C:\\repos\\agentplane"))
        self.assertTrue(payload["payload"]["workspace"]["local_command_root"].endswith("C:\\repos\\agentplane"))
        self.assertEqual("canonical-ref-only", payload["payload"]["path_policy"]["truth"])

    def test_infra_local_migration_entry_is_removed(self) -> None:
        result = subprocess.run(
            [sys.executable, "-m", "agentplane.cli", "infra", "local", "migrate", "plan"],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertNotEqual(0, result.returncode)
        self.assertIn("invalid choice", result.stderr)

# ======================================================================
# From: test_remote_cli.py
# ======================================================================

REPO_ROOT = Path(__file__).resolve().parents[2]

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

def expected_ssh_stdin_argv(config_path: Path, remote_command: str) -> list[str]:
    if os.name == "nt":
        drive = config_path.drive.rstrip(":").lower()
        tail = config_path.as_posix().split(":", 1)[1].lstrip("/") if config_path.drive else config_path.as_posix().lstrip("/")
        rendered_config = f"/mnt/{drive}/{tail}" if drive else config_path.as_posix()
        return ["wsl.exe", "-e", "ssh", "-T", "-F", rendered_config, "root@prod0-main", remote_command]
    return ["ssh", "-T", "-F", str(config_path), "root@prod0-main", remote_command]

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
                patch("agentplane.runtime.execution.subprocess.run", return_value=completed) as run_mock,
                patch("agentplane.cli.remote.sys.stdin", stdin_mock),
            ):
                payload = execute_remote_bash(
                    repo_root=root,
                    target="prod0-main",
                    remote_args=["echo"],
                    stdin_text="echo ok\r\n",
                )

            self.assertTrue(payload["ok"])
            self.assertEqual("stdin", payload["transport"])
            run_mock.assert_called_once()
            self.assertEqual(
                expected_ssh_stdin_argv(root / "secrets" / "ssh" / "config", "bash -s -- echo"),
                run_mock.call_args.args[0],
            )
            call_kwargs = run_mock.call_args.kwargs
            self.assertEqual(None, call_kwargs["cwd"])
            self.assertEqual(None, call_kwargs["env"])
            self.assertEqual(True, call_kwargs["capture_output"])
            self.assertEqual(False, call_kwargs["check"])
            self.assertEqual(300, call_kwargs["timeout"])
            if os.name == "nt":
                self.assertEqual(b"echo ok\n", call_kwargs["input"])
                self.assertEqual(False, call_kwargs["text"])
            else:
                self.assertEqual("echo ok\n", call_kwargs["input"])
                self.assertEqual(True, call_kwargs["text"])
                self.assertEqual("utf-8", call_kwargs["encoding"])
                self.assertEqual("replace", call_kwargs["errors"])

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
                "infra",
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
            self.assertEqual("infra", payload.get("command"))
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
                patch("agentplane.runtime.execution.subprocess.run", side_effect=fake_run) as run_mock,
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
            run_mock.assert_called_once()
            self.assertEqual(
                expected_ssh_stdin_argv(resolved_root / "secrets" / "ssh" / "config", "bash -s -- echo"),
                run_mock.call_args.args[0],
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
                    "backend_type": "ssh-linux",
                },
            )

    def test_remote_bash_dry_run_emits_structured_plan(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            script_file = Path(tmp) / "example.sh"
            script_file.write_text("#!/usr/bin/env bash\nset -euo pipefail\necho ok\n", encoding="utf-8")

            result = run_cli(
                "infra",
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
        self.assertEqual("infra", payload.get("command"))
        self.assertEqual("remote.bash", payload.get("action"))
        self.assertTrue(inner.get("ok"))
        self.assertEqual("prod0-main", payload.get("target"))
        self.assertEqual("script-file", inner.get("transport"))
        self.assertEqual("ssh-linux", inner.get("backend_type"))
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
            expected_ssh_stdin_argv(
                MAIN_REPO_ROOT / "secrets" / "ssh" / "config",
                "bash -s -- postgres18-prod 'value with spaces'",
            ),
            inner.get("ssh_argv"),
        )
        self.assertEqual("ssh-linux", inner.get("execution_plan", {}).get("backend_type"))
        self.assertEqual("ssh-linux", inner.get("backend", {}).get("backend_type"))
        self.assertIn("ledger_file", inner.get("operation", {}))

    def test_infra_remote_bash_rejects_non_formal_target(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            script_file = Path(tmp) / "example.sh"
            script_file.write_text("#!/usr/bin/env bash\nset -euo pipefail\necho ok\n", encoding="utf-8")

            result = run_cli(
                "infra",
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
            "infra",
            "remote",
            "bash",
            "prod0-main",
            "--dry-run",
            "--script-file",
            str(missing),
        )

        self.assertEqual(result.returncode, 1)
        self.assertIn("Script file not found", result.stderr)
