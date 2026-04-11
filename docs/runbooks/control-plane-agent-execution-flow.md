# Control Plane Agent Execution Flow

## 目的

本文定义 Agent 在 `AgentPlane` 仓库中的正式执行顺序，确保正式命令面、验证、ledger 回写与文档对齐形成稳定流程。

## 适用范围

- 主机治理
- 1Panel provider/debug 对象核对
- 运行服务操作
- 公网入口发布
- 应用交付
- 租户验证
- projection 验证 / fixture / ledger 刷新

## Automation / Projection 职责真源

`automation` 与 `projection` 的职责边界只在 [automation-stack.md](../architecture/automation-stack.md) 定义。
本文只描述执行顺序中的调用点，不重复定义职责所有权。

## 正式入口

所有正式操作都从 `uv run python -m agentplane.cli ...` 进入。`onepanel` 公开面只剩 `panel`、`firewall`、`cronjob`、`task`。`service` 只面向 inventory 中已声明的 tracked runtime service，不接受 raw 1Panel install id / project id / container id。`website` 当前默认入口已经开放到 `uv run python -m agentplane.cli website ...`；`website publish` 是 Cloudflare + 1Panel 公网入口的正式任务入口，不公开 raw onepanel / cloudflare 参数。运行服务、公网入口发布、fixture、verification、ledger 已分别归入 `service`、`website`、`projection`。

## 标准执行顺序

### 1. 前置检查

1. 确认当前在 WSL 环境执行。
2. 确认 `whoami`、`$HOME`、仓库根目录。
3. 确认目标 `target` 或 `env`。
4. 明确这是只读动作还是写动作。

### 2. 命令发现

优先顺序：

1. `uv run python -m agentplane.cli --help`
2. 对应 domain/object 的 `--help`
3. 对应 architecture / runbook

### 3. 计划阶段

对副作用动作，优先运行计划或 dry-run：

```bash
uv run python -m agentplane.cli service plan --target prod0-main --name newapi --operation reconcile --repo-root /root/work/AgentPlane
uv run python -m agentplane.cli website publish plan --target prod0-main --config-file /root/work/AgentPlane/secrets/services/token-public-ingress.env --cloudflare-env-file /root/work/AgentPlane/secrets/env/prod-jump.env --repo-root /root/work/AgentPlane
uv run python -m agentplane.cli app delivery deploy --target prod0-main --app sub2api --repo-root /root/work/AgentPlane --dry-run
```

### 4. 执行阶段

只有在前置检查与计划阶段通过后，才进入正式执行：

```bash
uv run python -m agentplane.cli service apply --target prod0-main --name newapi --operation reconcile --repo-root /root/work/AgentPlane --execute
uv run python -m agentplane.cli website publish apply --target prod0-main --config-file /root/work/AgentPlane/secrets/services/token-public-ingress.env --cloudflare-env-file /root/work/AgentPlane/secrets/env/prod-jump.env --repo-root /root/work/AgentPlane --execute
uv run python -m agentplane.cli app delivery deploy --target prod0-main --app sub2api --repo-root /root/work/AgentPlane --execute
```

### 5. 验证阶段

执行后必须验证 `live state`：

```bash
uv run python -m agentplane.cli service verify --target prod0-main --name newapi --repo-root /root/work/AgentPlane
uv run python -m agentplane.cli website publish verify --target prod0-main --config-file /root/work/AgentPlane/secrets/services/token-public-ingress.env --cloudflare-env-file /root/work/AgentPlane/secrets/env/prod-jump.env --repo-root /root/work/AgentPlane
uv run python -m agentplane.cli app delivery verify --target prod0-main --app sub2api --repo-root /root/work/AgentPlane --execute
uv run python -m agentplane.cli projection verification run --target prod0-main --profile prod0-readonly --repo-root /root/work/AgentPlane
```

### 6. Ledger / Inventory 回写

当动作影响正式状态或正式摘要时，继续回写。职责归属与边界解释统一见 [automation-stack.md](../architecture/automation-stack.md)：

```bash
uv run python -m agentplane.cli projection ledger refresh --target prod0-main --repo-root /root/work/AgentPlane --write
uv run python -m agentplane.cli app delivery inventory-refresh --target prod0-main --app sub2api --repo-root /root/work/AgentPlane --write
uv run python -m agentplane.cli app delivery doc-sync --target prod0-main --app sub2api --repo-root /root/work/AgentPlane --write
```

## 人工接力点

以下场景应暂停自动执行并转人工确认：

- 高风险正式切换
- 证书、域名、入口变更
- 数据迁移或回滚
- 计划输出与现场认知明显不一致
- 验证结果与预期冲突
- 需要跳出 formal domain 直接触碰 provider/debug 原生对象

## 结果记录要求

Agent 在结束时应至少明确：

- 执行了什么正式命令
- 哪些验证通过或失败
- 是否刷新了 `ledger`
- 是否需要补充人工 follow-up

## 禁止事项

1. 不要跳过计划阶段直接进入写操作。
2. 不要把文档说明当成现场验证结果。
3. 不要执行后不做验证。
4. 不要刷新 `ledger` 但不核对其内容是否与现场一致。

## 关联文档

- [control-plane.md](../architecture/control-plane.md#principles)
- [control-plane.md](../architecture/control-plane.md#cli-contract)
- [onepanel-cli-validation-workflow.md](onepanel-cli-validation-workflow.md)
- [app-project-delivery-workflow.md](app-project-delivery-workflow.md)
- [automation-stack.md](../architecture/automation-stack.md)
