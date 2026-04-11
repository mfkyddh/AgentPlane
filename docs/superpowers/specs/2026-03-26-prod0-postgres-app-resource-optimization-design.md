# Prod0 PostgreSQL Tenant Optimization Design

**Date:** 2026-03-26

## Goal

为 `prod0-main` 上现有共享实例 PostgreSQL 多租户方案补齐正式治理闭环，使 `newapi`、`sub2api`、`sub2apipay` 三个正式应用全部进入同一套 tenant 台账并受同等约束，同时完成管理员入口从历史 `app/app` 口径向正式 `postgres/<admin-password>` 口径切换，并建立声明、运行时、现场三层对账能力。

## Verified Current State

截至 2026-03-26，本专题已核对以下现场事实：

- `prod0-main` 上 PostgreSQL 生产实例为 `postgres18-prod`，当前仍由 `secrets/services/postgres/admin.prod0.env` 提供管理员连接入口。
- 远端正式 PostgreSQL 管理员配置仍使用 `POSTGRES_DB=app`、`POSTGRES_USER=app`。
- `newapi-prod` 当前使用独立数据库/角色 `newapi_prod0 / newapi_prod0`。
- `sub2api-prod` 当前使用独立数据库/角色 `sub2api_prod0 / sub2api_prod0`。
- `sub2apipay-prod` 当前已经连接独立数据库 `sub2apipay`，但使用角色 `sub2apipay_prod0` 的现场状态尚未收口进正式 tenant 台账。
- 仓库内正式 tenant ledger 当前只登记了 `newapi` 与 `sub2api`，尚未登记 `sub2apipay`。
- PostgreSQL 管理员入口切换方案已有独立设计，但其中明确把 `sub2apipay` 视为“必须脱离 app、但尚未进入正式 tenant 方案”的对象。

这些事实说明，`prod0-main` 的 PostgreSQL 现场已经部分完成“共享实例、分库分用户”隔离，但控制面仍存在账实不一致和历史入口未退役的问题。

## Problem Statement

当前方案的主要问题不是 PostgreSQL 实例级隔离不足，而是治理闭环不完整：

1. `sub2apipay` 已经具备独立数据库语义，但未纳入正式 tenant ledger，控制面无法对三个正式应用给出一致答案。
2. PostgreSQL 管理员入口仍绑定在历史 `app` 口径上，管理员身份与历史业务兼容入口未完全分离。
3. 现有 `tenant validate` / `tenant audit` 主要保证声明层一致性，尚未强制核对容器运行时连接和 PostgreSQL live state。
4. 历史 `app` 角色与 `app` 数据库尚未完成显式退役 gate，后续密码轮换、迁移和审计仍有不确定性。

## Non-Goals

本专题明确不做以下事项：

- 不将 `prod0-main` 的 PostgreSQL 从共享实例模式改为多实例模式。
- 不在本专题内重构 Redis 和 MinIO 的租户隔离模型。
- 不重做应用交付系统，只补足 PostgreSQL tenant 相关的合同、台账、审计和切换流程。
- 不强制在本专题内删除 `app` 数据库；其删除仅作为最后的可选收尾动作。

## Options

### Option A: 共享实例强化治理

保持 `postgres18-prod` 共享实例模型不变，把 `sub2apipay` 正式纳入 tenant ledger，并补齐独立数据库、独立角色、独立 secret、运行时对账、管理员入口切换和历史 `app` 退役 gate。

优点：

- 与 `newapi`、`sub2api` 的现有生产模型一致。
- 优先解决账实不一致和历史入口问题，收益最大。
- 风险面主要集中在控制面收口和管理员入口切换，改动边界清晰。
- 不引入新的 PostgreSQL 实例运维负担。

缺点：

- 仍然是共享实例，实例级隔离强度有限。

结论：

- 推荐采用。

### Option B: 按风险分层

保持 `newapi`、`sub2api` 继续共享 `postgres18-prod`，但将 `sub2apipay` 单独迁往新的 PostgreSQL 实例，并同时完成管理员入口切换和控制面对账。

优点：

- 支付相关应用获得更强隔离。

缺点：

- 专题会扩大为数据库迁移、备份恢复、实例生命周期管理。
- 实施复杂度和回滚复杂度显著升高。
- 偏离当前“治理优化”主线。

结论：

- 不作为本次方案基线。

### Option C: 全量单应用单实例

将 `newapi`、`sub2api`、`sub2apipay` 全部拆分到独立 PostgreSQL 实例。

优点：

- 隔离最强。

缺点：

- 运维成本与收益不成比例。
- 当前控制面、台账、审计逻辑都需要大幅重做。

结论：

- 当前阶段不采用。

## Approved Design

采用 **Option A: 共享实例强化治理**。

### Design Objectives

- `newapi`、`sub2api`、`sub2apipay` 全部进入正式 PostgreSQL tenant ledger。
- 三个应用全部使用各自 tenant PostgreSQL 凭据运行。
- PostgreSQL 管理员入口从 `app/app` 切换为 `postgres/<admin-password>`。
- `app-resources.json`、`inventory.json`、tenant secrets、容器运行时配置、PostgreSQL live state 五处信息可以相互对账。
- 历史 `app` 角色与 `app` 数据库的退役具备显式 gate 与回滚策略。

### Control Plane Model

对 `prod0-main` 统一采用以下 PostgreSQL tenant 对象模型：

- 真源台账：`inventory/servers/prod0-main/app-resources.json`
- 人类可读摘要：`inventory/servers/prod0-main/app_resources.md`
- 应用级摘要投影：`inventory/servers/prod0-main/inventory.json`
- tenant secret 真源：`secrets/app-resources/prod0-main/<app>/postgres.env`

三个正式应用 `newapi`、`sub2api`、`sub2apipay` 都必须在 `app-resources.json` 中拥有一条正式记录。每条记录至少包含：

- `owner_app`
- `ledger_status`
- `postgres.database`
- `postgres.user`
- `secret_files`

`inventory.json` 中每个应用的 `app_resource_summary.postgres` 只作为投影摘要，不作为分配真源。运行时 env 必须从 `secrets/app-resources/prod0-main/<app>/postgres.env` 投影生成，禁止直接手写与 tenant 真源不一致的连接串。

### Tenant Constraints

三个正式应用必须满足同等 PostgreSQL 约束：

- 共享同一个 `postgres18-prod` 实例。
- 各自拥有独立数据库。
- 各自拥有独立登录角色。
- 各自拥有独立密码和独立 tenant secret。
- 应用运行时禁止使用管理员角色。
- 不允许两个正式应用共享同一个 PostgreSQL 数据库或用户。

`sub2apipay` 在本方案中不再保留例外地位，必须与 `newapi`、`sub2api` 使用同等控制面和校验规则。

### Reconciliation Model

对账链路统一分为三层。

#### 1. 声明对账

校验合同、台账和 secret 路径声明是否一致。必须能拒绝以下情况：

- `sub2apipay` 缺 tenant 记录。
- `secret_file` 越界或未落在 `secrets/app-resources/prod0-main/<app>/`。
- 数据库名或用户名与台账不一致。
- 正式应用引用其他应用 tenant secret。
- 正式应用仍显式声明 `app`、`postgres` 等非 tenant 业务凭据。

#### 2. 运行时对账

校验实际容器 env 是否与 tenant secret 投影一致。必须能发现以下漂移：

- 应用容器仍连接旧数据库。
- 应用容器使用的用户名与 tenant secret 不一致。
- 应用运行时连接串中残留 `app`、管理员入口或其他非 tenant 账号。
- 应用配置目录中仍保留历史 PostgreSQL 连接引用。

#### 3. 现场对账

校验 `postgres18-prod` live state 是否与台账一致。至少核对：

- 台账声明的数据库存在。
- 台账声明的角色存在。
- 数据库 owner 与预期 tenant user 一致。
- 正式应用不再依赖历史 `app` 角色作为运行时入口。

实现原则是不新建平行 CLI，而是在现有 `tenant validate`、`tenant audit` 与 prod0 审计基线上扩展 PostgreSQL 专项检查。

## Execution Phases

### Phase 1: 控制面补齐

目标：先让仓库能正确描述三个正式应用的目标状态与当前状态。

动作：

- 在 `app-resources.json`、`app_resources.md` 中新增 `sub2apipay` PostgreSQL tenant 记录。
- 让 `inventory.json` 为 `sub2apipay` 生成 `app_resource_summary.postgres`。
- 增加 `secrets/app-resources/prod0-main/sub2apipay/postgres.env` 标准路径要求和相关模板/测试约束。
- 扩展 `tenant validate`、`tenant audit`、prod0 审计测试，使三个正式应用受同等规则约束。
- 明确“正式应用不得使用 `app` / 管理员 PostgreSQL 凭据”是硬校验项。

阶段 gate：

- 本地测试通过。
- 不需要修改线上配置。
- 仓库能够直接回答三个正式应用各自的 PostgreSQL database / user / secret path。

### Phase 2: runtime 对账能力落地

目标：仓库能够识别“台账正确但容器未切换”的漂移。

动作：

- 在 `tenant audit` 或 prod0 专项审计中加入容器 env 检查。
- 对 `newapi-prod`、`sub2api-prod`、`sub2apipay-prod` 读取 live env，核对数据库名和用户名是否与 tenant secret 一致。
- 增加对 `/opt/env_ubuntu`、应用 runtime env、compose 配置的历史引用扫描，拒绝残留 `postgresql://app:`、`DATABASE_USER=app` 或管理员业务引用。

阶段 gate：

- 在线 audit 能明确给出每个正式应用的 pass / drift 结果。
- 此阶段不修改 PostgreSQL 管理员入口。

### Phase 3: 管理员入口切换

目标：把 PostgreSQL 管理员入口从历史 `app` 切到正式 `postgres`。

动作：

- 先确保 `postgres` 登录角色存在、可登录并具备管理所需权限。
- 更新本地与远端 `secrets/services/postgres/admin.prod0.env` 到 `POSTGRES_DB=postgres`、`POSTGRES_USER=postgres`。
- 重启或重建 `postgres18-prod`，验证健康检查、管理员脚本和三个业务应用无回归。

阶段 gate：

- `psql -U postgres -d postgres` 成功。
- `postgres18-prod` 健康检查正常。
- 三个业务容器连接正常。
- 若任一验证失败，立即回滚 `admin.prod0.env` 并恢复容器。

### Phase 4: 历史兼容入口退役

目标：让 `app` 不再承担管理员或业务运行时入口。

动作：

- 确认三应用与所有受管配置都不再引用 `app`。
- 若 `app` 数据库仍需兼容保留，则将其 owner 切到 `postgres`，但禁止继续作为应用入口。
- 仅在无剩余依赖时才删除 `app` 角色。
- `app` 数据库删除作为单独可选收尾动作，不与本专题主线绑定。

阶段 gate：

- `pg_stat_activity` 中无 `usename = 'app'` 活跃连接。
- `/opt/env_ubuntu`、`/data`、仓库受管配置中无 `app` PostgreSQL 业务引用。
- 三应用至少稳定运行一个观察窗口。

## Validation Requirements

完成后至少必须证明以下事实：

- 三个正式应用全部存在于 PostgreSQL tenant ledger。
- 三个正式应用全部使用各自 tenant PostgreSQL 凭据。
- PostgreSQL 管理员入口已经切到 `postgres`。
- `tenant validate`、`tenant audit`、inventory 摘要、live state 四处信息一致。
- 不再存在“现场已独立但控制面缺席”的 PostgreSQL tenant。

分阶段验证要求如下。

### 阶段 1 验证

- `app-resources.json`、`app_resources.md`、`inventory.json` 对 `sub2apipay` 的 PostgreSQL 记录一致。
- 三个正式应用的 PostgreSQL tenant secret 路径符合标准位置。
- 本地测试全部通过。

### 阶段 2 验证

- 在线审计可以读取三个业务容器的 PostgreSQL 连接信息。
- 审计结果能够区分声明一致和 runtime 漂移。
- 历史 `app` 或管理员业务引用能够被报告为 drift。

### 阶段 3 验证

- `postgres` 角色存在且可登录。
- 使用新的 `admin.prod0.env` 可成功执行 `SELECT version();`。
- `postgres18-prod` 健康检查为 `healthy`。
- `newapi-prod`、`sub2api-prod`、`sub2apipay-prod` 均无 PostgreSQL 连接回归。

### 阶段 4 验证

- `app` 无活跃连接。
- 删除 `app` 角色前依赖检查返回为空，或记录明确的保留原因。
- 若保留 `app` 数据库，则 owner 已非 `app` 且不再作为业务入口。

## Rollback Strategy

回滚按阶段分离，不跨阶段混用。

### Phase 1 / Phase 2 回滚

- 回退仓库分支或恢复台账与测试变更。
- 线上状态不受影响。

### Phase 3 回滚

- 恢复 `admin.prod0.env` 到历史可用值。
- 重启 `postgres18-prod` 恢复旧的健康检查入口。
- 保留 `postgres` 角色，不要求在回滚时立即删除。

### Phase 4 回滚

- 在未真正 `DROP ROLE app` 前，只需恢复引用即可。
- 一旦已删除 `app` 角色，回滚必须通过重建角色、恢复密码、重建授权和对象 owner 才能完成，因此删除动作必须置于最后。

## Success Criteria

当且仅当以下条件全部满足时，本专题视为完成：

- `newapi`、`sub2api`、`sub2apipay` 三个正式应用全部被正式纳入 PostgreSQL tenant ledger。
- 三个正式应用全部运行在各自 tenant PostgreSQL 凭据下。
- PostgreSQL 管理员入口已切到 `postgres/<admin-password>`。
- `app` 不再作为任何正式应用或管理员流程的运行时入口。
- 对账工具能够稳定发现声明漂移、运行时漂移和现场漂移。
