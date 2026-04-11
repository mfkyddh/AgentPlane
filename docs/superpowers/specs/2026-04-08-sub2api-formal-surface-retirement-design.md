# Sub2API Formal Surface Retirement Design

**Date:** 2026-04-08

## Goal

把 `sub2api` 最终收口成一个严格受 `OP_Linux` 正式控制面管理的应用仓库，并同步削减 `OP_Linux` 侧仍暴露给 `sub2api` 的 legacy / compat 对象与说明。

本轮设计覆盖两个仓库、三段工作：

- 在 `/root/work/sub2api` 继续压缩历史面，只保留代码、测试、构建资产、开发态 Docker 资产、`deploy/op/` 合同和必要的非敏感摘要
- 在 `/root/work/OP_Linux` 把 `sub2api` 的 app resource、摘要投影、CLI 入口与 active runbook 收口到 formal app delivery surface
- 通过分阶段推进，避免把“应用仓库瘦身”和“控制面真源迁移”混成一次不可定位的大变更

## Why Now

`sub2api` 的正式生产治理主干已经收口到 `OP_Linux`，但现在仍然存在两个明显的剩余问题：

1. `sub2api` 仓库的 active tree 还保留 installer / systemd / generic self-hosted prod 资产与文案，继续给人一种“仓库本身仍可承担正式生产部署”的错误印象。
2. `OP_Linux` 虽然在文档上已经强调 host-first，但 `app resource` 相关代码、inventory、README、app summary 仍在持续输出 `secrets/app-resources/...` 这样的 compat path，导致 formal surface 口径和实际对象输出不一致。

如果不把这两层一起收口，后续任何新应用接入 `OP_Linux` 都会继承这套“正式流程已成型，但兼容残面仍在活跃面里说话”的状态。

## Hard Decision

本轮明确采用“formal-only”方向，不再保留 `sub2api` 的 active self-hosted / systemd / generic production deploy surface。

具体决定：

1. `sub2api` 不再继续扮演“既是开源应用仓库、又是正式生产安装仓库”的双重角色。
2. `sub2api` active tree 只保留：
   - 业务代码
   - 测试
   - runtime 构建资产
   - 开发态 Docker 资产
   - `deploy/op/contract*.yaml`
   - 必要的非敏感摘要
3. 所有正式 onboarding / deploy / rollback / verify / inventory-refresh / doc-sync 都只能从 `/root/work/OP_Linux` 的 `uv run python -m ops.cli ...` 发起。
4. `OP_Linux` 中凡是已纳入 formal app catalog 且合同为 `schema_version: 1` 的应用，默认不再通过 compat helper 暴露正式执行语义。

## Scope Boundary

本轮只做 `sub2api` 这一条正式样板链路的彻底收口，不同时推广到所有应用。

包含：

- `sub2api` 仓库 active deploy / readme / archive 结构收缩
- `OP_Linux` 中 `sub2api` 相关 app-resource 真源、投影、文档与 CLI 行为调整
- 为后续推广到 `newapi` / `sub2apipay` 提供一套已验证的 formal-only 样板

不包含：

- 上游开源仓库定位、GitHub Releases、对外发布策略重构
- 远端基础设施重新部署或迁移
- 非 `sub2api` 应用在同一轮内一起做 hard cut

## Current State Snapshot

### `sub2api` 当前剩余问题

直接核对到的 active 残面包括：

- 根 `README.md` 仍保留 `install.sh + systemd` 安装说明、网页升级和 rollback 叙事
- `deploy/README.md` 仍把 Docker / Binary Install 作为 active deployment methods
- active `deploy/` 下仍混有以下两类资产：
  - 应继续保留并归类为本地开发 / 构建资产的文件
  - 应退出 active tree 的 installer / systemd / generic production deploy 资产
- 当前最需要明确退场的历史正式面包括：
  - `install.sh`
  - `install-datamanagementd.sh`
  - `sub2api.service`
  - `sub2api-datamanagementd.service`
  - `docker-deploy.sh`
  - `build_image.sh`
  - `Caddyfile`
  - `DOCKER.md`
  - `deploy/prod/dist/*.tar.gz`
- 当前仍可能保留为 active dev asset 的文件包括 `docker-compose.dev.yml`、`docker-compose.local.yml`、`.env.example`、`config.example.yaml`，是否保留取决于它们是否只服务本地开发且不再承担正式生产叙事
- `docs/archive/` 已存在，但 active / archive 的边界还没有硬切到“只有 `deploy/op/` 才是正式 handoff 面”

### `OP_Linux` 当前剩余问题

直接核对到的 formal / compat 不一致包括：

- `ops/domain/app/secrets_lifecycle.py` 与 `ops/domain/app/lifecycle.py` 仍把 canonical secret path 生成为 `secrets/app-resources/<target>/<app>/<kind>.env`
- `inventory/servers/<target>/inventory.json`、`app-resources.json`、`ledgers/*.json`、目标 README、`app_resources.md` 仍持续打印这些 compat path
- active runbook 仍在部分段落里把 `secrets/app-resources/...` 作为应用资源凭据默认位置
- compat helper 仍在对象面周边保持较强存在感，formal app 还没有明确被限制为只能走 `app object` / `app delivery` / `service` / `website`

## Target State

### Target State A: `sub2api` 只保留应用仓库职责

目标形态：

```text
README.md
backend/
frontend/
tests/
deploy/
  build-runtime-artifacts.sh
  package-runtime-image.sh
  Dockerfile.runtime
  docker-entrypoint.sh
  op/
    contract.wsl.yaml
    contract.yaml
    contract.prod2.yaml
    runtime.env.example
docs/
  README.md
  owner/
  archive/
  OP_LINUX_DEPLOYMENT.wsl.md
  OP_LINUX_DEPLOYMENT.prod0-main.md
  OP_LINUX_DEPLOYMENT.prod2-main.md
  # 可选保留的本地开发 Docker 文档必须显式限定为 dev-only
```

约束：

- active `deploy/` 不再承载 systemd、binary install、generic production deploy、release tarball 残留
- active `deploy/` 若保留 Docker Compose 或 `.env.example` 一类文件，必须明确只服务本地开发 / 联调，不再承担正式生产说明
- generic self-hosted 文档如仍需保留，只能进入 `docs/archive/` 或上游公共文档路径，不得继续占据 active owner/operator surface
- active 根 README 只描述开发、构建、合同和 `OP_Linux` handoff 关系

### Target State B: `OP_Linux` 的 `sub2api` 只走 formal app delivery surface

目标形态：

- `app object`、`app delivery`、`service`、`website` 是唯一正式可操作对象面
- app resource canonical secret path 收口到 host-first 叶子路径
- active inventory / ledgers / summaries 不再打印 compat path
- compat helper 仅保留 archive / ledger / provider-debug 语义

建议的新 canonical app resource secret path：

`secrets/hosts/<target>/apps/<app>/resources/<kind>.env`

这是本轮建议的新规范，不是当前既有事实。采用它的原因：

- 与仓库已声明的 host-first truth 一致
- 避免把 `app-resources` 这个历史中间层继续暴露为正式路径名
- 便于把 host secret truth、runtime projection 和 README 摘要区分开

## Phased Execution Plan

### Phase 1: Shrink `sub2api` Active Surface

目标：先把应用仓库的边界改对。

动作：

- 重写 `sub2api` 根 README 与 `deploy/README.md`
- 把 installer / systemd / generic prod deploy 资产从 active tree 移出
- 清理 `deploy/prod/` 剩余 `dist/`、`tmp/` 等历史生成物
- 把仍需保留的历史材料统一归档到 `docs/archive/`
- 为 active `deploy/` 增加硬约束测试或快照校验，禁止旧资产回流

验收：

- active tree 不再出现 `install.sh`、`*.service`、`docker-deploy.sh`、`deploy/prod/dist` 等历史正式面
- 根 README 不再出现 systemd / binary install / rollback 作为当前正式使用方式
- `deploy/op/contract*.yaml`、runtime build 脚本、开发态 Docker 资产保持可用

### Phase 2: Migrate `OP_Linux` App Resource Truth To Host-First

目标：把 formal surface 的真实对象输出改正。

动作：

- 迁移 `ops/domain/app/*`、`projection runtime-env`、`app resource` / `app delivery` 对 canonical secret path 的定义
- 更新 `inventory.json`、`app-resources.json`、`ledgers/*.json`、README、`app_resources.md` 的投影输出
- 对 `sub2api`、`newapi`、`sub2apipay` 的相关测试统一改为新路径
- 确保 `sub2api` 的 get / verify / deploy / verify 主流程不回退到 compat path

验收：

- 新生成的 registry / inventory / summary 不再把 `secrets/app-resources/...` 当成 canonical 输出
- app-resource 相关代码与文档全部与 host-first 路径一致
- formal `sub2api` 交付链路验证通过

### Phase 3: Cut Down Legacy / Compat Surface In `OP_Linux`

目标：把 `sub2api` 从“formal-first”推进到“formal-only”。

动作：

- 对已进入 formal app catalog 且 `schema_version: 1` 的应用，compat helper 不再提供正式执行语义
- 压缩 active runbook、README、inventory summary 中对 compat path 和 compat helper 的主动暴露
- compat 只留在 `docs/reference/compat-retirement-ledger.md`、archive runbook 和 provider/debug 场景

验收：

- `sub2api` 的标准操作入口只剩 `app object`、`app delivery`、`service`、`website`
- active runbook 不再把 compat helper 当作可执行默认路径介绍
- compat helper 即使保留，也只承担只读排障或历史兼容语义

## Risks And Controls

### 风险 1：Phase 1 误删仍有开发价值的本地 Docker 资产

控制：

- 明确保留开发态 Compose / `.env.example` / runtime build 资产
- 删除范围只针对 installer / systemd / generic production deploy / tracked dist
- 通过 repo 快照测试固定 active `deploy/` 白名单

### 风险 2：Phase 2 会影响多个 app，不只是 `sub2api`

控制：

- 把 Phase 2 视为 `OP_Linux` 的对象域迁移，不伪装成 sub2api-only 文案清理
- 用 `sub2api` 做首个样板，但测试必须覆盖 `newapi`、`sub2apipay` 和 `wsl`
- 先改 canonical generation，再刷新 inventory / summary，避免“代码没变、摘要先漂移”

### 风险 3：compat helper 退得太快，影响现场排障

控制：

- 不要求立即物理删除 helper 文件
- 先删除其 formal execution 资格，再把剩余能力降级为 provider/debug only
- 保留 compat retirement ledger 和 archive runbook 作为解释层

## Verification Strategy

### Phase 1 Verification

- `sub2api` 仓库快照 / grep / shell 校验：确认 active tree 不再含旧资产
- `bash deploy/package-runtime-image.sh` 或最小构建校验通过
- `uv run python -m ops.cli app delivery validate-contract ...` 对 `wsl` / `prod0-main` / `prod2-main` 继续通过

### Phase 2 Verification

- `OP_Linux` 针对 app-resource、projection、inventory、summary 的单测全部通过
- `app object get/verify`、`app delivery validate-contract`、`deploy --dry-run`、`verify` 对 `sub2api` 通过
- 刷新后的 inventory / README / app summary 不再出现 compat canonical path

### Phase 3 Verification

- CLI / 文档测试证明 active docs 不再把 compat helper 当正式入口
- 对 formal app 尝试通过 compat helper 执行时，返回明确拒绝或只读语义
- `docs/reference/compat-retirement-ledger.md` 与剩余 compat 文件集合保持一致

## Recommended Order

推荐执行顺序固定为：

1. 先完成 Phase 1
2. 再完成 Phase 2
3. 最后完成 Phase 3

原因：

- 先改 `sub2api`，能立刻消除“应用仓库自己还是正式入口”的认知噪音
- 再改 `OP_Linux` 真源，能避免迁移后仍被旧应用仓库文案拉回去
- 最后削 compat surface，能让 formal-only 限制建立在已经稳定的新真源之上，而不是先卡死现场工具

## Definition Of Done

当且仅当以下条件同时成立，才算本轮完成：

- `sub2api` active tree 只保留代码、测试、构建资产、开发态 Docker 资产、`deploy/op/` 合同和必要非敏感摘要
- `OP_Linux` 对 `sub2api` 的 formal surface 不再输出 `secrets/app-resources/...` 作为 canonical truth
- `sub2api` 的正式执行入口只剩 `app object`、`app delivery`、`service`、`website`
- active README / runbook / inventory summary 与 CLI 行为一致
- compat 只留在 archive、ledger 和 provider/debug 语义，不再留在 active operator surface
