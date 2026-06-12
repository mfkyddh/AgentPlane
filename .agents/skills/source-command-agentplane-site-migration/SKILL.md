---
name: "source-command-agentplane-site-migration"
description: "Migrate a single website or public ingress path into AgentPlane-managed ingress model while preserving the current public entry until parallel validation passes."
---

# source-command-agentplane-site-migration

Use this skill when the user asks to run the migrated source command `agentplane-site-migration`.

## Command Template

# Site Migration Ops

Use for site or domain migration. Keep existing public entry online, create new ingress path, validate in parallel, then cut over only after user accepts evidence.

## Rules

- Never remove old entry until new path is validated and user confirms cutover
- Parallel validation is mandatory

Full details: `.agents/skills/site-migration-ops/SKILL.md`

## Overview

Migrate a single website or public ingress path into AgentPlane-managed ingress model while preserving the current public entry until parallel validation passes.

## Commands

```bash
agentplane ingress
```

## Downstream Docs

See `.agents/skills/site-migration-ops/SKILL.md` for detailed documentation.
