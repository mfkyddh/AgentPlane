# Linux Governance Specification

## 目标

定义本仓库在 Linux/WSL 环境下的统一治理约束，确保自动化可复用、可验证、可审计。
本页只定义 Linux / WSL backend 约束，不改变宿主入口选择。

## 治理边界

- 代码与模板（可跟踪）：`infra/compose/`、`ops/`、`templates/`、`docs/`、`inventory/`。
- 本地敏感文件（不可跟踪）：`secrets/`。
- 服务运行数据（主机态）：`/data/<service>/...`。
- 独立数据盘的正式 Linux 主机，应优先把该数据盘挂载到 `/data`。
- Docker 运行根目录应收口到 `/data/docker`；镜像层、容器层和构建缓存随 `data-root` 一起迁移，不单独定义“镜像下载目录”。
- 根 `AGENTS.md` 仅保留稳定规则，执行细节下沉到 runbook。
- AgentPlane 管理的应用仓库若使用 Git worktree，默认根目录为应用仓库内 `.worktrees/`，且应用仓库 `.gitignore` 必须忽略该目录。

## 执行模型

- 默认采用 `host-entry-first, backend-aware`。
- Windows 宿主场景固定走 `pwsh -> formal CLI -> WSL/SSH backend`；Linux/macOS 继续使用原生 POSIX shell。
- Windows 与 WSL 禁止共享同一个工作目录；WSL/Linux 源码绑定动作只能在 Linux 文件系统 checkout 内执行，不能使用 `/mnt/<drive>/...` 作为仓库根。
- 真实 WSL/SSH/Docker live integration gate 必须通过 `host live-gate` 单独执行；默认本地 `pytest` 不触发真实 backend。
- 当前已经处于 Linux 文件系统源码根时，源码绑定动作直接在该 backend 内执行，不再重复包一层宿主入口。
- 只有 WSL 内确实需要 shell 特性时才使用 `sh -lc` / `bash -lc`。
- 默认以 `root` 在 WSL 本地执行；仅在需要用户态环境或文件归属控制时切换用户。
- 远端 Linux 生产机默认走 `root` 直连 SSH；只有尚未完成 root 直连准备的目标，才临时走具备 sudo 权限账户。
- 命令和文件路径使用绝对 Linux 路径，避免跨目录误执行。

## 自动化与执行入口治理

- 仓库自动化主栈固定为 Python + `uv`。
- 每个物理 checkout 只保留根目录 `.venv`；不使用 `.venv-win`、`.venv-wsl` 或 `UV_PROJECT_ENVIRONMENT` 分叉虚拟环境。
- Bash 只作为薄包装层，不作为仓库主编排语言。
- Node.js 不是仓库主控制面；只用于临时工具调用或必要生态桥接。
- 仓库日常自动化正式入口统一为：
  `uv run python -m agentplane.cli ...`
- 之所以采用 Python + `uv`，是因为该组合更适合承载运维编排、配置治理、HTTP API 调用、结构化校验与可测试模块边界。
- `python -m` 入口必须与模块边界绑定，避免把仓库重新拉回零散脚本集合。
- Python 类项目的依赖安装、虚拟环境和命令执行优先使用 `uv`。
- Node.js 类项目的依赖安装和脚本执行优先使用 `pnpm`；临时 Node 工具优先 `pnpm dlx ...`，仅在不兼容时退回 `npx`。
- Docker Compose 运行命令统一使用 `docker compose`；不把 legacy `docker-compose` 作为正式依赖。
- Bash 脚本仅承担：
  - 环境引导（如最小化 bootstrap）
  - SSH 跳板包装
  - 对历史流程的兼容桥接
- 旧 Bash 流程改造时，优先变更为“Bash 调 Python CLI”，而不是继续扩展 Bash 业务逻辑。
- 新增或重构自动化能力时，优先落到 Python 模块并由 `agentplane.cli` 暴露命令入口。
- 仅在 Python 不可行或代价显著过高时，才引入新的 Bash/Node 常驻逻辑。
- live gate 正式入口为 `uv run python -m agentplane.cli host live-gate ...`；`plan` 可在任意 checkout 查看，`run --execute` 只允许在 Linux 文件系统 checkout 执行。
- WSL 本机 `1Panel` 计划任务只负责按周期触发，不在面板页面中保存业务逻辑。
- 新增 WSL 本机自动化任务时，必须同时提供：
  - 稳定的 `agentplane.cli` 命令入口
  - `inventory/servers/wsl/inventory.json` 中的登记项
  - 对应 runbook 与验证命令
- 涉及 `secrets/` 的周期性远端备份时，必须采用“快速指纹 + 强指纹”双阶段检测，避免无变化时重复打包上传。

## 资源与网络治理

- Compose 服务模板必须同时维护：
  - `docker-compose.wsl.yml`
  - `docker-compose.prod0.yml`
- 上述模板文件名属于仓库命名规范；实际执行统一使用 `docker compose -f ...`。
- 容器命名规则：
  - WSL 测试：`-dev`
  - 生产环境：`-prod`
- 仓库管理的宿主机发布端口默认绑定 `0.0.0.0`。
- 生产环境项目容器默认接入 `zqf_network`。
- `openresty` 相关 1Panel 容器是例外，必须使用 Docker `host` 网络。

## Secrets 治理

- 真实 SSH、env、密钥统一放在 `secrets/`。
- 模板统一放在 `templates/`。
- 新 PEM 文件在使用前必须 `chmod 600`。
- 本地 secrets 初始化统一参考：
  [bootstrap-secrets.md](../runbooks/bootstrap-secrets.md)

## 变更与验证基线

- 变更前先确认当前真实状态（容器、网络、配置），不要只依赖历史文档。
- 变更后至少完成：
  - 命令可达性验证
  - 关键服务状态验证
  - 文档一致性更新
- 公网/Cloudflare 路径排障时，优先用 loopback 或直连 IP 作为基准链路。

## 非目标

- 本文不替代服务专用 runbook，不覆盖特定生产专题操作步骤。
- 涉及专题迁移与切换的细节，按对应 runbook 执行。
