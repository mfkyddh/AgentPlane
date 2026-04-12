---
name: onepanel-container-ops
description: Use when the task is about container inspection, status verification, or container-level inventory alignment through the AgentPlane 1Panel CLI surface.
---

# 1Panel Container Ops

## Overview

Use the formal `service` domain for tracked runtime services before falling back to ad-hoc Docker commands.

## Commands

```bash
uv run python -m agentplane.cli service search --target <target> --repo-root <repo-root>
uv run python -m agentplane.cli service get --target <target> --name <service> --repo-root <repo-root>
uv run python -m agentplane.cli service verify --target <target> --name <service> --repo-root <repo-root>
uv run python -m agentplane.cli service plan --target <target> --name <service> --operation restart --repo-root <repo-root>
uv run python -m agentplane.cli service apply --target <target> --name <service> --operation restart --execute --repo-root <repo-root>
```

## Rules

- 公开运行态入口只接受 inventory 中已声明的 tracked service name。
- `onepanel container` 已退出公开默认入口；provider/debug 只留在低层 substrate。
- 仅对仓库已稳定验证的运行态操作使用 `apply --execute`。
