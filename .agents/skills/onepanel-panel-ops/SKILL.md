---
name: onepanel-panel-ops
description: Use when the task is about 1Panel panel settings, version baseline checks, bind-domain state, or panel-level verification through AgentPlane's CLI-first control plane.
---

# 1Panel Panel Ops

## Overview

Use the AgentPlane CLI as execution truth. Do not handcraft signed API calls in the skill.

## Commands

```bash
uv run python -m agentplane.cli onepanel --env <target> panel get
uv run python -m agentplane.cli onepanel --env <target> panel verify --key systemVersion
uv run python -m agentplane.cli onepanel --env <target> panel plan --key IpWhiteList --value 127.0.0.1
uv run python -m agentplane.cli onepanel --env <target> panel apply --key IpWhiteList --value 127.0.0.1 --execute
```

## Rules

- WSL is the first mutation test target.
- `apply` requires `--execute`.
- Refresh ledgers after panel-affecting changes.
