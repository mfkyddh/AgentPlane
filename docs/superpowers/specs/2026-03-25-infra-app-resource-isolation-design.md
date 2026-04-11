# Infrastructure Tenant Isolation Design

**Date:** 2026-03-25

## Goal

为 `OP_Linux` 建立一套正式、可审计、可强制执行的基础设施租户隔离方案。该方案要求仓库统一掌握基础设施管理员凭据，并为每个正式应用分配独立的数据库、账号、密码、Bucket、Namespace 或等价隔离单元，使应用之间在 PostgreSQL、Redis、MinIO 等基础设施上的资源、身份和权限互不干扰。

第一版要求覆盖：

- 正式主机：`prod0-main`
- 首批纳入应用：`sub2api`、`newapi`

第一版明确不纳入：

- `sub2apipay`

## Current State

- 仓库当前已经把正式基础设施真源收口到 `OP_Linux`，并通过 `inventory/servers/prod0-main/inventory.json` 记录 `postgres18-prod`、`redis7-prod`、`minio-prod` 等基础设施。
- 基础设施管理员类 secrets 当前主要以扁平文件形式存在于 `secrets/services/`，例如 `postgres.env`、`redis.conf`、`minio.env`。
- 应用运行时 env 也以扁平文件形式存在于 `secrets/services/<app>.prod0.env` 或 `secrets/services/<app>.wsl.env`，但这些文件只是连接参数集合，并没有被定义为“基础设施租户真源”。
- 现有 `ops.cli app validate-contract` 只校验应用依赖容器、数据目录、入口等合同约束，并不会强制校验“每个应用拥有独立数据库 / 用户 / Bucket / Namespace”。
- 仓库目前能够明确记录应用依赖哪个基础设施容器，但还不能系统回答“某个应用具体拥有哪个数据库、哪个 Redis user、哪个 Bucket、这些资源的正式 secret 文件在哪里”。

## Constraints

- `OP_Linux` 仍然是正式生产控制面的唯一真源，真实生产凭据必须保留在本仓库 `secrets/` 下，不下放到应用仓库。
- 非敏感索引、摘要、依赖关系必须写入 `inventory/`，但 `inventory/` 不保存真实密码。
- 生产基础设施管理员账号只能用于运维控制面，不允许应用运行时直接使用。
- 强制隔离必须覆盖三层：
  - 身份隔离：独立账号与密码
  - 资源隔离：独立数据库 / Bucket / Namespace / 等价隔离单元
  - 权限隔离：仅授予本应用所需最小权限
- 现有 `sub2api`、`newapi` 需要补齐台账并迁移到统一规范，不能只要求今后新增应用遵守。
- `sub2apipay` 本轮显式排除，不阻塞第一版方案落地。

## Options

### Option A: 文档台账型

只新增文档和手工登记规则，继续让管理员凭据与应用运行时凭据靠人工维护。

优点：

- 改动最小
- 能快速形成纸面规范

缺点：

- 不能形成强制校验
- 仍然容易回到“应用自己在 env 里随便写”的状态
- 无法可靠发现跨应用资源冲突

### Option B: 租户合同型

把每个应用对基础设施的独立使用视为正式“租户资源合同”，真实租户凭据放在 `secrets/`，非敏感分配台账放在 `inventory/`，并扩展 `ops.cli` 做一致性校验和审计。

优点：

- 能与现有 `app contract`、`inventory-refresh`、`doc-sync` 机制闭环
- 可以把“每应用独立资源”变成硬规则，而不是约定俗成
- 兼顾可读文档与后续自动化

缺点：

- 需要扩展合同 schema、台账结构与 CLI
- 第一版实施量中等

### Option C: 中央资源总表生成型

建立全局资源分配总表，由它统一生成应用运行时 env、inventory 摘要和远端建库建用户动作。

优点：

- 一致性最强
- 后续自动化空间最大

缺点：

- 初始复杂度最高
- 一次性引入生成器和完整生命周期，风险高于当前仓库需要

## Approved Design

采用 **Option B: 租户合同型**。第一版先把“资源租户”定义为正式控制面对象，落成目录结构、台账结构、合同扩展和强制校验；后续如需要再向生成型方案演进。

### 1. Core Model

每个正式应用都必须在基础设施层拥有一组独立、可审计的 **tenant resources**。这些资源不是“应用 env 里的一组字符串”，而是 OP_Linux 控制面下的正式对象。

对每个应用，正式租户记录至少包括：

- PostgreSQL：独立数据库、独立用户、独立密码
- Redis：独立 ACL user、独立密码、独立 logical DB、独立 key prefix
- MinIO：独立 Bucket，优先独立 access key / secret key
- 支持 Namespace 的系统：独立 Namespace
- 不支持 Namespace 的系统：必须使用等价隔离单元替代

### 2. Mandatory Isolation Rules

以下规则必须写成仓库级硬约束：

- 应用运行时禁止使用 PostgreSQL / Redis / MinIO 管理员账号。
- 不同应用不得共享同一个 PostgreSQL 数据库。
- 不同应用不得共享同一个 PostgreSQL 用户。
- 不同应用不得共享同一个 MinIO Bucket，除非登记为显式例外。
- Redis 不能只靠“不同 DB”视为隔离完成；必须同时拥有独立 ACL user 和独立 key prefix。
- 任何共享资源都必须作为例外登记，写明共享对象、原因、风险、批准人和失效时间；未登记共享一律视为违规。

### 3. Repository Layout

方案采用“管理员级 secrets + 应用租户级 secrets + 非敏感台账 + 应用运行时投影”四层结构。

#### 3.1 管理员级 secrets

仅供 OP_Linux 控制面、建库建用户、授权、轮换使用。

```text
secrets/services/postgres/admin.prod0.env
secrets/services/redis/admin.prod0.env
secrets/services/minio/admin.prod0.env
```

设计含义：

- PostgreSQL 管理员连接信息从当前扁平 `postgres.env` 口径演进为管理员真源
- Redis 管理口令或 ACL 管理参数进入 `admin.prod0.env`
- MinIO root 或管理员 access key 进入 `admin.prod0.env`

#### 3.2 应用租户级 secrets

每个应用每种基础设施单独一份真实 secret 文件，作为该应用正式租户真源。

```text
secrets/app-resources/prod0-main/sub2api/postgres.env
secrets/app-resources/prod0-main/sub2api/redis.env
secrets/app-resources/prod0-main/sub2api/minio.env

secrets/app-resources/prod0-main/newapi/postgres.env
secrets/app-resources/prod0-main/newapi/redis.env
secrets/app-resources/prod0-main/newapi/minio.env
```

WSL 也允许使用同样结构：

```text
secrets/app-resources/wsl/<app>/...
```

但第一版正式强制以 `prod0-main` 为主，WSL 结构与之对齐即可。

#### 3.3 非敏感模板

模板保留在 `templates/`，并与真实目录结构对齐：

```text
templates/services/postgres/admin.env.example
templates/services/redis/admin.env.example
templates/services/minio/admin.env.example
templates/app-resources/postgres.env.example
templates/app-resources/redis.env.example
templates/app-resources/minio.env.example
```

#### 3.4 非敏感租户台账

新增主机级租户资源台账：

```text
inventory/servers/prod0-main/app-resources.json
inventory/servers/prod0-main/app_resources.md
```

职责区分：

- `app-resources.json`：结构化租户分配真源
- `app_resources.md`：人类可读摘要
- `inventory.json`：服务器总体视图，保留汇总信息

#### 3.5 应用运行时投影文件

现有 `secrets/services/<app>.prod0.env` 可以继续保留，但其角色改为“运行时投影”，不再是租户资源真源。

真源关系固定为：

- 敏感租户真源：`secrets/app-resources/...`
- 应用运行时投影：`secrets/services/<app>.prod0.env`

### 4. Naming Rules

资源命名统一围绕 `app_id` 和环境短名展开。

命名基线：

- SQL 标识符使用 `snake_case`
- Bucket / Namespace 使用 `kebab-case`
- 环境短名第一版采用 `prod0`

#### 4.1 PostgreSQL

- 数据库名：`<app_id>_prod0`
- 用户名：`<app_id>_prod0`
- 密码：随机生成，不允许可预测命名

示例：

- `sub2api_prod0`
- `newapi_prod0`

#### 4.2 Redis

- ACL user：`<app_id>_prod0`
- key prefix：`<app_id>:`
- logical DB：为每个应用分配唯一 DB 编号

示例：

- user: `sub2api_prod0`
- prefix: `sub2api:`

#### 4.3 MinIO

- Bucket：`prod0-<app_id>`
- access key：`<app_id>_prod0`

示例：

- `prod0-sub2api`
- `prod0-newapi`

#### 4.4 Namespace

支持 Namespace 的系统统一采用：

- `prod0-<app_id>`

如系统不支持正式 Namespace，则必须在设计中明确其等价隔离单元。

### 5. Sensitive Data and Inventory Schema

#### 5.1 租户 secret 文件字段

PostgreSQL 示例：

```dotenv
PGHOST=postgres18-prod
PGPORT=5432
PGDATABASE=sub2api_prod0
PGUSER=sub2api_prod0
PGPASSWORD=replace-with-real-password
PGSSLMODE=disable
```

Redis 示例：

```dotenv
REDIS_HOST=redis7-prod
REDIS_PORT=6379
REDIS_USER=sub2api_prod0
REDIS_PASSWORD=replace-with-real-password
REDIS_DB=1
REDIS_KEY_PREFIX=sub2api:
REDIS_ENABLE_TLS=false
```

MinIO 示例：

```dotenv
S3_ENDPOINT=http://minio-prod:9000
S3_BUCKET=prod0-sub2api
S3_ACCESS_KEY=sub2api_prod0
S3_SECRET_KEY=replace-with-real-secret
S3_REGION=us-east-1
S3_PATH_STYLE=true
```

#### 5.2 `app-resources.json` 结构

`app-resources.json` 以 `app_id` 为主键，不保存真实密码，只记录归属、命名、投影文件和轮换信息。

示例结构：

```json
{
  "sub2api": {
    "owner_app": "sub2api",
    "status": "active",
    "postgres": {
      "database": "sub2api_prod0",
      "user": "sub2api_prod0"
    },
    "redis": {
      "user": "sub2api_prod0",
      "db": 1,
      "key_prefix": "sub2api:"
    },
    "minio": {
      "bucket": "prod0-sub2api",
      "access_key": "sub2api_prod0"
    },
    "namespaces": [
      {
        "system": "redis-keys",
        "name": "sub2api:"
      }
    ],
    "secret_files": [
      "secrets/app-resources/prod0-main/sub2api/postgres.env",
      "secrets/app-resources/prod0-main/sub2api/redis.env",
      "secrets/app-resources/prod0-main/sub2api/minio.env"
    ],
    "rotation": {
      "last_rotated_at": "2026-03-25",
      "rotation_owner": "OP_Linux"
    }
  }
}
```

### 6. Contract Extension

现有 `deploy/op/contract.yaml` 需要从“声明依赖容器”升级到“声明依赖容器 + 正式租户资源”。

新增非敏感块：

```yaml
infra:
  depends_on_containers:
    - postgres18-prod
    - redis7-prod
    - minio-prod
  tenant_resources:
    postgres:
      required: true
      database: sub2api_prod0
      user: sub2api_prod0
      secret_file: secrets/app-resources/prod0-main/sub2api/postgres.env
    redis:
      required: true
      user: sub2api_prod0
      db: 1
      key_prefix: sub2api:
      secret_file: secrets/app-resources/prod0-main/sub2api/redis.env
    minio:
      required: true
      bucket: prod0-sub2api
      access_key: sub2api_prod0
      secret_file: secrets/app-resources/prod0-main/sub2api/minio.env
```

规则：

- 合同只保存非敏感资源标识和 secret 路径，不保存真实密码。
- `tenant_resources` 只声明该应用“应该拥有什么”，真实值仍以 `secrets/app-resources/...` 为准。
- 如果应用未使用某类基础设施，可以在合同中不声明对应块；但只要声明使用，就必须拥有独立租户资源。

### 7. CLI and Enforcement

为了把方案变成硬规则，必须扩展现有 CLI，而不是只写文档。

#### 7.1 `ops.cli app validate-contract`

新增校验能力：

- 应用声明依赖 PostgreSQL 时，必须存在 `infra.tenant_resources.postgres`
- `tenant_resources.*.secret_file` 必须存在，且位于 `secrets/app-resources/<target>/<app_id>/`
- 合同中的数据库名、用户名、Bucket、Namespace、Redis user/DB/prefix 必须与 `app-resources.json` 一致
- 禁止 `newapi` 合同引用 `sub2api` 的 tenant secret
- 不允许同一 target 下两个应用拥有相同 PostgreSQL 数据库名或用户名
- 不允许同一 target 下两个应用拥有相同 MinIO Bucket
- Redis 至少要求 `(user, db, key_prefix)` 组合唯一

#### 7.2 新增租户审计入口

建议新增 `ops.cli tenant ...` 命令域，第一版至少包含：

- `uv run python -m ops.cli app resource verify --target prod0-main`
- `uv run python -m ops.cli app resource verify --target prod0-main`
- `uv run python -m ops.cli projection runtime-env apply --target prod0-main --app <app_id>`

职责：

- `validate`：校验合同、台账、secret 文件是否一致
- `audit`：校验资源唯一性、运行态漂移和越权引用
- `render-env`：从 tenant secrets 生成应用运行时投影 env

第一版可以先不做全自动 provisioning，但必须把租户校验与投影渲染收口到 CLI。

#### 7.3 `inventory-refresh` / `doc-sync`

扩展后：

- `inventory-refresh` 把每个应用的 `tenant_resources` 摘要写入 `inventory/servers/<target>/inventory.json` 的应用条目
- `doc-sync` 在应用摘要里写出：
  - 正式 PostgreSQL 数据库名与用户名
  - 正式 Redis user / DB / prefix
  - 正式 MinIO Bucket
  - 对应 tenant secret 文件路径

### 8. Lifecycle

#### 8.1 Provision

新增应用或纳入现有应用时，流程固定为：

1. 在 `app-resources.json` 中登记草稿租户
2. 创建 `secrets/app-resources/<target>/<app>/...` 文件
3. 使用管理员 secrets 在真实基础设施上创建数据库 / 用户 / Bucket / ACL user / 权限
4. 生成或更新 `secrets/services/<app>.<target>.env` 运行时投影
5. 校验合同、租户台账与运行时投影一致

#### 8.2 Rotate

密码轮换必须被定义为正式动作：

- PostgreSQL：改应用用户密码，更新 tenant secret，重渲染应用 env，验证通过后登记轮换时间
- Redis：改 ACL user 密码，必要时校验 DB 与 prefix 约束
- MinIO：更新应用 access key / secret key 或 service account

每次轮换都必须回写：

- `last_rotated_at`
- 操作者
- 影响应用
- 验证结果

#### 8.3 Retire

应用下线后：

- 先把租户状态改为 `retiring`
- 完成数据导出或归档
- 撤销凭据，把状态改为 `retired`
- 在保留窗口结束前，不允许直接把旧资源静默复用给别的应用

#### 8.4 Audit

审计分为四类：

- 静态审计：资源命名是否唯一、合同是否引用正确租户
- 权限审计：应用是否仍使用管理员账号
- 运行时审计：远端是否真实存在对应数据库 / 用户 / Bucket / ACL user
- 漂移审计：应用运行时 env 是否偏离 tenant secrets 真源

### 9. Existing Application Migration

第一批迁移范围固定为：

- `sub2api`
- `newapi`

本轮排除：

- `sub2apipay`

建议目标态：

- `sub2api`
  - PostgreSQL DB/User: `sub2api_prod0`
  - Redis user: `sub2api_prod0`
  - Redis key prefix: `sub2api:`
  - 若使用 MinIO，则 Bucket 为 `prod0-sub2api`
- `newapi`
  - 先按真实依赖登记已接入的基础设施，不在 spec 中假定其现状
  - 只要启用 PostgreSQL，则 DB/User 使用 `newapi_prod0`
  - 只要启用 Redis，则 user 使用 `newapi_prod0`，key prefix 使用 `newapi:`
  - 只要启用 MinIO，则 Bucket 使用 `prod0-newapi`

迁移顺序：

1. 新增模板、租户台账结构和合同字段
2. 为 `sub2api`、`newapi` 补齐 tenant secret
3. 在真实基础设施上创建或校正租户资源
4. 把应用运行时 env 改为从 tenant secret 投影生成
5. 执行合同校验、租户审计、部署验证、inventory 刷新和文档回写

### 10. Acceptance Criteria

方案完成后，必须满足：

- `prod0-main` 上任何正式应用只要依赖 PostgreSQL、Redis、MinIO 或 namespace 型基础设施，就必须有独立租户记录。
- 任何正式应用不得使用基础设施管理员账号作为运行时凭据。
- 任意两个应用不得共享 PostgreSQL 数据库、PostgreSQL 用户、MinIO Bucket。
- 任意两个应用不得共享同一组 Redis `(ACL user, key prefix)`；logical DB 也必须显式分配。
- `secrets/app-resources/...`、`app-resources.json`、`deploy/op/contract.yaml`、`inventory.json` 四处信息必须能互相对上。
- 仓库必须能直接回答 `sub2api` 和 `newapi` 各自拥有的数据库、账号、Bucket、Namespace 和 tenant secret 文件位置。

## Validation

第一版实施后至少需要做以下验证：

1. `validate-contract` 能拒绝缺少 `tenant_resources` 的正式应用合同。
2. `validate-contract` 能拒绝应用引用其他应用 tenant secret 的情况。
3. `tenant validate` 能发现资源重名、Bucket 冲突、Redis prefix 冲突。
4. `tenant render-env` 能从 tenant secret 生成应用运行时 env 投影。
5. `inventory-refresh` 能把租户摘要同步到主机 inventory。
6. `doc-sync` 能把租户摘要同步到应用侧非敏感文档。
7. `sub2api` 与 `newapi` 完成纳入后，仓库内能明确定位其 PostgreSQL / Redis / MinIO 租户真源和台账记录。

## Non-Goals

- 第一版不要求一次性实现所有基础设施的全自动 provisioning。
- 第一版不处理 `sub2apipay` 的租户纳入。
- 第一版不引入外部密码管理器，真实凭据仍统一保存在本仓库 `secrets/`。
- 第一版不改变 `OP_Linux` 是正式控制面真源的总体原则。
