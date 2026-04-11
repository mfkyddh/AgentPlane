# prod0-main 摘要

## 身份

- 备注：`0号生产机（主力）`
- 云厂商：`Tencent Cloud`
- 公网 IPv4：`175.178.114.192`
- 域名：`zzzai.cloud`
- SSH 别名：`prod0-main`

## 应用控制面

- `chatgpt-register-v2`：`compose` / `chatgpt-register-v2-prod` / `internal://127.0.0.1:18081`
- 依赖容器：`sub2api-prod`
- `newapi`：`compose` / `newapi-prod` / `https://newapi.zzzai.cloud:8443`
- 依赖容器：`postgres18-prod, redis7-prod`
- app_resource_summary.postgres：`{"database": "newapi_prod0", "secret_file": "secrets/hosts/prod0-main/apps/newapi/resources/postgres.env", "user": "newapi_prod0"}`
- app_resource_summary.redis：`{"db": 2, "key_prefix": "newapi:", "secret_file": "secrets/hosts/prod0-main/apps/newapi/resources/redis.env"}`
- app_resource_summary.minio：`{"access_key": "newapi_prod0", "bucket": "prod0-newapi", "isolation_level": "bucket-scoped-rw", "policy_name": "prod0-newapi-rw", "policy_scope": "bucket-only", "secret_file": "secrets/hosts/prod0-main/apps/newapi/resources/minio.env"}`
- `sub2api`：`compose` / `sub2api-prod` / `https://token.zzzai.cloud:8443`
- 依赖容器：`postgres18-prod, redis7-prod`
- app_resource_summary.postgres：`{"database": "sub2api_prod0", "secret_file": "secrets/hosts/prod0-main/apps/sub2api/resources/postgres.env", "user": "sub2api_prod0"}`
- app_resource_summary.redis：`{"db": 1, "key_prefix": "sub2api:", "secret_file": "secrets/hosts/prod0-main/apps/sub2api/resources/redis.env"}`
- app_resource_summary.minio：`{"access_key": "sub2api_prod0", "bucket": "prod0-sub2api", "isolation_level": "bucket-scoped-rw", "policy_name": "prod0-sub2api-rw", "policy_scope": "bucket-only", "secret_file": "secrets/hosts/prod0-main/apps/sub2api/resources/minio.env"}`
- `sub2apipay`：`compose` / `sub2apipay-prod` / `https://pay.zzzai.cloud:8443`
- 依赖容器：`postgres18-prod`
- app_resource_summary.postgres：`{"database": "sub2apipay", "secret_file": "secrets/hosts/prod0-main/apps/sub2apipay/resources/postgres.env", "user": "sub2apipay_prod0"}`

## App Resource 台账语义

- `app_resource_summary` 供 prod0 台账与对账使用；只有 Redis 采用共享 runtime 凭据，PostgreSQL/MinIO 继续记录各自租户凭据标识，其中 MinIO 额外登记 bucket-scoped policy 元数据。
- Redis 采用共享 runtime 凭据（shared runtime credential），并通过 DB 级逻辑分区 + key prefix 区分租户，不再把 per-app Redis user 视为活跃运行时依赖。
- MinIO 当前按 bucket-scoped policy 收敛：`policy_name` / `policy_scope` / `isolation_level` 反映控制面登记的对象存储权限边界。
- 这不是强隔离；它仅提供逻辑分区，真实 secret 仍需由受控 secrets 流程单独写入。

## 资料入口

- 结构化清单：`inventory/servers/prod0-main/inventory.json`
- 机器真源：`inventory/servers/prod0-main/inventory.json`
- 本摘要：`inventory/servers/prod0-main/README.md`
- README 只保留非敏感摘要，不承载第二真源；脚本消费和对象细节以 JSON 为准。

<!-- BEGIN AGENTPLANE_ONEPANEL_LEDGER -->
## 1Panel 对象台帐投影

- 生成时间：`2026-04-10T06:39:10.665204+00:00`
- 刷新命令：`uv run python -m agentplane.cli onepanel --env prod0-main ledger refresh --repo-root /root/work/AgentPlane --write`

### 对象计数

- `websites`: 4
- `containers`: 8
- `firewall`: 1
- `cronjobs`: 4
- `apps`: 1
- `app_resources`: 3
- `automations`: 4

### 最近 CLI 动作

- 无最近 onepanel CLI 记录。
<!-- END AGENTPLANE_ONEPANEL_LEDGER -->
