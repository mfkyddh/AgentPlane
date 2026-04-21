import sys
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
ONEPANEL_SCRIPTS = REPO_ROOT / "agentplane" / "scripts" / "onepanel"
if str(ONEPANEL_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(ONEPANEL_SCRIPTS))

from agentplane.scripts.onepanel import env_targets  # type: ignore  # noqa: E402


class OnePanelEnvTargetsTests(unittest.TestCase):
    def _run_cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-m", "agentplane.cli", *args],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

    def tearDown(self) -> None:
        if hasattr(env_targets, "_resolve_remote_api_paths"):
            env_targets._resolve_remote_api_paths.cache_clear()

    def test_resolve_repo_root_falls_back_to_common_git_root_for_worktree(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            main_root = tmp_root / "main"
            worktree_root = tmp_root / "worktree"
            git_worktree_dir = main_root / ".git" / "worktrees" / "demo"
            script_path = worktree_root / "agentplane" / "scripts" / "onepanel" / "env_targets.py"

            git_worktree_dir.mkdir(parents=True, exist_ok=True)
            script_path.parent.mkdir(parents=True, exist_ok=True)
            worktree_root.mkdir(parents=True, exist_ok=True)
            (worktree_root / ".git").write_text(f"gitdir: {git_worktree_dir}\n", encoding="utf-8")

            resolved = env_targets.resolve_repo_root(script_path)

            self.assertEqual(main_root, resolved)

    def test_prod_targets_use_agentplane_remote_paths_and_support_prod2(self) -> None:
        prod0_target = env_targets.get_target("prod0-main")
        prod2_target = env_targets.get_target("prod2-main")

        self.assertEqual("ssh", prod0_target.mode)
        self.assertEqual("ssh", prod2_target.mode)
        self.assertEqual("prod0-main", prod0_target.ssh_alias)
        self.assertEqual("prod2-main", prod2_target.ssh_alias)
        self.assertEqual(Path("/opt/agentplane/secrets/services/onepanel-api.env"), prod0_target.api_env_file)
        self.assertEqual(Path("/opt/agentplane/agentplane/scripts/onepanel/api_request.py"), prod0_target.api_request_script)
        self.assertEqual(Path("/opt/agentplane/secrets/services/onepanel-api.env"), prod2_target.api_env_file)
        self.assertEqual(Path("/opt/agentplane/agentplane/scripts/onepanel/api_request.py"), prod2_target.api_request_script)

    def test_supported_targets_include_prod2(self) -> None:
        self.assertIn("prod2-main", env_targets.supported_targets())

    def test_resolve_remote_api_paths_supports_env_ubuntu_legacy_root(self) -> None:
        target = env_targets.get_target("prod0-main")
        completed = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout="/opt/env_ubuntu/secrets/services/onepanel-api.env\n"
            "/opt/env_ubuntu/agentplane/scripts/onepanel/api_request.py\n",
            stderr="",
        )

        with mock.patch.object(env_targets, "run_command", return_value=completed) as run_command:
            env_file, script = env_targets.resolve_api_paths(target)

        self.assertEqual(Path("/opt/env_ubuntu/secrets/services/onepanel-api.env"), env_file)
        self.assertEqual(Path("/opt/env_ubuntu/agentplane/scripts/onepanel/api_request.py"), script)
        run_command.assert_called_once()

    def test_resolve_remote_api_paths_supports_live_root_work_repo(self) -> None:
        target = env_targets.get_target("prod0-main")
        completed = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout="/root/work/AgentPlane/secrets/services/onepanel-api.env\n"
            "/root/work/AgentPlane/agentplane/scripts/onepanel/api_request.py\n",
            stderr="",
        )

        with mock.patch.object(env_targets, "run_command", return_value=completed) as run_command:
            env_file, script = env_targets.resolve_api_paths(target)

        self.assertEqual(Path("/root/work/AgentPlane/secrets/services/onepanel-api.env"), env_file)
        self.assertEqual(Path("/root/work/AgentPlane/agentplane/scripts/onepanel/api_request.py"), script)
        run_command.assert_called_once()

    def test_phase4_lane12_projection_fixture_apply_requires_execute_for_mutation_guardrail(self) -> None:
        result = self._run_cli(
            "projection",
            "fixture",
            "apply",
            "--target",
            "wsl",
            "--profile",
            "wsl-fixture",
            "--repo-root",
            str(REPO_ROOT),
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("requires --execute", result.stderr)


if __name__ == "__main__":
    unittest.main()
