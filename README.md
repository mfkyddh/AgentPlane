# AgentPlane

`AgentPlane` 是 Linux / WSL 主机、基础设施服务和正式控制面的治理仓库。它负责统一运维入口、基础设施约束、inventory、runbook 与非敏感模板；业务应用仓库只负责代码、构建产物与非敏感交付合同。

## 仓库定位

- 正式控制面的真源在本仓库，不在业务应用仓库。
- 日常自动化统一从 `uv run python -m agentplane.cli ...` 进入。
- tracked 资产集中在 `docs/`、`infra/compose/`、`inventory/`、`agentplane/`、`templates/`。
- 本地敏感配置根目录是 `secrets/`；正式 truth 按 target 收口到 `secrets/hosts/<target>/...`，`secrets/services/...`、`secrets/app-resources/...`、`secrets/env/...` 如仍存在，只能视为投影文件或兼容路径，不反向充当真源；服务持久化数据默认放在 `/data/<service>/...`。

## 30 秒上手

Linux / WSL 里直接用 `uv run python -m agentplane.cli ...`。

Windows 宿主统一走：
`pwsh -NoProfile -ExecutionPolicy Bypass -File .\.codex\environments\lib\invoke-agentplane-windows-uv.ps1 python -m agentplane.cli ...`

不要在 Windows 控制面根目录直接执行 `uv run ...`，否则会踩 Linux `.venv` 与 Windows 本地环境混用问题。

1. 先检查当前宿主和工作区绑定：
   `uv run python -m agentplane.cli bootstrap inspect-local --repo-root <repo-root>`
2. 生成 bootstrap truth 空壳：
   `uv run python -m agentplane.cli bootstrap init-secrets --repo-root <repo-root>`
3. 按 `secrets/local/control-plane/README.md` 和 `secrets/targets/<target>/README.md` 只填写 Agent takeover 所需 truths：
   - `secrets/ssh/config`
   - `secrets/ssh/keys/*.pem`
4. 校验 truths 是否已就绪：
   `uv run python -m agentplane.cli bootstrap verify-secrets --repo-root <repo-root>`
5. 汇总仓库是否已具备 Agent takeover readiness：
   `uv run python -m agentplane.cli bootstrap doctor --repo-root <repo-root>`
6. 让 Agent 接管后续 domain 动作，再按任务类型下钻文档：
   - WSL 本机治理看 [wsl-host-governance.md](docs/runbooks/wsl-host-governance.md)
   - Linux 基线规则看 [linux-governance.md](docs/architecture/linux-governance.md)
   - 应用仓库接入看 [agentplane-app-collaboration.md](docs/architecture/agentplane-app-collaboration.md)
   - 泛化应用仓库规范看 [app-repository-standard.md](docs/reference/app-repository-standard.md)

## 日常入口

- 统一入口：`uv run python -m agentplane.cli <domain> <action> [flags]`
- Windows 宿主入口：`pwsh -NoProfile -ExecutionPolicy Bypass -File .\.codex\environments\lib\invoke-agentplane-windows-uv.ps1 python -m agentplane.cli <domain> <action> [flags]`
- 命令发现：`uv run python -m agentplane.cli --help`
- 常用仓库自检：`bash agentplane/scripts/internal/repo/self_check.sh`
- 常用主机入口：`uv run python -m agentplane.cli host inventory wsl`
- 常用主机审计：`uv run python -m agentplane.cli host audit wsl`
- 常用主机清理计划：`uv run python -m agentplane.cli host cleanup plan wsl --repo-root /root/work/AgentPlane`
- 常用主机自动化检索：`uv run python -m agentplane.cli host automation search wsl --repo-root /root/work/AgentPlane`
- 常用主机网络审计：`uv run python -m agentplane.cli host network audit prod2-main --repo-root /root/work/AgentPlane`
- 常用服务检索：`uv run python -m agentplane.cli service search --target prod0-main --repo-root /root/work/AgentPlane`
- 常用服务核验：`uv run python -m agentplane.cli service verify --target prod0-main --name postgres --repo-root /root/work/AgentPlane`
- 常用运行服务核验：`uv run python -m agentplane.cli service verify --target prod0-main --name newapi --repo-root /root/work/AgentPlane`
- 常用网站检索：`uv run python -m agentplane.cli website search --target prod0-main --repo-root /root/work/AgentPlane`
- 常用网站核验：`uv run python -m agentplane.cli website verify --target prod0-main --alias token --repo-root /root/work/AgentPlane`
- 常用公网入口发布计划：`uv run python -m agentplane.cli website publish plan --target prod0-main --config-file /root/work/AgentPlane/secrets/services/token-public-ingress.env --cloudflare-env-file /root/work/AgentPlane/secrets/env/prod-jump.env --repo-root /root/work/AgentPlane`
- 常用应用对象检索：`uv run python -m agentplane.cli app object search --target prod0-main --repo-root /root/work/AgentPlane`
- 常用应用对象核验：`uv run python -m agentplane.cli app object verify --target prod0-main --app sub2api --repo-root /root/work/AgentPlane`
- 常用应用交付合同校验：`uv run python -m agentplane.cli app delivery validate-contract --target prod0-main --app sub2api --repo-root /root/work/AgentPlane`
- 常用应用交付计划：`uv run python -m agentplane.cli app delivery deploy --target prod0-main --app sub2api --repo-root /root/work/AgentPlane --dry-run`
- 生产主机清单：`uv run python -m agentplane.cli host inventory prod0-main`
- `onepanel` 只用于 provider/debug 低层对象核对与排障，不作为日常默认入口。
- 正式任务默认从 `host`、`service`、`website`、`app`、`projection` 对应 domain 进入；不要把 `onepanel project` 一类低层对象当作起手命令。
- `service` 是正式受管运行服务对象面；固定对象保留 `postgres`、`redis`、`minio`、`mihomo`、`onepanel_openresty`，并扩展到 inventory 中已声明的 tracked runtime service。
- `service` 只接受 inventory 中已声明的受管运行服务对象，不公开 raw 1Panel install id / project id / container id。
- `service public-endpoint` 负责附着在 service 上的非 HTTP 公网协议端点对账，例如 Cloudflare DNS 与证书续期现场检查。
- `service materialize` 负责渲染附着在 service 事实上的客户端交付物；例如 `relay.zzzai.fun:24443` 的 Clash Local Profile。
- `relay.zzzai.fun:24443` 这类非 HTTP 协议公网入口继续附着在 `service` 事实上，不进入 `website publish`。
- `website` 是正式公网入口对象与发布任务面；以 `inventory.services.public_websites` 为声明真源，正式入口为 `uv run python -m agentplane.cli website ...`。
- `website publish` 是 Cloudflare + 1Panel 公网入口的正式任务入口。
- `app` 是正式应用 catalog、resource 与交付域；`app object` 负责 catalog object，`app resource` 负责 `inventory/servers/<target>/app-resources.json`、`secrets/hosts/<target>/...` 与 `inventory.services.<app>.app_resource_summary` 的资源归属核验；若仍提到 `secrets/app-resources/<target>/<app>/`，必须明确它只是兼容路径或投影输入，不是正式真源；`app delivery` 负责合同、构建、部署与回滚，运行态 restart/reconcile 走 `service`。
- `projection` 是正式派生任务域；README 只声明 `runtime-env`、`verification`、`fixture`、`ledger` 四个 surface，具体流程见 [onepanel-cli-validation-workflow.md](docs/runbooks/onepanel-cli-validation-workflow.md)。
- `onepanel` 只保留 provider/debug 低层对象面：`panel`、`firewall`、`cronjob`、`task`。
- `host automation` 是正式主机自动化任务面；当前以 `inventory/servers/wsl/inventory.json` 的 `automations[]` 为声明真源，并把 `1Panel cronjob` 作为调度器控制器。
- 仓库内部脚本实现位于 `agentplane/scripts/`；对外正式入口统一为 `uv run python -m agentplane.cli ...`。
- Compose 运行命令统一使用 `docker compose`；`infra/compose/` 下仍保留 `docker-compose.*.yml` 作为模板文件名。

## 工作区协作

- 默认在仓库内使用隔离 `git worktree`，项目本地目录优先为 `.worktrees/`。
- 进入新工作区后，先确认执行身份、`$HOME`、仓库根，再开始修改或执行运行态操作。
- 文档改动与代码改动都应先验证统一入口或相关基线，不把现有脏工作区和新任务混在一起。
- 运行态判断以 live state 为准；文档负责解释规则，不替代 `docker ps`、`docker inspect`、直接文件读取等现场核实。
- 详细 WSL 基线见 [wsl-host-governance.md](docs/runbooks/wsl-host-governance.md)；仓库结构概览直接看下方“目录导航”。

## 文档入口

### 正式资产

- [control-plane.md](docs/architecture/control-plane.md)
- [linux-governance.md](docs/architecture/linux-governance.md)
- [agentplane-app-collaboration.md](docs/architecture/agentplane-app-collaboration.md)

`docs/architecture/` 的正式正文已收口到这些长期合同；[docs/architecture/README.md](docs/architecture/README.md) 负责完整索引。`automation-stack.md` 和旧 control-plane 分页当前只保留过渡/断链兼容，不再作为 README 主入口。

### Active Docs

- [bootstrap-secrets.md](docs/runbooks/bootstrap-secrets.md)
- [wsl-host-governance.md](docs/runbooks/wsl-host-governance.md)
- [control-plane-agent-execution-flow.md](docs/runbooks/control-plane-agent-execution-flow.md)
- [control-plane-domain-onboarding.md](docs/runbooks/control-plane-domain-onboarding.md)
- [app-project-delivery-workflow.md](docs/runbooks/app-project-delivery-workflow.md)

`docs/runbooks/` 只保留当前仍活跃的操作指南；历史收口记录、阶段性专题和一次性迁移文档不再作为 README 主入口。

### Reference / History / Archive

- `docs/reference/`：当前的查询型真源层，已承接 `1Panel API compatibility` 和 `应用交付版本规范` 等稳定参考资料。
- [app-repository-standard.md](docs/reference/app-repository-standard.md)：新项目与开源二开项目的统一接入规范。
- [compat-retirement-ledger.md](docs/reference/compat-retirement-ledger.md)：compat 入口退役台账。
- [control-plane-naming-registry.md](docs/reference/control-plane-naming-registry.md)：跨层命名注册表。
- [docs/history/index.md](docs/history/index.md)：阶段计划、设计稿、交接记录的历史索引；当前仍主要回指 `docs/superpowers/` 下的计划资产。
- [docs/archive/README.md](docs/archive/README.md)：退出主流程的归档索引，集中列出历史架构快照和 archived runbook。

维护者 authoring 规则位于 `docs/maintainers/control-plane-authoring.md`，供维护者查阅，不放进普通读者主导航。

## 目录导航

- `.codex/`：Codex 运行配置、`environments/` 动作入口与项目技能。
- `docs/`：`architecture/` 放长期合同，`runbooks/` 放 active 操作指南，`reference/` 放稳定查询资料，[`history/index.md`](docs/history/index.md) 放阶段历史索引，[`archive/README.md`](docs/archive/README.md) 放归档导航，维护者 authoring 规则位于 `docs/maintainers/`。
- `infra/compose/`：服务 compose 资产，默认维护 `docker-compose.wsl.yml` 与 `docker-compose.prod0.yml`。
- `inventory/apps/`：受管应用 catalog。
- `inventory/servers/`：非敏感服务器信息、运行态摘要与探测记录。
- `agentplane/`：Python CLI、自动化代码与仓库内部脚本实现。
- `templates/`：本地私有文件模板。
- `secrets/`：本地敏感配置根目录；正式 truth 按 target 落在 `secrets/hosts/<target>/...`，其余子路径只在被明确标注为 projection 或 compatibility-only 时保留（git 忽略）。

## 常用模板

- [prod-jump.env.example](templates/env/prod-jump.env.example)
- [config.example](templates/ssh/config.example)
- [postgres.env.example](templates/services/postgres.env.example)
- [minio.env.example](templates/services/minio.env.example)
- [cliproxyapi.config.yaml.example](templates/services/cliproxyapi.config.yaml.example)
- [openclaw.env.example](templates/services/openclaw.env.example)
- [onepanel-api.env.example](templates/services/onepanel-api.env.example)
- [redis.conf.example](templates/services/redis.conf.example)

## 说明

- Git 只跟踪模板，不跟踪真实 `.env`、`.pem`、私有 `config`。
- 真实 secrets 真源默认放在 `secrets/hosts/<target>/...`；`secrets/services/...`、`secrets/app-resources/...`、`secrets/env/...` 如仍存在，只能作为投影文件或兼容入口；服务运行数据默认放在 `/data/<service>/...`。
- `bootstrap` 只阻断 Agent takeover 所需 truths；`prod-jump.env` 这类 projection 文件和人工浏览器登录辅助材料不再算 day-zero blocker。
- WSL 测试环境容器名以 `-dev` 结尾；生产环境容器名以 `-prod` 结尾。
