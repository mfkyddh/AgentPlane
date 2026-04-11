# Projection Runtime Env V1 Design

**Date:** 2026-04-02

## Goal

为 `OP_Linux` 收敛第一版正式 `projection runtime-env` 任务面，把 app runtime env projection 从 `tenant` 正式对象面彻底分层出去。

本轮目标：

- 新增正式入口 `uv run python -m ops.cli projection runtime-env ...`
- 把现有 app runtime env projection 语义从 `tenant render-env` 迁出
- 保持现有 runtime env merge 语义不变，只做边界重组
- 不进入 `newapi / sub2api / sub2apipay / chatgpt-register-v2*` 应用运行面
- 不进入 live deploy / app process / remote host apply 流程

## Scope

本轮纳入：

- `projection runtime-env plan --target <target> --app <app>`
- `projection runtime-env apply --target <target> --app <app>`
- `projection runtime-env verify --target <target> --app <app>`
- 新增 `ops.cli.projection`
- 新增 runtime env projection 任务层 / 领域层
- 把现有 `tenant render-env` 的既有 merge 语义迁移到新入口
- 同步 `README`、architecture、skill、CLI help、测试

本轮不纳入：

- `tenant audit-live` 迁出或语义重写
- `tenant validate / audit` 重构
- 应用合同、应用 compose、应用模板改造
- 远端 host 同步、应用部署、live service 校验
- `ledger / inventory / summary / skills / plugins / automation` 的通用 projection 总框架

## Boundary

| 域 | 管什么 | 不管什么 |
| --- | --- | --- |
| `tenant` | 资源租户声明真源、secret scope、`app_resource_summary` projection 一致性 | app runtime env 文件生成 |
| `projection runtime-env` | 从已声明 tenant truth 派生 app runtime env 文件，并核验当前文件是否与预期一致 | 租户分配真源、基础设施 live 写面、应用部署 |
| `app` | 应用合同、非敏感模板、交付说明 | 租户 secret truth 与 runtime env projection 实现 |

## Decision

`projection runtime-env v1` 采用“任务面收口、语义不扩张”的方式：

1. 正式入口采用 `projection runtime-env plan|apply|verify`。
2. `tenant` 继续只管资源租户对象，不再承载 runtime env generation。
3. 第一版沿用现有 `tenant render-env` 的 app-specific merge 语义，不在本轮重新设计 `newapi / sub2api / sub2apipay` 的 runtime key 规则。
4. `plan` 只计算 projection，不写文件。
5. `apply` 写 `secrets/services/<app>.<target-scope>.env`。
6. `verify` 只比较 tracked/local 文件与预期 projection，不扩张到 live host 或应用进程。
7. 本轮不保留 `tenant render-env` compat / alias / wrapper。

## CLI Shape

正式入口：

```bash
uv run python -m ops.cli projection runtime-env plan --target <target> --app <app> --repo-root /root/work/OP_Linux
uv run python -m ops.cli projection runtime-env apply --target <target> --app <app> --repo-root /root/work/OP_Linux
uv run python -m ops.cli projection runtime-env verify --target <target> --app <app> --repo-root /root/work/OP_Linux
```

退出正式对象面的历史入口：

```bash
uv run python -m ops.cli projection runtime-env apply ...
```

## Source Of Truth

- tenant declaration: `inventory/servers/<target>/app-resources.json`
- tenant secret scope: `secrets/app-resources/<target>/<app>/*.env`
- output file: `secrets/services/<app>.<target-scope>.env`
- current file preservation input: 现有 output file 中的非托管键

## Task Model

`projection runtime-env` 不是稳定对象 CRUD，而是围绕“派生一个运行时 env 文件”组织的任务面。

稳定输入：

- `target`
- `app`

稳定输出：

- `env_file`
- `managed_keys`
- `rendered_env`
- `changed`
- `ok`

## Action Semantics

### `plan`

- 读取 tenant registry 与 tenant secret files
- 读取当前 env 文件，用于保留非托管键顺序与 app-only keys
- 计算预期 projection
- 不写磁盘

### `apply`

- 先执行与 `plan` 相同的 projection 计算
- 通过后写回目标 env 文件
- 只写本地 tracked secret output，不触发 host sync

### `verify`

- 计算预期 projection
- 若目标 env 文件不存在，返回结构化失败
- 若当前文件内容与预期不一致，返回结构化 drift
- 不把 drift 自动修复成写操作

## Repository Structure

建议目录：

```text
ops/cli/
  projection.py

ops/domain/projection/
  runtime_env.py
```

原则：

- `tenant.py` 只保留 tenant truth / audit 相关动作
- runtime env projection 逻辑不再继续堆在 `tenant.py`
- 尽量复用现有 helper，而不是重写 app-specific merge 细节

## Testing Strategy

新增或重组测试，冻结以下合同：

- `ops.cli --help` 出现 `projection`
- `projection runtime-env --help` 暴露 `plan / apply / verify`
- `tenant --help` 不再暴露 `render-env`
- 旧 `render-env` 语义迁移后，现有 runtime env projection 行为保持一致
- `verify` 能结构化暴露 missing file / drift
- `apply` 仍保持“托管键更新，app-only keys 保留”的现有语义

## Risks

### 风险 1：只换入口名，没有换边界

如果只是保留 `tenant.py` 内原实现，再额外加一层转发，`tenant` 仍然是 runtime projection 的真实宿主，边界没有真正收口。

控制方式：把 runtime env projection 核心逻辑迁到独立模块，`tenant.py` 不再保留 `render-env` parser 与 handler。

### 风险 2：迁移时顺手改了应用运行语义

当前 `newapi / sub2api / sub2apipay` 的 env merge 规则已经被测试冻结；本轮若顺手“优化”，会把边界重组变成运行行为变更。

控制方式：先迁测试，再原样搬运实现，只允许做最小重构。

### 风险 3：把 projection v1 做成过大的通用框架

若同时把 inventory / ledger / summary / automation 都并入，会把本轮切口放大，重新失焦。

控制方式：第一版只做 `runtime-env` 一个 surface。

## Success Criteria

当以下条件同时满足时，认为 `projection runtime-env v1` 达成：

- `uv run python -m ops.cli projection runtime-env plan|apply|verify ...` 可用
- `tenant --help` 不再暴露 `render-env`
- 既有 runtime env projection 语义迁移后保持一致
- `tenant` 正式对象面不再承担 app runtime env projection
- README、architecture、skill、测试已同步到 `projection runtime-env v1` 口径
