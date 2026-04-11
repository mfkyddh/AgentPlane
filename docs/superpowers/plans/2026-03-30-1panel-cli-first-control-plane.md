# 1Panel CLI-First Control Plane Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 完成 OP_Linux 面向 1Panel `v2.1.7` 的 CLI-first 控制面重构，使对象 CLI、skills、插件、secrets 真源、台帐投影和应用协作流程收口到统一模型。

**Architecture:** 真实执行入口固定为 `uv run python -m ops.cli ...`。`ops/scripts/onepanel/` 负责 API/对象适配，skills 只做“何时用哪个 CLI”的路由，repo-local 插件只做参数分组、JSON 结果展示和团队分发。对象操作按 `search/get/plan/apply/verify/refresh-ledger` 收口，台帐由 host inventory 向对象 ledgers 投影并回写主机摘要。

**Tech Stack:** Python 3, `uv`, `pytest`, 1Panel `v2.1.7`, repo-local Codex skills/plugin scaffolds, tracked JSON/Markdown ledgers.

---

## Context

- 当前工作树：`/root/work/OP_Linux`
- 当前分支：`master`
- 1Panel 源码基线：`/root/github/1Panel`
- 上游版本：`v2.1.7`
- 当前 commit：`6e052b8ef`（`/root/github/1Panel`）

## Scope

本轮计划覆盖这些子目标：

1. 统一 `ops.cli onepanel` 对象入口和输出/错误模型
2. 让对象 CLI、skills、插件都回到 `CLI-first`
3. 建立 host-first secrets 到旧路径的兼容投影
4. 建立对象台帐与主机摘要投影
5. 为 WSL 1Panel fixture、prod2 兼容验证、prod0 审计保留明确路径

## Completed So Far

- [x] `/root/github/1Panel` 已同步到 `v2.1.7`
- [x] WSL 本地 1Panel 已从 `v2.1.5` 升级到 `v2.1.7`
- [x] 新增 1Panel 共享执行/对象层：
  - `ops/scripts/onepanel/executor.py`
  - `ops/scripts/onepanel/object_api.py`
  - `ops/scripts/onepanel/ledger.py`
- [x] `ops.cli onepanel` 已扩成对象化入口：
  - `panel`
  - `website`
  - `container`
  - `firewall`
  - `cronjob`
  - `app`
  - `project`
  - `task`
  - `ledger`
  - `ingress`
- [x] 默认输出已改为简洁文本，插件/自动化可用 `--json`
- [x] 基础稳定错误码已落地：
  - `onepanel.invalid_json`
  - `onepanel.invalid_request`
  - `onepanel.object_not_found`
  - `onepanel.api_failed`
  - `onepanel.command_failed`
- [x] `ledger refresh --write` 会：
  - 写 `inventory/servers/<host>/ledgers/*.json|md`
  - 回写 `inventory.json` 的 `object_ledgers`
  - 更新主机 `README.md` 的生成区块
  - 关联最近 onepanel CLI 操作
- [x] host-first secrets 投影命令已落地：
  - `uv run python -m ops.cli secrets sync-host-layout --target <target> --repo-root /root/work/OP_Linux --write`
- [x] 新的 CLI-first skills 已创建
- [x] 旧的 1Panel skills 已改成兼容入口
- [x] repo-local 插件骨架和 marketplace 已创建
- [x] 插件对象分组 skills 已补齐
- [x] `app/project/container` 已支持低风险 `plan/apply/verify` 闭环
- [x] `firewall` 已接入正式 API 子集：
  - `hosts/firewall/base`
  - `hosts/firewall/search`
  - `hosts/firewall/operate`
- [x] 已新增 `onepanel suite run`，把 WSL/prod2/prod0 的标准验证流程沉到仓库 CLI
- [x] `suite run --write-report` 可把验证结果写入 `inventory/servers/<env>/ledgers/verification-<profile>.json|md`
- [x] WSL 真实 API 凭据已接入本地 secrets：
  - `secrets/hosts/wsl/onepanel/api.env`
- [x] 已完成真实 WSL 验证：
  - `uv run python -m ops.cli onepanel --env wsl --json panel get`
  - `uv run python -m ops.cli onepanel --env wsl --json suite run --profile wsl-fixture --write-report`
  - `uv run python -m ops.cli onepanel --env wsl ledger refresh --write`
- [x] 1Panel 持久化产物已统一脱敏：
  - `suite` 报告文件
  - `ledger refresh` 生成的对象台帐
  - `inventory.json` 的 `object_ledgers` 投影
- [x] 远端 onepanel API 路径已补兼容探测：
  - 优先 `/opt/op_linux/...`
  - 回退 `/opt/env_ubuntu/...`
- [x] `suite run --write-report` 现在即使遇到真实不兼容也会写出失败报告
- [x] 已新增 `onepanel fixture` 编排层：
  - `fixture plan`
  - `fixture apply`
  - `fixture cleanup`
- [x] `wsl-fixture` 已具备 profile 默认 selector：
  - website alias: `oplinux-fixture`
  - project: `oplinux-fixture`
  - container: `oplinux-fixture-web`
  - cronjob: `oplinux-fixture`
- [x] 已完成真实 `prod0-main` 只读审计：
  - `uv run python -m ops.cli onepanel --env prod0-main panel get`
  - `uv run python -m ops.cli onepanel --env prod0-main suite run --profile prod0-readonly --write-report`
  - `uv run python -m ops.cli onepanel --env prod0-main ledger refresh --write`
- [x] 已完成真实 `prod2-main` 只读兼容验证与报告回填：
  - `uv run python -m ops.cli onepanel --env prod2-main suite run --profile prod2-readonly --write-report`
  - `uv run python -m ops.cli onepanel --env prod2-main ledger refresh --write`
- [x] 已完成 `prod0-main` / `prod2-main` 文档与审计口径收口：
  - `prod0-main` 明确定位为面向 `v2.1.7` 的升级前预检面，当前 live 实测版本固定为 `v2.1.6`
  - `prod2-main` 明确把 `project/app` 失败项记录为预期审计差异，而不是现场故障单
  - 通用 validation workflow 已明确 `verification-*.json|md` 属于 generated machine reports

## Current Design Decisions

- `CLI-first` 是硬规则，skills 和插件都不能成为第二真源。
- 人类用户默认看文本输出；程序化消费者只消费 `--json`。
- `plan` 和 `apply --execute` 必须分离。
- 写操作完成后必须跟 `verify`，随后 `refresh-ledger`。
- `firewall` 在未确认稳定 1Panel API 前继续 inventory-backed。
- `prod0-main` 仍保持升级前兼容审计，不作为本轮高风险执行目标。

## Problems Encountered

### 1. `onepanel` 默认输出与计划不符

- 现象：最初 `ops.cli` 默认输出就是 JSON，不适合人工日常运维。
- 处理：已改成默认文本 + `--json` 显式结构化输出。
- 状态：已解决。

### 2. ledgers 只写对象文件，没有继续投影

- 现象：最初 `refresh-ledger` 只生成 `ledgers/*.json|md`，无法形成主机摘要闭环。
- 处理：已增加 `inventory.json` 的 `object_ledgers` 投影和 `README.md` 的生成区块。
- 状态：已解决。

### 3. 旧 1Panel skills 仍会把人带回旧入口

- 现象：旧 skill 保留旧脚本路径或直接 API 的叙述，容易继续分叉。
- 处理：已把旧 skill 改写成兼容路由入口，明确回到 `uv run python -m ops.cli ...`。
- 状态：已解决。

### 4. 对象 CLI 能力不均衡

- 现象：最初 `container/app/project` 只有读/校验，没有统一写闭环。
- 处理：已基于 `v2.1.7` 源码确认并接入：
  - `apps/installed/op`
  - `containers/compose/operate`
  - `containers/operate`
- 状态：部分解决。

### 5. `firewall` 一直停留在 inventory-backed

- 现象：虽然 1Panel `v2.1.7` 已提供正式 host firewall API，但仓库实现仍只读本地 inventory。
- 处理：已基于源码确认并接入：
  - `POST /api/v2/hosts/firewall/base`
  - `POST /api/v2/hosts/firewall/search`
  - `POST /api/v2/hosts/firewall/operate`
- 状态：已解决最小正式子集。

### 5. 插件只有骨架，没有对象分组入口

- 现象：只有 manifest/marketplace，缺少可分发的对象分组 skills。
- 处理：已补 `plugins/op-linux-control-plane/skills/*/SKILL.md`
- 状态：已解决基础分组层。

### 6. 真实验证报告把 `apiKey` 等敏感字段原样写入 ledgers

- 现象：`suite run --write-report` 会把 `panel get` 的完整 payload 持久化到 `verification-*.json`，导致真实 `apiKey` 落盘。
- 处理：已新增 onepanel 持久化脱敏层，只对写入文件的报告和对象台帐生效，CLI 现场输出保持原样。
- 状态：已解决。

### 7. 远端 onepanel 控制面根目录存在双轨

- 现象：`prod0-main` 的真实 onepanel API env 与 `api_request.py` 位于 `/opt/env_ubuntu/...`，而代码原先只硬编码 `/opt/op_linux/...`。
- 处理：已把远端目标解析改成优先探测 `/opt/op_linux`，不存在时回退 `/opt/env_ubuntu`。
- 状态：已解决。

### 8. `suite run` 遇到真实不兼容时直接中断，无法回填失败报告

- 现象：`prod2-readonly` 在 `project` / `app` 检查失败时直接异常退出，无法留下现场报告。
- 处理：已改成逐项采集，失败项写 `ok=false` 与错误消息，仍继续写入 `verification-*.json|md`。
- 状态：已解决。

### 9. `prod2-main` 的现场对象分布与 runbook 预设不一致

- 现象：
  - `project`: `compose project not found: sub2api-prod`
  - `app`: `installed app search returned no items`
- 说明：
  - `sub2api` 当前在 `prod2-main` inventory 中登记为 OP_Linux `compose` 应用，而不是 1Panel `apps/installed` 对象。
  - 真实 `prod2-main` 现场可读取 `panel` / `website` / `container` / `firewall` / `task`，但当前 `prod2-readonly` 预设的 `project/app` 探针不会得到 `ok=true`。
- 状态：已确认并已落盘到失败报告，待后续统一对象边界说明。

### 10. WSL `cronjob search` 的排序字段与 `v2.1.7` 校验器不兼容

- 现象：真实 WSL 调 `cronjob search` 时返回 `PageCronjob.OrderBy` 校验失败。
- 根因：仓库实现传的是 `created_at`，而 `v2.1.7` 要求 `createdAt`。
- 处理：已修正对象 API helper 和测试。
- 状态：已解决。

### 11. WSL fixture website 创建依赖 `openresty` 已安装 runtime

- 现象：真实 WSL 执行 `website apply` 会返回 `record not found`。
- 根因：1Panel 创建 website 时会先查 `openresty` installed app；当前 WSL `app search` 中没有 `openresty`。
- 处理：已把该前置条件显式写入 `fixture plan/apply`，现在会返回 `blocked-missing-openresty`，而不是把原始 500 直接冒给操作者。
- 状态：已确认并已记录为当前 WSL fixture 的现场阻塞。

## Remaining Risks And Gaps

- [x] WSL 1Panel fixture 已具备真实创建 / 回收 CLI 路径
- [x] `suite run` 仍是 read-only 标准验证，不负责 fixture 创建/回收
- [ ] WSL fixture 首次 `apply` 若遇到历史残留 `oplinux-fixture-web` 容器名冲突，仍需先执行一次 `fixture cleanup --execute` 回到基线后再重跑
- [ ] `inventory.json` / `README.md` 的对象台帐投影还可以继续统一化
- [ ] 关联应用仓库的迁移回归（如 `new-api`、`sub2api`、`sub2apipay`）尚未全部串完

## External Blockers

- 当前已无 `prod0-main` / `prod2-main` 只读连接阻塞：
  - 真实 SSH 与 onepanel API 调用均已打通
- WSL 侧已不再阻塞：
  - `wsl-fixture` 真实 API 验证已可执行并已完成

## Verification Snapshot

最近通过的 onepanel 相关回归：

```bash
cd /root/work/OP_Linux
uv run python -m pytest tests/test_cli_entrypoints.py tests/test_onepanel_object_cli.py tests/test_onepanel_plugin_and_skills.py tests/test_onepanel_app_lifecycle.py tests/test_onepanel_project_lifecycle.py tests/test_onepanel_env_targets.py tests/test_onepanel_public_ingress.py tests/test_secrets_host_layout.py -q
```

结果：

- `60 passed, 18 subtests passed`

新增通过的脱敏与验证回归：

```bash
cd /root/work/OP_Linux
uv run python -m pytest tests/test_onepanel_object_cli.py tests/test_onepanel_verification_suite.py tests/test_onepanel_public_ingress.py tests/test_onepanel_env_targets.py -q
```

结果：

- `26 passed`

新增通过的真实 WSL 验证：

```bash
cd /root/work/OP_Linux
uv run python -m ops.cli onepanel --env wsl --json panel get
uv run python -m ops.cli onepanel --env wsl --json suite run --profile wsl-fixture --write-report
uv run python -m ops.cli onepanel --env wsl ledger refresh --write
```

结果：

- WSL 面板版本：`v2.1.7`
- `wsl-fixture`：`ok=true`

新增通过的目标解析与失败报告回归：

```bash
cd /root/work/OP_Linux
uv run python -m pytest tests/test_onepanel_env_targets.py tests/test_onepanel_verification_suite.py tests/test_onepanel_object_cli.py tests/test_onepanel_app_lifecycle.py tests/test_onepanel_project_lifecycle.py tests/test_onepanel_public_ingress.py -q
```

结果：

- `35 passed, 3 subtests passed`

新增通过的 fixture / profile 回归：

```bash
cd /root/work/OP_Linux
uv run python -m pytest tests/test_onepanel_fixture_manager.py tests/test_onepanel_object_cli.py tests/test_onepanel_verification_suite.py -q
```

结果：

- `26 passed`

新增完成的真实 `prod0-main` 审计：

```bash
cd /root/work/OP_Linux
uv run python -m ops.cli onepanel --env prod0-main --json panel get
uv run python -m ops.cli onepanel --env prod0-main suite run --repo-root /root/work/OP_Linux --profile prod0-readonly --firewall-tab port --write-report
uv run python -m ops.cli onepanel --env prod0-main ledger refresh --repo-root /root/work/OP_Linux --write
```

结果：

- 真实面板版本：`v2.1.6`
- `prod0-readonly`：`ok=yes`

新增完成的真实 WSL fixture 编排验证：

```bash
cd /root/work/OP_Linux
uv run python -m ops.cli onepanel --env wsl --json website apply --alias oplinux-fixture --domain oplinux-fixture.local --proxy http://127.0.0.1:18880 --group-id 1 --execute
uv run python -m ops.cli onepanel --env wsl --json fixture plan --profile wsl-fixture --repo-root /root/work/OP_Linux
uv run python -m ops.cli onepanel --env wsl --json fixture apply --profile wsl-fixture --repo-root /root/work/OP_Linux --execute
uv run python -m ops.cli onepanel --env wsl --json suite run --profile wsl-fixture --write-report
uv run python -m ops.cli onepanel --env wsl --json fixture cleanup --profile wsl-fixture --repo-root /root/work/OP_Linux --execute
uv run python -m ops.cli onepanel --env wsl ledger refresh --repo-root /root/work/OP_Linux --write
```

结果：

- `website apply`：真实 `/api/v2/websites` v2 `domains` payload 已打通，不再返回 500 空体
- `fixture apply`：清理历史残留容器后可成功创建 / 拉起 project，并启用 cronjob
- `suite run`：`wsl-fixture` 真实结果 `ok=true`
- `fixture cleanup`：project 被 down 到 `runningCount=0`，cronjob 被禁用，website 保留复用
- 已知现场细节：若首次 `fixture apply` 命中旧容器名冲突，先执行一次 `fixture cleanup --execute` 再重跑即可回到可复用基线

新增完成的真实 `prod2-main` 兼容验证：

```bash
cd /root/work/OP_Linux
uv run python -m ops.cli remote bash prod2-main
uv run python -m ops.cli onepanel --env prod2-main suite run --repo-root /root/work/OP_Linux --profile prod2-readonly --website-alias token --container-name sub2api-prod --project-name sub2api-prod --app-name sub2api --write-report
uv run python -m ops.cli onepanel --env prod2-main ledger refresh --repo-root /root/work/OP_Linux --write
```

结果：

- 真实面板版本：`v2.1.7`
- `prod2-readonly`：`ok=no`
- 失败项：
  - `project`: `compose project not found: sub2api-prod`
  - `app`: `installed app search returned no items`

## Next Execution Order

- [x] Task 1: 提交当前已完成的 CLI/skills/plugin/ledger 基础改动
- [x] Task 2: 把 WSL 1Panel fixture 从 runbook 提升到可执行 smoke/regression 套件
- [x] Task 3: 为 `firewall` 找到并验证 `v2.1.7` 正式 API 路径，或明确保留 inventory-backed 边界
- [x] Task 4: 在真实 `prod2-main` / `prod0-main` 上执行 suite 并回填报告
- [x] Task 5: 把对象台帐继续投影到更统一的 host summary / app 协作文档
- [x] 已补 `prod0-main` 升级预检口径、`prod2-main` 预期审计差异说明与通用 validation workflow 注释
- [ ] Task 6: 为 fixture 创建/回收补齐可执行脚本和测试
  - 当前已完成 profile/CLI/测试与 project+cronjob live 验证
  - website fixture 仍受 `openresty` runtime 缺失阻塞

## Update Rule

本文件作为本轮工作的持续记录：

- 每完成一个关键子目标，更新 `Completed So Far`
- 每发现一个新的实现/验证问题，更新 `Problems Encountered`
- 每跑一次新的完整回归，更新 `Verification Snapshot`
