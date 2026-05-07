# 技术栈与跨平台规范

> 本文合并了原 tech-stack.md、cross-platform.md 和 container-conventions.md 的核心内容。

---

## 当前基线

| 层面 | 标准选择 | 说明 |
|---|---|---|
| 语言 | Python `3.12+` | 与 `pyproject.toml` 保持一致 |
| 包管理 | `uv` | 依赖、虚拟环境、测试命令统一走 `uv` |
| CLI | Python 标准库 `argparse` + `agentplane.cli` | 轻依赖，不引入第二套 CLI 框架 |
| 测试 | `pytest` | 默认门禁必须离线、确定性 |
| lint | `ruff` | 覆盖导入排序、未使用导入和明显运行错误 |
| 文档 | Markdown | reference 放规则，runbook 放操作 |
| 容器 | Docker Compose v2：`docker compose` | 不使用旧式 `docker-compose` |
| 正式执行 | `agentplane ...` | 所有正式操作从统一 CLI 进入 |

---

## 引入新依赖

新增依赖前先回答：

1. 是否能用标准库或已有项目依赖解决
2. 是否会影响跨平台默认门禁
3. 是否会把 live 环境要求带进默认测试
4. 是否需要 secrets、网络、Docker 或 SSH
5. 是否有清晰的维护者、许可证和替代方案

生产依赖写进 `[project.dependencies]`；只服务开发、测试、格式化的依赖写进 `[dependency-groups].dev`。

---

## 跨平台约束

### Windows 宿主

| 规则 | 级别 | 原因 |
|---|---|---|
| 默认入口 Shell 使用 `pwsh` | 🔴 | `cmd` 语法差异大，易出错 |
| `git`、`uv`、`pnpm`、测试等直接在 `pwsh` 中运行 | 🟡 | 减少 Shell 切换开销 |
| 需要 Linux 能力时，优先用 `wsl.exe -e <程序> <参数>` | 🟡 | 直接调用 WSL 程序 |

### WSL 后端

| 规则 | 级别 | 原因 |
|---|---|---|
| Windows 和 WSL **共用同一份源码 checkout** | 🔴 | 避免两份代码不同步 |
| 不要仅为运行 WSL 操作而 clone 第二份仓库 | 🔴 | 会造成配置分叉 |
| 避免两个 Shell 同时执行包管理器写入 | 🟡 | 防止 `.venv` 损坏 |

### Linux / macOS

- 直接使用本地 POSIX Shell 执行本地命令
- 远程 Linux 操作走：`pwsh → agentplane.cli → WSL/SSH backend`

### Shell 选择决策

```
需要执行命令
  ├── Windows 原生命令 → pwsh
  ├── 需要 Linux 环境 → wsl.exe -e <程序> <参数>
  │   └── 需要管道/重定向 → wsl.exe bash -lc "cmd1 | cmd2 > out"
  └── 远程 Linux → agentplane infra remote bash
```

---

## 虚拟环境

| 规则 | 级别 | 原因 |
|---|---|---|
| Python 项目统一使用 `uv` | 🟡 | 速度快、行为一致 |
| 每个物理 checkout **只保留一个 `.venv`** | 🔴 | 禁止创建平台变种 |
| **不要**设置 `UV_PROJECT_ENVIRONMENT` 为平台相关路径 | 🔴 | 让 `uv` 自动使用根目录 `.venv` |
| Node.js 项目统一使用 `pnpm` | 🟡 | 速度快、磁盘省 |

### 为什么单虚拟环境

双环境（`.venv-win` + `.venv-wsl`）会导致：
- 依赖版本不同步
- `uv.lock` 与实际安装的包不一致
- 磁盘浪费

正确做法：`uv` 在 WSL 侧通过 `/mnt/` 访问同一个 `.venv`。

---

## CLI 可用性

| 优先级 | 方式 | 条件 |
|--------|------|------|
| 1 | `agentplane ...` | `uv tool install -e .` 已执行 |
| 2 | `uv run agentplane ...` | 仓库内，`uv` 可用 |
| 3 | `python -m agentplane ...` | `.venv` 已激活 |

---

## Node 与前端

本仓库不是前端应用仓库，默认不引入 Node 工具链。

如果接入的应用仓库需要 Node：
- 包管理使用 `pnpm`
- 构建、测试留在应用仓库
- 正式部署、验证仍由 AgentPlane 控制面发起

---

## 容器规范

### Docker Compose

| 规则 | 级别 | 原因 |
|---|---|---|
| 运行时命令统一使用 `docker compose`（空格） | 🔴 | 旧版已弃用 |
| 服务资产放在 `infra/compose/<service>/` | 🟡 | 统一存放 |
| 本地 Secrets 放在 `secrets/services/` | 🟡 | 与 compose 分离 |

### 容器命名

| 规则 | 级别 | 原因 |
|---|---|---|
| 测试环境容器名以 `-dev` 结尾 | 🔴 | 防止误删生产 |
| 生产环境容器名以 `-prod` 结尾 | 🔴 | 同上 |

格式：`<服务名>-<环境>`，例如 `sub2api-prod`、`postgres-dev`。

### 网络与数据

- 生产容器接入 `zqf_network`
- 持久化数据放在 `/data/<service>/...`
- Docker 运行根目录收口到 `/data/docker`

### Docker 应用打包

采用"宿主机构建 + runtime-only Dockerfile"模式：

1. 在 WSL 宿主机完成构建，产物放到 `dist/oplinux/`
2. Runtime-only Dockerfile 只复制产物，不重新编译
3. 正式交付链路：`build-artifact → ship-image → render-runtime → deploy/verify`

---

## 引入新技术

当一个文件或测试辅助明显过大时，不做一次性大爆炸重构：

1. 先补 characterization test，锁住当前行为
2. 每次业务改动只顺手抽出一个清晰职责
3. 拆分后保持旧入口兼容，直到调用点迁完再退役

---

## 关联文档

- [架构](architecture.md) — 控制面核心合同
- [命令参考](command-reference.md) — CLI 命令
