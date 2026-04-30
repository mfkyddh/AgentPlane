# Archive Docs

结论：docs/archive/ 只承接退出主流程的旧专题、历史架构快照和 archived runbook；这里不是当前控制面的默认入口。

## Architecture Snapshots

- [1panel-v2.1.5-project.md](architecture/1panel-v2.1.5-project.md): 已退出主线的信息架构快照，保留给历史对照。

## Archived Runbooks

- [control-plane-legacy-migration.md](runbooks/control-plane-legacy-migration.md): 旧脚本收敛策略。
- [onepanel-app-lifecycle.md](runbooks/onepanel-app-lifecycle.md): 1Panel 应用生命周期旧流程。
- [onepanel-cli-validation-workflow.md](runbooks/onepanel-cli-validation-workflow.md): 1Panel CLI 验证旧流程，已由通用 app delivery workflow 替代。
- [prod0-main-8443-openresty-cutover.md](runbooks/prod0-main-8443-openresty-cutover.md): 历史切换窗口记录。
- [prod0-main-sub2-control-plane-convergence.md](runbooks/prod0-main-sub2-control-plane-convergence.md): sub2apipay 历史收敛记录。
- [prod0-postgres-app-resource-ops.md](runbooks/prod0-postgres-app-resource-ops.md): 已退出 active 主流程的旧 app resource 运维专题。

## Archived Project Docs

- [communication.md](project/communication.md): 单人项目的沟通机制模板，当前阶段不需要。
- [risk-management.md](project/risk-management.md): 风险管理框架模板，当前阶段未使用。
- [roles.md](project/roles.md): 角色与职责模板，当前阶段为单人维护。

## Archived Maintainer Docs

- [layer-health-report.md](maintainers/layer-health-report.md): 四层体系健康度报告框架，当前阶段未使用。

## Boundary

- 当前正式入口仍是 agentplane ... 与 active runbook。
- archive 资产可以被引用，但不得重新回到仓库根主导航里的 active 操作路径。
- 如果某份材料重新进入当前流程，应迁回 docs/runbooks/、docs/reference/ 或 docs/architecture/，而不是继续在 archive 内增量维护。
