---
status: active
owner: AgentPlane maintainers
last_verified: 2026-04-25
superseded_by: null
audience: agent
layer: engineering
---

# 仓库结构规范

结论：AgentPlane 仓库采用固定顶层职责，不再保留顶层 `scripts/` 或公开兼容脚本入口。新增文件必须先归入现有职责；不能归入时，先更新本文和结构守门测试。

## 📂 顶层目录合同

| 路径 | 职责 | 约束 |
| --- | --- | --- |
| `agentplane/` | 生产代码、CLI、domain、runtime、provider、内部执行资产 | 正式能力必须通过 `agentplane ...` 暴露；内部脚本只能服务 CLI 或 provider |
| `tests/` | 自动化测试与测试 helper | 按业务域组织；共享 helper 放 `tests/support/`，不得新增万能 helper |
| `docs/` | 人读文档 | `architecture/` 放长期架构，`reference/` 放规范，`runbooks/` 放操作流程，`archive/` 只放退出主流程材料 |
| `infra/compose/` | Docker Compose 资产 | 每个服务一个目录；目标环境文件使用 `docker-compose.<target>.yml` |
| `inventory/` | 非敏感状态台账和逻辑真源 | 只保存逻辑路径与观察摘要，不写宿主物理路径或 secrets |
| `templates/` | 非敏感模板 | 只放 `.example`、示例配置和模板说明 |
| `.agents/` | Agent skill 真源与 marketplace 元数据 | 跨 Agent 通用 skill 目录；skill 内容必须路由回正式 CLI |
| `.github/`、`.githooks/` | CI 与 Git hook | Hook 和 CI 只能调用模块化命令或正式 CLI |

## 📄 顶层文件合同

| 文件 | 职责 |
| --- | --- |
| `README.md` | 项目入口、快速开始和高层导航 |
| `AGENTS.md` | AI 助手执行规则摘要 |
| `CONTRIBUTING.md`、`SECURITY.md`、`SUPPORT.md`、`CODE_OF_CONDUCT.md`、`LICENSE` | 开源协作、治理和许可证材料 |
| `ROADMAP.md` | 项目成熟度、阶段目标和非目标 |
| `CHANGELOG.md` | 面向人的版本变更摘要 |
| `pyproject.toml`、`uv.lock` | Python 包、工具链和锁定依赖 |

## 🔒 本地态合同

这些目录允许存在于工作区，但不得进入 Git，不得成为文档或代码默认入口。

| 路径 | 类型 | 处理规则 |
| --- | --- | --- |
| `secrets/` | 真实 secrets | 保留本地；禁止提交；文档只能引用目录语义，不展示真实内容 |
| `local/` | 本地协作材料 | 保留本地；需要长期化时迁入 `docs/` 或 `inventory/` 后再提交 |
| `tmp/` | 运行产物、operation ledger、渲染候选文件 | 可按需清理；不能作为真源 |
| `.venv/` | Python 虚拟环境 | 只保留根目录单份；可重建，不提交 |
| `.pytest_cache/`、`.ruff_cache/`、`__pycache__/` | 工具缓存 | 可随时清理，不提交 |
| `.worktrees/` | 本地临时 worktree 容器 | 只作本机工作区，不提交 |
| `.workbuddy/` | 本地协作工具状态 | 只作本机状态，不提交 |

如果某个本地态目录需要转为长期资产，必须先回答：

1. 它是否包含 secret 或宿主物理路径。
2. 它应该进入 `docs/`、`inventory/`、`templates/`、`infra/compose/` 还是 `agentplane/`。
3. 它是否会引入新的执行入口。
4. 是否需要新增结构守门测试。

## 🧭 新文件放置决策表

| 新文件类型 | 放置位置 |
| --- | --- |
| CLI 命令入口 | `agentplane/cli/` |
| 业务规则、对象生命周期、状态计算 | `agentplane/domain/<domain>/` |
| 跨平台执行、路径解析、backend 选择 | `agentplane/runtime/` |
| 外部服务协议适配 | `agentplane/adapters/` 或 `agentplane/providers/` |
| 内部远端脚本、provider 执行辅助 | `agentplane/scripts/internal/` 或明确的 provider 子目录 |
| 仓库治理逻辑 | `agentplane/domain/repository/` |
| 操作手册 | `docs/runbooks/` |
| 长期规范 | `docs/reference/` |
| 架构解释 | `docs/architecture/` |
| 文档地图 | `docs/README.md` |
| Docker Compose | `infra/compose/<service>/` |
| 非敏感 env/config 示例 | `templates/` |
| 真实 secret | `secrets/`，禁止提交 |
| 一次性迁移脚本 | 不入库；如果必须留痕，写成 runbook 结果或归档说明 |

## ⚠️ 禁止事项

- 禁止新增顶层业务目录，除非本文先定义长期职责。
- 禁止新增顶层 `scripts/`、`tools/`、`ops/` 作为第二入口。
- 禁止在 active 文档中把脚本路径写成默认执行入口。
- 禁止以 `utils.py`、`helpers.py`、`misc.py` 命名新生产模块。
- 禁止在 tracked 文件里保存 Windows 盘符、WSL UNC、`/mnt/...`、`/root/...` 等宿主物理路径作为真源。
- 禁止继续登记兼容入口；旧入口要么删除，要么移入 `docs/archive/` 作为历史说明。

## ✅ 结构变更 Checklist

每次新增、移动或删除文件前，先确认：

1. 它是否能归入已有顶层职责。
2. 它是否引入了新的执行入口。
3. 它是否包含 secret、宿主物理路径或现场私有路径。
4. 它是否需要同步更新 `README.md`、`AGENTS.md` 或文档索引。
5. 它是否需要新增或更新结构守门测试。
6. 它是否可以通过 `agentplane ...` 或模块化 Python 命令验证。
7. 如果它是 active 文档，是否能通过 [documentation-governance.md](documentation-governance.md) 的链接与可读性要求。
