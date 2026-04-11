# App V1 Real Catalog NewAPI Phase 2 Design

**Date:** 2026-04-02

## Goal

把 `newapi` 纳入第二个真实 `app` catalog entry，并补齐其在 `app object` 与 `apps` object ledger 中的正式登记。

本轮继续保持 `app v1` 既有边界：

- 不进入应用层运行面
- 不进入应用业务仓库运行面
- 不新增 compat / alias / wrapper / 隐式扫描
- 不扩 `app object` / `app delivery` 公开字段

## Why Now

上一轮把 `newapi` 排除在真实 catalog 之外，理由是“`/root/work/newapi` 不存在”。当前核对结果表明：

- 真正存在的应用仓库根是 `/root/work/new-api`
- `deploy/op/contract.yaml` 与 `deploy/op/contract.prod2.yaml` 都真实存在
- `docs/OP_LINUX_DEPLOYMENT.md` 与 `docs/OP_LINUX_DEPLOYMENT.prod2-main.md` 都真实存在
- 现有 `validate-contract` 已能直接通过这两份合同
- `inventory.services.newapi` 已在 `prod0-main` 与 `prod2-main` 正式投影

因此 `newapi` 已满足“catalog 只做稳定寻址”的第二阶段准入条件。

## Scope

本轮纳入：

- 在 `inventory/apps/catalog.json` 中登记 `newapi`
- `newapi` 只登记 `prod0-main` 与 `prod2-main`
- `app object search / get` 通过 tracked catalog 解析 `newapi`
- `app delivery validate-contract` 通过 tracked catalog 解析 `newapi`
- `inventory/servers/prod0-main/ledgers/apps.json|md` 纳入 `newapi`
- `inventory/servers/prod2-main/ledgers/apps.json|md` 纳入 `newapi`
- 对应测试冻结与最小文档同步

本轮不纳入：

- `wsl` target 的真实 catalog entry
- 应用仓库代码、模板、构建脚本或运行时文件改造
- live deploy / verify / cutover
- `catalog` 自动校验 `repo_root` 存在性的泛化机制
- 新的 `app object` 字段或新的 `catalog` 字段

## Decision

`newapi` 作为第二个真实 entry 纳入 catalog，精确形状为：

```json
{
  "app": "newapi",
  "repo_name": "new-api",
  "repo_root": "/root/work/new-api",
  "service_key": "newapi",
  "contracts": {
    "prod0-main": "deploy/op/contract.yaml",
    "prod2-main": "deploy/op/contract.prod2.yaml"
  }
}
```

与首条 `sub2api` entry 并列后，tracked catalog 只表达两类信息：

1. `target + app` 的稳定寻址
2. `inventory.services.<service_key>` 的投影映射键

它仍然不承载 runtime 投影本身。

## Object Boundary Freeze

`catalog` 继续只承担稳定寻址，不承载以下字段：

- `public_url`
- `control_plane`
- `app_resource_summary`
- `rollback_entry`
- `config_files`
- `runtime_root`

这些字段继续只留在 contract 或 target inventory 投影中。

同时明确冻结以下排除项：

- 不把 `/root/work/newapi` 作为别名或兼容路径
- 不做 sibling repo 扫描
- 不做 `repo_name` 模糊匹配
- 不把 `wsl` 混入“真实 onboarding 完成”口径

## Ledger Decision

`apps` object ledger 应反映“当前 tracked app object 集合”，因此在 `catalog` 纳入 `newapi` 后：

- `prod0-main` `apps` ledger 必须包含 `sub2api`、`newapi`
- `prod2-main` `apps` ledger 必须包含 `sub2api`、`newapi`
- `wsl` `apps` ledger 继续保持当前真实 tracked 范围，不因本轮变化新增 `newapi`

本轮只更新 `apps` object ledger，不扩展其他 object ledger。

## Tests-First Freeze

先补并跑失败测试，冻结：

1. tracked `catalog.json` 精确包含 `sub2api` 和 `newapi`
2. `newapi` 只映射 `prod0-main` 与 `prod2-main`
3. `app object search/get` 能在 `prod0-main` 与 `prod2-main` 解析 `newapi`
4. `newapi` 的 `summary_files` 指向真实摘要文件
5. `app delivery validate-contract --target prod0-main/prod2-main --app newapi` 成功
6. `prod0-main` 与 `prod2-main` 的 tracked `apps` ledger 都已纳入 `newapi`
7. `wsl` search 结果继续不出现 `newapi`

## Success Criteria

- `inventory/apps/catalog.json` 正式包含 `newapi`
- `uv run python -m ops.cli app object get --target prod0-main --app newapi` 成功
- `uv run python -m ops.cli app object get --target prod2-main --app newapi` 成功
- `uv run python -m ops.cli app delivery validate-contract --target prod0-main --app newapi` 成功
- `uv run python -m ops.cli app delivery validate-contract --target prod2-main --app newapi` 成功
- `inventory/servers/prod0-main/ledgers/apps.json|md` 和 `inventory/servers/prod2-main/ledgers/apps.json|md` 都反映 `newapi`
