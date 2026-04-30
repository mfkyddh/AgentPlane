---
status: active
owner: AgentPlane maintainers
last_verified: 2026-04-29
superseded_by: null
audience: both
layer: technical
---

# 架构决策记录

结论：本目录记录会长期影响 AgentPlane 代码、文档、测试和公开协作方式的架构决策。短期操作步骤仍放在 runbook。

## 决策列表

| ADR | 状态 | 主题 |
| --- | --- | --- |
| [0001-cli-first-control-plane.md](0001-cli-first-control-plane.md) | accepted | 使用 CLI-first 控制面，而不是脚本集合或托管平台。 |

## 新 ADR 触发条件

- 引入新的生产依赖或工具链。
- 改变公开 CLI 合同、schema 或输出 envelope。
- 新增 provider 或改变 provider 与 domain 的边界。
- 调整公开仓库与本地私有材料边界。
- 改变测试、CI、发布或安全门禁的默认策略。

