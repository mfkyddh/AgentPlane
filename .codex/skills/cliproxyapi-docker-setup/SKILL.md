---
name: cliproxyapi-docker-setup
description: Use when Codex needs to install, upgrade, redeploy, or repair router-for-me/CLIProxyAPI in Docker for this Ubuntu or WSL repository, especially when pinning a verified image digest, fixing Docker pull failures, checking WSL-to-Windows localhost forwarding, or verifying the management and API endpoints after deployment.
---

# CLIProxyAPI Docker Setup

Deploy, upgrade, or repair `router-for-me/CLIProxyAPI` as a project-local Docker service inside this repository. Reuse the repository's Docker layout conventions, keep long-lived data under `/data/cliproxyapi`, and make the resulting instance safe-by-default for local development.

## Quick Objective

- Fresh install: create or refresh `infra/compose/cliproxyapi/docker-compose.wsl.yml`, `infra/compose/cliproxyapi/docker-compose.prod0.yml`, `infra/compose/cliproxyapi/config.yaml`, `infra/compose/cliproxyapi/.env.wsl`, and `infra/compose/cliproxyapi/.env.prod0`, create the live config at `/data/cliproxyapi/config/config.yaml`, then start the intended environment and verify `/v1/models`.
- Upgrade: verify the latest upstream release, pull the corresponding official image, pin the new digest in both tracked env files, recreate the container, and verify the running version from logs.
- Repair: keep existing secrets and auth data, fix image pull or network issues first, then restart and re-test the API.

## Workflow

1. Verify the real WSL repository path, effective Linux user, Docker availability, and that `zqf_network` already exists.
2. Inspect the existing `infra/compose/cliproxyapi/` files plus `/data/cliproxyapi/config/config.yaml` before editing so upgrades preserve the current password, API key, proxy, and callback ports unless the user asked to rotate them.
3. Verify the target upstream version from the official GitHub releases page or repository tags before changing anything, then inspect the upstream `router-for-me/CLIProxyAPI` repository so the expected ports, mounts, and config fields match the current project state.
4. Pull the official Docker image tag for the requested version and capture the verified digest.
5. Pin the verified digest in both `infra/compose/cliproxyapi/.env.wsl` and `infra/compose/cliproxyapi/.env.prod0`; do not leave the service on a floating tag.
6. Create or update `infra/compose/cliproxyapi/docker-compose.wsl.yml`, `infra/compose/cliproxyapi/docker-compose.prod0.yml`, `infra/compose/cliproxyapi/config.yaml`, the tracked env files, and the live config at `/data/cliproxyapi/config/config.yaml` with the chosen official image, port bindings, and generated or preserved secrets.
7. Keep the service attached to `zqf_network`, use canonical container names `cli-proxy-api-dev` and `cli-proxy-api-prod`, publish the repository-managed API on `0.0.0.0:8318`, and persist auth state plus logs under `/data/cliproxyapi/auths` and `/data/cliproxyapi/logs`.
8. On current releases such as `v6.9.1`, the container also listens on `8318`, so the compose API mapping must be host `8318` to container `8318`; do not carry forward an old `8318:8317` mapping from older assumptions.
9. On current releases such as `v6.9.1`, the management UI is served from the same listener as the API, so the canonical local management entrypoint remains `http://127.0.0.1:8318/management.html`; do not keep a dead `8085` port mapping just for legacy symmetry.
10. If the user wants to edit config through the management API or UI, do not mount `/data/cliproxyapi/config/config.yaml` as read-only; the bind mount must stay writable or saves will fail with write errors.
11. If CLIProxyAPI must use a proxy running on the Windows host while the service runs in Docker under WSL, do not set `proxy-url` to `127.0.0.1` or `localhost` inside the container. Use the current WSL default gateway IP as the host address in `config.yaml`, for example `http://<wsl-default-gateway>:7890`.
12. If Docker image pulls time out in this WSL environment, inspect `/etc/docker/daemon.json`, confirm the configured registry mirrors, and check whether the Docker daemon itself needs `HTTP_PROXY` and `HTTPS_PROXY` pointed at the current WSL gateway proxy. In this repository, `docker.1ms.run` is the preferred mirror and `docker.m.daocloud.io` is a good fallback when reachable.
13. If the management panel static asset is missing, persist `/CLIProxyAPI/static` to `/data/cliproxyapi/static` and pre-seed the official `management.html` release asset there so `/management.html` remains available after restarts.
14. The legacy `/root/cliproxyapi` binary deployment has been removed from this workspace baseline; keep the repository-managed Docker service on `8318`, and treat `8317` as free unless a user explicitly introduces another unmanaged local instance.
15. Start or restart the intended environment with `docker compose --env-file infra/compose/cliproxyapi/.env.wsl -f infra/compose/cliproxyapi/docker-compose.wsl.yml up -d` or `docker compose --env-file infra/compose/cliproxyapi/.env.prod0 -f infra/compose/cliproxyapi/docker-compose.prod0.yml up -d`, verify the container status, inspect logs, and test a basic authenticated endpoint such as `/v1/models`.
16. When performing an upgrade, verify the running version string from container logs or process output after restart and confirm the container image digest matches the pinned digest.
17. If WSL can reach `127.0.0.1:8318` but Windows cannot reach `http://127.0.0.1:8318`, test the direct WSL IP from Windows first and bypass local proxy settings while testing, for example with `curl.exe --noproxy '*'` or PowerShell `Invoke-WebRequest -Proxy $null`. If the direct WSL IP works but Windows `localhost` still hangs, refresh WSL localhost forwarding with `wsl.exe --shutdown`, then re-test after WSL boots again.
18. Report the management password and at least one client API key clearly in the final response when the password is actually known in plaintext. If only the bcrypt `secret-key` hash is available, say that the plaintext password is not recoverable from the current files and offer to rotate it instead. Then explain the next step that still requires user credentials: adding upstream API keys or running OAuth login flows for Codex, Claude, Gemini, Qwen, or iFlow.

## File Layout

- `infra/compose/cliproxyapi/docker-compose.wsl.yml`
- `infra/compose/cliproxyapi/docker-compose.prod0.yml`
- `/data/cliproxyapi/config/config.yaml`
- `infra/compose/cliproxyapi/.env.wsl`
- `infra/compose/cliproxyapi/.env.prod0`

## Notes

- CLIProxyAPI does not require Postgres by default; local file-backed auth storage is enough for a first deployment.
- Prefer the official published CLIProxyAPI image and pin the exact version tag or digest after verifying it.
- Prefer preserving existing management secrets and API keys during upgrades unless the user explicitly asks to rotate them.
- Treat `docker pull` failures separately from container runtime failures; on this machine, registry mirror timeouts and missing Docker daemon proxy settings are a common upgrade blocker.
- When Docker logs mention `registry-1.docker.io` together with `Host doesn't match ... host=docker.1ms.run`, infer that Docker is still pulling via the configured mirror rather than bypassing it.
- When diagnosing Windows access, remember that this machine often sets `HTTP_PROXY`, `HTTPS_PROXY`, and `ALL_PROXY` on the Windows side. A 502 from `curl.exe` to the WSL IP often means the request went through the local proxy rather than directly to WSL.
- Keep config comments concise and practical so future edits are easy to reason about.
- Update `AGENTS.md` when you discover a durable rule such as required callback ports or local-only exposure defaults.
