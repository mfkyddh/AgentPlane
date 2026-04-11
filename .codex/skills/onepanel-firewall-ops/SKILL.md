---
name: onepanel-firewall-ops
description: Use when the task is about tracked firewall posture, allowed ports, or host-level firewall verification in the AgentPlane control plane.
---

# Firewall Ops

## Overview

Use the 1Panel host firewall API through the unified CLI. Inventory still matters for reconciliation, but base/search/operate should now come from `onepanel firewall`.

## Commands

```bash
uv run python -m agentplane.cli onepanel --env <target> firewall get --tab port --json
uv run python -m agentplane.cli onepanel --env <target> firewall search --type port --info 22 --json
uv run python -m agentplane.cli onepanel --env <target> firewall verify --tab port --expected-active true --json
uv run python -m agentplane.cli onepanel --env <target> firewall plan --operation restart --json
uv run python -m agentplane.cli onepanel --env <target> firewall apply --operation restart --execute --json
uv run python -m agentplane.cli onepanel --env <target> ledger refresh --repo-root /root/work/AgentPlane --write --json
```

## Rules

- Do not treat UI clicks as formal firewall operations.
- Keep tracked inventory aligned with live host state after API-side changes.
