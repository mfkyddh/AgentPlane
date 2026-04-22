---
status: active
owner: control-plane
last_verified: 2026-04-11
superseded_by: null
---

# Control Plane Path Policy

## Goal

控制面 tracked 文件只保存可迁移的 canonical refs；宿主访问路径只存在于 runtime resolution 和 verification 结果里。

## Allowed In Canonical Truth

- `apps/<app>/contracts/<target>`
- 其它不含宿主路径前缀、可被 resolver 解释的逻辑引用

## Rejected From Canonical Truth

- Windows drive paths，例如 `D:/...`、`C:/...`
- Linux host-local paths，例如 `/root/...`、`/mnt/...`
- WSL UNC paths，例如 `\\wsl.localhost\...`

## Boundary Rules

- `truth` 只保存 canonical ref。
- `ledger` 只保存稳定摘要，不回写宿主访问路径。
- `verification` 允许保存 `resolved_path` 和现场观察值。

## Current Formal App Contract Rule

- app catalog 的 `repo_ref` 使用 `apps/<app>`。
- 标准 app contract ref 使用 `apps/<app>/contracts/<target>`。
- 当前 runtime 可以兼容读取旧 catalog/ledger 里的宿主路径或相对路径，但写回时必须收敛到 canonical refs。
