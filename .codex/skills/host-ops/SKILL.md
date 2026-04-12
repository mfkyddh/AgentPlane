---
name: host-ops
description: Use when the task is about host identity, SSH topology, host-level inventory, or host-first secret organization in AgentPlane.
---

# Host Ops

## Overview

In the template repository, host truth stays in Git-tracked truth plus local secrets. Route host work through the formal `uv run python -m agentplane.cli host ...` entrypoints instead of calling legacy helpers or author-site wrappers directly.

## Boundaries

- `host` covers `inventory`, `audit`, `cleanup`, `automation`, `network`, `remote bash`, and `secrets`.
- `panel / firewall` stay in the `onepanel` domain and do not move into `host`.
- Fresh forks should start with `bootstrap inspect-local --repo-root <repo-root>` before host operations.

## Commands

```bash
uv run python -m agentplane.cli host inventory <target> --repo-root <repo-root>
uv run python -m agentplane.cli host audit <target> --repo-root <repo-root>
uv run python -m agentplane.cli host cleanup plan <target> --repo-root <repo-root>
uv run python -m agentplane.cli host cleanup apply <target> --repo-root <repo-root>
uv run python -m agentplane.cli host automation search <target> --repo-root <repo-root>
uv run python -m agentplane.cli host automation get <target> --name <automation-name> --repo-root <repo-root>
uv run python -m agentplane.cli host automation verify <target> --name <automation-name> --repo-root <repo-root>
uv run python -m agentplane.cli host automation plan <target> --name <automation-name> --operation <operation> --repo-root <repo-root>
uv run python -m agentplane.cli host automation apply <target> --name <automation-name> --operation <operation> --repo-root <repo-root> --execute
uv run python -m agentplane.cli host network audit <target> --repo-root <repo-root>
uv run python -m agentplane.cli host network ensure <target> --repo-root <repo-root>
uv run python -m agentplane.cli host remote bash <target> -- whoami
uv run python -m agentplane.cli host secrets init-data-services <target> --repo-root <repo-root>
uv run python -m agentplane.cli host secrets sync-layout <target> --repo-root <repo-root> --write
```
