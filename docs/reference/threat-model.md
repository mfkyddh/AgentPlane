---
status: active
owner: AgentPlane maintainers
last_verified: 2026-04-29
superseded_by: null
audience: agent
layer: engineering
---

# AgentPlane 威胁模型

结论：本文档是 AgentPlane 运行中可能出什么事的分类框架，不是安全审计报告。威胁模型的目标是帮助 Agent 和人类识别风险类别、触发条件和缓解措施，而不是提供安全工具或运行时保护。

首轮只覆盖三类威胁：意外破坏、越权操作、状态漂移。不覆盖网络攻击、认证绕过、数据泄露——这些是基础设施安全，不是控制面安全。

## 🧠 分类框架

| # | 威胁类别 | 定义 | 影响对象 |
| --- | --- | --- | --- |
| T1 | 意外破坏 | Agent 在未被警告的情况下破坏了受管状态或真源 | inventory、ledger、tracked 文件 |
| T2 | 越权操作 | Agent 执行了人类未显式授权的高风险动作 | 目标主机、应用服务、生产数据 |
| T3 | 状态漂移 | 多个 Agent 或多次执行对同一对象持有不同理解，导致操作基于过期或冲突状态 | inventory、ledger、workbook 任务状态 |

## ⚠️ T1：意外破坏

### 定义

Agent 在执行写操作时，未正确获取锁、未验证前置条件、或错误地覆盖了并发修改的结果，导致受管状态损坏。

### 触发条件

| 场景 | 触发条件 | 风险等级 |
| --- | --- | --- |
| 并发写 inventory | 两个 Agent 同时修改同一 `inventory.json` | high |
| 未验证即写回 | Agent 跳过现场验证直接写回 ledger | medium |
| 错误覆盖 tracked 文件 | Agent 用本地快照覆盖了远程已更新的文件 | high |
| Git 冲突未处理 | Agent 在有未提交变更时直接写入并提交 | medium |

### 现有缓解

| 缓解措施 | 覆盖场景 | 缺口 |
| --- | --- | --- |
| 无（当前无文件锁） | — | 并发写无防护 |
| `repo status` 检查脏工作区 | Git 冲突未处理 | 只检测，不阻止 |
| `--dry-run` 模式 | 非预期写回 | 依赖 Agent 自律使用 |

### P6 要补的

1. **文件级锁规则定义**（详见 [concurrency-and-approval.md](concurrency-and-approval.md)）：锁粒度、锁获取/释放规则、锁失败处理
2. **写前验证规则**：写回 inventory / ledger 前必须运行现场验证（`live state` 优先级最高）
3. **脏工作区强制暂停**：`git status --short` 非空时，高风险写操作必须暂停并说明

## ⚠️ T2：越权操作

### 定义

Agent 执行了人类未显式授权的高风险动作。包括：未经审批修改生产配置、在错误 target 上执行、超出任务书授权范围的动作。

### 触发条件

| 场景 | 触发条件 | 风险等级 |
| --- | --- | --- |
| 高风险命令无审批 | Agent 直接执行 deploy、rollback、fixture apply 等 | high |
| target 选错 | Agent 把生产 target 当成 staging 执行 | high |
| Skill 绕过 CLI | Skill 直接拼 SSH / Docker 命令，跳过 `agentplane ...` 审批链 | high |
| 阶段门未确认即执行 | Agent 在阶段状态为 `planned` 或 `discussion-required` 时直接拆任务并执行 | medium |

### 现有缓解

| 缓解措施 | 覆盖场景 | 缺口 |
| --- | --- | --- |
| `--dry-run` / `--execute` 二元开关 | 高风险命令无审批 | 不强制，依赖 Agent 使用 |
| 阶段门（workbook） | 阶段门未确认即执行 | 只约束 Agent 自律，无运行时强制 |
| AGENTS.md 规则 | Skill 绕过 CLI | 只约束，不执行 |

### P6 要补的

1. **审批门禁概念模型**（详见 [concurrency-and-approval.md](concurrency-and-approval.md)）：高风险操作分类、审批触发条件、`--execute --approve` 扩展方案
2. **阶段门运行时检查**：`agentplane` CLI 在阶段状态未 `approved` 时拒绝执行高风险命令（远期实现）
3. **Skill 路由审计规则**：Skill 不得直接执行 SSH / Docker / API 调用，必须路由到 `agentplane ...`（已在 AGENTS.md，P6 强化检查）

## ⚠️ T3：状态漂移

### 定义

多个 Agent 或同个 Agent 的多次执行，对同一对象（target、app、service）持有不同理解，导致后续操作基于过期或冲突的状态进行。

### 触发条件

| 场景 | 触发条件 | 风险等级 |
| --- | --- | --- |
| 主/子 Agent 状态不同步 | 主 Agent 派遣子 Agent 后，子 Agent 修改了状态但主 Agent 未感知 | medium |
| inventory 缓存过期 | Agent 使用本地缓存的 inventory，而远程已更新 | medium |
| 多轮对话状态丢失 | Agent 新会话未正确恢复上下文，基于过期 workbook 状态推进 | high |
| ledger 未刷新 | Agent 基于过期 ledger 做决策 | low |

### 现有缓解

| 缓解措施 | 覆盖场景 | 缺口 |
| --- | --- | --- |
| 继续执行协议（workbook P1） | 多轮对话状态丢失 | 依赖 Agent 遵守协议 |
| `repo status` 检查 `ledger_updated` | ledger 未刷新 | 只提示，不阻止 |
| Operation Receipt | 部分（有 Receipt 时可追溯） | P2 定义但未强制所有任务产生 Receipt |

### P6 要补的

1. **Agent ID 传递规则**：主/子 Agent 身份标识、操作归属、Receipt 中 `agent_id` 字段定义
2. **状态刷新强制规则**：高风险操作前必须重新读取 inventory / ledger 真源，不得使用缓存
3. **继续执行协议增强**：`git status --short` 检查 + `repo status` 检查作为恢复的强制第一步（已在 P1，P6 明确写入威胁缓解）

## 📊 威胁等级定义

| 等级 | 含义 | 响应要求 |
| --- | --- | --- |
| `high` | 可能导致数据损坏、生产中断或不可恢复状态 | 必须有缓解措施，执行前必须审批 |
| `medium` | 可能导致错误操作或需要人工修正 | 建议有缓解措施，执行前应提示 |
| `low` | 信息性风险，不影响核心状态 | 面板展示即可，不阻塞执行 |

## 🔗 与风险推导的关系

本文档定义的威胁类别，直接映射到 `agentplane repo status` 中 `risks[]` 的推导规则：

| 威胁类别 | risks[].kind | 推导来源 |
| --- | --- | --- |
| T1 意外破坏 | `dirty_worktree`（间接） | `git status --short` |
| T2 越权操作 | `discussion_required` / `blocked_phase` | workbook 阶段状态 |
| T3 状态漂移 | `stale_data` | `ledger_updated` 超过 30 天 |

> 威胁模型是**分类框架**，风险推导是**运行时检测**。前者定义"可能出什么事"，后者定义"如何发现它正在发生"。

## 🚫 不覆盖的范围

以下主题属于基础设施安全或网络安全，不在 AgentPlane 控制面威胁模型范围内：

| 不覆盖 | 原因 |
| --- | --- |
| 网络攻击（DDoS、入侵、提权） | 属于主机/网络安全，AgentPlane 不直接处理 |
| 认证绕过（token 泄露、SSH 密钥泄露） | 属于 secrets 管理，已有 `secrets/` 目录隔离 |
| 数据泄露（inventory 敏感信息暴露） | 属于数据安全，AgentPlane 原则是不将敏感信息写入 tracked 文件 |
| 依赖库漏洞 | 属于供应链安全，由 `uv` / `pip-audit` 等工具处理 |

## 📋 后续计划

| 计划 | 内容 | 阶段 |
| --- | --- | --- |
| 规则定义 | 本文档已完成三类威胁的分类框架定义 | P6 |
| 锁机制实现 | 文件级锁的跨平台实现（首选 `filelock` 库） | 后续阶段 |
| 审批门禁实现 | `--execute --approve` 的 CLI 扩展 | 后续阶段 |
| Agent ID 落地 | Operation Receipt 增加 `agent_id` 字段 | 后续阶段 |
| 威胁检测增强 | `repo status` 中增加更多威胁检测维度 | 后续阶段 |
