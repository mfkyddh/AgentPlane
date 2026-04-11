import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
CORE_WINDOWS_ENTRY_DOCS = (
    REPO_ROOT / "AGENTS.md",
    REPO_ROOT / "docs" / "maintainers" / "control-plane-authoring.md",
    REPO_ROOT / "docs" / "runbooks" / "powershell-wsl-remote-bash.md",
)
FORBIDDEN_WINDOWS_SHELL_TERMS = (
    "powershell.exe",
    "Windows PowerShell",
)


class WslFirstDocsTests(unittest.TestCase):
    def test_core_windows_entry_docs_standardize_on_pwsh_not_legacy_powershell(self) -> None:
        for path in CORE_WINDOWS_ENTRY_DOCS:
            text = path.read_text(encoding="utf-8")
            for term in FORBIDDEN_WINDOWS_SHELL_TERMS:
                with self.subTest(path=str(path), term=term):
                    self.assertNotIn(term, text)

    def test_repo_agents_doc_declares_pwsh_entry_and_backend_aware_routing(self) -> None:
        text = (REPO_ROOT / "AGENTS.md").read_text(encoding="utf-8")

        self.assertIn("On Windows hosts, use `pwsh` as the default local entry shell.", text)
        self.assertIn("`wsl.exe -e <program> <args...>`", text)
        self.assertIn("Control plane location determines the entry host; source location determines the local execution host.", text)

    def test_remote_bash_runbook_promotes_pwsh_to_formal_windows_entry(self) -> None:
        text = (REPO_ROOT / "docs" / "runbooks" / "powershell-wsl-remote-bash.md").read_text(encoding="utf-8")

        self.assertIn("Windows 主控制面正式入口", text)
        self.assertIn("`pwsh`", text)
        self.assertIn("`wsl.exe -e <program> <args...>`", text)
        self.assertNotIn("补充入口", text)
        self.assertNotIn("默认工作流仍然是先进入 WSL", text)

    def test_runbook_keeps_compat_helper_scripts_out_of_active_execution_path(self) -> None:
        text = (REPO_ROOT / "docs" / "runbooks" / "powershell-wsl-remote-bash.md").read_text(encoding="utf-8")
        self.assertIn("兼容层", text)
        self.assertIn("不再作为长期主命令面", text)
        self.assertIn("agentplane/scripts/onepanel/api_request.py", text)
        self.assertIn("app_lifecycle.py", text)
        self.assertIn("project_lifecycle.py", text)
        self.assertIn("compat helper", text)
        self.assertIn("Formal catalog apps with `schema_version: 1` must use", text)

    def test_authoring_rules_switch_shared_baseline_to_pwsh_entry_plus_backend_awareness(self) -> None:
        text = (REPO_ROOT / "docs" / "maintainers" / "control-plane-authoring.md").read_text(encoding="utf-8")

        self.assertIn("Windows 上 `pwsh` 优先", text)
        self.assertIn("backend-aware", text)
        self.assertNotIn("| 共享 skill | WSL-first、正式入口基线、真源优先级、写后验证纪律 |", text)
        self.assertNotIn("每个 skill 都重复 WSL-first、`repo-root`、验证纪律", text)

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
