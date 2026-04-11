# Win WSL SSH Remote Execution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把当前 `Windows + WSL + SSH` 运维链路从“可用但偏临时的 wrapper 模式”推进到“WSL-first、CLI-first、可复用、可审计”的正式执行架构。

**Architecture:** 先固化 PowerShell/WSL 边界与 SSH 复用，再把现有 wrapper 收口为兼容层，并补出 `ops.cli remote bash` 的最小正式命令面。最后再处理 apply 审计、远端 staging 清理和 SSH 基线收紧。

**Tech Stack:** PowerShell 7, WSL, Bash, Python (`uv`, `pytest`), OpenSSH, repository governance docs

---

### Task 1: 固化 PowerShell 与 WSL 边界规则

**Files:**
- Modify: `AGENTS.md`
- Modify: `docs/runbooks/wsl-host-governance.md`
- Modify: `docs/runbooks/powershell-wsl-remote-bash.md`

- [ ] **Step 1: 把 PowerShell 规则写成稳定仓库规则**

明确：
- 统一推荐 `pwsh 7`
- PowerShell 只负责传 `argv` 进入 WSL
- 能 `wsl.exe -e <program>` 就不要 `bash -lc`
- 禁止 PowerShell 拼复杂远端 shell 文本

- [ ] **Step 2: 在 runbook 中加入允许/禁止样例**

增加：
- 推荐调用样例
- 禁用写法清单
- 何时允许 stdin，何时必须 script-file

### Task 2: 启用 SSH 连接复用

**Files:**
- Modify: `secrets/ssh/config`
- Modify: `templates/ssh/config.example` or equivalent tracked template if present
- Modify: `docs/runbooks/powershell-wsl-remote-bash.md`

- [ ] **Step 1: 为仓库 SSH alias 增加连接复用配置**

建议：
- `ControlMaster auto`
- `ControlPersist 10m`
- `ControlPath /tmp/oplinux-ssh-%C`

- [ ] **Step 2: 做只读验证**

Run:
- `ssh -F /root/work/OP_Linux/secrets/ssh/config prod0-main true`
- 重复执行同一命令并比较延迟

Expected:
- 二次连接明显复用

### Task 3: 冻结 shell wrapper 职责

**Files:**
- Modify: `ops/scripts/remote/run_remote_bash.sh`
- Modify: `docs/runbooks/powershell-wsl-remote-bash.md`

- [ ] **Step 1: 明确 wrapper 只是兼容层**

要求：
- 不再继续向 wrapper 堆积业务 flag
- 帮助信息明确其定位是兼容/引导层

- [ ] **Step 2: 保证 wrapper 只做三件事**

只保留：
- repo-root 与 ssh config 解析
- 脚本文件 / stdin 到远端 `bash -s --`
- 参数透传

### Task 4: 补 `ops.cli remote bash` 的最小正式入口

**Files:**
- Modify: `ops/cli/app.py`
- Create or modify: `ops/cli/remote.py`
- Modify: `ops/ssh.py`
- Modify: `tests/test_cli_entrypoints.py`
- Create: `tests/test_remote_cli.py`

- [ ] **Step 1: 先写失败测试**

覆盖：
- `uv run python -m ops.cli remote bash <target> --script-file ...`
- `--dry-run`
- worktree 下 repo-root / ssh config 解析
- 非 root 目标自动 `sudo`

- [ ] **Step 2: 运行测试确认先红**

Run:
- `uv run pytest tests/test_cli_entrypoints.py tests/test_remote_cli.py -q`

- [ ] **Step 3: 实现最小命令面**

命令面：
- `ops.cli remote bash <target> [--repo-root <path>] [--script-file <linux-path>] [--dry-run] [-- <arg>...]`

- [ ] **Step 4: 测试变绿**

Run:
- `uv run pytest tests/test_cli_entrypoints.py tests/test_remote_cli.py tests/test_ssh_targets.py -q`

### Task 5: 把正式文档与自动化入口切到 CLI

**Files:**
- Modify: `docs/runbooks/powershell-wsl-remote-bash.md`
- Modify: `docs/runbooks/wsl-host-governance.md`
- Modify: relevant runbooks under `docs/runbooks/`

- [ ] **Step 1: 所有正式示例优先改为 `uv run python -m ops.cli remote bash ...`**

wrapper 只保留为：
- 兼容入口
- 过渡说明
- break-glass 例外

- [ ] **Step 2: 审核现有 `wsl.exe -u root -e bash -lc 'ssh ...'` 示例**

把复杂示例改成：
- `wsl.exe -> uv run python -m ops.cli ...`
- 或 `wsl.exe -> Linux script file`

### Task 6: 收紧远端 staging 与 apply 记录

**Files:**
- Modify: `ops/cli/apps.py`
- Modify: `ops/scripts/remote/deploy_data_services_to_host.sh`
- Modify: `ops/scripts/remote/remote_deploy_data_services.sh`
- Modify: relevant app delivery runbooks

- [ ] **Step 1: 把固定远端中转目录改成唯一 op_id staging**

目标：
- 不复用固定目录
- 成功/失败都清理

- [ ] **Step 2: 为正式 apply 补最小操作记录**

至少输出：
- op_id
- target
- rendered command or artifact summary
- result

- [ ] **Step 3: 验证不会遗留 `/tmp` 敏感文件**

### Task 7: 收紧 SSH 基线与例外边界

**Files:**
- Modify: `secrets/ssh/config`
- Modify: `inventory/servers/*/inventory.json`
- Modify: relevant governance docs

- [ ] **Step 1: 评估并收紧 `StrictHostKeyChecking` 策略**

目标：
- 日常自动化不再长期依赖 `accept-new`

- [ ] **Step 2: 收紧 password auth / root-only 例外的文档边界**

明确：
- 什么是引导期例外
- 什么是长期默认

### Task 8: 最终验证

**Files:**
- Verification only

- [ ] **Step 1: CLI 与 SSH helper 测试**

Run:
- `uv run pytest tests/test_ssh_targets.py tests/test_cli_entrypoints.py tests/test_remote_cli.py -q`

- [ ] **Step 2: 远端只读连通性与 dry-run**

Run:
- `uv run python -m ops.cli remote bash prod0-main --dry-run --script-file /root/work/OP_Linux/ops/scripts/remote/example.sh`
- `printf "%s\n" "set -euo pipefail" "echo remote_ok" | uv run python -m ops.cli remote bash prod0-main`

- [ ] **Step 3: 治理检查**

Run:
- `uv run python -m ops.cli audit filesystem --env wsl`

Expected:
- 正式入口、wrapper、SSH 配置、文档和审计规则口径一致
