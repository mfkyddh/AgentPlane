import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
ACTIVE_TEMPLATE_DOCS = (
    REPO_ROOT / "README.md",
    REPO_ROOT / "AGENTS.md",
    REPO_ROOT / "docs" / "architecture" / "README.md",
    REPO_ROOT / "docs" / "architecture" / "control-plane.md",
    REPO_ROOT / "docs" / "architecture" / "agentplane-app-collaboration.md",
    REPO_ROOT / "docs" / "architecture" / "linux-governance.md",
    REPO_ROOT / "docs" / "architecture" / "automation-stack.md",
    REPO_ROOT / "docs" / "reference" / "app-repository-standard.md",
    REPO_ROOT / "docs" / "runbooks" / "control-plane-domain-onboarding.md",
    REPO_ROOT / "docs" / "runbooks" / "control-plane-agent-execution-flow.md",
)
ACTIVE_TEMPLATE_SKILLS = (
    REPO_ROOT / ".codex" / "skills" / "onepanel-app-ops" / "SKILL.md",
    REPO_ROOT / ".codex" / "skills" / "onepanel-container-ops" / "SKILL.md",
    REPO_ROOT / ".codex" / "skills" / "onepanel-firewall-ops" / "SKILL.md",
    REPO_ROOT / ".codex" / "skills" / "onepanel-website-ops" / "SKILL.md",
)
README_CORE_CONTRACT_LINKS = (
    "[control-plane.md](docs/architecture/control-plane.md)",
    "[linux-governance.md](docs/architecture/linux-governance.md)",
    "[agentplane-app-collaboration.md](docs/architecture/agentplane-app-collaboration.md)",
)
ARCHITECTURE_CORE_CONTRACT_LINKS = (
    "[control-plane.md](control-plane.md)",
    "[linux-governance.md](linux-governance.md)",
    "[agentplane-app-collaboration.md](agentplane-app-collaboration.md)",
)
ARCHITECTURE_TEMPLATE_LINKS = (
    "[agent-first-template-truth-model.md](agent-first-template-truth-model.md)",
    "[control-plane-path-policy.md](../reference/control-plane-path-policy.md)",
    "[app-repository-standard.md](../reference/app-repository-standard.md)",
)
FORBIDDEN_TEMPLATE_DEFAULTS = (
    "/root/work/AgentPlane",
    "D:\\Projects\\AgentPlane",
    "ops.cli",
    "separate checkout",
    "separate checkouts",
)


def collect_active_docs() -> str:
    return "\n".join(path.read_text(encoding="utf-8") for path in ACTIVE_TEMPLATE_DOCS)


def collect_active_template_surface() -> str:
    files = (*ACTIVE_TEMPLATE_DOCS, *ACTIVE_TEMPLATE_SKILLS)
    return "\n".join(path.read_text(encoding="utf-8") for path in files)


class DocsNoLegacyTermsTests(unittest.TestCase):
    def test_template_docs_do_not_reintroduce_author_site_defaults(self) -> None:
        text = collect_active_template_surface()
        for forbidden in FORBIDDEN_TEMPLATE_DEFAULTS:
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, text)

    def test_readme_describes_template_bootstrap_path(self) -> None:
        text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")

        self.assertIn("fork / clone", text)
        self.assertIn("bootstrap inspect-local", text)
        self.assertIn("bootstrap init-secrets", text)
        self.assertIn("bootstrap verify-secrets", text)
        self.assertIn("bootstrap doctor", text)
        self.assertIn("让 Agent 接管", text)

    def test_readme_describes_template_truth_and_runtime_model(self) -> None:
        text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")

        self.assertIn("Agent-first control plane template repository", text)
        self.assertIn("Git tracked truth + local secrets", text)
        self.assertIn("Windows / Linux / macOS 只在 `resolver / backend` 层分叉", text)
        self.assertIn("人类输入面只剩 `secrets` 和少量 `identity`", text)
        self.assertIn("不再默认引用作者现场目录", text)

    def test_entry_indexes_link_template_contracts(self) -> None:
        readme_text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        architecture_index_text = (
            REPO_ROOT / "docs" / "architecture" / "README.md"
        ).read_text(encoding="utf-8")

        for link in README_CORE_CONTRACT_LINKS:
            with self.subTest(doc="README", link=link):
                self.assertIn(link, readme_text)

        for link in ARCHITECTURE_CORE_CONTRACT_LINKS:
            with self.subTest(doc="architecture", link=link):
                self.assertIn(link, architecture_index_text)

        for link in ARCHITECTURE_TEMPLATE_LINKS:
            with self.subTest(doc="architecture", link=link):
                self.assertIn(link, architecture_index_text)

        self.assertIn("[docs/history/index.md](docs/history/index.md)", readme_text)
        self.assertIn("[docs/archive/README.md](docs/archive/README.md)", readme_text)

    def test_agents_doc_declares_template_backend_aware_rules(self) -> None:
        text = (REPO_ROOT / "AGENTS.md").read_text(encoding="utf-8")

        self.assertIn("Agent-first control plane template repository", text)
        self.assertIn("Default to a host-entry-first, backend-aware workflow.", text)
        self.assertIn("On Windows hosts, use `pwsh` as the default local entry shell.", text)
        self.assertIn("`wsl.exe -e <program> <args...>`", text)
        self.assertIn(
            "Formal host-scoped remote execution must prefer `uv run python -m agentplane.cli host remote bash ...`.",
            text,
        )
        self.assertIn(
            "Control plane location determines the entry host; backend execution must route through resolver-provided workspace bindings.",
            text,
        )
        self.assertNotIn("retained as the WSL/Linux backend path during migration", text)

    def test_app_repository_standard_defines_template_boundary(self) -> None:
        text = (REPO_ROOT / "docs" / "reference" / "app-repository-standard.md").read_text(
            encoding="utf-8"
        )

        self.assertIn("应用仓库只负责代码、构建资产、合同与非敏感模板", text)
        self.assertIn("控制面模板仓库负责 bootstrap、正式执行、验证、回写与对外 runbook", text)
        self.assertIn("默认采用 host-entry-first, backend-aware", text)
        self.assertIn("不要再维护第二控制面", text)
        self.assertIn("`deploy/agentplane/contract.yaml`", text)
        self.assertNotIn("WSL-first", text)

    def test_domain_onboarding_and_execution_flow_use_template_placeholders(self) -> None:
        onboarding_text = (
            REPO_ROOT / "docs" / "runbooks" / "control-plane-domain-onboarding.md"
        ).read_text(encoding="utf-8")
        flow_text = (
            REPO_ROOT / "docs" / "runbooks" / "control-plane-agent-execution-flow.md"
        ).read_text(encoding="utf-8")

        self.assertIn("bootstrap inspect-local --repo-root <repo-root>", onboarding_text)
        self.assertIn("host inventory <target> --repo-root <repo-root>", onboarding_text)
        self.assertIn("只写 formal CLI、skill、runbook 与测试合同", onboarding_text)

        self.assertIn("bootstrap inspect-local --repo-root <repo-root>", flow_text)
        self.assertIn("bootstrap doctor --repo-root <repo-root>", flow_text)
        self.assertIn("Windows / Linux / macOS 只在 `resolver / backend` 层分叉", flow_text)
        self.assertIn("plan -> apply -> verify -> ledger -> inventory -> doc-sync", flow_text)
        self.assertIn("`pwsh`", flow_text)
        self.assertNotIn("确认当前在 WSL 环境执行", flow_text)

    def test_core_contract_docs_use_template_placeholders(self) -> None:
        control_plane = (REPO_ROOT / "docs" / "architecture" / "control-plane.md").read_text(
            encoding="utf-8"
        )
        collaboration = (
            REPO_ROOT / "docs" / "architecture" / "agentplane-app-collaboration.md"
        ).read_text(encoding="utf-8")
        governance = (REPO_ROOT / "docs" / "architecture" / "linux-governance.md").read_text(
            encoding="utf-8"
        )
        automation = (REPO_ROOT / "docs" / "architecture" / "automation-stack.md").read_text(
            encoding="utf-8"
        )

        self.assertIn("host inventory <target> --repo-root <repo-root>", control_plane)
        self.assertIn("service search --target <target> --repo-root <repo-root>", control_plane)
        self.assertIn(
            "website publish plan --target <target> --config-file <config-file> --cloudflare-env-file <cloudflare-env-file> --repo-root <repo-root>",
            control_plane,
        )
        self.assertIn(
            "app delivery validate-contract --target <target> --app <app> --repo-root <repo-root>",
            collaboration,
        )
        self.assertIn(
            "app delivery deploy --target <target> --app <app> --repo-root <repo-root> --image-ref <image:tag> --dry-run",
            collaboration,
        )
        self.assertIn("本页只定义 Linux / WSL backend 约束，不改变宿主入口选择。", governance)
        self.assertIn("[bootstrap-secrets.md](../runbooks/bootstrap-secrets.md)", governance)
        self.assertIn("host automation search <target> --repo-root <repo-root>", automation)
        self.assertIn(
            "projection verification run --target <target> --profile <profile> --repo-root <repo-root>",
            automation,
        )
        self.assertIn(
            "projection ledger refresh --target <target> --repo-root <repo-root> --write",
            automation,
        )


if __name__ == "__main__":
    unittest.main()
