---
status: active
owner: AgentPlane maintainers
last_verified: 2026-04-24
superseded_by: null
---

# Git 规范

> 本文档定义 AgentPlane 仓库的完整 Git 工作流规范。核心约束见 `AGENTS.md` 必读摘要。

---

## AGENTS.md 维护规则

AGENTS.md 是每次对话自动注入的工作手册，**不是规范文档**。为保证其精简性和信号密度，遵循以下规则：

| # | 规则 | 级别 |
|---|------|------|
| 1 | AGENTS.md 不超过 120 行 | 🔴 |
| 2 | 新规则一律先写进 `docs/reference/` 对应文档 | 🔴 |
| 3 | 只有 🔴 级别规则才可提炼一行到 AGENTS.md 必读摘要 | 🔴 |
| 4 | 每次往 AGENTS.md 添加内容时，必须评估是否需要同步移除旧内容 | 🟡 |
| 5 | 详细解释、枚举、示例留在 reference 文档，AGENTS.md 只放链接 | 🔴 |

**判断标准**：如果你添加的内容需要"因为…"来解释，它属于 reference 文档，不属于 AGENTS.md。

---

## 提交原子性

每条规则都是 AGENTS.md 中"原子提交"规则的详细展开。

### 逻辑变更单元

一个不可再分的最小有意义变更。判断标准：**能否用一句话说清楚"这次提交做了什么"**——如果需要"和"来连接，就应该拆分。

**合格的单个单元**：
- 重命名一个域（CLI + domain + tests + ledgers + skills + 文档引用）
- 修复一个 bug 及其对应的测试
- 新增一个 CLI 子命令及其文档
- 更新一组文档中的术语

**不合格（需要拆分）**：
- 重命名两个域 → 拆为 2 个提交
- 修 bug 时顺手格式化了其他无关文件 → 拆为 `fix` + `style`
- 新功能 + 配套文档 + 配套测试 → 如果文件分散在不同模块，按模块拆

### 暂存文件数阈值

| 暂存文件数 | 动作 |
|-----------|------|
| ≤ 5 | 正常提交 |
| 6–15 | 自查：这些变更是否属于同一个逻辑单元？ |
| > 15 | **必须评估拆分**：几乎一定是多个逻辑单元混在一起 |

---

## 提交消息（Commit Message）

所有提交消息必须遵循 [Conventional Commits](https://www.conventionalcommits.org/) 格式：

```
<type>(<scope>): <description>

[可选 body：补充说明]

[可选 footer：关联信息]
```

### Type 枚举

只允许以下值：

| type | 用途 | 示例 |
|------|------|------|
| `feat` | 新功能 | `feat(cli): add infra automation subcommand` |
| `fix` | 修复 bug | `fix(projection): resolve path resolution on Windows` |
| `refactor` | 重构（不改行为） | `refactor(domain): rename host to infra` |
| `docs` | 仅文档变更 | `docs(architecture): update control-plane spec` |
| `test` | 仅测试变更 | `test(infra): add live gate integration tests` |
| `chore` | 构建/工具/配置 | `chore: unify line endings via .gitattributes` |
| `style` | 格式调整（不影响逻辑） | `style: remove trailing whitespace` |
| `perf` | 性能优化 | `perf(ledger): cache inventory lookups` |

### Scope 枚举

按项目实际模块：

| scope | 对应模块 |
|-------|---------|
| `cli` | `agentplane/cli/` |
| `domain` | `agentplane/domain/` |
| `adapters` | `agentplane/adapters/` |
| `providers` | `agentplane/providers/` |
| `runtime` | `agentplane/runtime/` |
| `scripts` | `agentplane/scripts/` |
| `infra` | 基础设施相关 |
| `ingress` | 入口治理相关 |
| `app` | 应用生命周期相关 |
| `plugin` | `plugins/` |

跨模块变更时，选择**主要影响**的模块作为 scope。如果影响均匀，可省略 scope（如 `chore: ...`）。

### Description 规则

| # | 规则 | 原因 |
|---|------|------|
| 1 | 祈使句、现在时（`add` 不用 `added`） | 与 Git 自身风格一致 |
| 2 | 首字母小写，结尾不加句号 | 保持简洁 |
| 3 | 不超过 72 个字符 | `git log --oneline` 有截断 |
| 4 | 说"做了什么"而非"怎么做的" | diff 已经说明了 how |

### Body 规则

| # | 规则 | 原因 |
|---|------|------|
| 1 | 超过 3 个文件或涉及跨模块变更时，必须有 body | 一行说不清 |
| 2 | Body 用条目式列出具体变更 | 可读性优于散文 |
| 3 | Body 解释"为什么"，而非"做了什么" | diff 已经说明了 what |

### 示例

**正确**：
```
refactor(domain): rename host to infra

- Replace 'host' domain with 'infra' across CLI, domain logic,
  tests, ledgers, and skills
- Update all documentation and plugin references
- Move projection/runtime_env into app/projection package

'host' is ambiguous with /etc/hosts and SSH host keys.
'infra' better reflects infrastructure management scope.
```

**错误**：
```
❌ refactor: rename host->infra and website->ingress domains
   （两个独立重命名混在一个提交）

❌ Fixed the bug where paths were wrong on Windows
   （非祈使句，无 type 前缀）

❌ feat: update stuff
   （描述无信息量）
```

### 本地校验

仓库提供提交消息检查脚本：

```bash
uv run python scripts/check_commit_message.py --message "docs(git): add commit policy enforcement"
```

如果希望 Git 在本地提交时自动拦截不合规标题，可启用仓库内 hook：

```bash
git config core.hooksPath .githooks
```

CI 会检查 PR 范围内的新增提交标题；直接 push 到 `main` 时只检查 HEAD，避免早期历史提交标题阻塞主线。等历史完全收敛后，可把 push 检查收紧为完整 push range。

---

## 分支策略

| # | 规则 | 级别 |
|---|------|------|
| 1 | `main` 分支始终可部署 | 🔴 |
| 2 | 功能开发使用 `feat/<简述>` 分支 | 🟡 |
| 3 | Bug 修复使用 `fix/<简述>` 分支 | 🟡 |
| 4 | 重构使用 `refactor/<简述>` 分支 | 🟡 |
| 5 | 合并到 `main` 前必须通过测试 | 🔴 |
| 6 | 禁止 `push --force` 到 `main` | 🔴 |

> 🟢 **当前阶段**：单人项目，直接在 `main` 上提交是可接受的。当项目进入多人协作或有 CI 后，应切换到分支 + 合并模式。

---

## 换行符与编码

| # | 规则 | 级别 |
|---|------|------|
| 1 | `.gitattributes` 为换行符唯一权威，仓库级 `core.autocrlf=false` | 🔴 |
| 2 | 所有文本文件入库 LF（`* text=auto eol=lf`） | 🔴 |
| 3 | 仅 `*.bat` / `*.cmd` 例外允许 CRLF | 🟡 |

背景：Windows 宿主 + WSL 共用同一份 checkout，工作区必须统一 LF，否则 WSL 侧工具会将 `\r` 视为内容的一部分。

---

## 仓库配置

| # | 规则 | 级别 |
|---|------|------|
| 1 | 提交前确保已配置 `user.name` 和 `user.email` | 🟡 |
| 2 | 避免并行写入 Git 配置文件 | 🟢 |
| 3 | AgentPlane 管理的应用仓库，Git worktree 必须放在 `<repo>/.worktrees/` | 🟡 |
| 4 | 创建 worktree 前，应用仓库的 `.gitignore` 必须已忽略 `.worktrees/` | 🔴 |
| 5 | `secrets/` 必须在 `.gitignore` 中 | 🔴 |
| 6 | 提交前检查 `git diff --cached`，确认无意外文件混入 | 🟡 |
