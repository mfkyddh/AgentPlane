# [ARCHIVED] prod0 PostgreSQL App Resource Ops

> 历史窗口快照。该文档仅保留 `2026-03-26` 前后租户化对账窗口的现场记录，不是当前正式入口。
> 当前决策请回到 `inventory/servers/prod0-main/`、active runbook，以及 `uv run python -m ops.cli app resource ...` 的现行控制面口径。

## 2026-03-26 现场状态

- `prod0-main:/opt/op_linux/secrets/services/postgres/admin.prod0.env` 已切到 `POSTGRES_DB=postgres` 与 `POSTGRES_USER=postgres`。
- `prod0-main:/data/sub2apipay/config/sub2apipay-prod.env` 当前 `DATABASE_URL` 已使用 `sub2apipay_prod0@sub2apipay`。
- `prod0 PostgreSQL app resource live audit helper` 在 2026-03-26 现场返回 `ok=true`。
- catalog 现场已经满足 `sub2apipay` 数据库 owner 为 `sub2apipay_prod0`，因此本轮不做重复 cutover、不轮换 `sub2apipay` 密码、不重启容器。

## 本轮动作范围

本轮只做两件事：

1. 从远端 live `DATABASE_URL` 回填本地 secret `secrets/app-resources/prod0-main/sub2apipay/postgres.env`。
2. 补齐只读默认的远端校验脚本 `ops/scripts/remote/prod0-postgres-app-resource-cutover.sh`，把现场状态固化成可重复执行的对账入口。

这不是一次新的生产切换。默认路径只做对账与核验，不修改密码、不改应用配置、不重启服务。

## 运行命令

### 1. app resource 现场审计

```text
/root/work/OP_Linux/.worktrees/codex-prod0-pg-app-resource-optimization
historical helper: prod0 PostgreSQL app resource live audit helper
```

预期结果是 JSON 中包含 `"ok": true` 且 `findings` 为空。

### 2. 远端只读校验脚本

```bash
cd /root/work/OP_Linux/.worktrees/codex-prod0-pg-app-resource-optimization
bash ops/scripts/remote/run_remote_bash.sh prod0-main --script-file /root/work/OP_Linux/.worktrees/codex-prod0-pg-app-resource-optimization/ops/scripts/remote/prod0-postgres-app-resource-cutover.sh
```

脚本默认输出：

- `sub2apipay` 数据库 owner
- `postgres` 数据库 owner
- `sub2apipay_prod0`、`postgres`、`app` 三个角色是否存在
- `sub2apipay-prod.env` 中 `DATABASE_URL` 对应的 host、port、database、user

脚本内部预留了 `APPLY_POSTGRES_OWNER_FIX=1` 开关，用于在明确评估后单独修正 `postgres` 数据库 owner；默认执行路径不会触发这个分支。除非已经单独批准该变更，否则不要开启这个开关。

### 3. 远端 `psql` 直接核验

```bash
cd /root/work/OP_Linux/.worktrees/codex-prod0-pg-app-resource-optimization
printf '%s\n' \
  'set -euo pipefail' \
  'source /opt/op_linux/secrets/services/postgres/admin.prod0.env' \
  'export PGPASSWORD="$POSTGRES_PASSWORD"' \
  'docker exec -e PGPASSWORD="$PGPASSWORD" postgres18-prod psql -h 127.0.0.1 -p 5432 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -At -F $'\''\t'\'' -c "SELECT datname, pg_catalog.pg_get_userbyid(datdba) FROM pg_database WHERE datname IN ('\''postgres'\'','\''sub2apipay'\'') ORDER BY datname;"' \
| bash ops/scripts/remote/run_remote_bash.sh prod0-main
```

预期至少看到：

- `sub2apipay    sub2apipay_prod0`
- `postgres      app`

## Residual Issue

- 截至 2026-03-26，`postgres` 数据库 owner 仍是 `app`。
- 这个状态不影响 `sub2apipay` 已经完成的 app resource 化现状，因为业务运行时已经使用 `sub2apipay_prod0@sub2apipay`。
- 如果后续要彻底退役 `app` 角色或清理历史管理口径，需要单独评估 `postgres` 数据库 owner、剩余依赖和回滚路径，再执行一次受控变更。

## Observation Gate

- 2026-03-26 的即时快照显示，`pg_stat_activity` 里仍然可以看到 `app` 会话，因此 24 小时观察窗当前不能判定为通过。
- 同一时间点在 `sub2apipay` 内按 `relowner = app` 检查，仍能看到大量 `information_schema`、`pg_catalog`、`pg_toast` 下的系统对象。
- 因此当前只能把 `app` 视为仍有剩余依赖，不能执行 `DROP ROLE app`。
- 后续若要推进角色退役，至少要重新跑一次观察窗检查，并单独评估这些对象是否属于预期的系统 bootstrap 残留，还是还存在未迁出的历史依赖。
