---
name: agentplane-projection-ops
description: Use for runtime environment projection, drift verification, fixture projection, ledger refresh, inventory refresh, and non-sensitive doc-sync through AgentPlane.
---

# AgentPlane Projection Ops

## Overview

Use this domain skill for generated runtime env files, projection verification, ledgers, inventory summaries, and doc-sync after formal state changes.

## Commands

```bash
agentplane project projection runtime-env plan --target <target> --app <app> --repo-root <repo-root>
agentplane project projection runtime-env apply --target <target> --app <app> --repo-root <repo-root>
agentplane project projection runtime-env verify --target <target> --app <app> --repo-root <repo-root>
agentplane project projection verification run --target <target> --profile <profile> --repo-root <repo-root>
agentplane project projection fixture plan --target <target> --profile <profile> --repo-root <repo-root>
agentplane project projection fixture apply --target <target> --profile <profile> --repo-root <repo-root> --execute
agentplane project projection fixture cleanup --target <target> --profile <profile> --repo-root <repo-root> --execute
agentplane project projection ledger refresh --target <target> --repo-root <repo-root> --write
agentplane app delivery inventory-refresh --target <target> --app <app> --repo-root <repo-root> --write
agentplane app delivery doc-sync --target <target> --app <app> --repo-root <repo-root> --write
```

## Rules

- Live state beats inventory projection; inventory beats runbook prose.
- Projection outputs are generated artifacts, not human-maintained truth.
- After any write, verify the projection or refresh path that was touched.
- Do not ask the Agent to edit ledgers or inventory JSON by hand.

## Downstream Docs

- `docs/architecture.md`
- `docs/runbooks/control-plane-agent-execution-flow.md`
