---
status: active
owner: AgentPlane maintainers
last_verified: 2026-04-24
superseded_by: null
---

# 技术栈规范

本文定义 AgentPlane 仓库默认采用、允许采用和需要审批后采用的技术选择。目标是控制复杂度，而不是禁止演进。

## 当前基线

| 层面 | 标准选择 | 说明 |
| --- | --- | --- |
| 语言 | Python `3.12+` | 与 `pyproject.toml` 保持一致 |
| 包管理 | `uv` | 依赖、虚拟环境、测试命令统一走 `uv` |
| CLI | Python 标准库 `argparse` + `agentplane.cli` | 当前项目保持轻依赖，不引入第二套 CLI 框架 |
| 测试 | `pytest` | 默认门禁必须离线、确定性 |
| lint | `ruff` | 覆盖导入排序、未使用导入和明显运行错误 |
| 文档 | Markdown + `docs/reference` / `docs/runbooks` | reference 放规则，runbook 放操作 |
| 容器 | Docker Compose v2：`docker compose` | 不使用旧式 `docker-compose` 作为正式入口 |
| 正式执行 | `agentplane ...` | 所有正式操作从统一 CLI 进入 |

## 引入新依赖

新增依赖前先回答：

1. 是否能用标准库或已有项目依赖解决。
2. 是否会影响跨平台默认门禁。
3. 是否会把 live 环境要求带进默认测试。
4. 是否需要 secrets、网络、Docker 或 SSH。
5. 是否有清晰的维护者、许可证和替代方案。

生产依赖要写进 `[project.dependencies]`；只服务开发、测试、格式化的依赖写进 `[dependency-groups].dev`。

## Python 边界

- 仓库只维护根目录 `.venv`，不创建 `.venv-win`、`.venv-wsl` 等平台变种。
- 不设置平台专属的 `UV_PROJECT_ENVIRONMENT`。
- Windows 宿主默认从 `pwsh` 入口执行；需要 Linux 能力时通过 resolver/backend 路由到 WSL 或远端。
- 跨平台路径处理优先使用现有 runtime/path policy，不在调用点拼接平台路径。

## Node 与前端

本仓库不是前端应用仓库，默认不引入 Node 工具链。

如果接入的应用仓库需要 Node：

- 包管理使用 `pnpm`。
- 构建、测试、制品生产留在应用仓库。
- 正式部署、验证、inventory 回写仍由 AgentPlane 控制面发起。

## 基础设施与远端

- 正式远端 Linux 操作走 `agentplane infra ...`，不要手写多层 `ssh ... bash -c`。
- 真实 Docker、SSH、WSL、provider 操作必须显式 plan，再在明确环境中 execute。
- secrets 只放 `secrets/`，非敏感模板放 `templates/`。

## 技术债处理

当一个文件或测试辅助明显过大时，不做一次性大爆炸重构。推荐策略：

- 先补 characterization test，锁住当前行为。
- 每次业务改动只顺手抽出一个清晰职责。
- 拆分后保持旧入口兼容，直到调用点迁完再退役。
