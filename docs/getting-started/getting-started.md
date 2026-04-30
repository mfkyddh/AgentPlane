---
status: active
owner: AgentPlane maintainers
last_verified: 2026-04-30
superseded_by: null
audience: human
---

# 🧭 AgentPlane 入门指南

结论：AgentPlane 是一套让 AI 安全接管基础设施的"遥控器"系统。你下指令，AI 先匹配 Skill，再通过 `agentplane ...` 执行，全程有计划、有验证、有记录。

---

## 😰 问题

让 AI 直接执行 `ssh prod "docker restart myapp"`——没有计划、没有验证、没有记录、没有回滚。

## ✅ AgentPlane 的做法

所有操作通过 `agentplane ...` 标准化入口执行，每个入口自动完成：

```
检查依赖 → 执行操作 → 验证结果 → 留下记录
```

核心理念：**配置中心**（Git 中的权威定义）vs **现场状态**（服务器实际运行）。AgentPlane 持续对比两者，发现不一致时及时报告。

---

## 🤖 AI 是怎么工作的？

当你对 AI 说"把 sub2api 部署到 prod0-main"，AI 会执行：

```
理解意图 → 匹配 Skill → 制定计划 → 向你确认 → 执行 → 验证 → 记录 → 汇报
```

**关键步骤**：

| 步骤 | 做什么 | 谁在做 |
|------|--------|--------|
| 理解意图 | 把自然语言翻译成结构化意图（目标、环境、版本、约束） | AI |
| 匹配 Skill | 从 `.agents/skills` 选择能力入口 | AI |
| 制定计划 | 生成具体 CLI 命令序列 | AI |
| **确认计划** | 审核计划，同意或调整 | **人类** |
| 执行操作 | 加 `--execute` 真正执行 | AI |
| 验证结果 | 运行验证命令，检查容器、健康检查、公网入口 | AI |
| 留下记录 | 写入操作日志、刷新台账、更新文档 | AI |
| 向你汇报 | 给你人类可读的摘要 | AI |

> 📌 **人类在两个点必须介入**：确认计划（第 4 步）和验收结果（第 8 步）。其他步骤 AI 自主完成。

---

## 🎯 核心概念速查

| 概念 | 含义 |
|------|------|
| **配置中心** | Git 中的权威状态定义，回答"我们期望系统应该是什么样" |
| **Skill** | AI Agent 的意图入口，把自然语言路由到正式 CLI |
| **执行闭环** | Plan → Apply → Verify → 记录 → 刷新台账 → 同步文档 |
| **三层投影** | Inventory（声明）→ Ledger（证据）→ Summary（摘要） |

**Skill 路由示例**：

| 你说 | AI 选择的 Skill |
|------|-----------------|
| "部署一个应用" | `app-delivery-ops` → `agentplane app delivery ...` |
| "检查服务状态" | `agentplane-service-ops` → `agentplane service ...` |
| "纳管新主机" | `host-onboarding-ops` → `agentplane bootstrap ...` |

详细概念见 [术语表](../reference/glossary.md) 和 [架构概览](architecture-overview.md)。

---

## 👥 人类与 AI 的分工

| 责任 | 人类 | AI |
|------|:---:|:---:|
| 定目标、定约束 | ✅ | ❌ |
| 制定计划、选择 Skill | ❌ | ✅ |
| **确认计划** | ✅ | ❌ |
| 执行、验证、记录 | ❌ | ✅ |
| **验收** | ✅ | ❌ |

> ⚠️ 高风险操作（生产切换、证书变更、数据迁移）时人类必须介入。任何时候你都可以说"停"。

---

## 🧭 怎么跟 AI 协作？

**你用自然语言表达意图，AI 自主推进全部实施工作。** 你不需要记命令、写代码或管 git。

项目有一条**主线**（当前阶段必须完成的三件事）。你提的需求，AI 自动判断归属：

| 你说 | AI 会做 |
|------|--------|
| "继续推进主线" | 从上次停下的地方继续 |
| "帮我部署这个应用" | 匹配 Skill，执行部署 |
| "我有个新想法" | 评估归属，安排执行或记录到 backlog |
| "停" | 立即停止 |

AI 使用 `docs/project/backlog.md` 追踪主线进度，每次会话开始会告诉你当前位置。详细规则见 [人机协作协议](../reference/human-ai-collaboration.md)。

---

## 🚀 下一步：动手试试

### 体检你的环境

```bash
# 1. 检查本地环境
agentplane bootstrap inspect-local --repo-root .

# 2. 运行诊断
agentplane bootstrap doctor --repo-root .

# 3. 初始化 secrets
agentplane bootstrap init-secrets --repo-root .

# 4. 验证 secrets
agentplane bootstrap verify-secrets --repo-root .
```

### 查看项目状态

```bash
# 生成状态报告
agentplane repo status --repo-root . --html tmp/agentplane-status.html

# 运行健康检查
agentplane repo health-check --repo-root .
```

### 更多资源

- **想上手部署？** → [应用交付流程](../runbooks/app-project-delivery-workflow.md)
- **想了解 AI 执行规范？** → [AI 执行闭环](../runbooks/control-plane-agent-execution-flow.md)
- **想深入架构设计？** → [控制面核心合同](../architecture/control-plane.md)
- **想知道当前状态？** → [状态与验证](../runbooks/current-state-and-validation.md)
- **想看术语定义？** → [术语表](../reference/glossary.md)

---

## 🔗 关联文档

- [AGENTS.md](../../AGENTS.md) — AI 的完整工作规范
- [Skill 盘点](../history/skill-surface-audit.md) — 历史 Skill 能力面快照
- [愿景](../strategy/vision.md) — AgentPlane 的边界和适用场景
