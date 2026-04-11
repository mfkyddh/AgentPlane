# WSL Governance Convergence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 WSL 的受管 compose 服务、运行态、审计规则和 inventory 快照重新收口到当前仓库根。

**Architecture:** 先通过测试定义新的治理行为，再修改审计、inventory 和 compose 资产，最后执行容器重建与目录清理。运行态切换只在仓库声明与测试变绿后进行，避免临时失配。

**Tech Stack:** Python (`uv`, `pytest`), Docker Compose, YAML, repository governance docs

---

### Task 1: 定义新的治理行为

**Files:**
- Modify: `tests/test_wsl_audit.py`
- Modify: `tests/test_inventory_generation.py`
- Modify: `tests/test_cli_entrypoints.py`
- Modify: `tests/compose-template-layout.sh`

- [ ] **Step 1: 写失败测试覆盖新规则**

新增以下断言：
- `infra/compose/<service>/.env.wsl`、`.env.prod0` 会触发 WSL 审计违规。
- inventory 将 repo-managed 容器与 unmanaged 容器分开。
- `chatgpt-register-wsl` 的 compose 目录和 secret/env 约束被模板测试覆盖。

- [ ] **Step 2: 运行测试确认先红**

Run: `PYTHONPATH=/root/work/OP_Linux uv run pytest tests/test_wsl_audit.py tests/test_inventory_generation.py tests/test_cli_entrypoints.py -q`
Expected: FAIL，失败点来自新增治理断言。

### Task 2: 实现审计和 inventory 规则

**Files:**
- Modify: `ops/cli/audit.py`
- Modify: `ops/cli/inventory.py`

- [ ] **Step 1: 只写最小实现让新测试可过**

实现：
- `infra/compose/<service>/.env.*` 违规检测。
- WSL inventory 按 repo root 下声明的 compose 项目标签过滤 repo-managed 容器，并新增 `unmanaged_docker_containers`。

- [ ] **Step 2: 运行测试验证变绿**

Run: `PYTHONPATH=/root/work/OP_Linux uv run pytest tests/test_wsl_audit.py tests/test_inventory_generation.py tests/test_cli_entrypoints.py -q`
Expected: PASS

### Task 3: 调整 compose 资产与模板

**Files:**
- Modify: `infra/compose/cliproxyapi/docker-compose.wsl.yml`
- Modify: `infra/compose/cliproxyapi/docker-compose.prod0.yml`
- Modify: `infra/compose/cliproxyapi/README.md`
- Create: `infra/compose/chatgpt-register-wsl/docker-compose.wsl.yml`
- Create: `infra/compose/chatgpt-register-wsl/docker-compose.prod0.yml`
- Create: `infra/compose/chatgpt-register-wsl/README.md`
- Modify: `templates/services/cliproxyapi.env.example`
- Create: `templates/services/chatgpt-register-wsl.env.example`

- [ ] **Step 1: 迁移 env 引用到 secrets/services**

把 `cliproxyapi` 的 compose 改为引用 `../../../secrets/services/cliproxyapi.*.env`，README 与模板同步更新。

- [ ] **Step 2: 新增 chatgpt-register-wsl 受管服务目录**

创建双 compose 模板和 README，保持容器名、host 网络、数据目录与当前运行态一致。

- [ ] **Step 3: 删除空壳目录冲突源**

删除 `infra/compose/token-openresty` 空目录，避免审计持续报错。

- [ ] **Step 4: 运行模板与测试检查**

Run: `PYTHONPATH=/root/work/OP_Linux uv run pytest tests/test_wsl_audit.py tests/test_inventory_generation.py tests/test_cli_entrypoints.py -q`
Run: `bash tests/compose-template-layout.sh`
Expected: PASS

### Task 4: 收口本地 secret/env 和 inventory

**Files:**
- Create: `secrets/services/cliproxyapi.wsl.env`
- Create: `secrets/services/cliproxyapi.prod0.env`
- Create: `secrets/services/chatgpt-register-wsl.env`
- Create: `secrets/services/chatgpt-register.prod0.env`
- Modify: `inventory/servers/wsl/inventory.json`

- [ ] **Step 1: 把 env 落到 secrets/services**

从现有运行参数复制 `cliproxyapi` 与 `chatgpt-register-wsl` 所需 env。

- [ ] **Step 2: 生成并写回新的 WSL inventory**

Run: `uv run python -m ops.cli inventory wsl --repo-root /root/work/OP_Linux --write`
Expected: inventory 反映当前 repo root、受管服务和 unmanaged 容器拆分。

### Task 5: 切换运行态并清理目录

**Files:**
- Runtime only: Docker containers and `/data` directories

- [ ] **Step 1: 用当前仓库根重建 data services**

Run `docker compose up -d --force-recreate` for `minio`, `postgres`, `redis` from `/root/work/OP_Linux/infra/compose/...`
Expected: 容器 label 指向当前仓库根。

- [ ] **Step 2: 切换 chatgpt-register-v2-wsl 到仓库受管 compose**

Run new compose from `infra/compose/chatgpt-register-wsl/docker-compose.wsl.yml`
Expected: 容器继续运行，但 label 和 env file 指向当前仓库。

- [ ] **Step 3: 删除用户指定的 legacy 数据目录**

删除 `/data/apps/nginx-ui-official` 和 `/data/nginx/sites/*`

- [ ] **Step 4: 做最终验证**

Run: `uv run python -m ops.cli audit filesystem --env wsl --repo-root /root/work/OP_Linux`
Run: `uv run python -m ops.cli inventory wsl --repo-root /root/work/OP_Linux`
Run: `docker inspect minio-dev postgres18-dev redis7-dev chatgpt-register-v2-wsl cli-proxy-api-dev`
Expected: 审计通过，inventory 更新，相关容器 label 全部收口到当前仓库根。
