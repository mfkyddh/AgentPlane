---
status: active
owner: AgentPlane maintainers
last_verified: 2026-05-07
audience: both
---

# 核心术语表

> 结论：本文是 AgentPlane 唯一术语真源。术语按项目模型、域、投影模型、执行模型、底层平台、协作治理六组组织，与架构文档一一对应。

术语状态说明：

| 状态 | 含义 | 使用规则 |
|------|------|---------|
| `public` | 公开前台概念 | README、入门文档可以出现 |
| `internal` | 内部工程概念 | 架构、reference、maintainer 文档可以出现 |
| `future` | 未来机制 | 当前不建设，不作为验收口径 |

---

## 项目模型

回答的问题：**AgentPlane 帮助用户管理什么？**

> 详细定义见 [愿景 > 项目模型](core/vision.md#项目模型)。
> 每一层项目模型都有对应的管理能力（域），见 [架构 > 域](core/architecture.md#域)。

| 中文名（English Name） | 一句话定义 | 状态 | 避免误用 |
|------------------------|-----------|------|---------|
| 项目（Project） | 用户希望 AgentPlane 帮助管理的完整单元，如"商城系统"。只是一个分组标签——你不会"部署一个项目"，你部署的是项目里的 App | public | 不要把项目等同于 Git 仓库（repo）；项目是业务概念，repo 是代码载体 |
| 应用（App） | 项目中可独立部署、验证、回滚的业务单元，与项目是 1:1 或 1:N 关系 | public | 不要把应用等同于 1Panel 原生 app，也不要把所有容器都叫应用 |
| 目标环境（Target） | 被管理的运行环境，当前主要是服务器（Host），未来可扩展到云服务 | public | Target 是命令和配置中的稳定引用，不等同于物理路径或 IP 地址 |
| 应用项目（Application Project） | 承载某个应用源代码、构建资产、测试和交付合同的独立仓库 | public | 应用项目仓库不是生产控制面，不应保存正式 secrets、正式 inventory 或生产部署脚本 |
| 应用交付合同（Application Delivery Contract） | 应用仓库交给 AgentPlane 的非敏感交付说明，位于 `deploy/agentplane/contract.yaml` | public | 合同描述交付边界，不保存真实密钥 |
| 基础设施即应用（Infrastructure as Apps） | PostgreSQL、Redis、MinIO 等基础设施服务作为 App 管理在专门的基础设施项目中，没有特例 | public | 不要把基础设施服务当成特殊对象——它们和业务应用用同一套流程管理 |

---

## 域

回答的问题：**AgentPlane 怎么划分职责？**

> 详细定义见 [架构 > 域](core/architecture.md#域)。
> 决策背景见 [决策记录 005](decisions/005-domain-model.md)。

| 中文名（English Name） | 一句话定义 | 状态 | 避免误用 |
|------------------------|-----------|------|---------|
| 域（Domain） | AgentPlane 的职责划分，每个域对应项目模型的一层 | public | 域不是代码模块——一个域可能包含多个代码模块 |
| infra 域 | Target 配置（主机、网络、Secrets），对应项目模型的 Target 层 | public | infra 不管具体服务——具体服务由 service 域管理 |
| service 域 | 运行时管理（所有 Docker 容器的健康、重启、日志），对应项目模型的运行时层 | public | service 不区分基础设施容器和业务容器——它们都是 Docker 容器 |
| app 域 | 应用交付生命周期（catalog、构建、部署、回滚），对应项目模型的 App 层 | public | app 不管运行时——运行时由 service 域管理 |
| ingress 域 | 公网入口（域名、SSL、路由），对应项目模型的对外访问层 | public | ingress 不是 1Panel website 的别名——它只是 provider 层底座 |
| project 域 | 项目治理（分组、聚合状态、项目级配置），对应项目模型的 Project 层 | public | project 不是 repo 管理——repo 是代码载体，project 是业务分组 |

---

## 投影模型

回答的问题：**AgentPlane 怎么管理数据？**

> 详细定义见 [架构 > 三层投影模型](core/architecture.md#三层投影模型)。

| 中文名（English Name） | 一句话定义 | 状态 | 避免误用 |
|------------------------|-----------|------|---------|
| 投影（Projection） | 从真源派生的只读视图（如 Host Inventory、Object Ledgers、App Summary） | internal | 不要把投影作为新用户主线概念——它是内部数据模型 |
| 真源（Source of Truth） | 某一类事实的正式来源（如 Git 配置、Live State、Inventory、Ledger） | internal | 真源优先级：Live State > Inventory > Ledger > Runbook |
| 台账（Host Inventory） | 记录某个 Target 有哪些受管对象的结构化声明 | internal | 不要让人手维护 inventory 作为事实——它应由正式流程刷新 |
| 证据（Object Ledgers） | 围绕对象或操作生成的机器派生验证记录 | internal | 不要把 ledger 当成用户需要直接编辑的文档 |
| 摘要（App Summary） | 面向人类的当前状况摘要，从台账和证据派生 | internal | — |
| 现场状态（Live State） | 通过现场命令、API、文件读取等方式获得的当前真实状态 | internal | — |
| 操作凭证（Operation Receipt） | 一次正式操作完成后给人类阅读的结构化摘要 | internal | 当前不要求新用户理解模板字段 |
| 异常复盘（Exception Review） | 失败、紧急绕过、回滚、审批拒绝后的复盘记录 | internal | — |

---

## 执行模型

回答的问题：**AgentPlane 怎么执行操作？**

> 详细定义见 [架构 > CLI 接口规范](core/architecture.md#cli-接口规范) 和 [架构 > 任务入口模型](core/architecture.md#任务入口模型)。

| 中文名（English Name） | 一句话定义 | 状态 | 避免误用 |
|------------------------|-----------|------|---------|
| CLI | AgentPlane 的正式执行入口，形态为 `agentplane <domain> <surface> <verb> [flags]` | public | 不要把脚本、runbook 或手写 shell 当成正式 CLI |
| Skill | AI Agent 理解人类意图后选择的能力入口，负责路由到正式 CLI | public | Skill 不执行第二套逻辑，不直接拼 SSH、Docker 或 provider API |
| Surface | 命令中的对象面或工作流面。对象面操作单个对象，工作流面执行跨对象的流程 | internal | — |
| Verbs | 命令中的动作部分，即"你想做什么"（如 search、get、plan、apply、verify） | public | — |
| 任务入口（Task Entry） | 面向 Agent 的正式任务入口，表达"下一步要做什么"，而不是底层对象 CRUD | internal | 不要把 task-entry 暴露成新用户必须理解的概念 |
| 执行闭环（Execution Loop） | 所有操作遵循 Plan → Apply → Verify → Record 流程 | internal | — |
| 错误 Envelope | CLI 返回错误时的统一 JSON 结构，方便 Agent 解析 | internal | — |

---

## 底层平台

回答的问题：**AgentPlane 依赖什么底层设施？**

> 技术细节见 [编码与协作规范](conventions.md#技术栈基线)。

| 中文名（English Name） | 一句话定义 | 状态 | 避免误用 |
|------------------------|-----------|------|---------|
| 底层平台（Substrate） | 被 AgentPlane 管理的底层基础设施平台（如 1Panel、Docker Compose） | internal | — |
| 适配层（Provider） | 封装外部平台 API 的适配层，让上层代码不用关心底层细节 | internal | — |
| 运行时适配器（Adapter） | 处理运行时环境差异的适配器（如 docker_runtime、systemd_runtime） | internal | — |

---

## 协作治理

回答的问题：**人、AI、文档如何协同？**

> 规则细节见 [conventions.md](conventions.md) 和 [Maintainer 指南](maintainer-guide.md)。

| 中文名（English Name） | 一句话定义 | 状态 | 避免误用 |
|------------------------|-----------|------|---------|
| 主 Agent（Main Agent） | 接受人类意图、负责阶段门和整体进度的 Agent | internal | — |
| 子 Agent（Sub Agent） | 由主 Agent 派遣，执行有限范围具体任务的 Agent | internal | — |
| 配置中心（Config Center） | Git 中的权威状态定义，回答"我们期望系统应该是什么样" | internal | — |
| 道法术 | 原则体系的三个层次：道（哲学基座）、法（方法论）、术（工程原则） | internal | 道 > 法 > 术，冲突时高层级优先 |
| 阶段门（Stage Gate） | 长期推进决策的人类确认点 | internal | — |

---

## 补充术语

不属于核心模型，但需要在术语表中定义。

| 中文名（English Name） | 一句话定义 | 状态 | 避免误用 |
|------------------------|-----------|------|---------|
| 项目资产总表（Project Registry） | 未来可能用于统一管理多个项目、应用仓库、文档站、服务组件的总表 | `future` | 当前不建设 schema，不作为验收口径 |
| 项目复用模板（Blueprint） | 未来用于沉淀同类项目创建、接入、交付经验的复用模板 | `future` | 当前不创建正式 blueprint 文件 |
| 应用索引（App Catalog） | 已进入正式 app delivery 执行面的应用索引 | internal | — |
| 全局配置（Global Config） | 作用于整个项目的配置，例如域名策略、网络约束、共享依赖 | `future` | 当前阶段不需要单独实现 Global Config 对象域 |

---

## 如何使用本表

- **遇到不熟悉的术语**：先查本表，再点击对应组的关联文档深入了解
- **新增术语**：必须先在本表定义，再在其他文档引用
- **术语冲突**：以本表为准，其他文档中的定义应与本表一致
- **判断术语状态**：`public` 可出现在 README 和入门文档；`internal` 只在架构和 reference 文档出现；`future` 不作为当前建设项

---

## 关联文档

- [愿景](core/vision.md) — 项目模型、目标用户、核心价值
- [架构](core/architecture.md) — 域、投影模型、CLI 接口、执行闭环
- [原则](core/principles.md) — 道法术三层原则体系
- [入门指南](getting-started.md) — 面向人类的概念解释
