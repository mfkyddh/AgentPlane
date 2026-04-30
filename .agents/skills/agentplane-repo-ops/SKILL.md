---
name: agentplane-repo-ops
description: Use for AgentPlane repository governance, docs sanity, secret/privacy scanning, fast tests, release checks, and Skill catalog consistency.
---

# AgentPlane Repo Ops

## Overview

Use this domain skill for repository self-governance: documentation checks, privacy and secret boundaries, release readiness, test gates, and Skill catalog consistency.

## Commands

```bash
uv run python -m agentplane.cli repo docs-sanity --repo-root <repo-root>
uv run python -m agentplane.cli repo privacy-scan --repo-root <repo-root>
uv run python -m agentplane.cli repo secret-scan --repo-root <repo-root>
uv run python -m agentplane.cli repo skills check --repo-root <repo-root>
uv run python -m agentplane.cli repo skills list --repo-root <repo-root>
uv run python -m agentplane.cli repo skills export --repo-root <repo-root>
uv run python -m agentplane.cli repo skills sync --repo-root <repo-root>
uv run python -m agentplane.cli repo status --repo-root <repo-root>
uv run python -m agentplane.cli repo status --repo-root <repo-root> --html tmp/agentplane-status.html
uv run python -m agentplane.cli repo health-check --repo-root <repo-root>
uv run python -m agentplane.cli repo release-check --repo-root <repo-root>
uv run python -m agentplane.cli test fast --tb=short
```

## Rules

- Any active doc added or moved must be reachable from an active index or upstream doc.
- Any formal capability change must update the matching Skill or explicitly explain why no Skill changed.
- Do not commit real secrets, maintainer-local inventory, production runbooks, rendered prod compose, or private Skills.
- Run the narrowest useful test first, then the repo gate required for the change.

## Downstream Docs

- `docs/reference/documentation-governance.md`
- `docs/reference/open-source-readiness.md`
- `docs/maintainers/control-plane-authoring.md`
