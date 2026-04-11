# NewAPI OP_Linux Isolation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 `/root/work/new-api` 按新的基础设施隔离要求正式接入 `OP_Linux`，补齐 WSL 与 prod0 的 PostgreSQL/Redis 租户化交付链路，并统一二开版本号与 Docker tag 规则。

**Architecture:** 方案分两部分。`new-api` 仓库负责宿主机构建脚本、runtime image 打包、合同与非敏感摘要；`OP_Linux` 仓库负责 target-aware 的 runtime 渲染、tenant env 投影、compose 模板、inventory/doc-sync 和验证命令。WSL 不创建网站对象，prod0 复用现有网站对象。

**Tech Stack:** Python CLI, Docker Compose, Go, Bun, YAML, unittest/pytest

---

### Task 1: Lock OP_Linux behavior with failing tests

**Files:**
- Modify: `tests/test_app_cli.py`
- Modify: `tests/test_prod0_postgres_app_resource_audit.py`
- Modify: `tests/test_sub2api_compose_layout.py`

- [ ] **Step 1: Add failing tests for `newapi` WSL runtime rendering**
- [ ] **Step 2: Add failing tests for `newapi` tenant env projection using `SQL_DSN` and `REDIS_CONN_STRING`**
- [ ] **Step 3: Add failing tests for version/tag formatting helpers**
- [ ] **Step 4: Run focused tests and confirm failures are for the intended missing behavior**

### Task 2: Implement OP_Linux runtime and tenant changes

**Files:**
- Modify: `ops/cli/apps.py`
- Modify: `ops/cli/prod0_postgres_app_resource_audit.py`
- Create: `infra/compose/newapi/docker-compose.wsl.yml`
- Modify: `infra/compose/newapi/docker-compose.prod0.yml`
- Modify: `inventory/servers/wsl/inventory.json`

- [ ] **Step 1: Make app render/verify/doc-sync aware of WSL local verification**
- [ ] **Step 2: Fix `newapi` tenant env projection to output runtime-consumed keys**
- [ ] **Step 3: Add and align `newapi` WSL compose template**
- [ ] **Step 4: Re-run focused OP_Linux tests until green**

### Task 3: Implement `new-api` app-side onboarding changes

**Files:**
- Modify: `deploy/op/contract.yaml`
- Modify: `docs/OP_LINUX_DEPLOYMENT.md`
- Modify: `deploy/prod/newapi-prod.env.example`
- Create: `deploy/build-runtime-artifacts.sh`
- Create: `deploy/package-runtime-image.sh`
- Create: `deploy/Dockerfile.runtime`
- Modify: `.dockerignore`
- Modify: `Dockerfile`

- [ ] **Step 1: Add failing app-side checks where practical for build/tag contract assumptions**
- [ ] **Step 2: Introduce host-built runtime artifact packaging path**
- [ ] **Step 3: Add tenant resource declarations and WSL/prod0-ready env template guidance**
- [ ] **Step 4: Wire the `zzz` fork version/tag format into packaging output**

### Task 4: Verify end-to-end onboarding flow

**Files:**
- Modify: `docs/architecture/op-linux-app-collaboration.md`
- Modify: `docs/runbooks/app-project-delivery-workflow.md`

- [ ] **Step 1: Run focused OP_Linux tests**
- [ ] **Step 2: Run `uv run python -m ops.cli app validate-contract` for `new-api`**
- [ ] **Step 3: Run `uv run python -m ops.cli app render-runtime` for `wsl` and `prod0-main`**
- [ ] **Step 4: Run `uv run python -m ops.cli projection runtime-env apply` for `newapi`**
- [ ] **Step 4.1: Ensure Python dependency execution stays on `uv`, and any Node dependency install/build path in this plan prefers `pnpm`**
- [ ] **Step 5: Run `bash deploy/build-runtime-artifacts.sh` and `IMAGE_TAG=verify bash deploy/package-runtime-image.sh` in `/root/work/new-api`**
