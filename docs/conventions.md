---
status: active
owner: AgentPlane maintainers
last_verified: 2026-05-07
audience: both
---

# 编码与协作规范

> 结论：本文是 AgentPlane 所有参与者（人类和 AI）的行为准则。AGENTS.md 和 CLAUDE.md 引用本文，不重复维护。

---

## 编码行为准则

基于 [Karpathy Guidelines](https://x.com/karpathy/status/2015883857489522876)，减少常见 LLM 编码错误。

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

## 技术栈基线

| 层面 | 标准选择 | 说明 |
|---|---|---|
| 语言 | Python `3.12+` | 与 `pyproject.toml` 保持一致 |
| 包管理 | `uv` | 依赖、虚拟环境、测试命令统一走 `uv` |
| CLI | Python 标准库 `argparse` + `agentplane.cli` | 轻依赖，不引入第二套 CLI 框架 |
| 测试 | `pytest` | 默认门禁必须离线、确定性 |
| lint | `ruff` | 覆盖导入排序、未使用导入和明显运行错误 |
| 文档 | Markdown | reference 放规则，runbook 放操作 |
| 容器 | Docker Compose v2：`docker compose` | 不使用旧式 `docker-compose` |
| 正式执行 | `agentplane ...` | 所有正式操作从统一 CLI 进入 |

---

## 依赖管理

新增依赖前先回答：

1. 是否能用标准库或已有项目依赖解决
2. 是否会影响跨平台默认门禁
3. 是否会把 live 环境要求带进默认测试
4. 是否需要 secrets、网络、Docker 或 SSH
5. 是否有清晰的维护者、许可证和替代方案

生产依赖写进 `[project.dependencies]`；只服务开发、测试、格式化的依赖写进 `[dependency-groups].dev`。

---

## 跨平台约束

### Windows 宿主

| 规则 | 级别 | 原因 |
|---|---|---|
| 默认入口 Shell 使用 `pwsh` | 🔴 | `cmd` 语法差异大，易出错 |
| `git`、`uv`、`pnpm`、测试等直接在 `pwsh` 中运行 | 🟡 | 减少 Shell 切换开销 |
| 需要 Linux 能力时，优先用 `wsl.exe -e <程序> <参数>` | 🟡 | 直接调用 WSL 程序 |

### WSL 后端

| 规则 | 级别 | 原因 |
|---|---|---|
| Windows 和 WSL **共用同一份源码 checkout** | 🔴 | 避免两份代码不同步 |
| 不要仅为运行 WSL 操作而 clone 第二份仓库 | 🔴 | 会造成配置分叉 |
| 避免两个 Shell 同时执行包管理器写入 | 🟡 | 防止 `.venv` 损坏 |

### Linux / macOS

- 直接使用本地 POSIX Shell 执行本地命令
- 远程 Linux 操作走：`pwsh → agentplane.cli → WSL/SSH backend`

### Shell 选择决策

```
需要执行命令
  ├── Windows 原生命令 → pwsh
  ├── 需要 Linux 环境 → wsl.exe -e <程序> <参数>
  │   └── 需要管道/重定向 → wsl.exe bash -lc "cmd1 | cmd2 > out"
  └── 远程 Linux → agentplane infra remote bash
```

---

## 虚拟环境

| 规则 | 级别 | 原因 |
|---|---|---|
| Python 项目统一使用 `uv` | 🟡 | 速度快、行为一致 |
| 每个物理 checkout **只保留一个 `.venv`** | 🔴 | 禁止创建平台变种 |
| **不要**设置 `UV_PROJECT_ENVIRONMENT` 为平台相关路径 | 🔴 | 让 `uv` 自动使用根目录 `.venv` |
| Node.js 项目统一使用 `pnpm` | 🟡 | 速度快、磁盘省 |

双环境（`.venv-win` + `.venv-wsl`）会导致依赖版本不同步、`uv.lock` 与实际安装的包不一致。正确做法：`uv` 在 WSL 侧通过 `/mnt/` 访问同一个 `.venv`。

---

## CLI 可用性

| 优先级 | 方式 | 条件 |
|--------|------|------|
| 1 | `agentplane ...` | `uv tool install -e .` 已执行 |
| 2 | `uv run agentplane ...` | 仓库内，`uv` 可用 |
| 3 | `python -m agentplane ...` | `.venv` 已激活 |

---

## 容器规范

### Docker Compose

| 规则 | 级别 | 原因 |
|---|---|---|
| 运行时命令统一使用 `docker compose`（空格） | 🔴 | 旧版已弃用 |
| 服务资产放在 `infra/compose/<service>/` | 🟡 | 统一存放 |
| 本地 Secrets 放在 `secrets/services/` | 🟡 | 与 compose 分离 |

### 容器命名

| 规则 | 级别 | 原因 |
|---|---|---|
| 测试环境容器名以 `-dev` 结尾 | 🔴 | 防止误删生产 |
| 生产环境容器名以 `-prod` 结尾 | 🔴 | 同上 |

格式：`<服务名>-<环境>`，例如 `sub2api-prod`、`postgres-dev`。

### 网络与数据

- 生产容器接入 `zqf_network`
- 持久化数据放在 `/data/<service>/...`
- Docker 运行根目录收口到 `/data/docker`

### Docker 应用打包

采用"宿主机构建 + runtime-only Dockerfile"模式：

1. 在 WSL 宿主机完成构建，产物放到 `dist/oplinux/`
2. Runtime-only Dockerfile 只复制产物，不重新编译
3. 正式交付链路：`build-artifact → ship-image → render-runtime → deploy/verify`

---

## Node 与前端

本仓库不是前端应用仓库，默认不引入 Node 工具链。

如果接入的应用仓库需要 Node：
- 包管理使用 `pnpm`
- 构建、测试留在应用仓库
- 正式部署、验证仍由 AgentPlane 控制面发起

---

## 引入新技术

当一个文件或测试辅助明显过大时，不做一次性大爆炸重构：

1. 先补 characterization test，锁住当前行为
2. 每次业务改动只顺手抽出一个清晰职责
3. 拆分后保持旧入口兼容，直到调用点迁完再退役

---

## 求是 Skills 使用原则

**强制规范**：回答问题时，必须首先声明使用了哪些 skills。格式：

```
**Skills**: [skill-name-1], [skill-name-2], ...
```

或在没有使用任何 skill 时明确说明：

```
**Skills**: 无
```

---

在以下场景必须主动调用对应的 qiushi-skill：

| 场景 | 调用的 Skill | 触发信号 |
|------|-------------|---------|
| 做重大判断或决策前 | `qiushi-skill:investigation-first` | 信息不足、需要先摸清现状 |
| 面对复杂问题不知从何入手 | `qiushi-skill:contradiction-analysis` | 多个因素冲突、主次不清 |
| 完成阶段性工作后 | `qiushi-skill:criticism-self-criticism` | 阶段验收、需要审查质量 |
| 面对长期复杂任务 | `qiushi-skill:protracted-strategy` | 无法速胜、需要分阶段推进 |
| 多个任务争夺注意力 | `qiushi-skill:concentrate-forces` | 优先级过多、资源紧张 |
| 需要收集多方意见 | `qiushi-skill:mass-line` | 需要整合多源信息 |
| 从零起步、资源有限 | `qiushi-skill:spark-prairie-fire` | bootstrap、MVP、小团队起步 |
| 多个目标需要平衡 | `qiushi-skill:overall-planning` | trade-offs、目标冲突 |
| 提出方案需要验证 | `qiushi-skill:practice-cognition` | experiment、prototype、validate |

优先原则：先用 `实事求是` 约束判断，再在明确适用时调用下游 skill。

**原则驱动决策**：做架构、设计、原则相关判断时，必须参考 [principles.md](core/principles.md) 的道法术体系。具体来说：
- **道层**：判断是否实事求是、是否抓住了主要矛盾
- **法层**：判断是否做了调查研究、是否集中兵力、是否符合奥卡姆剃刀
- **术层**：判断是否符合 CLI-first、Agent-first、证据优先、YAGNI、DRY、KISS

---

## 哲学原则

不需要显式调用 skill，但在对应场景中主动应用：

- **奥卡姆剃刀** — 如无必要，勿增实体（法层）
- **费曼学习法** — 用简单语言解释复杂概念（术层：KISS 的应用）
- **苏格拉底式提问** — 通过提问引导思考，而非直接给答案（法层：调查研究的应用）
- **YAGNI** — 只实现当前需要的功能（术层）
- **DRY** — 消除重复代码（术层）
- **KISS** — 保持简单（术层）

> 原则的完整体系见 [principles.md](core/principles.md)（道法术三层）。

---

## 文档编写规范

> 以下 11 条原则是编写项目文档的强制性规范。从 architecture.md 重写过程中提炼，经实践验证有效。

### 结构原则

| 原则 | 要求 | 验收标准 |
|------|------|---------|
| **主线明确** | 用一条清晰的主线组织全文，章节间有逻辑递进关系 | 读者能说出"这份文档在讲什么" |
| **渐进式复杂度** | 从简单到复杂：是什么 → 怎么工作 → 边界和约束 | 前文为后文建立心智模型 |
| **先结论后展开** | 每个章节开头用一句话给出结论，再详细阐述 | 忙碌的读者只看结论也能理解核心 |
| **单一职责** | 一份文档只解决一个问题；跨主题内容引用其他文档 | 架构不涉及技术选型，技术选型不涉及架构 |

### 表达原则

| 原则 | 要求 | 验收标准 |
|------|------|---------|
| **术语先行** | 首次使用专业术语前，必须先解释其含义 | 新读者不会因术语卡住 |
| **回答"为什么"** | 每个设计决策都附带动机说明 | 读者理解为什么这样做，而不只是知道怎么做 |
| **具体示例** | 抽象概念必须配具体示例（CLI 命令、代码片段、场景描述） | 读者看完能立即上手 |
| **面向读者** | 内容深度和表达方式根据目标读者调整 | 不同角色看到不同的重点 |

### 治理原则

| 原则 | 要求 | 验收标准 |
|------|------|---------|
| **不重复维护** | 引用其他文档，不复制粘贴；唯一真源在原文件 | 改一处即生效，不需要同步多处 |
| **关联显式化** | 当本文档的概念与其他文档存在展开、映射或视角关系时，必须显式说明这种关系 | 读者不需要自己推理"这个概念对应那个文档的什么" |
| **Frontmatter 元数据** | 每份文档必须有：status、owner、last_verified、audience | 可以快速判断文档是否过时、谁负责、给谁看 |
| **可验证性** | 文档中的声明应该是可验证的 | "所有操作必须从 CLI 进入"是可验证的，"系统应该好用"不是 |

**关联显式化的三种情况**：

| 关系类型 | 含义 | 示例 |
|----------|------|------|
| **向上引用** | 本文档的概念是另一个文档的展开 | architecture.md 的域是 vision.md 项目模型的管理能力展开 |
| **向下映射** | 本文档的概念对应另一个文档的实体 | roadmap.md 的里程碑对应 principles.md 的原则 |
| **横向关联** | 两个文档的概念是同一事物的不同视角 | architecture.md 的执行闭环和 principles.md 的"执行闭环"原则 |

---

## 反模式

| 错误做法 | 正确做法 |
|----------|----------|
| `scripts/` 当入口 | `agentplane ...` |
| Skill 拼 SSH/Docker | 走 CLI |
| 多层 `ssh bash -c` | `infra remote bash` |
| 大批量单提交 | 按逻辑拆分 |
| 格式混功能 | 独立提交 |
| 平台变种 venv | 只用根 `.venv` |

---

## 协作协议

**人类表达意图，AI 自主推进，所有工作回归主线。**

- **会话开始**：读取 `PROGRESS.md`，确认主线进度，向人类报告当前位置
- **收到需求**：判断归属
  - 直接服务主线（当前阶段目标）→ 合入主线，立即执行
  - 间接相关 → 创建分支任务，完成后回归主线
  - 完全无关 → 记录到 backlog，询问是否现在做
- **会话结束**：更新 `PROGRESS.md`，标记完成项，记录进度

---

## 关联文档

- [AGENTS.md](../AGENTS.md) — AI 工作规范（引用本文）
- [CLAUDE.md](../CLAUDE.md) — Claude 特有指令（引用本文）
- [愿景](core/vision.md) — 项目定位与约束
- [原则](core/principles.md) — 道法术三层原则体系
- [架构](core/architecture.md) — 技术架构
- [术语表](glossary.md) — 术语定义
