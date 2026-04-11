---
name: tencent-cloud-service-migration
description: Migrate infrastructure or control-plane services from this repository's active Tencent Cloud host to another explicitly scoped host from WSL, keeping the source host unchanged, reusing project SSH aliases, copying only the intended runtime config, and validating the destination host before cutover. Use when Codex is asked to move PostgreSQL, Redis, MinIO, nginx-ui, 1Panel-adjacent control-plane assets, or similar host-local services from `prod0-main` to another approved host, or between active cloud hosts tracked by the repository.
---

# Tencent Cloud Service Migration

Use this skill when the user wants to recreate services on another Tencent Cloud host in this repository without blindly copying an entire machine.

## Workflow

1. Start from WSL and use the project SSH aliases in `secrets/ssh/config`. Treat `prod0-main` as the verified current source endpoint; any destination host must be explicitly named and present in repository inventory before migration begins.
2. Verify the source host's real runtime shape before planning the migration. Do not trust old inventory alone; confirm containers, port bindings, mounts, and live config with `docker ps`, `docker inspect`, and direct file reads on the source host.
3. Lock the migration scope explicitly:
   - infrastructure only: recreate containers and credentials but do not copy business data
   - config migration: copy the selected runtime config directories or files
   - blank control plane: deploy the destination service with empty state when the user wants a fresh management plane
4. Keep the source host unchanged. Do not stop, rebuild, reload, or rewrite the source host unless the user explicitly asks for cutover work there.
5. For Dockerized data services in this repository, prefer shipping the tracked compose assets plus selected files from `secrets/services/` to the destination host and running a deterministic remote script from `/tmp/env_ubuntu_deploy`.
6. When bind-mounted runtime files are copied under a destination path such as `/opt/env_ubuntu/secrets`, ensure the deployed directories stay traversable and any files read by non-root container processes remain readable enough inside the container.
7. If the destination host cannot pull a required image but the source host already has it locally, stream it with `docker save | docker load` instead of debugging registries first.
8. For `nginx-ui-prod` migrations, copy only the intended control-plane directories, currently `/data/apps/nginx-ui-official/nginx` and `/data/apps/nginx-ui-official/nginx-ui`, then retarget domain names, certificate paths, and upstreams for the destination host before reloading Nginx.
9. If the destination host's Docker daemon hits `EOF` through `https://mirror.ccs.tencentyun.com`, put `https://docker.1ms.run` first in `/etc/docker/daemon.json` `registry-mirrors`, keep the Tencent mirror as fallback, restart Docker, and retry the pull before inventing a new image source.
10. For `nginx-ui-prod` reverse proxies on an explicit public port such as `8443`, preserve the incoming host and port with `proxy_set_header Host $http_host`; using `$host` can make nginx-ui WebSocket self-checks fail with `request origin not allowed`.
12. Validate the destination host from both layers:
   - direct local upstream checks such as `127.0.0.1:<port>`
   - front-door checks such as `curl -kI -H 'Host: <fqdn>' https://127.0.0.1:8443`
13. Update repository inventory and durable rules in the same turn when the migration reveals live behavior that differs from tracked docs.

## Repository-Specific Patterns

- Data-service infrastructure-only migration currently uses:
  - `ops/scripts/remote/deploy_data_services_to_host.sh`
  - `ops/scripts/remote/remote_deploy_data_services.sh`
- `nginx-ui-prod` migration currently uses:
  - `ops/scripts/remote/deploy_nginx_ui_to_host.sh`
  - `ops/scripts/remote/remote_deploy_nginx_ui.sh`
- `prod0-main` is the current `zzzai.cloud` host.

## Cloudflare Notes

- For account-owned Cloudflare tokens in this repository, verify them with:
  `GET /accounts/<account_id>/tokens/verify`
- Do not treat `GET /user/tokens/verify` as authoritative for these tokens; it can report `Invalid API Token` even while the account token is active.
- Zone DNS writes still require the token resource scope to include the target zone explicitly.

## Verification Checklist

- Source host services still run unchanged after migration.
- Destination host containers match the intended image, mounts, and port bindings.
- Destination host local checks succeed for each migrated service.
- If domains are part of the migration, Cloudflare DNS points only to the destination host and the destination reverse proxy routes each host header to the intended upstream.
- For nginx-ui migrations on `8443`, the destination no longer logs repeated `websocket: request origin not allowed` errors during UI self-check.
- Any intentionally missing upstream, such as an uninstalled `127.0.0.1:18080`, is called out explicitly as a known partial state instead of being mistaken for a failed migration.
