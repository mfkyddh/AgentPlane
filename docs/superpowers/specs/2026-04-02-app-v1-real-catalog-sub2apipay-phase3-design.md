# App V1 Real Catalog Sub2ApiPay Phase 3 Design

**Date:** 2026-04-02

## Goal

把 `sub2apipay` 纳入第三个真实 `app` catalog entry，并只为 `prod0-main` 补齐其在 `app object` 与 tracked `apps` object ledger 中的正式登记。

本轮继续保持 `app v1` 既有边界：

- 不进入应用运行面
- 不进入应用仓库运行面
- 不新增 compat / alias / wrapper / 隐式扫描
- 不扩 `app object` / `app delivery` 公开字段

## Why Now

当前 `sub2api`、`newapi` 已进入真实 tracked catalog，`app object` 与 `app delivery validate-contract` 都已经切到 `inventory/apps/catalog.json` 做正式解析。

`sub2apipay` 现阶段也满足进入真实 catalog 的最小条件：

- 目标应用仓库根固定为 `/root/work/sub2apipay`
- 正式合同固定为 `/root/work/sub2apipay/deploy/op/contract.yaml`
- `prod0-main` 已存在稳定的 inventory 投影与公网入口
- 本轮只需要补 tracked catalog 与 prod0 `apps` ledger，不需要扩展行为层

因此这轮适合继续沿用 `app v1` 的 data-only 收口方式，把 `sub2apipay` 纳入第三条真实 tracked entry。

## Scope

本轮纳入：

- 在 `inventory/apps/catalog.json` 中登记 `sub2apipay`
- `sub2apipay` 只登记 `prod0-main`
- `app object search / get` 通过 tracked catalog 解析 `sub2apipay`
- `app delivery validate-contract` 通过 tracked catalog 解析 `sub2apipay`
- `inventory/servers/prod0-main/ledgers/apps.json|md` 纳入 `sub2apipay`
- 对应测试冻结与最小文档同步

本轮不纳入：

- `prod2-main` target 的真实 catalog entry
- `wsl` target 的真实 catalog entry
- 应用仓库代码、模板、构建脚本或运行时文件改造
- live deploy / verify / cutover
- 新的 `catalog` 字段、`app object` 字段或兼容解析路径

## Decision

`sub2apipay` 作为第三个真实 entry 纳入 tracked catalog，精确形状为：

```json
{
  "app": "sub2apipay",
  "repo_name": "sub2apipay",
  "repo_root": "/root/work/sub2apipay",
  "service_key": "sub2apipay",
  "contracts": {
    "prod0-main": "deploy/op/contract.yaml"
  }
}
```

这条 entry 只表达两类稳定信息：

1. `prod0-main + sub2apipay` 的正式合同寻址
2. `inventory.services.sub2apipay` 的投影映射键

它不承载 runtime 投影本身，也不为其他 target 提供默认映射。

## Object Boundary Freeze

`catalog` 继续只承担稳定寻址，不承载以下字段：

- `public_url`
- `control_plane`
- `app_resource_summary`
- `rollback_entry`
- `config_files`
- `runtime_root`

这些字段继续只留在 contract 或 target inventory 投影里。

同时冻结以下排除项：

- 不把 `prod2-main` 自动补成第二个 target
- 不把 `wsl` 混入“真实 onboarding 完成”口径
- 不做 sibling repo 扫描或 repo alias
- 不把 `inventory.services.*` 的 runtime 字段回写到 catalog

## Ledger Decision

`apps` object ledger 继续表达“当前 tracked app object 集合”，因此在 `catalog` 纳入 `sub2apipay` 后：

- `prod0-main` `apps` ledger 必须包含 `sub2api`、`newapi`、`sub2apipay`
- `prod2-main` `apps` ledger 继续保持 `sub2api`、`newapi`
- `wsl` `apps` ledger 继续保持当前真实 tracked 范围，不因本轮变化新增 `sub2apipay`

本轮只更新 `prod0-main` `apps` object ledger，不扩展其他 object ledger。

## Tests-First Freeze

先补并跑失败测试，冻结：

1. tracked `catalog.json` 精确包含 `sub2api`、`newapi`、`sub2apipay`
2. `sub2apipay` 只映射 `prod0-main`
3. `app object search/get` 能在 `prod0-main` 解析 `sub2apipay`
4. `prod2-main` 与 `wsl` 的 search 结果继续不出现 `sub2apipay`
5. `app delivery validate-contract --target prod0-main --app sub2apipay` 成功
6. `prod0-main` 的 tracked `apps` ledger 已纳入 `sub2apipay`

## Success Criteria

- `inventory/apps/catalog.json` 正式包含 `sub2apipay`
- `uv run python -m ops.cli app object get --target prod0-main --app sub2apipay` 成功
- `uv run python -m ops.cli app object search --target prod2-main` 结果不出现 `sub2apipay`
- `uv run python -m ops.cli app object search --target wsl` 结果不出现 `sub2apipay`
- `uv run python -m ops.cli app delivery validate-contract --target prod0-main --app sub2apipay` 成功
- `inventory/servers/prod0-main/ledgers/apps.json|md` 反映 `sub2apipay`
