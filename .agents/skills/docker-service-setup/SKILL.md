---
name: docker-service-setup
description: Use for installing or repairing repository-managed Docker Compose services such as PostgreSQL, Redis, MinIO, nginx-ui, CLIProxyAPI, or OpenClaw after deciding that a formal AgentPlane service setup workflow is needed.
---

# Docker Service Setup

## Overview

Use this workflow skill for initial setup or repair of repository-managed Docker Compose services. It replaces the per-service setup skills for PostgreSQL, Redis, MinIO, nginx-ui, CLIProxyAPI, and OpenClaw Docker.

Prefer a formal AgentPlane CLI workflow when one exists. When the repository has not yet wrapped a setup task, keep the raw compose work scoped to `infra/compose/<service>` and turn durable lessons into templates, tests, or reference docs.

## Commands

```bash
uv run python -m agentplane.cli infra remote bash <target> -- docker version
uv run python -m agentplane.cli infra secrets sync-layout <target> --repo-root <repo-root> --write
uv run python -m agentplane.cli service search --target <target> --repo-root <repo-root>
uv run python -m agentplane.cli service verify --target <target> --name <service> --repo-root <repo-root>
```

If compose is still the implementation path, use the tracked service directory:

```bash
docker compose -f infra/compose/<service>/docker-compose.<target>.yml up -d
```

## Service Baselines

| Service | Compose root | Persistent data expectation |
| --- | --- | --- |
| PostgreSQL | `infra/compose/postgres` | `/data/postgres/data` |
| Redis | `infra/compose/redis` | `/data/redis/data` |
| MinIO | `infra/compose/minio` | `/data/minio/data` and `/data/minio/config` |
| nginx-ui | `infra/compose/nginxwebui` or provider-specific successor | `/data` backed application state |
| CLIProxyAPI | `infra/compose/cliproxyapi` | service env and management auth under secrets |
| OpenClaw Docker | `infra/compose/openclaw` | `/data/openclaw` |

## Rules

- Pin images or upstream source versions when the service becomes durable.
- Keep real env files under `secrets/`; tracked files are templates only.
- Verify container health, endpoint behavior, and persistence after restart.
- After setup, route normal runtime operations back to `agentplane-service-ops`.

## Downstream Docs

- `docs/reference/container-conventions.md`
- `docs/reference/repository-structure.md`
