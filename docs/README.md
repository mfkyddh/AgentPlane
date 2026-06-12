# AgentPlane 文档

> AgentPlane 文档分三层：战略层（是什么、怎么想、往哪走、怎么建）、战术层（怎么上手、怎么操作、怎么协作、怎么治理）和执行层（当前在做什么、做过什么）。术语表和决策记录是公共索引。

---

## 快速导航

| 我想... | 去这里 |
|---------|--------|
| 快速上手 | [入门指南](getting-started.md) |
| 查命令 | [命令参考](command-reference.md) |
| 理解架构 | [架构](core/architecture.md) |
| 了解规则 | [编码与协作规范](conventions.md) |
| 查术语 | [术语表](glossary.md) |

---

## 战略层（项目根基）

回答：AgentPlane 是什么、怎么想、往哪走、怎么建。

- [愿景](core/vision.md) — 目标用户、解决什么问题、项目模型、核心价值
- [原则](core/principles.md) — 道法术三层原则体系
- [路线图](core/roadmap.md) — Alpha → Beta → GA 三阶段推进
- [架构](core/architecture.md) — 5 域模型、投影模型、CLI 接口、执行闭环

## 战术层（具体实现）

回答：怎么上手、怎么操作、怎么协作、怎么治理。

- [入门指南](getting-started.md) — 5 分钟跑起来
- [命令参考](command-reference.md) — 所有 CLI 命令
- [编码与协作规范](conventions.md) — 技术栈、编码规则、文档规范、协作协议
- [Maintainer 指南](maintainer-guide.md) — 治理资产约束、Skill 同步门禁

## 公共索引

- [术语表](glossary.md) — 唯一术语真源
- [决策记录](decisions/) — 关键决策追溯
- [Runbooks](runbooks/) — 操作手册和验证记录
- [Schemas](schemas/) — 数据格式和迁移文档

### 决策记录

- [011. 运行时拆分](decisions/011-runtime-split.md) — 核心逻辑与 Provider 解耦

### Runbooks

- [静态站点验证](runbooks/static-site-verification.md) — 静态站点部署验证流程

### Schemas

- [Contract 迁移](schemas/contract-migration.md) — contract.yaml v1→v2 迁移指南

## 执行层（当前进度）

回答：当前在做什么、做过什么。

- [主线追踪器](../PROGRESS.md) — 主线条件、进度、分支任务、人机协作实验
- [版本变更](../CHANGELOG.md) — 版本里程碑

---

## 归档文档

历史文档、旧 runbook、教程、WebUI 详细设计等已归档到 [archive/](archive/)。

---

## AI 入口

- [AGENTS.md](../AGENTS.md) — AI 工作规范
- [CLAUDE.md](../CLAUDE.md) — Claude 特有指令
