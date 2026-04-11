---
name: onepanel-container-ops
description: Use when the task is about container inspection, status verification, or container-level inventory alignment through the AgentPlane 1Panel CLI surface.
---

# 1Panel Container Ops

## Overview

Use the formal `service` domain for tracked runtime services before falling back to ad-hoc Docker commands.

## Commands

```bash
uv run python -m agentplane.cli service search --target <target> --repo-root /root/work/AgentPlane
uv run python -m agentplane.cli service get --target <target> --name newapi --repo-root /root/work/AgentPlane
uv run python -m agentplane.cli service verify --target <target> --name newapi --repo-root /root/work/AgentPlane
uv run python -m agentplane.cli service plan --target <target> --name newapi --operation restart --repo-root /root/work/AgentPlane
uv run python -m agentplane.cli service apply --target <target> --name newapi --operation restart --execute --repo-root /root/work/AgentPlane
```

## Rules

- 公开运行态入口只接受 inventory 中已声明的 tracked service name。
- `onepanel container` 已退出公开默认入口；provider/debug 只留在低层 substrate。
- 仅对仓库已稳定验证的运行态操作使用 `apply --execute`。
