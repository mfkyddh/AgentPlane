# WSL Host Governance Runbook

## 这台 WSL 现在扮演什么角色

当前 `wsl` 不是“唯一控制面源码位置”，而是本地 Linux 验证与 fixture 目标。  
本仓库现在要分清 3 个路径：

- Windows 控制面源码：`D:\Projects\AgentPlane`
- `wsl` target 当前 live repo 路径：`/root/work/AgentPlane`
- WSL 侧如果要执行源码绑定动作，必须使用 Linux 文件系统 checkout，例如 `/root/work/AgentPlane`，不能使用 `/mnt/<drive>/...`

文档、CLI 与 inventory 讨论的都是“角色”，不是把 Windows 工作目录和 WSL 工作目录混成一个。

## 当前结论

- `host inventory wsl`、`host audit wsl` 当前通过。
- `projection verification run --target wsl --profile wsl-fixture` 当前通过。
- `sub2api` 在 `wsl` 上的 `app object verify` 与 `app delivery verify --execute` 当前通过。
- 当前 `sub2api-dev` 的健康探针是 `http://127.0.0.1:18080/health`。

## 先看哪几个入口

### 如果你在 Windows 宿主

优先先确认控制面和 backend 绑定：

```powershell
pwsh -NoProfile -ExecutionPolicy Bypass -File .\.codex\environments\lib\invoke-agentplane-windows-uv.ps1 python -m agentplane.cli bootstrap inspect-local --repo-root D:\Projects\AgentPlane
pwsh -NoProfile -ExecutionPolicy Bypass -File .\.codex\environments\lib\invoke-agentplane-windows-uv.ps1 python -m agentplane.cli host local inspect --repo-root D:\Projects\AgentPlane
```

### 如果你已经在 WSL backend

优先从独立 Linux 文件系统 checkout 执行：

```bash
cd /root/work/AgentPlane
uv run python -m agentplane.cli host inventory wsl --repo-root /root/work/AgentPlane
uv run python -m agentplane.cli host audit wsl --repo-root /root/work/AgentPlane
uv run python -m agentplane.cli host live-gate plan --profile wsl --repo-root /root/work/AgentPlane
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
cd /root/work/AgentPlane
uv run python -m agentplane.cli host inventory wsl --repo-root /root/work/AgentPlane
uv run python -m agentplane.cli host audit wsl --repo-root /root/work/AgentPlane
uv run python -m agentplane.cli projection verification run --target wsl --profile wsl-fixture --repo-root /root/work/AgentPlane
```

真实 live gate 只在这个 Linux 文件系统 checkout 中显式执行：

```bash
cd /root/work/AgentPlane
uv run python -m agentplane.cli host live-gate run --profile wsl --repo-root /root/work/AgentPlane --execute
```

### 4. `sub2api` 应用面

```bash
cd /root/work/AgentPlane
uv run python -m agentplane.cli app object verify --target wsl --app sub2api --repo-root /root/work/AgentPlane
uv run python -m agentplane.cli app delivery verify --target wsl --app sub2api --repo-root /root/work/AgentPlane --execute
```

## 写回顺序

WSL 目标状态变化后，仍然按这个顺序回写：

1. `host inventory wsl --write`
2. `projection ledger refresh --target wsl --write`
3. 需要验证报告时再执行 `projection verification run --write-report`

`inventory/servers/wsl/README.md` 只是摘要，不承担第二真源职责。

## 当前需要继续保持的边界

- `wsl` 是本地 Linux 目标，不等于 Windows 控制面源码目录。
- 不要在 WSL 中对 `/mnt/<drive>/...` 下的 Windows checkout 执行 `uv`、`pytest`、`git` 或包管理命令。
- 任何自动化、fixture、app 验证都优先走 `uv run python -m agentplane.cli ...`。
- `sub2api` 的应用仓库真源当前在 `/root/work/sub2api`；控制面只通过 catalog 和 contract 读取它，不在本仓库复制第二份应用真源。
