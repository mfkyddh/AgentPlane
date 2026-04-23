# 🤖 AI 助手工作规范

> 本文档是给 AI 助手（Agent）的工作手册，定义了在 AgentPlane 仓库中工作的规则、约定和最佳实践。
>
> **作用**：确保所有 AI 操作都遵循统一标准，避免因平台差异、命令方式不同或规范缺失导致的问题。

---

## 📌 必读摘要（先读这 10 条）

以下规则优先级最高，每次工作时都应首先检查：

| # | 规则 | 级别 | 原因 |
|---|------|------|------|
| 1 | **统一入口**：所有正式操作必须从 `agentplane ...` 进入 | 🔴 | 保证操作可追溯、可验证 |
| 2 | **Secrets 绝不提交**：敏感信息只放 `secrets/` 目录 | 🔴 | 防止密码泄露到 Git 历史 |
| 3 | **单份源码**：Windows 和 WSL 共用同一个仓库目录 | 🔴 | 避免配置分叉、状态不一致 |
| 4 | **单虚拟环境**：只使用根目录 `.venv`，不创建 `.venv-win` 等变种 | 🔴 | 保持环境一致性 |
| 5 | **原子提交**：每个逻辑变更单元独立提交，禁止大批量混提交 | 🔴 | 便于 bisect、revert、cherry-pick |
| 6 | **Conventional Commits**：提交消息必须使用 `type(scope): description` 格式 | 🔴 | 可按类型过滤，自动生成 changelog |
| 5 | **先计划后执行**：高风险操作必须有 `plan` 阶段 | 🔴 | 避免误操作造成损失 |
| 6 | **执行后必验证**：每次变更都要运行最小验证 | 🟡 | 确保变更生效且无副作用 |
| 7 | **用 `pwsh` 而非 `cmd`**：Windows 上默认用 PowerShell | 🟡 | 统一命令语法、兼容性好 |
| 8 | **先查帮助再执行**：不确定时用 `--help` 查看命令说明 | 🟡 | 减少试错、提高效率 |

> 🔴 = 强制（Must）— 不遵守会出问题  
> 🟡 = 推荐（Should）— 最佳实践  
> 🟢 = 注意（Note）— 补充说明

---

## 🚀 执行入口规范

### CLI 统一入口

所有正式操作**必须**通过以下命令进入：

```bash
agentplane <domain> <surface> <verb> [flags]
```

> 安装方式：`uv tool install -e .`（在项目根目录执行一次即可）。如果尚未安装，可用 `uv run agentplane` 作为临时替代。

**各级别入口对照表**：

| 你想做什么 | 正确入口 | ❌ 错误做法 |
|-----------|----------|------------|
| 查看命令列表 | `agentplane --help` | 直接翻源码猜命令 |
| 主机清理 | `agentplane infra cleanup ...` | 直接执行 `rm -rf` 或脚本 |
| 基础设施自动化 | `agentplane infra automation ...` | 手写 cron 任务 |
| 网络治理 | `agentplane infra network ...` | 直接操作 `iptables` |
| 远程执行 | `agentplane infra remote bash ...` | 手写多层 `ssh ... bash -c` |
| Secrets 管理 | `agentplane infra secrets ...` | 直接编辑 `.env` 文件 |
| 现场验证 | `agentplane infra live-gate ...` | 直接跑 pytest（会触发真实连接） |

**原因**：统一的 CLI 入口封装了环境解析、后端路由、错误处理和安全检查。绕过 CLI 直接操作会丢失这些保护。

### 命令动词约定

不同场景优先使用以下动词：

| 场景 | 推荐动词 |
|------|---------|
| 查询对象 | `search`、`get` |
| 变更对象 | `plan`、`apply`、`verify` |
| 刷新记录 | `refresh-ledger` |
| 工作流 | `run`、`fixture`、`migrate`、`doctor` |

**原因**：统一动词降低认知成本，也便于日志过滤和审计。

---

## 🖥️ 跨平台工作流

### Windows 宿主规范

| # | 规则 | 级别 | 原因 |
|---|------|------|------|
| 1 | 默认入口 Shell 使用 `pwsh`（PowerShell Core） | 🔴 | `cmd` 语法差异大，易出错 |
| 2 | `git`、`uv`、`pnpm`、测试等宿主子命令直接在 `pwsh` 中运行 | 🟡 | 减少 Shell 切换开销 |
| 3 | 需要 Linux 能力时，优先用 `wsl.exe -e <程序> <参数>` | 🟡 | 直接调用 WSL 程序，避免额外 Shell 层 |
| 4 | 只有需要 WSL 侧 Shell 特性（如管道、重定向）时才用 `wsl.exe bash -lc` | 🟢 | 减少不必要的 Shell 包装 |

### WSL 后端规范

| # | 规则 | 级别 | 原因 |
|---|------|------|------|
| 1 | Windows 和 WSL **共用同一份源码 checkout** | 🔴 | 避免两份代码不同步 |
| 2 | WSL 通过 Resolver 提供的 `/mnt/<盘符>/...` 绑定访问源码 | 🟢 | 这是系统提供的映射机制 |
| 3 | 不要仅为运行 WSL 操作而 clone 第二份仓库 | 🔴 | 会造成配置分叉和维护负担 |
| 4 | 避免两个 Shell（Windows + WSL）同时执行包管理器写入 | 🟡 | 防止 `.venv` 或 `node_modules` 损坏 |

### Linux / macOS 规范

| # | 规则 | 级别 | 原因 |
|---|------|------|------|
| 1 | 直接使用本地 POSIX Shell 执行本地命令 | 🟡 | 原生支持，无需额外适配 |
| 2 | 远程 Linux 操作应走：`pwsh → agentplane.cli → WSL/SSH backend` | 🔴 | 保持统一入口，不要手写多层命令 |

### 虚拟环境规范

| # | 规则 | 级别 | 原因 |
|---|------|------|------|
| 1 | Python 项目统一使用 `uv` 进行依赖安装和环境管理 | 🟡 | `uv` 速度快、行为一致 |
| 2 | 每个物理 checkout **只保留一个 `.venv`** | 🔴 | 禁止创建 `.venv-win`、`.venv-wsl` 等平台变种 |
| 3 | **不要**设置 `UV_PROJECT_ENVIRONMENT` 为平台相关路径 | 🔴 | 让 `uv` 自动使用根目录 `.venv` |
| 4 | Node.js 项目统一使用 `pnpm` | 🟡 | 速度快、磁盘省 |
| 5 | 临时 Node 二进制优先用 `pnpm dlx ...` | 🟡 | 避免全局安装 |

---

## 🔐 安全与敏感信息

### Secrets 管理

| # | 规则 | 级别 | 原因 |
|---|------|------|------|
| 1 | **真实 Secrets 只放在 `secrets/` 目录** | 🔴 | 该目录已被 `.gitignore` 保护 |
| 2 | 非敏感模板放在 `templates/` | 🟡 | 方便复用且可提交 Git |
| 3 | 控制面 Bootstrap 真源：`secrets/local/control-plane/` | 🟢 | 本地初始化输入面 |
| 4 | 目标环境 Secrets：`secrets/targets/<target>/` | 🟢 | 按目标环境隔离 |
| 5 | SSH 别名从 `secrets/ssh/config` 读取 | 🟡 | 避免在公共文档中硬编码环境特定别名 |
| 6 | 新生成的 PEM 私钥必须先执行 `chmod 600` | 🔴 | 防止密钥权限过宽导致 SSH 拒绝连接 |

### Git 规范

#### 提交原子性

| # | 规则 | 级别 | 原因 |
|---|------|------|------|
| 1 | 每个逻辑变更单元必须独立提交 | 🔴 | 便于 bisect、revert、cherry-pick |
| 2 | 暂存文件数超过 15 个时，必须评估是否拆分为多个提交 | 🔴 | 大批量混提交 = 追踪困难 |
| 3 | 禁止"先全做完再一次性提交"的工作模式 | 🔴 | 变更越大，出错概率越高，回退成本越高 |
| 4 | 无关变更不得混入同一提交（如：修 bug 顺手改格式） | 🔴 | 格式变更会掩盖实质变更，干扰 review 和 bisect |

**逻辑变更单元**：一个不可再分的最小有意义变更。例如：
- ✅ 重命名一个域（CLI + domain + tests + ledgers + skills + 文档引用）
- ✅ 修复一个 bug 及其对应的测试
- ✅ 新增一个 CLI 子命令及其文档
- ❌ 只改了一个文件的一行（可合并到同逻辑单元的提交中）
- ❌ 修 bug 时顺手格式化了其他无关文件

#### 提交消息（Commit Message）

所有提交消息必须遵循 [Conventional Commits](https://www.conventionalcommits.org/) 格式：

```
<type>(<scope>): <description>

[可选 body：补充说明]

[可选 footer：关联信息]
```

**Type 枚举**（只允许以下值）：

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

**Scope 枚举**（按项目实际模块）：

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

**Description 规则**：

| # | 规则 | 级别 | 原因 |
|---|------|------|------|
| 1 | 使用祈使句、现在时（`add` 不用 `added`，`fix` 不用 `fixed`） | 🔴 | 与 Git 自身风格一致（`Merge branch` 而非 `Merged branch`） |
| 2 | 首字母小写，结尾不加句号 | 🟡 | 保持简洁，避免与正文混淆 |
| 3 | 不超过 72 个字符 | 🔴 | `git log --oneline` 和 GitHub PR 列表有截断 |
| 4 | 说明"做了什么"而非"怎么做的" | 🟡 | `rename host to infra` > `change all references from host to infra` |

**Body 规则**（可选但推荐）：

| # | 规则 | 级别 | 原因 |
|---|------|------|------|
| 1 | 超过 3 个文件或涉及跨模块变更时，必须有 body | 🔴 | 一行说不清"为什么" |
| 2 | Body 用条目式列出具体变更 | 🟡 | 可读性优于散文 |
| 3 | Body 解释"为什么"而非"做了什么"（做了什么看 diff） | 🟡 | diff 已经说明了 what |

**正确示例**：
```
refactor(domain): rename host to infra

- Replace 'host' domain with 'infra' across CLI, domain logic,
  tests, ledgers, and skills
- Update all documentation and plugin references
- Move projection/runtime_env into app/projection package

'host' is ambiguous with /etc/hosts and SSH host keys.
'infra' better reflects infrastructure management scope.
```

**错误示例**：
```
❌ refactor: rename host->infra and website->ingress domains
   （两个独立重命名混在一个提交）

❌ Fixed the bug where paths were wrong on Windows
   （非祈使句，无 type 前缀）

❌ feat: update stuff
   （描述无信息量）
```

#### 分支策略

| # | 规则 | 级别 | 原因 |
|---|------|------|------|
| 1 | `main` 分支始终可部署 | 🔴 | 主线必须稳定 |
| 2 | 功能开发使用 `feat/<简述>` 分支 | 🟡 | 隔离开发，便于 review |
| 3 | Bug 修复使用 `fix/<简述>` 分支 | 🟡 | 同上 |
| 4 | 重构使用 `refactor/<简述>` 分支 | 🟡 | 同上 |
| 5 | 合并到 `main` 前必须通过测试 | 🔴 | 不合入已知故障 |
| 6 | 禁止 `push --force` 到 `main` | 🔴 | 不可逆操作，会覆盖他人工作 |

> 🟢 **当前阶段**：单人项目，直接在 `main` 上提交是可接受的。当项目进入多人协作或有 CI 后，应切换到分支 + 合并模式。

#### 换行符与编码

| # | 规则 | 级别 | 原因 |
|---|------|------|------|
| 1 | `.gitattributes` 为换行符唯一权威，仓库级 `core.autocrlf=false` | 🔴 | Windows+WSL 共用 checkout 必须统一 LF |
| 2 | 所有文本文件入库 LF（`* text=auto eol=lf`） | 🔴 | 跨平台一致性 |
| 3 | 仅 `*.bat` / `*.cmd` 例外允许 CRLF | 🟡 | Windows 原生脚本必须 CRLF |

#### 仓库配置

| # | 规则 | 级别 | 原因 |
|---|------|------|------|
| 1 | 提交前确保已配置 `user.name` 和 `user.email` | 🟡 | 避免匿名提交 |
| 2 | 避免并行写入 Git 配置文件 | 🟢 | 防止配置冲突 |
| 3 | AgentPlane 管理的应用仓库，Git worktree 必须放在 `<repo>/.worktrees/` | 🟡 | 统一存放位置 |
| 4 | 创建 worktree 前，应用仓库的 `.gitignore` 必须已忽略 `.worktrees/` | 🔴 | 防止 worktree 被误提交 |
| 5 | `secrets/` 必须在 `.gitignore` 中 | 🔴 | 防止敏感信息泄露到 Git 历史 |
| 6 | 提交前检查 `git diff --cached`，确认无意外文件混入 | 🟡 | 最后一道防线 |

---

## 🐳 服务与容器规范

### Docker Compose

| # | 规则 | 级别 | 原因 |
|---|------|------|------|
| 1 | 运行时命令统一使用 `docker compose`（空格） | 🔴 | 旧版 `docker-compose`（连字符）已弃用 |
| 2 | 服务资产放在 `infra/compose/<service>/` | 🟡 | 统一存放，便于查找 |
| 3 | 本地运行时 Secrets 放在 `secrets/services/` | 🟡 | 与 compose 文件分离 |
| 4 | 服务模板放在 `templates/services/` | 🟡 | 非敏感模板可复用 |
| 5 | 可按需保留 `docker-compose.wsl.yml` 或 `docker-compose.<target>.yml` | 🟢 | 特定后端需要差异化配置时 |

### 容器命名

| # | 规则 | 级别 | 原因 |
|---|------|------|------|
| 1 | 测试环境容器名以 `-dev` 结尾 | 🔴 | 明确区分环境，防止误删生产 |
| 2 | 生产环境容器名以 `-prod` 结尾 | 🔴 | 同上 |

### 网络与数据

| # | 规则 | 级别 | 原因 |
|---|------|------|------|
| 1 | 生产环境中，项目管理的容器和 1Panel 应用容器应接入 tracked truth 中声明的共享网络 | 🔴 | 保证服务间通信 |
| 2 | 专用网络只能作为附加（additive），不能替代共享网络 | 🟡 | 避免网络隔离导致服务不可达 |
| 3 | 持久化数据优先放在 `/data/<service>/...` | 🟡 | 统一数据盘路径，便于备份 |

---

## ✅ 完成标准（Definition of Done）

每次工作完成后，必须满足以下标准：

| # | 检查项 | 级别 | 原因 |
|---|--------|------|------|
| 1 | 运行最小相关验证 | 🔴 | 证明变更生效 |
| 2 | 优先使用 live state 检查（如 `docker ps`、`docker inspect`、CLI verify） | 🟡 | 实际状态比文档更可信 |
| 3 | 修改了文档、skill 或 Codex 配置时，运行对应的合同测试 | 🟡 | 防止文档与实现不一致 |
| 4 | 如果某项无法验证，必须明确说明**什么没验证**以及**为什么** | 🔴 | 避免留下隐性风险 |

### 复杂工作先计划

> 🟡 **推荐**：涉及行为变更或复杂逻辑的工作，应先制定计划再实施。
>
> 原因：计划阶段可以发现潜在问题，减少返工。

---

## 🚫 反模式（不要做这些）

| 反模式 | 为什么错 | 正确做法 |
|--------|---------|---------|
| 把 `ops/scripts/*` 当作第一入口 | 脚本不是正式 CLI，缺少验证和路由 | 使用 `agentplane ...` |
| Skill 直接拼 SSH / Docker / API 调用 | 跳过 CLI 等于跳过安全检查和日志记录 | Skill 只做路由和提示，执行走 CLI |
| 用 Runbook 代替正式控制面 | Runbook 是给人看的，不是给机器执行的 | Runbook 解释流程，CLI 执行操作 |
| 手写多层 `ssh ... bash -c "..."` | 容易出引号转义问题，且不可审计 | 使用 `infra remote bash` |
| 直接设置 `UV_PROJECT_ENVIRONMENT` 为 `.venv-win` | 破坏单环境约定 | 让 `uv` 自动使用 `.venv` |
| 在共享文档中硬编码 SSH 别名 | 环境特定信息会泄露或过时 | 从 `secrets/ssh/config` 读取 |
| 只更新文档、不更新 ledger 或 inventory | 台账与实际状态脱节 | 执行 → 验证 → 刷新 ledger → 同步文档 |
| 大批量变更一次性提交 | 无法 revert、bisect、cherry-pick 单个逻辑单元 | 按逻辑变更单元拆分提交 |
| Commit Message 无 type 前缀 | 无法按类型过滤（如只看 bug 修复） | 使用 Conventional Commits 格式 |
| Commit Message 描述"怎么做的" | diff 已经说明了 what，浪费信息位 | 描述"做了什么"和"为什么" |
| 格式调整混入功能变更 | 格式 diff 噪音掩盖实质变更，干扰 review | 格式调整独立提交（type=`style`） |
| `git push --force` 到 main | 不可逆，会覆盖他人工作 | 永远不要 force push 到 main |

---

## 📚 文档索引

按用途分类的文档速查：

### 入门必读
- [README.md](README.md) — 仓库入口、快速开始
- [docs/runbooks/current-state-and-validation.md](docs/runbooks/current-state-and-validation.md) — 当前状态总览 ⭐ **最新**

### 架构设计（长期规范）
- [docs/architecture/control-plane.md](docs/architecture/control-plane.md) — 控制面核心架构
- [docs/architecture/linux-governance.md](docs/architecture/linux-governance.md) — Linux 治理规范
- [docs/architecture/agentplane-app-collaboration.md](docs/architecture/agentplane-app-collaboration.md) — AgentPlane 与应用仓库协作规范

### 操作手册（日常指南）
- [docs/runbooks/bootstrap-secrets.md](docs/runbooks/bootstrap-secrets.md) — Secrets 初始化
- [docs/runbooks/wsl-host-governance.md](docs/runbooks/wsl-host-governance.md) — WSL 环境管理
- [docs/runbooks/app-project-delivery-workflow.md](docs/runbooks/app-project-delivery-workflow.md) — 应用交付流程
- [docs/runbooks/live-integration-gate.md](docs/runbooks/live-integration-gate.md) — 现场集成验证

### 参考文档（查阅用）
- [docs/reference/app-repository-standard.md](docs/reference/app-repository-standard.md) — 应用仓库标准
- [docs/reference/testing-architecture.md](docs/reference/testing-architecture.md) — 测试架构
- [docs/reference/control-plane-naming-registry.md](docs/reference/control-plane-naming-registry.md) — 命名规范
- [docs/reference/compat-retirement-ledger.md](docs/reference/compat-retirement-ledger.md) — 兼容退役记录
- [docs/reference/open-source-readiness.md](docs/reference/open-source-readiness.md) — 开源就绪检查

### 维护者文档
- [docs/maintainers/control-plane-authoring.md](docs/maintainers/control-plane-authoring.md) — 编写规范

---

## 🗺️ 仓库目录速查

| 目录 | 用途 | 是否提交 Git |
|------|------|-------------|
| `README.md` | 仓库入口、导航 | ✅ |
| `docs/architecture/` | 架构设计合同 | ✅ |
| `docs/runbooks/` | 活跃操作手册 | ✅ |
| `docs/reference/` | 参考文档（标准、命名、兼容性） | ✅ |
| `docs/maintainers/` | 维护者专用规范 | ✅ |
| `infra/compose/` | Docker Compose 资产 | ✅ |
| `inventory/` | 非敏感状态台账 | ✅ |
| `agentplane/` | Python CLI 与自动化代码 | ✅ |
| `templates/` | 非敏感模板 | ✅ |
| `.codex/` | Codex skill 与环境动作 | ✅ |
| `secrets/` | 本地真实 Secrets | ❌ |
| `tests/` | 自动化测试 | ✅ |

---

> 💡 **提示**：子目录下的 `AGENTS.md` 文件会覆盖本文件的规则。如果当前工作目录附近有 `AGENTS.md`，优先遵守那个文件的规则。
