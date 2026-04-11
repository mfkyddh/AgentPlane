---
name: onepanel-app-lifecycle
description: Use when a legacy workflow asks for 1Panel app-store lifecycle work and this compatibility entry must route the task into the canonical AgentPlane CLI-first 1Panel skills.
---

# 1Panel App Lifecycle Alias

## Overview

This is a compatibility alias, not a full execution skill. The execution truth stays `CLI-first`, with `uv run python -m agentplane.cli ...` as the stable entrypoint owned by the routed canonical skills.

## Router

- Installed 1Panel app objects, app-store state, and app-level verification: route to `onepanel-app-ops`
- Requests that are really about the mapped Compose project or runtime container state: route to `onepanel-container-ops`
- Post-change reconciliation, inventory refresh, or summary sync: route to `inventory-ledger-ops`

## Alias Rules

- Do not maintain a command catalog in this compatibility layer; concrete command examples belong in the routed canonical skill.
- Do not handcraft `/api/v2/apps/*` HTTP flows here.
- Keep WSL as the first execution target, and keep lifecycle-adjacent work in the canonical `plan/apply/verify/refresh` flow defined by the routed skill.
