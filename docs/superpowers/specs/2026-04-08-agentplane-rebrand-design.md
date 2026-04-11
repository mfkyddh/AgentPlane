# AgentPlane Rebrand Design

**Date:** 2026-04-08

## Goal

把 `OP_Linux` 一步到位重命名为 `AgentPlane`，并在不保留任何兼容层的前提下，同时完成主控制面仓库与 `sub2api` 协作面的硬切。

本轮覆盖两部分：

- `/root/work/OP_Linux` 当前控制面仓库整体切换到 `AgentPlane`
- `/root/work/sub2api` 只改与控制面的协作面、合同、文档、路径，不改 `sub2api` 自身公开项目名、`app_id`、`service_key`、镜像名、容器名和业务品牌

本轮不覆盖：

- `newapi`、`sub2apipay` 等其他应用仓库的 AgentPlane 协作面迁移
- `sub2api` 的上游开源品牌、README 产品定位、域名、生态文案重命名
- 为旧名字保留 alias、shim、wrapper、fallback、双目录、双入口

## Why Now

当前 active surface 里，`OP_Linux` 这个名字已经深入以下层面：

- 仓库根 README、architecture、runbook、reference、inventory、template
- Python 包目录 `ops/`、模块导入、CLI 入口 `uv run python -m ops.cli ...`
- repo-owned skills、plugin、技能投影生成器、测试快照
- 自动化任务名、R2 备份桶名、远端路径 `/opt/op_linux`、本地状态目录 `/data/op_linux`
- `sub2api` 的 handoff 合同目录 `deploy/op/` 与摘要文件 `docs/OP_LINUX_DEPLOYMENT.*.md`

如果只改品牌文案，不改 CLI、包名、路径和 handoff 资产，会留下长期语义裂缝：对外叫 `AgentPlane`，实际执行入口仍是 `ops.cli` 和 `OP_Linux` 路径。这与“彻底改造、不考虑兼容”的目标冲突。

## Hard Decisions

1. 品牌和正式执行入口一起硬切。正式 CLI 从 `uv run python -m ops.cli ...` 改为 `uv run python -m agentplane.cli ...`。
2. Python 包目录整体从 `ops/` 改为 `agentplane/`，不保留 `ops` 兼容包。
3. 仓库、远端目录、数据目录、自动化名字、插件名字、文档名字统一改成 `AgentPlane` / `agentplane`，不保留旧路径 fallback。
4. `sub2api` 保持应用品牌不变，但它与控制面的协作目录、合同文件、摘要文件、repo-local skills、owner docs 必须一起切到 `AgentPlane` 语义。
5. 因为本轮不迁移其他应用仓库，又不保留兼容层，所以 active formal app-repo collaboration scope 只能保留 `sub2api`。`newapi`、`sub2apipay` 必须退出当前 active `app` catalog，等待后续单独迁移。
6. archive 文档允许以“历史快照”身份提及 `OP_Linux`，但 active README、active runbook、正式命令示例、repo-owned skills、插件说明中不得继续把 `OP_Linux` 当成现役名字。
7. 仓库根目录重命名必须靠后执行。因为 project-local worktree 内部保存了 gitdir 路径，最终从 `/root/work/OP_Linux` 改到 `/root/work/AgentPlane` 后，需要执行 `git worktree repair` 或直接重建相关 worktree。

## Rejected Approaches

### 方案 A：只改品牌，不改 CLI 与包名

放弃原因：

- 会保留 `AgentPlane` 与 `ops.cli` 并存的永久裂缝
- 所有测试、skill、plugin、脚本仍要解释“新品牌 + 旧入口”
- 不符合“不考虑历史兼容性”

### 方案 B：双入口并存一段时间

放弃原因：

- 本质上仍是兼容层
- 会迫使 `sub2api` 和后续应用仓库继续处理双目录、双命令、双摘要文件
- 与本轮目标正面冲突

### 方案 C：本轮连 `newapi`、`sub2apipay` 一起迁移

放弃原因：

- 范围超出当前用户要求
- 会把“主控制面重命名”与“多个应用仓库协作面迁移”绑成一次大切换，难以定位问题
- 本轮只需要把 `sub2api` 做成首个完整样板

## Naming Contract

| 旧值 | 新值 | 说明 |
| --- | --- | --- |
| `OP_Linux` | `AgentPlane` | 正式产品名与仓库主名 |
| `op_linux` / `op-linux` | `agentplane` | 机器 slug、路径片段、备份前缀统一小写单词 |
| `/root/work/OP_Linux` | `/root/work/AgentPlane` | 主仓库根目录 |
| `uv run python -m ops.cli ...` | `uv run python -m agentplane.cli ...` | 正式 CLI 入口 |
| `ops/` | `agentplane/` | Python 包目录 |
| `op-linux-ops-cli` | `agentplane-cli` | `pyproject.toml` 中的项目名 |
| `/opt/op_linux` | `/opt/agentplane` | 远端正式控制面根目录 |
| `/data/op_linux` | `/data/agentplane` | 本地或远端状态数据目录 |
| `plugins/op-linux-control-plane/` | `plugins/agentplane-control-plane/` | 品牌化插件目录 |
| `docs/architecture/op-linux-app-collaboration.md` | `docs/architecture/agentplane-app-collaboration.md` | 应用协作文档主名 |
| `wsl-op-linux-secrets-backup` | `wsl-agentplane-secrets-backup` | 自动化任务名 |
| `OP_Linux_Backups` | `AgentPlane_Backups` | R2 备份桶名 |
| `backups/op_linux/...` | `backups/agentplane/...` | R2 备份前缀 |
| `deploy/op/` | `deploy/agentplane/` | `sub2api` handoff 合同目录 |
| `docs/OP_LINUX_DEPLOYMENT.<target>.md` | `docs/AGENTPLANE_DEPLOYMENT.<target>.md` | `sub2api` 非敏感交接摘要 |

## Current State Snapshot

### 主控制面仓库当前状态

已直接确认的 active 耦合包括：

- `README.md`、active runbook、architecture、template、tests、skills 中大量硬编码 `/root/work/OP_Linux`
- `pyproject.toml` 当前项目名为 `op-linux-ops-cli`
- Python 包当前是 `ops/`，其下包含 `cli/`、`domain/`、`scripts/`、`adapters/`
- 自动化脚本默认值仍使用 `/data/op_linux`、`OP_Linux_Backups`、`wsl-op-linux-secrets-backup`
- 插件目录和生成器仍使用 `plugins/op-linux-control-plane/`
- `inventory/apps/catalog.json` 当前仍把 `sub2api`、`newapi`、`sub2apipay` 都纳入 active app catalog

### `sub2api` 当前状态

已直接确认的 active 耦合包括：

- 根 `README.md`、`AGENTS.md`、`docs/README.md`、`docs/owner/README.md` 全部把正式控制面指向 `/root/work/OP_Linux`
- 合同目录当前为 `deploy/op/contract*.yaml`
- 合同中的摘要文件路径当前为 `docs/OP_LINUX_DEPLOYMENT.<target>.md`
- repo-local skills 当前直接引用 `/root/work/OP_Linux/.codex/skills/...` 和 `uv run python -m ops.cli ...`
- `sub2api` 保持自身品牌、`app_id=sub2api`、`service_key=sub2api`、`image_name=sub2api-prod` 的现状

## Target State

### Target State A: AgentPlane 主仓库成为唯一正式控制面

目标状态：

- active surface 全部使用 `AgentPlane` / `agentplane`
- 正式执行入口全部使用 `uv run python -m agentplane.cli ...`
- Python 源码、tests、plugin、repo-owned skills、生成器、inventory 输出全部使用新包名和新路径
- 远端脚本、自动化、备份、默认目录和 bucket 名不再出现 `op_linux`
- active formal app catalog 只保留已经迁移完成的 `sub2api`

### Target State B: `sub2api` 只保留 AgentPlane handoff surface

目标状态：

- `sub2api` 继续叫 `sub2api`
- `deploy/op/` 改为 `deploy/agentplane/`
- `deploy/agentplane/contract.wsl.yaml`
- `deploy/agentplane/contract.yaml`
- `deploy/agentplane/contract.prod2.yaml`
- `deploy/agentplane/runtime.env.example`
- `docs/AGENTPLANE_DEPLOYMENT.wsl.md`
- `docs/AGENTPLANE_DEPLOYMENT.prod0-main.md`
- `docs/AGENTPLANE_DEPLOYMENT.prod2-main.md`
- README、AGENTS、docs index、owner docs、repo-local skills 只提 `AgentPlane`
- `app_id`、`service_key`、镜像名、容器名、数据路径、业务域名保持不变

### Target State C: 其他应用仓库退出本轮 active repo-collaboration scope

为了保证“无兼容层”与“本轮只迁移 `sub2api`”同时成立，本轮必须收紧 formal app catalog：

- `inventory/apps/catalog.json` active 范围只保留 `sub2api`
- `newapi`、`sub2apipay` 的 repo-level app delivery 协作入口从 active scope 中移出
- 若它们仍有 service / website / host 相关对象，这些对象按既有基础设施对象面单独存在，但不再声称已经完成 AgentPlane repo 协作迁移

这个决定是本轮设计的硬约束，不是临时建议。否则系统会立刻进入“品牌已改、formal app repo 协作却半新半旧”的不一致状态。

## Workstreams

### Workstream 1: 主控制面身份硬切

内容：

- `README.md`、`AGENTS.md`、`docs/architecture/*`、`docs/runbooks/*`、`templates/*`、`inventory/*` 全量改名
- `docs/architecture/op-linux-app-collaboration.md` 改名为 `docs/architecture/agentplane-app-collaboration.md`
- active 文档示例命令全部改成 `uv run python -m agentplane.cli ...`

结果：

- 主文档面不再出现 `OP_Linux` 作为现役名字

### Workstream 2: Python 包与 CLI 硬切

内容：

- `ops/` 整体重命名为 `agentplane/`
- 所有 `from ops...`、`import ops...`、`python -m ops.cli` 改为新包路径
- `pyproject.toml` 中项目名、描述、wheel packages 同步更新
- 相关 CLI 与 import 测试同步改名

结果：

- 运行、导入、测试、帮助输出都只认识 `agentplane`

### Workstream 3: 插件、skills、生成器、自动化与路径硬切

内容：

- `plugins/op-linux-control-plane/` 改为 `plugins/agentplane-control-plane/`
- 技能投影生成器、plugin README、测试快照统一切到新名字
- 自动化默认名、R2 bucket、prefix、状态目录、命令串全部改名
- `/opt/op_linux`、`/data/op_linux`、`op_linux` 片段统一改到 `agentplane`

结果：

- 控制面周边资产不再对外暴露旧名字

### Workstream 4: `sub2api` handoff surface 硬切

内容：

- `deploy/op/` 改为 `deploy/agentplane/`
- 合同中的 `env_template`、`docs.app_summary_file` 等路径同步更新
- `docs/OP_LINUX_DEPLOYMENT.*.md` 改为 `docs/AGENTPLANE_DEPLOYMENT.*.md`
- `README.md`、`AGENTS.md`、`docs/README.md`、`docs/owner/README.md`、repo-local skills、校验脚本统一切到新名字
- 所有 `/root/work/OP_Linux` 改为 `/root/work/AgentPlane`
- 所有 `uv run python -m ops.cli ...` 改为 `uv run python -m agentplane.cli ...`

结果：

- `sub2api` 的正式控制面 handoff 只面向 `AgentPlane`

### Workstream 5: Active app catalog 收口到 `sub2api`

内容：

- 更新 `inventory/apps/catalog.json`
- 同步修正依赖 catalog 的测试、文档、摘要说明
- 不为 `newapi`、`sub2apipay` 增加 `deploy/agentplane` fallback 或 repo 路径 fallback

结果：

- 本轮 active formal app-repo collaboration 只有一条完全迁移链路：`sub2api`

### Workstream 6: 仓库根目录最终切换

内容：

- 在工作树内完成大部分改动和测试
- 在最终切换阶段把主仓库从 `/root/work/OP_Linux` 改到 `/root/work/AgentPlane`
- 对 project-local worktree 执行 `git worktree repair`，或直接删掉并重新创建仍需要保留的 worktree
- 修正所有依赖绝对路径的测试和文档后，再做最终验证

结果：

- 文件系统路径与品牌一致，且 worktree 状态恢复正常

## No-Compatibility Rules

本轮明确禁止以下做法：

- 保留 `ops/` 作为 import alias
- 保留 `python -m ops.cli` 作为 wrapper
- 保留 `/root/work/OP_Linux`、`/opt/op_linux`、`/data/op_linux` 的路径探测 fallback
- 同时保留 `deploy/op/` 与 `deploy/agentplane/`
- 同时保留 `docs/OP_LINUX_DEPLOYMENT.*.md` 与 `docs/AGENTPLANE_DEPLOYMENT.*.md`
- 在 active 文档里写“新名字推荐，旧名字也可以”

## Verification

本轮完成时至少要通过以下验证：

1. 主控制面入口验证：
   `uv run python -m agentplane.cli --help`
2. 主仓库相关测试通过：
   - CLI 入口测试
   - docs / skills / plugin 生成测试
   - app object / app delivery / website / service 相关最小回归测试
3. active surface 旧名清扫：
   - `rg -n "OP_Linux|op_linux|op-linux|python -m ops\\.cli" README.md docs inventory templates tests .codex plugins agentplane`
4. `sub2api` handoff surface 清扫：
   - `rg -n "/root/work/OP_Linux|deploy/op|OP_LINUX_DEPLOYMENT|python -m ops\\.cli" README.md AGENTS.md docs deploy .agents .codex tools`
5. `sub2api` 正式链路验证：
   - `uv run python -m agentplane.cli app object get --target prod0-main --app sub2api --repo-root /root/work/AgentPlane`
   - `uv run python -m agentplane.cli app delivery validate-contract --target wsl --app sub2api --repo-root /root/work/AgentPlane`
6. active formal app catalog 验证：
   - `inventory/apps/catalog.json` 只保留 `sub2api`

设计阶段不要求远端生产环境现场切换验证；那属于实施阶段验证。

## Risks And Controls

### 风险 1：仓库根目录改名会破坏现有 worktree

控制：

- 把目录改名放到实施末段
- 提前接受“现有 worktree 需要 repair 或重建”的事实，不尝试发明兼容路径
- 最终验证前重新检查两个 repo 的 branch / worktree 状态

### 风险 2：`newapi`、`sub2apipay` 本轮不迁移会造成 formal app surface 缺口

控制：

- 主动把它们从 active repo-collaboration catalog 中移出，而不是假装还能继续工作
- 在 README、architecture、后续计划里明确说明：它们等待下一轮 AgentPlane 迁移

### 风险 3：`sub2api` handoff 资产迁移后，doc-sync 与合同路径一起断裂

控制：

- 合同目录、摘要文件名、catalog 路径、repo-local skills 必须同一轮同时改
- `app object get` 与 `app delivery validate-contract` 必须作为最小回归验证

### 风险 4：archive 与 active 文档混杂旧名

控制：

- active surface 要求旧名清零
- archive 只允许在“历史快照”语境里保留旧名，不允许再把旧名写成当前入口

## Done Definition

本设计视为落地完成，必须同时满足：

- `AgentPlane` 成为主仓库、CLI、包名、路径、插件、自动化、文档的唯一现役名字
- `sub2api` 只通过 `deploy/agentplane/` 与 `docs/AGENTPLANE_DEPLOYMENT.*.md` 对接控制面
- `sub2api` 自身品牌与业务标识保持不变
- active formal app-repo collaboration scope 只保留 `sub2api`
- active surface 不再存在任何旧入口 alias 或双路径兼容

## Recommendation

采用本设计直接执行，不做“品牌先改一半、执行入口以后再改”的过渡。对当前目标而言，唯一自洽的路线就是：

- 主控制面硬切到 `AgentPlane`
- `sub2api` handoff 同步硬切
- 其他应用仓库暂时退出 active repo-collaboration scope，后续单独迁移

这条路线改动面最大，但与“彻底改造完成、不考虑历史兼容性”的要求完全一致。
