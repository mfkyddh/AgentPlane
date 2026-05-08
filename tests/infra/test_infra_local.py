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
from agentplane.domain.infra import networks as network_domain
from agentplane.runtime.host_profile import HostProfile
from agentplane.runtime.platform import HostPlatform
from agentplane.runtime.wsl_bridge import inspect_local_host
from tests.support.cli import run_agentplane_cli as run_cli
from tests.support.constants import CONTAINER_SUB2API, CONTAINER_POSTGRES
from tests.support.fake_scripts import write_fake_command
from tests.support.paths import REPO_ROOT

pytestmark = pytest.mark.e2e


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


def run_cli_json(*args: str) -> dict:
    result = run_cli(*args)
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
        self.assertEqual(
            "/mnt/c/repos/agentplane/.agentplane/staging", payload["payload"]["workspace"]["artifact_staging_root"]
        )
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
        tail = (
            config_path.as_posix().split(":", 1)[1].lstrip("/")
            if config_path.drive
            else config_path.as_posix().lstrip("/")
        )
        rendered_config = f"/mnt/{drive}/{tail}" if drive else config_path.as_posix()
        return ["wsl.exe", "-e", "ssh", "-T", "-F", rendered_config, "root@prod0-main", remote_command]
    return ["ssh", "-T", "-F", str(config_path), "root@prod0-main", remote_command]


