# Website Object V1 Design

**Date:** 2026-04-02

## Goal

为 `OP_Linux` 增加正式 `website` 对象域，形成 `uv run python -m ops.cli website ...` 入口，统一表达公网入口对象，不进入应用运行面。

## Scope

本轮纳入：

- 正式入口 `uv run python -m ops.cli website ...`
- 动作 `search / get / verify / plan / apply / refresh-ledger`
- 稳定引用 `target + alias`
- 声明真源 `inventory.services.public_websites`
- live state 聚合 `1Panel website detail + https detail`

本轮不纳入：

- `newapi / sub2api / sub2apipay / chatgpt-register-v2*` 应用运行面
- Cloudflare DNS 管理
- ACME 账号与证书签发工作流
- `panel / firewall` 对象迁移
- 1Panel website update / delete / operate 的广义写面

## Boundary

| 域 | 管什么 | 不管什么 |
| --- | --- | --- |
| `website` | 公网入口、反代、HTTPS、域名切换 | 数据服务本体 |
| `onepanel` | 1Panel API 原生对象，如 panel、website、firewall、project、app | 宿主机和服务对象的统一抽象 |
| `service` | 反代目标服务本体 | 公网入口对象 |
| `app` | 合同里声明入口需求 | 现场网站对象的正式操作 |

## Decision

`website v1` 不把现有 `onepanel website` 重命名一层，而是建立正式对象域：

1. 对外稳定引用使用 `alias`，不使用 1Panel `id`。
2. declaration 从 tracked `inventory.services.public_websites` 读取。
3. live state 通过 1Panel substrate 聚合。
4. `plan/apply` 第一版只开放 `reconcile`，且执行面只支持 create/noop；若发现 drift，仅结构化暴露，不伪造写能力。

## CLI Shape

```bash
uv run python -m ops.cli website search --target <target>
uv run python -m ops.cli website get --target <target> --alias <alias>
uv run python -m ops.cli website verify --target <target> --alias <alias>
uv run python -m ops.cli website plan --target <target> --alias <alias> --operation reconcile
uv run python -m ops.cli website apply --target <target> --alias <alias> --operation reconcile --execute
uv run python -m ops.cli website refresh-ledger --target <target> --repo-root /root/work/OP_Linux --write
```

## Source Of Truth

- declaration：`inventory/servers/<target>/inventory.json -> services.public_websites`
- live state：`1Panel website search/detail/https`
- projection：`inventory/servers/<target>/ledgers/websites.json|md` 与 `inventory.object_ledgers`

## Reconcile Rule

- 若对象缺失：允许 create + post-verify
- 若对象已匹配声明：返回 noop + post-verify
- 若对象存在 drift：返回结构化 drift，不进入伪执行
