# App Resource CLI Surface Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans`. Keep checklist formatting for tasks.

**Goal:** 把正式的 `app resource` CLI surface 在 `ops.cli` 里公开：`uv run python -m ops.cli app resource <search|get|verify|refresh-ledger>`，统一 payload 中的 `action` 为 `resource.*`，并且顶层 HELP 不再提 `tenant`/`resource-tenants`/`app_resource_summary`，所有 tests、docs、skills、scripts 只提 final naming。

**Architecture:** `ops/cli/apps.py` 在 `app` parser 下注册 `resource` surface，`ops/domain/app/resource_handlers` 负责 routing，`ops/scripts/onepanel/ledger.py`、`tests/test_app_resource_cli.py` 继续以 final naming 写 ledger/fixtures；`ops/cli/app.py` 只注册 formal domains (`host`, `service`, `website`, `projection`, `app resource`)，不再引入 `tenant` parser。

**Tech Stack:** Python 3.12、`argparse`、`pytest`/`unittest`、inventory JSON、Markdown docs、existing `onepanel` ledger helpers.

---

### Task 1: Lock the new CLI contract

**Files:**
- Modify: `tests/test_cli_entrypoints.py`
- Create: `tests/test_app_resource_cli.py`
- Test: `tests/test_cli_entrypoints.py`
- Test: `tests/test_app_resource_cli.py`

- [ ] **Step 1:** `tests/test_cli_entrypoints.py` 要断言 `uv run python -m ops.cli` 输出里只出现正式 command (`app`, `host`, `service`, `website`, `projection` 等)，`tenant` 不存在；`app --help` 要列出 `object`、`resource`、`delivery`；`app resource --help` 要覆盖 `search/get/verify/refresh-ledger`。
- [ ] **Step 2:** `tests/test_app_resource_cli.py` 写好对 `search/get/verify/refresh-ledger` 的契约，fixture helpers 直接声明 `inventory/servers/<target>/app-resources.json` 与 payload 中的 `app_resource_summary`。
- [ ] **Step 3:** 运行 `uv run python -m pytest tests/test_cli_entrypoints.py tests/test_app_resource_cli.py -q`，确认当前 fail 因 CLI surface 未实现。

### Task 2: Implement the `app resource` handler

**Files:**
- Modify: `ops/cli/apps.py`
- Create: `ops/domain/app/resource_handlers.py`
- Modify: `ops/domain/app/resource_registry.py`
- Modify: `ops/domain/app/resource_models.py`
- Modify: `tests/test_app_resource_cli.py`
- Test: `tests/test_app_resource_cli.py`

- [ ] **Step 1:** `handle_app_command()` 中的 `app resource` branch 路由到 `resource_handlers`，`action` 统一成 `resource.search/get/verify/refresh-ledger`，payload 里只包含 `app_resource_summary`、`resource`、`declared`、`projection`、`secret_files`。
- [ ] **Step 2:** `resource_handlers` 使用 `search_app_resources`/`get_app_resource`/`verify_app_resource`/`refresh_app_resource_ledger`，payload 的 error id 重命名成 `app.resource.*`。
- [ ] **Step 3:** fixture tests run with final names and `inventory`/`secrets` layout, verifying CLI output includes `app resource` naming only.

### Task 3: Remove tenant CLI registration

**Files:**
- Modify: `ops/cli/app.py`
- Modify: `tests/test_cli_entrypoints.py`

- [ ] **Step 1:** `ops/cli/app.py` 只注册 `host`、`service`、`website`、`app object`/`resource`/`delivery`、`projection`，不再导入或注册 `ops.cli.tenant`。
- [ ] **Step 2:** `tests/test_cli_entrypoints.py` 中 `CliEntrypointsTests` 中 assert `tenant` is not listed in `--help` and `run_cli("tenant", "--help")` returns invalid choice (argparse).
- [ ] **Step 3:** Run `uv run python -m pytest tests/test_cli_entrypoints.py -q` and confirm the CLI help contract passes.

### Task 4: Docs, skills, and ledger onboarding

**Files:**
- Modify: `README.md`
- Modify: `docs/architecture/control-plane.md`
- Modify: `.codex/skills/app-resource-ops/SKILL.md`
- Modify: `docs/runbooks/*` (active docs referencing resources)
- Test: `tests/test_docs_no_legacy_terms.py`

- [ ] **Step 1:** Update README/control-plane/runbooks to show `uv run python -m ops.cli app resource ...` commands and describe `app resource` using `app-resources.json`, `app_resource_summary`, `secrets/app-resources/`.
- [ ] **Step 2:** `.codex/skills/app-resource-ops/SKILL.md` should keep the skill name but mention the formal public entry: `uv run python -m ops.cli app resource ...` and reference the resource ledger paths.
- [ ] **Step 3:** `tests/test_docs_no_legacy_terms.py` ensures `tenant` legacy terms do not appear in active docs; only the new names survive.

### Task 5: Final verification

**Files:** verify only

- [ ] **Step 1:** `uv run python -m pytest tests/test_cli_entrypoints.py tests/test_app_resource_cli.py tests/test_docs_no_legacy_terms.py tests/test_onepanel_plugin_and_skills.py -q`
- [ ] **Step 2:** `uv run python -m ops.cli app resource --help` lists the four actions; top-level CLI help no longer lists the removed legacy resource object entry.
- [ ] **Step 3:** `rg -n \"tenant\" docs/ README.md .codex/skills` only matches historical plans.
