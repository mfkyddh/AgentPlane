# prod2-main 1Panel 公网接入口径（正式）

## 定位

- 本手册定义 `prod2-main` 已上线的 active 公网入口口径。
- AgentPlane 的正式运维控制面是 `uv run python -m agentplane.cli ...`；runbook 只解释专题流程、风险与人工接力点。
- `ops/scripts/onepanel/*.py`、`api_request.py`、页面点击只保留给 compat、troubleshooting 或现场只读核对。
- 主机目标摘要由 `inventory/servers/prod2-main/README.md`（公开摘要）与 `inventory/servers/prod2-main/inventory.json`（运行级真源）共同构成，所有公开网站描述均以这两个文件为依据，避免出现漂移的个别“单点口径”。

## 正式链路

- 主机：`prod2-main`（`38.12.32.94`）
- 正式域名：`1panel.zzzai.fun`
- 正式公网 URL：`https://1panel.zzzai.fun/p2panel443`
- 正式公网 HTTPS 端口：`443`
- DNS 托管：`Cloudflare`
- 证书签发与续签：`Let's Encrypt DNS-01`
- 正式公网入口基础设施层：`1panel-openresty-prod`
- OpenResty 网络模式：Docker `host`
- 共享 Docker 网络：`zqf_network`
- `zqf_network` 现场子网：`172.19.0.0/16`
- 站点治理：必须先创建为 1Panel 网站对象，再由 OpenResty 承载
- 证书目录真源：`/data/1panel/www/certs/`
- `uv run python -m agentplane.cli host inventory prod2-main --repo-root /root/work/AgentPlane` 当前是 tracked inventory readback，不是 live host collector；它与 `inventory/servers/prod2-main/inventory.json` 共同定义 prod2-main 的仓库级主机真值。
- `uv run python -m agentplane.cli projection ledger refresh --target prod2-main --repo-root /root/work/AgentPlane --write` 只刷新 object ledger / `ledgers/*.json|md` / README；若需要新的 `verification-prod2-*.json|md`，必须单独执行 `projection verification run --write-report`。

### 主机级公开网站对象（来自 `inventory/servers/prod2-main/inventory.json`）

| 别名 | 域名 | 公共 URL | 说明 |
| --- | --- | --- | --- |
| `1panel` | `1panel.zzzai.fun` | `https://1panel.zzzai.fun/p2panel443` | `1panel-openresty-prod`（host 网络 443）向 `http://127.0.0.1:2096` 反代；证书由 `1panel-zzzai-fun`（`/data/1panel/www/certs/1panel-zzzai-fun`）提供。 |
| `token` | `token.zzzai.fun` | `https://token.zzzai.fun` | `sub2api-prod`（AgentPlane compose）绑定 `127.0.0.1:18080`，依赖 `zqf_network`；`inventory` 中的 `public_url` 与 CLI `website get/verify` 自此处读取。 |
| `newapi` | `newapi.zzzai.fun` | `https://newapi.zzzai.fun` | `newapi-prod`（compose）绑定 `127.0.0.1:3000`，`public_url` 与 `inventory` 对齐。 |
| `vmail` | `vmail.zzzai.fun` | `https://vmail.zzzai.fun` | `vmail-prod`（compose）绑定 `127.0.0.1:3001`，借助 `1panel-openresty-prod` 提供外部 HTTPS。 |

内部控制面：`chatgpt-register-v2-prod2` 仅暴露 `internal://127.0.0.1:18082`，不作为 public ingress。

## 正式主入口

当前 active 默认姿态是只读验证；公网入口变更只在受控窗口内通过 `website publish` 执行。

正式只读校验与台帐刷新：

```bash
env -C /root/work/AgentPlane uv run python -m agentplane.cli website verify \
  --target prod2-main \
  --alias 1panel \
  --repo-root /root/work/AgentPlane

env -C /root/work/AgentPlane uv run python -m agentplane.cli projection verification run \
  --target prod2-main \
  --profile prod2-readonly \
  --repo-root /root/work/AgentPlane \
  --write-report

env -C /root/work/AgentPlane uv run python -m agentplane.cli projection ledger refresh \
  --target prod2-main \
  --repo-root /root/work/AgentPlane \
  --write
```

如需在受控窗口内修复或重放公网入口，正式任务入口是：

```bash
env -C /root/work/AgentPlane uv run python -m agentplane.cli website publish plan \
  --target prod2-main \
  --config-file /root/work/AgentPlane/secrets/services/onepanel-public-ingress.prod2.env \
  --cloudflare-env-file /root/work/AgentPlane/secrets/env/prod-jump.env \
  --repo-root /root/work/AgentPlane

env -C /root/work/AgentPlane uv run python -m agentplane.cli website publish apply \
  --target prod2-main \
  --config-file /root/work/AgentPlane/secrets/services/onepanel-public-ingress.prod2.env \
  --cloudflare-env-file /root/work/AgentPlane/secrets/env/prod-jump.env \
  --repo-root /root/work/AgentPlane \
  --execute

env -C /root/work/AgentPlane uv run python -m agentplane.cli website publish verify \
  --target prod2-main \
  --config-file /root/work/AgentPlane/secrets/services/onepanel-public-ingress.prod2.env \
  --cloudflare-env-file /root/work/AgentPlane/secrets/env/prod-jump.env \
  --repo-root /root/work/AgentPlane
```

bridge 网络是正式控制面前置条件；需要现场核对或修复时走：

```bash
env -C /root/work/AgentPlane uv run python -m agentplane.cli host network audit \
  prod2-main \
  --repo-root /root/work/AgentPlane

env -C /root/work/AgentPlane uv run python -m agentplane.cli host network ensure \
  prod2-main \
  --repo-root /root/work/AgentPlane
```

## 当前只读审计边界

- `prod2-readonly` 是 `prod2-main` 的兼容审计面，不要求所有探针都为绿。
- `sub2api` 当前在 `prod2-main` 的正式真源是 AgentPlane `compose` 工作负载，而不是 1Panel `apps/installed` 对象。
- 因此 `project` / `app` 相关失败项当前按“对象边界差异”解释，不直接判定为现场故障。
- 机器报告文件 `inventory/servers/prod2-main/ledgers/verification-prod2-readonly.json|md` 只保留事实输出，不手工写解释性文字。

## Bridge 事件归档

- 2026-03-28 时 `br-66f7da1be943` 丢失 `172.19.0.1/16` 与 `172.19.0.0/16` 路由，导致 `127.0.0.1:18080` 无法再转到 `sub2api-prod:8080`，随之 OpenResty 对外反代失效；该事件作为知识留存，活跃口径仍以 `inventory/servers/prod2-main/inventory.json` 中的 `managed_bridge_networks` 项为准。
- 现阶段正式治理是用 `inventory/servers/prod2-main/inventory.json` 的 `managed_bridge_networks`（`zqf_network 172.19.0.0/16`）与 `uv run python -m agentplane.cli host network audit prod2-main` / `host network ensure prod2-main` 保持一致，避免该网桥漂移。

## Live-State 验证

```bash
ss -ltnp | grep ':443'

curl -skI https://1panel.zzzai.fun/p2panel443
docker exec 1panel-openresty-prod nginx -T | grep ssl_certificate
```

证书续签完成后的 reload hook：

```bash
docker exec 1panel-openresty-prod nginx -t && \
docker exec 1panel-openresty-prod nginx -s reload
```

通过标准：

- `website verify --target prod2-main --alias 1panel --repo-root /root/work/AgentPlane` 返回 `ok=true`
- `projection verification run --target prod2-main --profile prod2-readonly` 只出现已知对象边界差异
- 如执行了公网入口变更，`website publish verify` 与 live-state 结论一致
- `curl` 与 `nginx -T` 结论一致
- bridge 网络 audit/ensure 不再报告 gateway 与路由漂移

## Compat / Troubleshooting

以下内容只用于排障或现场只读核对，不是正式主入口：

- `python3 /opt/agentplane/ops/scripts/onepanel/api_request.py GET /api/v2/websites/list ...`
- 直接打开 1Panel 面板核对网站对象、证书对象或 cronjob 页面
- 宿主机底层 bridge 检查：

```bash
docker network inspect zqf_network --format '{{json .}}'
ip -json -4 addr show dev br-66f7da1be943
ip -json route show 172.19.0.0/16
curl -sv http://127.0.0.1:18080/health
```

- OpenResty app 模板未渲染时的现场补救：

```bash
grep -E '^(WEBSITE_DIR|PANEL_APP_PORT_HTTP|PANEL_APP_PORT_HTTPS)=' \
  /data/1panel/apps/openresty/openresty/.env

grep -n 'listen ' /data/1panel/apps/openresty/openresty/conf/default/00.default.conf
grep -n 'listen ' /data/1panel/apps/openresty/openresty/conf/default/default.conf

cd /data/1panel/apps/openresty/openresty
docker compose down
docker compose up -d --force-recreate
docker compose run --rm --entrypoint /usr/local/openresty/bin/openresty openresty -t
```

历史切换窗口、一次性补救和故障过程记录，应归档到 `docs/archive/runbooks/...`，不要继续保留在 active 主流程中。

## 禁止事项

- 不允许把 `8443` 继承为 `prod2-main` 的默认正式公网端口
- 不允许绕过 1Panel 网站对象，直接用手工 vhost 作为最终交付
- 不允许把历史迁移端口、临时入口或 legacy 组件恢复成正式公网入口
