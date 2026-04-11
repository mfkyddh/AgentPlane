---
name: onepanel-ops
description: Use when an older 1Panel API skill name is invoked and this compatibility entry must route the task into the canonical AgentPlane CLI-first 1Panel skills.
---

# 1Panel Ops Alias

## Overview

This is a legacy compatibility alias. `CLI-first` is mandatory: this entry only chooses the correct canonical skill, while execution stays in `uv run python -m agentplane.cli onepanel ...`.

## Router

- Panel settings, version baselines, or bind-domain state: route to `onepanel-panel-ops`
- Website objects, proxy targets, or HTTPS bindings: route to `onepanel-website-ops`
- Containers or runtime verification: route to `onepanel-container-ops`
- Installed app objects or app-store state: route to `onepanel-app-ops`
- Cronjobs or schedule checks: route to `onepanel-cronjob-ops`
- Reconciliation, inventory refresh, or summaries: route to `inventory-ledger-ops`

## Alias Rules

- Do not duplicate subcommand examples in this compatibility layer; detailed command inventories belong to the routed canonical skills.
- Do not build signed HTTP requests or TypeScript-side direct API flows here.
- Keep formal writes in the canonical `plan`, `apply --execute`, `verify`, and `refresh-ledger` flow defined by the routed skill.
