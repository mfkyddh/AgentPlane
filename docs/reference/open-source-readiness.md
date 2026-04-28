---
status: active
owner: AgentPlane maintainers
last_verified: 2026-04-22
superseded_by: null
audience: agent

---

# Open Source Readiness

结论：开源准备度基线，仓库对外开放前的必须项检查清单。

This repository is being shaped as a one-checkout, cross-platform open source control plane template.

Public positioning lives in [project-positioning.md](project-positioning.md). Release maturity and staged goals live in [../../ROADMAP.md](../../ROADMAP.md).

## Baseline Requirements

- A single checkout works on macOS, Linux, and Windows.
- Windows can use WSL as a backend without requiring a second source checkout.
- No active docs, templates, inventory, or skills depend on maintainer-local paths.
- Default tests are offline and deterministic.
- Live WSL, Docker, SSH, and provider validation is explicit.
- Real secrets stay out of Git.
- Maintainer-local inventories, runbooks, rendered compose files, and private skills stay ignored and out of public Git.
- Contributor, security, support, license, code style, tech stack, release process, and test architecture documents are present at the repository root or under `docs/reference/`.
- Roadmap, changelog, issue templates, and architecture decision records exist for public collaboration.
- Tests are grouped by domain directory with shared helpers isolated under `tests/support/`.
- Repository health checks are available through `agentplane repo health-check`.
- Git-visible files are scanned for obvious secret material in CI.
- Git-visible files are scanned for private environment material through `agentplane repo privacy-scan`.
- Active docs are checked through `agentplane repo docs-sanity`.
- Release readiness is checked through `agentplane repo release-check`.

## Remaining Hard-Cut Work

- Keep provider helpers internal and route public workflows through the formal CLI.
- Move remaining direct `tests/onepanel` script substrate coverage behind provider-level contracts where practical.
- Run live gate with `--execute` only in an explicitly prepared WSL/SSH/Docker environment.
- Keep release automation current after the first public tag.
