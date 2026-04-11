# README Governance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把根 `README.md` 收口成短而稳定的仓库总入口，并把细则下沉到现有 `docs/` 文档。

**Architecture:** 先对齐现有治理文档中的边界与统一入口，再按“定位、上手、协作、索引、导航”的结构重写 README，最后验证所有链接路径存在且 diff 仅包含预期文档改动。

**Tech Stack:** Markdown, repository governance docs, shell verification

---

### Task 1: 对齐 README 信息源

**Files:**
- Read: `README.md`
- Read: `docs/architecture/linux-governance.md`
- Read: `docs/architecture/repo-layout.md`
- Read: `docs/architecture/op-linux-app-collaboration.md`
- Read: `docs/runbooks/wsl-host-governance.md`

- [ ] **Step 1: 提取稳定口径**

确认 README 只能复用以下稳定信息：
- `OP_Linux` 是治理仓库和控制面真源
- 统一入口是 `uv run python -m ops.cli ...`
- secrets、templates、`infra/compose/`、`inventory/servers/` 的边界
- 隔离工作区协作只写原则，不写长流程

### Task 2: 重写根 README 结构

**Files:**
- Modify: `README.md`

- [ ] **Step 1: 按总览结构重写**

把 README 收口为：
- 仓库定位
- 30 秒上手
- 日常入口
- 新工作区协作
- 文档入口
- 目录导航
- 常用模板

- [ ] **Step 2: 删除易漂移细节**

删掉会与 runbook 重复的操作性解释，只保留入口命令与文档链接。

### Task 3: 验证文档治理结果

**Files:**
- Verify: `README.md`
- Verify: `docs/superpowers/specs/2026-03-26-readme-governance-design.md`
- Verify: `docs/superpowers/plans/2026-03-26-readme-governance.md`

- [ ] **Step 1: 检查 README 链接路径**

Run: `cd /root/work/OP_Linux/.worktrees/codex-readme-governance && while read -r path; do test -e "${path#/root/work/OP_Linux/}" || { echo "missing: $path"; exit 1; }; done < <(grep -oP '\\]\\(\\K[^)]+' README.md | grep '^/root/work/OP_Linux/')`
Expected: no output

- [ ] **Step 2: 检查最终 diff**

Run: `cd /root/work/OP_Linux/.worktrees/codex-readme-governance && git diff -- README.md docs/superpowers/specs/2026-03-26-readme-governance-design.md docs/superpowers/plans/2026-03-26-readme-governance.md`
Expected: only intended documentation changes
