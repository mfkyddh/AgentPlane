---
status: active
owner: AgentPlane maintainers
last_verified: 2026-04-29
superseded_by: null
audience: both
---

# AgentPlane 终极蓝图 v4

结论：本文是 AgentPlane 的长期战略蓝图。它回答“AgentPlane 要成为怎样的工程控制面、按什么阶段演进、哪些机制必须长期存在”；正式执行合同仍以 [control-plane.md](../architecture/control-plane.md) 和 `agentplane ...` 为准。

## 🎯 总体定位

AgentPlane 是小团队的 Agent-first 工程控制平面：人类制定方向、边界和审批口径，Agent 通过 Skill 理解意图并路由到正式 CLI，所有重要动作通过计划、执行、验证、证据和回写进入可追踪航道。

更短的表达：

> 人类定方向，Skill 做路由，CLI 做执行，项目入航道。

AgentPlane 不追求成为大型 DevOps 平台、通用 Agent 框架或托管 SaaS。它优先服务个人开发者、小团队、开源维护者和自托管服务维护者，让少量项目和主机在 AI 参与后仍然保持清晰、可验证、可回滚、可审计。

当前仓库已经不是从零自举状态。仓库治理、文档治理、Skill catalog、离线测试、secrets 边界和 `repo status` 已经可用；后续重点是把战略、任务状态、操作凭证、项目注册、可视化和多阶段协作逐步机制化。

## 🧭 真源关系

| 主题 | 真源 | 说明 |
| --- | --- | --- |
| 长期战略和阶段方向 | 本文 | 说明 AgentPlane 为什么演进、往哪里演进 |
| 阶段推进和任务状态 | [agentplane-roadmap-workbook.md](../maintainers/agentplane-roadmap-workbook.md) | 下次“继续执行”时先看这里 |
| 正式执行合同 | [control-plane.md](../architecture/control-plane.md) | 定义 CLI、task-entry、输出、错误和投影合同 |
| Agent 执行纪律 | [AGENTS.md](../../AGENTS.md) | 每次 AI 执行必须遵守的短规则 |
| Skill 暴露面 | [.agents/skills/catalog.yaml](../../.agents/skills/catalog.yaml) | Agent 可触发能力的公开 catalog |
| 仓库健康状态 | `agentplane repo status --repo-root .` | 只读汇总文档、Skill、catalog 和 inventory 摘要 |

核心规则：

1. 蓝图不替代控制面合同。
2. 工作计划不替代真实验证。
3. Skill 不替代 CLI 实现。
4. README 和 runbook 不替代 inventory / ledger 真源。

## 📌 核心原则

### 1. Skill 路由，CLI 执行

Skill 是 Agent 理解人类意图的入口，负责触发、路由、边界提示和验证提醒；正式动作必须回到 `agentplane ...`。

正确链路是：

```text
人类意图 -> Skill 路由 -> agentplane CLI -> verify -> ledger -> inventory/doc-sync -> 人类摘要
```

### 2. 人类阶段门

长期计划不能靠 Agent 自动一路推进。每个阶段开始前必须先和人类讨论三件事：

1. 具体实施方向
2. 技术采用
3. 概念边界

只有这三项被确认后，才能把阶段拆成具体任务和技术细节。

### 3. 证据优先

没有证据的正式操作，不算完成。证据要分层，避免把人类淹没在日志里：

| 层级 | 作用 |
| --- | --- |
| 原始输出 | 排查和还原过程 |
| Operation Receipt | 每次正式任务的结构化摘要 |
| 异常复盘 | 失败、绕过、回滚、审批拒绝后的学习材料 |
| 趋势报告 | 帮助人类判断哪些能力应该改进 |

### 4. 渐进控制

项目不必一次性完全进入 AgentPlane。建议长期保留接入等级：

| 等级 | 含义 |
| --- | --- |
| Level 0 | 未接入，只能人工说明 |
| Level 1 | 登记接入，进入项目注册表 |
| Level 2 | 规范检查接入，可被 AgentPlane 检查 |
| Level 3 | 部署运维接入，正式运维走 AgentPlane |
| Level 4 | 完整生命周期接入，创建、开发、交付、运维、复盘都受管 |

### 5. 受控例外

紧急情况允许临时绕过部分流程，但必须记录原因、动作、影响、恢复情况、补交凭证截止时间和复盘结果。重复出现的例外必须沉淀为正式 Skill、规范或 runbook。

### 6. 可视化服务决策

可视化不是为了好看，而是帮助人类快速回答：

1. 当前有哪些项目和 target？
2. 哪些阶段正在推进？
3. 哪些任务卡住了？
4. 哪些 Skill 或规范经常失败？
5. 哪些对象的 ledger 或 inventory 已经过期？

### 7. Dogfooding

AgentPlane 必须首先管理自己。任何对外声称可复用的能力，优先在 AgentPlane 仓库自己的文档、Skill、测试、状态面板和任务书中跑通。

## 🧩 长期机制

### 阶段工作计划

阶段工作计划是长期推进的状态真源。每个阶段只在开始前细化，避免过早把远期计划写成假确定性。

任务完成后必须回写：

1. 状态
2. 完成日期
3. 验证命令或证据
4. 后续影响

### Operation Receipt

Operation Receipt 是每次正式任务的人类可读摘要。早期可以先用 Markdown，后续再引入 schema。

最小字段建议：

| 字段 | 含义 |
| --- | --- |
| `operation_id` | 稳定编号 |
| `goal` | 人类目标 |
| `skill` | 使用或触发的 Skill |
| `commands` | 正式命令摘要 |
| `verification` | 验证结果 |
| `artifacts` | ledger、inventory、文档或报告引用 |
| `follow_up` | 后续任务 |

### Exception Review

异常复盘记录失败、紧急绕过、回滚和审批拒绝。它的目标不是追责，而是把问题转化为更好的 Skill、规范、测试或证据。

### Project Registry

项目注册表是比 app catalog 更上层的项目视图。它可以覆盖 AgentPlane 自身、应用仓库、文档站、服务组件和未来示范项目。`inventory/apps/catalog.json` 仍然是 app delivery 的正式 catalog，不直接承担全部项目治理语义。

### Blueprint

项目蓝图定义某类项目如何创建、验证、接入、部署和退役。早期只做少量低风险蓝图，优先服务示范闭环，而不是追求类型覆盖。

### Status Dashboard

`agentplane repo status` 是第一版控制面状态面板。后续可逐步增加阶段状态、任务状态、Operation Receipt、项目注册表和风险摘要。

## 🗺️ 阶段路线

| 阶段 | 名称 | 目标 |
| --- | --- | --- |
| P0 | 蓝图落库与任务机制建立 | 把 v4 蓝图、阶段工作计划和继续执行协议纳入 active docs |
| P1 | 任务书与“继续执行”闭环稳定 | 让 Agent 能根据任务书恢复上下文、定位下一步并回写状态 |
| P2 | 操作凭证、例外和复盘模型 | 建立 Operation Receipt、Exception Review 和最小证据规范 |
| P3 | 项目注册表与项目蓝图模型 | 区分 project registry、app catalog 和 blueprint，定义最小字段 |
| P4 | 应用生命周期示范闭环 | 选择低风险示范项目跑通接入、变更、验证、回写、退役口径 |
| P5 | 可视化控制面增强 | 将阶段、项目、任务、风险和证据接入 `repo status` 或静态面板 |
| P6 | 安全、并发与多 Agent 受控扩展 | 补充威胁模型、锁机制、阶段审批和多 Agent 协作边界 |

每个阶段正式开始前，都必须先在 [agentplane-roadmap-workbook.md](../maintainers/agentplane-roadmap-workbook.md) 记录人类确认。

## ✅ 成熟度判断

AgentPlane 从 alpha 走向 beta，不取决于 Skill 数量，而取决于这些闭环是否稳定：

1. 人类能用一句目标触发正确 Skill。
2. Agent 能找到当前阶段和下一项任务。
3. 正式动作能产生验证和证据。
4. 任务完成状态能回写到工作计划。
5. 异常能进入复盘并转化为长期资产。
6. 项目接入和退役都能走同一套生命周期口径。
7. 状态面板能帮助人类判断下一步，而不是只展示数据。

## 🔗 关联文档

- [Roadmap](../../ROADMAP.md)
- [阶段工作计划](../maintainers/agentplane-roadmap-workbook.md)
- [控制面合同](../architecture/control-plane.md)
- [Agent 执行闭环](../runbooks/control-plane-agent-execution-flow.md)
- [文档治理规范](documentation-governance.md)
- [项目定位](project-positioning.md)
- [威胁模型](threat-model.md)
