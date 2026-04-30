---
status: active
owner: AgentPlane maintainers
last_verified: 2026-04-29
superseded_by: null
audience: agent
layer: engineering
---

# AgentPlane 子 Agent 协作边界

结论：本文档定义 AgentPlane 中"主 Agent 派遣子 Agent 执行子任务"的协作模型。首轮只定义规则和边界，不实现运行时机制。多人各自 Agent 或并发 Agent 不在本文档范围内。

## 核心概念

| 概念 | 含义 | 职责 |
| --- | --- | --- |
| 主 Agent | 接受人类意图、负责阶段门和整体进度的 Agent | 派遣、收口、回写 |
| 子 Agent | 由主 Agent 派遣，执行有限范围具体任务的 Agent | 执行、回传、不回写 |
| 委托边界 | 主 Agent 授权子 Agent 可操作的对象和命令范围 | 权限隔离 |
| 收口点 | 子 Agent 完成后，主 Agent 验证结果并决定是否回写的决策点 | 人类兜底 |

## 派遣模型

### 派遣触发条件

主 Agent 只能在以下条件下派遣子 Agent：

| # | 条件 | 示例 |
| --- | --- | --- |
| 1 | 任务可独立拆分，子任务之间无顺序依赖 | P6-T1、P6-T2、P6-T3 互不依赖 |
| 2 | 子任务有明确的可验证完成标准 | "文档写入完成且 docs-sanity ok" |
| 3 | 主 Agent 能在收口点验证子 Agent 的输出 | 子 Agent 返回结构化结果 |

不满足以上条件时，主 Agent 应串行执行，不得派遣。

### 派遣协议

派遣时必须向子 Agent 传递：

```
{
  "task_id": "<阶段任务 ID，如 P6-T2>",
  "task_description": "<具体任务描述>",
  "allowed_scopes": ["<允许操作的文件/对象列表>"],
  "forbidden_scopes": ["<明确禁止的操作>"],
  "verification_criteria": "<完成验证标准>",
  "agent_id": "<子 Agent 标识，用于 Receipt 回写>"
}
```

## 权限委托边界

### 子 Agent 允许的操作

| 操作类别 | 是否允许 | 条件 |
| --- | --- | --- |
| 读取文件 | ✅ | 不限 |
| 写入指定文件 | ✅ | 必须在 `allowed_scopes` 内 |
| 执行 `agentplane ...` 只读命令 | ✅ | 如 `repo status`、`skills check` |
| 执行 `agentplane ...` 写命令 | ⚠️ | 必须主 Agent 显式授权，且为低风险 |
| 修改 workbook 阶段/任务状态 | ❌ | 只能由主 Agent 回写 |
| `git commit` / `git push` | ❌ | 只能由主 Agent 执行 |
| 修改 `AGENTS.md`、`control-plane.md` 等核心合同 | ❌ | 必须人类确认 |

### 最小权限原则

1. 默认不授权任何写操作。
2. 必须写操作时，显式列出允许的文件路径，不得通配。
3. 高风险命令（`deploy`、`rollback`、`fixture apply`）一律不得委托给子 Agent。

## 结果回传规则

### 回传内容

子 Agent 完成后必须向主 Agent 回传：

| 字段 | 含义 | 必填 |
| --- | --- | --- |
| `task_id` | 对应的任务 ID | ✅ |
| `status` | `success` / `partial` / `failed` | ✅ |
| `summary` | 人类可读的执行摘要 | ✅ |
| `evidence` | 验证证据（如 docs-sanity 输出、测试通过证明） | ✅ |
| `files_changed` | 修改的文件列表 | 当有写操作时必填 |
| `agent_id` | 子 Agent 标识 | ✅ |

### 主 Agent 收口职责

主 Agent 收到子 Agent 回传后，必须：

1. **验证 evidence**：不信任子 Agent 的 `status` 声明，独立运行验证命令
2. **检查 `files_changed`**：确认修改范围未超出 `allowed_scopes`
3. **决定是否回写**：只有验证通过后，主 Agent 才回写 workbook 任务状态
4. **处理失败**：子 Agent 失败时，主 Agent 必须向人类报告，不得自动重试或绕过

## 禁止行为

以下行为在任何情况下都禁止：

| # | 禁止行为 | 原因 |
| --- | --- | --- |
| 1 | 子 Agent 自行 `git commit` 或回写 workbook | 破坏主 Agent 的收口权 |
| 2 | 子 Agent 修改非授权文件 | 权限逃逸 |
| 3 | 主 Agent 在未验证 evidence 的情况下回写状态 | 状态造假 |
| 4 | 子 Agent 派遣子 Agent（嵌套派遣） | 权限链不可追溯 |
| 5 | 子 Agent 修改 `secrets/` 目录或读取敏感信息 | 安全风险 |
| 6 | 多个子 Agent 同时写同一文件且无协调 | 意外破坏（T1 威胁） |

## 与威胁模型的关系

本文档定义的协作边界，直接缓解威胁模型中的两类威胁：

| 威胁 | 缓解措施 |
| --- | --- |
| T2 越权操作 | 权限委托边界 + 禁止行为表 |
| T3 状态漂移 | 结果回传 + 主 Agent 收口验证 |

T1 意外破坏的缓解（文件锁）在 [concurrency-and-approval.md](concurrency-and-approval.md) 中定义。

## 远期扩展

以下能力首轮只定义概念，不实现：

| 扩展 | 说明 | 触发条件 |
| --- | --- | --- |
| Agent ID 正式化 | Operation Receipt 增加 `agent_id` 字段 | 需要追溯多 Agent 操作历史时 |
| 嵌套派遣审批 | 主 Agent 申请派遣子 Agent 时需人类审批 | 子任务风险评级为 `high` 时 |
| 子 Agent 超时回收 | 子 Agent 超过设定时间未回传，主 Agent 自动回收 | 需要生产级稳定性时 |

## 相关文档

- [威胁模型](threat-model.md)
- [锁规则与审批边界](concurrency-and-approval.md)（待创建）
- [阶段工作计划](../maintainers/agentplane-roadmap-workbook.md)
- [Operation Receipt 模板](../maintainers/agentplane-roadmap-workbook.md#operation-receipt-模板)
