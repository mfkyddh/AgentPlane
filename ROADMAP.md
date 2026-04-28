---
status: active
owner: AgentPlane maintainers
last_verified: 2026-04-29
superseded_by: null
audience: both
---

# Roadmap

AgentPlane is currently an alpha-stage, CLI-first control plane template for AI-assisted infrastructure operations.

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

| Milestone | Goal | Exit criteria |
| --- | --- | --- |
| M1: Public contributor loop | Make external PRs self-verifying. | CI runs on pull requests and pushes, issue templates exist, and release checks are documented. |
| M2: Release engineering | Make tags reproducible. | `uv build` passes in release checks and release notes are maintained. |
| M3: Contract hardening | Make app delivery contracts machine-checkable. | JSON Schema exists for the current contract and CLI errors carry stable codes. |
| M4: Runtime decomposition | Reduce high-risk files. | App delivery runtime responsibilities are split by contract, render, deploy, verify, and inventory/doc sync. |
| M5: Provider contracts | Keep provider details behind formal surfaces. | Provider behavior has focused contract tests and public docs point to task entries. |

## Not Goals

- AgentPlane is not a replacement for Terraform or a full GitOps controller.
- AgentPlane is not an SSH script collection.
- AgentPlane does not store production secrets, private host inventories, or maintainer-local runbooks in public Git.
- AgentPlane does not make application repositories own production control-plane state.

