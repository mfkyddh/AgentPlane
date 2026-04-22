# prod0-main Governance Runbook

## 这台机器当前的角色

`prod0-main` 是 0 号生产机。  
当前正式口径很简单：

- 主机级对象面：`host`
- 网站与公网入口：`1Panel + OpenResty`
- 应用运行控制面：`AgentPlane compose`
- 主数据根目录：`/data`
- 样板应用：`sub2api`

## 2026-04-14 已核实的事实

### 已通过

- `host remote bash prod0-main` 的 Windows 入口和实际远端执行都可用。
- `sub2api` 的 `app resource verify` 已通过。
- `sub2api` 的 `service verify` 已通过。
- 当前 `sub2api` 两条探针链路都健康：
  - 宿主机回环：`http://127.0.0.1:18080/health`
  - 公网入口：`https://token.zzzai.cloud:8443/health`

### 仍有问题

1. `host audit prod0-main` 仍报 `sub2api` 的 config file 路径没有收口到目标目录语义。
当前 live path 仍然是 `/opt/agentplane/secrets/services/*.env`。

2. `host network audit prod0-main` 显示 `zqf_network` 缺少声明中的必需容器。
当前缺口按 `inventory/servers/prod0-main/inventory.json` 的 `managed_bridge_networks.required_for` 为准。

3. `projection verification run --target prod0-main --profile prod0-readonly` 当前失败。  
现场缺少 `/opt/agentplane/agentplane/scripts/onepanel/api_request.py`，导致 readonly 1Panel 验证面失效。

## 先执行哪几步

### 1. 主机与远端连通性

```bash
uv run python -m agentplane.cli host inventory prod0-main --repo-root <repo-root>
uv run python -m agentplane.cli host audit prod0-main --repo-root <repo-root>
uv run python -m agentplane.cli host network audit prod0-main --repo-root <repo-root>
uv run python -m agentplane.cli host remote bash prod0-main --dry-run --script-file agentplane/scripts/internal/remote/example.sh --repo-root <repo-root>
```

如果要直接读现场：

```bash
printf '%s\n' 'set -euo pipefail' 'hostname' 'docker ps --format "{{.Names}}"' \
  | uv run python -m agentplane.cli host remote bash prod0-main --repo-root <repo-root>
```

### 2. `sub2api` 应用面

```bash
uv run python -m agentplane.cli app resource verify --target prod0-main --app sub2api --repo-root <repo-root>
uv run python -m agentplane.cli projection runtime-env verify --target prod0-main --app sub2api --repo-root <repo-root>
uv run python -m agentplane.cli service verify --target prod0-main --name sub2api --repo-root <repo-root>
```

### 3. 只读验证面

```bash
uv run python -m agentplane.cli projection verification run --target prod0-main --profile prod0-readonly --repo-root <repo-root>
uv run python -m agentplane.cli projection ledger refresh --target prod0-main --repo-root <repo-root> --write
```

目前第 1 条命令仍会因为远端 helper 缺失而失败，这个结论本身就是当前状态，不要把它误读成“仓库文档写错了”。

## 当前治理重点

### 目录与 secrets

- `secrets/hosts/prod0-main/` 是主机级 truth。
- `secrets/services/` 仍承担 runtime projection 文件落点，但要和主机目录合同保持一致。
- `inventory/servers/prod0-main/README.md` 只是摘要；对象细节和审计仍看 `inventory.json` 与 `ledgers/`。

### 网络与入口

- `onepanel_openresty` 继续是 `host` 网络模式。
- 其余应用容器默认接入 `zqf_network`。
- `mihomo.service` 仍是宿主级正式基础设施，任何 Docker 网络或代理改动都要一起复核。

### `sub2api`

- 当前正式入口：`https://token.zzzai.cloud:8443`
- 当前正式容器：`sub2api-prod`
- 当前依赖：`postgres18-prod`、`redis7-prod`
- 当前数据目录：`/data/sub2api/data`

## 接下来应该补什么

1. 修掉 `prod0-readonly` 远端 helper 缺失，恢复只读验证面。
2. 对齐 `sub2api` config file 的目录合同。
3. 对齐 `zqf_network` 的 required container 声明与现场实际容器。
