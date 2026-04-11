import json
import subprocess
import sys
import unittest
from pathlib import Path

from agentplane.runtime.platform import HostPlatform
from agentplane.runtime.wsl_bridge import inspect_local_host


REPO_ROOT = Path(__file__).resolve().parents[1]


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
    def test_windows_host_keeps_wsl_backend_paths_in_posix_form(self) -> None:
        payload = inspect_local_host(
            r"\\wsl.localhost\Ubuntu\root\work\AgentPlane",
            host_platform=HostPlatform(os_name="windows", has_wsl=True, is_wsl=False),
        )

        self.assertEqual("/root/work/AgentPlane", payload["legacy_control_root"])
        self.assertEqual("/root/work/AgentPlane", payload["linux_backend_root"])
        self.assertEqual("windows-wsl", payload["host_profile"]["linux_backend"])
        self.assertEqual("/root/work/AgentPlane/.agentplane/staging", payload["workspace"]["artifact_staging_root"])
        self.assertEqual("/root/work/AgentPlane", payload["workspace"]["source_root"])
        self.assertEqual("/root/work/AgentPlane", payload["workspace"]["local_command_root"])

    def test_host_local_inspect_reports_windows_control_root(self) -> None:
        payload = run_cli_json("host", "local", "inspect", "--repo-root", "D:/Projects/AgentPlane")

        self.assertEqual("host", payload["command"])
        self.assertEqual("local.inspect", payload["action"])
        self.assertEqual("local", payload["target"])
        self.assertTrue(payload["payload"]["control_root"].endswith("D:\\Projects\\AgentPlane"))
        self.assertEqual("wsl-linux", payload["payload"]["linux_backend"]["backend_type"])
        self.assertEqual("windows", payload["payload"]["host_profile"]["os_name"])
        self.assertEqual("windows-wsl", payload["payload"]["host_profile"]["linux_backend"])
        self.assertEqual("/root/work/AgentPlane/.agentplane/staging", payload["payload"]["workspace"]["artifact_staging_root"])
        self.assertTrue(payload["payload"]["workspace"]["source_root"].endswith("D:\\Projects\\AgentPlane"))
        self.assertTrue(payload["payload"]["workspace"]["local_command_root"].endswith("D:\\Projects\\AgentPlane"))
        self.assertEqual("canonical-ref-only", payload["payload"]["path_policy"]["truth"])

    def test_host_local_migration_plan_includes_private_dirs(self) -> None:
        payload = run_cli_json("host", "local", "migrate", "plan", "--windows-root", "D:\\Projects\\AgentPlane")

        self.assertEqual("local.migrate.plan", payload["action"])
        self.assertIn("secrets", payload["payload"]["private_dirs"])


if __name__ == "__main__":
    unittest.main()
