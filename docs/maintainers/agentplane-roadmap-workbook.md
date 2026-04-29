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
| P1 | 任务书与“继续执行”闭环稳定 | `done` | 已由人类确认：恢复上下文、Markdown 规则、只管继续执行 | Agent 能稳定恢复上下文、定位下一任务、回写状态 |
| P2 | 操作凭证、例外和复盘模型 | `done` | 已由人类确认：人类可读凭证、Markdown 模板、只定义模型 | Operation Receipt 与 Exception Review 最小模型可用 |
| P3 | 项目注册表与项目蓝图模型 | `done` | 已由人类确认：弱化 Project Registry、Markdown 规则、只定义关系 | App Catalog 与 Blueprint 边界清晰，Project Registry 暂缓 |
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
| 具体实施方向 | 恢复上下文：让 Agent 下次继续时先读真源、查状态、定位阶段和下一步 |
| 技术采用 | Markdown 规则：首轮只维护本文，不新增 CLI、schema 或 repo status 投影 |
| 概念边界 | 只管继续执行：不设计 Operation Receipt、Exception Review、project registry 或可视化 |

### 固定恢复检查清单

当人类说“继续执行”时，Agent 必须按此顺序恢复上下文：

1. 读取本文、[终极蓝图](../reference/agentplane-ultimate-blueprint.md) 和 [Roadmap](../../ROADMAP.md)。
2. 运行 `agentplane repo status --repo-root .`，确认 docs、privacy、skills 和 catalog 状态。
3. 运行 `git status --short`，确认是否存在 Git 可见未提交变更。
4. 如果工作区干净，定位阶段总览中第一个状态不是 `done` 或 `superseded` 的阶段。
5. 如果该阶段是 `planned` 或 `discussion-required`，先和人类讨论实施方向、技术采用、概念边界。
6. 如果该阶段是 `approved` 或 `active`，定位该阶段第一个非 `done`、非 `deferred` 的任务。
7. 如果没有可继续任务，说明当前路线已完成或需要人类新增阶段。

### 脏工作区处理规则

如果 `git status --short` 返回任何未提交变更，Agent 必须先停下并说明：

1. 未提交文件列表。
2. 这些文件是否看起来属于上一次任务、当前任务或未知来源。
3. 继续执行的风险。
4. 建议的下一步，例如先提交、先丢弃、先转存或由人类确认归属。

Agent 不得自动把已有未提交变更纳入当前任务，也不得自动提交无法确认归属的残留变更。

### 初始候选任务

| ID | 任务 | 状态 | 完成日期 | 验证或证据 | 后续影响 |
| --- | --- | --- | --- | --- | --- |
| P1-T1 | 设计“继续执行”时的固定检查清单 | `done` | 2026-04-29 | 本节“固定恢复检查清单” | 让 Agent 恢复上下文更稳定 |
| P1-T2 | 决定任务书是否需要 repo status 投影 | `done` | 2026-04-29 | 结论：P1 不做投影，自动化留到 P5 | 保持 P1 为 Markdown-only 协议 |

## P2 操作凭证、例外和复盘模型

### 阶段门

| 确认项 | 结论 |
| --- | --- |
| 具体实施方向 | 人类可读凭证：让正式任务完成后留下可读、可追踪、可复盘的长期记忆 |
| 技术采用 | Markdown 模板：首轮只在本文定义填写规则，不新增 CLI、schema 或自动化 |
| 概念边界 | 只定义模型：不决定保存目录，不接入 `tmp/operation-ledger`、inventory ledger、repo status 或 dashboard |

### 触发规则

| 场景 | 必须产物 |
| --- | --- |
| 正式阶段任务完成 | Operation Receipt |
| 验证失败 | Operation Receipt + Exception Review |
| 紧急绕过 | Operation Receipt + Exception Review |
| 回滚发生 | Operation Receipt + Exception Review |
| 审批拒绝 | Exception Review |

### Operation Receipt 模板

用于每个正式阶段任务完成后，记录人类可读的完成凭证。

```markdown
#### Operation Receipt

| 字段 | 内容 |
| --- | --- |
| 任务 | <阶段任务 ID 和标题> |
| 目标 | <本次任务要达成什么> |
| 触发 Skill | <使用或匹配到的 Skill；无则写“无，原因：...”> |
| 正式命令或动作 | <关键 agentplane 命令、验证命令或文档动作摘要> |
| 验证结果 | <通过/失败/未运行及原因> |
| 证据链接 | <相关文档、commit、ledger、status 输出或报告引用> |
| 后续影响 | <推进到哪个阶段、留下什么 follow-up> |
```

### Exception Review 模板

用于失败、紧急绕过、回滚、审批拒绝等异常场景。目标是把异常转化为规范、Skill、测试或后续任务。

```markdown
#### Exception Review

| 字段 | 内容 |
| --- | --- |
| 异常类型 | <失败 / 紧急绕过 / 回滚 / 审批拒绝> |
| 发生原因 | <已知原因；未知则写待查> |
| 影响范围 | <影响的阶段、任务、target、app 或文档> |
| 恢复动作 | <已经做了什么恢复；没有则写无> |
| 复盘结论 | <需要新增规则、Skill、测试、文档或后续任务吗> |
| 后续任务 | <任务 ID 或待创建任务> |
```

### 任务

| ID | 候选任务 | 状态 |
| --- | --- | --- |
| P2-T1 | 定义 Operation Receipt 最小字段 | `done` |
| P2-T2 | 定义 Exception Review 最小字段 | `done` |

## P3 项目注册表与项目蓝图模型

### 阶段门

| 确认项 | 结论 |
| --- | --- |
| 具体实施方向 | 弱化 Project Registry：当前不建立项目总台账，先讲清 App Catalog 与 Blueprint 的关系 |
| 技术采用 | Markdown 规则：首轮只维护本文，不新增 reference、schema、CLI 或真实数据文件 |
| 概念边界 | 只定义关系：不创建 Project Registry，不创建真实 blueprint 文件，不修改 `inventory/apps/catalog.json` |

### 概念关系

P3 不要求同时建设三个机制。当前只保留两个必要概念，并把 Project Registry 延后。

| 概念 | 当前定位 | 是否现在建设 |
| --- | --- | --- |
| App Catalog | 已存在的 app delivery 执行索引，回答“哪些 app 能被 `agentplane app delivery ...` 正式识别和交付” | 是，沿用 `inventory/apps/catalog.json` |
| Blueprint | 未来复用项目创建或接入经验的标准配方，回答“同类项目下次怎么创建/接入” | 只保留概念，不创建文件 |
| Project Registry | 上层项目资产总表，回答“我长期管理哪些项目” | 暂缓，等项目数量和类型变多后再讨论 |

更简单的关系：

```text
App Catalog = 已进入正式 app delivery 执行面的应用索引
Blueprint = 创建或接入同类项目时复用的方法模板
Project Registry = 未来可能需要的全部项目资产总表
```

### 当前规则

1. 需要 `agentplane app delivery ...` 正式识别的应用，才进入 App Catalog。
2. 重复出现的项目创建、接入或交付经验，才沉淀为 Blueprint。
3. 文档站、工具库、控制面自身等“不是 app delivery 应用”的对象，不要硬塞进 App Catalog。
4. Project Registry 暂时不落文件、不定义 schema、不作为当前阶段验收口径。
5. 后续如果出现多个非 app delivery 项目需要统一管理，再单独开启 Project Registry 阶段。

| ID | 候选任务 | 状态 |
| --- | --- | --- |
| P3-T1 | 区分 project registry 与 app catalog | `done` |
| P3-T2 | 定义第一个低风险项目蓝图候选 | `done` |

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

当前阶段：P4 应用生命周期示范闭环。

下一步：

1. 先和人类讨论 P4 的实施方向。
2. 再讨论 P4 的技术采用。
3. 最后确认 P4 的概念边界。
4. 三项确认后，再拆 P4 的具体任务。
