# App V1 Design

**Date:** 2026-04-02

## Goal

为 `OP_Linux` 收敛第一版正式 `app` 域，形成“`app object` + `app delivery`”双面模型。

本轮目标：

- 为 `app` 建立正式对象面，统一表达受管应用对象
- 为现有交付链建立正式任务面，避免继续把对象查询和交付流程混在一起
- 对外稳定引用改为 `target + app`
- 保持不进入应用业务仓库运行面
- 保持不进入应用层运行面
- 保持现有 Docker / Compose 合同与交付语义，不在本轮扩张 runtime 类型

## Scope

本轮纳入：

- `uv run python -m ops.cli app object ...`
- `uv run python -m ops.cli app delivery ...`
- `app object` 动作：`search / get / verify / refresh-ledger`
- `app delivery` 动作：`validate-contract / build-artifact / ship-image / render-runtime / deploy / rollback / verify / inventory-refresh / doc-sync`
- 新增 tracked `app` catalog，作为 `target + app -> contract` 的正式解析入口
- `ops.domain.app` 对象层与任务层分层
- 同步 `README`、architecture、skill、CLI help、测试

本轮不纳入：

- 新的应用 runtime 类型
- 应用内部业务健康诊断、应用日志分析、应用进程内调试
- 应用仓库中的源码、测试、构建脚本或模板改造
- remote host 上额外的运行态编排框架
- 把 `inventory-refresh` / `doc-sync` 抽成通用 projection 框架
- compat / alias / wrapper / 兼容层

## Boundary

| 域 | 管什么 | 不管什么 |
| --- | --- | --- |
| `app object` | 受管应用声明、合同定位、inventory 投影、summary 投影、对象 ledger、一致性校验 | 构建、上传、切换、回滚、现场执行 |
| `app delivery` | 应用正式交付流程、切换计划、切换执行、交付后核验、inventory/doc 投影刷新 | 应用对象检索、对象台账查询 |
| `tenant` | 资源租户声明真源、secret scope、`app_resource_summary` projection 一致性 | 应用合同、应用交付流程 |
| `projection runtime-env` | 从 tenant truth 派生 app runtime env 文件 | 应用对象目录、应用交付切换 |
| `website` | 公网入口对象 | 应用交付对象和应用运行合同 |
| `service` | 基础设施与宿主服务对象 | 业务应用交付流程 |

## Decision

`app v1` 采用“双面收口、单域归档”的方式：

1. `app` 仍是一个正式域，但公开两个 surface：`object` 与 `delivery`。
2. `app object` 回答“这个应用对象是什么、现在登记成什么样”。
3. `app delivery` 回答“这个应用下一步如何正式交付”。
4. 公开稳定输入统一使用 `target + app`，不再把外部 `--contract` 文件路径保留为主入口。
5. `contract` 继续是应用仓库真源，但通过 OP_Linux tracked `app` catalog 做正式发现。
6. `inventory-refresh` 与 `doc-sync` 继续留在 `app delivery`，因为它们属于交付闭环的投影回写，不属于通用 `projection` 域。
7. 第一版不扩 runtime 类型，不改变既有 Docker / Compose 交付语义，只做边界重组和公开入口收口。

## Why Two Surfaces

当前 `app` 入口存在两个不同问题混在一起：

- 一类动作在查询和核验受管应用对象
- 一类动作在驱动正式交付流程

若继续把两类动作都堆在单层 `app <action>` 下，会出现：

- `app` 成为唯一没有清晰对象面的主域
- 公开入口长期依赖 `--contract /abs/path` 这种不稳定输入
- Agent 难以区分“查对象”和“做交付”

因此本轮不把 `app` 拆成两个独立顶级域，而是在同一域下明确双 surface：

- `app object`
- `app delivery`

这样既保留“应用是一个完整领域”的语义，又把对象面和任务面真正分开。

## CLI Shape

正式对象面：

```bash
uv run python -m ops.cli app object search --target <target> --repo-root /root/work/OP_Linux
uv run python -m ops.cli app object get --target <target> --app <app> --repo-root /root/work/OP_Linux
uv run python -m ops.cli app object verify --target <target> --app <app> --repo-root /root/work/OP_Linux
uv run python -m ops.cli app object refresh-ledger --target <target> --repo-root /root/work/OP_Linux --write
```

正式交付面：

```bash
uv run python -m ops.cli app delivery validate-contract --target <target> --app <app> --repo-root /root/work/OP_Linux
uv run python -m ops.cli app delivery build-artifact --target <target> --app <app> --repo-root /root/work/OP_Linux
uv run python -m ops.cli app delivery ship-image --target <target> --app <app> --repo-root /root/work/OP_Linux
uv run python -m ops.cli app delivery render-runtime --target <target> --app <app> --repo-root /root/work/OP_Linux
uv run python -m ops.cli app delivery deploy --target <target> --app <app> --repo-root /root/work/OP_Linux --dry-run
uv run python -m ops.cli app delivery deploy --target <target> --app <app> --repo-root /root/work/OP_Linux --execute
uv run python -m ops.cli app delivery verify --target <target> --app <app> --repo-root /root/work/OP_Linux --execute
uv run python -m ops.cli app delivery rollback --target <target> --app <app> --repo-root /root/work/OP_Linux --execute
uv run python -m ops.cli app delivery inventory-refresh --target <target> --app <app> --repo-root /root/work/OP_Linux --write
uv run python -m ops.cli app delivery doc-sync --target <target> --app <app> --repo-root /root/work/OP_Linux --write
```

约束：

- `--contract` 不再是公开主入口
- 内部解析 contract 时统一走 tracked `app` catalog
- 若 catalog 找不到 `target + app`，直接结构化失败，不退回隐式扫描或兼容路由

## Source Of Truth

| 层 | 真源 |
| --- | --- |
| app catalog | `inventory/apps/catalog.json` |
| app declaration | 应用仓库 `deploy/op/contract*.yaml` |
| app inventory projection | `inventory/servers/<target>/inventory.json -> services.<service_key>` |
| app human summary | 应用仓库 `docs/OP_LINUX_DEPLOYMENT*.md` |
| app object ledger | `inventory/servers/<target>/ledgers/apps.json|md` 与 `inventory.object_ledgers` |

规则：

1. `catalog` 只负责稳定寻址，不覆盖合同内容本身。
2. `contract` 仍是应用定义真源。
3. `inventory.services.<service_key>` 是 target 侧结构化投影，不反向成为合同真源。
4. `app summary` 是人类可读摘要，不反向成为任何机器真源。

## App Catalog Model

为支持 `target + app` 稳定引用，第一版增加 tracked catalog：

```json
{
  "apps": [
    {
      "app": "sub2api",
      "repo_name": "sub2api",
      "repo_root": "/root/work/sub2api",
      "service_key": "sub2api",
      "contracts": {
        "prod0-main": "deploy/op/contract.yaml",
        "wsl": "deploy/op/contract.yaml",
        "prod2-main": "deploy/op/contract.prod2.yaml"
      }
    }
  ]
}
```

第一版要求：

- `app` 是正式稳定引用
- `repo_root` 是应用仓库正式根目录，不从当前 shell 或隐式 sibling 扫描猜测
- `service_key` 用于映射 `inventory.services.<service_key>`
- `contracts.<target>` 给出相对 `repo_root` 的正式合同路径

第一版不做：

- 自动发现 sibling 仓库
- 模糊匹配 repo 名
- 多合同优先级推断

## Object Model

`app object` 至少暴露：

- `app`
- `target`
- `repo_name`
- `service_key`
- `contract_file`
- `inventory_entry`
- `summary_files`
- `ledger_status`

其中：

- `contract_file` 回答声明真源在哪里
- `inventory_entry` 回答当前 target 投影成了什么
- `summary_files` 回答人类摘要回写到哪里
- `ledger_status` 回答对象台账是否已刷新

## Object Action Semantics

### `search`

列出某个 `target` 下已登记的 app 对象：

- 从 `app catalog` 读取候选
- 只返回当前 target 存在 contract 映射的对象
- 聚合最小 inventory 摘要

最小返回字段：

- `app`
- `service_key`
- `contract_file`
- `control_plane`
- `public_url`

### `get`

聚合读取单个 app 对象：

- `catalog` 中的 app 声明
- 解析后的 contract 摘要
- `inventory.services.<service_key>` 投影
- 目标 summary 文件路径

`get` 回答“定义了什么、当前投影成什么”，不执行 live deploy 验证。

### `verify`

第一版最小正式对象核验：

1. `catalog` 中存在该 `target + app`
2. contract 文件存在且可通过 `validate-contract`
3. `service_key` 能正确映射到 `inventory.services`
4. `inventory` 中关键投影字段与 contract 一致
5. summary 输出路径可被稳定解析

返回：

- `ok`
- `checks`
- `failures`
- `evidence`

第一版不把 `deploy verify` 的 live 探针结果混进 `app object verify`。

### `refresh-ledger`

刷新 app 对象台账：

- `inventory/servers/<target>/ledgers/apps.json`
- `inventory/servers/<target>/ledgers/apps.md`
- `inventory.object_ledgers`
- 必要的主机摘要投影

第一版 `refresh-ledger` 只刷新对象台账，不执行合同投影回写，不代替 `inventory-refresh` 或 `doc-sync`。

## Delivery Action Semantics

`app delivery` 基本沿用当前动作集合，但收口到 `target + app` 稳定输入。

### `validate-contract`

- 通过 `catalog` 定位 contract
- 复用现有合同校验语义
- 保持 tenant 资源、secret scope、rollback entry 等现有规则不变

### `build-artifact`

- 复用现有构建语义
- 仍在 WSL 执行应用仓库声明的构建命令
- 保留现有 auto-version 逻辑

### `ship-image`

- 复用现有本地 `docker save` + SSH + 远端 `docker load` 语义

### `render-runtime`

- 复用现有 Compose 渲染语义
- 继续以 contract 为输入真源

### `deploy` / `rollback`

- 保持现有 `--dry-run` / `--execute` 语义
- 保持现有 network ensure、remote sync、切换步骤与 rollback entry 语义

### `verify`

- 保持现有交付后核验语义
- 它属于 delivery verify，不等于 object verify

### `inventory-refresh` / `doc-sync`

- 继续属于交付闭环
- 因为这两个动作依赖本次交付所引用的 contract 和 target
- 它们是 app delivery 的“投影回写动作”，不是通用 projection 域

## Repository Structure

建议目录：

```text
ops/cli/
  app.py

ops/domain/app/
  catalog.py
  object_handlers.py
  delivery_handlers.py
  ledger.py
  models.py

inventory/apps/
  catalog.json
```

原则：

- `ops/cli/app.py` 只负责 `app object` / `app delivery` 命令形状
- 原 `ops/cli/apps.py` 中的业务逻辑迁入 `ops.domain.app.delivery_handlers`
- app object 聚合逻辑进入 `ops.domain.app.object_handlers`
- catalog 解析独立到 `ops.domain.app.catalog`
- 不继续把 `app` 堆成一个超大 CLI 文件

## Testing Strategy

本轮先做测试冻结，再实施。

新增测试文件建议：

- `tests/test_app_object_cli.py`

继续保留并重构：

- `tests/test_app_cli.py`

### `app object` 需要冻结的合同

- `ops.cli --help` 中 `app` 具备 `object` / `delivery`
- `app object --help` 暴露 `search / get / verify / refresh-ledger`
- `search` 通过 `catalog` 列出 target 下受管 app
- `get` 聚合 `catalog`、contract、inventory、summary path
- `verify` 能结构化暴露 catalog 缺失、contract 缺失、inventory drift
- `refresh-ledger` 能刷新 `apps` ledger，而不篡改 contract 或 inventory 声明

### `app delivery` 需要冻结的合同

- `app delivery --help` 暴露现有交付动作
- 现有 `validate-contract / build-artifact / render-runtime / deploy / rollback / verify / inventory-refresh / doc-sync` 语义保持一致
- 公开输入改为 `--app` 后，已有核心行为仍成立
- `inventory-refresh` 继续写 `inventory.services.<service_key>`
- `doc-sync` 继续写 target-aware app summary
- 不新增 compat 入口，不保留旧 `app <action>` 单层公开面

## Migration Rule

本轮迁移原则：

1. 先新增 `catalog` 与 `app object` 失败测试
2. 再把现有 `app` 任务动作迁入 `app delivery`
3. 最后删除旧的单层公开 parser

不做：

- 旧 parser 保留一层 wrapper
- `--contract` 与 `--app` 双公开入口长期并存
- 为了减少改动继续让旧 `ops/cli/apps.py` 作为真实宿主

## Risks

### 风险 1：只换 parser，没换边界

如果只是把 `app deploy` 改成 `app delivery deploy`，但核心逻辑仍集中在旧文件里，后续 `app object` 和 `app delivery` 仍会重新耦合。

控制方式：同步拆出 `ops.domain.app`，明确 object / delivery handler。

### 风险 2：公开输入仍被 `--contract` 绑死

如果公开主入口继续依赖文件路径，`task-entry` 就不是稳定对象引用，Agent 仍要先知道外部 sibling 仓库绝对路径。

控制方式：正式入口统一改为 `target + app`，contract 路径通过 tracked catalog 解析。

### 风险 3：把 object verify 和 delivery verify 混成一个东西

这会让对象面重新承担 live deploy / health probe / 远端切换语义，边界又会回到当前混合状态。

控制方式：`app object verify` 只做声明与投影一致性；现场健康核验继续留在 `app delivery verify`。

### 风险 4：过早把 inventory/doc-sync 推进通用 projection 框架

这会把本轮从“收口 app 正式面”扩张成“重写全仓投影模型”。

控制方式：本轮只在 `app` 域内明确它们属于 delivery 闭环投影。

## Success Criteria

当以下条件同时满足时，认为 `app v1` 达成：

- `uv run python -m ops.cli app object ...` 可用
- `uv run python -m ops.cli app delivery ...` 可用
- `app object` 与 `app delivery` 边界明确，测试已冻结
- `target + app` 成为公开稳定引用
- `catalog` 能稳定解析 target 对应 contract
- 现有 Docker / Compose 交付语义保持一致
- 不进入应用业务仓库运行面
- 不进入应用层运行面
- README、architecture、skill、测试已同步到 `app v1` 口径
