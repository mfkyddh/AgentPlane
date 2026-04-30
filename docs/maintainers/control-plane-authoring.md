---
status: active
owner: AgentPlane maintainers
last_verified: 2026-04-29
superseded_by: null
audience: agent

---

# Control Plane Authoring

结论：`docs/maintainers/control-plane-authoring.md` 是 `AgentPlane` maintainer authoring 规则的唯一正文真源。控制面的长期架构合同看 [../architecture/control-plane.md](../architecture/control-plane.md)；专题执行步骤继续放在对应 runbook。

## 目标

本文约束 maintainer 在编写或收敛以下资产时的稳定写法：

- skill
- reference 文档
- maintainer 向导
- 示例、模板、测试与索引之间的联动规则

本文不承载单次迁移、单次事故或现场执行步骤。

## 真源分层

| 主题 | 正文真源 | maintainer 该做什么 |
| --- | --- | --- |
| 控制面长期架构合同 | [../architecture/control-plane.md](../architecture/control-plane.md) | 先对齐正式入口、对象面、任务面、输出合同、`inventory / ledger` 原则 |
| maintainer authoring 规则 | 本文 | 决定 skill、reference、runbook、测试、模板各自该写什么 |
| 文档可读性与可达性 | [../reference/documentation-governance.md](../reference/documentation-governance.md) | 控制 emoji、短文本、索引、孤立文档和 docs-sanity 门禁 |
| 专题执行步骤 | `docs/runbooks/*` | 只写正式流程、风险边界、人工接力点，不写第二实现 |
| 代码、模板、测试 | 仓库实际文件 | 保持与正式合同、示例、索引一致 |

## 治理资产闭环

| 资产 | 角色 | maintainer 约束 |
| --- | --- | --- |
| 代码 | 定义正式能力、输出合同、错误模型 | 新增正式能力时，先有正式 CLI，再补周边资产 |
| 模板 | 沉淀稳定输入骨架 | 只承载可复用骨架，不承载一次性现场上下文 |
| skill | Agent 路由层 | 负责触发、约束、验证、回写提示，不变成第二实现 |
| 文档 | 长期合同与专题解释层 | 架构页讲长期边界，runbook 讲专题流程，maintainer 页讲写法 |
| 测试 | 回归与约束层 | 冻结 CLI 合同、文档入口、skill 引用与历史事故修复 |
| 发布或收口 | 一次正式变更的对外一致性 | 至少确认代码、文档、模板、skill、测试没有明显漂移 |

## Skill 同步门禁

AgentPlane 的能力必须以 Skill 形式暴露给 AI Agent。任何改变正式行为的变更，都必须同步检查 `.agents/skills`。

| 变更类型 | 必须同步 |
| --- | --- |
| 新增、重命名或删除 CLI 命令 | 更新对应 skill 的触发条件、命令示例和最小验证 |
| 改变 domain/runtime/provider 行为 | 更新 skill 的边界、禁止行为、ledger 或 inventory 回写要求 |
| 新增或退役 runbook/reference | 更新 skill 下钻链接，避免 Agent 继续走旧入口 |
| 新增模板、compose 或 secrets 布局 | 更新 skill 的前置条件和真源路径说明 |
| 新增正式对象域或 workflow | 新增或重构 skill，并把它登记到 `.agents/skills/catalog.yaml` |

每个相关 PR 或逻辑提交至少满足一项：

1. 已同步修改对应 skill。
2. 已新增、删除或重构 skill，并更新 catalog。
3. 已在提交说明或 PR 描述中明确“无需更新 skill”的原因。

不得把“后续再补 skill”作为完成口径。若能力已经进入 `agentplane ...`，但没有可触发的 skill，视为对 Agent 不可用。

每次线上事故、接口变化、权限坑或输出歧义，都应尽量沉淀为以下至少一类资产：

- fixture
- regression test
- 文档修正
- skill 引导修正
- 示例补充

## Skill Authoring Contract

### 分层模型

| 层级 | 责任 | 不应承载什么 |
| --- | --- | --- |
| 共享 skill | Windows 上 `pwsh` 优先、backend-aware 正式入口基线、真源优先级、写后验证纪律 | 不要把所有领域细节重复一遍 |
| 领域 skill | 围绕对象域做意图路由，如 `infra`、`app-resource`、`onepanel`、`app-delivery` | 不要把专题流程塞成正文 |
| workflow skill | 编排多个领域、阶段顺序、失败回退点、人工确认点 | 不要替代领域 skill 的原子规范 |
| reference 文档 | 补充单个正式动作或单个稳定流程的细节 | 不要复制整份 runbook 或架构合同 |

### 正式入口优先级

正式建议的命令优先级固定为：

```text
agentplane.cli > internal implementation asset > runbook > ad-hoc shell
```

解释：

- `agentplane.cli` 是正式命令面。
- 内部实现资产只能由 CLI、provider 或测试调用，不能写成默认入口。
- runbook 用来解释流程、风险和人工步骤，不是第一命令面。
- ad-hoc shell 只能用于现场诊断，不能写成长期合同建议。

### skill 必备信息

每个控制面 skill 至少应覆盖：

1. 触发条件
2. 前置条件
3. 不触发条件或非目标
4. 快速决策
5. 标准命令
6. 最小验证
7. `inventory / ledger` 对齐要求
8. runbook 下钻入口
9. 禁止行为

workflow skill 可额外补：

1. 阶段顺序
2. 失败回退点
3. 人工确认点

### reference 文档必备信息

单动作 reference 建议固定包含：

1. 本文补充什么
2. 本文不补充什么
3. 对应真源入口
4. 最小命令示例
5. 已知差异或漂移提醒

补充规则：

- 长期文档不要写死 `.worktrees/` 绝对路径；需要保留现场路径时，只允许放在 `history` 或 handoff 的“执行快照”部分。
- `docs/reference/**/*.md` 与 `docs/maintainers/**/*.md` 在文首提供统一 metadata block，字段固定为 `status`、`owner`、`last_verified`、`superseded_by`；`last_verified` 必须使用 `YYYY-MM-DD`。
- 后续新增或再次改动的长期文档也必须沿用同一 metadata block，不允许再发明第二种写法。
- 仓库结构、入口边界和新增文件放置规则统一记录到 [`docs/reference/repository-structure.md`](../reference/repository-structure.md)。
- 跨层名称映射统一回指 [`docs/reference/control-plane-naming-registry.md`](../reference/control-plane-naming-registry.md)。

### secrets 写法约束

skill、reference、runbook 在提到 secrets 路径时，必须明确区分：

1. 真源声明：`secrets/hosts/<target>/...`
2. 运行时投影：`secrets/services/...` 等由真源派生的本机运行文件
3. 运行时投影路径：由正式真源生成的本机消费文件，只能标注为 `projection-only`

补充规则：

- 不要把笼统的 `secrets/`、`secrets/services/...`、`secrets/app-resources/...`、`secrets/env/...` 写成“真实文件默认位置”或“正式真源目录”。
- 若仍需提到旧路径，必须放入 archive 或历史说明，不得反向充当真源。
- 同时出现真源路径与投影路径时，先写 `secrets/hosts/<target>/...`，再写 projection-only 路径。

### `inventory / ledger` 写法约束

skill 或 reference 在涉及写操作时，必须明确区分：

1. 真源声明：`inventory/servers/<target>/inventory.json`
2. 机器派生：`inventory/servers/<target>/ledgers/*.json|md`
3. 人类解释：runbook、maintainer 文档、主机说明

写操作后，必须说明是否需要：

- `inventory refresh`
- `refresh-ledger`
- 应用摘要或主机摘要回写

写法上遵循 [../architecture/control-plane.md](../architecture/control-plane.md) 的真源优先级：`live state > inventory projection > runbook explanation`。

## 文档联动规则

### 架构页

架构页只保留长期稳定合同，例如：

- 正式入口
- 对象面与任务面边界
- 输出与错误 envelope
- `inventory / ledger` 投影原则

不要把 maintainer authoring 细则、专题步骤或案例操作继续堆回架构页。

### runbook

runbook 负责专题流程、风险边界、人工接力点与最小验证；需要 authoring 规则时，链接回本文；需要长期控制面合同时，链接回 [../architecture/control-plane.md](../architecture/control-plane.md)。

人类可读表达、emoji 语义、文档地图和孤立文档规则统一看 [../reference/documentation-governance.md](../reference/documentation-governance.md)。新增 active 文档必须加入 [../README.md](../README.md) 或被对应领域索引链接。

### 历史材料优先级

- active docs 与现行 code/test 优先于历史 spec、plan、handoff。
- 不要把历史设计稿中的旧路径、旧文案、旧 rollback 形态重新抄回 active docs；历史材料只用于解释来路，不反向覆盖当前真源。
- active `docs/architecture/` 与 `docs/runbooks/` 不保留旧链接占位文档；已经退出主流程的正文直接迁入 `docs/archive/`，当前入口只链接 active 真源或 archive 索引。

### 示例与测试

文档中的正式示例应尽量来自以下任一真源，而不是作者记忆：

- 已实现 CLI
- 现有模板
- 已验证 runbook
- 可回归 fixture

避免长期存在“文档示例无人验证”的孤立资产。

## 强制规则

1. 正式控制面能力优先写成 `agentplane ...`。
2. skill 不得把兼容脚本包装成正式能力。
3. skill 不得复制大段 runbook 内容。
4. skill 与文档都不得要求 Agent 手工维护 `inventory` 真源或台账文件。
5. 新增正式能力时，代码、文档、skill、测试至少要更新必要组合，而不是只改一处。
6. 文档示例必须使用正式入口，且能在代码、模板或已验证 runbook 中找到来源。
7. 历史事故修复不应只停留在聊天记录或临时 shell 历史中，应尽量转化为可回归资产。
8. 正式能力对外完成前，必须存在可触发的 skill 或明确的“不需要 Skill”记录。

## 反模式

- 每个 skill 都重复 Windows / WSL 入口细节、`repo-root`、验证纪律，导致共享规则漂移。
- 把专题流程写成第二份 runbook，或者把 runbook 写成第二实现。
- 只列命令，不交代触发条件、边界和最小验证。
- 只改代码，不同步检查模板、索引、skill、文档或测试。
- 让正式示例依赖未被说明的临时上下文。
- 让事故修复停留在一次性聊天记录里，不形成长期资产。

## 关联文档

- [../architecture/control-plane.md](../architecture/control-plane.md)
- [../reference/control-plane-naming-registry.md](../reference/control-plane-naming-registry.md)
- [../runbooks/control-plane-domain-onboarding.md](../runbooks/control-plane-domain-onboarding.md)
- [../runbooks/control-plane-agent-execution-flow.md](../runbooks/control-plane-agent-execution-flow.md)
