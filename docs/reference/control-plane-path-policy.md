---
status: active
owner: control-plane
last_verified: 2026-04-11
superseded_by: null
audience: agent
layer: engineering
---

# Control Plane Path Policy

结论：逻辑路径优先于物理路径，真源只保存仓库内相对路径，物理路径由 resolver 动态生成。

## Goal

控制面 tracked 文件只保存**逻辑路径**（与平台无关的仓库内相对路径）；宿主物理路径只存在于 runtime resolution 和 verification 结果里。

> 💡 **逻辑路径 vs 物理路径**：逻辑路径如 `apps/sub2api/contracts/prod0-main`，不含 Windows 盘符、WSL 挂载点或 Linux 绝对前缀，在所有平台都一样。物理路径如 `<repo-root>\apps\...` 或 `/opt/agentplane/apps/...`，是 Resolver 在运行时动态生成的。

## Allowed In Tracked Truth

以下逻辑路径可以写入真源、台账等 tracked 文件：

- `apps/<app>/contracts/<target>` —— 应用交付合同
- `inventory/servers/<target>/inventory.json` —— 目标环境台账
- 其它不含宿主路径前缀、可被 resolver 解释的仓库内相对路径

## Rejected From Tracked Truth

以下物理路径**禁止**写入真源、台账等 tracked 文件：

- Windows drive paths，例如 `D:/...`、`C:/...`
- Linux host-local paths，例如 `/root/...`、`/mnt/...`
- WSL UNC paths，例如 `\\wsl.localhost\...`

## Boundary Rules

| 产物 | 能保存什么 | 不能保存什么 |
|------|-----------|-------------|
| **truth**（真源） | 逻辑路径 | 物理路径 |
| **ledger**（台账） | 稳定摘要（逻辑路径） | 物理路径 |
| **verification**（验证证据） | 逻辑路径 + `resolved_path`（物理路径） + 现场观察值 | — |

## Current Formal App Contract Rule

- app catalog 的 `repo_ref` 使用逻辑路径 `apps/<app>`。
- 标准 app contract ref 使用逻辑路径 `apps/<app>/contracts/<target>`。
- 当前 runtime 可以兼容读取旧 catalog/ledger 里的物理路径或相对路径，但写回时必须收敛到逻辑路径。
