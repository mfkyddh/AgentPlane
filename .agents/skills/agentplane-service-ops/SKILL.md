---
name: agentplane-service-ops
description: Use for formal service object search, inspection, verification, restart/reconcile planning, and execution through the AgentPlane service surface.
---

# AgentPlane Service Ops

## Overview

Use this domain skill for runtime service objects such as managed containers. The user intent may mention Docker or 1Panel, but the public Agent route is the `service` domain unless the task is initial installation or host onboarding.

## Commands

```bash
agentplane service search --target <target> --repo-root <repo-root>
agentplane service get --target <target> --name <service> --repo-root <repo-root>
agentplane service verify --target <target> --name <service> --repo-root <repo-root>
agentplane service plan --target <target> --name <service> --operation restart --repo-root <repo-root>
agentplane service apply --target <target> --name <service> --operation restart --repo-root <repo-root> --execute
```

## Capability Details

- `verify` checks: container state, image reference, network binding, compose project name, compose config file path (via Docker inspect labels).
- When inventory declares `project_name`, `compose_file`, or `config_files`, `verify` cross-checks against Docker compose labels to detect drift.

## Rules

- Inspect with `search`, `get`, or `verify` before mutation.
- Treat `verify` as live runtime drift evidence for container state, image, network binding, and compose identity labels when declared.
- Use `plan` before `apply` for any formal restart or reconcile.
- Do not expose provider/debug commands as the first answer to the user.
- After service state changes, refresh inventory or ledger only through the formal projection skills.

## Downstream Docs

- `docs/architecture/control-plane.md`
- `docs/runbooks/control-plane-agent-execution-flow.md`
