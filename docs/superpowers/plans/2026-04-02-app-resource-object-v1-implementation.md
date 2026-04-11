# App Resource Object V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 确定正式的 `app resource` 对象面，把所有资源租户真源、projection 字段、ledger 脚本与 CLI 解析用 `app-resources.json`、`app_resource_summary`、`ledgers/app_resources.*`、`secrets/app-resources/<target>/<app>/` 命名统一，彻底去掉 `tenant` 兼容叙述。

**Architecture:** `ops.cli.apps` 引入 `app resource` surface，`ops.domain.app.resource_models`/`resource_registry`/`resource_handlers` 以 `AppResourceDefinition` 为核心，`ops/scripts/onepanel/ledger.py` 将 ledger 写入 `ledgers/app_resources.json`/`.md`，投影数据来源于 `inventory.services.<app>.app_resource_summary`。所有 CLI、测试、文档、skill、脚本都只说 `app resource`。

**Tech Stack:** Python 3.12、`argparse`、`unittest`/`pytest`、JSON/Markdown inventory 资产、现有 `ops.cli.tenant_state` helper（重命名为资源 helper）、现有 `ops.scripts.onepanel.ledger.refresh_ledgers`。

---

### Task 1: Freeze the `app resource` CLI contract

**Files:**
- Create: `tests/test_app_resource_cli.py`
- Modify: `tests/test_cli_entrypoints.py`
- Test: `tests/test_app_resource_cli.py`
- Test: `tests/test_cli_entrypoints.py`

- [ ] **Step 1: 把 `ops.cli` 帮助输出固定为：`app resource` surface 公开 `search/get/verify/refresh-ledger`，顶层 `tenant` command 不存在**

- [ ] **Step 2: 在 `tests/test_app_resource_cli.py` 里把固定表征写成新 tracked truth 命名**

  ```python
  self.assertIn("app resource", app_help.stdout)
  self.assertIn("refresh-ledger", app_resource_help.stdout)
  self.assertNotIn("\n  tenant", run_cli("--help").stdout)
  ```

- [ ] **Step 3: 用 `app-resources.json`、`app_resource_summary`、`secrets/app-resources/...` 写入 fixture helpers，verify 投影字段唯一叫 `app_resource_summary`，错误码里只有 `app.resource.*`**

- [ ] **Step 4: 运行上述测试，确认旧 `tenant` surface 报错**

  Run: `uv run python -m pytest tests/test_cli_entrypoints.py tests/test_app_resource_cli.py -q`
  Expected: FAIL，因为资源 surface 尚未实现。

### Task 2: 实现资源对象域，重命名模块与模型

**Files:**
- Create: `ops/domain/app/resource_models.py`
- Create: `ops/domain/app/resource_registry.py`
- Create: `ops/domain/app/resource_handlers.py`
- Modify: `ops/cli/apps.py`
- Modify: `ops/cli/app_resource_state.py`
- Test: `tests/test_app_resource_cli.py`

- [ ] **Step 1: `AppResourceDefinition` 包含 `app`、`owner_app`、`resource_kinds`、`ledger_status`、`resources`、`secret_files`，并提供 `app_resource_summary` 聚合**

- [ ] **Step 2: `resource_registry` 用 `app_resource_summary` 字段判断 projection 可用性，所有 `search/get/verify` 都读 `inventory/servers/<target>/app-resources.json` 与 `inventory.services.<app>.app_resource_summary`**

- [ ] **Step 3: 将 `ops.cli.tenant_state` 重命名并修改字段助手：`registry_file()` 只返回 `app-resources.json`，`app_resource_secret_dir()` 只指向 `secrets/app-resources/...`，`secret_file_statuses`、`inventory_projection()` 返回 `app_resource_summary`**

- [ ] **Step 4: 运行资源对象测试，确保 `resource.search`、`resource.get`、`resource.verify` 依赖 final naming**

  Run: `uv run python -m pytest tests/test_app_resource_cli.py -q`
  Expected: PASS for domain helpers.

### Task 3: 让 CLI 调用和 ledger 写入最终路径

**Files:**
- Modify: `ops/cli/apps.py`
- Modify: `ops/scripts/onepanel/ledger.py`
- Test: `tests/test_app_resource_cli.py`
- Test: `tests/test_cli_entrypoints.py`
- Test: `tests/test_onepanel_plugin_and_skills.py`

- [ ] **Step 1: 在 `ops/cli/apps.py` 中的 `handle_app_command()` 里注册 `app resource` parser，并把 action 命名统一为 `resource.search/get/verify/refresh-ledger`**

- [ ] **Step 2: `ops/scripts/onepanel/ledger.py` 只生成 `ledgers/app_resources.json/md`，并保持 `app_resource_summary` 作为 projection 证据**

- [ ] **Step 3: `tests/test_onepanel_plugin_and_skills.py` 断言 skill 文档只提 `app resource`，catalog entrypoint 仍指向 `uv run python -m ops.cli app`**

- [ ] **Step 4: 重新跑 CLI + ledger + skill 测试确认宽高**

  Run: `uv run python -m pytest tests/test_cli_entrypoints.py tests/test_app_resource_cli.py tests/test_onepanel_plugin_and_skills.py -q`
  Expected: PASS once CLI recognizes new surface.

### Task 4: Docs & skills final sweep

**Files:**
- Modify: `README.md`
- Modify: `docs/architecture/control-plane.md`
- Modify: `.codex/skills/app-resource-ops/SKILL.md`
- Modify: `docs/runbooks/xxx` (active docs referencing resources)
- Test: `tests/test_docs_no_legacy_terms.py`

- [ ] **Step 1: 把 README、control-plane、runbooks 里所有 `tenant` word 替换为 `app resource` 同步脚本/skill 示例**

- [ ] **Step 2: `.codex/skills/app-resource-ops/SKILL.md` 明确写 `app resource` 命令，同时保留 skill 名称历史痕迹**

- [ ] **Step 3: `tests/test_docs_no_legacy_terms.py` 黑名单只搜 `app-resources.json`、`app_resource_summary`、`secrets/app-resources/`，确保 active docs 只提 final names**

- [ ] **Step 4: 最后统一运行文档 + skills 合同**

  Run: `uv run python -m pytest tests/test_docs_no_legacy_terms.py tests/test_onepanel_plugin_and_skills.py -q`
  Expected: PASS.

### Task 5: Final verification and self-check

**Files:** Verify only

- [ ] **Step 1: `uv run python -m pytest tests/test_cli_entrypoints.py tests/test_app_resource_cli.py tests/test_onepanel_plugin_and_skills.py tests/test_docs_no_legacy_terms.py -q`**

- [ ] **Step 2: `rg -n \"tenant\" docs/ README.md .codex/skills` should return nothing relevant outside this spec**

- [ ] **Step 3: 自检：确认 `app resource` 相关模块、tests、docs 都用 `app-resources.json` / `app_resource_summary` / `secrets/app-resources/` / `app.resource.*` 统一命名**
