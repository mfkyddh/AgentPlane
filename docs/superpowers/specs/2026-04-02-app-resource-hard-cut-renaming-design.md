# App Resource Hard-Cut Renaming Design

**Date:** 2026-04-02

## Goal

在不保留 compat/alias/wrapper 的前提下，一次性移除 `tenant` 作为正式对象语义与内部命名宿主，把 `app resource` 变成公开入口、内部模块、tracked truth、projection、ledger、secret scope 的唯一命名体系。

本轮目标：

- 公开入口只保留 `uv run python -m ops.cli app resource ...`
- 内部模块不再以 `ops.domain.tenant` 作为真实宿主
- tracked truth、projection 字段、ledger 文件、secret 目录同步切到 `app resource` 命名
- active docs、skills、tests 不再把 `tenant` 当正式对象或正式 substrate 名称
- 不保留旧路径 fallback、双读双写、过渡映射或兼容窗口

## Scope

本轮纳入：

- CLI：`app resource search / get / verify / refresh-ledger`
- 内部模块：`ops/domain/app/resource_*`
- 声明真源：`inventory/servers/<target>/app-resources.json`
- projection 字段：`inventory.services.<app>.app_resource_summary`
- ledger：`inventory/servers/<target>/ledgers/app_resources.json|md`
- secret scope：`secrets/app-resources/<target>/<app>/`
- docs / skills / tests / inventory fixture / README 生成逻辑同步

本轮不纳入：

- 任何 compat wrapper、旧词 alias、fallback 读取
- 只改文案不改机器真源的“半迁移”
- 与 `app resource` 无关的对象域重构
- live runtime 行为扩张

## Problem

当前仓库已经把正式公开入口收口到 `app resource`，但底层仍残留：

- `app-resources.json`
- `app_resource_summary`
- `ledgers/app_resources.json`
- `secrets/app-resources/...`
- `ops.domain.tenant`

这会造成三层错位：

1. 对外叫 `app resource`
2. 对内真实宿主仍是 `tenant`
3. tracked truth 仍用 `tenant` 词汇

如果继续保留这组混合命名，后续每一轮都要解释“哪一层是正式的、哪一层只是历史遗留”，成本会持续上升。

## Decision

一步到位统一为以下命名：

| 层 | 最终命名 |
| --- | --- |
| 正式 CLI | `uv run python -m ops.cli app resource ...` |
| 内部模块 | `ops/domain/app/resource_models.py` / `resource_registry.py` / `resource_handlers.py` |
| 声明真源 | `inventory/servers/<target>/app-resources.json` |
| projection 字段 | `inventory.services.<app>.app_resource_summary` |
| ledger 文件 | `inventory/servers/<target>/ledgers/app_resources.json|md` |
| secret scope | `secrets/app-resources/<target>/<app>/` |
| 错误前缀 | `app.resource.*` / `prod0.app_resource.*` |

硬约束：

1. 不保留 `tenant` 顶层公开入口作为正式合同。
2. 不保留旧文件名和旧字段名 fallback。
3. 不保留 `ops.domain.tenant` 作为 compat 宿主。
4. 不在同轮同时扩张新行为，只做命名和边界硬切。

## Naming Contract

正式对象及其 substrate 统一采用以下名称：

```text
app resource object
app-resources.json
app_resource_summary
ledgers/app_resources.json
secrets/app-resources/<target>/<app>/
```

保留说明：

- `app resource` 用于对象语义与错误前缀
- `app-resources.json` 用于 tracked truth 文件
- `app_resource_summary` 用于 JSON 字段名
- `app_resources` 用于 ledger 文件名，避免路径中混用 `-` 与 `.`

## Source Of Truth

迁移完成后的正式链路：

- declaration: `inventory/servers/<target>/app-resources.json`
- secret scope: `secrets/app-resources/<target>/<app>/*.env`
- projection: `inventory/servers/<target>/inventory.json -> services.<app>.app_resource_summary`
- ledger projection: `inventory/servers/<target>/ledgers/app_resources.json|md`

禁止保留：

- `app-resources.json`
- `app_resource_summary`
- `ledgers/app_resources.json|md`
- `secrets/app-resources/...`

## Implementation Shape

目标代码结构：

```text
ops/domain/app/
  resource_models.py
  resource_registry.py
  resource_handlers.py

ops/cli/
  apps.py
  audit.py

ops/domain/projection/
  runtime_env.py

ops/scripts/onepanel/
  ledger.py
```

处理原则：

1. `app resource` 相关读取、写回、校验全部直接依赖新路径和新字段。
2. 删除 `ops/domain/tenant/`，不保留 compat wrapper。
3. `tenant validate / audit / audit-live` 若仍存在，则必须一起退出正式代码路径；不允许它们继续依赖旧真源继续“半活着”。
4. `projection runtime-env`、`prod0 audit`、README 生成逻辑、inventory 写回逻辑同轮改完。

## Migration Strategy

一步到位迁移顺序：

1. 先冻结最终合同测试  
   目标：先锁定 `app-resources.json`、`app_resource_summary`、`app.resource.*` 的最终结果。

2. 再切代码读写面  
   目标：CLI、handlers、projection、audit、ledger 统一读写新路径，不读旧路径。

3. 同轮改 tracked truth 与 fixture  
   目标：仓库内 inventory fixture、README 生成输入、测试样例全部切到新命名。

4. 最后删除旧入口与旧模块  
   目标：防止代码里留下“旧名仍能跑”的假象。

## Testing Strategy

最小必要验证应覆盖：

- `tests/test_app_resource_cli.py`
  - `app resource` 仍能 `search / get / verify / refresh-ledger`
- `tests/test_app_cli.py`
  - 合同校验错误码统一为 `app.resource.*`
- `tests/test_prod0_audit.py`
  - 审计错误码与读取路径统一为 `prod0.app_resource.*`
- `tests/test_projection_runtime_env_cli.py`
  - runtime env projection 使用新的 app resource registry 语义
- docs / skills 测试
  - active docs、skill 示例、README 不再出现正式 `tenant` 语义
- 旧词清扫检查
  - active surface 不再出现 `app-resources.json`、`app_resource_summary`、`secrets/app-resources/`

## Risks

### 风险 1：一次改动面过大

因为这不是单纯命令面收口，而是数据面与路径面迁移，同轮涉及 CLI、projection、inventory、docs、tests。

控制方式：严格限制范围在 `app resource` 全链路，不扩展到其他对象域。

### 风险 2：历史脚本或生成逻辑漏改

如果 `ledger.py`、README 生成逻辑或某些 fixture 仍写旧名，会产生“测试绿但 tracked 文件继续回写旧名”的假完成。

控制方式：必须加入基于 `rg` 的旧词清扫检查，并对 README / ledger / inventory 写回做验证。

### 风险 3：tracked truth 迁移导致大面积 diff

一旦改文件名和字段名，仓库中的 inventory fixture、说明文档、断言都会一起变化。

控制方式：接受这是一次数据面迁移，不把“大 diff”当异常；用测试锁住结果，而不是压缩范围成半迁移。

## Success Criteria

当以下条件同时满足时，认为本轮达成：

- `tenant` 不再是正式对象入口、正式内部宿主或正式 tracked truth 名称
- `ops/domain/tenant/` 已删除
- `app-resources.json` 成为唯一声明真源
- `app_resource_summary` 成为唯一 projection 字段
- `ledgers/app_resources.json|md` 成为唯一 ledger 文件
- `secrets/app-resources/...` 成为唯一正式 secret scope
- active docs / skills / tests 不再把 `tenant` 当正式对象或正式 substrate
- 最小相关测试通过

