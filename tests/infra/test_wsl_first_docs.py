import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CORE_TEMPLATE_ENTRY_DOCS = (
    REPO_ROOT / "README.md",
    REPO_ROOT / "AGENTS.md",
    REPO_ROOT / "docs" / "architecture" / "linux-governance.md",
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

        self.assertIn("Windows 上默认用 PowerShell", text)
        self.assertIn("`wsl.exe -e <程序>`", text)
        self.assertIn("Windows 和 WSL 共用同一个仓库目录", text)
        self.assertIn("只使用根目录 `.venv`", text)
        self.assertIn("远程 Linux 走 `agentplane infra remote bash`", text)

    def test_linux_governance_declares_backend_role_not_wsl_first_entry(self) -> None:
        text = (REPO_ROOT / "docs" / "architecture" / "linux-governance.md").read_text(
            encoding="utf-8"
        )

        self.assertIn("本页只定义 Linux / WSL backend 约束，不改变宿主入口选择。", text)
        self.assertIn("host-entry-first, backend-aware", text)
        self.assertIn("`pwsh -> formal CLI -> WSL/SSH backend`", text)
        self.assertNotIn("默认在当前 WSL shell 中直接执行 Linux 命令", text)
        self.assertNotIn("如果当前不在 WSL，会先进入 WSL", text)

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
        self.assertIn("Windows 与 WSL 默认共享同一份源码 checkout", flow_text)

    def test_template_surface_docs_do_not_reintroduce_wsl_first_language(self) -> None:
        for path in CORE_TEMPLATE_ENTRY_DOCS:
            text = path.read_text(encoding="utf-8")
            for term in FORBIDDEN_WSL_FIRST_TERMS:
                with self.subTest(path=str(path), term=term):
                    self.assertNotIn(term, text)


if __name__ == "__main__":
    unittest.main()
