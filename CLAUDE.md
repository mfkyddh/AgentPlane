# CLAUDE.md

> 本文档是 Claude Code 专属指令。通用 AI 规则见 [AGENTS.md](AGENTS.md)。
> 本文档只包含 Claude 特有的协作协议、方法论集成和架构补充。

## 协作协议

**人类表达意图，AI 自主推进，所有工作回归主线。**

**会话开始**：读取 `docs/project/backlog.md`，确认主线进度，向人类报告当前位置。

**需求处理**：收到任何需求后，先判断归属：
- 直接服务主线（当前阶段目标）→ 合入主线，立即执行
- 间接相关 → 创建分支任务，完成后回归主线
- 完全无关 → 记录到 backlog，询问是否现在做

**会话结束**：更新 `docs/project/backlog.md`，标记完成项，记录进度。

**主线**：当前阶段的唯一目标是完成三件事（见 backlog.md）。所有工作都应围绕主线推进。

## 架构概要

**包层次**:
- `agentplane/cli/` — argparse 命令处理器（每个领域一个模块）
- `agentplane/domain/` — 业务逻辑（领域驱动，含 models/handlers/lifecycle/registry）
- `agentplane/runtime/` — 跨平台执行层（`@register_backend("type")` 自注册）
- `agentplane/providers/` — 外部服务集成（1Panel、Cloudflare）
- `agentplane/adapters/` — 服务协议适配器（docker_runtime、systemd_runtime）
- `agentplane/scripts/` — 内部执行资产（不是一级入口）

**关键模式**:
- **后端注册表**: `@register_backend("type")` 装饰器自注册执行后端
- **投影模型**: Host Inventory → Object Ledgers → App Summaries
- **路径策略**: 只跟踪逻辑路径；物理路径仅出现在运行时解析中
- **Skill 路由**: `.agents/skills/` 定义映射到 CLI 命令的能力，Skill 永不直接执行

**目标环境**: `wsl`（本地开发）、`prod0-main`（生产服务器）

## 约定补充

- **Python 3.12+**，唯一运行时依赖是 `PyYAML>=6.0`
- **包管理器**: `uv`。根目录单个 `.venv`
- **Ruff**: line-length=120, rules E4/E7/E9/F/I
- **测试**: 新测试必须标记 `unit`/`integration`/`e2e`。默认排除 `live_gate`、`integration_wsl` 等
- **跨平台源码**: Windows 和 WSL 共用一个 checkout 和一个 `.venv`

## 文档约定

两层原则：`docs/` 给人看，`AGENTS.md` 给 AI 看。活跃文档需要 YAML frontmatter（`status`、`owner`、`last_verified`、`audience`）且必须被索引链接。

## 求是 Skills 使用原则

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

## 其他哲学原则

以下不需要显式调用 skill，但在对应场景中主动应用：

- **第一性原理** — 架构设计时从基本事实出发
- **奥卡姆剃刀** — 如无必要，勿增实体
- **费曼学习法** — 用简单语言解释复杂概念
- **苏格拉底式提问** — 通过提问引导思考，而非直接给答案
- **YAGNI** — 只实现当前需要的功能
- **DRY** — 消除重复代码
- **KISS** — 保持简单
- **SOLID** — 遵循职责单一、开闭原则等

## GStack

使用 `/browse` skill 进行所有网页浏览，**不要使用** `mcp__claude-in-chrome__*` 工具。

可用 skills：

| Skill | 用途 |
|-------|------|
| `/browse` | 网页浏览和测试 |
| `/office-hours` | 办公时间 |
| `/plan-ceo-review` | CEO 审查计划 |
| `/plan-eng-review` | 工程审查计划 |
| `/plan-design-review` | 设计审查计划 |
| `/design-consultation` | 设计咨询 |
| `/design-shotgun` | 设计快速迭代 |
| `/design-html` | HTML 设计 |
| `/review` | 代码审查 |
| `/ship` | 发布 |
| `/land-and-deploy` | 部署 |
| `/canary` | 金丝雀发布 |
| `/benchmark` | 基准测试 |
| `/connect-chrome` | 连接 Chrome |
| `/qa` | 质量保证 |
| `/qa-only` | 仅 QA |
| `/design-review` | 设计审查 |
| `/setup-browser-cookies` | 浏览器 Cookie 设置 |
| `/setup-deploy` | 部署设置 |
| `/setup-gbrain` | GBrain 设置 |
| `/retro` | 回顾 |
| `/investigate` | 调查 |
| `/document-release` | 文档发布 |
| `/codex` | Codex |
| `/cso` | CSO |
| `/autoplan` | 自动规划 |
| `/plan-devex-review` | DevEx 审查计划 |
| `/devex-review` | DevEx 审查 |
| `/careful` | 谨慎模式 |
| `/freeze` | 冻结 |
| `/guard` | 守护 |
| `/unfreeze` | 解冻 |
| `/gstack-upgrade` | GStack 升级 |
| `/learn` | 学习 |

## 关键文档

| 文档 | 用途 |
|------|------|
| `docs/architecture/control-plane.md` | 控制面核心契约 |
| `docs/reference/repository-structure.md` | 目录契约 |
| `docs/reference/git-conventions.md` | Git 规则 |
| `docs/reference/cross-platform.md` | 跨平台规则 |
| `docs/reference/testing-architecture.md` | 测试分层 |
