---
status: active
owner: AgentPlane maintainers
last_verified: 2026-04-30
superseded_by: null
audience: both
---

# AgentPlane 文档地图

结论：🧭 按阅读顺序组织的文档导航。第一次阅读走入门路线；执行任务时按 runbook；维护规范时看 reference。

---

## 🧭 1. 入门路线

| 阶段 | 文档 | 说明 |
|------|------|------|
| 1 | [入门指南](getting-started/getting-started.md) | 安装、体检、第一次使用 |
| 2 | [架构概览](getting-started/architecture-overview.md) | 一句话理解 + 投影模型 |
| 3 | [部署第一个应用](tutorials/deploy-first-app.md) | 动手教程 |
| 4 | [人机协作协议](reference/human-ai-collaboration.md) | 怎么跟 AI 协作 |

---

## 🎯 2. 战略与方向

| 文档 | 说明 |
|------|------|
| [愿景](strategy/vision.md) | 是什么、解决什么、不做什么、约束、干系人 |
| [原则](strategy/principles.md) | 哲学基座、方法论、工程原则 |
| [路线图](strategy/roadmap.md) | 三阶段推进、里程碑、长期机制 |
| [决策记录](strategy/decisions/) | 为什么这样做 |

---

## 📋 3. 项目管理

| 文档 | 说明 |
|------|------|
| [主线追踪器](project/backlog.md) | 当前任务进度、分支任务 |

---

## 🧠 4. 架构

| 文档 | 说明 |
|------|------|
| [控制面合同](architecture/control-plane.md) | 核心架构：task-entry、配置中心 |
| [协作边界](architecture/agentplane-app-collaboration.md) | 控制面与应用仓库的边界 |
| [Linux 治理](architecture/linux-governance.md) | Linux / WSL backend 治理 |
| [架构决策](architecture/decisions/) | 长期架构决策记录 |
| [架构目录索引](architecture/README.md) | 架构文档导航 |

---

## 🛠️ 5. 工程规范

### 🧪 代码与流程

| 文档 | 说明 |
|------|------|
| [代码风格](reference/code-style.md) | 代码和文档风格基线 |
| [Git 规范](reference/git-conventions.md) | 提交、分支、合并规则 |
| [测试架构](reference/testing-architecture.md) | 测试分层和 marker 规范 |
| [测试规范](reference/testing-conventions.md) | marker、并行、文件组织、本地工作流 |
| [发布流程](reference/release-process.md) | 发布和健康检查 |

### 📌 仓库与文档

| 文档 | 说明 |
|------|------|
| [仓库结构](reference/repository-structure.md) | 顶层目录和新文件放置规则 |
| [文档治理](reference/documentation-governance.md) | frontmatter、emoji、链接和门禁 |
| [四层文档体系](reference/documentation-layers.md) | 文档分层、审查节奏 |
| [术语表](reference/glossary.md) | 核心术语统一定义 |

### 🔧 平台与基础设施

| 文档 | 说明 |
|------|------|
| [技术栈约束](reference/tech-stack.md) | Python、uv、Ruff 等技术选型 |
| [跨平台规范](reference/cross-platform.md) | Windows / WSL / Linux 规则 |
| [容器规范](reference/container-conventions.md) | Docker Compose、容器命名、打包规范 |
| [命名注册表](reference/control-plane-naming-registry.md) | app_id、容器名、路径策略 |

### 🔐 安全与开源

| 文档 | 说明 |
|------|------|
| [威胁模型](reference/threat-model.md) | 安全威胁分析 |
| [开源准备度](reference/open-source-readiness.md) | 开源前检查清单、公开边界 |

### 🚀 应用交付

| 文档 | 说明 |
|------|------|
| [App Runtime 拆分](reference/app-runtime-decomposition.md) | App runtime 拆分路线 |
| [公开 Schema](reference/schemas/README.md) | 公开合同 schema 索引 |

---

## 📦 6. 运维手册

完整列表和按场景分类见 [Runbook 导航](runbooks/README.md)。

| 文档 | 说明 |
|------|------|
| [应用交付流程](runbooks/app-project-delivery-workflow.md) | 应用接入与交付主路径 |
| [Agent 执行闭环](runbooks/control-plane-agent-execution-flow.md) | 执行 → 验证 → 记录 |
| [Secrets 引导](runbooks/bootstrap-secrets.md) | secrets 初始化 |
| [WSL 治理](runbooks/wsl-host-governance.md) | WSL 主机治理 |
| [当前状态](runbooks/current-state-and-validation.md) | 状态和验证快照 |

---

## 🤖 7. 维护者

| 文档 | 说明 |
|------|------|
| [Control Plane Authoring](maintainers/control-plane-authoring.md) | 控制面编写规则 |
| [Roadmap Workbook](maintainers/agentplane-roadmap-workbook.md) | 阶段推进、任务状态追踪 |

---

## 🕰️ 8. 历史与归档

| 文档 | 说明 |
|------|------|
| [历史材料](history/index.md) | 退出主线的审计材料 |
| [归档文档](archive/README.md) | 退役文档、旧 runbook |

---

## 🚀 9. 教程

| 文档 | 说明 |
|------|------|
| [部署第一个应用](tutorials/deploy-first-app.md) | 从零部署 sub2api |
| [排查部署失败](tutorials/troubleshoot-failed-deployment.md) | 常见错误和排查思路 |
| [添加新服务器](tutorials/add-new-server.md) | 纳管新服务器 |

---

## 🤖 10. AI 入口

| 文档 | 说明 |
|------|------|
| [AGENTS.md](../AGENTS.md) | AI 工作规范 |
| [控制面合同](architecture/control-plane.md) | 正式执行合同 |
| [Agent 执行闭环](runbooks/control-plane-agent-execution-flow.md) | 执行流程 |
| [命名注册表](reference/control-plane-naming-registry.md) | 对象命名规则 |

---

## ✅ 11. 文档门禁

> 📌 新增或移动文档后必须运行以下命令，CI 会检查。

```bash
uv run python -m agentplane.cli repo docs-sanity --repo-root .
uv run python -m agentplane.cli repo skills check --repo-root .
uv run python -m agentplane.cli repo status --repo-root . --html tmp/agentplane-status.html
uv run python -m agentplane.cli repo privacy-scan --repo-root .
```
