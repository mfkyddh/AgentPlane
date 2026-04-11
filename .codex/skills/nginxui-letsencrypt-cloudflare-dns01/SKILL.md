---
name: nginxui-letsencrypt-cloudflare-dns01
description: Issue or repair public Let's Encrypt certificates for this repository's Tencent Cloud nginx-ui deployments when Cloudflare is set to grey-cloud direct access or when port 80/443 validation is unavailable. Use when Codex is asked to replace self-signed or Cloudflare Origin certificates on `prod0-main` or similar hosts, obtain certs through Cloudflare DNS-01, sync them into `/data/apps/nginx-ui-official/nginx/certs`, and install automatic renewal plus nginx reload. The canonical container name is `nginx-ui-prod`.
---

# nginx-ui Let's Encrypt via Cloudflare DNS-01

Use this skill when a Tencent Cloud host in this repository serves HTTPS through `nginx-ui-prod` on `8443`, but the current certificate is self-signed or Cloudflare Origin CA and the domain now needs direct browser trust after switching Cloudflare from orange-cloud proxy to grey-cloud direct access.

## Workflow

1. Start from WSL and use the project SSH aliases in `secrets/ssh/config`.
   The common target for this workflow is:
   - `prod0-main` for `175.178.114.192` / `zzzai.cloud`

2. Confirm the current HTTPS layout before changing certificates.
   Check:
   - `sudo docker ps --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}'`
   - current nginx config under `/data/apps/nginx-ui-official/nginx/conf.d/`
   - current certificate files under `/data/apps/nginx-ui-official/nginx/certs/`
   - local SNI result with `openssl s_client -connect 127.0.0.1:8443 -servername <fqdn>`

3. Do not assume HTTP-01 will work.
   On this repository's Tencent hosts, UFW commonly allows only `22/tcp` and `8443/tcp`.
   If `80/tcp` or `443/tcp` is not open, skip HTTP-01 and use Cloudflare DNS-01 directly.

4. Reuse the repository Cloudflare token from `secrets/env/prod-jump.env`.
   Prefer validating zone access with:
   ```bash
   curl -H "Authorization: Bearer $CLOUDFLARE_API_TOKEN" \
     "https://api.cloudflare.com/client/v4/zones?name=zzzai.cloud"
   ```
   Do not rely on `/user/tokens/verify` alone for this repository's token shape; zone read/edit access is the real gate.

5. Prepare a persistent Let’s Encrypt working directory on the host:
   - `/data/apps/letsencrypt`
   - `/data/apps/letsencrypt/lib`
   - `/data/apps/letsencrypt/cloudflare.ini`

   The credential file must be mode `600` and use:
   ```ini
   dns_cloudflare_api_token = <token>
   ```

6. On hosts where outbound internet needs Mihomo, run Certbot through Docker with `--network host` and the host proxy.
   The working proxy path on `prod0-main` is:
   ```text
   http://172.18.0.1:7890
   ```
   Container bridge networking did not reliably reach either the proxy or Let's Encrypt in this environment, while `--network host` did.

7. Dry-run first with DNS-01 and a longer propagation wait.
   A working command shape is:
   ```bash
   sudo docker run --rm --network host \
     -e HTTPS_PROXY=http://172.18.0.1:7890 \
     -e HTTP_PROXY=http://172.18.0.1:7890 \
     -e NO_PROXY=localhost,127.0.0.1,::1 \
     -v /data/apps/letsencrypt:/etc/letsencrypt \
     -v /data/apps/letsencrypt/lib:/var/lib/letsencrypt \
     -v /data/apps/letsencrypt/cloudflare.ini:/cloudflare.ini:ro \
     certbot/dns-cloudflare:latest certonly \
     --dns-cloudflare \
     --dns-cloudflare-credentials /cloudflare.ini \
     --dns-cloudflare-propagation-seconds 120 \
     --dry-run -n --agree-tos -m admin@zzzai.cloud \
     -d zzzai.cloud -d nginx.zzzai.cloud -d token.zzzai.cloud
   ```
   In this repository, `120` seconds was enough while `10` seconds was not.

8. After dry-run succeeds, request the real certificate with the same command minus `--dry-run`.
   Certbot stores the live certificate under:
   - `/data/apps/letsencrypt/live/<primary-domain>/fullchain.pem`
   - `/data/apps/letsencrypt/live/<primary-domain>/privkey.pem`

9. Before replacing nginx-ui certs, back up the current files in `/data/apps/nginx-ui-official/nginx/certs/`.
   Then copy the new cert and key into the exact paths used by the active nginx configs, for example:
   - `/data/apps/nginx-ui-official/nginx/certs/zzzai.cloud.pem`
   - `/data/apps/nginx-ui-official/nginx/certs/zzzai.cloud.key`

10. Validate and reload nginx from the running container:
   ```bash
   sudo docker exec nginx-ui-prod nginx -t
   sudo docker exec nginx-ui-prod nginx -s reload
   ```

11. Install automatic renewal as a host script plus cron entry.
   The proven path on `prod0-main` is:
   - script: `/usr/local/sbin/renew_zzzai_cloud_cert.sh`
   - cron: `/etc/cron.d/renew_zzzai_cloud_cert`

   The renewal script should:
   - rerun `certbot renew` with the same DNS-01 and proxy settings
   - compare live certs with nginx-ui cert paths
   - copy only when changed
   - run `nginx -t` and reload only when the cert actually changed

12. Record the final state in local inventory docs if the certificate source changed.
   For this repository, update:
   - `inventory/servers/prod0-main/README.md`
   - `inventory/servers/prod0-main/inventory.json`

## Verification Checklist

- `sudo docker exec nginx-ui-prod nginx -t` succeeds
- `echo | sudo openssl s_client -connect 127.0.0.1:8443 -servername <fqdn> | sudo openssl x509 -noout -issuer -dates` shows Let’s Encrypt for each intended host
- the certificate paths under `/data/apps/nginx-ui-official/nginx/certs/` match the files under `/data/apps/letsencrypt/live/<primary-domain>/`
- `sudo /usr/local/sbin/renew_zzzai_cloud_cert.sh` exits successfully when the certificate is not yet due
- browsers no longer warn about self-signed or Cloudflare Origin CA certificates for the direct-access domains

## Notes

- Let’s Encrypt certificates are free DV certificates. The cost here is only DNS/API access and operational work, not certificate purchase.
- Cloudflare Origin CA certificates are valid only when Cloudflare stays in front; once the domain is switched to grey-cloud direct access, browsers will not trust them.
- If a domain still returns `502` after the certificate fix, separate TLS from upstream health. In this repository, `token.zzzai.cloud` can still return `502` if `127.0.0.1:18080` is absent even when the certificate is correct.
- If direct testing from the local Windows or WSL machine times out while the host-local `openssl s_client -connect 127.0.0.1:8443` succeeds, treat that as a network-path problem first, not a certificate deployment failure.
