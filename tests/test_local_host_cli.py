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
    def test_windows_host_does_not_bind_wsl_to_windows_repo_root(self) -> None:
        payload = inspect_local_host(
            "C:/repos/agentplane",
            host_platform=HostPlatform(os_name="windows", has_wsl=True, is_wsl=False),
        )

        self.assertIsNone(payload["legacy_control_root"])
        self.assertIsNone(payload["linux_backend_root"])
        self.assertEqual("windows-wsl", payload["host_profile"]["linux_backend"])
        self.assertTrue(payload["workspace"]["artifact_staging_root"].endswith(r"C:\repos\agentplane\.agentplane\staging"))
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

    def test_host_local_inspect_reports_windows_control_root(self) -> None:
        payload = run_cli_json("host", "local", "inspect", "--repo-root", "C:/repos/agentplane")

        self.assertEqual("host", payload["command"])
        self.assertEqual("local.inspect", payload["action"])
        self.assertEqual("local", payload["target"])
        self.assertTrue(payload["payload"]["control_root"].endswith("C:\\repos\\agentplane"))
        self.assertEqual("wsl-linux", payload["payload"]["linux_backend"]["backend_type"])
        self.assertEqual("windows", payload["payload"]["host_profile"]["os_name"])
        self.assertEqual("windows-wsl", payload["payload"]["host_profile"]["linux_backend"])
        self.assertTrue(
            payload["payload"]["workspace"]["artifact_staging_root"].endswith(
                r"C:\repos\agentplane\.agentplane\staging"
            )
        )
        self.assertTrue(payload["payload"]["workspace"]["source_root"].endswith("C:\\repos\\agentplane"))
        self.assertTrue(payload["payload"]["workspace"]["local_command_root"].endswith("C:\\repos\\agentplane"))
        self.assertEqual("canonical-ref-only", payload["payload"]["path_policy"]["truth"])

    def test_host_local_migration_plan_includes_private_dirs(self) -> None:
        payload = run_cli_json("host", "local", "migrate", "plan", "--windows-root", "D:\\Projects\\AgentPlane")

        self.assertEqual("local.migrate.plan", payload["action"])
        self.assertIn("secrets", payload["payload"]["private_dirs"])


if __name__ == "__main__":
    unittest.main()
