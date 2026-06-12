---
name: "source-command-agentplane-projection-ops"
description: "Runtime environment projection, drift verification, fixture projection, ledger refresh, inventory refresh, and doc-sync through AgentPlane."
---

# source-command-agentplane-projection-ops

Use this skill when the user asks to run the migrated source command `agentplane-projection-ops`.

## Command Template

# AgentPlane Projection Ops

Use for generated runtime env files, projection verification, ledgers, inventory summaries, and doc-sync after formal state changes.

## Key Commands

```bash
agentplane projection verify --target <target> --repo-root <repo-root>
agentplane projection refresh-ledger --target <target> --repo-root <repo-root> --write
agentplane projection inventory --target <target> --repo-root <repo-root>
agentplane projection doc-sync --target <target> --repo-root <repo-root>
```

## Rules

- Projection files are generated, not manually edited
- After state changes, always refresh projection ledger

Full details: `.agents/skills/agentplane-projection-ops/SKILL.md`

## Overview

Runtime environment projection, drift verification, fixture projection, ledger refresh, inventory refresh, and doc-sync through AgentPlane.

## Commands

```bash
agentplane project projection
```

## Downstream Docs

See `.agents/skills/agentplane-projection-ops/SKILL.md` for detailed documentation.
