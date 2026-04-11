# Website Object V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 `OP_Linux` 增加正式 `website` 对象域入口 `uv run python -m ops.cli website ...`，统一表达公网入口对象，不进入应用运行面。

**Architecture:** `website v1` 复用现有 `onepanel` substrate 作为 provider/live-state 适配层，但正式对象域以 `target + alias` 为稳定引用，声明真源直接读取 `inventory/servers/<target>/inventory.json` 里的 `services.public_websites`。第一版只开放 `search / get / verify / plan / apply / refresh-ledger`，其中写操作仅支持 `reconcile`。

**Tech Stack:** Python 3、`argparse` CLI、现有 `ops/scripts/onepanel` object API/ledger substrate、`unittest`

---

### Task 1: Freeze CLI Contract

**Files:**
- Create: `tests/test_website_cli.py`
- Modify: `tests/test_cli_entrypoints.py`

- [ ] **Step 1: Write the failing tests for the top-level CLI contract**

为以下行为先写失败测试：
- `ops.cli --help` 包含 `website`
- `ops.cli website --help` 包含 `search/get/verify/plan/apply/refresh-ledger`
- `website plan` 只接受 `reconcile`
- `website apply` 缺少 `--execute` 时失败

- [ ] **Step 2: Run the targeted tests and verify they fail for the right reason**

Run: `python -m pytest tests/test_cli_entrypoints.py tests/test_website_cli.py -q`

Expected: FAIL because `website` command does not exist yet.

- [ ] **Step 3: Implement the minimal top-level parser and handler wiring**

新增 `ops/cli/website.py`，并在 `ops/cli/app.py` 注册 `website` 子命令与分发。

- [ ] **Step 4: Re-run the targeted tests and verify green**

Run: `python -m pytest tests/test_cli_entrypoints.py tests/test_website_cli.py -q`

Expected: PASS for the CLI shape assertions.

### Task 2: Freeze Website Object Semantics

**Files:**
- Create: `tests/test_website_cli.py`
- Create: `ops/domain/website/models.py`
- Create: `ops/domain/website/registry.py`
- Create: `ops/domain/website/handlers.py`

- [ ] **Step 1: Write the failing tests for `search/get/verify` object semantics**

为以下行为写失败测试：
- `search` 从 `inventory.services.public_websites` 列出对象，而不是直接依赖 API 搜索结果
- `get` 返回 `website` 声明摘要和 `live` 聚合结果
- `verify` 校验 alias、domain、proxy、HTTPS enable、SSL 绑定，并返回结构化 `checks/failures/evidence`

- [ ] **Step 2: Run the targeted tests and verify they fail correctly**

Run: `python -m pytest tests/test_website_cli.py -q`

Expected: FAIL because domain models/handlers do not exist yet.

- [ ] **Step 3: Implement the minimal registry and read-only handlers**

新增 `ops/domain/website/`：
- `models.py` 定义声明对象模型
- `registry.py` 读取 `inventory.services.public_websites`
- `handlers.py` 实现 `search/get/verify`

- [ ] **Step 4: Re-run the targeted tests and verify green**

Run: `python -m pytest tests/test_website_cli.py -q`

Expected: PASS for read-only object semantics.

### Task 3: Freeze Reconcile Plan/Apply Behavior

**Files:**
- Modify: `tests/test_website_cli.py`
- Modify: `ops/domain/website/handlers.py`

- [ ] **Step 1: Write the failing tests for `plan/apply reconcile`**

为以下行为写失败测试：
- `plan reconcile` 给出 preflight、steps、verify_after_apply
- 若现场对象已匹配声明，计划为空变更或 `noop`
- 若对象缺失，计划走 `create`
- 若对象存在但 `proxy/domain/https` 不匹配，计划反映 drift
- `apply reconcile --execute` 运行后再做 post-verify，并返回结构化结果

- [ ] **Step 2: Run the targeted tests and verify they fail**

Run: `python -m pytest tests/test_website_cli.py -q`

Expected: FAIL because reconcile logic is not implemented.

- [ ] **Step 3: Implement the minimal reconcile planner/apply flow**

第一版只做：
- create proxy website
- post-verify

不做：
- Cloudflare DNS
- ACME 账号管理
- 证书签发工作流
- 应用运行面联动

- [ ] **Step 4: Re-run the targeted tests and verify green**

Run: `python -m pytest tests/test_website_cli.py -q`

Expected: PASS for `reconcile` planning and apply behavior.

### Task 4: Freeze Ledger Refresh Projection

**Files:**
- Modify: `tests/test_website_cli.py`
- Modify: `ops/domain/website/handlers.py`

- [ ] **Step 1: Write the failing tests for `refresh-ledger`**

为以下行为写失败测试：
- `website refresh-ledger --target <target> --repo-root <root> --write` 刷新 `websites.json/.md`
- 更新 `inventory.object_ledgers`
- 不修改 `services.public_websites` 原始声明

- [ ] **Step 2: Run the targeted tests and verify they fail**

Run: `python -m pytest tests/test_website_cli.py -q`

Expected: FAIL because `refresh-ledger` is not wired in the new domain yet.

- [ ] **Step 3: Implement minimal ledger bridge**

复用现有 `ops/scripts/onepanel/ledger.py`，只做正式 `website` 对象域的薄封装，不新增第二套投影实现。

- [ ] **Step 4: Re-run the targeted tests and verify green**

Run: `python -m pytest tests/test_website_cli.py -q`

Expected: PASS for projection refresh behavior.

### Task 5: Sync Docs And Skills

**Files:**
- Create: `docs/superpowers/specs/2026-04-02-website-object-v1-design.md`
- Modify: `README.md`
- Modify: `docs/architecture/control-plane.md`
- Modify: `.codex/skills/onepanel-website-ops/SKILL.md`
- Modify: `.codex/skills/catalog.yaml`
- Modify: `plugins/op-linux-control-plane/skills/websites/SKILL.md`

- [ ] **Step 1: Write the failing docs/skill contract tests**

补测试固定：
- README 展示 `website` 为正式对象域
- websites plugin stable entrypoint 改为 `uv run python -m ops.cli website ...`

- [ ] **Step 2: Run the targeted tests and verify they fail**

Run: `python -m pytest tests/test_cli_entrypoints.py tests/test_onepanel_plugin_and_skills.py -q`

Expected: FAIL because docs/skill text still points to `onepanel website`.

- [ ] **Step 3: Update docs and skill routing**

同步正式入口、边界说明和插件文案；不新增 compat / alias / wrapper。

- [ ] **Step 4: Re-run the targeted tests and verify green**

Run: `python -m pytest tests/test_cli_entrypoints.py tests/test_onepanel_plugin_and_skills.py -q`

Expected: PASS.

### Task 6: Final Verification

**Files:**
- Verify only

- [ ] **Step 1: Run the focused regression suite**

Run:
- `python -m pytest tests/test_website_cli.py -q`
- `python -m pytest tests/test_cli_entrypoints.py tests/test_onepanel_plugin_and_skills.py tests/test_onepanel_object_cli.py -q`

Expected: PASS.

- [ ] **Step 2: Run one combined verification command**

Run: `python -m pytest tests/test_website_cli.py tests/test_cli_entrypoints.py tests/test_onepanel_plugin_and_skills.py tests/test_onepanel_object_cli.py -q`

Expected: PASS with no new failures.
