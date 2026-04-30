---
status: active
owner: AgentPlane maintainers
last_verified: 2026-04-30
superseded_by: null
audience: both
---

# 📖 核心术语表

结论：本文集中定义 AgentPlane 中的核心术语，避免概念分散和重复定义。遇到不熟悉的术语时，请先查阅本表。

---

## 控制面核心

| 术语 | 一句话定义 | 详细说明 |
|------|-----------|----------|
| **object** | 控制面中的稳定对象，如 `infra`、`app`、`service`、`ingress` | [控制面合同](../architecture/control-plane.md) |
| **task-entry** | 面向 Agent 的正式任务入口，不等价于底层对象 CRUD | [控制面合同](../architecture/control-plane.md) |
| **source of truth** | 某一类事实的正式真源（如 Git 配置、inventory、ledger） | [控制面合同](../architecture/control-plane.md) |
| **live state** | 通过现场命令、API、文件读取等方式获得的当前真实状态 | [控制面合同](../architecture/control-plane.md) |
| **配置中心** | Git 中的权威状态定义，回答"我们期望系统应该是什么样" | [入门指南](../getting-started/getting-started.md) |

## 投影与台账

| 术语 | 一句话定义 | 详细说明 |
|------|-----------|----------|
| **inventory** | 目标环境的正式非敏感台账，记录受管对象和摘要状态 | [控制面合同](../architecture/control-plane.md) |
| **ledger** | 围绕某类对象或某次验证生成的机器派生记录 | [控制面合同](../architecture/control-plane.md) |
| **projection** | 从真源派生的只读视图（如 inventory、ledger、app summary） | [控制面合同](../architecture/control-plane.md) |
| **app summary** | 面向应用项目或主机摘要的非敏感结果 | [控制面合同](../architecture/control-plane.md) |

## 执行流程

| 术语 | 一句话定义 | 详细说明 |
|------|-----------|----------|
| **执行闭环** | Plan → Apply → Verify → 记录 → 刷新台账 → 同步文档 | [入门指南](../getting-started/getting-started.md) |
| **Skill** | AI Agent 的意图入口，负责把自然语言路由到正式 CLI | [入门指南](../getting-started/getting-started.md) |
| **标准化入口** | AI 不直接操作底层资源，而是通过 `agentplane ...` 执行任务 | [入门指南](../getting-started/getting-started.md) |

## 底层平台

| 术语 | 一句话定义 | 详细说明 |
|------|-----------|----------|
| **substrate** | 被 AgentPlane 管理的底层基础设施平台（如 1Panel、Docker Compose） | [项目定位](project-positioning.md) |
| **provider** | 封装外部平台 API 的适配层，让上层代码不用关心底层细节 | [项目定位](project-positioning.md) |
| **adapter** | 处理运行时环境差异的适配器（如 docker_runtime、systemd_runtime） | [仓库结构](repository-structure.md) |

## 应用交付

| 术语 | 一句话定义 | 详细说明 |
|------|-----------|----------|
| **contract.yaml** | 应用仓库必须提供的交付合同，描述非敏感交付面 | [协作规范](../architecture/agentplane-app-collaboration.md) |
| **app catalog** | 已进入正式 app delivery 执行面的应用索引 | [Roadmap Workbook](../maintainers/agentplane-roadmap-workbook.md) |
| **blueprint** | 创建或接入同类项目时复用的方法模板 | [终极蓝图](agentplane-ultimate-blueprint.md) |
| **Operation Receipt** | 每次正式任务的人类可读摘要 | [Roadmap Workbook](../maintainers/agentplane-roadmap-workbook.md) |
| **Exception Review** | 失败、紧急绕过、回滚、审批拒绝后的复盘记录 | [Roadmap Workbook](../maintainers/agentplane-roadmap-workbook.md) |

## 安全与协作

| 术语 | 一句话定义 | 详细说明 |
|------|-----------|----------|
| **主 Agent** | 接受人类意图、负责阶段门和整体进度的 Agent | [Agent 协作边界](agent-collaboration.md) |
| **子 Agent** | 由主 Agent 派遣，执行有限范围具体任务的 Agent | [Agent 协作边界](agent-collaboration.md) |
| **阶段门** | 长期推进决策的人类确认点 | [Roadmap Workbook](../maintainers/agentplane-roadmap-workbook.md) |
| **审批门禁** | 单次高风险操作的执行前确认 | [并发与审批](concurrency-and-approval.md) |

---

## 如何使用本表

- **遇到不熟悉的术语**：先查本表，再点击"详细说明"链接深入了解
- **新增术语**：在对应文档中定义后，同步更新本表
- **术语冲突**：以本表为准，其他文档中的定义应与本表一致

---

## 🔗 关联文档

- [控制面核心合同](../architecture/control-plane.md) — 术语的主要定义来源
- [入门指南](../getting-started/getting-started.md) — 面向人类的概念解释
- [文档治理规范](documentation-governance.md) — 文档分层和链接规则
