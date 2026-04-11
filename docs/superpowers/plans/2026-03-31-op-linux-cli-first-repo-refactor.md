# OP_Linux CLI-First Repository Refactor Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不进入应用层改造的前提下，先把 `OP_Linux` 自身收敛为更清晰的 CLI-first 治理仓库：正式控制面单点收口，脚本/文档/skills/test 的第二真源被压缩，历史过程资产退出主导航。

**Architecture:** 本轮以“仓库瘦身 + 真源收口 + 兼容层下沉”为主，不改变应用仓库边界，也不把应用 Compose/应用 env 模板迁出本仓库。正式入口继续固定为 `uv run python -m ops.cli ...`；`ops/scripts/*` 只保留 transport substrate、兼容 shim 和少量暂未替代的 internal helper；文档分成 `README -> architecture -> runbooks -> reference/archive` 四层；skills 以 `.codex/skills/` 为唯一正文真源，其余层转为派生。

**Tech Stack:** Python 3, `uv`, `pytest`, Bash thin wrapper, tracked Markdown/JSON inventory and ledgers, repo-local Codex skills/plugins, Git worktree.

---

## Context

- 主仓库：`/root/work/OP_Linux`
- 本次计划工作区：`/root/work/OP_Linux/.worktrees/codex-cli-first-repo-refactor`
- 本次计划分支：`codex/cli-first-repo-refactor-plan`
- 当前阶段只改 `OP_Linux` 仓库自身
- 明确不做的事：
  - 不迁移应用仓库 Docker 资产
  - 不调整应用层 `deploy/op/contract.yaml`
  - 不收口 `newapi` / `sub2api` / `sub2apipay` / `chatgpt-register-v2` 等应用运行面
  - 不清理远端 live state

## Scope

本轮计划覆盖这些目标：

1. 收敛仓库入口、架构文档、runbook 和历史文档的信息架构。
2. 压缩第二控制面：让 runbook、skills、plugins 不再重复承载正式命令面。
3. 重新划清 `ops.cli`、`ops/scripts/*`、`inventory/ledgers`、`templates` 的职责边界。
4. 把测试从“冻结仓库现状”拆成“冻结正式合同”和“冻结兼容策略”。
5. 为下一阶段应用层改造清理出干净边界，但不进入应用层。

## 重新审视 / Gap / 优化

- 当前计划没有偏离 `CLI-first repository refactor` 主线：本轮仍然只处理仓库入口、正式真源、兼容层、历史资产与测试口径，不提前进入应用运行面和远端 live state 改造。
- 需要补强的不是方向，而是“收口之后如何承接更宽对象域”的显式设计。原计划把仓库瘦身、真源收口、兼容层下沉写得比较清楚，但没有把收口完成后如何继续扩到 `host / service / website / tenant / app / projection` 写成清晰挂点。
- 因此，本计划补充以下扩展挂点，作为后续控制面演进的显式承接面：
  - `host`：`host identity`、`ssh`、`firewall`、`ip address`、`filesystem / mounts`、`baseline / doctor / inventory-refresh`
  - `service / website`：`postgres`、`redis`、`minio`、`nginx / openresty`、website object 生命周期
  - `tenant / resource`：`database`、`role`、`user`、`schema`、`bucket`、`policy`、`secret projection`
  - `app`：`contract schema`、更多 `runtime` 类型、`rollback / smoke / doc-sync` 统一化
  - `projection`：`ledger / inventory / summary / versioning / skills / plugins / automation` 的薄层化
- 这些补充不改变当前 Phase 0-7 的主线，只是把 Phase 4-7 的意义写清楚：它们不只是仓库瘦身动作，而是在为后续正式对象域和横向扩展能力准备底座。

## Success Criteria

- `README.md` 和主导航只暴露正式真源，不再把历史过程资产当主入口。
- `docs/architecture/` 只保留长期稳定合同；维护者 authoring 规则和历史快照退出该目录。
- `docs/runbooks/` 中 active runbook 的主路径统一切到 `ops.cli`。
- `docs/superpowers/` 不再作为主资产区；历史计划/设计/交接进入 `archive` 或 `history`。
- `ops/scripts/remote/` 只保留 transport/compat/internal helper，不再继续膨胀为专题脚本仓。
- `.codex/skills/` 明确成为唯一正文真源；`.agents/skills/` 和插件分组层转为派生。
- 测试先冻结新的合同，再允许瘦身对象；不再让 repo snapshot 测试阻断所有结构整理。
- `host / service / website / tenant / app / projection` 的后续扩展挂点在计划与架构口径中被明确写清，而不是继续隐含在 runbook 或脚本命名里。
- 每一阶段结束时都有一段对照总体目标的阶段总结，并更新状态。

## Non-Goals

- 不把应用 Compose 从 `infra/compose/<app>/` 迁回应用仓库。
- 不删除应用 env 模板或重构 `ops.cli app` 的应用交付语义。
- 不在本轮解决所有 1Panel helper 的正式对象化替代。
- 不触碰生产主机或 WSL live state，除非阶段验证明确要求只读命令。

## Execution Rules

### Workspace Rule

- [x] 所有改动必须只发生在新工作区：`/root/work/OP_Linux/.worktrees/codex-cli-first-repo-refactor`
- [x] 禁止在主工作树 `/root/work/OP_Linux` 直接改文件
- [x] 分支固定从 `codex/` 前缀开始

### Delegation Rule

- [ ] 主协调线程只负责任务拆分、状态更新、阶段总结、验证收口
- [ ] 具体文件改动优先交给子代理
- [ ] 允许并行使用最多 `12` 个子代理
- [ ] 子代理写集必须尽量互斥，避免多人改同一文件

### Stop Rule

- [ ] 如果某一阶段任务过大、写集过宽、或需要跨越到应用层，立即停止在当前阶段末尾
- [ ] 停止前至少完成：
  - 当前阶段已完成子任务的状态回写
  - 最小验证
  - 提交当前变更
  - 记录下一会话的继续入口

### Stage Review Rule

每个阶段结束都必须追加一段“阶段总结”，至少回答：

- 已经完成了哪些工作
- 这些工作如何对应总体目标
- 哪些问题仍未解决
- 下一阶段从哪里开始

## Global Status Board

- [x] Phase 0: 建立边界、工作区和测试拆分策略
- [x] Phase 1: 收敛入口与信息架构
- [x] Phase 2: 收敛 architecture / reference / archive
- [x] Phase 3: 收敛 active runbook 与历史 runbook
- [x] Phase 4: 收敛 remote 层与 transport substrate
- [x] Phase 5: 收敛 skills / plugins / pointer 层
- [x] Phase 6: 收敛 templates / inventory / ledger 的非应用层资产
- [x] Phase 7: 全仓复核、阶段总结、交接到下一阶段

## File Map

### 核心会改目录

- `README.md`
- `docs/architecture/`
- `docs/runbooks/`
- `docs/reference/`（新增）
- `docs/history/`（新增）
- `docs/archive/`（新增）
- `ops/cli/`
- `ops/scripts/remote/`
- `ops/scripts/onepanel/`
- `.codex/skills/`
- `.agents/skills/`
- `plugins/op-linux-control-plane/skills/`
- `tests/`

### 当前阶段只评估、不进入应用层改造的目录

- `infra/compose/newapi/`
- `infra/compose/sub2api/`
- `infra/compose/sub2apipay/`
- `infra/compose/chatgpt-register-v2/`
- `infra/compose/chatgpt-register-v2-prod2/`
- `infra/compose/vmail/`
- `templates/services/newapi*.example`
- `templates/services/sub2api*.example`
- `templates/services/sub2apipay*.example`
- `templates/services/chatgpt-register-v2*.example`

## Phase 0: 建立边界、工作区和测试拆分策略

**Files:**
- Modify: `docs/superpowers/plans/2026-03-31-op-linux-cli-first-repo-refactor.md`
- Modify: `tests/test_cli_entrypoints.py`
- Modify: `tests/test_docs_no_legacy_terms.py`
- Modify: `tests/test_wsl_first_docs.py`
- Modify: `tests/compose-template-layout.sh`
- Create: `tests/test_repo_snapshot_contracts.py`

- [x] **Step 1: 建立独立工作区并验证最小基线**

Run:

```bash
cd /root/work/OP_Linux
git worktree add .worktrees/codex-cli-first-repo-refactor -b codex/cli-first-repo-refactor-plan
cd /root/work/OP_Linux/.worktrees/codex-cli-first-repo-refactor
uv run python -m ops.cli --help
uv run python -m pytest tests/test_cli_entrypoints.py -q
```

Expected:
- worktree 创建成功
- CLI help 正常输出
- `tests/test_cli_entrypoints.py` 通过

- [ ] **Step 2: 把测试拆成三层合同**

目标层次：
- 公共合同：CLI 入口、错误 envelope、文档默认路径
- 兼容合同：legacy alias、compat path、compat projection
- 仓库快照：当前仓库中存在哪些历史对象

需要修改：
- `tests/compose-template-layout.sh` 只保留模板字段和结构合同
- 新建 `tests/test_repo_snapshot_contracts.py` 承接“文件仍存在”的快照类检查
- `tests/test_docs_no_legacy_terms.py` 缩小到 active 文档，不继续扫描所有历史文档

- [ ] **Step 3: 明确当前阶段不进入应用层**

要在计划和测试里一起固化：
- `infra/compose/<app>/` 与应用 env 模板本轮不删
- 相关测试改成“允许继续存在，但不视为仓库核心定位的一部分”

- [ ] **Step 4: 跑阶段验证**

Run:

```bash
cd /root/work/OP_Linux/.worktrees/codex-cli-first-repo-refactor
uv run python -m pytest tests/test_cli_entrypoints.py tests/test_docs_no_legacy_terms.py tests/test_wsl_first_docs.py -q
bash tests/compose-template-layout.sh
```

Expected:
- 公共合同类测试通过
- `compose-template-layout` 如果仍依赖 repo 实物，需在阶段总结中明确剩余问题

- [ ] **Step 5: 更新状态并写 Phase 0 总结**

更新：
- 本计划中的 `Global Status Board`
- 本阶段 checklist
- “Phase 0 Summary” 段落

### Phase 0 Summary

- [ ] 已填写

## Phase 1: 收敛入口与信息架构

**Files:**
- Modify: `README.md`
- Modify: `AGENTS.md`
- Modify: `docs/architecture/repo-layout.md`
- Modify: `docs/runbooks/prod0-main-sub2-control-plane-convergence.md`
- Create: `docs/architecture/README.md`

- [x] **Step 1: 收紧 README 只暴露正式资产**

处理目标：
- 只保留正式入口和活跃文档入口
- 把历史文档和阶段性专题从主导航移走
- 明确 `docs/reference/`、`docs/history/`、`docs/archive/` 未来位置

- [x] **Step 2: 简化或移除重复入口文档**

处理目标：
- `docs/architecture/repo-layout.md` 并入 `README.md` 后降为极短过渡/跳转页，后续再删除
- `AGENTS.md` 的项目内索引与 `README.md` 保持一致，不再双份扩写

- [x] **Step 3: 把已自认历史的 runbook 降级**

至少处理：
- `docs/runbooks/prod0-main-sub2-control-plane-convergence.md`

动作：
- 去掉主入口曝光
- 改到 `history/archive` 口径

- [x] **Step 4: 新建 architecture 索引页**

目标：
- 在 `docs/architecture/README.md` 中定义核心合同、reference、maintainers、history 的分层关系

- [x] **Step 5: 跑阶段验证**

Run:

```bash
cd /root/work/OP_Linux/.worktrees/codex-cli-first-repo-refactor
uv run python -m pytest tests/test_docs_no_legacy_terms.py tests/test_wsl_first_docs.py -q
```

- [x] **Step 6: 更新状态并写 Phase 1 总结**

### Phase 1 Summary

- [x] 已填写
- 已完成的工作：`README.md` 已收紧为正式资产和 active docs 的主入口，主导航移除了历史文档、阶段性专题和 host-specific runbook 的曝光，并明确了 `docs/reference/`、`docs/history/`、`docs/archive/` 的后续分层方向；`AGENTS.md` 的 Documentation Index 已收敛为双入口，只保留 `README.md` 和 `docs/architecture/README.md`；`docs/architecture/README.md` 已新建，并定义 `Core Contracts / Reference / Maintainers / History And Archive` 的信息架构；`docs/architecture/repo-layout.md` 已改成极短过渡/跳转页；`docs/runbooks/prod0-main-sub2-control-plane-convergence.md` 已降级为 archived historical runbook 口径，不再冒充当前正式入口。
- 这些工作如何对应“收敛入口与信息架构”：仓库主入口现在收敛到 `README.md -> docs/architecture/README.md` 的双层入口，正式资产、参考资料、维护者说明和历史归档的层次被明确拆开；历史过程文档和 host-specific 运行材料退出主导航，减少第二入口和重复索引，让读者先进入正式控制面，再按层次继续下钻。
- 还没解决什么：Phase 1 只完成了入口和分层骨架的收口，尚未开始 Phase 2 里 architecture 正文与 reference/archive 的进一步迁移，也还没有处理 active runbook 的 CLI-first 重写、`ops/scripts/*` 的职责收敛、skills/plugins pointer 层和 templates/inventory/ledger 的后续收口。
- 下一阶段从哪里开始：从 Phase 2 开始，继续按 `docs/architecture/README.md` 新定义的分层，把 architecture 正文中的核心合同、reference、maintainers、history/archive 内容进一步拆清，并推进旧页面的过渡或迁移。
- 补充说明：`docs/architecture/repo-layout.md` 本阶段采用的是过渡/跳转页，而不是直接删除，这是为了避免断链的稳妥处理。

## Phase 2: 收敛 architecture / reference / archive

**Files:**
- Modify: `docs/architecture/control-plane-methodology.md`
- Modify: `docs/architecture/control-plane-cli-contract.md`
- Modify: `docs/architecture/control-plane-task-entry-model.md`
- Modify: `docs/architecture/control-plane-inventory-ledger-model.md`
- Modify: `docs/architecture/control-plane-skill-contract.md`
- Modify: `docs/architecture/control-plane-governance-assets.md`
- Modify: `docs/architecture/automation-stack.md`
- Modify: `docs/architecture/linux-governance.md`
- Modify: `docs/architecture/onepanel-api-compatibility.md`
- Modify: `docs/architecture/app-delivery-versioning.md`
- Modify: `docs/architecture/1panel-v2.1.5-project.md`
- Create: `docs/architecture/control-plane.md`
- Create: `docs/maintainers/control-plane-authoring.md`
- Create: `docs/reference/onepanel-api-compatibility.md`
- Create: `docs/reference/app-delivery-versioning.md`
- Create: `docs/archive/architecture/1panel-v2.1.5-project.md`

- [x] **Step 1: 合并控制面六件套**

目标：
- `control-plane-methodology + cli-contract + task-entry-model + inventory-ledger-model` 合并为一份 `docs/architecture/control-plane.md`
- 保留旧文件一段过渡期时，旧文件只做跳转或 superseded 标记

- [x] **Step 2: 把维护者 authoring 规则迁出 architecture**

目标：
- 把 `control-plane-skill-contract` 和 `control-plane-governance-assets` 合并到 `docs/maintainers/control-plane-authoring.md`

- [x] **Step 3: 清掉 architecture 中的窄主题与历史快照**

目标：
- `onepanel-api-compatibility.md` 移到 `docs/reference/`
- `app-delivery-versioning.md` 移到 `docs/reference/`
- `1panel-v2.1.5-project.md` 移到 `docs/archive/architecture/`

- [x] **Step 4: 合并重复的运行基线说明**

目标：
- `automation-stack.md` 并入 `linux-governance.md` 或 `README.md`

- [x] **Step 5: 跑阶段验证**

Run:

```bash
cd /root/work/OP_Linux/.worktrees/codex-cli-first-repo-refactor
uv run python -m pytest tests/test_docs_no_legacy_terms.py tests/test_wsl_first_docs.py -q
```

- [x] **Step 6: 更新状态并写 Phase 2 总结**

### Phase 2 Summary

- [x] 已填写
- 已完成的工作：`docs/architecture/control-plane.md` 已成为控制面核心合同正文真源，长期方法论、CLI 合同、task-entry 模型和 `inventory / ledger` 投影已在同一处收口；`docs/maintainers/control-plane-authoring.md` 已承接 maintainer authoring 规则；`docs/reference/onepanel-api-compatibility.md` 与 `docs/reference/app-delivery-versioning.md` 已成为 reference 真源；`docs/archive/architecture/1panel-v2.1.5-project.md` 已承接历史架构快照；`automation-stack.md` 已降级为指向 `linux-governance.md` 的过渡 stub。
- 这些工作如何对应总体目标：architecture、reference、maintainer、archive 的边界已经收紧到仓库入口层可验证的事实。仓库根 `README.md` 与 `docs/architecture/README.md` 现在暴露同一组 core contracts，并分别指向 reference、maintainer 和 archive 的当前真源；`docs/runbooks/control-plane-domain-onboarding.md` 也已切到 `control-plane.md` 的统一锚点。旧 control-plane 分页与 `automation-stack.md` 不再作为核心入口暴露；`tests/test_docs_no_legacy_terms.py` 现已冻结这些入口链接与 active/formal docs 集合。
- 仍未解决的问题：Phase 2 完成的是长期合同与入口收口，尚未处理 Phase 3 的 active runbook CLI-first 重写与历史 runbook 迁移；`docs/history/` 目录本身尚未实化，当前 history 层仍由 `docs/superpowers/plans/` 和少量已降级 runbook 承接，后续需要在 Phase 3 继续收口。
- 下一阶段从哪里开始：从 Phase 3 开始，优先处理 active runbook 与历史 runbook 的边界，把仍留在 `docs/runbooks/` 的历史材料继续迁向 archive/history 口径，并把 active runbook 的正文入口统一切到 `ops.cli`。

## Phase 3: 收敛 active runbook 与历史 runbook

**Files:**
- Modify: `docs/runbooks/onepanel-app-lifecycle.md`
- Modify: `docs/runbooks/prod0-main-1panel-public-access.md`
- Modify: `docs/runbooks/prod2-main-1panel-public-access.md`
- Modify: `docs/runbooks/wsl-secrets-backup.md`
- Modify: `docs/runbooks/wsl-zzz-skills-sync.md`
- Modify: `docs/runbooks/onepanel-cli-validation-workflow.md`
- Modify: `docs/runbooks/app-project-delivery-workflow.md`
- Modify: `docs/runbooks/docker-host-runtime-packaging-template.md`
- Modify: `docs/runbooks/docker-app-onboarding-checklist.md`
- Modify: `docs/runbooks/prod0-main-openresty-certificate-management.md`
- Modify: `docs/runbooks/wsl-onepanel-api-fixtures.md`
- Create: `docs/archive/runbooks/prod0-main-8443-openresty-cutover.md`
- Create: `docs/archive/runbooks/prod0-postgres-app-resource-ops.md`
- Create: `docs/archive/runbooks/prod0-main-sub2-control-plane-convergence.md`

- [x] **Step 1: 重写 5 篇 active 第二控制面 runbook**

必须切到 CLI-first 的文档：
- `onepanel-app-lifecycle.md`
- `prod0-main-1panel-public-access.md`
- `prod2-main-1panel-public-access.md`
- `wsl-secrets-backup.md`
- `wsl-zzz-skills-sync.md`

要求：
- 主入口只能是 `ops.cli`
- 页面观察和 `api_request.py` 降为排障或 compat 说明

已完成：
- 上述 5 篇 active runbook 已按 CLI-first 口径回写，正文主入口统一回到 `uv run python -m ops.cli ...`
- 页面观察、fixture、`api_request.py` 和窗口期操作已降到排障、兼容或历史说明，不再充当正式入口

- [x] **Step 2: 合并重复 runbook**

至少处理：
- `wsl-onepanel-api-fixtures.md` -> 并入 `onepanel-cli-validation-workflow.md`
- `prod0-main-openresty-certificate-management.md` -> 并回 `prod0-main-1panel-public-access.md`
- `docker-app-onboarding-checklist.md` -> 并回 `app-project-delivery-workflow.md` 或 `docker-host-runtime-packaging-template.md`

已完成：
- `wsl-onepanel-api-fixtures.md` 的 active fixture 说明已并回 `onepanel-cli-validation-workflow.md`
- `prod0-main-openresty-certificate-management.md` 的 active 证书操作已并回 `prod0-main-1panel-public-access.md`
- `docker-app-onboarding-checklist.md` 的 active onboarding 口径已回收进 `app-project-delivery-workflow.md`，并同步收紧 `docker-host-runtime-packaging-template.md` 的边界

- [x] **Step 3: 归档历史窗口文档**

至少处理：
- `prod0-main-8443-openresty-cutover.md`
- `prod0-postgres-app-resource-ops.md`
- `prod0-main-sub2-control-plane-convergence.md`

已完成：
- 上述 3 篇窗口期 runbook 已迁到 `docs/archive/runbooks/` 口径，退出 active runbook 主路径

- [x] **Step 4: 记录本阶段最小验证边界**

Run:

```bash
cd /root/work/OP_Linux/.worktrees/codex-cli-first-repo-refactor
git status --short docs/runbooks docs/archive/runbooks
```

Expected:
- active runbook 与 archived runbook 的文件集合已经按本阶段目标分层
- `tests/test_docs_no_legacy_terms.py` / `tests/test_wsl_first_docs.py` 的统一回归继续并入后续 Phase 7 全仓验证

- [x] **Step 5: 更新状态并写 Phase 3 总结**

### Phase 3 Summary

- [x] 已填写
- 已完成的工作：本阶段已经把 `onepanel-app-lifecycle.md`、`prod0-main-1panel-public-access.md`、`prod2-main-1panel-public-access.md`、`wsl-secrets-backup.md`、`wsl-zzz-skills-sync.md` 重写为 CLI-first active runbook；把 `wsl-onepanel-api-fixtures.md` 的 active fixture 口径并回 `onepanel-cli-validation-workflow.md`；把 `prod0-main-openresty-certificate-management.md` 的 active 证书操作并回 `prod0-main-1panel-public-access.md`；把 `docker-app-onboarding-checklist.md` 的 active onboarding 内容回收进 `app-project-delivery-workflow.md`，并同步收紧 `docker-host-runtime-packaging-template.md` 的边界；同时把 `prod0-main-8443-openresty-cutover.md`、`prod0-postgres-app-resource-ops.md`、`prod0-main-sub2-control-plane-convergence.md` 归入 `docs/archive/runbooks/`。
- 这些工作如何对应总体目标：`docs/runbooks/` 的 active 层现在更接近“正式 CLI 运维入口”，窗口期 runbook、fixture 页面、证书专题页、onboarding checklist 不再继续充当第二控制面。也就是说，本阶段完成的是 runbook 面的收口，让正式命令面继续回到 `ops.cli`，同时把历史过程资产从主导航和 active 路径上剥离出去。
- 还没解决什么：本阶段只完成了文档收口，还没有进入 Phase 4 的 remote substrate、compat helper 和脚本语义下沉；`ops/scripts/onepanel/*`、`ops/scripts/remote/*` 仍然存在过渡态入口；更宽对象域的正式承接面还没有落到 `host / service / website / tenant / app / projection` 的 CLI 对象层里；文档相关测试的统一回归也还留在后续阶段。
- 下一阶段从哪里开始：从 Phase 4 开始，先把 Python remote substrate、`ops/scripts/remote/` 语义和 onepanel compat helper 的边界收紧。这个阶段的目标不是继续做文档瘦身，而是为后续 `host` 与 `service / website` domain 扩展提供稳定底座。

## Post-Refactor Expansion Roadmap

以下路线图是本 repo refactor 完成之后的后续承接面，不替代当前 Phase 4-7，也不与当前计划冲突。Phase 4-7 负责把仓库底座收紧；下面这些阶段负责在收紧后的底座上扩控制面对象域。

### Roadmap A: Host Domain Formalization

- 目标：把 `host` 从“runbook + helper + 临时脚本集合”升级为正式 CLI domain，显式覆盖 `host identity`、`ssh`、`firewall`、`ip address`、`filesystem / mounts`、`baseline`、`doctor`、`inventory-refresh`。
- 入口：基于 Phase 4 的 Python remote substrate 和正式远程执行链，把现有 `host ssh-secure verify/apply`、baseline 检查、inventory refresh 能力收束进 `ops.cli host` 的稳定对象模型。
- 最小成功标准：至少一个 host 可以通过统一 CLI 完成 `identity / ssh / firewall / ip / filesystem` 的 live-read、verify、apply，并把结果写回统一 `inventory / ledger / summary`。

### Roadmap B: Service And Website Lifecycle

- 目标：把 `postgres`、`redis`、`minio`、`nginx / openresty` 与 website object 纳入统一生命周期，而不是继续散落在 runbook、compose 文件和 1Panel helper 之间。
- 入口：基于现有 service module contract、Phase 4 的 substrate 收口和 Phase 6 的模板/投影边界，逐步建立 `ops.cli service` / `ops.cli website` 的 deploy、verify、backup、restore、reconcile 语义。
- 最小成功标准：至少一种 data service 和一种 website / edge service 完成从声明、验证、状态汇总到最小变更执行的统一路径。

### Roadmap C: Tenant / Resource / Database Object Domain

- 目标：让 `tenant`、`database`、`role`、`user`、`schema`、`bucket`、`policy`、`secret projection` 成为可组合的正式对象层，而不是继续隐含在脚本参数和 Markdown 说明里。
- 入口：在 Phase 6 收紧 `inventory / ledger / templates` 后，先为 PostgreSQL 与对象存储建立 resource object spec，再把 `tenant` 的 secret projection 和 resource ownership 接上统一对象图。
- 最小成功标准：至少覆盖一条数据库对象链和一条对象存储对象链，支持 `desired/live diff`、最小 apply、summary 和 secret projection 对齐。

### Roadmap D: Application Delivery Evolution

- 目标：在不破坏应用仓库边界的前提下，演进 `deploy/op/contract.yaml`、支持更多 runtime 类型，并把 `rollback / smoke / doc-sync / delivery summary` 统一成正式交付合同。
- 入口：以当前 `docs/runbooks/app-project-delivery-workflow.md`、`docs/reference/app-delivery-versioning.md` 和 `ops.cli app` 为基础，先冻结 contract schema 和 runtime capability registry，再推进交付链扩展。
- 最小成功标准：至少支持多于一种 runtime 类型，并且每次应用交付都具备 contract 校验、smoke 验证、rollback hook 和 doc-sync 输出。

### Roadmap E: Projection / Automation / Plugin Evolution

- 目标：把 `ledger / inventory / summary / versioning / skills / plugins / automation` 全部压成薄层 projection，避免仓库在扩域时重新长出第二控制面。
- 入口：依托 Phase 5 的 canonical skill metadata、Phase 6 的 projection boundary 和 Phase 7 的最终 relink，建立 “formal object state -> generated projection” 的统一链路。
- 最小成功标准：skills、plugins、automation、inventory summary、versioning summary 都可以从 canonical metadata 或 formal object state 派生，人工双写被压到最小。

## Phase 4: 收敛 remote 与 onepanel compat substrate，并为 host / service domain 预备 substrate

**Files:**
- Modify: `ops/cli/remote.py`
- Modify: `ops/cli/prod0_postgres_app_resource_audit.py`
- Modify: `ops/scripts/remote/run_remote_bash.sh`
- Modify: `ops/scripts/remote/prod0-postgres-app-resource-live-audit.sh`
- Modify: `ops/scripts/onepanel/api_request.py`
- Modify: `ops/scripts/onepanel/app_lifecycle.py`
- Modify: `ops/scripts/onepanel/project_lifecycle.py`
- Modify: `ops/scripts/onepanel/env_targets.py`
- Modify: `ops/cli/apps.py`
- Move: `ops/scripts/remote/example.sh`
- Move: `ops/scripts/remote/example-arg.sh`
- Create: `ops/scripts/internal/remote/`
- Modify: `docs/runbooks/powershell-wsl-remote-bash.md`
- Modify: `docs/runbooks/control-plane-legacy-migration.md`
- Modify: `tests/test_remote_cli.py`
- Modify: `tests/test_prod0_postgres_app_resource_audit.py`
- Modify: `tests/test_repo_snapshot_contracts.py`
- Modify: `tests/test_wsl_first_docs.py`
- Modify: `tests/test_app_cli.py`

- [x] **Step 1: 统一 Python remote executor 调用链**

目标：
- `tenant.py` 与后续 `host / service / website` 任务统一通过 Python remote substrate
- CLI 内部不再 shell 回 `run_remote_bash.sh`

- [x] **Step 2: 重定义 `ops/scripts/remote/` 目录语义**

目标：
- 目录内长期只保留：
  - `run_remote_bash.sh`
  - 文档 fixture
  - 少量尚未替代的 internal helper
- 示例与 helper-only 脚本迁往 `ops/scripts/internal/remote/`
- 为后续 `host baseline / doctor / inventory-refresh`、service lifecycle 和 website lifecycle 预留稳定装配点

- [x] **Step 3: 先吸收已有正式语义的脚本**

优先对象：
- `tenant audit-live`
- future `host / service / website` 对 substrate 的复用装配点

本阶段明确不做：
- `cleanup apply`
- `host ssh-secure verify/apply`
- `host baseline / doctor / inventory-refresh` 的公开对象层设计

- [x] **Step 4: 标记但不越界处理高风险专题脚本**

当前阶段只完成：
- 远端高风险专题脚本继续维持 internal/compat 过渡态，不进入行为重写
- `host / service / website` 后续对象层将直接复用本阶段收口出的 substrate
- 不进入应用层部署重构

- [x] **Step 5: 收敛 onepanel helper 的定位，不直接删除**

目标：
- 明确 `ops/scripts/onepanel/` 是实现包，不再扩展脚本式主入口
- `api_request.py` / `app_lifecycle.py` / `project_lifecycle.py` 统一改判为 `compat`
- `ops/cli/apps.py` 对旧 helper 的直接路径依赖，先改成有明确 compat 注释和替代路线
- `env_targets.py` 中 helper 绝对路径 contract 先保留，但在代码和文档中标记为过渡态

要求：
- 不直接删 compat helper
- 先改文档、调用方和测试口径，再考虑目录迁移
- `client.py` / `executor.py` / `object_api.py` / `verification.py` / `fixture_manager.py` / `ledger.py` 继续作为 onepanel CLI 的 internal 真源保留

- [x] **Step 6: 跑阶段验证**

Run:

```bash
cd /root/work/OP_Linux/.worktrees/codex-cli-first-repo-refactor
uv run python -m pytest tests/test_cli_entrypoints.py tests/test_wsl_first_docs.py -q
uv run python -m pytest tests/test_onepanel_env_targets.py tests/test_onepanel_plugin_and_skills.py -q
uv run python -m pytest tests/test_remote_cli.py tests/test_prod0_postgres_app_resource_audit.py tests/test_repo_snapshot_contracts.py tests/test_app_cli.py -q
```

- [x] **Step 7: 更新状态并写 Phase 4 总结**

### Phase 4 Summary

- [x] 已填写
- 已完成的工作：`ops.cli remote` 已提供仓库内部可复用的 Python substrate，`tenant audit-live` 已直接复用该 substrate；`ops/scripts/remote/` 已压回 transport/compat/internal 语义，示例脚本迁入 `ops/scripts/internal/remote/`；`ops/scripts/onepanel/` 的历史脚本入口已明确标为 compat helper，runbook 与 legacy migration 文档已同步改口。
- 这些工作如何对应总体目标：正式命令面不再回跳 shell wrapper，第二控制面的执行语义被压回 compat 层；同时 future `host / service / website` 已有统一的 remote substrate 和 onepanel internal 承接面可复用。
- 还没解决什么：`host / service / website` 公开对象层尚未建立；高风险专题脚本仍处在 internal/compat 过渡态；onepanel helper 仍未完成对象化替代。
- 下一阶段从哪里开始：从 Phase 5 开始，继续收敛 skills / plugins / pointer 层，把 canonical metadata 与派生层关系压薄。

## Phase 5: 收敛 skills / plugins / pointer 层，并建立 domain capability catalog

**Files:**
- Modify: `.codex/skills/`
- Modify: `.agents/skills/README.md`
- Modify: `plugins/op-linux-control-plane/README.md`
- Modify: `plugins/op-linux-control-plane/skills/`
- Modify: `tests/test_onepanel_plugin_and_skills.py`
- Create: `.codex/skills/catalog.yaml`
- Create: `scripts/` or `ops/scripts/automation/` generator helper if needed

- [x] **Step 1: 冻结 `.codex/skills/` 为唯一正文真源**

目标：
- 文档中明确：
  - `.codex/skills/` 可手工维护
  - `.agents/skills/` 是 pointer/stub
  - `plugins/.../skills/` 是分发层
- skill 元数据要能表达 `host / service / website / tenant / app / projection` 的 domain coverage

- [x] **Step 2: 收敛 `.codex` 内部 compat skill 重复**

优先处理：
- `onepanel-app-lifecycle`
- `openclaw-1panel`

要求：
- compat skill 只做 alias/router
- 不再维护完整命令摘要

- [x] **Step 3: 建立 skill catalog 和生成链**

目标：
- 从 canonical metadata 生成 `.agents` 指针层
- 从 canonical metadata 生成插件分组技能层
- canonical metadata 同时记录 domain、alias、入口命令、兼容态与投影来源

- [x] **Step 4: 加防漂移测试**

目标：
- 测试不再只验证“文件存在”
- 开始验证：
  - plugin group 覆盖域
  - aliases 一致
  - 无重复 group 归属
  - `host / service / website / tenant / app / projection` 覆盖关系与 catalog 一致

- [x] **Step 5: 跑阶段验证**

Run:

```bash
cd /root/work/OP_Linux/.worktrees/codex-cli-first-repo-refactor
uv run python -m pytest tests/test_onepanel_plugin_and_skills.py -q
```

- [x] **Step 6: 更新状态并写 Phase 5 总结**

### Phase 5 Summary

- [x] 已填写
- 已完成的工作：新增 `.codex/skills/catalog.yaml` 作为 canonical metadata，收口 `.agents/skills/*` 为固定格式 pointer/stub，并通过 `ops/scripts/automation/generate_skill_projections.py` 生成 plugin group skills；同时把 `onepanel-app-lifecycle`、`openclaw-1panel` 压成 compat router，并补齐 `.agents/skills/README.md`、`plugins/op-linux-control-plane/README.md` 的 generated 口径；另外把 `onepanel-openresty-site-migration` 从旧的 direct wrapper 指引切回 canonical `CLI-first` skill 路由。
- 这些工作如何对应总体目标：Phase 5 已把 skills / plugins / pointer 层压成“`.codex/skills/` 正文真源 + `catalog.yaml` 最小元数据 + `.agents` / plugin skills 派生层”的结构，避免 repo-local skills、plugin 分组层和 compat 层继续各自维护第二套命令摘要。
- 还没解决什么：`openclaw-1panel` 目录仍保留历史 direct-API 包资产与编译产物，它们已经被文案降级为 legacy compatibility package，但本阶段没有继续清理这些历史文件，也没有进入 `tenant` / `panel` 的 plugin group 扩面。
- 下一阶段从哪里开始：从 Phase 6 开始，继续收敛非应用层 `templates / inventory / ledger` 资产，并把 projection hook 压到更清晰的边界上。
- 该阶段完成后，skills / plugins / automation 应该具备“围绕正式 domain 做薄分发”的能力，而不是继续各自维护第二套命令摘要。

## Phase 6: 收敛 templates / inventory / ledger 的非应用层资产，并为更宽对象域保留 projection hook

**Files:**
- Modify: `templates/services/minio.env.example`
- Modify: `templates/services/postgres.env.example`
- Modify: `templates/services/redis.conf.example`
- Modify: `templates/services/onepanel-*.example`
- Modify: `templates/app-resources/*.example`
- Modify: `infra/compose/cliproxyapi/config.yaml`
- Modify: `infra/compose/redis/redis.conf`
- Modify: `inventory/servers/*/README.md`
- Modify: `inventory/servers/*/app_resources.md`
- Modify: `inventory/servers/*/ledgers/*.md`
- Modify: `tests/test_inventory_generation.py`

- [x] **Step 1: 先清 legacy 模板的双入口错觉**

优先处理：
- `templates/services/minio.env.example`
- `templates/services/postgres.env.example`
- `templates/services/redis.conf.example`

要求：
- 明确 canonical template
- legacy projection-only 模板降级或归档
- 模板命名和目录边界要能承接后续 `service / resource / secret projection` 扩展

- [x] **Step 2: 压缩 pointer 型配置文件**

目标：
- `infra/compose/cliproxyapi/config.yaml`
- `infra/compose/redis/redis.conf`

根据实际用途决定：
- 留 README 说明
- 留 template 指针
- 或转成生成产物
- 避免让配置样例再次变成未来 `host / service / tenant` 对象域的第二真源

- [x] **Step 3: 收紧 inventory/ledger 的 Markdown 投影**

目标：
- `.json` 继续作为机器真源
- `README.md` / `app_resources.md` / `ledgers/*.md` 只保留摘要层，不再承载第二真源
- 为后续 `database / bucket / policy / secret projection` 等对象保留统一 summary / ledger / projection 接口

- [x] **Step 4: 明确应用层资产继续延后**

在本阶段总结中再次写明：
- `infra/compose/newapi` 等目录仍保留
- 这些对象进入下一阶段应用层改造

- [x] **Step 5: 跑阶段验证**

Run:

```bash
cd /root/work/OP_Linux/.worktrees/codex-cli-first-repo-refactor
uv run python -m pytest tests/test_inventory_generation.py tests/test_prod0_audit.py tests/test_wsl_audit.py -q
```

- [x] **Step 6: 更新状态并写 Phase 6 总结**

### Phase 6 Summary

- [x] 已填写
- 该阶段完成后，需要能够说明：哪些模板和 ledger 已经只是 projection，哪些对象层可以继续安全扩展而不重新长出手工双写。
- 已完成的工作：继续把 `templates/services/minio.env.example`、`templates/services/postgres.env.example`、`templates/services/redis.conf.example` 固化为 projection-only 入口；`infra/compose/cliproxyapi/config.yaml` 与 `infra/compose/redis/redis.conf` 明确保持 pointer/placeholder 角色；同时把 `inventory/servers/*/README.md`、`app_resources.md`、`ledgers/*.md` 统一压成“机器真源在 JSON，Markdown 只保留非敏感摘要”的口径，并修正 `prod2-main` tenant ledger 不再泄漏 `_meta` / `infrastructure` / `tenants` 这类 registry 脚手架键。
- 这些工作如何对应总体目标：Phase 6 已把非应用层模板、pointer 配置和 inventory/ledger Markdown 从“可能被继续手工双写”的状态，收紧为“canonical template / tracked pointer / JSON 真源 / Markdown 投影”四种清晰角色，为后续 `service / resource / secret projection` 和更宽对象域扩展保留了单一机器真源边界。
- 还没解决什么：应用层 `infra/compose/newapi`、`infra/compose/sub2api`、`infra/compose/sub2apipay`、`infra/compose/chatgpt-register-v2*` 与对应应用模板仍刻意保留；`app-resources.json` 自身的对象域建模还没有继续抽象成更通用的 `resource / projection` 合同，本阶段只先收紧 Markdown 投影，不重写机器真源结构。
- 下一阶段从哪里开始：从 Phase 7 开始，做全仓最小回归、总状态盘点与交接说明，明确下一轮应优先从 `host / service / website / tenant / app / projection` 哪个对象域切入；本轮仍不进入应用层运行面。

## Phase 7: 全仓复核、阶段总结、交接到下一阶段扩展路线

**Files:**
- Modify: `docs/superpowers/plans/2026-03-31-op-linux-cli-first-repo-refactor.md`
- Modify: `README.md`
- Modify: `docs/architecture/README.md`
- Modify: `docs/history/index.md`
- Modify: `docs/archive/README.md`

- [x] **Step 1: 跑全仓最小回归**

Run:

```bash
cd /root/work/OP_Linux/.worktrees/codex-cli-first-repo-refactor
uv run python -m pytest tests/test_cli_entrypoints.py tests/test_docs_no_legacy_terms.py tests/test_wsl_first_docs.py tests/test_inventory_generation.py tests/test_onepanel_plugin_and_skills.py tests/test_onepanel_env_targets.py tests/test_secrets_host_layout.py -q
```

- [x] **Step 2: 对照总体目标做最终盘点**

至少核对：
- 正式入口是否只剩 `ops.cli`
- active 文档是否清掉第二控制面
- 历史资产是否退出主导航
- skills 是否只剩一个正文真源
- 非应用层资产边界是否变清晰
- `host / service / website / tenant / app / projection` 的扩展挂点是否已在架构与计划里明确写清

- [x] **Step 3: 写最终阶段总结**

必须包含：
- 本轮已完成的范围
- 本轮刻意未完成的范围
- 下一阶段从 `host / service / website / tenant / app / projection` 哪个方向起步

- [x] **Step 4: 如果本阶段已经过大，停止并提交当前变更**

Run:

```bash
cd /root/work/OP_Linux/.worktrees/codex-cli-first-repo-refactor
git status --short
git add README.md docs ops tests .codex .agents plugins
git commit -m "docs: add cli-first repository refactor plan"
```

如果不是最终完成态，也要写清：
- 下一会话从哪个 phase 开始
- 哪些验证已经通过
- 哪些子任务尚未开始

- [x] **Step 5: 更新总状态板**

### Phase 7 Summary

- [x] 已填写
- 已完成的工作：按 Phase 7 规定重新跑了全仓最小回归，结果为 `41 passed, 258 subtests passed`；同时补齐了 `docs/history/index.md` 与 `docs/archive/README.md`，把此前只在文案中提到、但尚未实化的 history/archive 导航变成真实索引页，并同步更新 `README.md` 与 `docs/architecture/README.md` 的入口说明。
- 这些工作如何对应总体目标：正式入口仍收口在 `uv run python -m ops.cli ...`；active 文档中的脚本入口已降为 compat/helper 语义；历史资产已退出仓库根主导航，改由 `docs/history/` 与 `docs/archive/` 索引承接；skills 继续保持 `.codex/skills/` 正文真源、`catalog.yaml` 元数据真源、`.agents`/plugin 只做派生层；非应用层 `templates / inventory / ledger` 也维持“canonical template / pointer / JSON 真源 / Markdown projection”边界。
- 本轮刻意未完成的范围：没有进入应用层运行面；`infra/compose/newapi`、`sub2api`、`sub2apipay`、`chatgpt-register-v2*` 及其应用模板仍按计划保留；也没有把 `host / service / website / tenant` 进一步对象化成新的正式 CLI 子域。
- 下一阶段建议从哪里开始：优先从 `host` 对象域切入，而不是 `app` 或继续做纯 `projection` 收尾。原因是仓库定位本来就是 Linux / WSL 主机与控制面治理，当前 CLI 已有 `audit / remote / network / secrets / onepanel firewall/panel` 等 host 相关能力，但仍分散在动作或兼容语义里，尚未形成显式 `host` 正式对象面；先把 `host identity / ssh / firewall / filesystem / baseline / doctor / inventory-refresh` 收口成统一对象域，能在不进入应用运行面的前提下，为后续 `service / website / tenant` 扩展提供更稳的宿主边界。
- 下一会话继续入口：从 `host` 对象域的 CLI 合同与文档入口开始，优先盘点 `audit`、`remote`、`network`、`secrets`、`onepanel-firewall`、`onepanel-panel` 这些现有能力里哪些应该上收成 host 正式对象命令，哪些继续保留为 substrate 或 compat helper。
- 提交状态说明：本阶段没有新增提交；当前工作树保留未提交改动，供下一会话直接在同一 worktree 上继续，不回滚、不覆盖现有脏树内容。
- 最终交接不只说明了“仓库已经瘦身到什么程度”，也明确了下一轮控制面扩展应从 `host` 对象域起步。

## Subagent Assignment Model

建议的并行拆分上限：`12` 个子代理。

### 固定分工

1. `architecture/README` 收口
2. `runbooks/active` 重写
3. `runbooks/archive` 迁移
4. `docs/superpowers -> history/archive` 迁移
5. `remote` transport/substrate
6. `onepanel` helper 边界
7. `skills canonical` 正文层
8. `plugin skill` 派生层
9. `tests` 合同拆分
10. `inventory/ledger` 摘要层
11. `templates` legacy/canonical 清理
12. `final verification + docs relink`

### 调度原则

- 每个子代理只处理一个 write scope
- 涉及共享文件时，先让 explorer 分析，再分配给单一 worker
- 主协调线程不直接写大量文件，只做：
  - 任务编排
  - 进度回写
  - review
  - verify
  - 阶段总结

## Next-Session Handoff Template

如果需要在新会话继续，直接复用下面这段摘要：

```text
继续执行 OP_Linux 的 CLI-first repository refactor 计划。
工作区固定在 /root/work/OP_Linux/.worktrees/codex-cli-first-repo-refactor
分支固定在 codex/cli-first-repo-refactor-plan
当前阶段只改 OP_Linux 仓库自身，不进入应用层。
先打开 docs/superpowers/plans/2026-03-31-op-linux-cli-first-repo-refactor.md
从第一个未完成的 Phase 开始；每完成一个 Phase，更新状态并补写该阶段总结。
所有文件改动优先交给子代理，主线程只负责调度、review、verify、阶段总结。
如果某一阶段任务过大，就在当前阶段末尾停止、提交，并记录下一会话入口。
```

## Current Snapshot

- [x] 独立 worktree 已创建：`/root/work/OP_Linux/.worktrees/codex-cli-first-repo-refactor`
- [x] 计划分支已创建：`codex/cli-first-repo-refactor-plan`
- [x] 最小基线已通过：
  - `uv run python -m ops.cli --help`
  - `uv run python -m pytest tests/test_cli_entrypoints.py -q`
- [x] 计划内已完成阶段：
  - `Phase 0`
  - `Phase 1`
  - `Phase 2`
  - `Phase 3`
- [x] 已完成多域分析：
  - architecture
  - runbooks
  - historical docs
  - remote layer
  - skills/plugins
  - templates/inventory boundary
  - contract tests
