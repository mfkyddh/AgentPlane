# Sub2API Repo Governance And Onboarding Design

**Date:** 2026-04-07

## Goal

把 `/root/work/sub2api` 从“带有大量二开过程痕迹、历史发布残留和本地经验文档的应用仓库”，收口成符合 `OP_Linux` 当前 CLI-first 规范的应用仓库样板。

本轮目标同时覆盖两条线：

- 仓库治理线：`AGENTS.md`、仓库级 skill、Codex 环境、文档结构、目录结构、私有数据边界、历史产物治理
- 应用接入线：以 `wsl -> prod0-main -> prod2-main` 的顺序，把 `sub2api` 完整纳入 `OP_Linux` 的 `app object + app delivery` 正式闭环

## Why Now

当前 `sub2api` 已经具备部分 `OP_Linux` 接入能力，但整体状态仍然是“部署链路局部成型、仓库治理层明显漂移”：

- `prod0-main` 与 `prod2-main` 已有 `contract`、`compose` 运行面和部分 `inventory` truth
- `wsl` 已经有 `compose` / env 模板 / app-resource 预铺资产，但仍未成为正式 `app` target
- 仓库入口文档、Makefile、repo skill、Codex 环境仍保留旧控制面、旧路径和失效引用
- 应用仓库中的 `docs/OP_LINUX_DEPLOYMENT.*.md` 已存在，但 `wsl` 摘要与 tenant secret 路径仍明显漂移
- 仓库同时承载 public 说明、owner 说明、历史打包残留和 agent 执行痕迹，边界不清

如果不先完成这一轮治理收口，后续把别的应用仓库接入 `OP_Linux` 时会复制这些问题，而不是复制一套稳定样板。

## Decision

采用“低侵入、分阶段、双线并行但先治理后放大接入”的方案。

核心决策如下：

1. `sub2api` 继续保持“开源二开项目”属性，不强行删除上游面向公众的安装文档和通用部署资产。
2. 仓库 owner / 运维 / Agent 的正式入口统一指向 `OP_Linux`，不再让 repo 内文档或脚本形成第二正式控制面。
3. `sub2api` 应用接入采用显式多 target 合同：
   - `deploy/op/contract.wsl.yaml`
   - `deploy/op/contract.yaml`（`prod0-main`）
   - `deploy/op/contract.prod2.yaml`
4. `wsl` 被定义为正式治理目标，但它是 dev-target，不伪装成生产 target。
5. 应用仓库中的真实私有数据只保留本地开发运行所需部分；生产 secrets、SSH、跳板、正式 env truth 全部回到 `OP_Linux`。
6. 历史产物、临时执行痕迹和 agent 运行残留不再作为长期 tracked 资产继续累积。

## Design Principles

### 1. Single Formal Entry

正式生产控制面只允许来自 `/root/work/OP_Linux` 的 `uv run python -m ops.cli ...`。

`sub2api` 仓库只负责：

- 业务代码
- 测试
- runtime 构建资产
- 非敏感模板
- `deploy/op/contract*.yaml`
- 非敏感应用摘要

### 2. WSL-First Without Windows-First Wrapping

仓库协作默认是 `WSL-first`。Windows 只保留浏览器外壳和必要桥接，不应成为主入口表达方式。

### 3. Public / Owner / Archive Separation

仓库内文档必须显式区分三类：

- public：上游用户、开源访客、普通部署者可读
- owner：当前仓库 owner 与 `OP_Linux` 协作面
- archive：历史发布、旧控制面、旧 smoke、迁移前快照

### 4. Secrets Are Not Docs

文档只描述边界和模板，不保存真实 secrets、跳板来源、远端控制上下文，不把 repo 根目录 `.env` 和 `.prod-jump.env` 当成长期正式规范。

### 5. Archive Is Explicit

历史资产可以保留，但必须明确标记为 archive，并且不能继续污染 active 入口。

## Current Gap Summary

| 主题 | 当前问题 | 影响 |
| --- | --- | --- |
| `AGENTS.md` | 不是 `OP_Linux` 推荐的 6 段结构，并且首屏引用了不存在的 `.planning/PROJECT.md`、`.planning/ROADMAP.md` | 新接手者第一步就踩空 |
| Makefile | 仍保留失效 `prod-*` 提示、旧 `/root/work/env_ubuntu` 路径、以及指向不存在目录的 target | 命令面不可信 |
| Codex 环境 | 只有 `environment.toml`，没有标准 `setup/`、`actions/`、`lib/`；而且主入口是 Win32 wrapper | 与仓库 `WSL-first` 规则冲突 |
| repo skill | `.agents/skills/*` 有价值，但命令、路径和 contract 引用已明显漂移 | agent 很容易按旧控制面工作 |
| 文档结构 | `README`、`DEV_GUIDE`、`zqfdocs`、`docs/`、`deploy/prod/` 同时承担 active + archive + owner 语义 | 读者无法快速判断什么是当前真源 |
| 部署摘要 | `docs/OP_LINUX_DEPLOYMENT.wsl.md` 仍指向 `deploy/op/contract.yaml`，三份摘要仍使用 `secrets/tenants/...`，与 `OP_Linux` 当前 `secrets/app-resources/...` 真源不一致 | app-side 摘要会继续误导使用者和后续 doc-sync |
| 本地私有数据 | 根目录 `.env`、`.prod-jump.env` 仍是事实入口；文档里还存在外部仓库 env 依赖与硬编码开发凭据 | 私有数据边界不清 |
| tracked 生成物 | `.superpowers/**` 与 `deploy/prod/dist/*.tar.gz` 已被跟踪 | 仓库长期污染、同步成本变高 |
| 应用接入 | `inventory/apps/catalog.json` 尚未为 `sub2api` 登记 `wsl` contract；`prod2-main` 的 `token.zzzai.fun` 仍未进入 `websites` ledger 正式对象 | 样板项目还未形成完整闭环 |

## Validated State Snapshot

以下状态已在 2026-04-07 直接核对：

- `/root/work/sub2api/deploy/op/contract.yaml` 与 `/root/work/sub2api/deploy/op/contract.prod2.yaml` 已存在；`contract.wsl.yaml` 仍不存在。
- `/root/work/OP_Linux/inventory/apps/catalog.json` 目前只登记了 `prod0-main` 和 `prod2-main` 两个 `sub2api` contract。
- 执行
  `uv run python -m ops.cli app object verify --target wsl --app sub2api --repo-root /root/work/OP_Linux`
  与
  `uv run python -m ops.cli app delivery validate-contract --target wsl --app sub2api --repo-root /root/work/OP_Linux`
  都返回
  `app catalog missing target mapping: target=wsl app=sub2api`。
- `/root/work/OP_Linux/infra/compose/sub2api/docker-compose.wsl.yml`、`templates/services/sub2api.wsl.env.example`、`inventory/servers/wsl/app-resources.json` 已存在，因此 `wsl` 不是零状态，而是“控制面资产已预铺、app object 尚未闭环”的状态。
- `/root/work/OP_Linux/inventory/servers/prod2-main/ledgers/websites.json` 当前只有 `1panel`，`token.zzzai.fun` 只出现在 `inventory.json`、`apps.json`、`containers.json` 与验证输出中，尚未收口为正式 `website` 对象。
- `/root/work/sub2api/docs/OP_LINUX_DEPLOYMENT.wsl.md` 仍引用 `deploy/op/contract.yaml`；三份 `OP_LINUX_DEPLOYMENT.*.md` 仍使用 `secrets/tenants/...`，与 `OP_Linux` 当前 `secrets/app-resources/...` 真源不一致。
- 全局 personal skill `C:\Users\Administrator\.agents\skills\zzz-oplinux-app-delivery` 已删除；未来 `OP_Linux` 应用交付 guidance 的正式入口只保留仓库级 `app-delivery-ops` 与相关 runbook。

## Target State

### Application Repo Shape

`sub2api` 收口后的目标形态：

```text
AGENTS.md
README.md
docs/
  README.md
  api/
  owner/
  archive/
  OP_LINUX_DEPLOYMENT.wsl.md
  OP_LINUX_DEPLOYMENT.prod0-main.md
  OP_LINUX_DEPLOYMENT.prod2-main.md
deploy/
  build-runtime-artifacts.sh
  package-runtime-image.sh
  Dockerfile.runtime
  docker-entrypoint.sh
  op/
    contract.wsl.yaml
    contract.yaml
    contract.prod2.yaml
.codex/
  environments/
    environment.toml
    setup/
    actions/
    lib/
.agents/
  skills/
secrets/
  local/              # untracked local dev secrets
```

说明：

- `docs/owner/` 承载当前 owner / `OP_Linux` 协作说明
- `docs/archive/` 承载 `deploy/prod/` 旧时代说明的长期归档引用
- `secrets/local/` 是目标私有数据落点；repo 根 `.env` 只作为过渡兼容输入

### OP_Linux Shape

`OP_Linux` 中继续承载正式 truth：

- `inventory/apps/catalog.json`
- `inventory/servers/<target>/inventory.json`
- `infra/compose/sub2api/docker-compose.wsl.yml`
- `infra/compose/sub2api/docker-compose.prod0.yml`
- `infra/compose/sub2api/docker-compose.prod2.yml`
- `templates/services/sub2api.wsl.env.example`
- `templates/services/sub2api.prod0.env.example`
- `templates/services/sub2api.prod2.env.example`

## Formal Release Usage Model

### Human-Facing Usage

改造完成后，人类使用口径固定拆成两段：

1. 在应用仓库 `/root/work/sub2api` 准备发布输入：
   - 代码
   - 测试
   - `deploy/op/contract*.yaml`
   - runtime 构建脚本
   - 非敏感模板
2. 在控制面仓库 `/root/work/OP_Linux` 执行正式发布动作：
   - `app delivery onboard`（首次纳管）
   - `app delivery validate-contract`
   - `app delivery build-artifact`
   - `app delivery ship-image`
   - `app delivery deploy`
   - `app delivery verify`
   - `app delivery inventory-refresh`
   - `app delivery doc-sync`

这意味着：

- `make wsl-*`、repo-local dev 脚本、repo-local bootstrap 仍然保留，但只服务本地开发与预演，不再承担正式发布语义。
- 应用仓库内的构建脚本仍然存在，但它们退回到“交付输入原语”的角色；正式发布入口统一由 `OP_Linux` CLI 调用，不再由人直接记忆第二套脚本链路。
- steady-state 发布与回滚都必须在 `/root/work/OP_Linux` 的 WSL shell 内执行，不再从应用仓库根目录发起正式切换。

### Agent-Facing Governance

Agent 的正式口径固定为：

- skill 负责“选流程、辨边界、避免第二控制面”
- `uv run python -m ops.cli ...` 负责“真正执行正式动作”

具体边界：

- 应用仓库 repo-local skill 只负责本地开发、构建、预演、repo 内上下文建立。
- 涉及 onboarding、deploy、rollback、inventory、doc-sync 的正式动作时，Agent 必须切换到 `/root/work/OP_Linux`，并使用 `target + app` 形式调用 `app object` / `app delivery`。
- skill 不是执行真源；正式执行真源永远是 `OP_Linux` 的 CLI-first 命令面。

## Repo-Level Skill Governance Model

### Source Of Truth

`OP_Linux` 的仓库级 skill 真源固定为：

- `.codex/skills/`
- `.codex/skills/catalog.yaml`

`.agents/skills/` 只作为轻量 pointer layer，不再承载第二份 skill 真源。

### Global Skill Retirement

`zzz-oplinux-app-delivery` 已被定义为过渡期 global skill，不再保留。原因不是它“完全没价值”，而是：

- global skill 不随 `OP_Linux` 仓库版本一起演进，容易漂移
- 它复制了仓库内已经正式存在的 app delivery 边界
- 它会诱导 Agent 在仓库外形成“看起来像正式入口”的第二解释层

未来规则：

- 不再新增新的 `zzz-*` 全局 `OP_Linux` skill
- 与 `OP_Linux` 直接耦合的治理技能，全部下沉为 repo-level skill
- 个人全局 skill 只保留真正跨仓库、与某个仓库版本无关的通用能力

### Skill Tiers

截至 2026-04-07，`OP_Linux` 的 repo-level skill catalog 中有 32 个目录项，其中 30 个 `canonical`、2 个 `compat`。这只是当前盘点快照，不是长期必须冻结的裸数字；长期应冻结的是“分层模型”：

| 层级 | 目标 | 长期口径 |
| --- | --- | --- |
| core control-plane skills | 表达正式对象域、任务域、投影域的主干能力 | 长期稳定，优先复用 |
| compat skills | 承接旧命名、旧入口或过渡期调用习惯 | 可以逐步退役，不再扩张 |
| scenario/setup skills | 承接特定服务安装、迁移、专项排障 | 允许按场景增减 |

当前应视为长期主干的 core control-plane skill 至少包括：

- `app-delivery-ops`
- `app-resource-ops`
- `host-ops`
- `inventory-ledger-ops`
- `projection-ops`
- `onepanel-app-ops`
- `onepanel-container-ops`
- `onepanel-cronjob-ops`
- `onepanel-firewall-ops`
- `onepanel-panel-ops`
- `onepanel-website-ops`

兼容层当前仅应保留少量明确标记的 skill，例如：

- `onepanel-app-lifecycle`
- `openclaw-1panel`

设计上不应该承诺“未来永远只有 32 个 repo-level skill”；真正要冻结的是：

- repo-owned source of truth
- core / compat / scenario 三层边界
- 与正式 CLI-first 控制面的直接对应关系

## Phase Plan

## Phase 1: Contract And Entry Cleanup

### Goal

先把“入口可信度”修到可用状态，不让新接手者、Agent、未来文档迁移都建立在失效入口上。

### Scope

- 重写 `sub2api` 根 `AGENTS.md` 为 6 段结构：
  - `Scope`
  - `Repo Map`
  - `Standard Commands`
  - `Working Rules`
  - `Definition Of Done`
  - `Docs`
- 去掉不存在的 `.planning/PROJECT.md`、`.planning/ROADMAP.md` 引用
- 把 active 层文档和 Makefile 中的 `/root/work/env_ubuntu` 全部改成 `/root/work/OP_Linux`
- 清理或重写失效入口：
  - `make prod-deploy`
  - `make prod-rollback`
  - `make prod-verify*`
  - 指向不存在的 `datamanagement` / `tools/secret_scan.py`

### Exit Criteria

- 从 `AGENTS.md -> README -> docs 导航` 的路径不再出现失效引用
- active 层不再出现 `/root/work/env_ubuntu`
- Makefile 只保留当前仍有效或明确归档的入口

## Phase 2: Codex And Repo Skill Standardization

### Goal

把仓库协作工具面改成与 `OP_Linux` 当前规范一致，而不是“继续依赖旧 wrapper 和旧命令”。

### Scope

- 把 `.codex/environments/` 补齐为标准结构：
  - `environment.toml`
  - `setup/`
  - `actions/`
  - `lib/`
- 主动作语义切到 WSL 命令面，Windows 仅作为桥接实现细节
- repo 内与 app delivery 相关的 guidance 全部统一指向 `/root/work/OP_Linux/.codex/skills/app-delivery-ops` 与正式 runbook
- 更新 `.agents/skills/*`：
  - 全部切到 `app object` / `app delivery`
  - 不再使用旧 `--contract` 公开主入口
  - 不再引用不存在的 `docs/OP_LINUX_DEPLOYMENT.md`
- 清理所有 active 引用中的已退役 global skill：
  - `zzz-oplinux-app-delivery`
- 固定 repo-level skill 真源关系：
  - `.codex/skills/`
  - `.codex/skills/catalog.yaml`
  - `.agents/skills/` 仅作为 pointer layer
- 新增一个轻量的 repo skill index 文档，说明什么时候用哪个 skill

### Exit Criteria

- Codex action 的公开表达和仓库 `WSL-first` 一致
- repo skill 不再指向旧 CLI 或失效路径
- active guidance 不再引用已退役的 global app-delivery skill
- app delivery 的 skill 解释层与 `OP_Linux` runbook / CLI 口径一致
- 新 agent 进入仓库时可以直接信任这些仓库内工具

## Phase 3: Documentation And Repository Topology Cleanup

### Goal

把文档从“混合堆放”改成“分层导航”，同时尽量不破坏上游 public 说明。

### Scope

- 根 `README` 继续承担 public / upstream 面向用户的角色
- 新增 `docs/README.md` 作为 owner 文档导航
- `zqfdocs/` 逐步迁到 `docs/owner/`
- `deploy/prod/` 只保留 archive 定位，并在 `docs/archive/` 中建立说明索引
- `docs/superpowers/` 标记为 maintainers-only / agent planning material，不再作为常规入口

### Exit Criteria

- active 文档导航固定为：
  - 根 `README`
  - `AGENTS.md`
  - `docs/README.md`
- `zqfdocs/` 与 `deploy/prod/` 不再承担 active 入口角色

## Phase 4: Secrets And Private State Boundary Hardening

### Goal

把本地开发私有数据、跳板控制数据、生产 secrets 的边界彻底拉开。

### Scope

- 文档中不再把 `.prod-jump.env` 作为 active 规范入口
- 生产 / SSH / jump / website / provider secrets 全部回到 `OP_Linux/secrets/`
- 应用仓库只保留本地开发私有状态，目标路径为 `secrets/local/`
- `.env` 作为过渡兼容输入保留一段时间，待脚本迁移后再退役
- 从 active 文档中移除硬编码开发凭据和外部仓库 env 依赖
- 明确 `docs/OP_LINUX_DEPLOYMENT.*.md` 为 `doc-sync` 生成物，不手工长期维护

### Exit Criteria

- 应用仓库不再承载正式部署控制私有数据
- active 文档不再写死本地明文凭据或 jump 来源
- 本地开发私有状态有统一落点和忽略规则

## Phase 5: Archive And Generated Artifact Governance

### Goal

停止把历史 tarball、临时 agent 运行痕迹和生成物当成长期源码资产继续跟踪。

### Scope

- 停止跟踪 `.superpowers/**`
- 停止跟踪 `deploy/prod/dist/*.tar.gz`
- 为 archive 二进制保留 manifest / 说明，而不是把大文件长期留在 git
- 复核并冻结 generated 文件策略：
  - `backend/data/`
  - `*.tsbuildinfo`
  - build 输出目录

### Guardrail

本阶段涉及 tracked 文件移除或 archive 迁移，执行前需要用户明确批准。

### Exit Criteria

- git 仓库不再持续累积历史 tarball 与运行残留
- generated / archive / source 的边界清晰

## Phase 6: Complete Sub2API Onboarding As The Reference App

### Goal

在治理面完成收口后，再把 `sub2api` 做成真正可复制的 `OP_Linux` 应用样板。

### Scope

- 新增 `deploy/op/contract.wsl.yaml`
- `inventory/apps/catalog.json` 为 `sub2api` 显式登记：
  - `wsl`
  - `prod0-main`
  - `prod2-main`
- 将 `wsl` 定义为正式 dev-target：
  - `sub2api-dev`
  - `postgres18-dev`
  - `redis7-dev`
  - `0.0.0.0:18080`
- 固化 `prod0-main` 为样板 target
- 补齐 `prod2-main` 的 `website` truth，把 `token.zzzai.fun` 收口到正式 `website` 对象
- 统一 `inventory-refresh` / `doc-sync` 输出

### Exit Criteria

- `uv run python -m ops.cli app object verify --target wsl --app sub2api --repo-root /root/work/OP_Linux` 通过
- `uv run python -m ops.cli app delivery validate-contract --target wsl --app sub2api --repo-root /root/work/OP_Linux` 通过
- `prod0-main` 的 `service` / `website` / `doc-sync` 形成稳定样板
- `prod2-main` 的 `service` 与 `website token` 都进入正式闭环

## Why This Order

顺序必须是：

1. 先修入口和规则
2. 再修 agent / Codex 工具面
3. 再整理文档与目录
4. 再收紧 secrets 边界
5. 再处理 archive 和 tracked 大文件
6. 最后完成应用接入闭环

原因：

- 如果入口和文档不先收口，后续每个阶段都会反复踩旧路径和失效命令
- 如果私有数据和 archive 不先分层，应用接入结果会继续把历史噪音写回 repo
- 如果 `wsl` 不先成为正式 target，`sub2api` 不能作为真正的接入样板复制到其他项目

## Implementation Planning Boundary

这份 design 文档刻意覆盖完整治理收口，不应直接落成单一 implementation plan。进入执行时应拆成至少四个子计划：

1. 仓库入口与工具面修复：
   覆盖 Phase 1-2，先修 `AGENTS.md`、Makefile、Codex 环境、repo skill 漂移。
2. 文档、私有状态与 archive 治理：
   覆盖 Phase 3-5，收口文档导航、`docs/OP_LINUX_DEPLOYMENT.*`、`secrets/local/`、tracked 生成物；其中 tracked 文件移除仍需要用户明确批准。
3. `wsl` 正式 target 收口：
   覆盖 `contract.wsl.yaml`、`catalog.json` target mapping、wsl 摘要文档与验证命令通过。
4. `prod2-main` 网站对象与最终同步闭环：
   覆盖 `token.zzzai.fun` 的正式 `website` truth、`inventory-refresh`、`doc-sync` 与样板冻结。

推荐先写第 1 个子计划，因为它能先消除失效入口和旧控制面误导，降低后续三个阶段的返工概率。

## Success Criteria

- `sub2api` 成为符合 `OP_Linux` 当前规范的应用仓库样板
- active 文档、repo skill、Codex 环境、命令入口全部指向当前正式控制面
- 仓库只保留长期有效源码、模板和非敏感合同，不再继续积累历史执行残留
- `wsl -> prod0-main -> prod2-main` 的应用接入顺序被正式冻结，并可直接复用到下一批应用仓库
