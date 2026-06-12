---
name: "source-command-agentplane-tencent-migration"
description: "Migrate infrastructure or control-plane services between Example Cloud hosts, keeping source host unchanged and validating destination before cutover."
---

# source-command-agentplane-tencent-migration

Use this skill when the user asks to run the migrated source command `agentplane-tencent-migration`.

## Command Template

# Tencent Cloud Service Migration

Use when moving PostgreSQL, Redis, MinIO, nginx-ui, or control-plane assets between active cloud hosts tracked by the repository.

## Rules

- Never blindly copy entire machine state
- Validate destination host before cutover
- Keep source host unchanged

Full details: `.agents/skills/tencent-cloud-service-migration/SKILL.md`

## Overview

Migrate infrastructure or control-plane services between Example Cloud hosts, keeping source host unchanged and validating destination before cutover.

## Commands

```bash
agentplane infra
```

## Downstream Docs

See `.agents/skills/tencent-cloud-service-migration/SKILL.md` for detailed documentation.
