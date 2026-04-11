# App Resource Object V1 Design

**Date:** 2026-04-02

## Goal

把 `tenant` 正式对象语义彻底收敛为 `app resource`，不保留兼容层，把公开入口、内部模块、tracked truth、projection、ledger、secret scope 全部统一到 `app resource` 命名体系与物理路径。

本轮目标：

- 公开入口只剩 `uv run python -m ops.cli app resource ...`，不再注册 `tenant` 公开命令
- 内部数据、模块、错误前缀、测试、docs、skills 统一指向 `app resource` ；旧 `tenant`、`app-resources.json` 等命名被完全替换
- tracked truth、projection、ledger、secret scope 分别使用 `app-resources.json`、`app_resource_summary`、`ledgers/app_resources.json|md`、`secrets/app-resources/<target>/<app>/`
- `app resource verify` 保持以 `app_resource_summary` 投影为 evidence，`refresh-ledger` 继续写 `ledgers/app_resources*`

## Scope

本轮纳入：

- CLI：`app resource search / get / verify / refresh-ledger`
- 内部模块：`ops/domain/app/resource_*`
- 声明真源：`inventory/servers/<target>/app-resources.json`
- 投影：`inventory.services.<app>.app_resource_summary`
- Ledger：`inventory/servers/<target>/ledgers/app_resources.json|md`
- Secret scope：`secrets/app-resources/<target>/<app>/`
- `README`、architecture、skill、测试、inventory fixture、ledger generator 同轮同步命名

本轮不纳入：

- 旧 `tenant` 兼容入口、alias、双轨命令
- 旧命名 `app-resources.json`、`app_resource_summary`、`ledgers/tenants*`、`secrets/app-resources/...` 的任何读写
- 不受当前对象影响的 `app object` / `app delivery` 语义扩张
- 实时 runtime env 生成、live audit、projection CLI 的功能迁移

## Boundary

| 面 | 管什么 | 不管什么 |
| --- | --- | --- |
| `app object` | 应用合同、catalog、summary、ledger 指针 | 具体共享资源的归属、secret、投影一致性 |
| `app resource` | app 关联的 PostgreSQL/Redis/MinIO 等共享资源的声明、secret scope、`app_resource_summary` 投影、一致性校验 | runtime / delivery / live 运行时写入 |
| `app delivery` | 正式交付／部署／交付回归证据 | 资源租户真源 |

关键约束：

- `app resource` 只负责 `search / get / verify / refresh-ledger`，不再扩散到 `runtime env`、`audit-live`、`projection` CLI
- `app resource` 的 `verify` 以 `app-resources.json` 为 expected，以 `app_resource_summary` 为 evidence
- `app resource refresh-ledger` 只写 `ledgers/app_resources.json|md`，不碰旧 `tenant` ledger

## Decision

将所有正式对象语义硬切到新命名。

| 层 | 最终命名 |
| --- | --- |
| CLI | `uv run python -m ops.cli app resource ...` |
| 内部模块 | `ops/domain/app/resource_models.py` / `resource_registry.py` / `resource_handlers.py` |
| declaration | `inventory/servers/<target>/app-resources.json` |
| projection field | `inventory.services.<app>.app_resource_summary` |
| ledger | `inventory/servers/<target>/ledgers/app_resources.json` / `.md` |
| secret scope | `secrets/app-resources/<target>/<app>/` |
| error prefix | `app.resource.*` |

硬约束：

1. 不保留任何 `tenant` 命名作为正式入口或真源。
2. 不保留 `app-resources.json` 路径的读写；所有对象行为都使用 `app-resources.json`。
3. 不保留 `app_resource_summary` 字段；`verify`、`get` 聚合的是 `app_resource_summary`。
4. `refresh-ledger` 只写新的 ledger 文件，千万不可再输出到 `ledgers/tenants*`。

## CLI Shape

```bash
uv run python -m ops.cli app resource search --target <target> --repo-root /root/work/OP_Linux
uv run python -m ops.cli app resource get --target <target> --app <app> --repo-root /root/work/OP_Linux
uv run python -m ops.cli app resource verify --target <target> --app <app> --repo-root /root/work/OP_Linux
uv run python -m ops.cli app resource refresh-ledger --target <target> --repo-root /root/work/OP_Linux --write
```

约束：

- `--app` 仍是唯一稳定选择器
- `action` 语义固定为 `resource.search / resource.get / resource.verify / resource.refresh-ledger`
- CLI help、skills、documentation 全部指向 `app resource`；旧 `tenant` 命令不再出现在 active docs

## Source Of Truth

- declaration: `inventory/servers/<target>/app-resources.json`
- secret scope: `secrets/app-resources/<target>/<app>/*.env`
- projection: `inventory/servers/<target>/inventory.json -> services.<app>.app_resource_summary`
- ledger projection: `inventory/servers/<target>/ledgers/app_resources.json|md`

禁止保留：`app-resources.json`、`app_resource_summary`、`ledgers/tenants.*`、`secrets/app-resources/...`

## Object Model

`app resource` 对象用 `target + app` 作为选择器，字段至少包括：

- `app`
- `owner_app`
- `resource_kinds`
- `ledger_status`
- `secret_files`
- `app_resource_summary`

按资源种类继续暴露子对象：

- `postgres`
- `redis`
- `minio`

所有字段都直接映射到 `app-resources.json` 的结构，`get`/`verify` 读取后不做 live 写。

## Action Semantics

### `search`

- 只从 `app-resources.json` 读取
- 返回 `app`、`owner_app`、`resource_kinds`、`ledger_status`
- 不读旧 `resource-tenants` 或 `app_resource_summary`

### `get`

聚合：

- declaration (`app-resources.json`)
- secret files (`secrets/app-resources/<target>/<app>/`)
- projection (`app_resource_summary`)

### `verify`

最小核验集合：

1. declaration 结构完整
2. secret files 在安全路径下且存在
3. `app_resource_summary` 与 declaration 保持一致

输出 `ok / checks / failures / evidence`，错误前缀 `app.resource.*`

### `refresh-ledger`

- 写入 `inventory/servers/<target>/ledgers/app_resources.json` 和 `.md`
- 同步 `inventory.object_ledgers`
- 不再写 `tenants` ledger

## Verification Rule

所有 `verify` 逻辑以 `app_resource_summary` 为 evidence，绝不把投影反向当成 declaration。若 projection 不存在，按结构化缺失暴露，而不是继续使用老命名。

## Repository Structure

建议目录：

```text
ops/cli/
  apps.py
  app_resource.py

ops/domain/app/
  resource_models.py
  resource_registry.py
  resource_handlers.py

ops/domain/projection/
  runtime_env.py

ops/scripts/onepanel/
  ledger.py
```

原则：

1. CLI 只负责 expose `app resource` surface，handler 逻辑移入 `ops/domain/app/`
2. `app resource` 相关读取、校验、ledger 只依赖新路径和字段
3. 旧 `ops/domain/tenant` 必须彻底移动或删除，不保留 compat wrapper

## Testing Strategy

新增 `tests/test_app_resource_object_cli.py`，锁定以下行为：

- `app resource` 公开 `search / get / verify / refresh-ledger`
- `search` 基于 `app-resources.json`
- `get` 聚合 declaration、secret、projection
- `verify` 在 projection drift、secret 缺失、scope 越界时返回 `app.resource.*` failure
- `refresh-ledger` 刷新 `app_resources` ledger，不写旧 ledger

继续保留 `tests/test_app_resource_cli.py`，确保 `app` CLI 只曝光 `resource` surface

## Risks

### 风险 1：数据面命名残留

如果 `app` CLI 已改，但文件系统还写 `app-resources.json`、`app_resource_summary`，会在后续轮次再产生兼容成本。

控制方式：加入 `rg` 清扫和 inventory fixture 变更，同时让 `refresh-ledger`/`inventory write` 强制新路径。

### 风险 2：命令与对象语义错位

若 `app resource` 仍暴露 `plan`/`apply`/`render-env`，会让对象面膨胀到 runtime。控制方式：只保留 `search/get/verify/refresh-ledger`。

### 风险 3：old errors 泄漏

若 `app resource` 仍返回 `tenant.*` 错误前缀，skill 和 docs 会继续引用旧命名。控制方式：统一错误前缀到 `app.resource.*`，CI 中检查不再出现 `tenant.`。

## Success Criteria

- `uv run python -m ops.cli app resource ...` 成为唯一正式资源对象入口
- `app-resources.json` / `app_resource_summary` / `ledgers/app_resources.*` / `secrets/app-resources/...` 成为唯一 tracked truth 体系
- documentation、skills、tests、inventory fixture 和 ledger generator 全部指向 `app resource`
- CLI、handler、ledger 代码不再触碰 `tenant` 路径
- `verify` 输出结构化 `app.resource.*` 错误，`refresh-ledger` 只写到新 ledger
