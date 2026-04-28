---
name: app-delivery-ops
description: Use when an application repository needs onboarding, contract validation, build, deployment, rollback, verification, inventory refresh, or deployment summary write-back through the AgentPlane control plane.
---

# App Delivery Ops

## Overview

Application repositories own code, artifacts, and `deploy/agentplane/contract*.yaml`. AgentPlane owns the formal delivery workflow. Route every app delivery action through `uv run python -m agentplane.cli app ...`; do not ask the Agent to run Docker, SSH, or registry commands directly as the delivery path.

Use this workflow skill when the user asks to onboard an app, validate a contract, build or ship an artifact, deploy, roll back, verify, refresh inventory, or write the deployment summary.

Do not use this skill for host setup, service restart, website ingress repair, or generic repo checks; use the corresponding `agentplane-*` skill.

## Commands

```bash
uv run python -m agentplane.cli app delivery onboard --target <target> --app <app> --app-repo-root <app-repo-root> --repo-root <repo-root>
uv run python -m agentplane.cli app object get --target <target> --app <app> --repo-root <repo-root>
uv run python -m agentplane.cli app delivery validate-contract --target <target> --app <app> --repo-root <repo-root>
uv run python -m agentplane.cli app delivery build-artifact --target <target> --app <app> --repo-root <repo-root>
uv run python -m agentplane.cli app delivery deploy --target <target> --app <app> --repo-root <repo-root> --dry-run
uv run python -m agentplane.cli app delivery deploy --target <target> --app <app> --repo-root <repo-root> --execute
uv run python -m agentplane.cli app delivery verify --target <target> --app <app> --repo-root <repo-root> --execute
uv run python -m agentplane.cli app delivery inventory-refresh --target <target> --app <app> --repo-root <repo-root> --write
uv run python -m agentplane.cli app delivery doc-sync --target <target> --app <app> --repo-root <repo-root> --write
```

## Required Discipline

- Validate the contract before build, deploy, rollback, verify, or doc-sync.
- Use `--dry-run` for deployment planning and `--execute` only after the user accepts the plan.
- Final acceptance returns to the catalog-resolved app repository root; `--app-repo-root` is only a temporary override.
- After tracked runtime changes, refresh inventory and write the non-sensitive deployment summary.

## Downstream Docs

- `docs/runbooks/app-project-delivery-workflow.md`
- `docs/architecture/agentplane-app-collaboration.md`
