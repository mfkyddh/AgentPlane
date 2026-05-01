---
status: active
owner: AgentPlane maintainers
last_verified: 2026-04-30
superseded_by: null
audience: both
---

# AI 助手工作规范

> 👤 **人类读者**：本文档面向 AI Agent。如果你想了解"AI 是怎么工作的"，请查看
> [docs/getting-started/getting-started.md](docs/getting-started/getting-started.md)。
>
> 本文档是 AI 助手的工作手册，每次对话自动注入。只放核心约束，详细规范见 `docs/reference/`。
>
> **维护规则**：本文档不超过 120 行。新规则一律先写进 reference 文档，只有 🔴 级别规则才可提炼一行到此处。

---

## 项目概述

AgentPlane 是一个 Agent-first 控制面 CLI 工具。所有正式操作通过 `agentplane <domain> <surface> <verb> [flags]` 进入，提供 plan → execute → verify → record 生命周期。`.agents/skills/` 中定义的 Skill 是 AI 入口，它们路由到 CLI 命令——永远不要绕过 CLI。

**入口**: `agentplane/cli/app.py` → `main()`（也可 `python -m agentplane`）。

**常用命令**: `uv run agentplane ...`（无需全局安装）· `agentplane test fast --tb=short`（快速测试）· `agentplane repo health-check --repo-root .`（健康检查）· `agentplane --help`（命令列表）

---

## 必读摘要

| # | 规则 | 级别 |
|---|------|------|
| 1 | **统一入口**：所有正式操作必须从 `agentplane ...` 进入 | 🔴 |
| 2 | **Secrets 绝不提交**：敏感信息只放 `secrets/` 目录 | 🔴 |
| 3 | **单份源码**：Windows 和 WSL 共用同一个仓库目录 | 🔴 |
| 4 | **单虚拟环境**：只使用根目录 `.venv`，不创建平台变种 | 🔴 |
| 5 | **原子提交**：每个逻辑变更单元独立提交，暂存超 15 文件必须评估拆分 | 🔴 |
| 6 | **Conventional Commits**：`type(scope): description` 格式 | 🔴 |
| 7 | **先计划后执行**：高风险操作必须有 plan 阶段 | 🔴 |
| 8 | **固定顶层结构**：新增顶层目录前先更新 `docs/reference/repository-structure.md` | 🔴 |
| 9 | **执行后必验证**：每次变更都运行最小验证 | 🟡 |
| 10 | **用 `pwsh` 而非 `cmd`**：Windows 上默认用 PowerShell | 🟡 |
| 11 | **先查帮助再执行**：不确定时用 `--help` | 🟡 |
| 12 | **文档必须可达**：新增 active 文档必须加入索引或被上游文档链接 | 🔴 |
| 13 | **测试分层+并行**：新增测试必须标记 unit/integration/e2e；禁止按操作/环境拆分测试文件 | 🔴 |
| 14 | **main 合入门禁**：合入 `main` 前必须通过测试或 CI | 🔴 |
| 15 | **Skill 同步**：正式能力变更必须同步 `.agents/skills` 或说明无需更新 | 🔴 |
| 16 | **单人维护收尾**：小任务完成后必须自动 commit、合入本地 `main`、推送 `origin main` | 🔴 |
| 17 | **提交前必须通过本地检查**：`git commit` 前通过 pre-commit，`git push` 前通过 pre-push | 🔴 |

---

## 跨平台约束

- Windows 默认 `pwsh`，需 Linux 时 `wsl.exe -e <程序>`
- 远程 Linux 走 `agentplane infra remote bash`，禁止手写多层 SSH
- Python 用 `uv`，Node 用 `pnpm`，禁止 `UV_PROJECT_ENVIRONMENT` 指向平台路径

> 完整规范：[docs/reference/cross-platform.md](docs/reference/cross-platform.md)

## 安全约束

- 真实 Secrets 只放 `secrets/`（已被 `.gitignore` 保护）
- 非敏感模板放 `templates/`
- 新 PEM 私钥必须 `chmod 600`

## Git 约束

- 原子提交，无关变更不混入
- Conventional Commits：`type(scope): description`，type 仅限 `feat|fix|refactor|docs|test|chore|style|perf`
- 超过 3 个文件或跨模块变更时必须有 body
- `.gitattributes` 为换行符唯一权威（`* text=auto eol=lf`），`core.autocrlf=false`
- 单人维护默认完成小任务后自动 commit、合入本地 `main`、推送 `origin main`
- 禁止 `push --force` 到 main

> 完整规范：[docs/reference/git-conventions.md](docs/reference/git-conventions.md)

---

## 编码行为准则

基于 [Karpathy Guidelines](https://x.com/karpathy/status/2015883857489522876)，减少常见 LLM 编码错误：

### 1. 先思考再编码

- 明确假设；不确定就问，不要猜测
- 有多种解释时全部列出，不要默默选一种
- 有更简单方案时主动提出；遇到不清楚的地方停下来，说明哪里不确定

### 2. 简洁优先

- 最少代码解决问题；不加未要求的功能
- 单次使用的代码不做抽象
- 不加没被要求的"灵活性"或"可配置性"
- 不为不可能的场景写错误处理
- 200 行能缩到 50 行就重写

### 3. 精准改动

- 只改必须改的；不"顺手改进"相邻代码
- 匹配现有风格，即使你会写得不同
- 发现无关死代码只提醒，不删除
- 只清理自己改动造成的孤儿代码

### 4. 目标驱动执行

- 把任务转化为可验证的目标："加验证" → "写测试然后让它通过"
- 多步任务先列计划：`步骤 → 验证方式`
- 强成功标准让 AI 能独立循环；弱标准（"让它能跑"）需要反复确认

---

## 反模式

`scripts/` 当入口 → 用 `agentplane ...`；Skill 拼 SSH/Docker → 走 CLI；多层 `ssh bash -c` → `infra remote bash`；大批量单提交 → 按逻辑拆分；格式混功能 → 独立提交；平台变种 venv → 只用根 `.venv`。

## 文档索引

完整地图见 [docs/README.md](docs/README.md)。最常用：[控制面合同](docs/architecture/control-plane.md) · [跨平台](docs/reference/cross-platform.md) · [Git 规范](docs/reference/git-conventions.md) · [测试分层](docs/reference/testing-architecture.md) · [代码联动](docs/maintainers/control-plane-authoring.md)
