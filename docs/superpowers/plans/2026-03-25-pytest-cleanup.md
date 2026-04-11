# Pytest Entry And Cleanup CLI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 `uv run pytest` 直接可用，并为 WSL 增加安全可执行的 cleanup apply 流程。

**Architecture:** 先用测试定义新的 package/cleanup 行为，再补 pyproject 打包声明和 cleanup 执行器，最后用真实命令验证入口和清理效果。

**Tech Stack:** Python, uv, pytest, hatchling, stdlib filesystem operations

---

### Task 1: 定义 pytest 打包与 cleanup 行为

**Files:**
- Create: `tests/test_pyproject_config.py`
- Create: `tests/test_cleanup.py`
- Modify: `tests/test_cli_entrypoints.py`

- [ ] **Step 1: 写失败测试**

覆盖：
- `pyproject.toml` 必须声明可安装 build-system，并把 `ops` 打进 wheel。
- `cleanup plan` 会列出白名单临时产物。
- `cleanup apply` 会删除白名单路径并返回结果分类。
- CLI help 和 JSON 输出包含 `cleanup apply`。

- [ ] **Step 2: 运行测试确认先红**

Run: `PYTHONPATH=/root/work/OP_Linux uv run pytest tests/test_pyproject_config.py tests/test_cleanup.py tests/test_cli_entrypoints.py -q`
Expected: FAIL

### Task 2: 实现 package 与 cleanup

**Files:**
- Modify: `pyproject.toml`
- Modify: `ops/cli/cleanup.py`
- Modify: `ops/cli/app.py`

- [ ] **Step 1: 实现最小代码使测试通过**

加入 build-system、wheel 打包配置，新增 cleanup action 枚举和 apply 执行器。

- [ ] **Step 2: 跑目标测试**

Run: `PYTHONPATH=/root/work/OP_Linux uv run pytest tests/test_pyproject_config.py tests/test_cleanup.py tests/test_cli_entrypoints.py -q`
Expected: PASS

### Task 3: 验证真实入口

**Files:**
- None

- [ ] **Step 1: 验证 pytest 入口**

Run: `uv run pytest -q`
Expected: PASS without manual `PYTHONPATH`

- [ ] **Step 2: 验证 cleanup plan/apply**

Run: `uv run python -m ops.cli cleanup plan --env wsl --repo-root /root/work/OP_Linux`
Run: `uv run python -m ops.cli cleanup apply --env wsl --repo-root /root/work/OP_Linux`
Expected: 返回结构化 JSON，且 apply 只处理仓库白名单内临时产物。
