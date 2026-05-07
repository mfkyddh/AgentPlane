---
status: archived
owner: AgentPlane maintainers
last_verified: 2026-04-25
superseded_by: null
audience: agent
layer: technical
---

# Architecture Docs

结论：`docs/architecture/` 只保留 Agent-first control plane template repository 的长期合同正文；旧链接占位文档、阶段性迁移说明和窄主题 reference 不放在本目录。

## 📋 Core Contracts

- [control-plane.md](control-plane.md): 正式 CLI、task-entry、truth / projection 和对外 domain 语义。
- [linux-governance.md](linux-governance.md): Linux 基础设施治理与长期运行基线。
- [agentplane-app-collaboration.md](agentplane-app-collaboration.md): 控制面模板仓库与应用仓库的职责边界。

## 🔗 Reference

- [control-plane-naming-registry.md](../reference/control-plane-naming-registry.md)
- [repository-structure.md](../reference/repository-structure.md)
- [app-repository-standard.md](../reference/app-repository-standard.md)
- [onepanel-api-contract.md](../reference/onepanel-api-contract.md)
- [app-delivery-versioning.md](../reference/app-delivery-versioning.md)
- [control-plane-naming-registry.md](../reference/control-plane-naming-registry.md)

## 🤖 Maintainers

- [control-plane-authoring.md](../maintainers/control-plane-authoring.md)

维护者规则只放在 `docs/maintainers/`；仓库根 `README.md` 面向模板使用者，`AGENTS.md` 只保留短合同。

## 🕰️ History And Archive

- [docs/history/index.md](../history/index.md)
- [docs/archive/README.md](../archive/README.md)

历史计划、handoff 和 archived runbook 继续保留，但不再作为 template-facing 正式正文。

## 🚫 Non-Goals

- 不在 `docs/architecture/` 保留仅用于跳转的 stub。
- 不把 reference 正文复制回 architecture。
- 不把 history/archive 内容重新包装成 active contract。
