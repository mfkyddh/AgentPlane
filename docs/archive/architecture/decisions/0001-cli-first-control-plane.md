---
status: archived
owner: AgentPlane maintainers
last_verified: 2026-04-29
superseded_by: null
audience: both
layer: technical
---

# 架构决策 0001：CLI-First 控制面

结论：AgentPlane 采用 CLI-first 控制面。正式能力必须通过 `agentplane ...` 暴露，脚本、provider helper 和 skill 只能作为实现或路由层。

## 📖 背景

AI Agent 可以直接调用 SSH、Docker、云 API 或本地脚本，但这些入口很难统一验证、审计和回写状态。AgentPlane 的目标是让 Agent 操作基础设施时有稳定任务语言，而不是把一次性命令堆成新的控制面。

## 🎯 决策

- 正式入口固定为 `agentplane <domain> <surface> <verb> [flags]`。
- 涉及真实状态变更的命令必须支持计划、显式执行、验证和证据输出。
- skill 和 runbook 只路由到正式 CLI，不复制第二套实现。
- provider/debug 层可以存在，但不能替代业务任务入口。

## 📊 影响

| 方面 | 影响 |
| --- | --- |
| 代码 | 新能力先进入 CLI/domain/runtime 边界，再补文档和 skill。 |
| 文档 | README、runbook 和 skill 必须推荐正式 CLI，而不是脚本路径。 |
| 测试 | CLI 合同测试是公开行为的最低证明。 |
| 开源协作 | 外部贡献者可以通过统一命令和门禁理解项目行为。 |

## ⚖️ 取舍

CLI-first 不如直接脚本快，但它换来稳定输出、统一错误、审计证据和跨平台策略。AgentPlane 优先选择长期可治理性。

