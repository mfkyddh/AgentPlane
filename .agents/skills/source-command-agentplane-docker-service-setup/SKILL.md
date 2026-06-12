---
name: "source-command-agentplane-docker-service-setup"
description: "Install or repair repository-managed Docker Compose services such as PostgreSQL, Redis, MinIO, nginx-ui, CLIProxyAPI, or OpenClaw."
---

# source-command-agentplane-docker-service-setup

Use this skill when the user asks to run the migrated source command `agentplane-docker-service-setup`.

## Command Template

# Docker Service Setup

Use for initial setup or repair of repository-managed Docker Compose services.

## Rules

- Only for services that are repository-managed via Docker Compose
- After setup, verify service health

Full details: `.agents/skills/docker-service-setup/SKILL.md`

## Overview

Install or repair repository-managed Docker Compose services such as PostgreSQL, Redis, MinIO, nginx-ui, CLIProxyAPI, or OpenClaw.

## Commands

```bash
agentplane service
```

## Downstream Docs

See `.agents/skills/docker-service-setup/SKILL.md` for detailed documentation.
