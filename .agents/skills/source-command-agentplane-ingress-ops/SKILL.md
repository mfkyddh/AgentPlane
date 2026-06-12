---
name: "source-command-agentplane-ingress-ops"
description: "Website and public ingress object search, inspection, verification, publication planning, certificate binding, and ledger refresh through AgentPlane."
---

# source-command-agentplane-ingress-ops

Use this skill when the user asks to run the migrated source command `agentplane-ingress-ops`.

## Command Template

# AgentPlane Ingress Ops

Use for public HTTP ingress, website aliases, Cloudflare-backed publication, certificate binding, and ingress ledger refresh.

## Key Commands

```bash
agentplane ingress search --target <target> --repo-root <repo-root>
agentplane ingress get --target <target> --site <site> --repo-root <repo-root>
agentplane ingress verify --target <target> --site <site> --repo-root <repo-root>
agentplane ingress refresh-ledger --target <target> --repo-root <repo-root> --write
```

## Rules

- Provider (1Panel, nginx-ui, OpenResty, Cloudflare) is implementation detail
- Route through `agentplane ingress ...`

Full details: `.agents/skills/agentplane-ingress-ops/SKILL.md`

## Overview

Website and public ingress object search, inspection, verification, publication planning, certificate binding, and ledger refresh through AgentPlane.

## Commands

```bash
agentplane ingress
```

## Downstream Docs

See `.agents/skills/agentplane-ingress-ops/SKILL.md` for detailed documentation.
