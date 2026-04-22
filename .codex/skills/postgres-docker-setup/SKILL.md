---
name: postgres-docker-setup
description: Install or upgrade PostgreSQL 18.x in Ubuntu or WSL using Docker Compose, store the project files under infra/compose/postgres, keep PostgreSQL data under /data/postgres/data, pin the requested image tag, connect the service to zqf_network, and verify container health, version, connectivity, and persistence. Use when Codex is asked to set up PostgreSQL in Docker for local development, reorganize PostgreSQL Docker files, or fix PostgreSQL persistence and network wiring in this repository.
---

# Postgres Docker Setup

Set up PostgreSQL 18.x as a small local development service using Docker Compose, with a fixed image tag, repository files under `infra/compose/postgres`, and host data persisted under `/data/postgres/data`.

## Workflow

1. Verify the requested PostgreSQL image tag exists on the official Docker Hub page before editing compose because patch tags change over time.
2. Detect the effective Linux user, `HOME`, the real WSL repository path, Docker availability, and whether the intended user can access `/var/run/docker.sock`.
3. If the intended user lacks Docker socket access, either add that user to the `docker` group and verify in a fresh login shell, or run Docker commands as `root` if the user asked to proceed immediately.
4. Confirm the deployment shape before writing files: fixed image tag, host port, host data path, default database name, default application user, password generation policy, and whether to join `zqf_network`.
5. Create or update `infra/compose/postgres/docker-compose.wsl.yml` and `infra/compose/postgres/docker-compose.prod0.yml`. Keep them minimal: one `postgres` service, fixed `postgres:<tag>` image, `restart: unless-stopped`, `shm_size` sized for small workloads, published host port `0.0.0.0:5432:5432`, host bind mount `/data/postgres/data:/var/lib/postgresql`, and the explicit external Docker network required by the project.
6. Store credentials and bootstrap values in `infra/compose/postgres/.env` when the user wants a reusable local setup. Use `POSTGRES_DB`, `POSTGRES_USER`, and either the user-provided password or a generated password.
7. For PostgreSQL 18 official images, set `PGDATA` under `/var/lib/postgresql/<major>/docker` so the bind-mounted data stays aligned with the versioned cluster layout used by the image.
8. Add a health check with `pg_isready`, create `/data/postgres/data` before startup, then run `docker compose up -d` from the repository's `infra/compose/postgres` directory.
9. Verify `docker ps`, health status, `SELECT version();`, basic connectivity using the created application database and user, and that initialized data appears under `/data/postgres/data`.
10. If you learn a new durable environment pitfall, update `AGENTS.md` in the same turn.

## File Layout

Use this repository layout:

```text
infra/compose/postgres/
  docker-compose.wsl.yml
  docker-compose.prod0.yml
```

Do not leave PostgreSQL compose files at the repository root when the task is specifically for this project.

## Recommended Compose Baseline

Use a small, commented compose file shaped like this, then adapt to the user's request:

```yaml
services:
  postgres:
    image: postgres:18.3
    container_name: postgres18-dev
    restart: unless-stopped
    shm_size: 256mb
    environment:
      TZ: Asia/Shanghai
      POSTGRES_DB: ${POSTGRES_DB}
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      PGDATA: /var/lib/postgresql/18/docker
    ports:
      - "0.0.0.0:5432:5432"
    volumes:
      - /data/postgres/data:/var/lib/postgresql
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U $$POSTGRES_USER -d $$POSTGRES_DB"]
      interval: 10s
      timeout: 5s
      retries: 10
      start_period: 20s
    networks:
      - zqf_network

networks:
  zqf_network:
    external: true
```

## Command Pattern

Prefer explicit WSL user targeting:

```bash
wsl -d Ubuntu -u <user> bash -lc '...'
```

Create the host data directory:

```bash
mkdir -p /data/postgres/data
```

Start PostgreSQL:

```bash
cd <repo-root>/infra/compose/postgres
docker compose up -d
```

Verify health and version:

```bash
docker inspect -f '{{.State.Health.Status}}' postgres18-dev
docker exec postgres18-dev psql -U <user> -d <db> -tAc "SELECT version();"
```

Check persistence output:

```bash
find /data/postgres/data -maxdepth 3 | sort | head -n 20
```

## Notes

- In this repository, both the WSL and prod0 tracked compose templates publish PostgreSQL on `0.0.0.0:5432`.
- In this repository, prefer the existing external Docker network `zqf_network` when wiring PostgreSQL to other local services.
- Keep the requested image tag fixed. If the user says "latest" but also asks to pin a version, verify the latest patch tag first and then write that exact tag.
- Report the exact image tag, compose path, host port, host data path, generated or supplied credentials, and validation results after setup.
