# Managed Bridge Network Governance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 OP_Linux 增加通用的受管 Docker bridge 网络治理能力，并把它接入生产部署前置流程与新机器治理文档。

**Architecture:** 新增独立 `ops.cli network` 模块，读取 inventory 中的 `managed_bridge_networks` 声明，提供 `audit` / `ensure` 两个动作。`app deploy` 与 `app verify` 在生产目标执行前调用 `network ensure`，把 bridge gateway drift 从人工排障变成控制面治理步骤。

**Tech Stack:** Python 3.14, `ops.cli`, JSON inventory, pytest/unittest

---

### Task 1: Add failing tests for managed bridge network declarations

**Files:**
- Modify: `tests/test_app_cli.py`
- Test: `tests/test_app_cli.py`

- [ ] **Step 1: Write failing tests for inventory-driven network audit/ensure**

Add tests that expect:

```python
payload = {
    "ssh": {"aliases": ["prod2-main"], "user": "root"},
    "managed_bridge_networks": [
        {
            "name": "zqf_network",
            "driver": "bridge",
            "subnet": "172.19.0.0/16",
            "gateway_ip": "172.19.0.1/16",
            "required_for": ["sub2api-prod"],
        }
    ],
    "services": {
        "postgres": {"container_name": "postgres18-prod"},
        "redis": {"container_name": "redis7-prod"},
        "minio": {"container_name": "minio-prod"},
    },
}
```

- [ ] **Step 2: Run the focused tests to verify they fail**

Run: `uv run pytest tests/test_app_cli.py -q`
Expected: FAIL because `ops.cli network` does not exist yet.

### Task 2: Add failing tests for deploy/verify integration

**Files:**
- Modify: `tests/test_app_cli.py`
- Test: `tests/test_app_cli.py`

- [ ] **Step 1: Write failing tests that production deploy/verify prepend network ensure**

Add tests asserting `app deploy prod2-main --execute` and `app verify prod2-main --execute` expose an initial network-ensure step in returned commands/results.

- [ ] **Step 2: Run tests to verify they fail for the expected reason**

Run: `uv run pytest tests/test_app_cli.py -q`
Expected: FAIL because deploy/verify do not yet call network governance.

### Task 3: Implement the network governance module

**Files:**
- Create: `ops/cli/networks.py`
- Modify: `ops/cli/app.py`
- Test: `tests/test_app_cli.py`

- [ ] **Step 1: Implement inventory loading and declaration validation**
- [ ] **Step 2: Implement `network audit`**
- [ ] **Step 3: Implement `network ensure`**
- [ ] **Step 4: Register the parser in `ops/cli/app.py`**

- [ ] **Step 5: Run focused tests**

Run: `uv run pytest tests/test_app_cli.py -q`
Expected: network CLI tests pass, deploy/verify integration tests may still fail.

### Task 4: Integrate network ensure into production app flows

**Files:**
- Modify: `ops/cli/apps.py`
- Test: `tests/test_app_cli.py`

- [ ] **Step 1: Add a reusable production preflight hook that runs `network ensure` for production targets**
- [ ] **Step 2: Call the hook from `deploy_app(..., execute=True)`**
- [ ] **Step 3: Call the hook from `verify_app(..., execute=True)`**
- [ ] **Step 4: Keep WSL behavior unchanged**

- [ ] **Step 5: Run focused tests**

Run: `uv run pytest tests/test_app_cli.py -q`
Expected: all new app/network tests pass.

### Task 5: Extend filesystem/inventory audit coverage

**Files:**
- Modify: `ops/cli/audit.py`
- Modify: `tests/test_prod0_audit.py`

- [ ] **Step 1: Add audit rules for malformed `managed_bridge_networks` declarations**
- [ ] **Step 2: Add tests for missing/invalid network declaration shape**
- [ ] **Step 3: Run focused tests**

Run: `uv run pytest tests/test_prod0_audit.py -q`
Expected: audit tests pass.

### Task 6: Declare prod2 managed bridge networks and update runbooks

**Files:**
- Modify: `inventory/servers/prod2-main/inventory.json`
- Modify: `inventory/servers/prod2-main/README.md`
- Modify: `docs/runbooks/app-project-delivery-workflow.md`
- Modify: `docs/runbooks/prod2-main-1panel-public-access.md`

- [ ] **Step 1: Add `managed_bridge_networks` to `prod2-main` inventory**
- [ ] **Step 2: Add incident note and governance note to `prod2-main` README**
- [ ] **Step 3: Update app delivery runbook to require `network ensure` before production cutover**
- [ ] **Step 4: Update prod2 public-access runbook to explain bridge gateway drift and the control-plane fix**

- [ ] **Step 5: Run documentation-sensitive tests if any, then re-read changed docs**

### Task 7: Full verification

**Files:**
- Verify: `ops/cli/networks.py`
- Verify: `ops/cli/apps.py`
- Verify: `ops/cli/audit.py`
- Verify: `inventory/servers/prod2-main/inventory.json`

- [ ] **Step 1: Run focused regression suite**

Run: `uv run pytest tests/test_app_cli.py tests/test_prod0_audit.py tests/test_onepanel_project_lifecycle.py tests/test_onepanel_compose_policy.py -q`
Expected: PASS

- [ ] **Step 2: Run control-plane command smoke checks**

Run:

```bash
uv run python -m ops.cli network audit --target prod2-main --repo-root /root/work/OP_Linux/.worktrees/codex/bridge-network-governance
uv run python -m ops.cli network ensure --target prod2-main --repo-root /root/work/OP_Linux/.worktrees/codex/bridge-network-governance
```

Expected: `ok: true` and no repair required on the already-fixed live host.

- [ ] **Step 3: Review `git status --short` and summarize changed files**
