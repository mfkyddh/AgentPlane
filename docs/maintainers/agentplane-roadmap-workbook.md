---
status: active
owner: AgentPlane maintainers
last_verified: 2026-04-29
superseded_by: null
audience: agent
---

# AgentPlane Roadmap Workbook

结论：本文是 AgentPlane 长期路线图的阶段推进真源。下次人类引用本文并说“继续执行”时，Agent 必须先读取本文、[终极蓝图](../reference/agentplane-ultimate-blueprint.md) 和 [Roadmap](../../ROADMAP.md)，再定位当前阶段和下一项未完成任务。

## 🎯 用途

本文只记录长期阶段、状态、阶段门和任务推进，不替代：

| 不替代 | 真源 |
| --- | --- |
| 正式执行合同 | [control-plane.md](../architecture/control-plane.md) |
| Agent 短规则 | [AGENTS.md](../../AGENTS.md) |
| Skill catalog | [.agents/skills/catalog.yaml](../../.agents/skills/catalog.yaml) |
| 运行状态 | `inventory/`、`ledger`、`agentplane repo status` |

## 🧭 继续执行协议

当人类引用本文或蓝图并说“继续执行”时，Agent 必须按顺序执行：

1. 读取 [终极蓝图](../reference/agentplane-ultimate-blueprint.md)、本文和 [Roadmap](../../ROADMAP.md)。
2. 运行只读状态检查：`agentplane repo status --repo-root .`。
3. 找到第一个非 `done`、非 `superseded` 的阶段。
4. 如果该阶段状态是 `planned` 或 `discussion-required`，先和人类讨论实施方向、技术采用、概念边界。
5. 如果该阶段状态是 `approved` 或 `active`，找到第一个未完成任务并继续。
6. 每完成一个任务，回写任务状态、完成日期、验证命令或证据、后续影响。
7. 执行后运行最小验证；只改文档时至少运行 docs-sanity、skills check 和 repo status。
8. 验证通过后必须自动 commit、合入本地 `main`、推送 `origin main`；失败或暂停时必须说明原因。

禁止行为：

1. 不读取任务书就从记忆继续。
2. 阶段门未确认就拆细任务或执行实现。
3. 完成任务但不回写状态。
4. 只写“完成”，不记录验证证据。
5. 验证通过后留下未提交或未推送的 Git 可见变更。

## 📌 状态词表

阶段状态：

| 状态 | 含义 |
| --- | --- |
| `planned` | 已进入长期路线，但尚未讨论阶段门 |
| `discussion-required` | 下一步必须先和人类讨论 |
| `approved` | 阶段方向、技术采用、概念边界已确认，可拆任务 |
| `active` | 正在执行具体任务 |
| `blocked` | 等待外部信息或人工处理 |
| `done` | 阶段完成并通过验收 |
| `superseded` | 被新阶段或新方案替代 |

任务状态：

| 状态 | 含义 |
| --- | --- |
| `todo` | 待开始 |
| `in-progress` | 正在进行 |
| `blocked` | 暂停等待 |
| `done` | 已完成并记录证据 |
| `deferred` | 暂缓，不阻塞当前阶段 |

## 🗺️ 阶段总览

| 阶段 | 名称 | 状态 | 阶段门 | 验收口径 |
| --- | --- | --- | --- | --- |
| P0 | 蓝图落库与任务机制建立 | `done` | 已由人类确认：active 战略文档、Markdown 任务书、严格阶段门 | 蓝图、任务书、Roadmap、文档地图落库并通过最小验证 |
| P1 | 任务书与“继续执行”闭环稳定 | `discussion-required` | 待讨论实施方向、技术采用、概念边界 | Agent 能稳定恢复上下文、定位下一任务、回写状态 |
| P2 | 操作凭证、例外和复盘模型 | `planned` | 待讨论 | Operation Receipt 与 Exception Review 最小模型可用 |
| P3 | 项目注册表与项目蓝图模型 | `planned` | 待讨论 | project registry、app catalog、blueprint 边界清晰 |
| P4 | 应用生命周期示范闭环 | `planned` | 待讨论 | 低风险示范项目完成接入、变更、验证、回写、退役口径 |
| P5 | 可视化控制面增强 | `planned` | 待讨论 | repo status 或静态面板能展示阶段、任务、项目、风险 |
| P6 | 安全、并发与多 Agent 受控扩展 | `planned` | 待讨论 | 威胁模型、锁机制、审批边界和多 Agent 规则进入正式合同 |

## P0 蓝图落库与任务机制建立

### 阶段门

| 确认项 | 结论 |
| --- | --- |
| 具体实施方向 | 把 v3 草案重写为 active 战略蓝图，并接入 Roadmap |
| 技术采用 | 首轮只用 Markdown active docs，不新增 CLI、schema 或自动化 |
| 概念边界 | 蓝图是战略真源，任务书是推进真源，执行真源仍是 `agentplane ...` |

### 任务

| ID | 任务 | 状态 | 完成日期 | 验证或证据 | 后续影响 |
| --- | --- | --- | --- | --- | --- |
| P0-T1 | 新增终极蓝图 v4 active 文档 | `done` | 2026-04-29 | `docs/reference/agentplane-ultimate-blueprint.md` | 建立长期战略入口 |
| P0-T2 | 新增 Roadmap Workbook active 文档 | `done` | 2026-04-29 | `docs/maintainers/agentplane-roadmap-workbook.md` | 建立“继续执行”状态入口 |
| P0-T3 | 更新 Roadmap 和 docs 地图链接 | `done` | 2026-04-29 | `ROADMAP.md`、`docs/README.md` | 避免 active 文档孤立 |
| P0-T4 | 运行最小验证并回写本任务书 | `done` | 2026-04-29 | `repo docs-sanity`、`repo skills check`、`repo status` 均通过 | 下次从 P1 阶段门讨论开始 |

## P1 任务书与“继续执行”闭环稳定

### 阶段门

| 确认项 | 结论 |
| --- | --- |
| 具体实施方向 | 待和人类讨论 |
| 技术采用 | 待和人类讨论 |
| 概念边界 | 待和人类讨论 |

### 初始候选任务

| ID | 任务 | 状态 | 完成日期 | 验证或证据 | 后续影响 |
| --- | --- | --- | --- | --- | --- |
| P1-T1 | 设计“继续执行”时的固定检查清单 | `todo` |  |  | 让 Agent 恢复上下文更稳定 |
| P1-T2 | 决定任务书是否需要 repo status 投影 | `todo` |  |  | 决定是否进入自动化 |

## P2 操作凭证、例外和复盘模型

阶段开始前必须先讨论方向、技术采用和概念边界。

| ID | 候选任务 | 状态 |
| --- | --- | --- |
| P2-T1 | 定义 Operation Receipt 最小字段 | `todo` |
| P2-T2 | 定义 Exception Review 最小字段 | `todo` |

## P3 项目注册表与项目蓝图模型

阶段开始前必须先讨论方向、技术采用和概念边界。

| ID | 候选任务 | 状态 |
| --- | --- | --- |
| P3-T1 | 区分 project registry 与 app catalog | `todo` |
| P3-T2 | 定义第一个低风险项目蓝图候选 | `todo` |

## P4 应用生命周期示范闭环

阶段开始前必须先讨论方向、技术采用和概念边界。

| ID | 候选任务 | 状态 |
| --- | --- | --- |
| P4-T1 | 选择示范项目和目标环境 | `todo` |
| P4-T2 | 跑通接入、验证、回写、退役口径 | `todo` |

## P5 可视化控制面增强

阶段开始前必须先讨论方向、技术采用和概念边界。

| ID | 候选任务 | 状态 |
| --- | --- | --- |
| P5-T1 | 决定阶段和任务状态如何进入状态面板 | `todo` |
| P5-T2 | 增加风险和下一步摘要 | `todo` |

## P6 安全、并发与多 Agent 受控扩展

阶段开始前必须先讨论方向、技术采用和概念边界。

| ID | 候选任务 | 状态 |
| --- | --- | --- |
| P6-T1 | 定义 AgentPlane 威胁模型 | `todo` |
| P6-T2 | 定义高风险操作锁和多 Agent 边界 | `todo` |

## ✅ 当前继续入口

当前阶段：P1 任务书与“继续执行”闭环稳定。

下一步：

1. 先和人类讨论 P1 的实施方向。
2. 再讨论 P1 的技术采用。
3. 最后确认 P1 的概念边界。
4. 三项确认后，再拆 P1 的具体任务。
