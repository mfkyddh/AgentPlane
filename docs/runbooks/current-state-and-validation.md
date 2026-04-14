# AgentPlane 当前现状与验证

## 这页解决什么问题

这不是第二真源，而是给人看的当前状态总览。  
机器可消费的正式真源仍然是 `inventory/`、`tmp/operation-ledger/`、`secrets/` 和应用仓库合同。

## 2026-04-14 快照

### 控制面与源码位置

| 角色 | 当前路径 | 说明 |
| --- | --- | --- |
| Windows 控制面源码根 | `D:\Projects\AgentPlane` | 当前主入口所在目录；本地 `git`、文档编辑、Windows 侧 `pwsh` 包装都从这里发起。 |
| Linux backend 源码根 | `/mnt/d/Projects/AgentPlane` | 当前 Windows 控制面对应的 WSL backend 路径；`uv`、`pytest`、Linux-only 构建与验证从这里执行。 |
| WSL 目标机上的运行仓库 | `/root/work/AgentPlane` | `wsl` target 当前 inventory 中记录的 live repo 路径；它描述的是目标侧状态，不等于当前本地源码根。 |
| `sub2api` 应用仓库 | `/root/work/sub2api` | 当前正式样板应用仓库；`deploy/agentplane/contract*.yaml` 位于这里。 |

### 本轮重点样板

| 面 | 当前样板 | 角色 |
| --- | --- | --- |
| 本地/开发面 | `wsl` | 本地 fixture、回归验证、`sub2api-dev` 运行面。 |
| 生产面 | `prod0-main` | 0 号生产机；`AgentPlane compose + 1Panel/OpenResty` 联合控制面。 |
| 应用层 | `sub2api` | 当前唯一纳入本轮全面验证的应用层项目。 |

## 已验证结论

### 仓库命令面

- `bootstrap inspect-local`、`host local inspect` 在当前 Windows 控制面 + WSL backend 组合下可正常返回路径绑定结果。
- 当前本轮修复后，仓库 `pytest` 已恢复到全绿；之前卡住的 10 个失败都已收口。

### WSL

- `host inventory wsl`、`host audit wsl` 已通过。
- `projection verification run --target wsl --profile wsl-fixture` 已通过。
- `sub2api` 在 `wsl` 上执行 `app object verify`、`app delivery verify --execute` 已通过。
- 当前 `sub2api` WSL 探针为 `http://127.0.0.1:18080/health`，本轮验证返回 `{"status":"ok"}`。

### prod0-main

- `host remote bash prod0-main` 的 Windows 入口与实际 SSH backend 都可用。
- `sub2api` 在 `prod0-main` 上执行 `app object verify`、`app delivery deploy --dry-run`、`app delivery verify --execute` 已通过。
- 本轮验证确认了两条健康链路：
  - 宿主机回环：`http://127.0.0.1:18080/health`
  - 公网入口：`https://token.zzzai.cloud:8443/health`

## 当前明确存在的问题

### 仓库实现侧

1. `projection runtime-env plan` 当前会把渲染后的完整 env 直接输出到 stdout。  
这会把真实密码、JWT secret 等敏感值暴露在终端与日志里，应该改为默认脱敏或显式 `--reveal-secrets` 才允许输出。

2. `prod0-readonly` 的 1Panel 只读验证链路当前不可用。  
现场报错是远端缺少 `/opt/agentplane/agentplane/scripts/onepanel/api_request.py`，说明 prod0 的 readonly provider surface 与仓库当前 CLI/脚本布局已经漂移。

### 生产机环境侧

1. `host audit prod0-main` 仍然认为 `sub2api`、`sub2apipay` 的 config file 没有收口到目标目录。  
当前 live path 仍指向 `/opt/agentplane/secrets/services/*.env`，而不是预期的 `/data/<app>/...` 语义。

2. `host network audit prod0-main` 显示 `zqf_network` 缺少声明中的必需容器。  
当前缺口是 `chatgpt-register-v2-prod` 和 `minio-prod`；要么修 live state，要么修 inventory/required container contract，不能长期漂着。

## 建议优先级

### 先改仓库

1. 给 `projection runtime-env plan` 增加默认脱敏输出。
2. 修复 `prod0-readonly` 远端 onepanel helper 的分发/查找路径。
3. 把 prod0 的 config file 收口规则写成明确合同，避免 audit 和现场长期打架。

### 再改现场

1. 统一 prod0 的 `sub2api` / `sub2apipay` config file 落点。
2. 对齐 `zqf_network` 的 required container 声明与现场实际容器。
3. 重新执行 `prod0-readonly` 验证，确认 1Panel 只读面恢复。

## 推荐阅读顺序

1. [wsl-host-governance.md](./wsl-host-governance.md)
2. [prod0-main-governance.md](./prod0-main-governance.md)
3. [app-project-delivery-workflow.md](./app-project-delivery-workflow.md)
4. [onepanel-cli-validation-workflow.md](./onepanel-cli-validation-workflow.md)
