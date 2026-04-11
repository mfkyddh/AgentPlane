# prod2-main App Resources

- 机器真源：`inventory/servers/prod2-main/app-resources.json`
- 本文件是 Markdown 摘要投影，只保留应用资源识别、资源边界和非敏感 secret 路径提示。

- 台账状态：`business-app-resources-active`
- 基础设施底座已就绪并已上线：`1Panel`、`OpenResty`、`PostgreSQL`、`Redis`、`MinIO`
- `1Panel`：`v2.1.7` / `https://1panel.zzzai.fun/p2panel443`
- `OpenResty`：`1panel-openresty-prod` / `host` 网络 / `443`
- `PostgreSQL`：`postgres18-prod` / `running`
- `Redis`：`redis7-prod` / `running`
- `MinIO`：`minio-prod` / `running`

- `sub2api`
  - PostgreSQL: `sub2api_prod2` / `sub2api_prod2`
  - Redis: shared runtime credential / DB `1` / prefix `sub2api:`
  - MinIO: bucket `prod2-sub2api` / access key `sub2api_prod2` / policy `prod2-sub2api-rw` / `bucket-scoped-rw`
  - Secret files: `secrets/hosts/prod2-main/apps/sub2api/resources/postgres.env`, `secrets/hosts/prod2-main/apps/sub2api/resources/redis.env`, `secrets/hosts/prod2-main/apps/sub2api/resources/minio.env`

- `newapi`
  - PostgreSQL: `newapi_prod2` / `newapi_prod2`
  - Redis: shared runtime credential / DB `2` / prefix `newapi:`
  - MinIO: bucket `prod2-newapi` / access key `newapi_prod2` / policy `prod2-newapi-rw` / `bucket-scoped-rw`
  - Secret files: `secrets/hosts/prod2-main/apps/newapi/resources/postgres.env`, `secrets/hosts/prod2-main/apps/newapi/resources/redis.env`, `secrets/hosts/prod2-main/apps/newapi/resources/minio.env`

台账语义说明：
- 本台账反映 prod2-main 已分配的正式应用资源与其独立凭据边界。
- Redis 共享 runtime 凭据，通过 DB 级逻辑分区 + key prefix 区分应用资源。
- MinIO 记录 bucket-scoped policy 元数据，用于表达应用仅应访问自己的 bucket。
- 这不是强隔离；不同应用资源仍共享同一个 Redis 实例。
