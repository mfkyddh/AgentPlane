---
name: agentplane-service-ops
description: Use for formal service object search, inspection, verification, restart/reconcile planning, and execution through the AgentPlane service surface.
---

# AgentPlane Service Ops

## Overview

Use this domain skill for runtime service objects such as managed containers. The user intent may mention Docker or 1Panel, but the public Agent route is the `service` domain unless the task is initial installation or host onboarding.

## Commands

```bash
uv run python -m agentplane.cli service search --target <target> --repo-root <repo-root>
uv run python -m agentplane.cli service get --target <target> --name <service> --repo-root <repo-root>
uv run python -m agentplane.cli service verify --target <target> --name <service> --repo-root <repo-root>
uv run python -m agentplane.cli service plan --target <target> --name <service> --operation restart --repo-root <repo-root>
uv run python -m agentplane.cli service apply --target <target> --name <service> --operation restart --repo-root <repo-root> --execute
```

## Rules

- Inspect with `search`, `get`, or `verify` before mutation.
- Use `plan` before `apply` for any formal restart or reconcile.
- Do not expose provider/debug commands as the first answer to the user.
- After service state changes, refresh inventory or ledger only through the formal projection skills.

## Downstream Docs

- `docs/architecture/control-plane.md`
- `docs/runbooks/control-plane-agent-execution-flow.md`
