---
status: active
owner: AgentPlane maintainers
last_verified: 2026-04-29
superseded_by: null
audience: agent
---


# Git 规范

结论：Git 提交与合并规范，默认短生命周期分支 + PR + CI 通过 + squash merge；提交必须遵循 Conventional Commits + 原子提交 + LF 换行符统一。

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
| `repository` | `agentplane/domain/repository/` |
| `infra` | 基础设施相关 |
| `ingress` | 入口治理相关 |
| `app` | 应用生命周期相关 |

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
uv run python -m agentplane.domain.repository.commit_message --message "docs(git): add commit policy enforcement"
```

如果希望 Git 在本地提交时自动拦截不合规标题，可启用仓库内 hook：

```bash
git config core.hooksPath .githooks
```

CI 会检查 PR 范围内的新增提交标题；直接 push 到 `main` 时只检查 HEAD，避免早期历史提交标题阻塞主线。当前默认流程仍应走短生命周期分支和 PR。

---

## 分支策略

| # | 规则 | 级别 |
|---|------|------|
| 1 | `main` 分支始终可部署 | 🔴 |
| 2 | 默认使用短生命周期分支承接新变更 | 🔴 |
| 3 | 合并到 `main` 前必须通过本地最小验证或 CI | 🔴 |
| 4 | 默认通过 PR 合并到 `main` | 🔴 |
| 5 | 默认使用 squash merge，保持 `main` 历史可读 | 🟡 |
| 6 | 合并后删除已完成的远端和本地工作分支 | 🟡 |
| 7 | 禁止 `push --force` 到 `main` | 🔴 |

### 分支命名

| 场景 | 推荐分支 |
| --- | --- |
| AI Agent 日常变更 | `codex/<简述>` |
| 功能开发 | `feat/<简述>` |
| Bug 修复 | `fix/<简述>` |
| 重构 | `refactor/<简述>` |
| 文档或配置维护 | `docs/<简述>` / `chore/<简述>` |

### 合并到 main 的标准流程

1. 更新本地主分支：

   ```bash
   git switch main
   git pull --ff-only origin main
   ```

2. 创建短生命周期分支：

   ```bash
   git switch -c codex/<short-description>
   ```

3. 按逻辑单元提交，保持每个 commit 可独立解释和回滚：

   ```bash
   git add <files>
   git commit -m "fix(scope): describe the change"
   ```

4. 合并前运行最小验证。普通变更默认运行：

   ```bash
   uv run python -m agentplane.cli repo health-check --repo-root .
   ```

   文档-only 变更至少运行：

   ```bash
   uv run python -m agentplane.cli repo docs-sanity --repo-root .
   ```

5. 推送分支并打开 PR：

   ```bash
   git push -u origin codex/<short-description>
   ```

6. 等待 PR CI 通过。当前 PR gate 包含 fast test、docs-sanity、secret-scan、privacy-scan；发布或手动门禁使用 release-check。

7. CI 通过后默认 squash merge 到 `main`。如果一个 PR 内包含多个必须保留的独立提交，应优先拆成多个 PR，而不是依赖 merge commit 保留混合历史。

8. 合并后同步并清理分支：

   ```bash
   git switch main
   git pull --ff-only origin main
   git branch -d codex/<short-description>
   git push origin --delete codex/<short-description>
   ```

### 直接提交到 main 的例外

直接在 `main` 上提交只适用于维护者明确判断的低风险单点变更或紧急修复，并且仍必须满足：

- 提交前运行对应最小验证。
- 提交消息符合 Conventional Commits。
- 不使用 `push --force`。
- 不混入无关文件、真实 secrets 或本地运行态材料。

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
