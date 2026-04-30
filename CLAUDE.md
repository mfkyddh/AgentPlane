# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

AgentPlane 是一个 Agent-first 控制面 CLI 工具。所有正式操作通过 `agentplane <domain> <surface> <verb> [flags]` 进入，提供 plan → execute → verify → record 生命周期。`.agents/skills/` 中定义的 Skill 是 AI 入口，它们路由到 CLI 命令——永远不要绕过 CLI。

## 常用命令

```bash
# 安装（二选一）
uv tool install -e .                 # 全局安装
uv run agentplane ...                # 无需全局安装

# 测试
uv run python -m pytest                            # 默认离线测试
uv run python -m pytest -m unit                    # 仅单元测试
uv run python -m pytest -m "unit or integration"   # 单元 + 集成
uv run python -m agentplane.cli test fast --tb=short  # 快速测试（CI 使用）

# Lint / 格式化
uv run ruff check .
uv run ruff format .
pre-commit run --all-files

# 健康检查 / 发布检查
agentplane repo health-check --repo-root .
agentplane repo release-check --repo-root .

# CLI 帮助
agentplane --help
agentplane <domain> --help
```

## 架构

**入口**: `agentplane/cli/app.py` → `main()`（也可 `python -m agentplane`）。

**包层次**:
- `agentplane/cli/` — argparse 命令处理器。每个领域一个模块（`bootstrap.py`、`infra.py`、`service.py`、`ingress.py`、`apps.py`、`projection.py`、`repository.py`）。
- `agentplane/domain/` — 业务逻辑（领域驱动）。每个领域（`app/`、`infra/`、`ingress/`、`service/`、`repository/`）包含 models、handlers、lifecycle、registry。
- `agentplane/runtime/` — 跨平台执行层。后端通过 `runtime/backends/registry.py` 中的 `@register_backend("type")` 装饰器自注册。支持：linux_native、windows_wsl、ssh_linux、macos_lima。
- `agentplane/providers/` — 外部服务集成（1Panel、Cloudflare）。
- `agentplane/adapters/` — 服务协议适配器（docker_runtime、systemd_runtime）。
- `agentplane/scripts/` — 内部执行资产（不是一级入口）。

**关键模式**:
- **后端注册表**: `@register_backend("type")` 装饰器自注册执行后端。
- **投影模型**: Host Inventory（非敏感台账）→ Object Ledgers（机器派生证据）→ App Summaries（人类可读摘要）。
- **路径策略**: 只跟踪逻辑路径（`apps/<app>`）。物理路径（Windows 盘符、WSL UNC、`/mnt/...`）仅出现在运行时解析或验证证据中。
- **Skill 路由**: `.agents/skills/` 定义映射到 CLI 命令的能力。Skill 永不直接执行。

**目标环境**: `wsl`（本地开发）、`prod0-main`（生产服务器）。

## 约定

- **Python 3.12+**，唯一运行时依赖是 `PyYAML>=6.0`。
- **包管理器**: `uv`。根目录单个 `.venv`——不创建平台变种 venv。
- **Ruff**: line-length=120, rules E4/E7/E9/F/I。
- **提交**: Conventional Commits 格式——`type(scope): description`。type 仅限 `feat|fix|refactor|docs|test|chore|style|perf`。**强制原子提交**：一个提交只包含一个逻辑变更单元，能用一句话说清"这次提交做了什么"；超过 15 个文件必须评估拆分。详见 `docs/reference/git-conventions.md`。
- **测试**: 新测试必须标记 `unit`/`integration`/`e2e`。默认运行排除 `live_gate`、`integration_wsl`、`integration_remote`、`external_app`、`docker_required`、`ssh_required`。
- **Secrets**: 真实 secrets 仅放 `secrets/`（已 gitignore）。非敏感模板放 `templates/`。
- **Windows**: 用 `pwsh`，不用 `cmd`。Linux 操作用 `wsl.exe -e <program>`。远程 Linux 用 `agentplane infra remote bash`。
- **跨平台源码**: Windows 和 WSL 共用一个 checkout 和一个 `.venv`。

## 编码行为准则

基于 [Karpathy Guidelines](https://x.com/karpathy/status/2015883857489522876)，减少常见 LLM 编码错误：

1. **先思考再编码** — 明确假设，不确定就问；有多种解释时都列出来，不要默默选择
2. **简洁优先** — 最少代码解决问题；不加未要求的功能、抽象、配置项；200 行能 50 行搞定就重写
3. **精准改动** — 只改必须改的；不顺手"改进"相邻代码；匹配现有风格；只清理自己制造的无用代码
4. **目标驱动** — 定义可验证的成功标准；多步任务写出计划并逐步验证

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

优先原则：先用 `实事求是` 约束判断，再在明确适用时调用下游 skill。不要为了形式而调用，但也不要错过能显著改善判断的场景。

## 其他哲学原则使用指南

以下原则不需要显式调用 skill，但需要在对应场景中主动应用：

### 哲学基座

| 原则 | 应用场景 | 检查点 |
|------|----------|--------|
| **第一性原理** | 架构设计、技术选型、问题分析 | 是否从最基本的事实出发，而不是类比？ |
| **奥卡姆剃刀** | 设计决策、功能规划 | 是否简化到必要程度？如无必要，勿增实体 |

### 方法论

| 原则 | 应用场景 | 检查点 |
|------|----------|--------|
| **费曼学习法** | 文档编写、知识传递、解释概念 | 是否用简单语言解释复杂概念？ |
| **苏格拉底式提问** | 需求分析、决策讨论、引导思考 | 是否通过提问引导思考，而非直接给答案？ |

### 软件工程原则

| 原则 | 应用场景 | 检查点 |
|------|----------|--------|
| **YAGNI** | 功能设计、架构设计 | 是否只实现当前需要的功能，不过度设计？ |
| **DRY** | 代码编写、重构 | 是否消除了重复代码，提取了公共逻辑？ |
| **KISS** | 设计、实现 | 是否保持了简单，避免了不必要的复杂？ |
| **SOLID** | 架构设计、代码编写 | 是否遵循了单一职责、开闭原则等？ |

使用方式：在对应场景中主动检查，无需显式调用。

## 反模式

- 不要把 `scripts/` 当一级入口——用 `agentplane ...`。
- 不要手写多层 `ssh ... bash -c`——用 `infra remote bash`。
- 不要在一次提交中混入格式调整和功能变更。
- 不要创建平台变种 venv（`.venv-win`、`.venv-wsl`）。

## 文档

活跃文档需要 YAML frontmatter（`status`、`owner`、`last_verified`、`audience`）且必须被索引链接。关键文档：
- `docs/architecture/control-plane.md` — 核心架构契约
- `docs/reference/repository-structure.md` — 目录契约
- `docs/reference/git-conventions.md` — Git 规则
- `docs/reference/cross-platform.md` — 跨平台规则
- `docs/reference/testing-architecture.md` — 测试分层

## 四层文档体系

AgentPlane 采用四层文档体系，详见 `docs/reference/documentation-layers.md`：

1. **战略层** (`docs/strategy/`) — 愿景、原则、路线图、决策记录。回答：去哪里？为什么？
2. **项目层** (`docs/project/`) — 项目章程、角色、沟通、风险。回答：做什么？谁来做？何时做？
3. **工程层** (`docs/reference/`) — 代码风格、Git 规范、测试、发布。回答：如何做？如何保证质量？
4. **技术层** (`docs/architecture/`, `docs/runbooks/`) — 架构、规范、运维。回答：具体怎么做？如何维护？

新增文档时，先确定属于哪一层，再放入对应目录。
