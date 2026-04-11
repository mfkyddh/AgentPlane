---
name: host-ops
description: Use when the task is about host identity, SSH topology, host-level inventory, or host-first secret organization in AgentPlane.
---

# Host Ops

## Overview

Use AgentPlane as the authority for host metadata, SSH access, host-level ledgers, host automation truth, and host-first secret truth. Route host work through the formal `uv run python -m agentplane.cli host ...` entrypoints instead of calling legacy helpers directly.

## Boundaries

- `host` 当前覆盖 `inventory`、`audit`、`cleanup`、`automation`、`network`、`remote bash`、`secrets`；`automation` 已并入 `host`，`network` 已并入 `host`。
- `panel / firewall` 仍保留在 `onepanel` 域，不并入 `host`。

## Commands

```bash
uv run python -m agentplane.cli host inventory <target> --repo-root /root/work/AgentPlane
uv run python -m agentplane.cli host audit <target> --repo-root /root/work/AgentPlane
uv run python -m agentplane.cli host cleanup plan <target> --repo-root /root/work/AgentPlane
uv run python -m agentplane.cli host cleanup apply <target> --repo-root /root/work/AgentPlane
uv run python -m agentplane.cli host automation search wsl --repo-root /root/work/AgentPlane
uv run python -m agentplane.cli host automation get wsl --name wsl-zzz-skills-sync --repo-root /root/work/AgentPlane
uv run python -m agentplane.cli host automation verify wsl --name wsl-agentplane-secrets-backup --repo-root /root/work/AgentPlane
uv run python -m agentplane.cli host automation plan wsl --name wsl-agentplane-secrets-backup --operation reconcile --repo-root /root/work/AgentPlane
uv run python -m agentplane.cli host automation apply wsl --name wsl-agentplane-secrets-backup --operation reconcile --execute --repo-root /root/work/AgentPlane
uv run python -m agentplane.cli host network audit <target> --repo-root /root/work/AgentPlane
uv run python -m agentplane.cli host network ensure <target> --repo-root /root/work/AgentPlane
uv run python -m agentplane.cli host remote bash <target> -- whoami
uv run python -m agentplane.cli host secrets init-data-services <target> --repo-root /root/work/AgentPlane
uv run python -m agentplane.cli host secrets sync-layout <target> --repo-root /root/work/AgentPlane --write
```
