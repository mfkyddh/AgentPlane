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
uv run python -m agentplane.cli infra inventory <target> --repo-root <repo-root>
uv run python -m agentplane.cli infra audit <target> --repo-root <repo-root>
uv run python -m agentplane.cli infra network audit <target> --repo-root <repo-root>
uv run python -m agentplane.cli infra network ensure <target> --repo-root <repo-root>
uv run python -m agentplane.cli infra remote bash <target> -- whoami
uv run python -m agentplane.cli infra automation search <target> --repo-root <repo-root>
uv run python -m agentplane.cli infra automation get <target> --name <automation-name> --repo-root <repo-root>
uv run python -m agentplane.cli infra automation verify <target> --name <automation-name> --repo-root <repo-root>
uv run python -m agentplane.cli infra automation plan <target> --name <automation-name> --operation <operation> --repo-root <repo-root>
uv run python -m agentplane.cli infra automation apply <target> --name <automation-name> --operation <operation> --repo-root <repo-root> --execute
uv run python -m agentplane.cli infra secrets init-data-services <target> --repo-root <repo-root>
uv run python -m agentplane.cli infra secrets sync-layout <target> --repo-root <repo-root> --write
uv run python -m agentplane.cli onepanel --env <target> panel get
uv run python -m agentplane.cli onepanel --env <target> firewall verify --tab port --expected-active true --json
uv run python -m agentplane.cli onepanel --env <target> cronjob search --info <keyword>
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
