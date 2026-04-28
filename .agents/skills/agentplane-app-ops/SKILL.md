---
name: agentplane-app-ops
description: Use for app object truth, catalog inspection, app resource truth, resource projection verification, and app ledger refresh through AgentPlane.
---

# AgentPlane App Ops

## Overview

Use this domain skill when the user asks about app objects, app catalog state, app resource truth, resource projection, or resource ledgers. Use `app-delivery-ops` when the task is a full delivery workflow.

## Commands

```bash
uv run python -m agentplane.cli app object search --target <target> --repo-root <repo-root>
uv run python -m agentplane.cli app object get --target <target> --app <app> --repo-root <repo-root>
uv run python -m agentplane.cli app object verify --target <target> --app <app> --repo-root <repo-root>
uv run python -m agentplane.cli app object refresh-ledger --target <target> --repo-root <repo-root> --write
uv run python -m agentplane.cli app resource search --target <target> --repo-root <repo-root>
uv run python -m agentplane.cli app resource get --target <target> --app <app> --repo-root <repo-root>
uv run python -m agentplane.cli app resource verify --target <target> --app <app> --repo-root <repo-root>
uv run python -m agentplane.cli app resource refresh-ledger --target <target> --repo-root <repo-root> --write
uv run python -m agentplane.cli infra secrets sync-layout <target> --repo-root <repo-root> --write
```

## Rules

- App resource secrets truth starts under `secrets/hosts/<target>/apps/<app>/resources/`.
- Do not revive legacy app-resource projection paths as truth.
- App runtime restart or reconcile is a service task; route to `agentplane-service-ops`.
- App deploy/build/rollback/doc-sync is a delivery workflow; route to `app-delivery-ops`.

## Downstream Docs

- `docs/reference/app-repository-standard.md`
- `docs/architecture/agentplane-app-collaboration.md`
