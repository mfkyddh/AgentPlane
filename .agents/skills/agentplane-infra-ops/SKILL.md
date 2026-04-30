---
name: agentplane-infra-ops
description: Use for host identity, inventory, audit, network, secrets layout, remote command routing, 1Panel panel settings, firewall posture, and cronjob/automation checks through the AgentPlane CLI.
---

# AgentPlane Infra Ops

## Overview

Use this domain skill for infrastructure objects and host-adjacent control-plane state. The Agent may inspect and reconcile through the formal CLI, but must not build a second SSH, Docker, cloud API, or signed 1Panel API path.

This skill absorbs the public parts of the previous host, panel, firewall, and cronjob skills. Provider names such as 1Panel are implementation details unless the CLI surface explicitly exposes them.

## Commands

```bash
agentplane infra inventory <target> --repo-root <repo-root>
agentplane infra audit <target> --repo-root <repo-root>
agentplane infra network audit <target> --repo-root <repo-root>
agentplane infra network ensure <target> --repo-root <repo-root>
agentplane infra remote bash <target> -- whoami
agentplane infra automation search <target> --repo-root <repo-root>
agentplane infra automation get <target> --name <automation-name> --repo-root <repo-root>
agentplane infra automation verify <target> --name <automation-name> --repo-root <repo-root>
agentplane infra automation plan <target> --name <automation-name> --operation <operation> --repo-root <repo-root>
agentplane infra automation apply <target> --name <automation-name> --operation <operation> --repo-root <repo-root> --execute
agentplane infra secrets init-data-services <target> --repo-root <repo-root>
agentplane infra secrets sync-layout <target> --repo-root <repo-root> --write
agentplane onepanel --env <target> panel get
agentplane onepanel --env <target> firewall verify --tab port --expected-active true --json
agentplane onepanel --env <target> cronjob search --info <keyword>
```

## Rules

- Route remote Linux execution through `infra remote bash`; do not handcraft nested SSH.
- Secrets truth starts under `secrets/hosts/<target>/`; projection paths are not truth.
- Firewall and panel mutation must use plan/apply style when available.
- After infrastructure posture changes, run the smallest matching audit or verify command and refresh projection ledgers when state changed.

## Downstream Docs

- `docs/reference/cross-platform.md`
- `docs/runbooks/control-plane-agent-execution-flow.md`
- `docs/runbooks/control-plane-domain-onboarding.md`
