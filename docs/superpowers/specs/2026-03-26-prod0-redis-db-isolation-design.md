# Prod0 Redis DB Isolation Design

**Date:** 2026-03-26

## Goal

为 `prod0-main` 上所有受 `OP_Linux` 管理的应用统一 Redis 多租户策略，收敛为：

- 共享 Redis `default` 认证入口
- 以 `REDIS_DB` 作为主要逻辑分区单元
- 以 `REDIS_KEY_PREFIX` 作为登记字段和未来兼容字段，而不是当前已验证的强隔离机制
- 不再把 `REDIS_USER` / ACL 用户名作为生产运行时兼容性的前提

本次设计覆盖：

- `prod0-main`
- `OP_Linux` 控制面中的 Redis 租户台账、env 渲染、校验、审计、模板、文档
- 首批现网应用：`sub2api`、`newapi`

本次设计不覆盖：

- WSL 本地环境策略切换
- PostgreSQL 多租户模型变更
- MinIO 多租户模型变更

## Current State

- 2026-03-26 的正式切换尝试把 `sub2api` 与 `newapi` 都推向“独立 Redis ACL 用户 + 独立密码 + 独立 DB + 独立 key prefix”模型。
- `newapi` 当前通过 `REDIS_CONN_STRING` 调用 `redis.ParseURL` 建立连接，因此可以兼容不带用户名、带 URL encode 密码以及 `rediss://` 的连接串。
- `sub2api` 生产镜像的实际代码只消费 `REDIS_HOST`、`REDIS_PORT`、`REDIS_PASSWORD`、`REDIS_DB`、`REDIS_ENABLE_TLS`，并未读取 `REDIS_USER` / `REDIS_USERNAME`。
- 对本轮纳入应用做代码检索后，`sub2api` 与 `newapi` 当前都没有消费 `REDIS_KEY_PREFIX`；因此它不能被描述为当前已验证的运行时边界。
- 因此 `sub2api` 在切到租户级 Redis ACL 用户后，后台任务持续报 `WRONGPASS invalid username-password pair or user is disabled`，进而影响登录与限流链路。
- 为恢复可用性，生产机已执行最小回滚：
  - 恢复 `sub2api.prod0.env` 到切换前稳定版本
  - 删除新增的 Redis ACL 用户 `sub2api_prod0`
  - 保持 Redis `default` 用户密码认证与 `db1` 使用方式不变

这说明 Redis ACL 用户模型不能作为 `prod0-main` 的统一运行时前提，否则会把“应用能力差异”转成“生产事故”。

## Constraints

- `OP_Linux` 仍然是 `prod0-main` 的正式控制面真源，真实生产 secrets 继续留在仓库 `secrets/` 中。
- 生产策略必须优先考虑现网兼容性和稳定性，不能要求每个应用先改代码才能继续运行。
- Redis 多租户逻辑分区必须至少保证：
  - 每个应用分配唯一 `REDIS_DB`
  - 每个应用登记规范化后的唯一 `REDIS_KEY_PREFIX`
- 本方案的目标是生产兼容性和控制面一致性，不把 Redis 视为“互不信任租户”的强安全边界。
- 在共享 `default` 口令的前提下，应用仍可能跨 DB 访问其他逻辑分区；该风险必须在文档中明确暴露，不能用“已隔离”字样掩盖。
- `tenant render-env` 不能再为不支持 ACL 用户名的应用生成不兼容配置。
- `inventory/` 和 README 语义必须反映 live state，而不是继续描述已经被回滚的临时 remediation target。

## Options

### Option A: 统一 DB 级隔离

所有 `prod0-main` 应用统一使用 Redis `default` 用户密码认证，通过 `REDIS_DB` 实现逻辑分区，并保留 `REDIS_KEY_PREFIX` 作为登记字段和未来兼容字段。

优点：

- 与 `sub2api` 这类只支持密码认证的应用兼容
- 控制面规则简单，env 渲染和校验逻辑稳定
- 生产切换风险最小

缺点：

- 不是强安全隔离；被攻陷的应用理论上可以访问其他 DB
- 运行时不再体现“每应用独立 Redis 用户”
- 现阶段无法把“禁止管理动作”作为已落实的权限边界

### Option B: 双轨策略

默认使用 DB 级隔离，但允许支持 ACL 的应用单独启用 Redis 用户模型。

优点：

- 可兼容老应用，同时为新应用保留更强隔离能力

缺点：

- 控制面需要维护两套规则
- 审计、模板、文档和测试复杂度都会显著上升

### Option C: 强制 ACL，逐应用修代码

继续坚持 ACL 用户模型，要求应用逐个支持 Redis 用户名。

优点：

- 隔离边界最完整

缺点：

- 不满足现网兼容性要求
- 会把控制面整改变成多应用代码改造项目
- 与本次生产回滚经验直接冲突

## Approved Design

采用 **Option A: 统一 DB 级隔离** 作为 `prod0-main` 的正式 Redis 多租户策略。

### 1. Runtime Model

`prod0-main` 上的 Redis 运行时模型固定为：

- 统一认证入口：Redis `default` 用户密码
- 逻辑分区主轴：唯一 `REDIS_DB`
- 登记与未来兼容字段：规范化后的唯一 `REDIS_KEY_PREFIX`

运行时约束：

- `REDIS_USER` 不是 `prod0-main` 运行时必需字段
- 任何应用的生产连接成功与否都不能依赖 `REDIS_USER`
- Redis 默认认证口令的真源继续保存在管理员级 secret 中；应用 runtime secret 可以投影同一口令，但不再视为租户独立密码
- 本方案不声明 Redis 已形成强安全隔离；它只提供逻辑分区和运行时兼容性

容量与模式约束：

- `prod0-main` 当前是非集群 Redis，`cluster_enabled=0`
- 当前 `databases=16`
- 本方案仅在单机非集群、且可分配 DB 数量未耗尽时成立
- 如果正式应用数量逼近 DB 上限，或未来迁移到 Redis Cluster（仅支持 `db0`），必须触发新的架构变更，而不是继续沿用本方案

### 2. Tenant Secret Semantics

`secrets/app-resources/prod0-main/<app>/redis.env` 继续存在，但其语义调整为：

- 必填：
  - `REDIS_HOST`
  - `REDIS_PORT`
  - `REDIS_PASSWORD`
  - `REDIS_DB`
  - `REDIS_KEY_PREFIX`
  - `REDIS_ENABLE_TLS`
- 可选：
  - `REDIS_USER`

对于 `prod0-main`，`REDIS_USER` 仅作为历史兼容字段存在，不参与运行时兼容性保证。

`REDIS_PASSWORD` 在该模型下不再表示“每应用独立 Redis 密码”，而是“从 Redis 管理员真源投影出的共享运行时认证口令”。

`REDIS_KEY_PREFIX` 在当前阶段不表示“应用已被证明会对所有 Redis key 使用该前缀”，它只表示控制面登记的期望命名空间。只有应用代码与测试明确证明消费该字段时，才能把它升级为实际运行时边界的一部分。

### 3. Env Projection Rules

#### 3.1 sub2api

`tenant render-env --target prod0-main --app sub2api` 只投影：

- `REDIS_HOST`
- `REDIS_PORT`
- `REDIS_PASSWORD`
- `REDIS_DB`
- `REDIS_ENABLE_TLS`

不再投影 `REDIS_USER` 和 `REDIS_KEY_PREFIX`，因为当前 `sub2api` 代码并不消费这两个字段。

#### 3.2 newapi

`tenant render-env --target prod0-main --app newapi` 继续投影：

- `REDIS_CONN_STRING`
- `REDIS_URL`

但 URL 形态统一改为不带用户名，并按下列规则生成：

- `REDIS_ENABLE_TLS=false` 时使用 `redis://`
- `REDIS_ENABLE_TLS=true` 时使用 `rediss://`
- 密码必须先做 URL encode，再写入 userinfo 段

示例：

```text
redis://:<redis_password>@redis7-prod:6379/<db>
```

避免继续向现网写入“依赖 ACL 用户名”的连接串。

### 4. Validation And Audit Rules

`tenant validate` 与相关测试基线必须统一调整：

- 不再要求 `prod0-main` 的 Redis tenant secret 必须包含 `REDIS_USER`
- Redis 唯一性校验改为：
  - `REDIS_DB` 唯一
  - 规范化后的 `REDIS_KEY_PREFIX` 唯一
- 不再把“缺少 `REDIS_USER`”视为正式错误
- 继续禁止两个应用共享相同 `REDIS_DB`
- 继续禁止两个应用共享相同 `REDIS_KEY_PREFIX`

规范化规则：

- 去除首尾空白
- 强制要求以 `:` 结尾
- 比较时使用规范化后的值

校验含义：

- `REDIS_DB` 唯一是当前唯一可验证的运行时逻辑分区规则
- `REDIS_KEY_PREFIX` 唯一只是控制面登记一致性规则，不等价于“应用已按此前缀隔离”

如果未来重新引入 ACL 用户模型，应作为新的显式策略版本，而不是当前规则上的隐含扩展。

### 5. Inventory And Documentation Model

`inventory/servers/prod0-main/app-resources.json`、`app_resources.md`、`inventory.json` 和生成 README 必须统一表达：

- `prod0-main` Redis 已采用 DB 级隔离
- `prod0-main` Redis 已采用 DB 级逻辑分区，而非强安全隔离
- 每个应用记录其 `db` 与 `key_prefix`
- `user` 字段若保留，只能标记为非运行时必需的历史/兼容信息，不能再暗示 live runtime 依赖该字段

README 中必须明确说明：

- Redis 运行时逻辑分区以 DB 为准
- `key_prefix` 目前是登记字段，不表示应用已经被验证会严格按此前缀使用所有 Redis key
- 控制面不会为 `prod0-main` 的 Redis 运行时强制依赖 ACL 用户名
- Redis 密码在该阶段属于共享 runtime 凭据，不表示租户级独立 Redis 身份

### 6. Migration Plan

控制面迁移顺序固定为：

1. 先补红灯测试，锁定 `sub2api` 与 `newapi` 的新投影规则
2. 修改 `tenant render-env`、校验逻辑、模板与文档生成
3. 本地跑针对性测试
4. 在生产机备份现有 env 与 Redis ACL 状态，保留快速回滚路径
5. 在生产机重新渲染 `newapi.prod0.env` 和 `sub2api.prod0.env`
6. 逐个重建应用容器
7. 验证健康检查、Redis 连接、登录链路和无 `WRONGPASS`
8. 只有在日志、连接信息和直接认证验证都确认无客户端继续使用旧 ACL 用户后，才清理不再需要的 Redis ACL 用户
9. 任一步失败，立即恢复上一个稳定 env 并回到变更前 Redis ACL 状态

### 7. Non-Goals

本次设计明确不做：

- 要求所有应用支持 Redis ACL 用户名
- 在 `prod0-main` 上继续推进 Redis 用户级租户身份隔离
- 把 Redis 共享口令误表述为“每应用独立 Redis 密码”
- 调整 PostgreSQL 和 MinIO 的既有隔离模型
- 为 WSL 引入与 `prod0-main` 完全一致的 Redis 策略

## Testing Strategy

测试必须先覆盖以下行为：

- `sub2api` 的渲染结果不含 `REDIS_USER`
- `sub2api` 的渲染结果保留 `REDIS_ENABLE_TLS`
- `newapi` 的 `REDIS_CONN_STRING` / `REDIS_URL` 不含用户名，仅保留密码与 DB，并覆盖 `redis://` / `rediss://` 与 URL encode 分支
- `prod0-main` Redis tenant secret 缺少 `REDIS_USER` 时，`tenant validate` 仍通过
- 两个应用共享同一 `REDIS_DB` 时校验失败
- 两个应用共享同一规范化 `REDIS_KEY_PREFIX` 时校验失败
- 生成的 `app_resources.md` / README 正确表达“逻辑分区而非强安全隔离”的 live state

## Success Criteria

- `sub2api` 与 `newapi` 都可以在 `prod0-main` 上仅依赖 Redis `default` 用户密码认证运行
- `tenant render-env` 不再生成对 ACL 用户名有硬依赖的生产 env
- `tenant validate` / `tenant audit` / README / inventory 对 Redis live state 的描述一致
- 控制面文档不再把 DB 级逻辑分区误写成强安全隔离
- 生产验证中不再出现 Redis `WRONGPASS` 相关错误
