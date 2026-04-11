# Archive Docs

结论：docs/archive/ 只承接退出主流程的旧专题、历史架构快照和 archived runbook；这里不是当前控制面的默认入口。

## Architecture Snapshots

- [1panel-v2.1.5-project.md](../archive/architecture/1panel-v2.1.5-project.md): 已退出主线的信息架构快照，保留给历史对照。

## Archived Runbooks

- [prod0-main-8443-openresty-cutover.md](../archive/runbooks/prod0-main-8443-openresty-cutover.md): 历史切换窗口记录。
- [prod0-main-sub2-control-plane-convergence.md](../archive/runbooks/prod0-main-sub2-control-plane-convergence.md): sub2apipay 历史收敛记录。
- [prod0-postgres-app-resource-ops.md](../archive/runbooks/prod0-postgres-app-resource-ops.md): 已退出 active 主流程的旧 app resource 运维专题。

## Boundary

- 当前正式入口仍是 uv run python -m agentplane.cli ... 与 active runbook。
- archive 资产可以被引用，但不得重新回到仓库根主导航里的 active 操作路径。
- 如果某份材料重新进入当前流程，应迁回 docs/runbooks/、docs/reference/ 或 docs/architecture/，而不是继续在 archive 内增量维护。
