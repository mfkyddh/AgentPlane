# app_resources ledger

- 本文件是 Markdown 摘要投影，只保留对象清单与最近状态。
- 机器真源：同目录同名 `.json` 文件。
- 对应 JSON 真源见同目录同名 `.json` 文件；脚本消费与结构化字段以 JSON 为准。

- Redis 采用共享 runtime 凭据，并通过 DB 级逻辑分区 + key prefix 区分租户；这不是强隔离。
- PostgreSQL/MinIO 继续记录各自租户凭据标识，其中 MinIO 额外登记 bucket-scoped policy 元数据。

- `sub2api`
