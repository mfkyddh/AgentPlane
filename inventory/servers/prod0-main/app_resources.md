# prod0-main App Resource 台账

- 机器真源：`inventory/servers/prod0-main/app-resources.json`
- 本文件是 Markdown 摘要投影，只保留 app resource 识别、资源边界和 non-sensitive secret 路径提示；脚本消费请以 JSON 真源为准。

- `sub2api`
  - PostgreSQL: `sub2api_prod0` / `sub2api_prod0`
  - Redis: shared runtime credential / DB `1` / prefix `sub2api:`
  - MinIO: bucket `prod0-sub2api` / access key `sub2api_prod0` / policy `prod0-sub2api-rw` / `bucket-scoped-rw`
  - Secret files: `secrets/hosts/prod0-main/apps/sub2api/resources/postgres.env`, `secrets/hosts/prod0-main/apps/sub2api/resources/redis.env`, `secrets/hosts/prod0-main/apps/sub2api/resources/minio.env`
- `sub2apipay`
  - PostgreSQL: `sub2apipay` / `sub2apipay_prod0`
  - Secret files: `secrets/hosts/prod0-main/apps/sub2apipay/resources/postgres.env`
- `newapi`
  - PostgreSQL: `newapi_prod0` / `newapi_prod0`
  - Redis: shared runtime credential / DB `2` / prefix `newapi:`
  - MinIO: bucket `prod0-newapi` / access key `newapi_prod0` / policy `prod0-newapi-rw` / `bucket-scoped-rw`
  - Secret files: `secrets/hosts/prod0-main/apps/newapi/resources/postgres.env`, `secrets/hosts/prod0-main/apps/newapi/resources/redis.env`, `secrets/hosts/prod0-main/apps/newapi/resources/minio.env`

台账语义说明：
- 本台账反映 prod0-main 已生效的 live DB-partition 语义，并以 `app resource` 作为正式命名。
- Redis 共享 runtime 凭据，通过 DB 级逻辑分区 + key prefix 区分应用，不再把 per-app Redis user 视为活跃运行时依赖。
- MinIO 记录 bucket-scoped policy 元数据，用于表达每个应用仅应访问自己的 bucket。
- 这不是强隔离；app resource 之间仍共享同一个 Redis 实例。
- `secret_files` 表示标准落盘路径，不代表当前仓库已存在真实 secret 文件。
- 真实 secret 由 `ops.cli secrets` 或受控发布流程写入 `secrets/hosts/<target>/apps/<app>/resources/`，不在 tracked 模板内保存。
