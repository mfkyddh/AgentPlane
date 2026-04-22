---
status: active
owner: AgentPlane maintainers
last_verified: 2026-04-22
superseded_by: null
---

# Open Source Readiness

This repository is being shaped as a one-checkout, cross-platform open source control plane template.

## Baseline Requirements

- A single checkout works on macOS, Linux, and Windows.
- Windows can use WSL as a backend without requiring a second source checkout.
- No active docs, templates, inventory, or skills depend on maintainer-local paths.
- Default tests are offline and deterministic.
- Live WSL, Docker, SSH, and provider validation is explicit.
- Real secrets stay out of Git.
- Contributor, security, support, license, and test architecture documents are present at the repository root or under `docs/reference/`.
- Tests are grouped by domain directory with shared helpers isolated under `tests/support/`.

## Remaining Hard-Cut Work

- Retire remaining compatibility-only provider helpers once the formal CLI fully covers their use cases.
- Move remaining direct `tests/onepanel` script substrate coverage behind provider-level contracts where practical.
- Run live gate with `--execute` only in an explicitly prepared WSL/SSH/Docker environment.
- Publish a release process after the first public tag.
