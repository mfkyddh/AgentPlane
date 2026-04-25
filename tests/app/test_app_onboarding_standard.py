from __future__ import annotations

import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


class AppOnboardingStandardTests(unittest.TestCase):
    def test_reference_docs_for_app_onboarding_governance_exist(self) -> None:
        expected_paths = [
            "docs/reference/repository-structure.md",
            "docs/reference/app-repository-standard.md",
            "docs/reference/control-plane-naming-registry.md",
        ]

        for relative_path in expected_paths:
            with self.subTest(path=relative_path):
                self.assertTrue((REPO_ROOT / relative_path).is_file(), f"missing reference doc: {relative_path}")

    def test_readme_and_architecture_index_link_new_reference_docs(self) -> None:
        # README delegates to docs/README.md for detailed doc links
        architecture_index_text = (REPO_ROOT / "docs" / "architecture" / "README.md").read_text(encoding="utf-8")

        self.assertIn("[repository-structure.md](../reference/repository-structure.md)", architecture_index_text)
        self.assertIn("[app-repository-standard.md](../reference/app-repository-standard.md)", architecture_index_text)
        self.assertIn("[control-plane-naming-registry.md](../reference/control-plane-naming-registry.md)", architecture_index_text)

    def test_readme_prefers_bootstrap_first_startup_path(self) -> None:
        text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")

        self.assertIn("bootstrap inspect-local", text)
        self.assertIn("bootstrap init-secrets", text)
        self.assertIn("bootstrap verify-secrets", text)
        self.assertNotIn("onepanel-login.<target>.env", text)

    def test_bootstrap_runbook_uses_bootstrap_surface_as_day_zero_entry(self) -> None:
        text = (REPO_ROOT / "docs" / "runbooks" / "bootstrap-secrets.md").read_text(encoding="utf-8")

        self.assertIn("bootstrap inspect-local", text)
        self.assertIn("bootstrap init-secrets", text)
        self.assertIn("bootstrap verify-secrets", text)
        self.assertIn("bootstrap doctor", text)
        self.assertIn("onepanel-login.<target>.env", text)
        self.assertIn("不参与 bootstrap contract", text)
        self.assertIn("projection", text)

    def test_historical_superpowers_workspace_docs_are_removed_from_active_tree(self) -> None:
        self.assertFalse((REPO_ROOT / "docs" / "superpowers").exists())

    def test_repo_self_check_script_exists_and_runs_documented_checks(self) -> None:
        script_path = REPO_ROOT / "agentplane" / "scripts" / "internal" / "repo" / "self_check.sh"
        self.assertTrue(script_path.is_file(), msg=f"missing {script_path}")
        text = script_path.read_text(encoding="utf-8")

        self.assertIn("uv run python -m pytest", text)
        self.assertIn("tests/repository/test_docs_no_legacy_terms.py", text)
        self.assertIn("tests/repository/test_repo_snapshot_contracts.py", text)
        self.assertIn("tests/onepanel/test_onepanel_plugin_and_skills.py", text)
        self.assertIn("tests/app/test_app_onboarding_standard.py", text)
        self.assertNotIn("UV_PROJECT_ENVIRONMENT", text)

    def test_repo_ignores_only_the_single_default_venv(self) -> None:
        text = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8")

        self.assertIn(".venv/", text)
        self.assertNotIn(".venv-*/", text)

    def test_agents_doc_uses_compact_contract_sections(self) -> None:
        text = (REPO_ROOT / "AGENTS.md").read_text(encoding="utf-8")
        required_headings = (
            "## 必读摘要",
            "## 执行入口",
            "## 跨平台核心约束",
            "## 安全核心约束",
            "## Git 核心约束",
            "## 文档索引",
        )
        for heading in required_headings:
            with self.subTest(heading=heading):
                self.assertIn(heading, text)

    def test_app_collaboration_doc_calls_out_upstream_and_rollback_state(self) -> None:
        text = (REPO_ROOT / "docs" / "architecture" / "agentplane-app-collaboration.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("`origin` 指向你自己的可写仓库", text)
        self.assertIn("`upstream` 指向官方只读源", text)
        self.assertIn("发布前先创建回滚态", text)
        self.assertIn("回滚态", text)

    def test_app_delivery_runbook_makes_validate_contract_the_pre_deploy_gate(self) -> None:
        text = (REPO_ROOT / "docs" / "runbooks" / "app-project-delivery-workflow.md").read_text(
            encoding="utf-8"
        )

        self.assertIn("这是应用接入不变量的最早正式门禁", text)
        self.assertIn(
            "未通过前不进入 `build-artifact`、`ship-image`、`render-runtime`、`deploy`、`rollback` 或 `verify`",
            text,
        )
        self.assertIn("合同问题必须在这一步暴露", text)
        self.assertIn("`deploy --dry-run` 是部署计划入口，不是合同校验入口。", text)

        validation_section = text.split("### 4.4 最小本地验证", 1)[1].split("### 4.5", 1)[0]
        self.assertLess(
            validation_section.index("app delivery validate-contract"),
            validation_section.index("app delivery build-artifact"),
        )

    def test_app_repository_standard_keeps_second_app_fast_path_rules(self) -> None:
        text = (REPO_ROOT / "docs" / "reference" / "app-repository-standard.md").read_text(encoding="utf-8")

        self.assertIn("如果 target 之间入口、依赖或回退面不同，一开始就提供 target-aware 合同与摘要文件", text)
        self.assertIn("真实 app resource secrets 从首轮接入开始就固定放在 `secrets/hosts/<target>/apps/<app>/resources/`", text)
        self.assertIn("不为新接入项目再落一份 `secrets/app-resources/<target>/<app>/` 实体文件", text)
        self.assertIn("最终验收必须回到 catalog 指向的正式仓库根执行", text)

    def test_app_delivery_workflow_records_second_app_preflight_checks(self) -> None:
        text = (REPO_ROOT / "docs" / "runbooks" / "app-project-delivery-workflow.md").read_text(
            encoding="utf-8"
        )

        self.assertIn("### 4.6 第二个应用接入前的预检", text)
        self.assertIn("`--app-repo-root` 只用于临时 worktree 验证", text)
        self.assertIn("最终验收必须回到 catalog 指向的正式仓库根", text)
        self.assertIn("`deploy/agentplane/contract*.yaml`、`docs/AGENTPLANE_DEPLOYMENT.*.md`、`inventory/servers/<target>/...` 与 `secrets/hosts/<target>/...` 必须在同一轮变更里收口", text)
        self.assertIn("退役旧控制面时，不只删脚本和文案，还要删除 `secrets/app-resources/<target>/<app>/*.env` 实体旧文件", text)

    def test_authoring_rules_prefer_active_docs_over_historical_specs(self) -> None:
        text = (REPO_ROOT / "docs" / "maintainers" / "control-plane-authoring.md").read_text(
            encoding="utf-8"
        )

        self.assertIn("active docs 与现行 code/test 优先于历史 spec、plan、handoff", text)
        self.assertIn("不要把历史设计稿中的旧路径、旧文案、旧 rollback 形态重新抄回 active docs", text)


if __name__ == "__main__":
    unittest.main()
