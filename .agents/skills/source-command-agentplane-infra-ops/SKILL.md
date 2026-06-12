---
name: "source-command-agentplane-infra-ops"
description: "Host identity, inventory, audit, network, secrets layout, remote command routing, firewall posture, and automation checks through AgentPlane CLI."
---

# source-command-agentplane-infra-ops

Use this skill when the user asks to run the migrated source command `agentplane-infra-ops`.

## Command Template

# AgentPlane Infra Ops

Use for infrastructure objects and host-adjacent control-plane state. Never build a second SSH, Docker, or cloud API path.

## Key Commands

```bash
agentplane infra health <target> --repo-root <repo-root>
agentplane infra inventory <target> --repo-root <repo-root>
agentplane infra audit <target> --repo-root <repo-root>
agentplane infra network audit <target> --repo-root <repo-root>
agentplane infra network firewall-audit <target> --repo-root <repo-root>
agentplane infra remote bash <target> -- <command>
agentplane infra automation search <target> --repo-root <repo-root>
agentplane infra secrets sync-layout <target> --repo-root <repo-root> --write
```

## Rules

- Route remote Linux through `infra remote bash`; no handcrafted SSH
- Secrets truth: `secrets/hosts/<target>/`
- Firewall mutations use plan/apply style

Full details: `.agents/skills/agentplane-infra-ops/SKILL.md`

## Overview

Host identity, inventory, audit, network, secrets layout, remote command routing, firewall posture, and automation checks through AgentPlane CLI.

## Commands

```bash
agentplane infra
```

## Downstream Docs

See `.agents/skills/agentplane-infra-ops/SKILL.md` for detailed documentation.
