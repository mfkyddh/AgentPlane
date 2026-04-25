---
name: app-delivery-ops
description: Use when an application repository needs to hand off build, runtime, deployment, verification, or inventory sync work to the AgentPlane control plane.
---

# App Delivery Ops

## Overview

Application repositories own code, artifacts, and contracts. The control plane template resolves `target + app` through `inventory/apps/catalog.json` and executes formal deployment, verification, and write-back actions through `uv run python -m agentplane.cli app ...`.

## Commands

```bash
uv run python -m agentplane.cli app object get --target <target> --app <app> --repo-root <repo-root>
uv run python -m agentplane.cli app delivery validate-contract --target <target> --app <app> --repo-root <repo-root>
uv run python -m agentplane.cli app delivery build-artifact --target <target> --app <app> --repo-root <repo-root>
uv run python -m agentplane.cli app delivery deploy --target <target> --app <app> --repo-root <repo-root> --dry-run
uv run python -m agentplane.cli app delivery verify --target <target> --app <app> --repo-root <repo-root> --execute
```
