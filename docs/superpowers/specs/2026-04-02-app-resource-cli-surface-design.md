# App Resource CLI Surface Design

**Date:** 2026-04-02

## Goal

把当前 `tenant` 正式对象面收编进 `app` 域，形成“`app object` + `app resource` + `app delivery`”三面结构，强化“资源租户关系从属于 app”的公开心智模型，同时保持现有声明真源、projection 真源与 ledger substrate 不变。

本轮目标：

- 公开正式入口统一为 `uv run python -m ops.cli app resource ...`
- `app resource` 继续只公开 `search / get / verify / refresh-ledger`
- `tenant` 退出默认公开入口，不保留长期 compat/alias/wrapper
- 继续使用现有 `app-resources.json`、`secrets/app-resources/...`、`app_resource_summary`、`tenants` ledger 作为底层真源与投影
- 同步 docs、skills、catalog、测试到新口径

## Scope

本轮纳入：

- `uv run python -m ops.cli app resource ...`
- `app --help` 暴露 `object / resource / delivery`
- `app resource` 动作：`search / get / verify / refresh-ledger`
- 既有 `tenant` 对象测试与 skill/catalog 合同改写到 `app resource`
- architecture、README/skill 指针、CLI help、测试同步

本轮不纳入：

- `app-resources.json` 重命名
- `inventory.services.<app>.app_resource_summary` 字段重命名
- `ledgers/app_resources.json|md` 文件重命名
- `ops/domain/tenant/` 立即重构为新目录名
- `validate / audit / audit-live / render-env` 迁移设计之外的额外语义扩张
- 兼容过渡窗口、双轨公开入口

## Problem

当前 `tenant` 这层对象并不多余，但 `tenant` 这个顶层公开名称会把“应用关联的共享基础设施资源关系”误读成一个独立并列实体域。

代码与合同的实际语义是：

- 选择器是 `target + app`
- 真源是 `inventory/servers/<target>/app-resources.json`
- 核验目标是 `secrets/app-resources/<target>/<app>/` 与 `inventory.services.<app>.app_resource_summary`

这更接近“app 关联资源对象”，而不是独立业务实体。继续保留顶层 `tenant`，会让公开心智模型与底层事实继续错位。

## Decision

正式公开命令面调整为：

```bash
uv run python -m ops.cli app object ...
uv run python -m ops.cli app resource ...
uv run python -m ops.cli app delivery ...
```

具体决策：

1. `tenant` 顶层公开入口退出正式合同。
2. `app` 从双面扩为三面：`object`、`resource`、`delivery`。
3. `app resource` 承接当前 `tenant v1` 的正式对象职责。
4. 本轮是命令面和公开合同切换，不做底层真源迁移。
5. 不保留 `tenant` 长期 compat 入口，避免双轨继续污染正式边界。

## Boundary

| 面 | 管什么 | 不管什么 |
| --- | --- | --- |
| `app object` | 应用对象、catalog、合同定位、summary/ledger 指针 | 共享基础设施资源归属、正式交付 |
| `app resource` | app 关联的 PostgreSQL/Redis/MinIO 等共享资源声明、secret scope、`app_resource_summary` projection、一致性核验 | app catalog、合同交付、runtime env 生成、live 专题运维 |
| `app delivery` | 应用正式交付流程、构建、部署、验证、回滚 | 对象查询、资源归属真源 |

关键边界：

- `app resource` 仍以 `app-resources.json` 为 expected truth
- `app_resource_summary` 仍只是 projection evidence
- `app resource verify` 不混入 live runtime probe
- `projection runtime-env` 继续独立于 `app resource`

## CLI Shape

正式公开命令为：

```bash
uv run python -m ops.cli app resource search --target <target> --repo-root /root/work/OP_Linux
uv run python -m ops.cli app resource get --target <target> --app <app> --repo-root /root/work/OP_Linux
uv run python -m ops.cli app resource verify --target <target> --app <app> --repo-root /root/work/OP_Linux
uv run python -m ops.cli app resource refresh-ledger --target <target> --repo-root /root/work/OP_Linux --write
```

统一约束：

- 继续使用 `--app` 作为稳定选择器
- `command` 统一为 `app`
- `action` 采用 `resource.search`、`resource.get`、`resource.verify`、`resource.refresh-ledger`
- CLI help、skill 示例、catalog entrypoint 全部以 `app resource` 为准

## Source Of Truth

本轮不迁移底层命名，继续保留：

- declaration: `inventory/servers/<target>/app-resources.json`
- secret scope: `secrets/app-resources/<target>/<app>/*.env`
- projection: `inventory/servers/<target>/inventory.json -> services.<app>.app_resource_summary`
- ledger projection: `inventory/servers/<target>/ledgers/app_resources.json|md` 与 `inventory.object_ledgers`

原因：

1. 当前目标是切换公开命令面与心智模型。
2. 同轮重命名底层真源会把一次入口重构扩成一次对象真源迁移。
3. `resource-tenants`、`app_resource_summary`、`tenants` ledger 虽然命名保留旧词，但作为内部 substrate 仍可接受，后续可单独治理。

## Error Contract

公开入口改为 `app resource` 后，结构化错误前缀同步调整为 `app.resource.*`。

示例：

- `app.resource.object_not_found`
- `app.resource.secret_file_missing`
- `app.resource.secret_file_scope`
- `app.resource.registry_mismatch`
- `app.resource.projection_drift`

约束：

- 不再对外暴露 `tenant.*` 作为正式错误前缀
- 内部 helper 若仍沿用旧常量，可在 handler/CLI 层统一映射

## Implementation Shape

本轮优先重挂命令面，不重写领域逻辑：

```text
ops/cli/
  apps.py
  tenant.py

ops/domain/tenant/
  models.py
  registry.py
  handlers.py
```

实现原则：

1. 在 `ops/cli/apps.py` 中新增 `resource` surface。
2. 复用当前 `ops.domain.tenant` handler，避免同轮同时改名和改逻辑。
3. `ops/cli/prod0_postgres_app_resource_audit.py` 退出正式公开入口合同；若文件暂留，也只视为待移除遗留，不再被 docs/skills/tests 当作正式入口。
4. 领域目录改名如 `ops/domain/app_resource/` 另起一轮，不混入本次。

## Migration Strategy

本轮采用短周期、明确切换：

1. 先冻结测试合同  
   `app --help` 必须出现 `resource`；`tenant --help` 不再属于正式合同。

2. 再切 parser 与 handler 路由  
   `app resource ...` 直接接入现有资源对象逻辑。

3. 同轮收口 docs / skills / catalog  
   所有 active 文档与 skill 示例都只指向 `app resource`。

4. 最后移除 `tenant` 公开面残留  
   不保留新旧双轨共存窗口。

## Testing Strategy

本轮最小必要验证：

- `tests/test_cli_entrypoints.py`
  - `app --help` 包含 `resource`
  - `app resource --help` 暴露 `search / get / verify / refresh-ledger`
  - `tenant --help` 不再作为正式公开合同断言
- 资源对象行为测试
  - 原 `tenant` 对象测试迁到 `app resource` 入口
- `tests/test_onepanel_plugin_and_skills.py`
  - skill 示例改为 `uv run python -m ops.cli app resource ...`
  - catalog entrypoint 改为 `uv run python -m ops.cli app`
- 必要时补一个 architecture 文档口径测试

本轮不要求：

- live runtime 验证
- 底层 ledger 文件重命名验证
- 旧 `tenant` compat 行为回归

## Risks

### 风险 1：只改名字，不改边界

如果只是把 `tenant` 文案替换为 `resource`，但 docs、skill、help、错误前缀仍旧混用，用户会看到新的命令树却仍然感知到旧域。

控制方式：CLI、tests、skill、architecture 同轮切换；不保留双轨。

### 风险 2：把本轮扩成真源迁移

若同时重命名 `app-resources.json`、`app_resource_summary`、`tenants` ledger，本轮会从公开入口重构膨胀为数据面迁移。

控制方式：只改公开入口和合同，不改底层 substrate 名称。

### 风险 3：`app object` 与 `app resource` 再次耦合

若把资源关系直接塞回 `app object get/verify`，`app` 域会失去清晰分面，失败语义也会混成一团。

控制方式：保持 `app resource` 为独立 surface，而不是并入 `app object`。

## Success Criteria

当以下条件同时满足时，认为本轮达成：

- `uv run python -m ops.cli app resource ...` 成为唯一正式资源对象入口
- `app --help` 已稳定暴露 `object / resource / delivery`
- `tenant` 不再作为默认公开入口出现在 active docs、skills、合同测试中
- `app resource` 继续只负责 `search / get / verify / refresh-ledger`
- 底层真源与投影命名保持不变，没有引入数据面迁移
- 最小相关测试通过，且只覆盖新正式入口
