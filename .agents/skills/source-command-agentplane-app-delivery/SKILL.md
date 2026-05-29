---
name: "source-command-agentplane-app-delivery"
description: "Application onboarding, contract validation, build, deployment, rollback, verification, inventory refresh, and deployment summary write-back through AgentPlane."
---

# source-command-agentplane-app-delivery

Use this skill when the user asks to run the migrated source command `agentplane-app-delivery`.

## Command Template

# App Delivery Ops

Use when an application repository needs onboarding, contract validation, build, deployment, rollback, verification, or inventory refresh. Route every app delivery action through `agentplane app ...`.

## Key Commands

```bash
agentplane app delivery onboard --target <target> --app <app> --repo-root <repo-root>
agentplane app delivery build --target <target> --app <app> --repo-root <repo-root>
agentplane app delivery deploy --target <target> --app <app> --repo-root <repo-root>
agentplane app delivery rollback --target <target> --app <app> --repo-root <repo-root>
agentplane app delivery verify --target <target> --app <app> --repo-root <repo-root>
```

## Rules

- Do not run Docker, SSH, or registry commands directly as the delivery path
- App repos own code + contract YAML; AgentPlane owns the delivery workflow

Full details: `.agents/skills/app-delivery-ops/SKILL.md`
