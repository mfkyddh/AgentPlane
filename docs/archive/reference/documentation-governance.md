---
status: archived
owner: AgentPlane maintainers
last_verified: 2026-04-30
superseded_by: null
audience: agent
layer: engineering
---

# 文档治理规范

结论：AgentPlane 文档采用 **一份真源，多种投影**。人类文档负责理解和决策，Agent 文档负责约束和执行，机器门禁负责发现断链、孤立文档和入口漂移。

## 🎯 目标

| 目标 | 要求 |
| --- | --- |
| 人类好读 | 结构清楚、句子短、emoji 有语义，不写成堆叠式说明书 |
| Agent 好用 | 每页都能定位正式入口、真源、验证方式和下钻链接 |
| 不脱节 | 状态类内容尽量由 `agentplane ...` 生成或验证 |
| 可治理 | 能机械检查的规则进入 `repo docs-sanity` 或测试 |

## 👥 双重受众

| 受众 | 默认入口 | 阅读目标 |
| --- | --- | --- |
| 新读者 | [../../README.md](../../README.md) | 5 分钟知道项目是什么、能做什么、下一步读哪里 |
| 使用者 | [../README.md](../README.md) | 从文档地图进入概念、架构、runbook 或 reference |
| AI Agent | [../../AGENTS.md](../../AGENTS.md) | 获取短规则、正式入口、禁令和验证纪律 |
| 维护者 | [../maintainers/control-plane-authoring.md](../maintainers/control-plane-authoring.md) | 决定代码、skill、文档、测试如何一起演进 |

## 🗂️ 文档分层

| 层级 | 写什么 | 不写什么 |
| --- | --- | --- |
| `README.md` | 项目定位、快速开始、核心导航 | 细长架构合同、专题操作全集 |
| `AGENTS.md` | AI 每次执行必须遵守的短合同 | 背景故事、大段解释、重复 runbook |
| `docs/README.md` | 人类和 AI 的完整文档地图 | 具体操作步骤 |
| `docs/getting-started/` | 核心概念、第一次阅读路径 | 现场细节、事故记录 |
| `docs/architecture/` | 长期架构合同和边界 | 单次迁移、命令流水账 |
| `docs/reference/` | 稳定规范、命名、结构、风格（含术语表） | 案例叙事、临时排障 |
| `docs/runbooks/` | 专题流程、风险、验证、回写 | 第二套实现或 raw shell 默认入口 |
| `docs/maintainers/` | 文档、skill、测试、模板的写作规则 | 具体主机操作步骤 |
| `docs/history/`、`docs/archive/` | 历史材料和退役口径 | 当前事实真源 |

## ✍️ 人类可读标准

| 规则 | 级别 | 标准 |
| --- | --- | --- |
| README 保持干净 | 🔴 | 根 `README.md` 是开源首页，不使用可见 YAML frontmatter；治理元数据保留在 `docs/**`、`AGENTS.md` 等执行文档 |
| emoji 有语义 | 🔴 | `##` 标题必须带语义 emoji（从下方词典选取）；每个 emoji 帮助扫描，不做装饰堆叠 |
| 标题有序号 | 🟡 | 索引/导航类文档（README、目录页）的 `##` 标题建议带序号（`## 🧭 1. 入门路线`）；正文文档不强制 |
| 先给结论 | 🔴 | 每页 frontmatter 后第一行必须是 `结论：` 开头的一句话，说明本文解决什么问题 |
| 文字短 | 🔴 | 一个段落优先 1-3 句；能用表格表达就不用长段落 |
| 少 AI 味 | 🔴 | 避免空泛套话，如”全面赋能””极致体验”；直接写对象、动作、边界 |
| 命令真实 | 🔴 | 示例命令必须优先来自已实现 CLI、模板、测试或已验证 runbook |
| 风险显眼 | 🔴 | 破坏性动作、secret、生产环境、live gate 必须有 `⚠️` 或明确风险小节 |
| 提示块标记 | 🟡 | 重要提示、强制规则用 `> 📌` callout；风险用 `> ⚠️`；不用普通段落强调 |
| 章节分隔 | 🟡 | `##` 章节之间用 `---` 分隔线，帮助视觉分段 |

### emoji 语义词典

| emoji | 用途 |
| --- | --- |
| 🧭 | 入口、导航、阅读路径 |
| 🎯 | 目标、适用场景 |
| 🧠 | 概念、架构判断 |
| 🛠️ | 操作、命令、实现步骤 |
| ✅ | 验证、完成标准 |
| ⚠️ | 风险、禁止事项 |
| 🔗 | 链接、上下游文档 |
| 🔐 | secrets、安全 |
| 🤖 | Agent 执行规则 |
| 👤 | 人类决策点 |
| 🧪 | 测试、门禁 |
| 📌 | 稳定原则、强制规则 |
| 📋 | 任务、进度、清单 |
| 📦 | 部署、打包、运维 |
| 🚀 | 快速上手、教程 |
| 🔧 | 工具、基础设施 |
| 🕰️ | 历史、归档 |

### 可读性分层

不同文档类型采用不同程度的可读性增强：

| 文档类型 | emoji 标题 | 序号 | 结论行 | 分隔线 | callout | 示例 |
| --- | --- | --- |--- | --- | --- | --- |
| 索引/导航（README、目录页） | 🔴 | 🔴 | 🔴 | 🔴 | 🟡 | `docs/README.md` |
| 入门/教程（getting-started、tutorials） | 🔴 | 🟡 | 🔴 | 🔴 | 🟡 | `docs/getting-started/architecture-overview.md` |
| 正文规范（reference、architecture、runbook） | 🔴 | 🟢 | 🔴 | 🔴 | 🟡 | `docs/reference/cross-platform.md` |
| 决策记录（decisions/ADR） | 🟡 | 🟢 | 🔴 | 🟡 | 🟢 | `docs/strategy/decisions/002-boundary.md` |
| 维护者内部（maintainers） | 🟡 | 🟢 | 🔴 | 🟡 | 🟢 | `docs/maintainers/control-plane-authoring.md` |
| 历史/归档（history、archive） | 🟢 | 🟢 | 🟡 | 🟢 | 🟢 | `docs/history/index.md` |

级别说明：🔴 必须　🟡 建议　🟢 不强制

## 🔗 链接标准

1. 每个 active 文档必须能从另一个 active Markdown 文档到达。
2. 新文档必须加入 [../README.md](../README.md) 或被对应领域索引链接。
3. 每个专题 runbook 至少链接一个长期合同或 reference 文档。
4. 每个 reference 文档至少说明它补充什么、不补充什么、上游真源在哪里。
5. `docs/archive/` 与 `docs/history/` 可以保留历史链接，但不得反向覆盖 active 口径。

## 🤖 AI 全执行闭环

人类只需要表达目标、边界和验收口径。AI 执行时固定使用这条闭环：

```text
人类意图 -> AI 计划 -> agentplane plan -> apply -> verify -> ledger -> inventory refresh -> doc-sync -> 人类摘要
```

| 阶段 | 人类责任 | AI / CLI 责任 |
| --- | --- | --- |
| 方向 | 给目标、约束、风险接受度 | 澄清缺口，形成可执行计划 |
| 架构 | 确认长期边界 | 对齐 architecture/reference |
| 执行 | 不手工操作现场 | 通过 `agentplane ...` 执行 |
| 验收 | 看摘要和证据 | 运行最小验证，回写台账和文档 |

## 🧪 强制门禁

当前已经进入 `agentplane repo docs-sanity --repo-root .` 的规则：

| 检查 | 失败条件 |
| --- | --- |
| 本地链接 | active 文档存在断链 |
| 退役入口 | active 文档继续推荐旧命令入口 |
| 孤立文档 | active 文档没有任何其他 active 文档链接它 |

后续适合逐步纳入脚本的规则：

| 阶段 | 规则 | 建议入口 |
| --- | --- | --- |
| P1 | `docs/reference` 与 `docs/maintainers` metadata 完整 | `repo docs-sanity` |
| P1 | 新增 active 文档必须出现在文档地图 | `repo docs-sanity` |
| P2 | README 超长提醒，不阻断 | `repo docs-sanity --strict` |
| P2 | runbook 必须出现正式入口和最小验证 | `tests/repository` |
| P3 | 状态快照超过阈值提醒 | `projection ledger refresh` 或 `doc-sync` |
| P3 | 示例命令与 CLI help 对账 | `repo health-check` |

## 🧩 新文档模板

新 active 文档优先使用这个骨架：

```markdown
---
status: archived
owner: AgentPlane maintainers
last_verified: YYYY-MM-DD
superseded_by: null
audience: agent|human|both
layer: engineering|technical
---

# 标题

结论：一句话说明本文解决什么问题。

---

## 🎯 1. 适用场景

| 场景 | 是否适用 |
| --- | --- |

---

## 🛠️ 2. 正式入口

`agentplane ...`

---

## ✅ 3. 最小验证

`agentplane ... verify`

---

## 🔗 关联文档

- [上游合同](../architecture/control-plane.md)
```

## 📅 实施计划

| 阶段 | 目标 | 状态 |
| --- | --- | --- |
| 0 | 建立基线：本规范、文档地图、孤立文档检查 | ✅ 完成 |
| 1 | 收敛入口：README 瘦身为入口页，AGENTS 保持短合同 | ✅ 完成 |
| 2 | 统一模板：frontmatter、结论行、emoji 语义化标题 | ✅ 完成 |
| 3 | 强化门禁：元数据完整性、last_verified 过期、README 长度、结论行检查 | ✅ 完成 |
| 4 | 人机协同：人类意图模板、AI 执行闭环协议 | 🔄 进行中 |
| 5 | 自动回写：状态摘要由 `ledger / inventory / doc-sync` 生成 | 待启动 |
| 6 | CI 集成：fast test、docs-sanity、secret-scan、privacy-scan 纳入 PR pipeline；release-check 保留为发布门禁 | ✅ 完成 |

## 👤 人类意图输入模板

人类只需要表达目标、边界和验收标准。AI 负责补全结构并执行。

### 轻量格式

```markdown
🎯 目标：（一句话说明要达成什么）
🖥️ 目标环境：（wsl / prod0-main）
🚫 不希望改变的东西：（约束和边界）
✅ 验收标准：（怎么判断做完了）
⚠️ 风险等级：（低 / 中 / 高）
```

### 使用规则

- 人类可以只写自然语言，AI 自动补全结构
- AI 收到意图后，必须先输出计划，确认后再执行
- 执行完毕后，AI 必须检查：代码/文档/台账是否同步

## 🤖 AI 执行闭环协议

每次 AI 执行变更时，必须遵循以下闭环：

```text
人类意图 → AI 计划 → agentplane plan → apply → verify → ledger → inventory refresh → doc-sync → 人类摘要
```

### 收尾检查清单

AI 每次执行完毕后，必须确认：

| 检查项 | 要求 |
| --- | --- |
| 代码变更 | 是否运行了 `agentplane repo health-check --repo-root .`？ |
| 文档同步 | 是否更新了相关 active 文档的 `last_verified`？ |
| 台账同步 | 是否运行了 `projection ledger refresh --write`（如涉及运行状态）？ |
| docs-sanity | 是否通过了 `agentplane repo docs-sanity --repo-root .`？ |
| 人类摘要 | 是否向人类报告了做了什么、改了什么、还需要什么？ |

### 禁止事项

1. ❌ 执行后不做验证
2. ❌ 改了代码不检查文档是否需要同步
3. ❌ 改了文档不检查 docs-sanity
4. ❌ 对人类只报告"完成"，不说具体做了什么

## ✅ 维护 Checklist

- 是否加入 [../README.md](../README.md) 或领域索引？
- 是否说明读者、范围、正式入口和验证方式？
- 是否有上游合同和下游 runbook 链接？
- 是否避免把历史说明写成当前事实？
- 是否能通过 `agentplane repo docs-sanity --repo-root .`？
