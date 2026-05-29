---
name: "source-command-agentplane-project-ops"
description: "AgentPlane project governance, docs sanity, secret/privacy scanning, fast tests, release checks, and Skill catalog consistency."
---

# source-command-agentplane-project-ops

Use this skill when the user asks to run the migrated source command `agentplane-project-ops`.

## Command Template

# AgentPlane Project Ops

Use for project self-governance: documentation checks, privacy and secret boundaries, release readiness, test gates, and Skill catalog consistency.

## Key Commands

```bash
agentplane project health-check --repo-root <repo-root>
agentplane project docs-sanity --repo-root <repo-root>
agentplane project secret-scan --repo-root <repo-root>
agentplane test fast --tb=short
agentplane project skill-catalog-check --repo-root <repo-root>
```

## Rules

- This is project-level governance, not host operations
- Run health-check before releases

Full details: `.agents/skills/agentplane-project-ops/SKILL.md`
