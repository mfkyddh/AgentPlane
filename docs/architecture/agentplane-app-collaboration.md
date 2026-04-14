# AgentPlane 与应用层项目协作规范

## 1. 目的

本规范定义 `AgentPlane` 与应用层项目的长期边界、真源划分、交付合同和变更流程。目标是把正式生产控制面统一收口到 `AgentPlane`，让应用仓库只保留业务代码、构建资产、Docker 资产和非敏感交付合同。

适用范围：

- 与 `AgentPlane` 同级目录下的业务应用仓库
- 使用 `1Panel`、`OpenResty`、`Docker`、`PostgreSQL`、`Redis`、`MinIO` 等基础设施的项目
- 当前正式样板：`sub2api`
- 当前正式 schema：仅 `schema_version: 2`，且只覆盖 Docker / Compose 应用

## 2. 核心原则

- `AgentPlane` 是正式生产控制面的唯一真源。
- 应用仓库不保存生产 secrets、SSH 密钥、Cloudflare 私有材料、正式 inventory、正式回滚脚本。
- 应用仓库必须提供可复现的构建入口、Docker 资产、非敏感 env 模板，以及 `deploy/agentplane/contract.yaml`。
- 正式部署优先采用 `WSL 宿主机预编译 + runtime 镜像打包 + AgentPlane 托管切换`。
- Python 类应用或工具链优先使用 `uv` 管理依赖与执行命令；Node.js 类应用优先使用 `pnpm` 管理依赖与执行脚本。
- 正式 Docker 容器统一接入 `zqf_network`。
- `zqf_network` 内的服务通讯统一使用稳定容器名，不使用 `127.0.0.1` 访问容器依赖。
- 生产容器名一旦进入合同和 inventory，就视为接口，不再是可随意调整的实现细节。
- AgentPlane 管理的应用仓库默认把 Git worktree 放在仓库内 `.worktrees/`；应用仓库必须在 `.gitignore` 中忽略 `.worktrees/`，除非该仓库已有明确文档声明其他位置。

### 2.1 Git 远程治理

- 新项目没有官方上游时，只保留 `origin`。
- 开源二开项目中，`origin` 指向你自己的可写仓库，`upstream` 指向官方只读源。
- 同步官方更新时，固定从 `origin/main` 切 `sync/upstream-YYYYMMDD`，先 merge，再验证，再合回主线。
- 已发布主线不通过反复 rebase 官方分支来保持同步。

## 3. 职责边界

### 3.1 AgentPlane 负责

- 管理 Linux 主机、SSH 连接、IP/域名/别名映射、密钥和生产 secrets。
- 管理 `1Panel`、`OpenResty`、`Docker`、`PostgreSQL`、`Redis`、`MinIO` 等基础设施。
- 管理正式部署、发布切换、网站入口、回滚、inventory、服务器摘要和跨仓库文档回写。
- 维护通用命令入口：`uv run python -m agentplane.cli ...`
- 维护正式 inventory：`inventory/servers/<target>/inventory.json`

### 3.2 应用层项目负责

- 业务代码、测试、Dockerfile、镜像构建脚本、非敏感 env 模板。
- `deploy/agentplane/contract.yaml`
- 对外说明自己的运行需求、依赖容器、监听端口、健康检查、数据挂载、网站对象需求。
- 在 AgentPlane 的规范下构建交付物，不直接持有正式生产控制面。
- 需要隔离开发时，优先使用仓库内 `.worktrees/<branch>/` 作为默认工作区根目录。

### 3.3 应用仓库通用结构

应用仓库默认推荐以下稳定目录：

- `src/` 或按语言拆分的源码目录
- `tests/`
- `deploy/`
- `docs/`
- `dist/oplinux/`
- `tmp/`
- `.worktrees/`

其中：

- `deploy/` 负责 runtime 构建资产与 `deploy/agentplane/contract.yaml`
- `scripts/` 只允许放本地开发辅助脚本，不承担正式部署与正式回滚
- `dist/oplinux/` 是正式制品唯一打包入口

### 3.4 第二控制面禁令

- 不要在应用仓库保留 `deploy-prod.sh`、`rollback-prod.sh`、`publish-website.sh`、`issue-cert.sh`、`sync-inventory.sh` 这类正式控制面脚本。
- 应用仓库负责“怎么把自己打包好”；`AgentPlane` 负责“怎么把它正式上线并纳管”。

### 3.5 生命周期边界（Onboarding / Offboarding）

应用项目的生命周期动作必须是“对象域 + 投影链”的闭环，而不是临时手工操作或只改现场不改真源。

硬边界：

- 唯一正式入口固定为 `uv run python -m agentplane.cli ...`，不允许在应用仓库或人类文档里形成第二入口。
- Add/Remove 都必须同时覆盖：`catalog`、`app`、`app resource`、`service`、`website`、`projection`、`inventory`、`docs`。
- `inventory` 和 `docs` 永远是投影；任何“只改 README/摘要”但不改对象域的动作都不算生命周期完成。

Add（Onboarding）最小闭环语义：

- 通过 `inventory/apps/catalog.json` 建立 `target + app` 映射，使其进入 formal 对象域。
- `agentplane.cli app delivery validate-contract` 通过后，才允许进入交付与切换（执行细节见 active workflow）。
- 发布与验证完成后，必须把证据写入 operation ledger，并按顺序刷新 `inventory` 与 `doc-sync`。

Remove（Offboarding）最小闭环语义：

- 先撤销或下线公网入口与受管服务的关键承载，再处理应用交付面的退出策略（例如回到上一控制面）。
- 从 `inventory/apps/catalog.json` 移除映射，确保后续 workflow 不再继续把它当成受管对象。
- 刷新相关台账与投影，避免残留引用继续污染 `inventory` 与摘要文档。

标准与执行入口分工：

- 标准（边界、必走闭环、对象域清单）：见 [应用仓库统一接入规范](../reference/app-repository-standard.md)。
- 执行步骤（active workflow）：见 [应用项目接入 AgentPlane 工作流](../runbooks/app-project-delivery-workflow.md)。

### 3.6 禁止事项

- 不要在应用仓库提交生产 SSH 配置、生产私钥、真实 env、正式 inventory。
- 不要在应用仓库维护“另一个正式部署 runbook”。
- 不要在应用仓库写死正式机密路径后继续把它当成权威流程。
- 不要在 `zqf_network` 中通过临时 IP 或宿主机回环地址访问依赖容器。

## 4. 真源划分

| 主题 | 真源仓库 | 真源文件/入口 | 应用仓库可见内容 |
| --- | --- | --- | --- |
| 服务器身份、SSH、密钥、secrets | AgentPlane | `secrets/`、`inventory/servers/*/inventory.json` | 只保留索引说明 |
| 正式基础设施状态 | AgentPlane | `inventory/servers/*/inventory.json` | 非敏感部署摘要 |
| 正式应用对象与交付执行 | AgentPlane | `uv run python -m agentplane.cli app object ...` / `uv run python -m agentplane.cli app delivery ...` | 只保留交付合同 |
| 1Panel 网站对象、OpenResty、证书 | AgentPlane | `agentplane.cli onepanel` 及相关 runbook | 只声明入口需求 |
| 应用构建产物定义 | 应用仓库 | `deploy/agentplane/contract.yaml`、Dockerfile、构建脚本 | 真源 |
| 应用业务代码与测试 | 应用仓库 | 源码与测试目录 | 真源 |

### 4.1 对象域 / 任务域 / 投影链

| 分层 | 典型内容 | 归属 |
| --- | --- | --- |
| 对象域 | 应用仓库中的 `deploy/agentplane/contract.yaml` 加上 AgentPlane 中 `inventory/apps/catalog.json` 的 `target + app` 映射 | 应用仓库负责合同，AgentPlane 负责正式对象引用 |
| 任务域 | `app delivery validate-contract`、`build-artifact`、`ship-image`、`render-runtime`、`deploy`、`rollback`、`verify`、`inventory-refresh`、`doc-sync` | AgentPlane CLI 负责执行 |
| 投影链 | `live state -> tmp/operation-ledger/*.jsonl -> inventory/servers/<target>/inventory.json -> README / app summary` | AgentPlane 负责回写与对账 |

约束：

- `app object` 回答“应用对象是什么”；`app delivery` 回答“正式要怎么交付”；投影链回答“现场结果如何沉淀”。
- 合同前置校验只有一个正式入口：`uv run python -m agentplane.cli app delivery validate-contract ...`；门禁执行细节统一见 [应用项目接入 AgentPlane 工作流](../runbooks/app-project-delivery-workflow.md) 的步骤 1。
- 模板文档与 runbook 可以解释输入骨架和流程，但不应复制出第二套正式控制面。
- `ledger` 在 `app` 域当前表现为自动写入的 operation ledger，而不是单独的人工维护命令。

## 5. 控制面选择矩阵

| 场景 | 推荐控制面 | 说明 |
| --- | --- | --- |
| 正式 Docker 化业务应用 | AgentPlane 托管 Docker Compose | 标准方案。应用仓库只交付镜像和合同。 |
| 正式网站入口 | 1Panel 网站对象 + OpenResty | 统一承载正式域名、证书和反代。 |
| 基础设施型容器 | AgentPlane 管理的 Compose 或 1Panel 应用 | 以主机治理为主，不属于应用仓库。 |
| 本地 WSL 开发验证 | WSL Docker Compose | 用于开发、联调、预打包。不是正式生产控制面。 |
| 紧急回退 | 上一已知良好控制面 | 回退入口必须在合同和 inventory 中可追溯。 |

`sub2api` 的正式口径：

- 构建：WSL 宿主机先构建 runtime artifacts，再打包 runtime image
- 正式运行：AgentPlane 托管 Compose
- 公网入口：`1Panel` 网站对象 `token` + `OpenResty`
- 应用容器名：`sub2api-prod`
- 依赖容器名：`postgres18-prod`、`redis7-prod`

新 Docker 项目请直接复用：

- [Docker 应用宿主机构建模板](../runbooks/docker-host-runtime-packaging-template.md)
- [应用项目接入 AgentPlane 工作流](../runbooks/app-project-delivery-workflow.md)
- [应用交付版本规范](../reference/app-delivery-versioning.md)

## 6. 应用项目交付合同

每个应用仓库必须提供 `deploy/agentplane/contract.yaml`。该文件只描述非敏感交付面，不保存生产 secrets。

最小字段：

```yaml
schema_version: 2
app_id: sub2api
artifact:
  build_command: bash deploy/build-runtime-artifacts.sh
  output_path: dist/oplinux
  runtime_os: linux
  runtime_arch: amd64
packaging:
  backend: wsl-linux
  image_name: sub2api-prod
  image_tag_rule: <upstream>-zzz.<yyyymmdd>.v<n>.g<gitsha>
  package_command: bash deploy/package-runtime-image.sh
runtime:
  kind: compose
  container_name: sub2api-prod
  container_port: 8080
  host_binding: 127.0.0.1:18080
  healthcheck:
    path: /health
    expected_status: 200
  env_template: deploy/agentplane/runtime.env.example
infra:
  depends_on_containers:
    - postgres18-prod
    - redis7-prod
ingress:
  public_sites:
    - alias: token
      domain: token.zzzai.cloud
      public_url: https://token.zzzai.cloud:8443
      website_object: token
data:
  mounts:
    - host_path: /data/sub2api/data
      container_path: /app/data
rollback:
  previous_control_plane:
    kind: none
docs:
  app_summary_file: docs/AGENTPLANE_DEPLOYMENT.prod0-main.md
inventory:
  service_key: sub2api
```

字段规则：

- `schema_version`：当前必须是 `2`。没有该字段或仍停在旧结构的合同视为 legacy，只做兼容读取，不再扩展新类型。
- `app_id`：仓库级唯一应用标识。
- `artifact.build_command`：WSL/backend 内可直接执行的构建命令，用于产出 runtime artifacts。
- `artifact.output_path`、`runtime_os`、`runtime_arch`：固定交付物边界。
- `packaging.image_name`：镜像名，通常与生产容器名同族。
- `packaging.package_command`：把已生成 artifacts 打包成 runtime image 的命令。
- `packaging.image_tag_rule`：当前正式规范固定为 `<upstream>-zzz.<yyyymmdd>.v<n>.g<gitsha>`，详见 [应用交付版本规范](../reference/app-delivery-versioning.md)。
- `runtime.container_name`：正式稳定容器名，必须以 `-prod` 结尾。
- `runtime.host_binding`：宿主机对外暴露到哪个回环或端口。
- `runtime.healthcheck.path`：供部署后健康检查使用。
- `runtime.env_template`：非敏感 env 模板路径。
- `infra.depends_on_containers`：正式依赖容器名列表，必须与 AgentPlane inventory 一致。
- `ingress.public_sites`：域名、公开入口、1Panel 网站对象名。
- `ingress.mode: internal`：适用于无公网入口的 worker；`public_sites` 可为空，验证时只做容器和本机探针检查。
- `data.mounts`：持久化挂载，宿主机路径必须收口到 `/data/<app>/...`
- `rollback.previous_control_plane`：上一控制面；如果已经没有旧控制面，显式写 `kind: none`。
- `docs.app_summary_files`：按 target 回写给应用仓库的非敏感摘要路径映射。
- `docs.app_summary_file`：不区分 target 时的单文件非敏感摘要回写路径。
- `inventory.service_key`：该应用写入 AgentPlane inventory 时的服务键名。

## 7. 容器命名治理

本节是正式容器命名与改名约束的唯一完整描述；其他 active 文档只做引用，不再重复展开。

### 7.1 稳定命名规则

- 正式应用容器统一使用 `<app>-prod`
- WSL 开发容器统一使用 `<app>-dev`
- 基础设施容器使用显式稳定名，例如 `postgres18-prod`、`redis7-prod`

### 7.2 命名变更规则

若必须变更生产容器名，必须按以下顺序执行：

1. 更新应用合同 `runtime.container_name` 或 `infra.depends_on_containers`
2. 更新 AgentPlane Compose 模板
3. 更新 AgentPlane inventory
4. 更新验证命令与文档
5. 完成一次显式变更评审，再执行切换

未完成以上同步前，不允许直接改容器名。

## 8. 标准工作流

### 8.1 应用仓库 agent 的输出

- 业务代码已通过本仓库测试
- 宿主机构建脚本、runtime Dockerfile 与构建命令可在 WSL 复现
- `deploy/agentplane/contract.yaml` 已填写
- 非敏感 env 模板已更新
- 如使用 Git worktree，默认工作区目录为仓库内 `.worktrees/`，且 `.gitignore` 已覆盖该目录
- 若变更了端口、网站对象、容器名、依赖容器或数据目录，必须同步更新合同

Docker 类应用的推荐正式路径：

1. 在 WSL 宿主机执行应用仓库脚本，生成 runtime artifacts
2. 用 runtime-only Dockerfile 打包镜像
3. 继续由 `AgentPlane` 完成 `ship-image`、`render-runtime`、`deploy/verify`

不推荐把前端依赖安装、前端构建、Go 依赖下载和 Go 编译全部塞进正式 Docker build 主路径。

### 8.2 AgentPlane agent 的执行顺序

1. `validate-contract`
2. `build-artifact`
3. `ship-image`
4. `render-runtime`
5. 创建或确认 1Panel 网站对象
6. `deploy --dry-run` 并人工复核
7. `deploy --execute`；如失败则生成并执行 `rollback`
8. `verify`
9. `inventory-refresh`
10. `doc-sync`

补充边界：

- 当前正式主路径只支持 Docker / Compose 应用。
- `deploy`、`verify`、`rollback` 默认仍是 plan-first；显式传 `--execute` 时才进入真实执行。
- `--dry-run` 与 `--execute` 互斥。
- 正式闭环固定为 `plan -> apply -> verify -> ledger -> inventory -> doc-sync`；其中 `ledger` 由 `app` CLI 自动写入 `tmp/operation-ledger/*.jsonl`。

### 8.3 发布与回滚态

本节是 rollback-state 行为的唯一完整描述；其他 active 文档仅引用本节并承接执行顺序。

- 发布前先创建回滚态。
- 回滚态是发布开始前最后一个已知良好、可直接重新接管正式流量的运行态。
- 新版本先做切流前验证，再切流；切流后立即做切流后验证。
- 新版本验证成功并经过最小观察窗口后，再删除旧容器。
- 若本次发布包含不可逆数据变更，必须额外定义数据回退能力，不能只靠旧容器假装可回滚。

## 9. 标准命令入口

所有正式动作都从 AgentPlane 执行，公开稳定输入统一是 `target + app`：

```bash
uv run python -m agentplane.cli app object search --target <target> --repo-root <repo-root>
uv run python -m agentplane.cli app object get --target <target> --app <app> --repo-root <repo-root>
uv run python -m agentplane.cli app delivery validate-contract --target <target> --app <app> --repo-root <repo-root>
uv run python -m agentplane.cli app delivery build-artifact --target <target> --app <app> --repo-root <repo-root> --image-tag <tag>
uv run python -m agentplane.cli app delivery ship-image --target <target> --app <app> --repo-root <repo-root> --image-ref <image:tag>
uv run python -m agentplane.cli app delivery render-runtime --target <target> --app <app> --repo-root <repo-root> --image-ref <image:tag>
uv run python -m agentplane.cli app delivery deploy --target <target> --app <app> --repo-root <repo-root> --image-ref <image:tag> --dry-run
uv run python -m agentplane.cli app delivery deploy --target <target> --app <app> --repo-root <repo-root> --image-ref <image:tag> --execute
uv run python -m agentplane.cli app delivery verify --target <target> --app <app> --repo-root <repo-root> --execute
uv run python -m agentplane.cli app delivery inventory-refresh --target <target> --app <app> --repo-root <repo-root> --write
uv run python -m agentplane.cli app delivery doc-sync --target <target> --app <app> --repo-root <repo-root> --write
```

## 10. 1Panel 与网站入口规则

- 正式公网域名必须先在 `1Panel` 中存在网站对象。
- 网站对象负责把公网请求转发到宿主机回环绑定，例如 `http://127.0.0.1:18080`。
- 证书、OpenResty、反向代理和公网监听属于 AgentPlane 基础设施职责。
- 应用仓库只在合同中声明：域名、公开 URL、网站对象名、目标回环绑定。

`sub2api` 样板：

- 网站对象：`token`
- 公网入口：`https://token.zzzai.cloud:8443`
- 回环绑定：`127.0.0.1:18080`
- 宿主机反代目标：`http://127.0.0.1:18080`

## 11. inventory 与文档同步

- AgentPlane inventory 是正式真实状态的结构化真源。
- `tmp/operation-ledger/*.jsonl` 是 app workflow 的机器 ledger 证据。
- 应用仓库只接收 AgentPlane 回写的非敏感摘要，例如 `docs/AGENTPLANE_DEPLOYMENT.prod0-main.md` 与 `docs/AGENTPLANE_DEPLOYMENT.wsl.md`。
- 应用仓库如果改动了部署合同，必须重新触发 `inventory-refresh` 和 `doc-sync`。
- AgentPlane 如果改动了应用正式入口、控制面或回滚口径，也必须回写应用摘要，避免双边文档漂移。

投影顺序固定为：

1. 现场 `deploy` / `verify` 写 operation ledger
2. `inventory-refresh` 刷新结构化投影
3. `doc-sync` 回写人类摘要

推荐同步顺序：

1. 应用仓库更新合同
2. AgentPlane 校验合同并部署
3. AgentPlane 刷新 inventory
4. AgentPlane 回写应用摘要

## 12. Sub2API 样板

`sub2api` 是当前正式样板，其目标状态如下：

- 应用合同：应用仓库内的 `deploy/agentplane/contract.yaml`
- AgentPlane Compose 模板：`infra/compose/sub2api/docker-compose.prod0.yml`
- 正式容器名：`sub2api-prod`
- 依赖容器：`postgres18-prod`、`redis7-prod`
- 数据目录：`/data/sub2api/data`
- 正式入口：`https://token.zzzai.cloud:8443`
- 回退入口：无独立旧控制面

样板意义：

- 为后续新增应用仓库提供统一合同模板
- 为 AgentPlane 的 `app` 命令域提供真实接入范例
- 为“从旧控制面迁移到 Compose 主控”提供可回退路径
