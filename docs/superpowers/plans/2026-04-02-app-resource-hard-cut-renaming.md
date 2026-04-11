# App Resource Hard-Cut Renaming Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans`. Keep checkbox (`- [ ]`) styling for progress tracking.

**Goal:** 在 2026-04-02 的交付节点，把所有 `tenant` 命名直接重命名为 `app resource`，包括 tracked truth（`app-resources.json`、`app_resource_summary`）、tests、modules、skills、scripts、ledgers、secrets、CLI、docs，彻底收口到最终 contract，不再保留兼容表述。

**Architecture:** 由 `ops.cli.apps` 公开 `app resource` surface，`ops/domain/app/resource_*` 模块负责这一对象面，`ops/scripts/onepanel/ledger.py` 写入 `ledgers/app_resources.*`，inventory 真源是 `inventory/servers/<target>/app-resources.json`，projection 证据是 `inventory.services.<app>.app_resource_summary`，secrets 用 `secrets/app-resources/<target>/<app>/`。

**Tech Stack:** Python 3.12、`argparse`、`pytest`/`unittest`、JSON/Markdown inventory、现有 ledger 生成器、`superpowers` skill 文档。

---

### Task 1: Rename tracked truth assets & fixture helpers

**Files:** `inventory/servers/*/app-resources.json`, `tests/test_app_resource_cli.py`, `tests/test_docs_no_legacy_terms.py`

- [ ] **Step 1:** 把所有 `app-resources.json` 文件直接重命名为 `app-resources.json`，确认 inventory README 和 boxed fixtures 指向新路径。
- [ ] **Step 2:** 用 `app_resource_summary` 替换所有 projection 断言、fixtures 与 error id，确保 tests 只搜索 `app_resource_summary`。
- [ ] **Step 3:** 把 `secrets/app-resources/...` fixture 创建逻辑改为 `secrets/app-resources/<target>/<app>/`。
- [ ] **Step 4:** 更新 `tests/test_docs_no_legacy_terms.py` 的黑名单，只允许 final names，在 active docs/skills 里 `rg` 不应该找到 `app-resources.json`、`app_resource_summary`、`secrets/app-resources/`。

### Task 2: Rename modules & helpers

**Files:** `ops/domain/app/resource_models.py`, `ops/domain/app/resource_registry.py`, `ops/domain/app/resource_handlers.py`, `ops/cli/apps.py`, `ops/cli/app_resource_state.py`

- [ ] **Step 1:** 创建 `AppResourceDefinition`，把所有 `TenantDefinition` 字段映射到 `app resource` 命名，官方 helper 只暴露 `app_resource_summary` 字段。
- [ ] **Step 2:** `resource_registry` 与 `resource_handlers` 只读取 `app-resources.json` + `app_resource_summary`，计算 `resource.verify` 时只返回 `app.resource.*` 异常 id。
- [ ] **Step 3:** `ops/cli/apps.py` 里 `handle_app_command()` 增加 `app resource` surface，并删除对旧 `tenant` parser 的任何引用。
- [ ] **Step 4:** `ops/cli/app_resource_state.py` 仅保留 renamed helper 如 `registry_file(repo_root, target) -> .../app-resources.json`、`app_resource_secret_dir()`、`app_resource_summary_from_inventory()`。

### Task 3: Clean CLI surface & ledger scripts

**Files:** `ops/scripts/onepanel/ledger.py`, `tests/test_app_resource_cli.py`, `tests/test_cli_entrypoints.py`, `.codex/skills/app-resource-ops/SKILL.md`

- [ ] **Step 1:** 让 ledger 脚本写 `ledgers/app_resources.json`、`ledgers/app_resources.md`，并在 payload 中只报告 `app resource` counts。
- [ ] **Step 2:** `tests/test_cli_entrypoints.py` 断言 `uv run python -m ops.cli` 不再有 `tenant` command，`app resource --help` 列出 `search/get/verify/refresh-ledger`。
- [ ] **Step 3:** `tests/test_app_resource_cli.py` 断言 `handle_app_command()` 里的 resource action 都叫 `resource.*`，输出的 payload 只含 `app_resource_summary`、`app resource` projection。
- [ ] **Step 4:** `.codex/skills/app-resource-ops/SKILL.md` 保留 skill 名称但把 command block 和描述改为 `app resource` 命令。

### Task 4: Docs & skill sweep

**Files:** `README.md`, `docs/architecture/control-plane.md`, `docs/runbooks/*`, `tests/test_docs_no_legacy_terms.py`, `.codex/skills/catalog.yaml`

- [ ] **Step 1:** 把 active docs 中所有 `tenant` 句子替换成 final `app resource` 术语，加上 `uv run python -m ops.cli app resource ...` 示例。
- [ ] **Step 2:** `.codex/skills/catalog.yaml` 中 `app-resource-ops` entrypoint 指向 `uv run python -m ops.cli app`，skill text 明确写 `app resource` 命令。
- [ ] **Step 3:** 文档测试确认 `rg tenant` 只会在历史 spec/plan 出现，active docs/skills/README 均使用 final naming。

### Task 5: Verification & roll-up

**Files:** verify only

- [ ] **Step 1:** `uv run python -m pytest tests/test_cli_entrypoints.py tests/test_app_resource_cli.py tests/test_docs_no_legacy_terms.py tests/test_onepanel_plugin_and_skills.py -q`。
- [ ] **Step 2:** `rg -n \"tenant\" docs/ README.md .codex/skills` 没有 `tenant` surface 相关行。
- [ ] **Step 3:** 自检：确认 no `tenant` modules, CLI, docs, ledger scripts, tests, or fixtures remain in active surface.
