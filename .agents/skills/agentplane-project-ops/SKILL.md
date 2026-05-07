---
name: agentplane-project-ops
description: Use for AgentPlane project governance, docs sanity, secret/privacy scanning, fast tests, release checks, and Skill catalog consistency.
---

# AgentPlane Project Ops

## Overview

Use this domain skill for project self-governance: documentation checks, privacy and secret boundaries, release readiness, test gates, and Skill catalog consistency.

## Commands

```bash
agentplane project docs-sanity --repo-root <repo-root>
agentplane project privacy-scan --repo-root <repo-root>
agentplane project secret-scan --repo-root <repo-root>
agentplane project skills check --repo-root <repo-root>
agentplane project skills list --repo-root <repo-root>
agentplane project skills export --repo-root <repo-root>
agentplane project skills sync --repo-root <repo-root>
agentplane project status --repo-root <repo-root>
agentplane project status --repo-root <repo-root> --html tmp/agentplane-status.html
agentplane project health-check --repo-root <repo-root>
agentplane project release-check --repo-root <repo-root>
agentplane test fast --tb=short
```

## Rules

- Any active doc added or moved must be reachable from an active index or upstream doc.
- Any formal capability change must update the matching Skill or explicitly explain why no Skill changed.
- Do not commit real secrets, maintainer-local inventory, production runbooks, rendered prod compose, or private Skills.
- Run the narrowest useful test first, then the repo gate required for the change.

## Downstream Docs

- `docs/architecture.md`
- `docs/architecture.md`
