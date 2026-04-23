import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from agentplane.cli.inventory import generate_inventory_snapshot
from agentplane.domain import networks as network_domain
from agentplane.runtime.host_profile import HostProfile

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
    def test_host_help_lists_network(self) -> None:
        result = run_cli("host", "--help")
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
            ("host", "secrets-layout", "wsl", "--repo-root", str(REPO_ROOT)),
        ):
            with self.subTest(argv=argv):
                result = run_cli(*argv)
                self.assertNotEqual(0, result.returncode)
                self.assertIn("invalid choice", result.stderr)

    def test_host_inventory_wraps_inventory_payload(self) -> None:
        result = run_cli("host", "inventory", "wsl", "--repo-root", str(REPO_ROOT))
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual({"command", "action", "target", "payload"}, set(payload))
        self.assertEqual("host", payload["command"])
        self.assertEqual("inventory", payload["action"])
        self.assertEqual("wsl", payload["target"])
        self.assertIsInstance(payload["payload"], dict)

    def test_host_inventory_wsl_uses_backend_runner_contract_on_windows_host(self) -> None:
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

    def test_host_local_inspect_wraps_payload(self) -> None:
        result = run_cli("host", "local", "inspect", "--repo-root", "C:/repos/agentplane")
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual({"command", "action", "target", "payload"}, set(payload))
        self.assertEqual("host", payload["command"])
        self.assertEqual("local.inspect", payload["action"])
        self.assertEqual("local", payload["target"])
        self.assertEqual("wsl-linux", payload["payload"]["linux_backend"]["backend_type"])

    def test_host_audit_wraps_filesystem_audit_payload(self) -> None:
        result = run_cli("host", "audit", "wsl", "--repo-root", str(REPO_ROOT))
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual({"command", "action", "target", "payload"}, set(payload))
        self.assertEqual("host", payload["command"])
        self.assertEqual("audit", payload["action"])
        self.assertEqual("wsl", payload["target"])
        self.assertIsInstance(payload["payload"], dict)

    def test_host_cleanup_plan_wraps_cleanup_payload(self) -> None:
        result = run_cli("host", "cleanup", "plan", "wsl", "--repo-root", str(REPO_ROOT))
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual({"command", "action", "target", "payload"}, set(payload))
        self.assertEqual("host", payload["command"])
        self.assertEqual("cleanup.plan", payload["action"])
        self.assertEqual("wsl", payload["target"])
        self.assertIn("actions", payload["payload"])

    def test_host_cleanup_apply_wraps_cleanup_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / ".playwright-cli"
            target.mkdir(parents=True)
            (target / "page.yml").write_text("snapshot", encoding="utf-8")

            result = run_cli("host", "cleanup", "apply", "wsl", "--repo-root", str(root))
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual({"command", "action", "target", "payload"}, set(payload))
            self.assertEqual("host", payload["command"])
            self.assertEqual("cleanup.apply", payload["action"])
            self.assertEqual("wsl", payload["target"])
            self.assertEqual(1, payload["payload"]["removed_count"])

    def test_host_automation_search_wraps_payload(self) -> None:
        result = run_cli("host", "automation", "search", "wsl", "--repo-root", str(REPO_ROOT))
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual({"command", "action", "target", "payload"}, set(payload))
        self.assertEqual("host", payload["command"])
        self.assertEqual("automation.search", payload["action"])
        self.assertEqual("wsl", payload["target"])
        self.assertIn("items", payload["payload"])

    def test_host_remote_bash_wraps_dry_run_payload(self) -> None:
        script = REPO_ROOT / "agentplane" / "scripts" / "internal" / "remote" / "example.sh"
        result = run_cli(
            "host",
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
        self.assertEqual("host", payload["command"])
        self.assertEqual("remote.bash", payload["action"])
        self.assertEqual("prod0-main", payload["target"])
        self.assertTrue(payload["payload"]["dry_run"])

    def test_host_secrets_init_data_services_wraps_formal_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = run_cli(
                "host",
                "secrets",
                "init-data-services",
                "prod0-main",
                "--repo-root",
                str(root),
            )
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual({"command", "action", "target", "payload"}, set(payload))
            self.assertEqual("host", payload["command"])
            self.assertEqual("secrets.init-data-services", payload["action"])
            self.assertEqual("prod0-main", payload["target"])
            self.assertIn("files", payload["payload"])

    def test_host_secrets_sync_layout_wraps_sync_host_layout_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            host_root = root / "secrets" / "hosts" / "prod0-main" / "onepanel"
            host_root.mkdir(parents=True, exist_ok=True)
            (host_root / "api.env").write_text("ONEPANEL_API_KEY=demo\n", encoding="utf-8")

            result = run_cli(
                "host",
                "secrets",
                "sync-layout",
                "prod0-main",
                "--repo-root",
                str(root),
            )
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual({"command", "action", "target", "payload"}, set(payload))
            self.assertEqual("host", payload["command"])
            self.assertEqual("secrets.sync-layout", payload["action"])
            self.assertEqual("prod0-main", payload["target"])
            self.assertEqual("planned", payload["payload"]["projections"][0]["status"])

    def test_host_network_audit_uses_formal_host_shape_without_compat_source(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            inventory_dir = root / "inventory" / "servers" / "prod2-main"
            inventory_dir.mkdir(parents=True, exist_ok=True)
            inventory_dir.joinpath("inventory.json").write_text(
                json.dumps(
                    {
                        "ssh": {"aliases": ["prod2-main"], "user": "root"},
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
            (root / "secrets" / "ssh" / "config").write_text("Host prod2-main\n", encoding="utf-8")
            bin_dir = root / "bin"
            bin_dir.mkdir(parents=True, exist_ok=True)
            log_file = root / "network-audit.log"
            state_dir = root / "fake-network-state"
            state_dir.mkdir(parents=True, exist_ok=True)
            write_fake_bridge_network_ssh(bin_dir)

            result = run_cli(
                "host",
                "network",
                "audit",
                "prod2-main",
                "--repo-root",
                str(root),
                env_overrides={
                    "PATH": f"{bin_dir}:{os.environ['PATH']}",
                    "FAKE_CMD_LOG": str(log_file),
                    "FAKE_NETWORK_STATE_DIR": str(state_dir),
                },
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual({"command", "action", "target", "payload"}, set(payload))
            self.assertEqual("host", payload["command"])
            self.assertEqual("network.audit", payload["action"])
            self.assertEqual("prod2-main", payload["target"])
            self.assertFalse(payload["payload"]["ok"])

    def test_network_audit_fails_when_required_container_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            inventory_dir = root / "inventory" / "servers" / "prod2-main"
            inventory_dir.mkdir(parents=True, exist_ok=True)
            inventory_dir.joinpath("inventory.json").write_text(
                json.dumps(
                    {
                        "ssh": {"aliases": ["prod2-main"], "user": "root"},
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
                payload = network_domain.audit_managed_bridge_networks(root, "prod2-main")

            network = payload["networks"][0]
            self.assertFalse(payload["ok"])
            self.assertEqual(["missing-prod"], network["missing_required_containers"])
            self.assertIn("required_containers_missing", network["problems"])

    def test_host_network_ensure_uses_formal_host_shape_without_compat_source(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            inventory_dir = root / "inventory" / "servers" / "prod2-main"
            inventory_dir.mkdir(parents=True, exist_ok=True)
            inventory_dir.joinpath("inventory.json").write_text(
                json.dumps(
                    {
                        "ssh": {"aliases": ["prod2-main"], "user": "root"},
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
            (root / "secrets" / "ssh" / "config").write_text("Host prod2-main\n", encoding="utf-8")
            bin_dir = root / "bin"
            bin_dir.mkdir(parents=True, exist_ok=True)
            log_file = root / "network-ensure.log"
            state_dir = root / "fake-network-state"
            state_dir.mkdir(parents=True, exist_ok=True)
            write_fake_bridge_network_ssh(bin_dir)

            result = run_cli(
                "host",
                "network",
                "ensure",
                "prod2-main",
                "--repo-root",
                str(root),
                env_overrides={
                    "PATH": f"{bin_dir}:{os.environ['PATH']}",
                    "FAKE_CMD_LOG": str(log_file),
                    "FAKE_NETWORK_STATE_DIR": str(state_dir),
                },
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual({"command", "action", "target", "payload"}, set(payload))
            self.assertEqual("host", payload["command"])
            self.assertEqual("network.ensure", payload["action"])
            self.assertEqual("prod2-main", payload["target"])
            self.assertTrue(payload["payload"]["ok"])

