# Win WSL SSH Remote Execution Design

## Goal

为当前 `Windows + WSL + SSH -> 远端 Linux` 的开发运维模式定义一个长期可用的标准执行架构，减少 PowerShell quoting 故障，提升日常执行效率，并把正式生产变更收口到可测试、可审计、可复盘的入口。

## Scope

- 定义 Windows、WSL、Python CLI、Bash wrapper、SSH、远端执行之间的分层职责。
- 明确当前 `run_remote_bash.sh` 的定位。
- 给出 PowerShell 侧规则、WSL-first 工作流、CLI 演进方向、效率优化方向、治理与安全边界。
- 给出默认路径、备选路径和禁止路径。

## Non-Goals

- 不在本设计中直接实现 `ops.cli remote ...` 子命令。
- 不在本设计中重构已有应用交付、1Panel、tenant secrets 等其它控制面功能。
- 不把一次性 break-glass 运维动作完全消灭；只定义它们的边界。

## Problem Statement

当前主要故障模式发生在：

- `PowerShell -> wsl.exe -> bash -lc -> ssh -> remote bash`

在这条链路里，`$()`、`$var`、CRLF、多层引号、here-string 和 shell 重解析会彼此叠加，导致远端命令失真。问题本质不是 SSH 本身，而是执行文本跨越了过多语义边界。

同时，当前效率瓶颈也不在“脚本到底走 stdin 还是 scp”，而在：

- PowerShell / WSL / SSH 边界穿越过多
- 一个逻辑动作被拆成多次 `wsl.exe` 和多次 `ssh`
- SSH 未默认启用连接复用

## Decision Summary

长期标准应采用：

1. PowerShell 只作为入场层
2. WSL/Linux 作为唯一正式执行层
3. `uv run python -m ops.cli ...` 作为唯一正式命令面
4. Bash wrapper 只保留为薄包装/兼容层/救援层
5. 复杂远端逻辑只能以 Linux 文件或 Linux stdin 的形式进入 SSH
6. 默认启用 SSH 连接复用

## Design

### Layer 1: Windows Entry

Windows 侧只负责把参数安全送入 WSL，不承担复杂 shell 组装逻辑。

默认规则：

- 使用 `pwsh 7`
- 优先 `wsl.exe -u root -e <program> <args...>`
- 尽量避免 `wsl.exe ... bash -lc '...'`

Windows PowerShell 5.1 不再作为复杂 WSL/SSH 驱动层推荐路径。

### Layer 2: WSL Execution

正式动作在 WSL 内部执行，并使用 Linux 路径、Linux 文本文件、Linux 工具链完成编排。

这意味着：

- PowerShell 不再生成最终远端 shell 文本
- 复杂 Bash、SQL、awk、sed、heredoc 一律留在 Linux 文件中
- 日常入口可以是 WSL alias/function，但正式真源必须是 CLI

### Layer 3: Official Control Plane

正式执行面应继续向：

```bash
uv run python -m ops.cli ...
```

收口。

推荐新增最小正式命令面：

```bash
uv run python -m ops.cli remote bash <target> --repo-root <linux-path> [--script-file <linux-path>] [--dry-run] [-- <arg>...]
```

该命令的职责仅限于：

- 解析 SSH target
- 处理 worktree/common root
- 安全执行远端 Bash 脚本文件或 stdin
- 输出结构化结果

### Layer 4: Bash Wrapper

当前的：

- [run_remote_bash.sh](/root/work/OP_Linux/.worktrees/codex-prod0-postgres-admin-cutover/ops/scripts/remote/run_remote_bash.sh)

是正确的过渡方案，但不应继续膨胀成长期主产品面。

它的长期定位应是：

- 兼容入口
- CLI 未覆盖场景的薄 shim
- break-glass/人工救援路径

不应继续承载：

- 大量业务 flag
- 复杂状态机
- 审计/ledger 主逻辑
- 正式 plan/apply 编排

### Layer 5: Remote Execution

默认主路径：

- `WSL Linux script file/stdin -> ssh -T -> remote bash -s -- [args]`

这是当前环境下最稳的远端 Bash 传输方式。

原因：

- 避免 PowerShell 本地展开 `$()` 与 `$var`
- 避免多层 quoting 嵌套
- 对长脚本、复杂 SQL/awk/sed 适配最好
- 审计性比 inline shell 字符串更好

备选路径：

- `scp` / `tar | ssh` 到远端临时目录后执行

适合：

- 多文件资产
- 大脚本包
- 需要远端复跑和显式留档的操作

不推荐：

- PowerShell 内联多层 `ssh ... bash -lc ...`
- `base64` 作为默认脚本传输模式
- 把单行 `ssh` 命令扩展成复杂生产流程

## Efficiency Design

性能优化的优先级如下：

### 1. SSH Connection Reuse

默认启用：

- `ControlMaster=auto`
- `ControlPersist=5m~15m`
- `ControlPath=/tmp/.../%C`

这比“把脚本从 stdin 改成 base64”更有实际收益。

### 2. Reduce Boundary Crossings

一个逻辑动作应尽量收敛成：

- 一次 PowerShell -> WSL
- 一次 WSL CLI 编排
- 一组复用连接下的远端操作

而不是拆成多次 `wsl.exe` 与多次独立 `ssh`。

### 3. Transfer Modes

默认：

- 一次性远端脚本：`bash -s`
- 单文件：`scp`
- 多文件一次性投递：`tar | ssh tar`

按需：

- 重复同步目录：`rsync`
- 长任务：远端后台执行 + 日志跟随

## Governance And Security

长期标准不能只解决“命令能跑”，还要解决“谁能改生产、改前后留什么记录”。

### Formal Change Path

所有会改变正式状态的操作，默认必须从正式 CLI 发起，并具备：

- 参数校验
- preflight
- plan/apply 分离
- 结构化结果输出
- 失败点记录
- 回滚提示

### Secret Model

真源应保持在：

- `secrets/app-resources/...`
- `secrets/services/<service>/admin.<target>.*`

远端 `/opt/env_ubuntu/...` 和运行时 env 都只是派生副本。

### Remote Staging

远端 staging 必须使用每次唯一的操作目录，例如：

- `/run/oplinux/<op_id>`
- `/tmp/oplinux/<op_id>`

不得复用固定共享目录。

### Audit

长期应补上 operation ledger，至少记录：

- 操作 ID
- 操作者
- 时间
- 目标主机
- 输入摘要
- 渲染后的命令
- 结果
- 失败点

## Allowed Exceptions

允许例外：

- bootstrap
- read-only probe
- break-glass 救援
- 尚未模型化但必须立即执行的面板/厂商操作

例外条件：

- 必须有 runbook
- 作用域最小化
- 优先只读
- 不新增长期 secrets 副本
- 执行后补记录

同类动作第二次出现，就应升级进入 `ops.cli`。

## Prohibited Patterns

- 在 PowerShell 里拼整条 `wsl.exe ... bash -lc \"ssh ... '...$(...)...$var...'\"`
- 使用 Windows PowerShell 5.1 作为复杂 WSL/SSH 驱动层
- 双引号 here-string 承载远端 shell payload
- `Invoke-Expression` / `iex`
- 固定远端中转目录
- 上传远端临时文件后不清理
- 把 shell wrapper 当成长期正式控制面
- 继续把正式生产变更停留在“runbook + 手工 apply”

## Recommended Migration Direction

### Short Term

- 保留 `run_remote_bash.sh`
- 在 runbook 中把其定义为推荐兼容层
- 补 SSH 连接复用
- 把 PowerShell 侧规则写清楚

### Medium Term

- 新增 `ops.cli remote bash`
- 把正式文档和自动化入口切到 CLI
- 让 Bash wrapper 只做 shim

### Long Term

- 把正式 apply 纳入统一 ledger
- 收紧 SSH 信任与认证基线
- 收紧 shell 字符串执行面

## Verification

- 现有 wrapper/helper 测试：
  `uv run pytest tests/test_ssh_targets.py`
- 现有治理基线：
  `uv run python -m ops.cli audit filesystem --env wsl`
- 新命令面上线后，应新增 CLI 入口测试、dry-run 测试和结构化输出测试。
