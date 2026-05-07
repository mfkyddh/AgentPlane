---
name: agentplane-app-ops
description: Use for app object truth, catalog inspection, app resource truth, resource projection verification, and app ledger refresh through AgentPlane.
---

# AgentPlane App Ops

## Overview

Use this domain skill when the user asks about app objects, app catalog state, app resource truth, resource projection, or resource ledgers. Use `app-delivery-ops` when the task is a full delivery workflow.

## Commands

```bash
agentplane app object search --target <target> --repo-root <repo-root>
agentplane app object get --target <target> --app <app> --repo-root <repo-root>
agentplane app object verify --target <target> --app <app> --repo-root <repo-root>
agentplane app object discover --target <target> --repo-root <repo-root>
agentplane app object refresh-ledger --target <target> --repo-root <repo-root> --write
agentplane app resource search --target <target> --repo-root <repo-root>
agentplane app resource get --target <target> --app <app> --repo-root <repo-root>
agentplane app resource verify --target <target> --app <app> --repo-root <repo-root>
agentplane app resource refresh-ledger --target <target> --repo-root <repo-root> --write
agentplane infra secrets sync-layout <target> --repo-root <repo-root> --write
```

## Capability Details

- `discover` queries 1Panel installed apps, compares with catalog, classifies as managed (already in catalog) or unmanaged (not yet onboarded). Supports `--name` filter and `--include-managed`.
- `resource verify` checks: registry owner, secret file existence, inventory projection consistency. Optionally (when 1Panel API is reachable) cross-references declared databases against live provider state.
- `resource get` aggregates: declared payload, inventory projection, secret file statuses.

## Rules

- App resource secrets truth starts under `secrets/hosts/<target>/apps/<app>/resources/`.
- Do not revive legacy app-resource projection paths as truth.
- App runtime restart or reconcile is a service task; route to `agentplane-service-ops`.
- App deploy/build/rollback/doc-sync is a delivery workflow; route to `app-delivery-ops`.

## Downstream Docs

- `docs/architecture.md`
- `docs/architecture.md`
