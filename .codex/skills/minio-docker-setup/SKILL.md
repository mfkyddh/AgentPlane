---
name: minio-docker-setup
description: Install or redeploy MinIO in Ubuntu or WSL using Docker Compose, store the project files under infra/compose/minio, keep MinIO data and config under /data, pin the requested MinIO image tag, connect the service to zqf_network, and verify container, health endpoints, and persistence. Use when Codex is asked to set up MinIO in Docker for local development, reorganize MinIO Docker files, or fix MinIO storage and network wiring in this repository.
---

# MinIO Docker Setup

Set up MinIO as a small local development service using Docker Compose, with a fixed image tag, repository files under `infra/compose/minio`, and host data persisted under `/data/minio`.

## Workflow

1. Confirm the exact MinIO image tag the user wants before editing compose. If the user provided a fixed tag, keep it pinned.
2. Detect the effective Linux user, `HOME`, Docker availability, and whether the intended user can access `/var/run/docker.sock`.
3. If the intended user lacks Docker socket access, either add that user to the `docker` group and verify in a fresh login shell, or run Docker commands as `root` if the user asked to proceed immediately.
4. Create or update `infra/compose/minio/docker-compose.wsl.yml` and `infra/compose/minio/docker-compose.prod0.yml`.
5. Keep the compose file minimal: one `minio` service, fixed image tag, `container_name: minio-dev`, `restart: unless-stopped`, port mappings for `9000` and `9001`, environment variables for timezone and credentials, host bind mounts for data and config under `/data/minio`, `command: server --address ":9000" --console-address ":9001" /data`, and the explicit Docker network required by the project.
6. Unless the user explicitly requires it, do not add `privileged: true`; MinIO local development does not need elevated container privileges.
7. Create `/data/minio/data` and `/data/minio/config` before startup, then run `docker compose up -d` from `/root/work/env_ubuntu/infra/compose/minio`.
8. Verify `docker ps`, MinIO health endpoints, network wiring, and that files appear under `/data/minio/data` and `/data/minio/config`.
9. If you learn a new durable environment pitfall, update `AGENTS.md` in the same turn.

## File Layout

Use this repository layout:

```text
infra/compose/minio/
  docker-compose.wsl.yml
  docker-compose.prod0.yml
```

Do not leave MinIO compose files at the repository root when the task is specifically for this project.

## Recommended compose Baseline

Use a small, commented compose shaped like this, then adapt to the user request:

```yaml
services:
  minio:
    image: minio/minio:<fixed-tag>
    container_name: minio-dev
    restart: unless-stopped
    ports:
      - "9000:9000"
      - "9001:9001"
    environment:
      TZ: Asia/Shanghai
      MINIO_ROOT_USER: <user>
      MINIO_ROOT_PASSWORD: <password>
      MINIO_COMPRESS: "off"
      MINIO_COMPRESS_EXTENSIONS: ""
      MINIO_COMPRESS_MIME_TYPES: ""
    volumes:
      - /data/minio/data:/data
      - /data/minio/config:/root/.minio
    command: server --address ":9000" --console-address ":9001" /data
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

Create the host directories:

```bash
mkdir -p /data/minio/data /data/minio/config
```

Start MinIO:

```bash
cd /root/work/env_ubuntu/infra/compose/minio
docker compose up -d
```

Verify health and network:

```bash
docker ps --filter name=minio-dev
docker inspect -f '{{json .NetworkSettings.Networks}}' minio-dev
curl -fsS http://127.0.0.1:9000/minio/health/live
curl -fsS http://127.0.0.1:9000/minio/health/ready
```

Check persistence output:

```bash
find /data/minio -maxdepth 2 -type f | sort
```

## Notes

- In this repository, prefer the existing external Docker network `zqf_network` when wiring MinIO to other local services.
- Keep object data at `/data/minio/data` and MinIO config at `/data/minio/config`.
- In this repository's WSL test environments, MinIO should use the canonical container name `minio-dev`.
- Comment every important compose field so the user can maintain the file without guessing.
- Report exact image tag, compose path, credentials state, port bindings, network, and persistence paths after setup.
