---
status: archived
owner: AgentPlane maintainers
last_verified: 2026-04-02
superseded_by: null
audience: agent
layer: engineering
---

# 控制面命名注册表

结论：控制面命名注册表，确保对象域、surface、动词跨文档一致。

本文定义“一件东西在不同层应该叫什么”，避免 `example-api`、`example_api`、`service key`、容器名、compose 目录名半同步漂移。

本表中的“可强制”仅适用于正式 app contract 对象；基础设施服务、第三方官方镜像、历史快照目录不在当前强制范围内。

## 📋 当前可强制合同

| 字段 | 硬规则 | 说明 |
| --- | --- | --- |
| `app_id` | 必须匹配 `^[a-z0-9]+(?:-[a-z0-9]+)*$` | 在 `inventory/apps/catalog.json` 当前对应 `apps[].app` 字段；仅允许小写字母、数字、单个短横线；禁止前后短横线、连续短横线、下划线、大写。 |
| `inventory.service_key` | 必须与 `app_id` 完全相等 | 当前不接受别名，不接受运行态再命名。 |
| `image_family` | 默认正式 app 交付镜像 family 固定为 `<app_id>-prod`；登记为第三方官方镜像的目标可使用上游 family | 指镜像名去掉 tag / digest 后的 family，例如 `sub2api-prod:latest` 与 `sub2api-prod@sha256:...` 的 family 都是 `sub2api-prod`；`ghcr.io/wei-shaw/sub2api:latest` 的 family 是 `ghcr.io/wei-shaw/sub2api`。 |
| `prod_container` | 必须等于 `<app_id>-prod` | 不是“包含 `-prod`”，是完整等值。 |
| `dev_container` | 必须等于 `<app_id>-dev` | 不是“包含 `-dev`”，是完整等值。 |

## 📋 当前受强制的正式应用

| app_id | compose_dir | image_family | prod_container | dev_container | inventory.service_key |
| --- | --- | --- | --- | --- | --- |
| `sub2api` | `infra/compose/sub2api` | `wsl/prod0-main: ghcr.io/wei-shaw/sub2api` | `sub2api-prod` | `sub2api-dev` | `sub2api` |

## 📌 使用要求

- 新正式 app object 进入控制面前，必须先在本表新增一行，再允许进入合同校验。
- 未列入本表的对象，不得按正式 app naming contract 做失败判定。

---

## 🔧 路径策略

控制面 tracked 文件只保存**逻辑路径**（与平台无关的仓库内相对路径）；宿主物理路径只存在于 runtime resolution 和 verification 结果里。

> **逻辑路径 vs 物理路径**：逻辑路径如 `apps/sub2api/contracts/prod0-main`，不含 Windows 盘符、WSL 挂载点或 Linux 绝对前缀。物理路径如 `<repo-root>\apps\...` 或 `/opt/agentplane/apps/...`，是 Resolver 在运行时动态生成的。

### 允许写入真源的路径

- `apps/<app>/contracts/<target>` — 应用交付合同
- `inventory/servers/<target>/inventory.json` — 目标环境台账
- 其它不含宿主路径前缀、可被 resolver 解释的仓库内相对路径

### 禁止写入真源的路径

- Windows drive paths，例如 `D:/...`、`C:/...`
- Linux host-local paths，例如 `/root/...`、`/mnt/...`
- WSL UNC paths，例如 `\\wsl.localhost\...`

### 边界规则

| 产物 | 能保存什么 | 不能保存什么 |
|------|-----------|-------------|
| **truth**（真源） | 逻辑路径 | 物理路径 |
| **ledger**（台账） | 稳定摘要（逻辑路径） | 物理路径 |
| **verification**（验证证据） | 逻辑路径 + `resolved_path`（物理路径） + 现场观察值 | — |
