---
status: active
owner: AgentPlane maintainers
last_verified: 2026-04-02
superseded_by: null
---

# 1Panel API 合同

本文是 `AgentPlane` 的 `1Panel` API reference 真源。本文只定义长期稳定的对象覆盖、错误模型与 CLI/plugin 接口约束，不展开具体操作步骤或 host 级 runbook。

## Baseline

- Upstream source mirror: `/root/github/1Panel`
- Target API baseline: `v2.1.7`
- AgentPlane runtime principle: `CLI-first`
- 正式执行入口: `agentplane onepanel ...`

## Supported Targets

- `wsl`
  - Primary API regression and fixture environment.
  - Preferred local env source: `secrets/hosts/wsl/onepanel/api.env`
  - Projection env path: `secrets/services/onepanel-api.wsl.env`
- `prod2-main`
  - Live API validation target for `v2.1.7`.
  - Reads and low-risk idempotent writes may be validated here after WSL passes.
- `prod0-main`
  - Upgrade-prep audit target.
  - Default posture in this phase is read-only API inspection.

## Object Coverage

| Object | CLI Scope | Status | Primary Backing |
| --- | --- | --- | --- |
| Panel | `onepanel panel` | supported | `core/settings/search`, `core/settings/update` |
| Website | `agentplane.cli ingress ...` | supported through ingress domain | `websites/search`, `websites/:id`, `websites/:id/https`, `websites` |
| Container | provider-internal / service domain | supported for read/verify + low-risk op plan/apply | `containers/search`, `containers/info`, `containers/operate` |
| Cronjob | `onepanel cronjob` | supported | `cronjobs/search`, `cronjobs/load/info`, `cronjobs*` mutation paths |
| App | provider-internal / app delivery domain | supported for read/verify + low-risk op plan/apply | `apps/installed/search`, `apps/installed/info/:id`, `apps/installed/op` |
| Project | provider-internal / app delivery domain | supported for read/verify + op plan/apply | `containers/compose/search`, `containers/compose/operate` |
| Task Center | `onepanel task` | supported for read/verify | `logs/tasks/search`, `logs/tasks/executing/count` |
| Firewall | `onepanel firewall` | supported for base/search/verify + low-risk op plan/apply | `hosts/firewall/base`, `hosts/firewall/search`, `hosts/firewall/operate` |
| Ledger | `projection ledger refresh` / object `refresh-ledger` | supported | tracked inventory + app resource registry |

## Object / Workflow / Projection Boundary

- 对外 `onepanel` 对象域：`panel|firewall|cronjob|task`
- Website、app、project、container 与 ledger 通过各自 formal domain 或 provider-internal object API 承接，不再作为公开 `onepanel` scope。
- 任务域：`projection fixture ...` 与 `projection verification run ...`
- 投影链：`live state -> verification-<profile>.json|md -> object ledgers -> host README/runbook`

补充约束：

- `fixture` 只用于 WSL 可回收测试面，不扩展成 live host 第二控制面。
- `suite run` 保持只读；机器报告是审计证据，不自动等价于服务故障单。
- `ledger refresh --write` 负责把对象投影刷新到 tracked ledgers 与 inventory，不要求人手维护。

## API Rules

- Skills and plugins must never construct signed 1Panel HTTP requests themselves.
- Python modules under `agentplane/scripts/onepanel/` are provider substrate, not public script entrypoints. The signed request helper is `signed_request.py` and is invoked only by repository-owned providers.
- Human operators should default to concise CLI text output; plugins and automations should append `--json` and reuse the CLI result model directly.
- New object support should first land in WSL, then validate on `prod2-main`, then be considered for `prod0-main`.
- When a stable 1Panel API is unavailable or unverified, AgentPlane may temporarily read from tracked inventory, but that boundary must be documented explicitly.
- `plan` and `apply` remain separate states. `apply` must not execute unless `--execute` is present.
- `projection verification run` remains read-only. Any WSL fixture mutation must go through `agentplane projection fixture ...`.
- On targets such as `prod2-main`, `suite run` may be used as a live API audit even when some selectors intentionally do not resolve to 1Panel-native objects. A persisted failure report is valid audit evidence, not automatically a service-health failure.

## Error Model

Current stable CLI error codes include:

- `onepanel.invalid_json`
- `onepanel.invalid_request`
- `onepanel.object_not_found`
- `onepanel.api_failed`
- `onepanel.command_failed`

Plugins and automations should branch on `error.code`, not on free-form message text.

## Plugin Direction

- Repo-local plugin root: `plugins/agentplane-control-plane`
- Marketplace entry: `.agents/plugins/marketplace.json`
- Plugin skills group by control-plane object, but the plugin stays thin:
  - parameter collection
  - CLI dispatch
  - JSON result display
- Skills and plugin groups must map back to `agentplane onepanel ...` or adjacent AgentPlane CLI commands instead of becoming a second control-plane implementation.

## WSL Fixture Expectations

The WSL 1Panel test environment should keep a profile-backed recyclable fixture set for CLI and plugin validation:

- one proxy website object
- one compose project
- one cronjob
- one isolated test env file
- one cleanup path that can soft-reset the above safely through `onepanel fixture cleanup`

Active workflow and fixture lifecycle now live in [../runbooks/onepanel-cli-validation-workflow.md](../runbooks/onepanel-cli-validation-workflow.md).
