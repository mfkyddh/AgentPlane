# prod2-main relay-trojan

- 本手册定义 `prod2-main` 上 `relay-trojan` 的正式运行口径。
- `relay.zzzai.fun:24443` 不属于 `website` 对象；它是附着在 `service` 上的非 HTTP 公网协议端点。
- 正式核验入口：
  `uv run python -m agentplane.cli service verify --target prod2-main --name relay-trojan --repo-root <repo-root>`
- 正式公网端点核验入口：
  `uv run python -m agentplane.cli service public-endpoint verify --target prod2-main --name relay-trojan --cloudflare-env-file <repo-root>/secrets/env/prod-jump.env --repo-root <repo-root>`
- 正式公网端点对账入口：
  `uv run python -m agentplane.cli service public-endpoint apply --target prod2-main --name relay-trojan --cloudflare-env-file <repo-root>/secrets/env/prod-jump.env --execute --repo-root <repo-root>`
- 正式客户端 profile 渲染入口：
  `uv run python -m agentplane.cli service materialize --target prod2-main --name relay-trojan --artifact clash-local-profile --source <clash-profile-source> --merge-template <clash-profile-template> --output <clash-profile-output> --password <RELAY_TROJAN_PASSWORD> --repo-root <repo-root>`
- 当前 `zzzai.fun` 区域 DNS 配额已满，`relay.zzzai.fun A` 复用了旧 `acorn.zzzai.fun` SPF TXT 记录位，`_acme-challenge.relay.zzzai.fun TXT` 复用了旧 `amber.zzzai.fun` SPF TXT 记录位；后续若清理 Email Routing 记录，可再改回显式新增。
- 运行前置：
  `/opt/agentplane/secrets/services/relay-trojan.prod2.env`
  `/data/relay-trojan/config/config.json`
  `/data/relay-trojan/certs/fullchain.pem`
  `/data/relay-trojan/certs/privkey.pem`
- 证书续期：
  `/usr/local/bin/renew-relay-trojan-cert.sh`
  `17 3 1 * * /usr/local/bin/renew-relay-trojan-cert.sh >> /var/log/relay-trojan-cert-renew.log 2>&1`
- 说明：`service public-endpoint` 会优先读取 `inventory.services.relay-trojan.public_endpoint.dns` 与 `certificate`；`service materialize` 会优先读取 `client_profile` 与 `public_endpoint`，避免把 `server`、`port`、`sni` 再散落成专题脚本参数。
