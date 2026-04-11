import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
CORE_WSL_FIRST_DOCS = (
    REPO_ROOT / "README.md",
    REPO_ROOT / "AGENTS.md",
    REPO_ROOT / "docs" / "architecture" / "linux-governance.md",
    REPO_ROOT / "docs" / "runbooks" / "wsl-host-governance.md",
)
FORBIDDEN_DEFAULT_FLOW_TERMS = (
    "wsl.exe",
    "powershell.exe",
    "pwsh.exe",
    "Windows PowerShell",
)


class WslFirstDocsTests(unittest.TestCase):
    def test_core_wsl_first_docs_do_not_default_to_windows_wrappers(self) -> None:
        for path in CORE_WSL_FIRST_DOCS:
            text = path.read_text(encoding="utf-8")
            for term in FORBIDDEN_DEFAULT_FLOW_TERMS:
                with self.subTest(path=str(path), term=term):
                    self.assertNotIn(term, text)

    def test_readme_prefers_formal_cli_over_direct_script_entrypoint(self) -> None:
        text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")

        self.assertNotIn("python3 agentplane/scripts/onepanel/project_lifecycle.py", text)
        self.assertNotIn("uv run python -m agentplane.cli onepanel --env prod0-main project search", text)
        self.assertIn("`onepanel` 只用于 provider/debug 低层对象核对与排障，不作为日常默认入口。", text)

    def test_phase4_runbooks_mark_remote_wrapper_as_compat_only(self) -> None:
        text = (REPO_ROOT / "docs" / "runbooks" / "powershell-wsl-remote-bash.md").read_text(encoding="utf-8")
        self.assertIn("兼容层", text)
        self.assertIn("不再作为长期主命令面", text)
        self.assertIn("agentplane/scripts/onepanel/api_request.py", text)
        self.assertIn("app_lifecycle.py", text)
        self.assertIn("project_lifecycle.py", text)
        self.assertIn("compat helper", text)
        self.assertIn("Formal catalog apps with `schema_version: 1` must use", text)

    def test_onepanel_lifecycle_runbook_keeps_compat_helpers_out_of_active_execution_path(self) -> None:
        text = (REPO_ROOT / "docs" / "runbooks" / "onepanel-app-lifecycle.md").read_text(encoding="utf-8")
        self.assertIn("compat、troubleshooting", text)
        self.assertIn("Formal catalog apps with `schema_version: 1` must use", text)

    def test_legacy_migration_runbook_marks_script_entrypoints_as_compat(self) -> None:
        text = (REPO_ROOT / "docs" / "runbooks" / "control-plane-legacy-migration.md").read_text(encoding="utf-8")
        self.assertIn("compat", text)
        self.assertIn("agentplane/scripts/remote/run_remote_bash.sh", text)
        self.assertIn("旧 skill", text)
        self.assertIn("api_request.py", text)
        self.assertIn("app_lifecycle.py", text)
        self.assertIn("project_lifecycle.py", text)
        self.assertIn("不得重新写成默认路径", text)

    def test_onepanel_helper_entrypoints_are_marked_as_compat(self) -> None:
        helper_expectations = {
            REPO_ROOT / "agentplane" / "scripts" / "onepanel" / "api_request.py": "Prefer `python -m agentplane.cli onepanel ...` for formal control-plane flows.",
            REPO_ROOT / "agentplane" / "scripts" / "onepanel" / "app_lifecycle.py": "Formal AgentPlane runbooks should route through `uv run python -m agentplane.cli ...`.",
            REPO_ROOT / "agentplane" / "scripts" / "onepanel" / "project_lifecycle.py": "Formal AgentPlane runbooks should route through `uv run python -m agentplane.cli onepanel ...`.",
        }

        for path, expected_phrase in helper_expectations.items():
            text = path.read_text(encoding="utf-8")
            with self.subTest(path=str(path)):
                self.assertIn("Compatibility entrypoint", text)
                self.assertIn(expected_phrase, text)

    def test_onepanel_compat_bridges_are_called_out_in_code(self) -> None:
        apps_text = (REPO_ROOT / "agentplane" / "cli" / "apps.py").read_text(encoding="utf-8")
        env_targets_text = (REPO_ROOT / "agentplane" / "scripts" / "onepanel" / "env_targets.py").read_text(encoding="utf-8")

        self.assertIn("Compatibility bridge", apps_text)
        self.assertIn("object_api-backed lifecycle steps", apps_text)
        self.assertIn("Future replacement must come from formal CLI capability", apps_text)
        self.assertIn("not continued expansion of script entrypoints", apps_text)
        self.assertIn("Compatibility contract", env_targets_text)


if __name__ == "__main__":
    unittest.main()
