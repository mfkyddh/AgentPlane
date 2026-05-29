---
name: "source-command-agentplane-app-ops"
description: "App object truth, catalog inspection, app resource truth, resource projection verification, and app ledger refresh through AgentPlane."
---

# source-command-agentplane-app-ops

Use this skill when the user asks to run the migrated source command `agentplane-app-ops`.

## Command Template

# AgentPlane App Ops

Use when the user asks about app objects, app catalog state, app resource truth, resource projection, or resource ledgers. Use `app-delivery-ops` for full delivery workflows.

## Key Commands

```bash
agentplane app object search --target <target> --repo-root <repo-root>
agentplane app object get --target <target> --app <app> --repo-root <repo-root>
agentplane app object verify --target <target> --app <app> --repo-root <repo-root>
agentplane app object discover --target <target> --repo-root <repo-root>
agentplane app object refresh-ledger --target <target> --repo-root <repo-root> --write
agentplane app resource search --target <target> --repo-root <repo-root>
agentplane app resource get --target <target> --app <app> --repo-root <repo-root>
agentplane app resource verify --target <target> --app <app> --repo-root <repo-root>
```

## Rules

- App resource secrets truth: `secrets/hosts/<target>/apps/<app>/resources/`
- App runtime restart → route to `agentplane-service-ops`
- App deploy/build/rollback → route to `app-delivery-ops`

Full details: `.agents/skills/agentplane-app-ops/SKILL.md`
