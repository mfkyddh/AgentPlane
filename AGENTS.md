---
status: active
owner: AgentPlane maintainers
last_verified: 2026-04-29
superseded_by: null
audience: both
---

# AI 助手工作规范

> 👤 **人类读者**：本文档面向 AI Agent。如果你想了解"AI 是怎么工作的"，请查看
> [docs/getting-started/how-agent-works.md](docs/getting-started/how-agent-works.md)。
>
> 本文档是 AI 助手的工作手册，每次对话自动注入。只放核心约束，详细规范见 `docs/reference/`。
>
> **维护规则**：本文档不超过 120 行。新规则一律先写进 reference 文档，只有 🔴 级别规则才可提炼一行到此处。

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

---

## 执行入口

```bash
agentplane <domain> <surface> <verb> [flags]
```

AI 面向人的意图入口是 Skill；Skill 只做触发、路由和约束，正式执行仍回到 `agentplane ...`。

| 你想做什么 | 正确入口 |
|-----------|----------|
| 命令列表 | `agentplane --help` |
| 仓库健康检查 | `agentplane repo health-check` |
| 发布前检查 | `agentplane repo release-check` |
| 基础设施 | `agentplane infra ...` |
| Secrets | `agentplane infra secrets ...` |
| 现场验证 | `agentplane infra live-gate ...` |
| 应用交付 | `agentplane app ...` |

---

## 跨平台核心约束

- Windows 默认 `pwsh`，需 Linux 时 `wsl.exe -e <程序>`
- 远程 Linux 走 `agentplane infra remote bash`，禁止手写多层 SSH
- Python 用 `uv`，Node 用 `pnpm`，禁止 `UV_PROJECT_ENVIRONMENT` 指向平台路径

> 完整规范：[docs/reference/cross-platform.md](docs/reference/cross-platform.md)

---

## 安全核心约束

- 真实 Secrets 只放 `secrets/`（已被 `.gitignore` 保护）
- 非敏感模板放 `templates/`
- 新 PEM 私钥必须 `chmod 600`

---

## Git 核心约束

- 原子提交，无关变更不混入
- Conventional Commits：`type(scope): description`，type 仅限 `feat|fix|refactor|docs|test|chore|style|perf`
- 超过 3 个文件或跨模块变更时必须有 body
- `.gitattributes` 为换行符唯一权威（`* text=auto eol=lf`），`core.autocrlf=false`
- 默认短生命周期分支 + PR + CI 通过 + squash merge，合并后清理分支
- 禁止 `push --force` 到 main

> 完整规范：[docs/reference/git-conventions.md](docs/reference/git-conventions.md)

---

## 反模式

| ❌ 不要 | ✅ 应该 |
|---------|--------|
| 把 `scripts/` 当第一入口 | 使用 `agentplane ...` |
| Skill 直接拼 SSH/Docker/API | Skill 做路由，执行走 CLI |
| 手写多层 `ssh ... bash -c` | 使用 `infra remote bash` |
| 大批量变更一次性提交 | 按逻辑单元拆分 |
| 格式调整混入功能变更 | 格式调整独立提交 |

---

## 文档索引

完整地图见 [docs/README.md](docs/README.md)。AI 执行时最常需要：

| 文档 | 用途 |
|------|------|
| [docs/architecture/control-plane.md](docs/architecture/control-plane.md) | 控制面核心合同 |
| [docs/reference/documentation-governance.md](docs/reference/documentation-governance.md) | 文档治理（emoji、链接、门禁） |
| [docs/reference/cross-platform.md](docs/reference/cross-platform.md) | 跨平台规范 |
| [docs/maintainers/control-plane-authoring.md](docs/maintainers/control-plane-authoring.md) | 代码、Skill、文档、测试联动 |
| [docs/reference/git-conventions.md](docs/reference/git-conventions.md) | Git 规范 |
