# Control Plane Domain Onboarding

## 目的

本文定义新控制面领域接入 Agent-first 模板仓库的正式流程，确保新增领域不会绕开统一 CLI、skill、runbook、inventory 与测试合同。

## 适用范围

适用于任何新增或重构中的控制面领域，例如：

- 新的基础设施服务
- 新的网站入口治理域
- 新的应用资源域
- 新的应用交付子域

## 开场规则

- 先跑 `agentplane bootstrap inspect-local --repo-root <repo-root>`，确认当前 control root、workspace binding 与 backend 绑定。
- 如果是 fresh fork，再补 `bootstrap verify-secrets` 或 `bootstrap doctor`，确认 humans 只需要填 `secrets` 与少量 `identity`。
- 领域设计只写 formal CLI、skill、runbook 与测试合同，不写第二控制面脚本。

## 接入顺序

### 1. 定义对象与任务

长期边界统一看 [control-plane.md 的 Task-Entry Model](../architecture/control-plane.md#task-entry-model)。

先明确：

- 稳定 `object` 是什么
- 面向 Agent 的 `task-entry` 是什么
- 哪些动作属于对象域
- 哪些动作属于工作流域
- 哪些差异必须留在 `resolver / backend` 层

### 2. 定义 CLI 合同

正式命令面统一遵循 [control-plane.md 的 CLI Contract](../architecture/control-plane.md#cli-contract)。

至少明确：

- 命令路径
- 输入参数与 `<repo-root>` / `<target>` / `<app>` 占位符
- 输出 envelope
- 计划阶段
- 验证阶段

### 3. 定义 skill 路由

长期边界看 [control-plane.md 的 Principles](../architecture/control-plane.md#principles) 与 [Required Rules](../architecture/control-plane.md#required-rules)；maintainer 写法、分层和联动规则统一遵循 [../maintainers/control-plane-authoring.md](../maintainers/control-plane-authoring.md)。

至少补齐：

- 该域 skill 的触发条件
- 标准命令
- 最小验证
- `inventory / ledger` 对齐要求
- 下钻 runbook

### 4. 定义 runbook

至少补齐：

- 前置条件
- 风险边界
- 正式执行顺序
- 人工接力点

### 5. 定义 inventory / ledger 落点

长期投影规则统一看 [control-plane.md 的 Inventory And Ledger Projection](../architecture/control-plane.md#inventory-and-ledger-projection)。

明确：

- 是否需要新增对象 ledger
- 是否需要刷新 `inventory`
- 是否需要回写应用摘要或主机摘要

### 6. 定义测试与示例

至少补齐：

- CLI 合同测试
- 文档入口或引用测试
- 最小成功示例
- 典型失败示例

## 最小检查清单

新域接入完成前，应能回答：

1. 正式入口是什么？
2. 是否还存在历史旁路？如果存在，退役目标是什么？
3. skill 如何路由到正式入口？
4. runbook 如何解释流程而不变成第二实现？
5. 写后验证怎么做？
6. `ledger` 或 `inventory` 如何回写？

## 最小命令示例

```bash
agentplane --help
agentplane bootstrap inspect-local --repo-root <repo-root>
agentplane infra inventory <target> --repo-root <repo-root>
```

## 禁止事项

1. 不要只新增脚本，不新增正式 CLI。
2. 不要只写 runbook，不定义输出与验证合同。
3. 不要让 skill 直接路由到兼容脚本作为主路径。
4. 不要省略 `inventory` 或 `ledger` 对齐设计。

## 关联文档

- [../architecture/control-plane.md](../architecture/control-plane.md)
- [../architecture/control-plane.md#cli-contract](../architecture/control-plane.md#cli-contract)
- [../architecture/control-plane.md#task-entry-model](../architecture/control-plane.md#task-entry-model)
- [../architecture/control-plane.md#inventory-and-ledger-projection](../architecture/control-plane.md#inventory-and-ledger-projection)
- [../maintainers/control-plane-authoring.md](../maintainers/control-plane-authoring.md)
