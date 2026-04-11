# 应用项目接入 AgentPlane 工作流

## 1. 适用对象

本 runbook 面向两类执行者：

- 应用仓库 agent：负责业务代码、构建资产、非敏感 env 模板与 `deploy/agentplane/contract.yaml`
- AgentPlane agent：负责正式计划、正式切换、现场验证、投影回写与文档同步

当前边界：

- 仅正式支持 Docker / Compose 应用
- 当前正式合同口径是 `schema_version: 1`
- internal worker 可以不走公网入口，但必须提供本机探针端口与健康检查路径
- 构建模板与接入清单都收口到本文和 [Docker 应用宿主机构建模板](./docker-host-runtime-packaging-template.md)，不再拆成第二控制面文档
- onboarding/offboarding 的标准、边界与“add/remove 必走闭环”约束只在 reference 页面定义：见 [应用仓库统一接入规范](../reference/app-repository-standard.md)（本文只给 active workflow）

## 2. 对象域 / 任务域 / 投影链

| 分层 | 真源或入口 | 说明 |
| --- | --- | --- |
| 对象域 | 应用仓库中的 `deploy/agentplane/contract.yaml`、构建脚本、runtime Dockerfile、非敏感 env 模板，加上 AgentPlane 中 `inventory/apps/catalog.json` 的 `target + app` 映射 | 描述稳定对象边界，如 `app_id`、镜像名、容器名、依赖容器、挂载、入口需求、回滚入口，以及正式对象引用。 |
| 任务域 | `uv run python -m agentplane.cli app delivery <validate-contract|build-artifact|ship-image|render-runtime|deploy|rollback|verify|inventory-refresh|doc-sync> ...` | 正式交付动作统一从 AgentPlane CLI 发起；应用仓库不维护第二套 deploy / rollback 脚本。 |
| 投影链 | `live state -> tmp/operation-ledger/*.jsonl -> inventory/servers/<target>/inventory.json -> README / app summary` | `ledger` 是机器证据，`inventory` 是结构化投影，`doc-sync` 是人类可读摘要；人类文档不反向充当真源。 |

要点：

- `plan/apply/verify/ledger/inventory/doc-sync` 是正式闭环，不再由模板文档或 checklist 单独承载。
- `app delivery validate-contract` 是 contract-first 的单一正式门禁；完整门禁规则只在本文“步骤 1：合同校验”定义。
- `app object` 用于检索、核验和刷新应用对象台账；`app delivery` 用于正式交付。
- 当前 `app` 域没有独立的 `ledger` 子命令；机器 ledger 由 `app` CLI 动作自动写入 `tmp/operation-ledger/*.jsonl`。
- `inventory` 与 `doc-sync` 都是投影，不是现场状态本身；最终以 live state 为准。
- secrets 写法也遵循 host-first contract：真实值来自 `secrets/hosts/<target>/...`；交付阶段读取或生成的 `secrets/services/<app>.<target-scope>.env` 等文件只作为 runtime projection 或 compatibility file，不反向充当真源。

### 2.1 Automation / Projection 职责引用

`app delivery` 只负责交付动作与交付闭环内的调用顺序。
`automation` 与 `projection` 的职责边界统一以 [automation-stack.md](../architecture/automation-stack.md) 为准；本文不再定义第二套职责语义。

## 3. 前置条件

- 应用仓库与 `AgentPlane` 位于同级目录，例如：
  - `/root/work/AgentPlane`
  - `/root/work/sub2api`
- 若应用仓库使用 Git worktree，默认工作区根目录为 `<app_repo>/.worktrees/`，且应用仓库 `.gitignore` 已忽略 `.worktrees/`
- 应用仓库已具备可复现的 WSL 宿主机预编译与 runtime image 打包命令
- AgentPlane 已维护目标环境 inventory、SSH、基础设施与 `1Panel` 接入能力

## 4. 应用仓库接入清单

以下清单是 active 接入真源，已吸收旧 `docker-app-onboarding-checklist.md` 的内容。

### 4.1 项目定位

- [ ] 已确认项目是 Docker / Compose 应用，而不是基础设施服务或 `1Panel` 应用市场应用
- [ ] 已确认应用仓库与 `AgentPlane` 位于同级 WSL 路径
- [ ] 已明确正式容器名、监听端口、健康检查路径、数据目录、依赖容器名
- [ ] 已明确公网网站对象 / 域名，或确认 `ingress.mode=internal`
- [ ] 已准备非敏感 env 模板

### 4.2 构建资产

- [ ] 已创建 `deploy/build-runtime-artifacts.sh`
- [ ] 已创建 `deploy/package-runtime-image.sh`
- [ ] 已创建 `deploy/Dockerfile.runtime`
- [ ] 已确认 `deploy/docker-entrypoint.sh` 或等效 runtime 启动脚本存在
- [ ] 已约定统一制品目录，例如 `dist/oplinux/`
- [ ] 已在 `.dockerignore` 中为 `dist/oplinux/` 留出白名单
- [ ] 宿主机构建脚本能在 WSL 中重复执行，并直接复用本机缓存
- [ ] fallback 资源、静态资源和其他 runtime 必需文件都已复制到制品目录
- [ ] runtime Dockerfile 不再执行源码编译，只复制制品目录与必要脚本
- [ ] `IMAGE_NAME` / `IMAGE_TAG` 可通过环境变量覆盖
- [ ] `IMAGE_TAG=test bash deploy/package-runtime-image.sh` 能成功产出镜像

### 4.3 合同与交接

- [ ] 已创建或更新 `deploy/agentplane/contract.yaml`
- [ ] 新合同已填写 `schema_version: 1`
- [ ] `artifact.build_command` 已指向 `bash deploy/package-runtime-image.sh`
- [ ] `artifact.image_name` 与正式容器命名规则一致
- [ ] `runtime.container_name` 使用稳定 `-prod` 命名
- [ ] `infra.depends_on_containers` 与 AgentPlane inventory 一致
- [ ] `data.mounts` 已收口到 `/data/<app>/...`
- [ ] 已为应用仓库准备 target-aware 摘要文件占位，例如 `docs/AGENTPLANE_DEPLOYMENT.prod0-main.md` 与 `docs/AGENTPLANE_DEPLOYMENT.wsl.md`
- [ ] 如需隔离开发或并行改动，优先在应用仓库内使用 `.worktrees/<branch>/`
- [ ] 已先执行并通过 `uv run python -m agentplane.cli app delivery validate-contract --target <target> --app <app> ...`；这是应用接入不变量的最早正式门禁，未通过前不进入 `build-artifact`、`ship-image`、`render-runtime`、`deploy`、`rollback` 或 `verify`

### 4.4 最小本地验证

先过合同门禁，再做任何正式交付预演；不要把合同问题留到部署阶段才发现。

- [ ] 本仓库测试已按改动范围完成
- [ ] `uv run python -m agentplane.cli app delivery validate-contract --target <target> --app <app> ...` 通过
- [ ] `bash deploy/build-runtime-artifacts.sh` 成功
- [ ] `docker image inspect <image-name>:test >/dev/null` 成功
- [ ] `uv run python -m agentplane.cli app delivery build-artifact --target <target> --app <app> ... --dry-run` 输出正确的脚本型 `build_command`
- [ ] `uv run python -m agentplane.cli app delivery render-runtime --target <target> --app <app> ...` 输出的 Compose 满足正式容器、端口与网络规则

### 4.5 新 target 首次纳管补充项

- [ ] 在 `inventory/servers/<target>/inventory.json` 中声明 `managed_bridge_networks`
- [ ] 明确每个受管 bridge 网络的 `name`、`driver`、`subnet`、`gateway_ip` 与 `required_for`
- [ ] 首次上线前显式执行：

```bash
uv run python -m agentplane.cli host network audit <target> --repo-root /root/work/AgentPlane
uv run python -m agentplane.cli host network ensure <target> --repo-root /root/work/AgentPlane
```

原因：

- 仅声明“业务容器附着到 `zqf_network`”并不能保证宿主机仍能通过该 bridge 访问容器
- 一旦 bridge 网卡丢失 gateway IP 或路由，`127.0.0.1:<host_port> -> container:<port>` 会失效，公网入口通常会跟着故障

### 4.6 第二个应用接入前的预检

这一步的目标不是补充第二套流程，而是把 `Sub2API` 这次真正暴露出的返工点提前挡掉。接入第二个应用前，至少先核对以下 3 项：

- `--app-repo-root` 只用于临时 worktree 验证；如果你在应用 worktree 中修改合同或摘要，预检阶段可以显式覆盖，但最终验收必须回到 catalog 指向的正式仓库根。
- `deploy/agentplane/contract*.yaml`、`docs/AGENTPLANE_DEPLOYMENT.*.md`、`inventory/servers/<target>/...` 与 `secrets/hosts/<target>/...` 必须在同一轮变更里收口；不要只改 inventory 或只改 app summary，再把漂移留到 `verify` 阶段。
- 退役旧控制面时，不只删脚本和文案，还要删除 `secrets/app-resources/<target>/<app>/*.env` 实体旧文件，并用 repo self-check 或等效测试把它冻住。

## 5. AgentPlane Agent 标准执行流

### 步骤 1：合同校验

```bash
uv run python -m agentplane.cli app delivery validate-contract \
  --target prod0-main \
  --app sub2api \
  --repo-root /root/work/AgentPlane
```

这是应用接入不变量的最早正式门禁。任何 `build-artifact`、`ship-image`、`render-runtime`、`deploy`、`rollback`、`verify` 之前，都必须先通过这里。合同问题必须在这一步暴露，不允许等到 `deploy --dry-run`、`deploy --execute` 或 `verify --execute` 才发现。

校验目标：

- 合同字段完整
- 依赖容器名存在于 AgentPlane inventory
- 命名校验遵循 [AgentPlane 与应用层项目协作规范](../architecture/agentplane-app-collaboration.md) 第 7 节
- 持久化目录收口到 `/data/`
- 若 `ingress.mode=internal`，允许 `public_sites` 为空；验证阶段只检查容器与本机探针

### 步骤 2：在 WSL 构建交付物

```bash
uv run python -m agentplane.cli app delivery build-artifact \
  --target prod0-main \
  --app sub2api \
  --repo-root /root/work/AgentPlane \
  --image-tag <tag>
```

要求：

- 构建必须在 WSL 中可重复执行
- 镜像 tag 必须遵循 `<upstream>-zzz.<yyyymmdd>.v<n>.g<gitsha>`
- 若不想人工决定 tag，优先使用 `uv run python -m agentplane.cli app delivery build-artifact --auto-version ...`
- 不把真实 secrets 烘焙进镜像
- Python 依赖与命令入口优先使用 `uv`；Node.js 依赖与脚本入口优先使用 `pnpm`
- Docker 类项目默认推荐“两段式”构建：先在宿主机构建 runtime artifacts，再用 runtime-only Dockerfile 打包镜像
- `artifact.build_command` 应优先调用应用仓库脚本，例如 `bash deploy/package-runtime-image.sh`
- 不推荐把前端依赖安装、前端构建、Go 依赖下载和 Go 编译全部塞进正式 Docker build 主路径
- 如果 WSL 通过 Windows 侧 Clash/Mihomo 出网，Docker build 仍需显式传递代理参数
- 如果应用依赖 runtime fallback 资源文件，镜像必须显式复制这些资源

### 步骤 3：上传镜像到正式机

```bash
uv run python -m agentplane.cli app delivery ship-image \
  --target prod0-main \
  --app sub2api \
  --repo-root /root/work/AgentPlane \
  --image-ref sub2api-prod:<tag>
```

当前标准链路：

1. 本地 `docker save`
2. 通过 AgentPlane 管理的 SSH 入口上传
3. 远端 `docker load`

### 步骤 4：渲染正式运行时

```bash
uv run python -m agentplane.cli app delivery render-runtime \
  --target prod0-main \
  --app sub2api \
  --repo-root /root/work/AgentPlane \
  --image-ref sub2api-prod:<tag>
```

检查点：

- 生产 Compose 使用稳定容器名
- 绑定宿主机回环端口，例如 `127.0.0.1:18080:8080`
- 附着 `zqf_network`
- 依赖容器名与合同一致

### 步骤 5：准备网站入口

正式入口由 AgentPlane 负责，不在应用仓库内执行。

最小动作：

1. 在 `1Panel` 确认网站对象已存在
2. 网站对象的反代目标指向宿主机回环绑定
3. 证书与域名状态正常

`sub2api` 示例：

- 网站对象：`token`
- 域名：`token.zzzai.cloud`
- 入口：`https://token.zzzai.cloud:8443`
- 回环目标：`http://127.0.0.1:18080`

### 步骤 6：正式闭环

步骤 6 只处理已通过步骤 1 的应用；`deploy --dry-run` 是部署计划入口，不是合同校验入口。
rollback-state 的语义定义（何时创建、何时切流、何时删除旧运行态）统一以 [AgentPlane 与应用层项目协作规范](../architecture/agentplane-app-collaboration.md) 第 8.3 节为准；本节只承接执行顺序。

| 阶段 | 正式入口 | 说明 |
| --- | --- | --- |
| Plan | `uv run python -m agentplane.cli app delivery deploy --target <target> --app <app> ... --dry-run`；`uv run python -m agentplane.cli app delivery rollback --target <target> --app <app> ... --dry-run` | 先生成计划，再做人工复核；`--dry-run` 与 `--execute` 互斥。 |
| Apply | `uv run python -m agentplane.cli app delivery deploy --target <target> --app <app> ... --execute`；必要时 `rollback ... --execute` | 当前 `deploy` / `rollback` 都是 plan-first；真实切换必须显式追加 `--execute`。 |
| Verify | `uv run python -m agentplane.cli app delivery verify --target <target> --app <app> ... --execute` | 现场验证容器、探针、公开入口、依赖容器与网络状态。 |
| Ledger | `app` CLI 动作自动写入 `tmp/operation-ledger/*.jsonl` | 这是机器 ledger，不是人类 runbook；`build-artifact` 的版本序列也依赖该 ledger。 |
| Inventory | `uv run python -m agentplane.cli app delivery inventory-refresh --target <target> --app <app> ... --write` | 把现场状态收口到 `inventory/servers/<target>/inventory.json`；projection 侧职责边界见 `automation-stack.md`。 |
| Doc-sync | `uv run python -m agentplane.cli app delivery doc-sync --target <target> --app <app> ... --write` | 把非敏感摘要回写到 AgentPlane README 与应用仓库摘要文件。 |

推荐切换顺序：

1. 预渲染 Compose 与 env
2. 生成 `deploy --dry-run` 计划并复核
3. 确认旧控制面可回滚
4. 执行 `deploy --execute`
5. 立即执行 `verify --execute`
6. 刷新 `inventory`
7. 执行 `doc-sync`
8. 如失败，生成并执行 `rollback`

生产环境的 `app delivery deploy --execute` 与 `app delivery verify --execute` 会在切换前自动执行 `agentplane.cli host network ensure`。上线是否安全，不能只看“容器在跑”或“容器已挂载 `zqf_network`”；还必须确认宿主 bridge 口仍持有声明的 gateway IP 与路由。

### 步骤 7：常用正式命令

```bash
uv run python -m agentplane.cli app delivery deploy \
  --target prod0-main \
  --app sub2api \
  --repo-root /root/work/AgentPlane \
  --image-ref sub2api-prod:<tag> \
  --dry-run

uv run python -m agentplane.cli app delivery deploy \
  --target prod0-main \
  --app sub2api \
  --repo-root /root/work/AgentPlane \
  --image-ref sub2api-prod:<tag> \
  --execute

uv run python -m agentplane.cli app delivery verify \
  --target prod0-main \
  --app sub2api \
  --repo-root /root/work/AgentPlane \
  --execute

uv run python -m agentplane.cli app delivery inventory-refresh \
  --target prod0-main \
  --app sub2api \
  --repo-root /root/work/AgentPlane \
  --write

uv run python -m agentplane.cli app delivery doc-sync \
  --target prod0-main \
  --app sub2api \
  --repo-root /root/work/AgentPlane \
  --write
```

## 6. 容器命名变更引用

容器命名规则与改名步骤属于长期合同，唯一完整定义见 [AgentPlane 与应用层项目协作规范](../architecture/agentplane-app-collaboration.md) 第 7 节。
本 runbook 只要求在执行步骤前完成该节规定的同步项与验证项，不再重复展开规则正文。

## 7. 项目下线（Offboarding）标准执行流

本节定义“active workflow”，不新增第二入口。项目下线不是“删容器”这么简单，而是把受管对象从控制面中按生命周期闭环撤出，避免留下 catalog、台账、投影和文档的残留引用。

下线的最小闭环要求（同一次变更内完成，不允许开环）：

| 主题 | 最小动作 | 最小证据 |
| --- | --- | --- |
| catalog | 从 `inventory/apps/catalog.json` 移除 `target + app` 的正式映射 | `agentplane.cli app object search` 不再列出该 `target + app` |
| website / ingress | 撤销公网入口或确保入口不再指向该应用回环绑定；必要时通过 `agentplane.cli website publish ...` 生成并执行入口发布变更 | `agentplane.cli website verify` 或 `agentplane.cli website publish verify` 与现场一致 |
| service | 先确保服务不再承载正式流量与关键任务，再执行服务退役（统一走 `agentplane.cli service plan/apply`） | `agentplane.cli service verify` 与现场一致 |
| app delivery | 如需要回到上一控制面，先 `rollback`；如是完全退役，确保容器与依赖关系不再作为受管对象残留 | `agentplane.cli app delivery verify` 对应退出策略通过（例如回到旧控制面可用） |
| projection | 刷新派生任务台账，避免旧派生物继续影响 inventory 与验证 | `agentplane.cli projection ledger refresh` 完成 |
| inventory | 刷新结构化投影 | `agentplane.cli app delivery inventory-refresh --write` 后 inventory 不再包含该项目残影 |
| docs | 同步人类可读摘要 | `agentplane.cli app delivery doc-sync --write` 后摘要不再宣称仍受管 |

推荐执行顺序（plan-first）：

1. 先冻结发布窗口，明确下线策略：回到上一控制面（`rollback`）还是完全退役。
2. 如涉及公网入口变更：先 `plan`，人工复核后再 `apply --execute`，最后 `verify`。
3. 如涉及服务对象变更：先 `uv run python -m agentplane.cli service plan --target <target> --name <service> --operation <operation> ...`，复核后再 `service apply ... --execute`，最后 `service verify ...`。
4. 如需要回到上一控制面：先 `uv run python -m agentplane.cli app delivery rollback ... --dry-run`，复核后再 `rollback ... --execute`，并执行 `app delivery verify ... --execute`。
5. 更新 `inventory/apps/catalog.json`，移除该项目映射。
6. 刷新台账与投影证据（建议按影响域最小刷新）：
   - `uv run python -m agentplane.cli app object refresh-ledger --target <target> --repo-root /root/work/AgentPlane`
   - `uv run python -m agentplane.cli app resource refresh-ledger --target <target> --repo-root /root/work/AgentPlane`
   - `uv run python -m agentplane.cli website refresh-ledger --target <target> --repo-root /root/work/AgentPlane`
   - `uv run python -m agentplane.cli projection ledger refresh --repo-root /root/work/AgentPlane`
7. 以 “投影优先于人类文档” 的顺序完成收口：
   - `uv run python -m agentplane.cli app delivery inventory-refresh --target <target> --app <app> --repo-root /root/work/AgentPlane --write`
   - `uv run python -m agentplane.cli app delivery doc-sync --target <target> --app <app> --repo-root /root/work/AgentPlane --write`

注意：

- 下线不等于删除数据目录；数据保留/清理必须有额外审批与证据，不在本 runbook 的默认动作里。
- 下线涉及 secrets 退役时，遵循 host-first secrets 路径与 `host secrets` 入口，不在应用仓库或人类文档里手工维护另一套真源。

## 8. Sub2API 样板

`sub2api` 是当前正式样板，其目标状态如下：

- 应用合同：`/root/work/sub2api/deploy/agentplane/contract.yaml`
- AgentPlane Compose 模板：`infra/compose/sub2api/docker-compose.prod0.yml`
- 正式容器名：`sub2api-prod`
- 依赖容器：`postgres18-prod`、`redis7-prod`
- 数据目录：`/data/sub2api/data`
- 正式入口：`https://token.zzzai.cloud:8443`
- 回退入口：无独立旧控制面

## 9. 完成定义（Onboarding）

只有以下条件同时满足，才算真正接入完成：

- 应用仓库不再保存正式私有资产
- 应用仓库已采用统一模板结构与 `schema_version: 1` 合同
- 正式部署动作统一从 AgentPlane 发起
- `plan/apply/verify/ledger/inventory/doc-sync` 闭环能顺序跑通
- 应用接入不变量已在 `validate-contract` 阶段收口，不会等到 `deploy` / `verify` 阶段才暴露合同问题
- 正式 inventory 可从 AgentPlane 查到完整状态
- 应用仓库能看到最新非敏感部署摘要
- 回滚入口清晰且已记录


