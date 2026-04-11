# AgentPlane Rebrand Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在新工作树里把 `OP_Linux` 一步到位硬切为 `AgentPlane`，同时完成 `sub2api` 的控制面 handoff 迁移，不保留旧名字、旧 CLI、旧合同目录或旧摘要文件兼容层。

**Architecture:** 先用测试冻结新的命名合同，确保 CLI、包名、active docs、plugin、自动化常量和 active app catalog 都以 `AgentPlane` 为唯一现役名字。然后在主控制面仓库里先完成 Python 包和 CLI 重命名，再统一修改 docs/skills/plugin/automation/inventory；最后在 `sub2api` 工作树里把 `deploy/op/` 和 `docs/OP_LINUX_DEPLOYMENT.*.md` 整体切到 `AgentPlane` 语义，并在全部 tracked 文件改完之后执行仓库根目录最终切换。

**Tech Stack:** Python 3, `argparse`, Hatchling, Markdown, JSON, TOML, Bash, `uv`, `pytest`, `rg`, `git worktree`

---

## File Map

- `/root/work/OP_Linux/.worktrees/codex/agentplane-rebrand/pyproject.toml`
  Python 包发布元数据。必须把 `project.name` 和 wheel packages 从 `op-linux-ops-cli` / `ops` 改到 `agentplane-cli` / `agentplane`。
- `/root/work/OP_Linux/.worktrees/codex/agentplane-rebrand/ops/`
  当前 Python 包根目录。实现阶段必须整体移动到 `/root/work/OP_Linux/.worktrees/codex/agentplane-rebrand/agentplane/`。
- `/root/work/OP_Linux/.worktrees/codex/agentplane-rebrand/README.md`
  主仓库入口。必须改成 `AgentPlane` 名称、`/root/work/AgentPlane` 路径和 `uv run python -m agentplane.cli ...` 命令。
- `/root/work/OP_Linux/.worktrees/codex/agentplane-rebrand/docs/architecture/control-plane.md`
  控制面核心合同。必须整体切到 `AgentPlane` / `agentplane.cli` 语义。
- `/root/work/OP_Linux/.worktrees/codex/agentplane-rebrand/docs/architecture/op-linux-app-collaboration.md`
  当前应用协作文档主名。必须移动到 `docs/architecture/agentplane-app-collaboration.md`，并更新所有链接。
- `/root/work/OP_Linux/.worktrees/codex/agentplane-rebrand/docs/architecture/README.md`
  architecture 索引。必须指向新的 `agentplane-app-collaboration.md`。
- `/root/work/OP_Linux/.worktrees/codex/agentplane-rebrand/docs/maintainers/control-plane-authoring.md`
  maintainer 规则文档。必须更新 `AgentPlane` 文案、CLI 示例和 app-collaboration 文档链接。
- `/root/work/OP_Linux/.worktrees/codex/agentplane-rebrand/docs/runbooks/app-project-delivery-workflow.md`
  应用协作 active runbook。必须改成 `AgentPlane` 和 `deploy/agentplane/` 语义。
- `/root/work/OP_Linux/.worktrees/codex/agentplane-rebrand/docs/runbooks/wsl-host-governance.md`
  WSL active runbook。必须改成 `/root/work/AgentPlane`。
- `/root/work/OP_Linux/.worktrees/codex/agentplane-rebrand/docs/runbooks/prod0-main-governance.md`
  prod0 active runbook。必须改掉 `OP_Linux`、`ops.cli` 和 `/opt/op_linux` / `/data/op_linux`。
- `/root/work/OP_Linux/.worktrees/codex/agentplane-rebrand/docs/runbooks/prod2-main-1panel-public-access.md`
  prod2 active runbook。必须改掉 `OP_Linux` 和 `ops.cli` 示例。
- `/root/work/OP_Linux/.worktrees/codex/agentplane-rebrand/.codex/skills/catalog.yaml`
  技能投影目录真源。必须把所有 `entrypoint` 从 `ops.cli` 改为 `agentplane.cli`，并让 plugin group 重新生成到 `agentplane-control-plane`。
- `/root/work/OP_Linux/.worktrees/codex/agentplane-rebrand/.codex/skills/app-delivery-ops/SKILL.md`
- `/root/work/OP_Linux/.worktrees/codex/agentplane-rebrand/.codex/skills/app-resource-ops/SKILL.md`
- `/root/work/OP_Linux/.worktrees/codex/agentplane-rebrand/.codex/skills/host-ops/SKILL.md`
  active repo-owned skills。必须改成 `AgentPlane` 和 `agentplane.cli`。
- `/root/work/OP_Linux/.worktrees/codex/agentplane-rebrand/plugins/op-linux-control-plane/`
  当前 plugin 目录。必须整体移动到 `plugins/agentplane-control-plane/`。
- `/root/work/OP_Linux/.worktrees/codex/agentplane-rebrand/plugins/op-linux-control-plane/.codex-plugin/plugin.json`
  plugin 元数据。必须把 `name`、`description`、`displayName`、`developerName` 改到 `AgentPlane`。
- `/root/work/OP_Linux/.worktrees/codex/agentplane-rebrand/plugins/op-linux-control-plane/README.md`
  plugin 文档。必须改成 `AgentPlane`。
- `/root/work/OP_Linux/.worktrees/codex/agentplane-rebrand/ops/scripts/automation/generate_skill_projections.py`
  技能投影生成器。移动到 `agentplane/scripts/automation/generate_skill_projections.py` 后，必须把 plugin root、skill 名、描述和 CLI entrypoint 都切成 `AgentPlane`。
- `/root/work/OP_Linux/.worktrees/codex/agentplane-rebrand/ops/scripts/automation/backup_secrets_r2.py`
  自动化备份默认常量。移动后必须把 `DEFAULT_SOURCE_DIR`、`DEFAULT_STATE_FILE`、`DEFAULT_TMP_DIR`、`DEFAULT_BUCKET`、`DEFAULT_PREFIX`、`TASK_NAME` 改到 `agentplane`。
- `/root/work/OP_Linux/.worktrees/codex/agentplane-rebrand/templates/services/secrets-backup.r2.wsl.env.example`
  secrets 备份 env 模板。必须改成 `/root/work/AgentPlane`、`/data/agentplane`、`AgentPlane_Backups`、`backups/agentplane/...`。
- `/root/work/OP_Linux/.worktrees/codex/agentplane-rebrand/.codex/environments/actions/dev.sh`
  Codex 本地动作入口。必须改成 `uv run python -m agentplane.cli --help`。
- `/root/work/OP_Linux/.worktrees/codex/agentplane-rebrand/.codex/environments/environment.toml`
  环境说明。必须把开头的 `OP_Linux` 改成 `AgentPlane`。
- `/root/work/OP_Linux/.worktrees/codex/agentplane-rebrand/inventory/apps/catalog.json`
  active formal app catalog。必须只保留 `sub2api`，且合同路径切到 `deploy/agentplane/contract*.yaml`。
- `/root/work/OP_Linux/.worktrees/codex/agentplane-rebrand/inventory/servers/wsl/ledgers/automations.json`
- `/root/work/OP_Linux/.worktrees/codex/agentplane-rebrand/inventory/servers/wsl/ledgers/automations.md`
  自动化 ledger。必须改成 `wsl-agentplane-secrets-backup` 和 `agentplane.cli`。
- `/root/work/OP_Linux/.worktrees/codex/agentplane-rebrand/tests/test_cli_entrypoints.py`
  CLI 入口测试。必须把 `-m ops.cli` 改成 `-m agentplane.cli`。
- `/root/work/OP_Linux/.worktrees/codex/agentplane-rebrand/tests/test_project_lifecycle_acceptance.py`
  acceptance 测试。必须把 `from ops...` 和 `-m ops.cli` 改成 `agentplane`。
- `/root/work/OP_Linux/.worktrees/codex/agentplane-rebrand/tests/test_pyproject_config.py`
  pyproject 合同测试。必须冻结 `agentplane-cli` 和 `agentplane` wheel package。
- `/root/work/OP_Linux/.worktrees/codex/agentplane-rebrand/tests/test_docs_no_legacy_terms.py`
  active docs 合同测试。必须禁止 `OP_Linux` / `ops.cli` 出现在 active docs，并要求 `AgentPlane` / `agentplane.cli`。
- `/root/work/OP_Linux/.worktrees/codex/agentplane-rebrand/tests/test_onepanel_plugin_and_skills.py`
  plugin 和技能生成测试。必须冻结新的 plugin 目录和 `agentplane.cli` entrypoint。
- `/root/work/OP_Linux/.worktrees/codex/agentplane-rebrand/tests/test_secrets_backup_r2.py`
  secrets 备份常量测试。必须冻结新 bucket / prefix / task name。
- `/root/work/OP_Linux/.worktrees/codex/agentplane-rebrand/tests/test_app_object_cli.py`
  real tracked catalog / apps ledger 测试。必须改成只冻结 `sub2api`。
- `/root/work/OP_Linux/.worktrees/codex/agentplane-rebrand/tests/test_app_object_lifecycle.py`
  catalog 生命周期测试。必须允许 active catalog 只剩 `sub2api`。
- `/root/work/sub2api/.worktrees/codex/agentplane-handoff/README.md`
  `sub2api` 主入口。必须把正式控制面从 `/root/work/OP_Linux` 切到 `/root/work/AgentPlane`。
- `/root/work/sub2api/.worktrees/codex/agentplane-handoff/AGENTS.md`
  仓库协作规则。必须把 `OP_Linux` / `ops.cli` / `deploy/op` / `OP_LINUX_DEPLOYMENT` 全部切到新名字。
- `/root/work/sub2api/.worktrees/codex/agentplane-handoff/deploy/README.md`
  handoff 目录说明。必须改成 `deploy/agentplane/`。
- `/root/work/sub2api/.worktrees/codex/agentplane-handoff/deploy/op/`
  当前 handoff 合同目录。必须整体移动到 `/root/work/sub2api/.worktrees/codex/agentplane-handoff/deploy/agentplane/`。
- `/root/work/sub2api/.worktrees/codex/agentplane-handoff/docs/OP_LINUX_DEPLOYMENT.prod0-main.md`
- `/root/work/sub2api/.worktrees/codex/agentplane-handoff/docs/OP_LINUX_DEPLOYMENT.prod2-main.md`
- `/root/work/sub2api/.worktrees/codex/agentplane-handoff/docs/OP_LINUX_DEPLOYMENT.wsl.md`
  当前非敏感交接摘要。必须整体移动到 `docs/AGENTPLANE_DEPLOYMENT.*.md`。
- `/root/work/sub2api/.worktrees/codex/agentplane-handoff/docs/README.md`
- `/root/work/sub2api/.worktrees/codex/agentplane-handoff/docs/owner/README.md`
  docs 索引。必须更新到新的摘要文件名和 `AgentPlane` 文案。
- `/root/work/sub2api/.worktrees/codex/agentplane-handoff/.agents/skills/README.md`
- `/root/work/sub2api/.worktrees/codex/agentplane-handoff/.agents/skills/sub2api-prod-deploy/SKILL.md`
- `/root/work/sub2api/.worktrees/codex/agentplane-handoff/.agents/skills/sub2api-source-build/SKILL.md`
  repo-local skills。必须改成 `/root/work/AgentPlane` 和 `agentplane.cli`。
- `/root/work/sub2api/.worktrees/codex/agentplane-handoff/tools/git/test-active-formal-surface.sh`
  active handoff 面守卫脚本。必须从 `OP_Linux` / `deploy/op` / `OP_LINUX_DEPLOYMENT` 切到 `AgentPlane` / `deploy/agentplane` / `AGENTPLANE_DEPLOYMENT`。

### Task 1: 冻结 AgentPlane 命名合同测试

**Files:**
- Modify: `/root/work/OP_Linux/.worktrees/codex/agentplane-rebrand/tests/test_cli_entrypoints.py`
- Modify: `/root/work/OP_Linux/.worktrees/codex/agentplane-rebrand/tests/test_project_lifecycle_acceptance.py`
- Modify: `/root/work/OP_Linux/.worktrees/codex/agentplane-rebrand/tests/test_pyproject_config.py`
- Modify: `/root/work/OP_Linux/.worktrees/codex/agentplane-rebrand/tests/test_docs_no_legacy_terms.py`
- Modify: `/root/work/OP_Linux/.worktrees/codex/agentplane-rebrand/tests/test_onepanel_plugin_and_skills.py`
- Modify: `/root/work/OP_Linux/.worktrees/codex/agentplane-rebrand/tests/test_secrets_backup_r2.py`
- Modify: `/root/work/OP_Linux/.worktrees/codex/agentplane-rebrand/tests/test_app_object_cli.py`
- Modify: `/root/work/OP_Linux/.worktrees/codex/agentplane-rebrand/tests/test_app_object_lifecycle.py`

- [ ] **Step 1: 把 CLI runner 和 Python import 的失败测试先切到 `agentplane`**

在 `tests/test_cli_entrypoints.py` 和 `tests/test_project_lifecycle_acceptance.py` 中先把入口改成新模块：

```python
return subprocess.run(
    [sys.executable, "-m", "agentplane.cli", *args],
    cwd=REPO_ROOT,
    text=True,
    capture_output=True,
    check=False,
)
```

以及：

```python
from agentplane.domain.app.resource_paths import (
    app_resource_secret_dir,
    app_resource_secret_relative,
)
```

- [ ] **Step 2: 把 pyproject、docs、plugin、automation 常量断言改成 AgentPlane**

在 `tests/test_pyproject_config.py` 中改成：

```python
self.assertEqual("agentplane-cli", payload["project"]["name"])
self.assertEqual(["agentplane"], payload["tool"]["hatch"]["build"]["targets"]["wheel"]["packages"])
```

在 `tests/test_docs_no_legacy_terms.py`、`tests/test_onepanel_plugin_and_skills.py`、`tests/test_secrets_backup_r2.py` 中加入或替换为：

```python
self.assertIn("uv run python -m agentplane.cli", text)
self.assertNotIn("uv run python -m ops.cli", text)
self.assertIn("/root/work/AgentPlane", text)
self.assertNotIn("/root/work/OP_Linux", text)
```

```python
plugin_root = REPO_ROOT / "plugins" / "agentplane-control-plane" / "skills"
self.assertEqual("agentplane-control-plane-apps", frontmatter["name"])
self.assertIn("uv run python -m agentplane.cli app ...", plugin_skill_text)
```

```python
from agentplane.scripts.automation.backup_secrets_r2 import BackupConfig

self.assertEqual("AgentPlane_Backups", config.bucket)
self.assertEqual("backups/agentplane/secrets-main", config.prefix)
```

- [ ] **Step 3: 把 real tracked app catalog 与 apps ledger 测试改成只保留 `sub2api`**

在 `tests/test_app_object_cli.py` 中把 real catalog 冻结改成：

```python
self.assertEqual(
    {
        "apps": [
            {
                "app": "sub2api",
                "repo_name": "sub2api",
                "repo_root": "/root/work/sub2api",
                "service_key": "sub2api",
                "contracts": {
                    "wsl": "deploy/agentplane/contract.wsl.yaml",
                    "prod0-main": "deploy/agentplane/contract.yaml",
                    "prod2-main": "deploy/agentplane/contract.prod2.yaml",
                },
            }
        ]
    },
    payload,
)
```

并把搜索与 ledger 断言改成：

```python
self.assertEqual(["sub2api"], [item["app"] for item in payload_json["payload"]["items"]])
self.assertEqual(
    "/root/work/sub2api/deploy/agentplane/contract.yaml",
    payload_json["payload"]["items"][0]["contract_file"],
)
```

```python
self.assertEqual(["sub2api"], [item["app"] for item in items])
self.assertIn("`sub2api` / `compose`", ledger_markdown)
self.assertNotIn("`newapi` / `compose`", ledger_markdown)
self.assertNotIn("`sub2apipay` / `compose`", ledger_markdown)
```

在 `tests/test_app_object_lifecycle.py` 中把真实 catalog 预期简化成：

```python
self.assertEqual(["sub2api"], [item["app"] for item in apps])
```

- [ ] **Step 4: 运行冻结测试，确认它们先红在旧名字和旧 catalog 上**

Run:

```bash
cd /root/work/OP_Linux/.worktrees/codex/agentplane-rebrand
uv run python -m pytest \
  tests/test_cli_entrypoints.py \
  tests/test_project_lifecycle_acceptance.py \
  tests/test_pyproject_config.py \
  tests/test_docs_no_legacy_terms.py \
  tests/test_onepanel_plugin_and_skills.py \
  tests/test_secrets_backup_r2.py \
  tests/test_app_object_cli.py \
  tests/test_app_object_lifecycle.py -q
```

Expected:

- `ModuleNotFoundError` 或 `No module named agentplane`
- `uv run python -m ops.cli` 仍残留导致 docs/plugin 断言失败
- real tracked catalog 仍包含 `newapi`、`sub2apipay`

- [ ] **Step 5: 提交测试冻结**

```bash
cd /root/work/OP_Linux/.worktrees/codex/agentplane-rebrand
git add \
  tests/test_cli_entrypoints.py \
  tests/test_project_lifecycle_acceptance.py \
  tests/test_pyproject_config.py \
  tests/test_docs_no_legacy_terms.py \
  tests/test_onepanel_plugin_and_skills.py \
  tests/test_secrets_backup_r2.py \
  tests/test_app_object_cli.py \
  tests/test_app_object_lifecycle.py
git commit -m "test: freeze AgentPlane rename contract"
```

### Task 2: 主仓库 Python 包与 CLI 硬切

**Files:**
- Move: `/root/work/OP_Linux/.worktrees/codex/agentplane-rebrand/ops` -> `/root/work/OP_Linux/.worktrees/codex/agentplane-rebrand/agentplane`
- Modify: `/root/work/OP_Linux/.worktrees/codex/agentplane-rebrand/pyproject.toml`
- Modify: `/root/work/OP_Linux/.worktrees/codex/agentplane-rebrand/.codex/environments/actions/dev.sh`
- Modify: `/root/work/OP_Linux/.worktrees/codex/agentplane-rebrand/.codex/environments/environment.toml`
- Modify: all Python imports and `-m ops.cli` strings under `/root/work/OP_Linux/.worktrees/codex/agentplane-rebrand/agentplane`
- Modify: all Python test imports and `-m ops.cli` strings under `/root/work/OP_Linux/.worktrees/codex/agentplane-rebrand/tests`

- [ ] **Step 1: 先移动包目录并更新 `pyproject.toml`**

Run:

```bash
cd /root/work/OP_Linux/.worktrees/codex/agentplane-rebrand
git mv ops agentplane
```

然后把 `pyproject.toml` 改成：

```toml
[project]
name = "agentplane-cli"
version = "0.1.0"
description = "Minimal governance CLI for AgentPlane"
requires-python = ">=3.12"

[tool.hatch.build.targets.wheel]
packages = ["agentplane"]
```

- [ ] **Step 2: 把 Python import 与 CLI module string 全量切到 `agentplane`**

Run:

```bash
cd /root/work/OP_Linux/.worktrees/codex/agentplane-rebrand
rg -l 'from ops\.|import ops\.|"ops\.cli"|'\''ops\.cli'\''' agentplane tests \
  | xargs perl -0pi -e 's/from ops\./from agentplane\./g; s/import ops\./import agentplane\./g; s/"ops\.cli"/"agentplane.cli"/g; s/'\''ops\.cli'\''/'\''agentplane.cli'\''/g'
```

然后检查关键入口文件至少包含：

```python
from agentplane.cli.host import add_host_parser, handle_host_command
from agentplane.cli.service import add_service_parser, handle_service_command
from agentplane.cli.website import add_website_parser, handle_website_command
```

以及：

```python
if __name__ == "__main__":
    raise SystemExit(main())
```

位于 `/root/work/OP_Linux/.worktrees/codex/agentplane-rebrand/agentplane/cli/__main__.py`。

- [ ] **Step 3: 更新 Codex 环境动作入口**

把 `.codex/environments/actions/dev.sh` 改成：

```bash
#!/usr/bin/env bash
set -euo pipefail

uv run python -m agentplane.cli --help
```

把 `.codex/environments/environment.toml` 开头改成：

```toml
# Codex local environment contract for AgentPlane.
```

- [ ] **Step 4: 运行 CLI 与 import 最小验证**

Run:

```bash
cd /root/work/OP_Linux/.worktrees/codex/agentplane-rebrand
uv run python -m agentplane.cli --help
uv run python -m pytest \
  tests/test_cli_entrypoints.py \
  tests/test_project_lifecycle_acceptance.py \
  tests/test_pyproject_config.py -q
```

Expected:

- `uv run python -m agentplane.cli --help` 返回 0
- 这三组测试通过
- docs/plugin/catalog 相关测试仍可能失败，因为还没改 active surface

- [ ] **Step 5: 提交包名与 CLI 硬切**

```bash
cd /root/work/OP_Linux/.worktrees/codex/agentplane-rebrand
git add pyproject.toml .codex/environments/actions/dev.sh .codex/environments/environment.toml agentplane tests
git commit -m "refactor: rename ops package to agentplane"
```

### Task 3: 主仓库 active docs、skills、plugin、自动化常量全部切到 AgentPlane

**Files:**
- Modify: `/root/work/OP_Linux/.worktrees/codex/agentplane-rebrand/README.md`
- Move: `/root/work/OP_Linux/.worktrees/codex/agentplane-rebrand/docs/architecture/op-linux-app-collaboration.md` -> `/root/work/OP_Linux/.worktrees/codex/agentplane-rebrand/docs/architecture/agentplane-app-collaboration.md`
- Modify: `/root/work/OP_Linux/.worktrees/codex/agentplane-rebrand/docs/architecture/README.md`
- Modify: `/root/work/OP_Linux/.worktrees/codex/agentplane-rebrand/docs/architecture/control-plane.md`
- Modify: `/root/work/OP_Linux/.worktrees/codex/agentplane-rebrand/docs/maintainers/control-plane-authoring.md`
- Modify: `/root/work/OP_Linux/.worktrees/codex/agentplane-rebrand/docs/runbooks/app-project-delivery-workflow.md`
- Modify: `/root/work/OP_Linux/.worktrees/codex/agentplane-rebrand/docs/runbooks/wsl-host-governance.md`
- Modify: `/root/work/OP_Linux/.worktrees/codex/agentplane-rebrand/docs/runbooks/prod0-main-governance.md`
- Modify: `/root/work/OP_Linux/.worktrees/codex/agentplane-rebrand/docs/runbooks/prod2-main-1panel-public-access.md`
- Modify: `/root/work/OP_Linux/.worktrees/codex/agentplane-rebrand/.codex/skills/catalog.yaml`
- Modify: `/root/work/OP_Linux/.worktrees/codex/agentplane-rebrand/.codex/skills/app-delivery-ops/SKILL.md`
- Modify: `/root/work/OP_Linux/.worktrees/codex/agentplane-rebrand/.codex/skills/app-resource-ops/SKILL.md`
- Modify: `/root/work/OP_Linux/.worktrees/codex/agentplane-rebrand/.codex/skills/host-ops/SKILL.md`
- Move: `/root/work/OP_Linux/.worktrees/codex/agentplane-rebrand/plugins/op-linux-control-plane` -> `/root/work/OP_Linux/.worktrees/codex/agentplane-rebrand/plugins/agentplane-control-plane`
- Modify: `/root/work/OP_Linux/.worktrees/codex/agentplane-rebrand/plugins/agentplane-control-plane/.codex-plugin/plugin.json`
- Modify: `/root/work/OP_Linux/.worktrees/codex/agentplane-rebrand/plugins/agentplane-control-plane/README.md`
- Modify: `/root/work/OP_Linux/.worktrees/codex/agentplane-rebrand/agentplane/scripts/automation/generate_skill_projections.py`
- Modify: `/root/work/OP_Linux/.worktrees/codex/agentplane-rebrand/agentplane/scripts/automation/backup_secrets_r2.py`
- Modify: `/root/work/OP_Linux/.worktrees/codex/agentplane-rebrand/templates/services/secrets-backup.r2.wsl.env.example`
- Modify: `/root/work/OP_Linux/.worktrees/codex/agentplane-rebrand/inventory/servers/wsl/ledgers/automations.json`
- Modify: `/root/work/OP_Linux/.worktrees/codex/agentplane-rebrand/inventory/servers/wsl/ledgers/automations.md`
- Test: `/root/work/OP_Linux/.worktrees/codex/agentplane-rebrand/tests/test_docs_no_legacy_terms.py`
- Test: `/root/work/OP_Linux/.worktrees/codex/agentplane-rebrand/tests/test_onepanel_plugin_and_skills.py`
- Test: `/root/work/OP_Linux/.worktrees/codex/agentplane-rebrand/tests/test_secrets_backup_r2.py`

- [ ] **Step 1: 先改 active docs 主名、主链接和命令示例**

Run:

```bash
cd /root/work/OP_Linux/.worktrees/codex/agentplane-rebrand
git mv docs/architecture/op-linux-app-collaboration.md docs/architecture/agentplane-app-collaboration.md
```

然后把 `README.md` 和 active docs 里的示例切成：

```markdown
# AgentPlane

`AgentPlane` 是 Linux / WSL 主机、基础设施服务和正式控制面的治理仓库。

日常自动化统一从 `uv run python -m agentplane.cli ...` 进入。
```

以及：

```markdown
- 应用仓库接入看 [agentplane-app-collaboration.md](docs/architecture/agentplane-app-collaboration.md)
- 常用主机清理计划：`uv run python -m agentplane.cli host cleanup plan wsl --repo-root /root/work/AgentPlane`
```

- [ ] **Step 2: 把 skill catalog、plugin 目录和技能投影生成器改成 AgentPlane**

先移动 plugin 目录：

```bash
cd /root/work/OP_Linux/.worktrees/codex/agentplane-rebrand
git mv plugins/op-linux-control-plane plugins/agentplane-control-plane
```

把 `.codex/skills/catalog.yaml` 的 entrypoint 改成：

```yaml
entrypoint: uv run python -m agentplane.cli app
```

```yaml
entrypoint: uv run python -m agentplane.cli projection
```

把 `agentplane/scripts/automation/generate_skill_projections.py` 改成：

```python
PLUGIN_SKILLS_ROOT = Path("plugins/agentplane-control-plane/skills")

def _plugin_skill_name(group_name: str) -> str:
    return f"agentplane-control-plane-{group_name}"

def _plugin_description(group_name: str) -> str:
    return f"Generated plugin skill group for {group_name}; routes to AgentPlane CLI-first commands."

def _plugin_entrypoint(group_name: str) -> str:
    if group_name == "websites":
        return "uv run python -m agentplane.cli website ..."
    if group_name == "containers":
        return "uv run python -m agentplane.cli service ..."
    if group_name == "apps":
        return "uv run python -m agentplane.cli app ..."
    if group_name == "ledgers":
        return "uv run python -m agentplane.cli projection ..."
    if group_name in {"cronjobs", "firewall"}:
        return "uv run python -m agentplane.cli onepanel --env <target> ... --json"
    return "uv run python -m agentplane.cli ..."
```

把 `plugins/agentplane-control-plane/.codex-plugin/plugin.json` 至少改成：

```json
{
  "name": "agentplane-control-plane",
  "description": "CLI-first AgentPlane control-plane plugin for 1Panel, ledgers, tenants, and host operations.",
  "author": {
    "name": "AgentPlane",
    "email": "ops@example.invalid"
  },
  "interface": {
    "displayName": "AgentPlane Control Plane",
    "shortDescription": "CLI-first operations for 1Panel and AgentPlane assets.",
    "longDescription": "Thin plugin layer over the repository-owned Python CLI for 1Panel objects, ledgers, tenants, and host-first operations.",
    "developerName": "AgentPlane"
  }
}
```

- [ ] **Step 3: 改自动化常量、备份路径和 env 模板**

把 `agentplane/scripts/automation/backup_secrets_r2.py` 改成：

```python
DEFAULT_SOURCE_DIR = Path("/root/work/AgentPlane/secrets")
DEFAULT_STATE_FILE = Path("/data/agentplane/secrets-backup/state.json")
DEFAULT_TMP_DIR = Path("/tmp/agentplane-secrets-backup")
DEFAULT_BUCKET = "AgentPlane_Backups"
DEFAULT_PREFIX = "backups/agentplane/secrets-main"
TASK_NAME = "wsl-agentplane-secrets-backup"
```

把 `templates/services/secrets-backup.r2.wsl.env.example` 改成：

```env
SECRETS_BACKUP_SOURCE_DIR=/root/work/AgentPlane/secrets
SECRETS_BACKUP_STATE_FILE=/data/agentplane/secrets-backup/state.json
SECRETS_BACKUP_TMP_DIR=/tmp/agentplane-secrets-backup
SECRETS_BACKUP_BUCKET=AgentPlane_Backups
SECRETS_BACKUP_PREFIX=backups/agentplane/secrets-main
```

把 `inventory/servers/wsl/ledgers/automations.json` 和 `.md` 中的命令串改成：

```json
"command": "uv run python -m agentplane.cli host automation apply wsl --name wsl-agentplane-secrets-backup --operation run --execute"
```

- [ ] **Step 4: 重跑技能投影并验证 docs/plugin/automation**

Run:

```bash
cd /root/work/OP_Linux/.worktrees/codex/agentplane-rebrand
uv run python -m agentplane.scripts.automation.generate_skill_projections --repo-root .
uv run python -m pytest \
  tests/test_docs_no_legacy_terms.py \
  tests/test_onepanel_plugin_and_skills.py \
  tests/test_secrets_backup_r2.py -q
```

Expected:

- 生成的 plugin skills 落在 `plugins/agentplane-control-plane/skills/*/SKILL.md`
- 这三组测试通过

- [ ] **Step 5: 提交主仓库 active surface 改名**

```bash
cd /root/work/OP_Linux/.worktrees/codex/agentplane-rebrand
git add \
  README.md \
  docs \
  .codex/skills \
  plugins \
  agentplane/scripts/automation \
  templates/services/secrets-backup.r2.wsl.env.example \
  inventory/servers/wsl/ledgers/automations.json \
  inventory/servers/wsl/ledgers/automations.md
git commit -m "refactor: rename active control-plane surface to AgentPlane"
```

### Task 4: 收紧 active formal app catalog 到 `sub2api`

**Files:**
- Modify: `/root/work/OP_Linux/.worktrees/codex/agentplane-rebrand/inventory/apps/catalog.json`
- Modify: `/root/work/OP_Linux/.worktrees/codex/agentplane-rebrand/tests/test_app_object_cli.py`
- Modify: `/root/work/OP_Linux/.worktrees/codex/agentplane-rebrand/tests/test_app_object_lifecycle.py`
- Modify: `/root/work/OP_Linux/.worktrees/codex/agentplane-rebrand/inventory/servers/wsl/ledgers/apps.json`
- Modify: `/root/work/OP_Linux/.worktrees/codex/agentplane-rebrand/inventory/servers/wsl/ledgers/apps.md`
- Modify: `/root/work/OP_Linux/.worktrees/codex/agentplane-rebrand/inventory/servers/prod0-main/ledgers/apps.json`
- Modify: `/root/work/OP_Linux/.worktrees/codex/agentplane-rebrand/inventory/servers/prod0-main/ledgers/apps.md`
- Modify: `/root/work/OP_Linux/.worktrees/codex/agentplane-rebrand/inventory/servers/prod2-main/ledgers/apps.json`
- Modify: `/root/work/OP_Linux/.worktrees/codex/agentplane-rebrand/inventory/servers/prod2-main/ledgers/apps.md`

- [ ] **Step 1: 先把 tracked catalog 直接改成只保留 `sub2api`**

把 `inventory/apps/catalog.json` 改成：

```json
{
  "apps": [
    {
      "app": "sub2api",
      "repo_name": "sub2api",
      "repo_root": "/root/work/sub2api",
      "service_key": "sub2api",
      "contracts": {
        "wsl": "deploy/agentplane/contract.wsl.yaml",
        "prod0-main": "deploy/agentplane/contract.yaml",
        "prod2-main": "deploy/agentplane/contract.prod2.yaml"
      }
    }
  ]
}
```

- [ ] **Step 2: 用正式命令刷新 apps ledger，覆盖 `newapi` / `sub2apipay` 的旧 app-object 痕迹**

Run:

```bash
cd /root/work/OP_Linux/.worktrees/codex/agentplane-rebrand
uv run python -m agentplane.cli app object refresh-ledger --target wsl --repo-root . --write
uv run python -m agentplane.cli app object refresh-ledger --target prod0-main --repo-root . --write
uv run python -m agentplane.cli app object refresh-ledger --target prod2-main --repo-root . --write
```

Expected:

- 三个 target 的 `inventory/servers/*/ledgers/apps.json` 都只剩 `sub2api`
- `apps.md` 不再提 `newapi` 和 `sub2apipay`

- [ ] **Step 3: 把 real tracked app-object 测试同步到新的 ledger 结果**

在 `tests/test_app_object_cli.py` 中保留如下断言：

```python
ledger_json = json.loads(
    (REPO_ROOT / "inventory" / "servers" / target / "ledgers" / "apps.json").read_text(encoding="utf-8")
)
items = ledger_json["items"]
self.assertEqual(["sub2api"], [item["app"] for item in items])
self.assertEqual(
    "/root/work/sub2api/deploy/agentplane/contract.yaml" if target == "prod0-main" else
    "/root/work/sub2api/deploy/agentplane/contract.prod2.yaml" if target == "prod2-main" else
    "/root/work/sub2api/deploy/agentplane/contract.wsl.yaml",
    items[0]["contract_file"],
)
```

并在 `tests/test_app_object_lifecycle.py` 中把 active catalog 的最终预期保留为：

```python
self.assertEqual(["sub2api"], [item["app"] for item in apps])
```

- [ ] **Step 4: 跑 app-object 最小回归**

Run:

```bash
cd /root/work/OP_Linux/.worktrees/codex/agentplane-rebrand
uv run python -m pytest \
  tests/test_app_object_cli.py \
  tests/test_app_object_lifecycle.py -q
```

Expected:

- 通过
- real tracked catalog / ledger 只保留 `sub2api`

- [ ] **Step 5: 提交 active catalog 收口**

```bash
cd /root/work/OP_Linux/.worktrees/codex/agentplane-rebrand
git add inventory/apps/catalog.json inventory/servers/wsl/ledgers/apps.* inventory/servers/prod0-main/ledgers/apps.* inventory/servers/prod2-main/ledgers/apps.* tests/test_app_object_cli.py tests/test_app_object_lifecycle.py
git commit -m "refactor: keep only sub2api in active app catalog"
```

### Task 5: 把 `sub2api` handoff surface 硬切到 AgentPlane

**Files:**
- Modify: `/root/work/sub2api/.worktrees/codex/agentplane-handoff/README.md`
- Modify: `/root/work/sub2api/.worktrees/codex/agentplane-handoff/AGENTS.md`
- Modify: `/root/work/sub2api/.worktrees/codex/agentplane-handoff/deploy/README.md`
- Move: `/root/work/sub2api/.worktrees/codex/agentplane-handoff/deploy/op` -> `/root/work/sub2api/.worktrees/codex/agentplane-handoff/deploy/agentplane`
- Modify: `/root/work/sub2api/.worktrees/codex/agentplane-handoff/deploy/agentplane/contract.wsl.yaml`
- Modify: `/root/work/sub2api/.worktrees/codex/agentplane-handoff/deploy/agentplane/contract.yaml`
- Modify: `/root/work/sub2api/.worktrees/codex/agentplane-handoff/deploy/agentplane/contract.prod2.yaml`
- Modify: `/root/work/sub2api/.worktrees/codex/agentplane-handoff/deploy/agentplane/runtime.env.example`
- Move: `/root/work/sub2api/.worktrees/codex/agentplane-handoff/docs/OP_LINUX_DEPLOYMENT.wsl.md` -> `/root/work/sub2api/.worktrees/codex/agentplane-handoff/docs/AGENTPLANE_DEPLOYMENT.wsl.md`
- Move: `/root/work/sub2api/.worktrees/codex/agentplane-handoff/docs/OP_LINUX_DEPLOYMENT.prod0-main.md` -> `/root/work/sub2api/.worktrees/codex/agentplane-handoff/docs/AGENTPLANE_DEPLOYMENT.prod0-main.md`
- Move: `/root/work/sub2api/.worktrees/codex/agentplane-handoff/docs/OP_LINUX_DEPLOYMENT.prod2-main.md` -> `/root/work/sub2api/.worktrees/codex/agentplane-handoff/docs/AGENTPLANE_DEPLOYMENT.prod2-main.md`
- Modify: `/root/work/sub2api/.worktrees/codex/agentplane-handoff/docs/README.md`
- Modify: `/root/work/sub2api/.worktrees/codex/agentplane-handoff/docs/owner/README.md`
- Modify: `/root/work/sub2api/.worktrees/codex/agentplane-handoff/.agents/skills/README.md`
- Modify: `/root/work/sub2api/.worktrees/codex/agentplane-handoff/.agents/skills/sub2api-prod-deploy/SKILL.md`
- Modify: `/root/work/sub2api/.worktrees/codex/agentplane-handoff/.agents/skills/sub2api-source-build/SKILL.md`
- Modify: `/root/work/sub2api/.worktrees/codex/agentplane-handoff/tools/git/test-active-formal-surface.sh`

- [ ] **Step 1: 先把 handoff 守卫脚本改成 AgentPlane 规则**

把 `tools/git/test-active-formal-surface.sh` 的 required patterns 改成：

```bash
required_patterns=(
  'The formal production control plane for this fork lives in `/root/work/AgentPlane`.'
  "deploy/agentplane/contract.wsl.yaml"
  "deploy/agentplane/contract.yaml"
  "deploy/agentplane/contract.prod2.yaml"
)
```

然后把旧摘要名禁掉：

```bash
forbidden_patterns=(
  "/root/work/OP_Linux"
  "deploy/op/"
  "OP_LINUX_DEPLOYMENT"
  "python -m ops.cli"
)
```

- [ ] **Step 2: 移动合同目录和摘要文件，并改合同里的路径字段**

Run:

```bash
cd /root/work/sub2api/.worktrees/codex/agentplane-handoff
git mv deploy/op deploy/agentplane
git mv docs/OP_LINUX_DEPLOYMENT.wsl.md docs/AGENTPLANE_DEPLOYMENT.wsl.md
git mv docs/OP_LINUX_DEPLOYMENT.prod0-main.md docs/AGENTPLANE_DEPLOYMENT.prod0-main.md
git mv docs/OP_LINUX_DEPLOYMENT.prod2-main.md docs/AGENTPLANE_DEPLOYMENT.prod2-main.md
```

把合同里的字段改成：

```yaml
runtime:
  env_template: deploy/agentplane/runtime.env.example
docs:
  app_summary_file: docs/AGENTPLANE_DEPLOYMENT.prod0-main.md
```

以及：

```yaml
docs:
  app_summary_file: docs/AGENTPLANE_DEPLOYMENT.wsl.md
```

```yaml
docs:
  app_summary_file: docs/AGENTPLANE_DEPLOYMENT.prod2-main.md
```

- [ ] **Step 3: 改 README、AGENTS、docs 索引和 repo-local skills**

把 `README.md` 的正式控制面说明改成：

```markdown
The formal production control plane for this fork lives in `/root/work/AgentPlane`.
```

把 `AGENTS.md` 的正式入口改成：

```markdown
- Formal onboarding/deploy/rollback/verify/doc-sync: run `uv run python -m agentplane.cli app object ...` or `uv run python -m agentplane.cli app delivery ...` from `/root/work/AgentPlane`
```

把 `.agents/skills/sub2api-prod-deploy/SKILL.md` 改成：

```markdown
description: Use when /root/work/sub2api needs to hand a release candidate to the AgentPlane control plane for formal delivery, verification, rollback, or WSL rehearsal.
```

```markdown
- `/root/work/AgentPlane/.codex/skills/app-delivery-ops/SKILL.md`
- `uv run python -m agentplane.cli app delivery validate-contract --target prod0-main --app sub2api --repo-root /root/work/AgentPlane`
```

把 `docs/README.md` 和 `deploy/README.md` 的索引改成：

```markdown
- `docs/AGENTPLANE_DEPLOYMENT.wsl.md`
- `docs/AGENTPLANE_DEPLOYMENT.prod0-main.md`
- `docs/AGENTPLANE_DEPLOYMENT.prod2-main.md`
```

```markdown
> **Formal production control plane:** `/root/work/AgentPlane` owns production deploy, verify, rollback, inventory refresh, and doc-sync.
```

```markdown
| `agentplane/contract.wsl.yaml` | WSL contract consumed by AgentPlane |
| `agentplane/contract.yaml` | prod0-main contract consumed by AgentPlane |
| `agentplane/contract.prod2.yaml` | prod2-main contract consumed by AgentPlane |
```

- [ ] **Step 4: 运行 `sub2api` handoff 守卫和旧名清扫**

Run:

```bash
cd /root/work/sub2api/.worktrees/codex/agentplane-handoff
bash tools/git/test-active-formal-surface.sh
rg -n "/root/work/OP_Linux|deploy/op|OP_LINUX_DEPLOYMENT|python -m ops\.cli" README.md AGENTS.md docs deploy .agents tools
```

Expected:

- `tools/git/test-active-formal-surface.sh` 返回 `PASS`
- `rg` 没有命中

- [ ] **Step 5: 提交 `sub2api` handoff 硬切**

```bash
cd /root/work/sub2api/.worktrees/codex/agentplane-handoff
git add \
  README.md AGENTS.md deploy docs .agents tools/git/test-active-formal-surface.sh
git commit -m "refactor: rename OP handoff surface to AgentPlane"
```

### Task 6: 最终目录切换与全链路验证

**Files:**
- Modify: `/root/work/OP_Linux/.worktrees/codex/agentplane-rebrand/README.md`
- Modify: `/root/work/OP_Linux/.worktrees/codex/agentplane-rebrand/docs/**`
- Modify: `/root/work/OP_Linux/.worktrees/codex/agentplane-rebrand/.codex/**`
- Modify: `/root/work/OP_Linux/.worktrees/codex/agentplane-rebrand/plugins/**`
- Modify: `/root/work/OP_Linux/.worktrees/codex/agentplane-rebrand/templates/**`
- Modify: `/root/work/OP_Linux/.worktrees/codex/agentplane-rebrand/inventory/**`
- Modify: `/root/work/OP_Linux/.worktrees/codex/agentplane-rebrand/tests/**`
- Modify: `/root/work/sub2api/.worktrees/codex/agentplane-handoff/README.md`
- Modify: `/root/work/sub2api/.worktrees/codex/agentplane-handoff/AGENTS.md`
- Modify: `/root/work/sub2api/.worktrees/codex/agentplane-handoff/docs/**`
- Modify: `/root/work/sub2api/.worktrees/codex/agentplane-handoff/deploy/**`
- Modify: `/root/work/sub2api/.worktrees/codex/agentplane-handoff/.agents/**`

- [ ] **Step 1: 在切换目录前先做两仓 staged-free 验证**

Run:

```bash
cd /root/work/OP_Linux/.worktrees/codex/agentplane-rebrand
git status --short

cd /root/work/sub2api/.worktrees/codex/agentplane-handoff
git status --short
```

Expected:

- 两个工作树都只剩本轮已知改动
- 没有意外未跟踪文件

- [ ] **Step 2: 把主仓库根目录从 `OP_Linux` 改成 `AgentPlane`**

Run:

```bash
cd /root/work
mv OP_Linux AgentPlane
```

然后修复主仓库 worktree 元数据：

```bash
git -C /root/work/AgentPlane worktree repair /root/work/AgentPlane/.worktrees/codex/agentplane-rebrand
```

- [ ] **Step 3: 在新根目录下做旧名清扫**

Run:

```bash
cd /root/work/AgentPlane/.worktrees/codex/agentplane-rebrand
rg -n "OP_Linux|op_linux|op-linux|python -m ops\.cli" README.md docs inventory templates tests .codex plugins agentplane

cd /root/work/sub2api/.worktrees/codex/agentplane-handoff
rg -n "/root/work/OP_Linux|deploy/op|OP_LINUX_DEPLOYMENT|python -m ops\.cli" README.md AGENTS.md docs deploy .agents tools
```

Expected:

- 两个 `rg` 都无输出

- [ ] **Step 4: 跑最终最小闭环验证**

Run:

```bash
cd /root/work/AgentPlane/.worktrees/codex/agentplane-rebrand
uv run python -m agentplane.cli --help
uv run python -m agentplane.cli app object get --target prod0-main --app sub2api --repo-root /root/work/AgentPlane
uv run python -m agentplane.cli app delivery validate-contract --target wsl --app sub2api --repo-root /root/work/AgentPlane
uv run python -m pytest \
  tests/test_cli_entrypoints.py \
  tests/test_project_lifecycle_acceptance.py \
  tests/test_pyproject_config.py \
  tests/test_docs_no_legacy_terms.py \
  tests/test_onepanel_plugin_and_skills.py \
  tests/test_secrets_backup_r2.py \
  tests/test_app_object_cli.py \
  tests/test_app_object_lifecycle.py -q

cd /root/work/sub2api/.worktrees/codex/agentplane-handoff
bash tools/git/test-active-formal-surface.sh
```

Expected:

- CLI help 返回 0
- `app object get` 和 `validate-contract` 对 `sub2api` 返回 0
- pytest 通过
- `sub2api` 守卫脚本通过

- [ ] **Step 5: 提交最终绝对路径修正，并记录目录切换完成**

如果 Step 3 或 Step 4 为了清理绝对路径还改了 tracked 文件，则提交：

```bash
cd /root/work/AgentPlane/.worktrees/codex/agentplane-rebrand
git add README.md docs .codex plugins templates inventory tests agentplane pyproject.toml
git commit -m "fix: finalize AgentPlane path cutover"
```

如果主仓库在 Step 3 和 Step 4 无任何 tracked 文件变化，则不新增代码提交，只记录目录切换完成并进入收口。
