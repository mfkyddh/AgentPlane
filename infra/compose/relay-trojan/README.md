# relay-trojan prod2

`infra/compose/relay-trojan/docker-compose.prod2.yml` 是 `prod2-main` 的正式 relay 搭建，service key 为 `relay-trojan`，容器名固定为 `relay-trojan-prod`。
公网入口 `relay.zzzai.fun:24443`，使用 Trojan + TLS，容器直接读取 `/data/relay-trojan/config/config.json` 与 `/data/relay-trojan/certs/*`。
`infra/compose/relay-trojan/config.template.json` 是受管运行模板，部署前要把其中的 `<RELAY_TROJAN_PASSWORD>` 替换成真实值，生成 `/data/relay-trojan/config/config.json`。
`templates/services/relay-trojan.prod2.env.example` 不是 compose 启动参数文件；它是本地 `service.env` / `secrets/services/relay-trojan.prod2.env` 的模板，当前只承载需要渲染进 `config.json` 的运行参数。
证书路径固定为 `/data/relay-trojan/certs/fullchain.pem` 与 `/data/relay-trojan/certs/privkey.pem`，不从 env 注入。
实施时必须先生成并下发 `/data/relay-trojan/config/config.json`，再启动 compose；仅准备 env 文件还不足以让 Xray 工作。
