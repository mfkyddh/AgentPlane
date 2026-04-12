# Automation And Projection Responsibility Contract

## 目的

本页是 Phase 4 的单一职责口径：只定义 `automation` 与 `projection` 各自负责什么、何时触发、以及最小闭环顺序。
其他 active runbook 不再重复定义职责边界，只引用本页。

## 边界定义

| 域 | 正式入口 | 负责内容 | 不负责内容 |
| --- | --- | --- | --- |
| Automation | `uv run python -m agentplane.cli host automation ...` | 周期性治理任务的任务真源、调度真源、执行记录检索与人工触发 | 不负责运行时投影刷新，不替代 `app delivery`/`service`/`website` 的业务执行 |
| Projection | `uv run python -m agentplane.cli projection ...` | 现场状态验证、fixture 管理、ledger 刷新与投影回写 | 不负责任务调度，不替代 host automation 的计划与周期执行 |

## 责任协作顺序

标准协作顺序固定为：

1. 先完成业务动作（如 `app delivery`、`service`、`website`）。
2. 需要周期任务时，进入 `host automation` 口径完成调度或触发。
3. 需要状态投影回写时，进入 `projection` 口径完成 `verification`/`ledger` 刷新。
4. 人类摘要与文档同步仅消费投影结果，不反向充当真源。

对应原则：

- Automation 管“何时执行、执行什么周期任务”。
- Projection 管“执行后如何验证并把机器证据写回结构化投影”。
- 两者都不进入 daily thin gate 的强制 live 操作；daily gate 只保留稳定、快速合同测试。

## 最小命令闭环（示例）

```bash
uv run python -m agentplane.cli host automation search <target> --repo-root <repo-root>
uv run python -m agentplane.cli projection verification run --target <target> --profile <profile> --repo-root <repo-root>
uv run python -m agentplane.cli projection ledger refresh --target <target> --repo-root <repo-root> --write
```

## 引用规则

- 执行顺序类 runbook（例如 agent execution flow）只描述何时调用 automation/projection，不再复述职责定义。
- 应用交付类 runbook（例如 app project delivery）只描述交付流程中的调用点，不再定义 automation/projection 的所有权语义。
- 如发现职责描述冲突，以本页为准并在冲突页改为链接引用。

## 关联文档

- [linux-governance.md](./linux-governance.md)
- [control-plane-agent-execution-flow.md](../runbooks/control-plane-agent-execution-flow.md)
- [app-project-delivery-workflow.md](../runbooks/app-project-delivery-workflow.md)
