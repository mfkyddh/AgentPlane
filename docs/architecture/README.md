# Architecture Docs

结论：`docs/architecture/` 只保留长期稳定的架构合同；reference、maintainer authoring 和历史归档按相邻目录分层，不再把旧分页或窄主题继续当正式正文入口。

## Core Contracts

- [control-plane.md](control-plane.md): `AgentPlane` 统一控制面核心合同，收口方法论、CLI 合同、task-entry 模型与 `inventory / ledger` 投影规则。
- [linux-governance.md](linux-governance.md): Linux / WSL 主机治理基线；自动化栈的长期基线说明已并入这里。
- [agentplane-app-collaboration.md](agentplane-app-collaboration.md): `AgentPlane` 与应用仓库的协作边界、交付约束与职责分工。

`control-plane-methodology.md`、`control-plane-cli-contract.md`、`control-plane-task-entry-model.md`、`control-plane-inventory-ledger-model.md`、`control-plane-skill-contract.md`、`control-plane-governance-assets.md` 与 `automation-stack.md` 当前只保留过渡或 superseded 说明，不再列为 Core Contracts。

## Reference

`docs/reference/` 当前承接稳定但不应进入长期架构合同的查询型真源：

- [onepanel-api-compatibility.md](../reference/onepanel-api-compatibility.md)
- [app-delivery-versioning.md](../reference/app-delivery-versioning.md)
- [app-repository-standard.md](../reference/app-repository-standard.md)
- [compat-retirement-ledger.md](../reference/compat-retirement-ledger.md)
- [control-plane-naming-registry.md](../reference/control-plane-naming-registry.md)

## Maintainers

维护者 authoring 正文真源位于 [control-plane-authoring.md](../maintainers/control-plane-authoring.md)。仓库根 `README.md` 负责普通读者入口；`AGENTS.md` 只保留短索引，不再重复扩写专题列表。

## History And Archive

- [docs/history/index.md](../history/index.md): history 层入口；当前主要索引到 `docs/superpowers/plans/`、`specs/`、`handoffs/`。
- [docs/archive/README.md](../archive/README.md): archive 层入口；已承接退出主流程的架构快照与 archived runbook。
- Phase 3 之前，少量已降级的 historical runbook 仍暂留 `docs/runbooks/`，但不再属于 architecture 正式索引的一部分。

