# WSL Host Governance Runbook

## 这台 WSL 现在扮演什么角色

当前 `wsl` 不是“唯一控制面源码位置”，而是本地 Linux 验证与 fixture 目标。  
本仓库现在要分清 3 个角色：

- 控制面源码：`<repo-root>`，只保留一份 checkout。
- WSL backend 工作目录：由 resolver 从 `<repo-root>` 派生。
- 官方镜像应用：`sub2api` 当前由本仓库 compose 管理，WSL 从官方镜像源拉取。

文档、CLI 与 inventory 讨论的都是“角色”，不是要求用户维护两份源码。

## 当前结论

- `host inventory wsl`、`host audit wsl` 当前通过。
- `projection verification run --target wsl --profile wsl-fixture` 当前通过。
- `sub2api` 在 `wsl` 上通过 `projection runtime-env verify` 与 `service verify` 核对。
- 当前 `sub2api-dev` 的健康探针是 `http://127.0.0.1:18080/health`。

## 先看哪几个入口

### 如果你在 Windows 宿主

优先先确认控制面和 backend 绑定：

```powershell
pwsh -NoProfile -ExecutionPolicy Bypass -File .\.codex\environments\lib\invoke-agentplane-windows-uv.ps1 python -m agentplane.cli bootstrap inspect-local --repo-root <repo-root>
pwsh -NoProfile -ExecutionPolicy Bypass -File .\.codex\environments\lib\invoke-agentplane-windows-uv.ps1 python -m agentplane.cli host local inspect --repo-root <repo-root>
```

### 如果你已经在 WSL backend

优先从当前 checkout 执行：

```bash
cd <repo-root>
uv run python -m agentplane.cli host inventory wsl --repo-root <repo-root>
uv run python -m agentplane.cli host audit wsl --repo-root <repo-root>
uv run python -m agentplane.cli host live-gate plan --profile wsl --repo-root <repo-root>
```

## WSL 最小治理检查

### 1. 工具链

```bash
uv --version
python3 --version
docker --version
docker compose version
```

### 2. 网络基线

```bash
ip route | awk '/default/ {print $3}'
docker network inspect zqf_network >/dev/null
```

需要通过宿主代理出网时，优先使用当前默认网关，不把 `127.0.0.1` 当成跨边界真源。

### 3. 主机对象面

```bash
cd <repo-root>
uv run python -m agentplane.cli host inventory wsl --repo-root <repo-root>
uv run python -m agentplane.cli host audit wsl --repo-root <repo-root>
uv run python -m agentplane.cli projection verification run --target wsl --profile wsl-fixture --repo-root <repo-root>
```

真实 live gate 在当前 checkout 中显式执行：

```bash
cd <repo-root>
uv run python -m agentplane.cli host live-gate run --profile wsl --repo-root <repo-root> --execute
```

### 4. `sub2api` 应用面

```bash
cd <repo-root>
uv run python -m agentplane.cli projection runtime-env verify --target wsl --app sub2api --repo-root <repo-root>
uv run python -m agentplane.cli service verify --target wsl --name sub2api --repo-root <repo-root>
```

## 写回顺序

WSL 目标状态变化后，仍然按这个顺序回写：

1. `host inventory wsl --write`
2. `projection ledger refresh --target wsl --write`
3. 需要验证报告时再执行 `projection verification run --write-report`

`inventory/servers/wsl/README.md` 只是摘要，不承担第二真源职责。

## 当前需要继续保持的边界

- `wsl` 是本地 Linux target，不是第二份控制面源码。
- 不要同时从 Windows 与 WSL 对同一个 checkout 执行包管理器写操作。
- 任何自动化、fixture、service 验证都优先走 `uv run python -m agentplane.cli ...`。
- 当前没有 active 本地应用仓库 catalog object；需要从源码交付的应用重新 onboard 后再进入 `app delivery`。
