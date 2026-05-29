---
name: "source-command-agentplane-nginxui-cert"
description: "Issue or repair Let's Encrypt certificates for nginx-ui deployments when Cloudflare uses grey-cloud direct access or port 80/443 validation is unavailable."
---

# source-command-agentplane-nginxui-cert

Use this skill when the user asks to run the migrated source command `agentplane-nginxui-cert`.

## Command Template

# nginx-ui Let's Encrypt via Cloudflare DNS-01

Use when a host serves HTTPS through `nginx-ui-prod` but the certificate is self-signed or Cloudflare Origin CA and needs direct browser trust after switching Cloudflare from orange-cloud to grey-cloud.

## Rules

- Sync certs into `/data/apps/nginx-ui-official/nginx/certs`
- Install automatic renewal plus nginx reload

Full details: `.agents/skills/nginxui-letsencrypt-cloudflare-dns01/SKILL.md`
