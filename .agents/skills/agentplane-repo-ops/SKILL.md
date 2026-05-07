---
name: agentplane-repo-ops
description: Use for AgentPlane repository governance, docs sanity, secret/privacy scanning, fast tests, release checks, and Skill catalog consistency.
---

# AgentPlane Repo Ops

## Overview

Use this domain skill for repository self-governance: documentation checks, privacy and secret boundaries, release readiness, test gates, and Skill catalog consistency.

## Commands

```bash
agentplane repo docs-sanity --repo-root <repo-root>
agentplane repo privacy-scan --repo-root <repo-root>
agentplane repo secret-scan --repo-root <repo-root>
agentplane repo skills check --repo-root <repo-root>
agentplane repo skills list --repo-root <repo-root>
agentplane repo skills export --repo-root <repo-root>
agentplane repo skills sync --repo-root <repo-root>
agentplane repo provider onepanel route-fingerprint --source-root <1panel-source-root> --repo-root <repo-root>
agentplane repo provider onepanel route-fingerprint --source-root <1panel-source-root> --baseline tmp/onepanel-routes.json --fail-on-drift --repo-root <repo-root>
agentplane repo status --repo-root <repo-root>
agentplane repo status --repo-root <repo-root> --html tmp/agentplane-status.html
agentplane repo health-check --repo-root <repo-root>
agentplane repo health-check --repo-root <repo-root> --onepanel-source-root <1panel-source-root> --onepanel-baseline tmp/onepanel-routes.json --fail-on-onepanel-drift
agentplane repo release-check --repo-root <repo-root>
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
