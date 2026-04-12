# Architecture Docs

结论：`docs/architecture/` 只保留 Agent-first control plane template repository 的长期合同；active runbook、reference、maintainer authoring 与 history/archive 分层放在相邻目录，不再把作者现场或阶段性迁移说明当成正式入口。

## Core Contracts

- [control-plane.md](control-plane.md): 正式 CLI、task-entry、truth / projection 和对外 domain 语义。
- [linux-governance.md](linux-governance.md): Linux 主机治理与长期运行基线。
- [agentplane-app-collaboration.md](agentplane-app-collaboration.md): 控制面模板仓库与应用仓库的职责边界。
- [agent-first-template-truth-model.md](agent-first-template-truth-model.md): canonical refs、tracked truth、verification evidence 的模板真源模型。

## Reference

- [control-plane-path-policy.md](../reference/control-plane-path-policy.md)
- [app-repository-standard.md](../reference/app-repository-standard.md)
- [onepanel-api-compatibility.md](../reference/onepanel-api-compatibility.md)
- [app-delivery-versioning.md](../reference/app-delivery-versioning.md)
- [compat-retirement-ledger.md](../reference/compat-retirement-ledger.md)
- [control-plane-naming-registry.md](../reference/control-plane-naming-registry.md)

## Maintainers

- [control-plane-authoring.md](../maintainers/control-plane-authoring.md)

维护者规则只放在 `docs/maintainers/`；仓库根 `README.md` 面向模板使用者，`AGENTS.md` 只保留短合同。

## History And Archive

- [docs/history/index.md](../history/index.md)
- [docs/archive/README.md](../archive/README.md)

历史计划、handoff 和 archived runbook 继续保留，但不再作为 template-facing 正式正文。
