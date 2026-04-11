## 背景

当前仓库 PostgreSQL 模板与 WSL 运行中的 `postgres18-dev` 都使用 `POSTGRES_USER=app`、`POSTGRES_DB=app`。用户要求保留现有数据，在线调整为后续统一使用 `postgres/postgres` 登录。

## 目标

- 模板默认值改为 `POSTGRES_USER=postgres`
- 模板默认值改为 `POSTGRES_DB=postgres`
- WSL 运行中的 `postgres18-dev` 后续使用 `postgres/postgres` 登录
- 保留现有数据库数据，包括现有 `app` 数据库

## 方案

采用在线调整，不重建数据目录：

1. 更新模板文件 `templates/services/postgres.env.example`
2. 更新 WSL 实际运行配置 `secrets/services/postgres.env`
3. 在运行中的 PostgreSQL 实例内将超级用户 `app` 重命名为 `postgres`
4. 将该角色密码改为 `postgres`
5. 重启容器，使健康检查和默认连接库切换到 `postgres`
6. 验证 `postgres/postgres` 能连接 `postgres` 与 `app` 数据库

## 风险与约束

- 该调整会让依赖用户名 `app` 的客户端失效
- 现有数据目录不会重新初始化，因此必须通过 SQL 在线调整角色，而不是仅依赖 `POSTGRES_*` 环境变量
