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
| P4 | 应用生命周期示范闭环 | `done` | 已由人类确认：文档演练、Markdown 计划、不碰真实运行态 | 示范项目选择标准、生命周期顺序和验收口径已定义 |
| P5 | 可视化控制面增强 | `active` | 已由人类确认：状态可见化、轻量投影、不创造新真源 | repo status 或静态面板能展示阶段、任务、项目、风险 |
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

### 阶段门

| 确认项 | 结论 |
| --- | --- |
| 具体实施方向 | 文档演练 / 示范方案设计：先定义未来真实示范闭环怎么选、怎么跑、怎么验收 |
| 技术采用 | Markdown 计划：首轮只维护本文，不新增 CLI、schema 或 blueprint 文件 |
| 概念边界 | 不碰真实运行态：不修改 `inventory/apps/catalog.json`，不部署，不写 inventory / ledger / doc-sync 运行状态 |

### 示范项目选择标准

未来进入真实示范闭环的 app 必须同时满足：

1. 低风险：优先选择 WSL、本地或可回收目标，不直接从生产目标开始。
2. 合同清晰：已有或可以补齐 `schema_version: 2` app delivery contract。
3. 可验证：至少有健康检查、构建产物边界和 dry-run 路径。
4. 可回退：能说明失败后如何停止、清理或回到原状态。
5. 非敏感：不需要把真实 secrets、生产 runbook 或本地私有路径写进 Git。

### 示范生命周期顺序

真实执行前，必须先按以下顺序形成计划：

1. 选择候选 app 和 target。
2. 校验 app delivery contract。
3. 运行 build / render 的 dry-run 或等价预演。
4. 准备 catalog 接入口径，但不直接写入 catalog。
5. 准备 deploy / verify 计划，但不直接执行 deploy。
6. 准备 inventory-refresh / doc-sync 回写计划。
7. 准备退役口径：如何撤 catalog、入口、服务、ledger / inventory 摘要。

### 验收口径

P4 本轮只要求完成示范方案设计。验收通过条件：

1. 任务书能回答“什么 app 适合做示范”。
2. 任务书能回答“真实执行前先跑哪些检查”。
3. 任务书能回答“什么时候才允许修改 catalog 或 deploy”。
4. 本轮不产生真实运行态变更。

| ID | 候选任务 | 状态 |
| --- | --- | --- |
| P4-T1 | 选择示范项目和目标环境 | `done` |
| P4-T2 | 跑通接入、验证、回写、退役口径 | `done` |

## P5 可视化控制面增强

### 阶段门

| 确认项 | 结论 |
| --- | --- |
| 具体实施方向 | 状态可见化：让人类能快速看到当前阶段、下一步任务、风险提示、仓库健康状态、app / target 摘要 |
| 技术采用 | 轻量投影：优先增强 `agentplane repo status`，必要时生成静态 HTML 面板；不引入数据库、前端框架或常驻服务 |
| 概念边界 | 只展示已有真源：阶段状态来自本文，仓库状态来自 `repo status`，target / app 状态来自 inventory / ledger；面板不是新的管理中心 |

### Workbook 状态投影规则

P5 的可视化投影必须以本文为阶段和任务状态真源。首轮投影只读取 Markdown，不把状态复制到新的持久化文件。

建议未来在 `agentplane repo status --repo-root .` 中增加只读 `roadmap` 区块；如果选择静态 HTML 面板，也必须复用同一组字段，不另起一套解释规则。

最小投影字段：

| 字段 | 来源 | 含义 |
| --- | --- | --- |
| `current_phase.id` | 阶段总览第一个非 `done`、非 `superseded` 阶段 | 当前长期推进阶段 |
| `current_phase.name` | 阶段总览 | 当前阶段名称 |
| `current_phase.status` | 阶段总览 | 当前阶段状态 |
| `current_phase.gate` | 阶段总览或阶段门表 | 人类已确认或待确认的阶段门 |
| `next_task.id` | 当前阶段第一个非 `done`、非 `deferred` 任务 | 下一步任务 |
| `next_task.title` | 当前阶段任务表 | 下一步任务标题 |
| `next_task.status` | 当前阶段任务表 | 下一步任务状态 |
| `resume_entry` | “当前继续入口”段落 | 面向 Agent 的继续执行提示 |
| `source.path` | 固定为本文路径 | 投影来源 |
| `source.last_verified` | frontmatter `last_verified` | 文档最近人工确认日期 |

投影规则：

1. `done` 和 `superseded` 阶段不作为当前阶段。
2. `done` 和 `deferred` 任务不作为下一步任务。
3. 如果当前阶段是 `planned` 或 `discussion-required`，`next_task` 应为空，`resume_entry` 应提示先讨论阶段门。
4. 如果 Markdown 解析失败，`repo status` 不应伪造状态；应返回 warning，并提示人类直接查看本文。
5. 投影只负责展示，不自动修改任务状态、不自动推进阶段。

### 风险与下一步摘要字段

风险是已有真源的推导视图，不是新真源。面板通过风险字段让人类快速定位阻塞和异常，通过下一步摘要字段给出推荐动作。

#### 风险字段

| 字段 | 含义 |
| --- | --- |
| `risks[].kind` | 风险类型枚举，见下表 |
| `risks[].severity` | `high`：阻塞推进；`medium`：需要关注但不阻塞；`low`：信息提示 |
| `risks[].message` | 人类可读的风险描述 |
| `risks[].source_ref` | 产生风险的真源位置（阶段 ID、任务 ID、target 名、check 名等） |

风险类型推导规则：

| kind | 来源 | severity | 触发条件 |
| --- | --- | --- | --- |
| `blocked_phase` | workbook 阶段状态 | high | 阶段状态为 `blocked` |
| `discussion_required` | workbook 阶段状态 | high | 阶段状态为 `discussion-required` 或 `planned`（当前阶段） |
| `blocked_task` | workbook 任务状态 | medium | 当前阶段中存在 `blocked` 任务 |
| `failed_check` | repo status checks | high | `checks.docs.ok` / `checks.boundaries.ok` / `checks.skills.ok` 为 false |
| `missing_inventory` | repo status targets | medium | target 缺 `inventory.json` 或 `README.md` |
| `stale_data` | repo status targets | low | target 的 `ledger_updated` 超过 30 天未更新 |
| `dirty_worktree` | git status | medium | 存在未提交变更 |

推导规则：

1. 风险只从 workbook、repo status、git status 三个已有真源推导，不引入新数据源。
2. 每种 kind 最多出现一次；同一 kind 下如有多个实例，合并到 `message` 中说明。
3. 当前阶段的 `planned` 状态只在当前阶段时产生 `discussion_required` 风险；后续未到达的阶段不产生风险。
4. `stale_data` 的 30 天阈值与 `inventory/state-snapshot.md` 的时效性检查一致。
5. 如果没有任何风险，`risks` 为空数组，面板不展示风险区。

#### 下一步摘要字段

| 字段 | 含义 |
| --- | --- |
| `next_step.type` | 推荐动作类型枚举，见下表 |
| `next_step.description` | 人类可读的推荐动作描述 |
| `next_step.target_ref` | 关联的阶段 / 任务 / 问题 / 文件引用 |

推荐动作类型推导规则（按优先级从高到低，命中第一条即返回）：

| 优先级 | type | 触发条件 | description 示例 |
| --- | --- | --- | --- |
| 1 | `fix_issue` | 存在 `failed_check` 风险 | "修复 docs-sanity 错误后再继续推进" |
| 2 | `commit_changes` | 存在 `dirty_worktree` 风险 | "先提交或处理工作区残留变更" |
| 3 | `discuss_gate` | 当前阶段为 `planned` 或 `discussion-required` | "P6 阶段门待讨论，请确认实施方向、技术采用和概念边界" |
| 4 | `continue_task` | 当前阶段为 `approved` 或 `active`，有 `todo` 或 `in-progress` 任务 | "执行 P5-T2：定义风险和下一步摘要的最小字段" |
| 5 | `all_done` | 所有阶段为 `done` 或 `superseded` | "当前路线已完成，需要人类新增阶段" |

推导规则：

1. 下一步摘要是风险的补集：如果有阻塞风险，先建议修复风险；如果没有风险，建议推进任务。
2. `target_ref` 指向具体的阶段 ID、任务 ID 或 check 名，方便人类直接定位。
3. 如果 `next_step.type` 为 `all_done`，面板应提示人类检查是否需要新增阶段或结束路线。

### 第一轮任务

| ID | 任务 | 状态 | 完成日期 | 验证或证据 | 后续影响 |
| --- | --- | --- | --- | --- | --- |
| P5-T0 | 记录 P5 阶段门并拆分第一轮任务 | `done` | 2026-04-29 | 本节阶段门与第一轮任务表 | 下一步从 P5-T1 开始执行 |
| P5-T1 | 定义 Workbook 状态如何投影到 `repo status` 或静态面板 | `done` | 2026-04-29 | 本节“Workbook 状态投影规则” | 下一步定义风险和下一步摘要字段 |
| P5-T2 | 定义风险和下一步摘要的最小字段 | `done` | 2026-04-29 | 本节"风险与下一步摘要字段"定义了风险类型推导规则和下一步摘要推导规则 | 下一步决定首轮采用 CLI JSON 输出增强还是静态 HTML 面板 |
| P5-T3 | 决定首轮采用 CLI JSON 输出增强还是静态 HTML 面板 | `done` | 2026-04-29 | 见本节"首轮技术方案决策" | 下一步实现 roadmap 投影的代码和测试 |

### 首轮技术方案决策

结论：**首轮采用 CLI JSON 输出增强**，HTML 面板作为后续增量。

理由：

1. **阶段门方向一致**：P5 阶段门确认"优先增强 `agentplane repo status`"，JSON 输出就是 `repo status` 的核心产物。
2. **数据层优先**：当前代码已分离数据层（`build_repo_status()` → JSON dict）和展示层（`render_status_html()` → HTML string）。JSON 是 HTML 的上游数据源；先做数据层，展示层只需在 `render_status_html()` 中增加对应的 HTML 片段即可自然跟进。
3. **不引入前端复杂度**：JSON 增强只需在 `build_repo_status()` 中增加一个 `roadmap` key，解析 workbook Markdown 并填充 T1/T2 定义的投影字段。不需要前端框架、数据库或常驻服务。
4. **机器可读先于人类可视**：JSON 输出可以被 Agent、CI、脚本直接消费；HTML 面板只服务人类浏览。Agent 的"继续执行"协议依赖 JSON 输出中的 roadmap 状态，这一闭环比人类浏览面板更紧迫。
5. **已有 HTML 基础可复用**：`render_status_html()` 已有卡片、表格、状态指示器等组件模板。后续增加 roadmap/risks/next-step 区块只需复用 `_card()` 和 `<section class="panel">` 模式。

实现路径：

1. 在 `agentplane/domain/repository/status.py` 中新增 `_workbook_status(repo_root)` 函数，解析 workbook Markdown 并返回 roadmap 投影字段。
2. 在 `build_repo_status()` 中调用 `_workbook_status()`，将结果作为 `roadmap` key 加入 payload。
3. `roadmap` 区块的结构严格对应 T1 投影字段 + T2 风险和下一步摘要字段。
4. 如果 workbook 文件不存在或 Markdown 解析失败，`roadmap` 区块返回 `{"ok": false, "error": "..."}`，不伪造状态。
5. 后续增量：在 `render_status_html()` 中增加 roadmap/risks/next-step 面板区块。

### 第二轮任务

| ID | 任务 | 状态 | 完成日期 | 验证或证据 | 后续影响 |
| --- | --- | --- | --- | --- | --- |
| P5-T4 | 在 `repo status` JSON 输出中实现 roadmap 投影 | `todo` | | | Agent "继续执行"协议可消费 JSON 中的 roadmap 状态 |
| P5-T5 | 在 `repo status` JSON 输出中实现风险和下一步摘要推导 | `todo` | | | 面板能提示阻塞、异常和推荐下一步 |
| P5-T6 | 在静态 HTML 面板中增加 roadmap/risks/next-step 区块 | `todo` | | | 人类可直接浏览阶段、任务、风险和推荐下一步 |
| P5-T7 | 运行最小验证并回写本阶段任务状态 | `todo` | | | P5 阶段验收 |

## P6 安全、并发与多 Agent 受控扩展

阶段开始前必须先讨论方向、技术采用和概念边界。

| ID | 候选任务 | 状态 |
| --- | --- | --- |
| P6-T1 | 定义 AgentPlane 威胁模型 | `todo` |
| P6-T2 | 定义高风险操作锁和多 Agent 边界 | `todo` |

## ✅ 当前继续入口

当前阶段：P5 可视化控制面增强。

下一步：

1. 执行 P5-T4：在 `repo status` JSON 输出中实现 roadmap 投影。
2. 执行前先检查工作区和仓库状态。
3. P5-T4 完成后回写任务状态、验证证据和后续影响。
