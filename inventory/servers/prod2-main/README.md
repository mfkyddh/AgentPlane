# prod2-main 摘要

## 身份

- 备注：`2号生产机（主力）`
- 云厂商：`朝晞云`
- 公网 IPv4：`38.12.32.94`
- 域名：`zzzai.fun`
- SSH 别名：`prod2-main`

## 应用控制面

- `relay-trojan`：`compose` / `relay-trojan-prod` / `-`
- `sub2api`：`compose` / `sub2api-prod` / `https://token.zzzai.fun`
- 依赖容器：`postgres18-prod, redis7-prod`
- app_resource_summary.postgres：`{"database": "sub2api_prod2", "secret_file": "secrets/hosts/prod2-main/apps/sub2api/resources/postgres.env", "user": "sub2api_prod2"}`
- app_resource_summary.redis：`{"db": 1, "key_prefix": "sub2api:", "secret_file": "secrets/hosts/prod2-main/apps/sub2api/resources/redis.env"}`
- app_resource_summary.minio：`{"access_key": "sub2api_prod2", "bucket": "prod2-sub2api", "isolation_level": "bucket-scoped-rw", "policy_name": "prod2-sub2api-rw", "policy_scope": "bucket-only", "secret_file": "secrets/hosts/prod2-main/apps/sub2api/resources/minio.env"}`
- `vmail`：`compose` / `vmail-prod` / `https://vmail.zzzai.fun`
- 依赖容器：`1panel-openresty-prod`

## 资料入口

- 结构化清单：`inventory/servers/prod2-main/inventory.json`
- 机器真源：`inventory/servers/prod2-main/inventory.json`
- 本摘要：`inventory/servers/prod2-main/README.md`
- README 只保留非敏感摘要，不承载第二真源；脚本消费和对象细节以 JSON 为准。

<!-- BEGIN AGENTPLANE_ONEPANEL_LEDGER -->
## 1Panel 对象台帐投影

- 生成时间：`2026-04-22T10:57:19.196950+00:00`
- 刷新命令：`uv run python -m agentplane.cli projection ledger refresh --target prod2-main --repo-root <repo-root> --write`

### 对象计数

- `websites`: 2
- `containers`: 7
- `firewall`: 1
- `cronjobs`: 4
- `apps`: 0
- `app_resources`: 1
- `automations`: 4

### 最近 CLI 动作

- 无最近 onepanel CLI 记录。
<!-- END AGENTPLANE_ONEPANEL_LEDGER -->
