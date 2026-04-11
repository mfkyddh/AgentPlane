---
name: onepanel-app-ops
description: Use when the task is about installed 1Panel apps, app-store state, or app-level verification through the AgentPlane CLI-first control plane.
---

# 1Panel App Ops

## Overview

Use `app` for catalog/object truth, `service` for runtime restart/reconcile, and `app delivery` for contract/build/deploy flows. Keep this skill `CLI-first`.

## Commands

```bash
uv run python -m agentplane.cli app object search --target <target> --repo-root /root/work/AgentPlane
uv run python -m agentplane.cli app object get --target <target> --app <app> --repo-root /root/work/AgentPlane
uv run python -m agentplane.cli app object verify --target <target> --app <app> --repo-root /root/work/AgentPlane
uv run python -m agentplane.cli service get --target <target> --name newapi --repo-root /root/work/AgentPlane
uv run python -m agentplane.cli service plan --target <target> --name newapi --operation restart --repo-root /root/work/AgentPlane
uv run python -m agentplane.cli service apply --target <target> --name newapi --operation restart --execute --repo-root /root/work/AgentPlane
uv run python -m agentplane.cli app delivery validate-contract --target <target> --app <app> --repo-root /root/work/AgentPlane
```

## Rules

- `app` 公开域只做 catalog/object truth 与 delivery 流程，不承接 raw installed-app CRUD。
- app 运行态 restart/reconcile 统一走 `service`，不要回退到 `onepanel app/project`。
- Do not call `/api/v2/apps/*` directly from the skill.
