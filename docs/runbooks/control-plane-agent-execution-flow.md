# Control Plane Agent Execution Flow

## 目的

本文定义 Agent 在 Agent-first 控制面模板仓库中的正式执行顺序，确保正式命令面、验证、ledger 回写与文档对齐形成稳定闭环。

## 适用范围

- 主机治理
- provider/debug 对象核对
- 运行服务操作
- 公网入口发布
- 应用交付
- 应用资源与 projection 验证

## 真源与平台分工

- 真源模型固定为 `Git tracked truth + local secrets`。
- 人类输入面只剩 `secrets` 和少量 `identity`。
- Windows / Linux / macOS 只在 `resolver / backend` 层分叉。
- 正式闭环固定为 `plan -> apply -> verify -> ledger -> inventory -> doc-sync`。

## 正式入口

- 所有正式操作都从 `uv run python -m agentplane.cli ...` 进入。
- Windows 主机以 `pwsh` 为入口；Linux / macOS 继续使用原生 shell。
- `onepanel` 公开面只剩 `panel`、`firewall`、`cronjob`、`task`。
- `service`、`website`、`app`、`projection` 是对外默认 domain；不要把 provider/debug helper 当默认入口。

## 标准执行顺序

### 1. 入口检查

先确认当前模板仓库已经具备可执行上下文：

```bash
uv run python -m agentplane.cli bootstrap inspect-local --repo-root <repo-root>
uv run python -m agentplane.cli bootstrap doctor --repo-root <repo-root>
```

如果是在 Windows 宿主执行，正式入口仍然是 `pwsh`，只是后续 source-bound 或 remote 动作会落到对应 backend。

### 2. 命令发现

优先顺序：

1. `uv run python -m agentplane.cli --help`
2. 对应 domain / object 的 `--help`
3. 对应 architecture / runbook / skill

### 3. 计划阶段

对副作用动作，优先运行计划或 dry-run：

```bash
uv run python -m agentplane.cli service plan --target <target> --name <service> --operation reconcile --repo-root <repo-root>
uv run python -m agentplane.cli website publish plan --target <target> --config-file <file> --cloudflare-env-file <file> --repo-root <repo-root>
uv run python -m agentplane.cli app delivery deploy --target <target> --app <app> --repo-root <repo-root> --dry-run
```

### 4. 执行阶段

只有在前置检查与计划阶段通过后，才进入正式执行：

```bash
uv run python -m agentplane.cli service apply --target <target> --name <service> --operation reconcile --repo-root <repo-root> --execute
uv run python -m agentplane.cli website publish apply --target <target> --config-file <file> --cloudflare-env-file <file> --repo-root <repo-root> --execute
uv run python -m agentplane.cli app delivery deploy --target <target> --app <app> --repo-root <repo-root> --execute
```

### 5. 验证阶段

执行后必须验证 live state：

```bash
uv run python -m agentplane.cli service verify --target <target> --name <service> --repo-root <repo-root>
uv run python -m agentplane.cli website publish verify --target <target> --config-file <file> --cloudflare-env-file <file> --repo-root <repo-root>
uv run python -m agentplane.cli app delivery verify --target <target> --app <app> --repo-root <repo-root> --execute
uv run python -m agentplane.cli projection verification run --target <target> --profile <profile> --repo-root <repo-root>
```

### 6. 回写阶段

当动作影响正式状态或摘要时，继续回写：

```bash
uv run python -m agentplane.cli projection ledger refresh --target <target> --repo-root <repo-root> --write
uv run python -m agentplane.cli app delivery inventory-refresh --target <target> --app <app> --repo-root <repo-root> --write
uv run python -m agentplane.cli app delivery doc-sync --target <target> --app <app> --repo-root <repo-root> --write
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
- 是否刷新了 `ledger` / `inventory` / `doc-sync`
- 是否需要补充人工 follow-up

## 禁止事项

1. 不要跳过计划阶段直接进入写操作。
2. 不要把文档说明当成现场验证结果。
3. 不要执行后不做验证。
4. 不要把 OS 差异重新抬回 truth、runbook 或 skill 层。

## 关联文档

- [control-plane.md](../architecture/control-plane.md#principles)
- [control-plane.md](../architecture/control-plane.md#cli-contract)
- [onepanel-cli-validation-workflow.md](onepanel-cli-validation-workflow.md)
- [app-project-delivery-workflow.md](app-project-delivery-workflow.md)
