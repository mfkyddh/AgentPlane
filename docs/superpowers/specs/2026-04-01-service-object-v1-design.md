# Service Object V1 Design

**Date:** 2026-04-01

## Goal

为 `OP_Linux` 增加第一版显式 `service` 对象域，统一承接基础设施与宿主服务对象的正式控制面。

本轮目标：

- 新增正式入口 `uv run python -m ops.cli service ...`
- 第一版只覆盖基础设施与宿主服务对象
- 正式支持 `search / get / verify / plan / apply`
- 允许 `wsl`、`prod0-main`、`prod2-main` 进入正式 `apply`
- 不进入应用运行服务对象

## Scope

### 本轮纳入的服务对象

- `postgres`
- `redis`
- `minio`
- `mihomo`
- `onepanel_openresty`

### 本轮明确不纳入的对象

- `newapi`
- `sub2api`
- `sub2apipay`
- `chatgpt-register-v2*`
- `onepanel website`
- `onepanel panel`
- `onepanel firewall`

## Decision

`service v1` 先只覆盖“基础设施与宿主服务对象”，不覆盖“应用运行服务对象”。

原因：

1. 基础设施与宿主服务的边界更稳定，适合先把 `service` 对象合同立起来。
2. 应用运行服务对象会同时耦合 `app`、`tenant`、`website`、交付工作流和回滚语义，直接纳入会把第一版范围做散。
3. `website` 与 `onepanel` 当前已有相对稳定的对象面；真正缺的是统一的服务对象层。

## Object Model

`service` 域用于表达“宿主机上承载的基础设施与宿主服务对象”，而不是表达：

- 宿主机本体
- 1Panel 原生页面对象
- 应用仓库交付合同

对象域边界如下：

| 域 | 管什么 | 不管什么 |
| --- | --- | --- |
| `host` | 宿主机 identity、inventory、audit、network、remote、secrets-layout | 承载在宿主机上的具体服务对象 |
| `service` | 基础设施与宿主服务对象状态、变更、验证 | 应用代码交付、网站入口、资源租户 |
| `website` | 公网入口、反代、HTTPS、域名切换 | 数据服务本体 |
| `tenant` | PostgreSQL/Redis/MinIO 等资源归属与 projection | 服务进程生命周期 |
| `app` | 交付合同、构建、部署、回滚、验证工作流 | 基础设施服务对象通用操作 |
| `onepanel` | 1Panel API 原生对象，如 panel、website、firewall、project、app | 宿主机和服务对象的统一抽象 |

## CLI Shape

正式命令面：

```bash
uv run python -m ops.cli service search --target <target>
uv run python -m ops.cli service get --target <target> --name <service>
uv run python -m ops.cli service verify --target <target> --name <service>
uv run python -m ops.cli service plan --target <target> --name <service> --operation <op>
uv run python -m ops.cli service apply --target <target> --name <service> --operation <op> --execute
```

设计原则：

- 不采用 `service postgres get` 这种二级类型子命令
- 服务类型差异沉到 registry / adapter 层
- CLI 只暴露统一对象面

## Action Semantics

### `search`

列出目标环境下受管服务对象及其类型、控制面、最小状态摘要。

返回目标：

- `target`
- `items`
- 每个 item 至少包含 `name`、`kind`、`control_plane`

### `get`

读取单个服务对象的结构化现状，聚合：

- live state
- tracked inventory 摘要
- 如有必要的控制面补充字段

### `verify`

执行服务类型相关的最小正式校验，并输出：

- `ok`
- `checks`
- `failures`
- `evidence`

第一版不允许“只有文本结论没有结构化证据”。

### `plan`

生成服务变更计划，但不执行。输出必须包含：

- `target`
- `service`
- `operation`
- `preflight`
- `steps`
- `verify_after_apply`

### `apply`

执行正式变更，必须满足：

- 明确带 `--execute`
- 先跑 preflight
- 执行变更
- 执行 post-verify
- 输出结构化结果

不允许“只返回执行命令，不返回验证结果”的伪 apply。

## Operation Matrix

`service v1` 虽然统一提供 `plan / apply` 入口，但每种服务对象实际支持的 operation 由服务类型能力矩阵决定。

第一版建议的通用 operation：

- `start`
- `stop`
- `restart`
- `reload`
- `reconcile`

矩阵原则：

- 若某服务类型当前没有足够稳定的写操作真源，就只开放 `search / get / verify / plan`
- 不允许为了“接口整齐”伪造 `apply`

## Production Apply Rule

本轮允许：

- `wsl`
- `prod0-main`
- `prod2-main`

进入正式 `apply`。

但生产环境的 `apply` 必须满足以下规则：

1. 显式 `--execute`
2. 执行前有 preflight
3. 执行后有 post-verify
4. 结果可结构化记录
5. 若对象变更影响 tracked projection，必须刷新相应 inventory / ledger / summary

## Source Of Truth Strategy

`service` 不是单一底层控制面的代理层，而是聚合多种真源：

- `live state`
- tracked `inventory`
- tracked `secrets/contracts`
- 具体控制面 API 或宿主工具

按对象类型，第一版可能使用的真源包括：

- Docker / Compose
- systemd
- 1Panel project / container / website 相关只读对象
- inventory 中的 `services`、安全与端口声明

原则：

- 先以 live state 为准
- inventory 作为受管声明与 projection
- UI 点击与 ad-hoc shell 不能成为正式真源

## Repository Structure

后续目录结构建议不是按业务线拆，而是按“对象域 + adapter”分层：

```text
ops/cli/
  host.py
  service.py
  website.py
  tenant.py
  app.py

ops/domain/
  host/
  service/
  website/
  tenant/
  app/

ops/adapters/
  docker/
  systemd/
  onepanel/
  inventory/
  ssh/

ops/projection/
```

对 `service` 的建议内部结构：

```text
ops/domain/service/
  models.py
  registry.py
  planner.py
  verifier.py
  handlers.py

ops/adapters/service/
  postgres.py
  redis.py
  minio.py
  mihomo.py
  onepanel_openresty.py
```

原则：

- CLI 层负责命令形状和输出 envelope
- 对象语义进入 domain 层
- 服务类型差异进入 adapter 层
- 不把 CLI 做成一组 `service <type> ...` 的碎片入口

## Why Not `website` First

`website` 当前已经有较完整对象面：

- `uv run python -m ops.cli onepanel --env <target> website ...`

而 `service` 仍散落在：

- `app`
- `tenant`
- `inventory`
- `secrets`
- `compose`
- 宿主服务 runbook

因此本轮优先级应是补上 `service` 对象层，而不是重复包装已有 `website` 对象面。

## Why Application Runtime Services Wait

应用运行服务对象后续会进入 `service` 域，但不在本轮进行。

后续分工建议：

- `app`：交付合同、构建、部署、回滚、工作流
- `service`：已部署运行服务对象状态与正式变更
- `website`：公网入口与站点对象
- `tenant`：资源归属与 secret projection

本轮若提前把应用运行服务并入 `service`，会把 `app` 与 `service` 的边界一起拉进来，范围过宽。

## Testing Strategy

`service v1` 需要三层测试：

1. CLI 合同
   - `ops.cli --help` 出现 `service`
   - `ops.cli service --help` 暴露 `search/get/verify/plan/apply`
   - 参数形状统一
2. 对象能力矩阵
   - 每种服务类型支持哪些 operation
   - 不支持的写操作必须明确失败
3. 文档合同
   - active 文档、skill、architecture 统一承认 `service` 域
   - 不把基础设施服务对象继续埋在 `app / tenant / onepanel` 的说明里

## Risks

### Risk 1: `service` 变成杂项回收站

如果把基础设施服务、应用运行服务、网站对象、面板对象一起塞进 `service`，对象域会失去意义。

控制方式：

- 第一版只纳入基础设施与宿主服务对象

### Risk 2: CLI 过早按类型碎片化

如果直接做成 `service postgres ...`、`service redis ...`，以后会越来越像命令集合而不是统一对象面。

控制方式：

- 顶层统一命令形状
- 类型差异放到 registry / adapter

### Risk 3: 生产 `apply` 没有强验证

如果允许生产 `apply`，但没有 preflight 和 post-verify，就只是把风险包装成正式入口。

控制方式：

- 所有生产 `apply` 必须强制验证链

## Success Criteria

当以下条件成立时，`service v1` 视为成功：

- CLI 有正式 `service` 对象域
- 第一版覆盖基础设施与宿主服务对象
- `search / get / verify / plan / apply` 语义统一
- `prod0-main / prod2-main` 的 `apply` 有明确验证链
- `website`、`tenant`、`app`、`onepanel` 边界未被打乱
