---
status: archived
owner: AgentPlane maintainers
last_verified: 2026-05-01
superseded_by: null
audience: both
layer: engineering
---

# 📖 核心术语表

结论：本文是 AgentPlane 唯一术语真源。所有关键术语在此定义，其他文档只引用或做轻量解释。术语按六层+纵向贯通模型组织。

术语状态说明：

| 状态 | 含义 | 使用规则 |
|------|------|---------|
| `public` | 公开前台概念 | README、入门文档可以出现 |
| `internal` | 内部工程概念 | 架构、reference、maintainer 文档可以出现 |
| `future` | 未来机制 | 当前不建设，不作为验收口径 |
| `legacy` | 历史概念 | 只解释来源，不再推进 |

---

## 分层模型总览

```
              ┌──── 协作治理（纵向贯通）────┐
              │  主线机制 / 阶段门 / 审批门禁  │
              │  文档规范 / 人机协作协议       │
              │                              │
┌─────────────┼──────────────────────────────┐
│ 第一层      │  用户对象层                   │  public
├─────────────┼──────────────────────────────┤
│ 第二层      │  产品/项目层                  │  public
├─────────────┼──────────────────────────────┤
│ 第三层      │  应用项目层                   │  public
├─────────────┼──────────────────────────────┤
│ 第四层      │  控制面对象层                 │  internal
├─────────────┼──────────────────────────────┤
│ 第五层      │  任务入口层                   │  public / internal
├─────────────┼──────────────────────────────┤
│ 第六层      │  证据状态层                   │  internal
└─────────────┴──────────────────────────────┘
```

---

## 第一层：用户对象层

回答的问题：**谁在使用 AgentPlane？他们为什么需要它？**

| 中文名（English Name） | 一句话定义 | 状态 | 避免误用 |
|------------------------|-----------|------|---------|
| 用户对象（User Object） | AgentPlane 服务的目标人群，包括个人开发者、小团队、开源维护者、自托管服务维护者 | public | 不要把用户对象等同于 Linux 用户、Git 用户或系统账号 |

---

## 第二层：产品/项目层

回答的问题：**AgentPlane 最终帮助用户管理什么？**

| 中文名（English Name） | 一句话定义 | 状态 | 避免误用 |
|------------------------|-----------|------|---------|
| 产品/项目（Product/Project） | 用户希望 AgentPlane 帮助管理的完整产品或项目单元，可能包含多个业务系统、多个应用和全局配置 | public | 不要把这里的项目等同于 `docs/project/` 中的任务推进文档 |
| 业务系统（Business System） | 产品/项目中的业务功能单元，下面可以包含一个或多个应用 | public | 当前阶段不需要为业务系统建立 schema 或 CLI 对象 |
| 应用（Application/App） | 可被构建、部署、验证、回滚的业务应用 | public | 不要把应用等同于 1Panel 原生 app，也不要把所有容器都叫应用 |
| 全局配置（Global Config） | 作用于整个产品/项目的配置，例如域名策略、网络约束、共享依赖、全局 secrets 规则 | public | 当前阶段不需要单独实现 Global Config 对象域 |

---

## 第三层：应用项目层

回答的问题：**一个具体应用仓库如何交给 AgentPlane 管理？**

| 中文名（English Name） | 一句话定义 | 状态 | 避免误用 |
|------------------------|-----------|------|---------|
| 应用项目（Application Project） | 承载某个应用源代码、构建资产、测试和交付合同的独立仓库 | public | 应用项目仓库不是生产控制面，不应保存正式 secrets、正式 inventory 或生产部署脚本 |
| 应用交付合同（Application Delivery Contract） | 应用仓库交给 AgentPlane 的非敏感交付说明，通常位于 `deploy/agentplane/contract.yaml` | public | 合同描述交付边界，不保存真实密钥 |

---

## 第四层：控制面对象层

回答的问题：**AgentPlane 内部用哪些正式对象来管理用户的产品和应用？**

| 中文名（English Name） | 一句话定义 | 状态 | 避免误用 |
|------------------------|-----------|------|---------|
| 控制面对象（Control Plane Object） | AgentPlane 内部正式管理的对象，如 `infra`、`service`、`ingress`、`app`、`app resource` | internal | 不要让用户一上来理解所有控制面对象 |
| 主机/目标环境（Host/Target） | 被 AgentPlane 管理的运行环境，例如 `wsl`、`prod0-main` | public | `target` 是命令和配置中的稳定引用，不等同于物理路径或 IP 地址 |
| 服务（Service） | 在目标环境中长期运行并可被验证或操作的服务，例如 PostgreSQL、Redis、MinIO、业务服务容器 | public / internal | 不要把未登记、不可验证的一次性进程称为 formal service |
| 入口（Ingress） | 对外访问应用或服务的入口，包括域名、证书、反向代理、公网 URL 等 | public / internal | 不要直接把 1Panel website 当成公开主对象；它只是 provider 层底座 |
| 应用资源（App Resource） | 应用依赖的受管资源，例如数据库、secret scope、资源绑定关系 | internal | 不要把 app resource 当成应用运行态 env 投影 |
| 状态投影（Projection） | 从真源派生的只读视图（如 inventory、ledger、app summary） | internal | 不要把 projection 作为新用户主线概念 |
| 真源（Source of Truth） | 某一类事实的正式真源（如 Git 配置、inventory、ledger） | internal | — |
| 现场状态（Live State） | 通过现场命令、API、文件读取等方式获得的当前真实状态 | internal | — |

---

## 第五层：任务入口层

回答的问题：**AI 下一步应该通过什么正式入口执行任务？**

| 中文名（English Name） | 一句话定义 | 状态 | 避免误用 |
|------------------------|-----------|------|---------|
| Skill | AI Agent 理解人类意图后选择的能力入口，负责路由到正式 `agentplane ...` CLI | public | Skill 不执行第二套逻辑，不直接拼 SSH、Docker 或 provider API |
| CLI | AgentPlane 的正式执行入口，形态为 `agentplane <domain> <surface> <verb> [flags]` | public | 不要把脚本、runbook 或手写 shell 当成正式 CLI |
| 任务入口（Task Entry） | 面向 Agent 的正式任务语言，表达"下一步要做什么"，而不是底层对象 CRUD | internal | 不要把 task-entry 暴露成新用户必须理解的概念 |
| 工作流（Workflow） | 跨多个对象或多个阶段的正式编排动作 | internal | — |
| 执行闭环（Execution Loop） | Plan → Apply → Verify → 记录 → 刷新台账 → 同步文档 | internal | — |

---

## 第六层：证据状态层

回答的问题：**如何证明操作做过、做对了、可追溯？**

| 中文名（English Name） | 一句话定义 | 状态 | 避免误用 |
|------------------------|-----------|------|---------|
| 状态清单（Inventory） | AgentPlane 保存的结构化声明和状态摘要，记录某个 target 受管对象有哪些 | internal | 不要让人手维护 inventory 作为事实；它应由正式流程刷新 |
| 验证记录（Ledger） | 围绕对象或操作生成的机器派生验证记录 | internal | 不要把 ledger 当成用户需要直接编辑的文档 |
| 状态投影（Projection） | 从 live state、inventory、ledger 等来源派生出的状态视图或摘要 | internal | 不要把 projection 作为新用户主线概念 |
| 应用摘要（App Summary） | 面向人类的当前状况摘要 | internal | — |
| 操作凭证（Operation Receipt） | 一次正式操作完成后给人类阅读的结构化摘要 | internal | 当前不要求新用户理解模板字段 |
| 异常复盘（Exception Review） | 失败、紧急绕过、回滚、审批拒绝后的复盘记录 | internal | — |

---

## 协作治理（internal，跨层纵向）

回答的问题：**人、AI、文档、测试、规范如何协同，避免项目跑偏？**

本组不是某一特定层，而是贯穿六层的规则体系。

| 中文名（English Name） | 一句话定义 | 状态 | 避免误用 |
|------------------------|-----------|------|---------|
| 主线机制（Mainline Mechanism） | 当前阶段必须完成的唯一目标，所有工作围绕主线推进 | internal | 不进入 README 前台叙事 |
| 阶段门（Stage Gate） | 长期推进决策的人类确认点 | internal | — |
| 审批门禁（Approval Gate） | 单次高风险操作的执行前确认 | internal | — |
| 人机协作协议（Human-AI Collaboration Protocol） | 人与 AI 的协作规则，包括意图表达、任务归属、进度追踪 | internal | — |
| 主 Agent（Main Agent） | 接受人类意图、负责阶段门和整体进度的 Agent | internal | — |
| 子 Agent（Sub Agent） | 由主 Agent 派遣，执行有限范围具体任务的 Agent | internal | — |
| 配置中心（Config Center） | Git 中的权威状态定义，回答"我们期望系统应该是什么样" | internal | — |

---

## 补充术语

以下术语不属于分层模型的核心对象，但需要在术语表中定义。

### 底层平台

| 中文名（English Name） | 一句话定义 | 状态 | 避免误用 |
|------------------------|-----------|------|---------|
| 底层平台（Substrate） | 被 AgentPlane 管理的底层基础设施平台（如 1Panel、Docker Compose） | internal | — |
| 适配层（Provider） | 封装外部平台 API 的适配层，让上层代码不用关心底层细节 | internal | — |
| 运行时适配器（Adapter） | 处理运行时环境差异的适配器（如 docker_runtime、systemd_runtime） | internal | — |

### 未来机制

| 中文名（English Name） | 一句话定义 | 状态 | 避免误用 |
|------------------------|-----------|------|---------|
| 项目资产总表（Project Registry） | 未来可能用于统一管理多个产品/项目、应用仓库、文档站、服务组件的总表 | future | 当前不建设 schema，不作为验收口径，不替代 app catalog |
| 项目复用模板（Blueprint） | 未来用于沉淀同类项目创建、接入、交付经验的复用模板 | future | 当前不创建正式 blueprint 文件，不作为当前主线 |
| 应用索引（App Catalog） | 已进入正式 app delivery 执行面的应用索引 | internal | — |

---

## 📖 如何使用本表

- **遇到不熟悉的术语**：先查本表，再点击对应层的关联文档深入了解
- **新增术语**：必须先在本表定义，再在其他文档引用
- **术语冲突**：以本表为准，其他文档中的定义应与本表一致
- **判断术语状态**：`public` 可出现在 README 和入门文档；`internal` 只在架构和 reference 文档出现；`future` 不作为当前建设项

---

## 🔗 关联文档

- [控制面核心合同](../architecture/control-plane.md) — 控制面对象与任务入口的详细定义
- [入门指南](../getting-started/getting-started.md) — 面向人类的概念解释
- [愿景](../strategy/vision.md) — 用户对象与产品/项目定位
