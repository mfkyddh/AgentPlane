---
name: redis-docker-setup
description: Install or upgrade Redis 7.x in Ubuntu or WSL using Docker Compose, store the project files under infra/compose/redis, keep Redis data under /data, write a minimal fully commented redis.conf, and verify container, auth, and persistence. Use when Codex is asked to set up Redis in Docker for local development, reorganize Redis Docker files, or fix Redis persistence and docker socket access in this repository.
---

# Redis Docker Setup

Set up Redis 7.x as a small local development service using Docker Compose, with a fixed current 7.x image tag, repository files under `infra/compose/redis`, and host data persisted under `/data/redis/data`.

## Workflow

1. Verify the current Redis 7.x Docker tag before editing compose because the latest patch version changes over time.
2. Detect the effective Linux user, `HOME`, Docker availability, and whether the intended user can access `/var/run/docker.sock`.
3. If the intended user lacks Docker socket access, either add that user to the `docker` group and verify in a fresh login shell, or run Docker commands as `root` if the user asked to proceed immediately.
4. Create or update `infra/compose/redis/docker-compose.wsl.yml` and `infra/compose/redis/docker-compose.prod0.yml`, plus `infra/compose/redis/redis.conf` when needed.
5. Keep each compose file minimal: one `redis` service, fixed image tag, `restart: unless-stopped`, published host port `0.0.0.0:6379:6379`, host bind mount `/data/redis/data:/data`, `command: ["redis-server", "/usr/local/etc/redis/redis.conf"]`, and the explicit Docker network required by the project.
6. Keep `redis.conf` minimal but fully commented. Include only settings the user asked for or that materially improve a local dev setup.
7. When the user wants password auth, set `requirepass <value>` and verify with authenticated `redis-cli`.
8. Create `/data/redis/data` before startup, then run `docker compose up -d` from `/root/work/env_ubuntu/infra/compose/redis`.
9. Verify `docker ps`, Redis version, authenticated `PING`, and that persistence files appear under `/data/redis/data`.
10. If you learn a new durable environment pitfall, update `AGENTS.md` in the same turn.

## File Layout

Use this repository layout:

```text
infra/compose/redis/
  docker-compose.wsl.yml
  docker-compose.prod0.yml
  redis.conf
```

Do not leave Redis compose files at the repository root when the task is specifically for this project.

## Recommended redis.conf Baseline

Use a small, commented config shaped like this, then adapt to the user request:

```conf
bind 0.0.0.0
protected-mode yes
requirepass <password-if-requested>
# notify-keyspace-events Ex
port 6379
daemonize no
dir /data
save 900 1
save 300 10
save 60 10000
rdbcompression yes
dbfilename dump.rdb
appendonly yes
appendfilename "appendonly.aof"
appendfsync everysec
loglevel notice
logfile ""
```

## Command Pattern

Prefer explicit WSL user targeting:

```bash
wsl -d Ubuntu -u <user> bash -lc '...'
```

Create the host data directory:

```bash
mkdir -p /data/redis/data
```

Start Redis:

```bash
cd /root/work/env_ubuntu/infra/compose/redis
docker compose up -d
```

Verify auth and version:

```bash
docker exec redis7-dev redis-cli -a <password> PING
docker exec redis7-dev redis-cli -a <password> INFO server | grep '^redis_version:'
```

Check persistence output:

```bash
find /data/redis/data -maxdepth 2 -type f | sort
```

## Notes

- Keep the container path as `/data` even if the host path is `/data/redis/data`; this keeps the Redis config simpler.
- In this repository, both the WSL and prod0 tracked compose templates publish Redis on `0.0.0.0:6379`.
- In this repository, prefer the existing external Docker network `zqf_network` when wiring Redis to other local services.
- Comment every non-default Redis setting so the user can maintain the file without guessing.
- Report exact image tag, compose path, password state, port binding, and persistence path after setup.
