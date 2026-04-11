# app-oplinux-delivery 技能设计

## 1. 目标

创建一个全局可复用技能 `app-oplinux-delivery`，让应用层项目 agent 在面对“新增应用接入 OP_Linux”“从应用仓库发起构建、上传、部署、更新、回滚”“把旧控制面迁移到 OP_Linux”这类任务时，能够统一遵守同一套边界、流程和校验要求。

该技能不是 `sub2api` 专用技能，而是以 `sub2api` 作为首个正式样板，把当前已经沉淀在 `OP_Linux` 仓库中的协作规范、交付合同、Compose 控制面、台账同步和网站入口规则收敛成一个可触发、可复用的全局技能。

## 2. 范围

技能覆盖“应用层生命周期”而不是单次部署动作，范围包括：

- 应用项目首次接入 OP_Linux
- 应用项目的构建、打包、上传、部署计划、更新计划、验证、回滚计划
- 应用项目从旧控制面迁移到 OP_Linux 控制面
- 应用项目与 OP_Linux 的合同、inventory、摘要文档同步

本技能第一版唯一正式支持的应用类型：

- Docker / Compose 应用
- WSL 本地构建 + OP_Linux 正式托管

以下类型不纳入本技能第一版正式支持范围：

- 二进制发布型应用
- 静态站点 / 前端产物型应用

这两类仅保留未来扩展位，不在本技能第一版中提供正式合同形态、标准 CLI 路径或“可直接执行”的交付工作流。

## 3. 核心设计选择

### 3.1 单技能入口

采用单技能 `app-oplinux-delivery` 作为唯一入口，而不是拆成多个子技能。

原因：

- 新应用项目 agent 的触发门槛最低
- 用户只需要记住一个技能名
- 最符合“后续新增应用时，把这份指引交给 agent 即可”的使用目标

### 3.2 内部分层

虽然对外只有一个技能入口，但内部使用“轻量 SKILL.md + references 分层”的结构，避免单文件过长。

结构设计：

```text
app-oplinux-delivery/
├── SKILL.md
└── references/
    ├── trigger-rules.md
    ├── source-of-truth-map.md
    ├── execution-boundaries.md
    ├── repo-discovery.md
    └── sub2api-example.md
```

references 不复制现有 OP_Linux 规范，而只承载技能自己独有的补充信息：

- 何时触发 / 何时不触发
- 真源边界映射
- 当前 CLI 可执行能力与不可执行能力
- sibling 仓库发现与初始化引导
- `sub2api` 正式样板

### 3.3 样板驱动

`sub2api` 作为首个正式样板，但技能正文不写死 `sub2api` 细节。

通用规则放在主技能与 references 中，`sub2api` 只作为“正式 Docker / Compose 样板案例”收录到 `references/sub2api-example.md`。

## 4. 非目标

以下内容不纳入本技能第一版：

- 替代 OP_Linux 现有 CLI 的新执行框架
- 为二进制发布和静态站点定义完整通用合同
- 为所有应用类型一次性写完完整自动部署脚本
- 管理 1Panel 的全部底层 API 细节
- 管理基础设施服务本身的安装、升级或故障排查

这些内容继续留在 OP_Linux 自己的专项技能或 runbook 中。

## 5. 技能职责

技能必须回答四个问题：

1. 应用仓库 agent 该做什么
2. 应用仓库 agent 不能做什么
3. 应用仓库如何通过 OP_Linux 发起标准交付
4. 应用仓库如何在变更后保持和 OP_Linux 台账一致

对应职责如下：

- 识别当前任务是否属于“应用仓库与 OP_Linux 协作交付”
- 要求应用仓库提供 `deploy/op/contract.yaml`
- 要求应用仓库提供可复现构建入口和非敏感 env 模板
- 把正式部署动作收口到 `uv run python -m ops.cli app ...`
- 强制要求部署后的 inventory 和应用摘要同步

## 6. 硬规则

技能中必须明确写入以下不可协商规则：

- 应用仓库不保存正式 production secrets
- 应用仓库不保存正式 SSH 真源
- 应用仓库不保存正式 inventory 真源
- 应用仓库不保存正式 deploy / rollback 控制面真源
- 正式部署动作统一通过 OP_Linux 发起
- 没有明确用户批准时，应用仓库 agent 只能生成部署计划，不得直接执行正式切换
- 容器名、依赖容器名、数据目录、正式入口属于交付合同的一部分
- `zqf_network` 内服务间通讯使用稳定容器名，不使用临时 IP
- 部署变化完成后，必须同步 OP_Linux inventory 和应用仓库摘要文档

## 7. 技能触发条件

技能 description 应覆盖这些高频正向触发场景：

- 新增应用项目接入 OP_Linux
- 从应用仓库发起构建、上传、部署计划、更新计划、回滚计划
- 清理应用仓库中的旧生产控制面材料
- 将 legacy / systemd 控制面迁移到 OP_Linux 托管 Compose 控制面
- 检查应用合同、Compose 模板、inventory、应用摘要是否一致

技能必须包含最小激活信号：

- 当前任务明确涉及应用仓库
- 当前任务明确涉及 `deploy/op/contract.yaml`、应用构建、应用交付、应用迁移、应用回滚中的至少一项
- 当前任务要求应用仓库与 OP_Linux 协作，而不是单独处理基础设施

技能必须包含明确的不触发条件：

- 纯 OP_Linux 基础设施治理任务
- 纯 1Panel / OpenResty / 证书 / 网站对象维护任务
- PostgreSQL、Redis、MinIO、Docker 宿主机等基础设施服务安装升级任务
- 与应用仓库无关的远端主机治理任务

## 8. 仓库发现与接入前提

技能必须先判断当前环境是否满足 sibling 仓库拓扑：

- 应用仓库与 OP_Linux 位于同级目录，或用户明确提供 OP_Linux 仓库路径
- 应用仓库中存在 `deploy/op/contract.yaml`，或当前任务明确是“初始化接入”
- OP_Linux 中存在 `ops.cli app` 和对应 inventory

若不满足这些前提，技能必须进入“初始化引导”而不是假装可以直接部署。

需要显式区分三种状态：

1. 已接入：已有合同、已有 OP_Linux 路径、可校验
2. 待初始化：尚无合同或缺少模板，但项目目标是接入 OP_Linux
3. 不适用：不是应用交付任务，或当前项目不走 OP_Linux 模式

## 9. 合同版本策略

技能必须要求交付合同具备版本字段：

```yaml
schema_version: 1
```

版本策略：

- `schema_version: 1` 仅定义 Docker / Compose 应用的正式合同
- 没有 `schema_version` 的老合同视为 legacy，仅允许按现有 Docker / Compose 口径兼容
- 二进制发布和静态站点若未来纳入本技能，必须通过新版本 schema 扩展，而不是在 v1 中塞入非兼容字段

## 10. 通用工作流

技能主流程固定为以下十步：

1. 识别当前任务是否属于本技能适用范围
2. 识别应用是否已接入 OP_Linux
3. 检查是否已有 `deploy/op/contract.yaml`
4. 校验构建入口、Dockerfile 和非敏感 env 模板
5. 通过 OP_Linux 校验合同
6. 在 WSL 构建交付物
7. 通过 OP_Linux 上传交付物到目标主机
8. 通过 OP_Linux 渲染运行时并生成部署计划
9. 验证 origin / public 健康状态
10. 刷新 inventory 与应用摘要

技能必须在流程中反复强调：

- 应用仓库可以“发起请求”和“准备交付物”
- 正式部署必须由 OP_Linux 执行
- 在当前 OP_Linux 能力边界内，`deploy` / `rollback` 默认解释为“生成计划并要求人工复核”，不是“立即切换”

## 11. 自动化执行边界

技能实现时必须显式写明：

- `validate-contract`、`build-artifact`、`ship-image`、`render-runtime`、`inventory-refresh`、`doc-sync` 可以直接执行
- `deploy`、`rollback` 在当前版本中默认只生成计划
- 只有用户明确授权、且控制面能力允许时，才可以从计划进入真实切换
- 若当前 CLI 只支持 `--dry-run`，技能必须忠实反映这个边界，不能在技能里伪造“已经支持自动切换”

## 12. 应用类型矩阵

### 12.1 Docker / Compose 应用

第一版唯一正式主路径。

要求：

- 交付物为镜像
- 正式运行面为 OP_Linux 托管 Compose
- 数据目录挂载到 `/data/<app>/...`
- 正式入口由 1Panel 网站对象 + OpenResty 承担

### 12.2 二进制发布应用

第一版不支持，技能必须直接说明“不走本技能正式路径”，并建议：

- 先在 OP_Linux 文档或专项技能中定义单独控制面
- 或先迁移到 Docker / Compose，再回到本技能主路径

### 12.3 静态站点 / 前端产物应用

第一版不支持，技能必须直接说明“不走本技能正式路径”，并建议：

- 先在 OP_Linux 中定义静态站点专用交付模式
- 或等待后续 schema 版本扩展

## 13. 技能与现有资产的映射

该技能不应重新发明一套新流程，而是显式复用当前已有资产：

- `docs/architecture/op-linux-app-collaboration.md`
- `docs/runbooks/app-project-delivery-workflow.md`
- `ops/cli/apps.py`
- `infra/compose/sub2api/*`
- `deploy/op/contract.yaml`
- `docs/OP_LINUX_DEPLOYMENT.md`

技能要指导 agent 读取这些资产，而不是在技能正文中重复所有细节。

## 14. 验证策略

在技能实现后，至少做以下验证：

1. 让 agent 在一个新的 Docker / Compose 应用场景下识别它应使用此技能
2. 让 agent 在 `sub2api` 场景下正确判断：
   - 应用仓库能做什么
   - 必须通过 OP_Linux 做什么
3. 让 agent 能给出一次标准 Docker / Compose 交付流程
4. 让 agent 能指出应用仓库中哪些生产材料不应该保留
5. 让 agent 能要求同步 inventory 与应用摘要
6. 当任务是纯 1Panel / OpenResty / 证书治理时，技能不应触发
7. 当任务没有应用合同、没有 sibling OP_Linux 仓库、或根本不是 OP_Linux 协作场景时，技能应进入初始化 / 退出分支，而不是伪造可执行流程
8. 用一个非 `sub2api` 的 Docker / Compose 样本或合成 fixture 做正向验证，避免只对 `sub2api` 过拟合

## 15. 实施顺序

1. 创建全局技能目录 `app-oplinux-delivery`
2. 编写 `SKILL.md`
3. 补齐 `references/*`
4. 让 `SKILL.md` 明确 v1 仅支持 Docker / Compose
5. 用 `sub2api` 做正向验证
6. 用一个非 `sub2api` 的 Docker / Compose 样本做正向验证
7. 用基础设施任务和非接入项目做负向验证
8. 根据验证结果收紧触发条件和硬规则

## 16. 决策结论

采用单技能 `app-oplinux-delivery`，以“应用层完整生命周期”作为范围边界，但第一版只正式支持 Docker / Compose 应用。技能内部通过 references 分层，重点定义触发边界、真源映射、执行边界和仓库发现规则，并以 `sub2api` 作为正式样板案例。
