# OP_Linux CLI-First Repo Refactor Phase 4 Substrate Design

**Date:** 2026-03-31

**Status:** Draft approved in conversation, pending written spec review

**Goal**

在不进入应用层运行面改造、也不提前建立 `host / service / website` 公开 CLI 骨架的前提下，完成 `Phase 4` 的底座承接：把正式 remote 执行链收回 Python CLI，把 `ops/scripts/remote/` 压回 transport/compat/internal 语义，把 `ops/scripts/onepanel/` 中的历史脚本入口降级为 compat helper，并为后续 `host / service / website` 正式对象层预留稳定 substrate。

## Background

当前 `OP_Linux` 已完成入口、architecture、runbook 的 CLI-first 收口，但 `Phase 4` 相关代码仍处于过渡态：

1. [ops/cli/remote.py](/root/work/OP_Linux/.worktrees/codex-cli-first-repo-refactor/ops/cli/remote.py) 已经提供正式 `remote bash` CLI，但正式调用方还没有统一复用它的 Python substrate。
2. [ops/cli/prod0_postgres_app_resource_audit.py](/root/work/OP_Linux/.worktrees/codex-cli-first-repo-refactor/ops/cli/prod0_postgres_app_resource_audit.py) 的 `audit-live` 仍然通过 `bash ops/scripts/remote/run_remote_bash.sh ...` 间接执行远端脚本，而不是直接调用 Python remote substrate。
3. [ops/cli/networks.py](/root/work/OP_Linux/.worktrees/codex-cli-first-repo-refactor/ops/cli/networks.py) 已经直接使用 Python SSH substrate，这说明仓库内部已经存在更接近目标形态的实现方向。
4. [ops/cli/apps.py](/root/work/OP_Linux/.worktrees/codex-cli-first-repo-refactor/ops/cli/apps.py) 仍然直接依赖 [ops/scripts/onepanel/app_lifecycle.py](/root/work/OP_Linux/.worktrees/codex-cli-first-repo-refactor/ops/scripts/onepanel/app_lifecycle.py) 这类脚本式入口，容易让 compat helper 继续被误认成正式主路径。
5. [ops/scripts/onepanel/env_targets.py](/root/work/OP_Linux/.worktrees/codex-cli-first-repo-refactor/ops/scripts/onepanel/env_targets.py) 已冻结远端绝对路径探测与 legacy fallback 合同，对现阶段仍是必要过渡能力，但尚未被明确标成 compat contract。
6. [ops/scripts/remote/](/root/work/OP_Linux/.worktrees/codex-cli-first-repo-refactor/ops/scripts/remote/) 当前混放 transport wrapper、示例脚本、专题 cutover 脚本和一次性历史资产，目录语义不清。

因此，`Phase 4` 的核心不是再做一轮文档瘦身，而是把“正式入口、substrate、compat、internal”四者的运行时边界拉直。

## Scope

本次设计只覆盖以下范围：

1. `ops.cli` 内部正式 remote 执行链收口。
2. `ops/scripts/remote/` 的 transport / compat / internal 目录语义收紧。
3. `ops/scripts/onepanel/` 历史脚本入口的 compat 定位和调用边界收紧。
4. 为未来 `host / service / website` 扩域预留稳定 substrate 和装配点。
5. 同步更新 runbook、legacy migration 说明和最小测试口径。

本次不做：

1. 不新增 `ops.cli host`、`ops.cli service`、`ops.cli website` 的公开子命令骨架。
2. 不重写应用层 `deploy/op/contract.yaml`，不进入应用运行面部署改造。
3. 不一次性替换全部 onepanel helper 为对象化实现。
4. 不重写证书、8443 cutover、data services 等高风险专题脚本。
5. 不删除仍被现场或测试依赖的 compat helper，只降级其定位。

## Decision Summary

本阶段采用“分层承接”方案，而不是强收口或仅改文档标记。

### Rejected Option A: 一次性强收口

不采用“一次性把 `tenant / apps / cleanup` 等调用全部切到新 substrate、并立即大规模迁移 remote 与 onepanel 脚本”的方案。原因是写集过宽，容易把 `Phase 4` 做成半次大重构，超出“先做底座承接”的边界。

### Rejected Option B: 只改文档与 compat 标记

不采用“主要修改文档、注释和测试口径，但保留现有正式调用链”的方案。原因是这无法真正消除第二控制面对正式命令面的侵蚀，`tenant audit-live` 等正式能力仍会继续依赖 shell wrapper。

### Chosen Option: 分层承接

采用“正式链路先收口，compat 资产降级，internal 承接面显式化”的方案：

1. 正式 CLI 先统一回到 Python remote substrate。
2. `run_remote_bash.sh` 保留为 compat passthrough，而不是继续参与正式链路设计。
3. `ops/scripts/remote/` 只先完成目录语义分层，不做高风险专题脚本重写。
4. `ops/scripts/onepanel/` 中脚本式入口统一降级为 compat helper，但 internal object layer 继续保留。
5. 未来 `host / service / website` 只复用本次整理出的 substrate，不在本阶段提前公开对象层。

## Target State

`Phase 4` 完成后，仓库内部应收敛为三层结构：

| Layer | Responsibility | Phase 4 Requirement |
|---|---|---|
| Formal CLI | `ops.cli` 正式命令面，供 runbook、skills、测试引用 | 正式命令不再绕回 shell compat wrapper |
| Substrate / Internal | Python remote executor、onepanel internal object layer、必要专题脚本 | 作为后续 `host / service / website` 的共用底座，但不对外冒充主入口 |
| Compat | `run_remote_bash.sh`、`api_request.py`、`app_lifecycle.py`、`project_lifecycle.py` 等历史脚本入口 | 明确保留为过渡入口，不再扩展为默认命令面 |

具体目标：

1. [ops/cli/remote.py](/root/work/OP_Linux/.worktrees/codex-cli-first-repo-refactor/ops/cli/remote.py) 成为 remote bash 执行真源，并提供可复用的 Python API。
2. [ops/cli/prod0_postgres_app_resource_audit.py](/root/work/OP_Linux/.worktrees/codex-cli-first-repo-refactor/ops/cli/prod0_postgres_app_resource_audit.py) 的 `audit-live` 改为直接调用 Python remote substrate，但继续执行现有 live audit 脚本。
3. [ops/scripts/remote/run_remote_bash.sh](/root/work/OP_Linux/.worktrees/codex-cli-first-repo-refactor/ops/scripts/remote/run_remote_bash.sh) 仅保留 compat passthrough 作用。
4. `ops/scripts/remote/` 不再混放 transport 入口、示例、专题 cutover 脚本。
5. [ops/cli/apps.py](/root/work/OP_Linux/.worktrees/codex-cli-first-repo-refactor/ops/cli/apps.py) 对 onepanel 脚本入口的依赖被显式标成 compat 依赖，并记录替代路线。
6. [ops/scripts/onepanel/env_targets.py](/root/work/OP_Linux/.worktrees/codex-cli-first-repo-refactor/ops/scripts/onepanel/env_targets.py) 的 legacy fallback 合同继续保留，但被文档和测试明确定义为 compat contract。

## Architecture

### 1. Formal Execution Chain

正式命令的运行时链路收敛为：

```text
ops.cli command
-> Python domain handler
-> Python remote substrate
-> ssh/local execution contract
-> internal script or internal onepanel object layer
-> structured payload / ledger / tests
```

本阶段的关键变化是：

1. 正式命令先落到 Python substrate，而不是先落到 shell wrapper。
2. compat wrapper 只服务旧 runbook、人工救援或过渡期调用。
3. internal 脚本仍可被正式命令复用，但不直接向文档和技能暴露为主入口。

### 2. Remote Substrate Contract

`ops/cli/remote.py` 除继续处理 CLI 参数外，还需要显式承接仓库内部的可复用执行合同。

这个 substrate 的最小输入模型应统一为：

1. `repo_root`
2. `target`
3. 远端脚本来源：`script_file` 或 `stdin`
4. 透传参数
5. `dry_run`

最小输出模型应统一为：

1. 结构化 payload
2. 远端命令显示形态
3. `stdout / stderr / returncode`
4. `transport` 元数据
5. operation ledger 记录

这样未来的 `host baseline`、`host doctor`、`service verify`、`website reconcile` 都可以只关心“执行什么”，而不需要重新发明 SSH、stdin、script-file、ledger 这套链路。

### 3. Remote Directory Semantics

`ops/scripts/remote/` 在 `Phase 4` 后只应继续承载三类东西：

1. transport wrapper，例如 `run_remote_bash.sh`
2. 少量仍由正式命令调用、但暂未对象化替代的 internal remote 脚本
3. 文档/测试 fixture

其余专题脚本应按下面原则处理：

1. 仍参与正式命令链但未完成对象化替代的脚本，开始向 `ops/scripts/internal/remote/` 收口。
2. 证书、8443 cutover、data services 等高风险脚本，本阶段只做 internal/compat 标记与迁移路线说明，不改变运行语义。
3. 示例脚本不再留在让人误解为正式能力目录的位置。

### 4. OnePanel Layering

`ops/scripts/onepanel/` 在 `Phase 4` 后必须分成两类：

#### Internal True Source

继续保留为 onepanel CLI internal 真源：

1. `client.py`
2. `executor.py`
3. `object_api.py`
4. `verification.py`
5. `fixture_manager.py`
6. `ledger.py`
7. 其他纯内部模块，例如 `compose_policy.py`

#### Compat Script Entrypoints

明确降级为 compat helper：

1. `api_request.py`
2. `app_lifecycle.py`
3. `project_lifecycle.py`
4. `env_targets.py` 中的绝对路径和 legacy fallback contract

`Phase 4` 的目标不是移除这些 compat helper，而是：

1. 不再把它们作为 runbook、skill、CLI 的默认推荐路径。
2. 在调用方和文档里明确它们是过渡层。
3. 让未来 `website` 或 `service` 对象层优先复用 internal object API，而不是继续从 compat 脚本入口扩能力。

## File-Level Design

### `ops/cli/remote.py`

需要完成两件事：

1. 继续保留 `remote bash` 的正式 CLI。
2. 抽出仓库内部可复用的 Python remote executor API，供 `tenant.py` 等正式模块直接调用。

本阶段不扩展新的公开 subcommand，只收口 Python 执行 substrate。

### `ops/cli/prod0_postgres_app_resource_audit.py`

`_prod0_live_audit_snapshot()` 改为直接调用 Python remote substrate，不再通过 `bash ops/scripts/remote/run_remote_bash.sh ...`。

本次仍然复用现有 [ops/scripts/remote/prod0-postgres-app-resource-live-audit.sh](/root/work/OP_Linux/.worktrees/codex-cli-first-repo-refactor/ops/scripts/remote/prod0-postgres-app-resource-live-audit.sh)，因此属于执行链收口，而不是专题脚本重写。

### `ops/cli/networks.py`

不要求大改，但它已经体现“直接使用 Python SSH substrate”的方向，应作为 `Phase 4` 的参考形态，保证新抽出的 remote substrate 不与现有网络治理链冲突。

### `ops/cli/apps.py`

当前对 `app_lifecycle.py` 的直接路径依赖先不完全拔除，但必须：

1. 明确注释这是 compat 调用。
2. 写清未来替代路线是 internal object API / 正式 CLI capability，而不是继续扩脚本入口。
3. 不让新增逻辑继续向 compat helper 倾斜。

### `ops/scripts/remote/run_remote_bash.sh`

保留，但只能作为 passthrough：

1. 参数和 stdin 转交给 `python3 -m ops.cli remote bash`
2. 不新增专题语义
3. 不再被仓库内部正式命令回调

### `ops/scripts/remote/` 与 `ops/scripts/internal/remote/`

本阶段会开始显式区分：

1. transport/compat 入口
2. internal remote helper
3. 示例/fixture

不要求一次性迁完全部专题脚本，但要求迁移方向和目录语义已经明确。

### `ops/scripts/onepanel/env_targets.py`

保留当前绝对路径探测和 `/opt/env_ubuntu/...` fallback，因为 [tests/test_onepanel_env_targets.py](/root/work/OP_Linux/.worktrees/codex-cli-first-repo-refactor/tests/test_onepanel_env_targets.py) 已冻结这一兼容合同。

但本阶段必须同时做两件事：

1. 在代码和文档里写清这属于 compat contract。
2. 避免其他新代码继续把该 fallback 当成长期正式真源。

## Error Handling

本阶段采用保守错误处理原则：

1. internal 脚本执行失败时，保留原始 `stderr`、`returncode` 和结构化失败结果，不增加掩盖性兜底。
2. compat helper 仍然存在时，必须显式说清是 compat，而不是伪装成正式能力。
3. legacy 路径 fallback 允许继续保留，但必须在代码和测试中被定义为“过渡合同”。
4. 高风险专题脚本本阶段只做边界标记和迁移路线说明，不在“顺手重写”中引入新风险。

## Verification

`Phase 4` 的最小验证分为三层：

### 1. Formal CLI Contract

验证正式入口仍可用，且 remote 链路没有断：

```bash
cd /root/work/OP_Linux/.worktrees/codex-cli-first-repo-refactor
uv run python -m pytest tests/test_cli_entrypoints.py tests/test_wsl_first_docs.py -q
```

### 2. Compat Contract

验证 onepanel 过渡合同仍被保留：

```bash
cd /root/work/OP_Linux/.worktrees/codex-cli-first-repo-refactor
uv run python -m pytest tests/test_onepanel_env_targets.py tests/test_onepanel_plugin_and_skills.py -q
```

### 3. Phase-4-Specific Contract

如实现中新增测试，应优先冻结以下事实：

1. 正式 CLI 调用链不再通过 `run_remote_bash.sh` 回跳。
2. compat helper 仍存在，但文档与调用方已不把其视为默认主入口。
3. `remote` substrate 的输出仍保持结构化，可被 ledger 和后续对象层复用。

## Implementation Boundaries

### Allowed In Phase 4

1. 抽取 Python remote substrate 的内部复用接口。
2. 迁正式调用方到该 substrate。
3. 调整 remote / onepanel 目录和注释，使 compat/internal/formal 边界清晰。
4. 修改 runbook、legacy migration 文档和相关测试口径。

### Explicitly Deferred

1. `ops.cli host` 的公开对象层与生命周期。
2. `ops.cli service` / `ops.cli website` 的公开对象层与生命周期。
3. 应用层部署重构与 `deploy/op/contract.yaml` 调整。
4. 证书、OpenResty cutover、data services 等高风险专题脚本的语义重写。
5. 全量 onepanel helper 对象化替代。

## Why This Unlocks Future Domains

本设计为未来对象域扩展提供的是“共用下半层”，而不是公开空壳入口：

1. `host` 未来可直接复用 target 解析、remote substrate、结构化结果和 ledger 记录。
2. `service` 未来可在同一 substrate 上叠加 service module contract 与 inventory/ledger 投影。
3. `website` 未来可复用 onepanel internal object layer，而不需要继续从 compat 脚本入口向外长。

换句话说，`Phase 4` 完成后，后续扩域会从“干净 substrate + 明确 compat/internal 边界”往上长，而不是一边保留旧脚本主路径，一边叠加新的对象层。
