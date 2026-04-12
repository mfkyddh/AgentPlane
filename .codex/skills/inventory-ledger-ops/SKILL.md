---
name: inventory-ledger-ops
description: Use when the task is about object ledgers, inventory refresh, server summaries, or post-change reconciliation in the AgentPlane control plane.
---

# Inventory Ledger Ops

## Overview

Refresh ledgers and summaries after infrastructure or app changes so tracked state stays queryable. Use the formal CLI surfaces only; do not recreate second-control-plane summary scripts.

## Commands

```bash
uv run python -m agentplane.cli projection ledger refresh --target <target> --repo-root <repo-root> --write
uv run python -m agentplane.cli website refresh-ledger --target <target> --repo-root <repo-root> --write
uv run python -m agentplane.cli app object refresh-ledger --target <target> --repo-root <repo-root> --write
uv run python -m agentplane.cli app delivery inventory-refresh --target <target> --app <app> --repo-root <repo-root> --write
uv run python -m agentplane.cli app delivery doc-sync --target <target> --app <app> --repo-root <repo-root> --write
```
