---
name: onepanel-cronjob-ops
description: Use when the task is about 1Panel cronjobs, schedule inspection, manual trigger planning, or automation verification through the AgentPlane CLI.
---

# 1Panel Cronjob Ops

## Overview

Use the cronjob object CLI for search, detail, verification, and controlled mutation planning.

## Commands

```bash
uv run python -m agentplane.cli onepanel --env <target> cronjob search --info backup
uv run python -m agentplane.cli onepanel --env <target> cronjob get --id 2
uv run python -m agentplane.cli onepanel --env <target> cronjob verify --id 2
uv run python -m agentplane.cli onepanel --env <target> cronjob plan --mode handle --body-json '{"id":2}'
```

## Rules

- WSL is the first write-validation target.
- Keep cronjob changes auditable through ledgers and inventory.
