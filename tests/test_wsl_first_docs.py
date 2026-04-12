import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
CORE_TEMPLATE_ENTRY_DOCS = (
    REPO_ROOT / "README.md",
    REPO_ROOT / "AGENTS.md",
    REPO_ROOT / "docs" / "reference" / "app-repository-standard.md",
    REPO_ROOT / "docs" / "runbooks" / "control-plane-agent-execution-flow.md",
)
FORBIDDEN_WINDOWS_SHELL_TERMS = (
    "powershell.exe",
    "Windows PowerShell",
)
FORBIDDEN_WSL_FIRST_TERMS = (
    "WSL-first",
    "默认工作流仍然是先进入 WSL",
)


class WslFirstDocsTests(unittest.TestCase):
    def test_core_template_docs_standardize_on_pwsh_not_legacy_powershell(self) -> None:
        for path in CORE_TEMPLATE_ENTRY_DOCS:
            text = path.read_text(encoding="utf-8")
            for term in FORBIDDEN_WINDOWS_SHELL_TERMS:
                with self.subTest(path=str(path), term=term):
                    self.assertNotIn(term, text)

    def test_repo_agents_doc_declares_pwsh_entry_and_backend_aware_routing(self) -> None:
        text = (REPO_ROOT / "AGENTS.md").read_text(encoding="utf-8")

        self.assertIn("On Windows hosts, use `pwsh` as the default local entry shell.", text)
        self.assertIn("`wsl.exe -e <program> <args...>`", text)
        self.assertIn("Default to a host-entry-first, backend-aware workflow.", text)
        self.assertIn(
            "Control plane location determines the entry host; source location determines the local execution host.",
            text,
        )

    def test_readme_and_flow_promote_backend_split_instead_of_wsl_first(self) -> None:
        readme_text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        flow_text = (
            REPO_ROOT / "docs" / "runbooks" / "control-plane-agent-execution-flow.md"
        ).read_text(encoding="utf-8")

        self.assertIn("`pwsh`", readme_text)
        self.assertIn("Windows / Linux / macOS 只在 `resolver / backend` 层分叉", readme_text)
        self.assertIn("`pwsh`", flow_text)
        self.assertIn("bootstrap inspect-local", flow_text)
        self.assertIn("resolver / backend", flow_text)

    def test_template_surface_docs_do_not_reintroduce_wsl_first_language(self) -> None:
        for path in CORE_TEMPLATE_ENTRY_DOCS:
            text = path.read_text(encoding="utf-8")
            for term in FORBIDDEN_WSL_FIRST_TERMS:
                with self.subTest(path=str(path), term=term):
                    self.assertNotIn(term, text)


if __name__ == "__main__":
    unittest.main()
