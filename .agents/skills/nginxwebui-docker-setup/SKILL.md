---
name: nginxwebui-docker-setup
description: Deploy or redeploy nginxWebUI or the official nginx-ui Docker image on Ubuntu or WSL, persist application data under /data when the user prefers that layout, expose the management UI only through the intended port or reverse proxy, and verify both HTTP and WebSocket health after startup. Use when Codex is asked to install nginxWebUI/nginx-ui, move its data to /data, repair public access, or document a production nginx-ui deployment.
---

# nginxWebUI Docker Setup

Deploy nginxWebUI or the official nginx-ui container in a way that matches the host's existing public-access pattern.

## Workflow

1. Check the currently used host ports and identify which deployment style already exists on the target host:
   - legacy single-container `cym1102/nginxwebui`
   - official `uozi/nginx-ui` control plane, canonically named `nginx-ui-prod` on Tencent Cloud production hosts
2. For this repository's Tencent Cloud hosts, prefer the official image `uozi/nginx-ui:<tag>` when the host already runs or should be migrated to `nginx-ui-prod`.
3. If Docker pulls fail with `EOF` through `https://mirror.ccs.tencentyun.com`, put `https://docker.1ms.run` first in `/etc/docker/daemon.json` `registry-mirrors`, keep the Tencent mirror as fallback, restart Docker, then retry the pull.
4. When the user wants data under `/data` and the host uses the official image, mount:
   - `/data/apps/nginx-ui-official/nginx:/etc/nginx`
   - `/data/apps/nginx-ui-official/nginx-ui:/etc/nginx-ui`
5. For this repository's public Tencent Cloud deployment, keep `nginx-ui-prod` on Docker `infra` network and let Nginx listen on `8443`.
6. If browsers get `200` with an empty body in direct public tests, keep nginxWebUI itself behind loopback and add a tiny external reverse proxy as the stable workaround.
7. When reverse-proxying nginx-ui on an explicit public port such as `8443`, use `proxy_set_header Host $http_host` instead of `$host`; otherwise nginx-ui WebSocket self-checks can fail with `request origin not allowed`.
8. Do not treat the header banner `Self check failed, Nginx UI may not work properly` as proof that backend self-check items failed. The banner also depends on a frontend WebSocket probe to `/api/self_check/websocket`; if `/api/self_check` is all green and the WebSocket handshake returns `101 Switching Protocols`, the server-side configuration is usually fine and the remaining issue is often a stale browser session, stale token, or cached frontend state.
9. On `prod0-main`, the preferred active-site layout is:
   - active site files in `/data/apps/nginx-ui-official/nginx/sites-available/`
   - enable symlinks in `/data/apps/nginx-ui-official/nginx/sites-enabled/`
   - keep `stub_status_nginx-ui.conf` in `/data/apps/nginx-ui-official/nginx/conf.d/`
   If active sites are left only in `conf.d/`, Nginx still works, but nginx-ui's site-status scanner will mark those sites as `disabled` because it checks for `sites-enabled` symlinks.
10. If you migrate active site files from `conf.d/` to `sites-available/`, move the live files out of `conf.d/` instead of copying them. Leaving the same live `server` blocks in both places causes duplicate loads. Back up the original files first, create symlinks under `sites-enabled/`, run `nginx -t`, then reload.
11. Wait briefly after startup or layout changes, then verify with `docker ps`, `docker logs --tail`, and both front-door and upstream checks.
12. Record the published URL, image, data directory, site-layout decisions, and any reverse-proxy caveats in the local server inventory.

## Canonical Command Shape

```bash
docker run -d \
  --name nginx-ui-prod \
  --restart unless-stopped \
  --network host \
  -v /data/apps/nginx-ui-official/nginx:/etc/nginx \
  -v /data/apps/nginx-ui-official/nginx-ui:/etc/nginx-ui \
  -v /var/run/docker.sock:/var/run/docker.sock \
  uozi/nginx-ui:2.3.5
```

## Verification Checklist

- `docker ps --filter name=nginx-ui-prod` shows the container as running
- `curl -kI https://127.0.0.1:8443` returns an HTTP response on this repository's Tencent Cloud layout
- `curl -kI -H 'Host: <fqdn>' https://127.0.0.1:8443` reaches the intended vhost
- If the UI reports self-check failure, inspect logs for `request origin not allowed`; that usually means the reverse proxy passed `$host` instead of `$http_host`
- If `/api/self_check` is fully `success`, also test `/api/self_check/websocket` with a valid token and a real WebSocket upgrade; `101 Switching Protocols` means the frontend self-check path is healthy
- If nginx-ui marks live sites as disabled, verify that active site files exist under `sites-available/` and that matching symlinks exist under `sites-enabled/`
- The persistent data directories exist under `/data/apps/nginx-ui-official`

## Notes

- Legacy deployments still exist with `cym1102/nginxwebui`, but this repository's current canonical Tencent Cloud shape uses the official `uozi/nginx-ui` image and `nginx-ui-prod` container name.
- On this repository's Tencent Cloud host, single-container self-proxy tests still produced blank public pages for browser clients, while a tiny external reverse-proxy container worked reliably.
- On `prod0-main`, `nginx-ui-prod` self-check, analytics, and log WebSockets can false-fail if the reverse proxy drops the explicit `:8443` from the `Host` header.
- On `2026-03-24`, `prod0-main` uses the active site files `1panel.conf`, `nginx-ui.conf`, `pay.zzzai.cloud.conf`, and `zzzai-sub2api.conf` in `sites-available/` with matching symlinks in `sites-enabled/`; nginx-ui then reports `Collected 4 enabled sites`.
