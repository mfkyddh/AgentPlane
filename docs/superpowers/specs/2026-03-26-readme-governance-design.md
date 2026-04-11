# README Governance Design

## Goal

把仓库根 `README.md` 收口成稳定、短小的总入口：先说明 `OP_Linux` 的治理边界，再给出最小上手命令、隔离工作区协作原则，以及指向 `docs/` 的权威索引。

## Scope

- 重写根 `README.md` 的结构与文案。
- 增加“新工作区协作”最小原则说明。
- 把详细治理规则、runbook 和应用协作规范以下钻链接方式暴露。

## Non-Goals

- 不改动任何自动化逻辑、CLI 行为或测试。
- 不把 runbook 细节重新搬回 `README.md`。
- 不新增新的治理文档，只整理现有文档入口。

## Design

### Repository Positioning

README 顶部先明确 `OP_Linux` 是 Linux/WSL 主机与服务治理仓库，也是正式控制面的真源；它不是业务应用仓库。这样新读者在第一屏就能建立正确边界，避免把业务交付、生产 secrets 和基础设施治理混在一起。

### Thin Entry, Deep Docs

README 只保留最小稳定信息：

- 仓库定位
- 30 秒上手
- 日常统一入口
- 新工作区协作原则
- 文档索引
- 精简目录导航

所有操作性细节继续留在 `docs/architecture/*.md` 与 `docs/runbooks/*.md`。README 负责导航，不负责承载专题步骤。

### New Workspace Collaboration

新增一个简短区块说明在仓库内协作时的默认做法：

- 优先使用隔离 `git worktree`
- 变更前先确认执行身份、仓库根和基线命令
- 日常入口统一通过 `uv run python -m ops.cli ...`
- 运行态判断以 live state 为准，文档用于解释，不替代现场核实

这里不展开完整流程，只给出足够稳定的原则，并链接到 WSL 治理与仓库布局文档。

### Document Index

文档索引按用途分组，而不是简单堆链接：

- 架构与治理
- Runbook 与操作手册
- 应用仓库协作
- 模板与本地私有文件

这样可以让读者按任务类型快速下钻，而不是先猜文件名。

## Verification

- 检查 `README.md` 中引用的本地路径全部存在。
- 人工确认 README 一级段落控制在总览层，没有把专题步骤重新抄回根文档。
- `git diff -- README.md` 只体现文档治理改动。
