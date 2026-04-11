# App V1 Real Catalog Aftercare Design

**Date:** 2026-04-02

## Goal

把 `inventory/apps/catalog.json` 从空样本推进到第一批真实 app 登记，并保持 `app v1` 已定义的对象边界不被 runtime 投影反向污染。

## Scope

本轮只做：

- 为 `sub2api` 落地首条真实 catalog entry
- 在同一条 entry 中登记 `prod0-main` 和 `prod2-main`
- 用测试冻结首批真实 catalog 的对象边界和 target 范围

本轮不做：

- 不为缺失真实应用仓库的对象补 catalog entry
- 不把 `inventory.services.*` 的 runtime 字段写回 catalog
- 不扩 `app object` / `app delivery` 公开字段
- 不进入应用仓库运行面或执行应用层 cutover

## Decision

首批真实 catalog 只纳入 `sub2api`：

- `repo_root` 真实存在：`/root/work/sub2api`
- `prod0-main` 合同存在：`deploy/op/contract.yaml`
- `prod2-main` 合同存在：`deploy/op/contract.prod2.yaml`
- 两个 target 的 `inventory.services.sub2api` 都已有正式投影

本轮不纳入：

- `newapi`：虽然 `inventory` 已有投影，但当前 `/root/work/newapi` 不存在，暂不满足 `repo_root` 真实存在的 catalog 要求
- `sub2apipay`：当前没有应用仓库合同真源接入 `app v1` catalog
- `wsl`：首批真实登记聚焦生产 target，不把本地开发 target 混入“真实 onboarding 完成”口径

## Object Boundary Freeze

`catalog` entry 继续只承担稳定寻址，不承载 runtime 投影：

```json
{
  "app": "sub2api",
  "repo_name": "sub2api",
  "repo_root": "/root/work/sub2api",
  "service_key": "sub2api",
  "contracts": {
    "prod0-main": "deploy/op/contract.yaml",
    "prod2-main": "deploy/op/contract.prod2.yaml"
  }
}
```

约束：

- `public_url`、`control_plane`、`app_resource_summary`、`rollback_entry` 继续只留在 contract 或 `inventory` 投影
- 不做 sibling 扫描或 repo 名模糊匹配
- 缺少真实 `repo_root` 的对象，即使 `inventory` 已有投影，也不能先入 catalog

## Tests-First Freeze

先补并跑失败测试，冻结：

1. tracked `catalog.json` 的首批真实样式只包含 `sub2api`
2. `sub2api` 只映射 `prod0-main` 和 `prod2-main`
3. `prod0-main` 与 `prod2-main` 的 `app object search/get` 都能解析到真实合同
4. `wsl` 首批结果保持空

## Verification

最小验证只包括：

- 相关 pytest
- `uv run python -m ops.cli app object search/get`
- `uv run python -m ops.cli app delivery validate-contract --target prod0-main --app sub2api`
- `uv run python -m ops.cli app delivery validate-contract --target prod2-main --app sub2api`
