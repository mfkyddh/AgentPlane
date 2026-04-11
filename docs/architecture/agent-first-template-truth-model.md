# Agent-First Template Truth Model

## Scope

`AgentPlane` 的模板仓库真源只允许保存稳定、可迁移、可 fork 的逻辑引用，不允许把当前宿主机的访问路径回写进 tracked truth。

## Canonical Truth

- `truth` 只保存 canonical ref，例如 `apps/sub2api/contracts/prod0-main`。
- `truth` 不保存 Windows 盘符路径、WSL UNC 路径、`/root/...`、`/mnt/...` 这类宿主相关路径。
- App catalog 的正式对象标识由 `app`、`service_key`、`repo_ref`、target-specific `contracts` 组成。

## Runtime Resolution

- runtime 可以把 canonical ref 解析成当前宿主可访问的 `resolved_path`。
- `resolved_path` 是运行时观察值，不是 tracked truth。
- `app object` 这类 formal surface 可以同时输出 `canonical_ref` 和 `resolved_path`，用于区分逻辑真源与当前宿主视角。

## Projection Boundaries

- `ledger` 可以保存稳定、可消费的摘要字段，但不写宿主访问路径。
- `verification` 才允许出现宿主观察值，包括 `resolved_path`、现场探测值和其它运行期证据。
- resolver/backend 层以后可以替换，但 truth contract 不变。
