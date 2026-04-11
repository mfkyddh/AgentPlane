# 1Panel CLI Validation Workflow

## 目的

本文说明 1Panel 相关验证能力在正式控制面中的分工。验证 profile 仍然是：

- `wsl-fixture`
- `prod2-readonly`
- `prod0-readonly`

但正式任务入口已经从 `onepanel fixture/suite/ledger` 收口到 `projection verification`、`projection fixture`、`projection ledger`。`onepanel` 只保留 provider/debug 对象壳层。

## 控制面边界

| 分层 | 正式入口 | 说明 |
| --- | --- | --- |
| provider/debug 对象壳层 | `uv run python -m agentplane.cli onepanel <panel|firewall|cronjob|task> ...` | 只用于 1Panel provider 原生对象读取、debug 和底层核对。 |
| runtime-env 投影面 | `uv run python -m agentplane.cli projection runtime-env plan --target prod0-main --app sub2api --repo-root /root/work/AgentPlane` | 从 app resource truth 派生 app runtime env，不回写业务真源。 |
| 验证任务面 | `uv run python -m agentplane.cli projection verification run --target <target> --profile <profile> --repo-root /root/work/AgentPlane` | 统一承接只读验证套件；仍可按 profile 透传 website/container/project/app/firewall 选择器。 |
| fixture 任务面 | `uv run python -m agentplane.cli projection fixture <plan|apply|cleanup> --target wsl --profile wsl-fixture --repo-root /root/work/AgentPlane` | WSL 可回收测试面；`apply` / `cleanup` 必须显式带 `--execute`。 |
| ledger 任务面 | `uv run python -m agentplane.cli projection ledger refresh --target <target> --repo-root /root/work/AgentPlane --write` | 刷新 tracked verification report、object ledgers 与 inventory 投影。 |

## Website Publish 对齐规则（Lane 5）

`uv run python -m agentplane.cli website publish <plan|apply|verify> ...` 只负责公网入口发布本身。
发布后的验证与台帐刷新统一由 `projection` 控制面承接，不在 runbook 重复维护第二套流程：

- 验证：`projection verification run ...`
- 台帐刷新：`projection ledger refresh ... --write`

`website publish` 与 `website apply` 的 JSON 输出均提供 `follow_through` 字段，包含当前 target 对应的推荐命令。执行时优先消费该字段，避免文档和实现漂移。

## 验证面概览

| 验证面 | 角色 | 默认姿态 |
| --- | --- | --- |
| `wsl` + `wsl-fixture` | 主 mutation / regression / plugin 验证面 | 允许通过 `projection fixture` 变更 |
| `prod2-main` + `prod2-readonly` | 现场兼容性审计面 | 默认只读审计 |
| `prod0-main` + `prod0-readonly` | 升级前审计面 | 默认只读预检 |

## WSL Fixture Surface

`wsl` 仍是 primary mutation target，但生命周期命令已经迁到 `projection`。

环境入口：

- 首选 env 真源：`secrets/hosts/wsl/onepanel/api.env`
- 兼容旧路径：`secrets/services/onepanel-api.wsl.env`
- 最小连通性检查：

```bash
uv run python -m agentplane.cli onepanel --env wsl panel get
```

标准闭环：

### 1. Plan

```bash
uv run python -m agentplane.cli projection fixture plan --target wsl --profile wsl-fixture --repo-root /root/work/AgentPlane
```

### 2. Apply

```bash
uv run python -m agentplane.cli projection fixture apply --target wsl --profile wsl-fixture --repo-root /root/work/AgentPlane --execute
```

### 3. Verify

```bash
uv run python -m agentplane.cli projection verification run --target wsl --profile wsl-fixture --repo-root /root/work/AgentPlane --write-report
```

### 4. Ledger

```bash
uv run python -m agentplane.cli projection ledger refresh --target wsl --repo-root /root/work/AgentPlane --write
```

### 5. Recycle Baseline

```bash
uv run python -m agentplane.cli projection fixture cleanup --target wsl --profile wsl-fixture --repo-root /root/work/AgentPlane --execute
uv run python -m agentplane.cli projection ledger refresh --target wsl --repo-root /root/work/AgentPlane --write
```

## Prod2 Readonly Surface

`prod2-readonly` 继续用于 live 审计，但正式入口改为：

```bash
uv run python -m agentplane.cli projection verification run \
  --target prod2-main \
  --profile prod2-readonly \
  --repo-root /root/work/AgentPlane \
  --website-alias token \
  --container-name sub2api-prod \
  --app-name sub2api \
  --write-report
```

当前审计口径：

- `ok=false` 仍可能是有效审计结果。
- 当现场对象模型与 formal domain 边界不一致时，失败报告本身就是机器证据。
- 解释性说明写回 host README / runbook，不直接改 verification report。

如需刷新 tracked artifacts：

```bash
uv run python -m agentplane.cli projection ledger refresh --target prod2-main --repo-root /root/work/AgentPlane --write
```

## Prod0 Readonly Surface

`prod0-readonly` 继续用于升级前只读审计：

```bash
uv run python -m agentplane.cli projection verification run --target prod0-main --profile prod0-readonly --repo-root /root/work/AgentPlane --firewall-tab port --write-report
```

如需刷新对象投影：

```bash
uv run python -m agentplane.cli projection ledger refresh --target prod0-main --repo-root /root/work/AgentPlane --write
```

## 生成物与约束

- `projection verification run` 始终是只读验证。
- `projection fixture` 是 WSL fixture 创建、刷新、清理的唯一正式 mutation path。
- `--write-report` 会写入 `inventory/servers/<target>/ledgers/verification-<profile>.json|md`。
- `projection ledger refresh --write` 会刷新 `inventory/servers/<target>/ledgers/*.json|md` 以及 inventory 中的对象投影。
- `verification-*.json|md` 与对象 ledger 都是 generated machine artifacts，不手工改内容。
- plugin / automation 应消费 `--json` 输出，并基于 `error.code` 分支，不基于自由文本。
