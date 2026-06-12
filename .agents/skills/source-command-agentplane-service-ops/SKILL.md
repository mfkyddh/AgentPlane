---
name: "source-command-agentplane-service-ops"
description: "Service object search, inspection, verification, restart/reconcile planning, and execution through AgentPlane service surface."
---

# source-command-agentplane-service-ops

Use this skill when the user asks to run the migrated source command `agentplane-service-ops`.

## Command Template

# AgentPlane Service Ops

Use for runtime service objects such as managed containers. The user may mention Docker or 1Panel, but the route is the `service` domain.

## Key Commands

```bash
agentplane service search --target <target> --repo-root <repo-root>
agentplane service get --target <target> --service <service> --repo-root <repo-root>
agentplane service verify --target <target> --service <service> --repo-root <repo-root>
agentplane service restart --target <target> --service <service> --repo-root <repo-root>
```

## Rules

- Service state truth is the live container, not projection files
- After restart, always verify

Full details: `.agents/skills/agentplane-service-ops/SKILL.md`

## Overview

Service object search, inspection, verification, restart/reconcile planning, and execution through AgentPlane service surface.

## Commands

```bash
agentplane service
```

## Downstream Docs

See `.agents/skills/agentplane-service-ops/SKILL.md` for detailed documentation.
