# Prod0 PostgreSQL Admin Cutover Design

**Date:** 2026-03-26

## Goal

为 `prod0-main` 设计一套安全、可回滚的 PostgreSQL 管理员入口切换方案，把当前 `admin.prod0.env` 中的管理员默认连接从 `app/app` 切换为 `postgres/postgres`，并在不影响现网应用的前提下，逐步退役历史 `app` 角色与 `app` 数据库。

## Verified Current State

截至 2026-03-26，本专题的现场事实已经核对：

- 远端正式 PostgreSQL 管理员配置文件为 `/opt/env_ubuntu/secrets/services/postgres/admin.prod0.env`，当前值仍是 `POSTGRES_DB=app`、`POSTGRES_USER=app`。
- `postgres18-prod` 的 Compose 编排直接加载该文件，并用 `pg_isready -U $$POSTGRES_USER -d $$POSTGRES_DB` 做健康检查。
- 线上业务容器 `newapi-prod`、`sub2api-prod`、`sub2apipay-prod` 都在运行，并依赖 `postgres18-prod`。
- 线上数据库至少存在：`app`、`postgres`、`newapi_prod0`、`sub2api`、`sub2api_prod0`、`sub2apipay`。
- 线上角色列表中已确认存在：`app`、`newapi_prod0`、`sub2api_prod0`；当前没有证据表明 `postgres` 登录角色已经存在。
- `newapi-prod` 当前运行时连接使用 `newapi_prod0 / newapi_prod0`。
- `sub2api-prod` 当前运行时连接使用 `sub2api_prod0 / sub2api_prod0`。
- `sub2apipay-prod` 当前运行时连接仍使用 `app / sub2apipay`，其配置文件为 `/data/sub2apipay/config/sub2apipay-prod.env`。

这些事实意味着：

- `newapi` 与 `sub2api` 已经不依赖 `app` 角色。
- `sub2apipay` 仍依赖 `app` 角色。
- 只修改 `admin.prod0.env` 而不先准备 `postgres` 登录角色，会直接打断 PostgreSQL 健康检查与运维脚本。
- 在 `sub2apipay` 迁走之前，删除 `app` 角色一定会造成生产故障。

## Problem Statement

当前 `prod0-main` 的 PostgreSQL 管理员入口和历史业务入口仍然绑定在同一个 `app` 角色上，这有三个问题：

1. 管理员身份与历史业务身份混用，违背控制面与应用运行面分离原则。
2. `app` 角色已经不再服务 `newapi` 与 `sub2api`，但仍被 `sub2apipay` 与管理员脚本复用，导致后续退役无法一步完成。
3. 仓库模板已经朝 `postgres/postgres` 默认口径演进，但 `prod0-main` 的正式现场仍停留在旧口径，形成认知与运行时分叉。

## Non-Goals

本专题明确不做以下事情：

- 不重新初始化 PostgreSQL 数据目录。
- 不重建 `newapi_prod0`、`sub2api_prod0` 数据库或角色。
- 不把 `sub2apipay` 纳入 `app_resource_summary` 正式租户台账。
- 不在本专题内处理 Redis、MinIO 管理员切换。
- 不把 `sub2apipay` 改造成完整的多租户资源隔离样板。

## Options

### Option A: 只改 `admin.prod0.env`

直接把 `POSTGRES_DB` 和 `POSTGRES_USER` 改为 `postgres`，然后重启 `postgres18-prod`。

优点：

- 表面步骤最少。

缺点：

- 如果 `postgres` 登录角色不存在，健康检查会立刻失败。
- 远端部署脚本与 `psql` 验证命令会一起失效。
- 没有解决 `sub2apipay` 仍依赖 `app` 的问题。

结论：

- 不可接受。

### Option B: 一次性把 `app` 直接重命名为 `postgres`

在线把 `app` 角色重命名为 `postgres`，并同步更新密码、管理员配置和所有遗留客户端。

优点：

- 从角色命名上看最“彻底”。

缺点：

- 仍需同步改动 `sub2apipay` 的连接串。
- 风险集中在一个窗口内，回滚复杂。
- 对现有对象 owner、遗留连接、数据库授权的影响面更大。
- 一旦中间某一步失败，管理员入口和业务入口会一起混乱。

结论：

- 风险过高，不作为首选。

### Option C: 分阶段切换管理员入口，再迁走 `sub2apipay`，最后退役 `app`

先在线补齐 `postgres` 管理员角色并验证，再切换 `admin.prod0.env`；随后为 `sub2apipay` 创建专用角色并完成应用侧切换；最后在无剩余依赖时删除 `app` 角色，并视观察期结果决定是否删除 `app` 数据库。

优点：

- 将“管理员入口切换”和“历史业务退役”分成两个独立风险面。
- `newapi` 与 `sub2api` 不需要动。
- 每个阶段都可以单独回滚。
- 可以把“删 app 数据库”放到最后一个显式 gate，而不是和管理员切换绑死。

缺点：

- 步骤比一次性方案更多。
- 需要额外一次 `sub2apipay` 连接迁移。

结论：

- 推荐采用。

## Approved Design

采用 **Option C: 分阶段切换**。

### Phase 1: 准备 `postgres` 管理员角色

在运行中的 `postgres18-prod` 内新增或校正 `postgres` 登录角色，使其具备当前管理员脚本所需权限。此阶段不移除 `app`，不改业务应用连接。

要求：

- `postgres` 角色必须能够成功连接 `postgres` 与 `app` 数据库。
- 该角色必须满足现有健康检查、运维验证、人工 `psql` 运维入口的需要。
- 该阶段完成前，不得修改 `admin.prod0.env`。

### Phase 2: 切换管理员配置到 `postgres/postgres`

更新本地与远端的 `secrets/services/postgres/admin.prod0.env`，把：

- `POSTGRES_DB` 切到 `postgres`
- `POSTGRES_USER` 切到 `postgres`
- `POSTGRES_PASSWORD` 保持现有管理员密码，或按单独密码轮换方案更新

随后重建或重启 `postgres18-prod`，确认：

- 容器健康检查恢复为 `healthy`
- 远端验证脚本可继续使用
- `newapi-prod` 与 `sub2api-prod` 仍正常

该阶段完成后，`app` 角色仍保留，仅不再作为管理员入口。

### Phase 3: 迁移 `sub2apipay` 脱离 `app`

为 `sub2apipay` 创建专用业务角色，例如 `sub2apipay_prod0`，并将 `/data/sub2apipay/config/sub2apipay-prod.env` 中的 `DATABASE_URL` 改为新角色。

同时完成：

- `sub2apipay` 数据库 owner 调整
- `sub2apipay` 库内由 `app` 持有对象的 ownership reassign
- `sub2apipay-prod` 重启与功能验证

只有在 `sub2apipay` 成功切到专用角色后，`app` 才能进入退役候选状态。

### Phase 4: 退役 `app` 角色

在确认以下条件全部满足后，才能删除 `app` 角色：

- `pg_stat_activity` 中无 `usename = 'app'` 活跃连接
- `/opt/env_ubuntu`、`/data`、仓库内受管配置中无 `postgresql://app:` 或等价引用
- `sub2apipay` 已稳定运行至少一个 24 小时观察窗口
- 各数据库内 `app` 已不再拥有对象，或已完成 `REASSIGN OWNED`

如果其中任何一项不满足，则只允许保留 `app` 为未使用角色，不得强删。

### Phase 5: 决定是否删除 `app` 数据库

`app` 数据库的删除不再视为管理员入口切换的组成部分，而是最后的可选收尾动作。

删除条件：

- 明确无应用、脚本、人工流程依赖 `app` 数据库作为默认连接库
- 数据库内无需要保留的对象或历史数据
- 已完成至少一个 24 小时观察窗口，且无回滚需求

如果上述条件任一不满足，则保留 `app` 数据库并将其 owner 切到 `postgres`，作为历史兼容库存在。

## Required Repository Effects

本专题的执行结果应同步反映到仓库文档和控制面材料中：

- `secrets/services/postgres/admin.prod0.env` 的正式口径改为 `postgres/postgres`
- `templates/services/postgres/admin.env.example` 继续保持 `POSTGRES_DB=postgres`
- 针对 `prod0-main` 的 runbook 或计划文档需要明确：
  - `newapi`、`sub2api` 已经使用独立 PostgreSQL 角色
  - `sub2apipay` 不在正式 tenant 方案内，但必须脱离 `app`
  - `app` 的删除有前置 gate，不能和管理员切换合并

## Validation Requirements

每个阶段都必须有独立验证，不允许“改完再一起看”。

### 阶段 1 验证

- `postgres` 角色存在且可登录
- `psql -U postgres -d postgres` 成功
- `psql -U postgres -d app` 成功

### 阶段 2 验证

- `postgres18-prod` 健康检查为 `healthy`
- 使用新的 `admin.prod0.env` 跑 `SELECT version();` 成功
- `newapi-prod`、`sub2api-prod` 容器状态保持 `healthy`

### 阶段 3 验证

- `sub2apipay-prod` 重启后稳定运行
- `sub2apipay` 首页、登录态、关键支付链路无立即故障
- `pg_stat_activity` 可见 `sub2apipay` 已使用新角色

### 阶段 4 验证

- `app` 无活跃连接
- `DROP ROLE app` 前的依赖检查返回为空
- 删除角色后无应用报错

### 阶段 5 验证

- `app` 数据库若删除，`pg_database` 查询中不再出现 `app`
- 如保留，则 owner 已不再是 `app`

## Rollback Strategy

回滚按阶段进行，不跨阶段混用。

### 管理员入口阶段回滚

- 保留 `app` 角色不变
- 把 `admin.prod0.env` 还原为 `app/app`
- 重启 `postgres18-prod`

### `sub2apipay` 阶段回滚

- 保留新角色与新授权，不立即删除
- 把 `sub2apipay-prod.env` 的 `DATABASE_URL` 改回旧的 `app` 连接串
- 重启 `sub2apipay-prod`

### `app` 退役阶段回滚

- 在未真正 `DROP ROLE` 前，只需恢复引用即可
- 一旦已 `DROP ROLE app`，只能通过重新创建角色并恢复密码、授权、owner 来回滚，因此删除动作必须置于最后

## Success Criteria

当且仅当以下条件全部满足时，本专题可视为完成：

- `postgres18-prod` 的管理员入口已切到 `postgres/postgres`
- `newapi-prod` 与 `sub2api-prod` 未因本专题出现 PostgreSQL 连接回归
- `sub2apipay-prod` 已不再使用 `app` 角色
- `app` 角色已删除，或因明确 gate 暂缓删除且原因已记录
- `app` 数据库已删除，或因观察期策略保留且 owner 已非 `app`
