---
status: archived
owner: AgentPlane maintainers
last_verified: 2026-05-01
audience: both
---

# AgentPlane 愿景

结论：AgentPlane 是"给 Agent 的产品全生命周期控制面"，帮助个人开发者和小团队安全地管理产品从创建到运维的全过程。

---

## 一句话愿景

**给 Agent 的产品全生命周期控制面**

---

## 目标用户

| 用户类型 | 共同特点 |
|----------|----------|
| 个人开发者、小团队（2-10 人）、开源维护者、自托管服务维护者 | 资源有限、需要自动化、安全可控、可追溯 |

---

## 非目标

| 不做什么 | 理由 |
|----------|------|
| 替代 Terraform/Kubernetes/Ansible | 范围不同，AgentPlane 偏 Agent 任务入口和证据 |
| 大型企业多租户 | 目标用户是小团队和个人 |
| SaaS / 通用 Agent 框架 | 保持可 fork、聚焦产品生命周期 |
| 业务开发（代码编写、审查） | 这是人类的工作 |

---

## 产品/项目模型

AgentPlane 帮助用户管理的产品/项目（Product/Project）结构如下：

```text
产品/项目（Product / Project）
├── 业务系统（Business System）
│   └── 应用（Application / App）
├── 业务系统（Business System）
│   └── 应用（Application / App）
└── 全局配置（Global Config）
```

- **产品/项目**：用户希望 AgentPlane 帮助管理的完整单元
- **业务系统**：产品中的业务功能单元，可包含多个应用
- **应用**：可被构建、部署、验证、回滚的业务应用
- **全局配置**：作用于整个产品的配置（域名策略、网络约束等）

每个应用对应一个**应用项目**（Application Project）仓库，通过**应用交付合同**（Application Delivery Contract，`deploy/agentplane/contract.yaml`）与 AgentPlane 交接。

> 术语定义见 [核心术语表](../reference/glossary.md)。

## 核心价值

Agent 安全管理产品全生命周期——所有正式动作收口到 `agentplane ...`，输出结构化证据，遵循 plan → apply → verify → record 闭环。

---

## 约束

| 维度 | 约束 |
|------|------|
| 维护者 | 单人、业余时间 |
| 技术栈 | Python 3.12+、PyYAML>=6.0、uv |
| 设计 | CLI-first、Agent-first、可 fork、离线优先 |

---

## 关联文档

- [原则](principles.md) — 哲学和工程原则
- [路线图](roadmap.md) — 三阶段推进
- [决策记录](decisions/) — 关键决策追溯
- [核心术语表](../reference/glossary.md) — 唯一术语真源
