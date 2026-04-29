---
status: active
owner: AgentPlane maintainers
last_verified: 2026-04-29
superseded_by: null
audience: both
---

# Roadmap

AgentPlane is currently an alpha-stage, CLI-first control plane template for AI-assisted infrastructure operations.

## Strategic Blueprint

The long-term north-star plan is tracked in [AgentPlane 终极蓝图 v4](docs/reference/agentplane-ultimate-blueprint.md). Phase execution state is tracked in [AgentPlane Roadmap Workbook](docs/maintainers/agentplane-roadmap-workbook.md).

Phases P0–P6 (blueprint landing, resume protocol, evidence model, project model, lifecycle demo design, dashboard, and security framework) are complete. P7 (lifecycle verification) is the current phase — running a real app through the full onboarding → verify → receipt → offboard lifecycle to validate the designs from P0–P6.

These documents do not replace the formal control-plane contract. Formal operations still route through `agentplane ...`, and execution semantics remain governed by [control-plane.md](docs/architecture/control-plane.md).

## Stable Enough To Build On

| Area | Current status |
| --- | --- |
| Repository governance | `agentplane repo health-check` and `release-check` cover lint, tests, secret scan, privacy scan, and docs sanity. |
| CLI entrypoint discipline | Formal operations route through `agentplane ...`; direct scripts are implementation details. |
| Offline test gate | Default tests are designed to be deterministic and offline. |
| Documentation governance | Active docs have frontmatter, indexing, and sanity checks. |
| Secret boundary | Real secrets stay in ignored `secrets/`; examples live under `templates/`. |

## Alpha Boundaries

| Area | Why it is still alpha |
| --- | --- |
| Public installation story | The project is usable from source, but release artifacts and package publishing are not yet automated. |
| Provider surface | Provider/debug layers still need more contract tests before they are stable public APIs. |
| App delivery schema | `schema_version: 2` is the formal path, but machine-readable schema and migration notes are still being expanded. |
| Live gates | WSL, SSH, Docker, DNS, and provider checks require explicitly prepared environments. |

## Near-Term Milestones

| Milestone | Goal | Exit criteria | Progress |
| --- | --- | --- | --- |
| M1: Public contributor loop | Make external PRs self-verifying. | CI runs on pull requests and pushes, issue templates exist, and release checks are documented. | **Partially done** — CI workflow (`ci.yml`) covers 3-OS matrix fast-gate + release-gate; issue/PR templates exist. |
| M2: Release engineering | Make tags reproducible. | `uv build` passes in release checks and release notes are maintained. | **Partially done** — `repo release-check` CLI exists; `uv build` and release notes automation pending. |
| M3: Contract hardening | Make app delivery contracts machine-checkable. | JSON Schema exists for the current contract and CLI errors carry stable codes. | Pending. |
| M4: Runtime decomposition | Reduce high-risk files. | App delivery runtime responsibilities are split by contract, render, deploy, verify, and inventory/doc sync. | Pending. |
| M5: Provider contracts | Keep provider details behind formal surfaces. | Provider behavior has focused contract tests and public docs point to task entries. | Pending. |

## Long-Term Phases

| Phase | Goal | Tracking |
| --- | --- | --- |
| P0: Blueprint landing | Land the active strategic blueprint and workplan mechanism. | [Workbook](docs/maintainers/agentplane-roadmap-workbook.md#p0-蓝图落库与任务机制建立) |
| P1: Resume protocol | Make "continue execution" reliably recover current phase, next task, and status updates. | [Workbook](docs/maintainers/agentplane-roadmap-workbook.md#p1-任务书与继续执行闭环稳定) |
| P2: Evidence model | Define operation receipts, exceptions, and review records. | [Blueprint](docs/reference/agentplane-ultimate-blueprint.md#长期机制) |
| P3: Project model | Separate project registry, app catalog, and blueprints. | [Blueprint](docs/reference/agentplane-ultimate-blueprint.md#长期机制) |
| P4: Lifecycle demo | Prove a low-risk app lifecycle from onboarding through verification and retirement semantics. | [Workbook](docs/maintainers/agentplane-roadmap-workbook.md#p4-应用生命周期示范闭环) |
| P5: Dashboard evolution | Extend repo status or static dashboard with phase, task, project, and risk views. | [Workbook](docs/maintainers/agentplane-roadmap-workbook.md#p5-可视化控制面增强) |
| P6: Controlled scale | Add security, concurrency, approvals, and multi-Agent boundaries. | [Workbook](docs/maintainers/agentplane-roadmap-workbook.md#p6-安全并发与多-agent-受控扩展) |
| P7: Lifecycle verification | Run a real app through the full onboarding → verify → receipt → offboard lifecycle. | **Done** — [Workbook](docs/maintainers/agentplane-roadmap-workbook.md#p7-应用生命周期真实验证) |

## Not Goals

- AgentPlane is not a replacement for Terraform or a full GitOps controller.
- AgentPlane is not an SSH script collection.
- AgentPlane does not store production secrets, private host inventories, or maintainer-local runbooks in public Git.
- AgentPlane does not make application repositories own production control-plane state.
