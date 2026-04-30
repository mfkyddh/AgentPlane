---
status: active
owner: AgentPlane maintainers
last_verified: 2026-04-25
superseded_by: null
audience: agent
layer: technical
---

# 控制面核心合同

结论：`docs/architecture/control-plane.md` 是 `AgentPlane` 控制面核心合同的唯一正文真源。方法论、CLI 合同、task-entry 模型、inventory / ledger 投影模型的长期稳定内容统一维护在本文；专题步骤继续放在对应 runbook。

## 📋 范围

本文约束以下长期稳定事项：

- `AgentPlane` 的正式运维入口与控制面边界
- 面向 Agent 的任务入口模型与对象模型分层
- `inventory`、`ledger`、摘要回写与对账规则
- CLI 的命令形态、公共 flags、输出与错误合同

本文不承载以下内容：

- 单一专题的执行步骤
- 某次事故、迁移或变更的现场细节
- 兼容脚本的逐步操作手册

## 📖 核心术语

| 术语 | 含义 |
| --- | --- |
| `source of truth` | 某一类事实的正式真源 |
| `object` | 控制面中的稳定对象，如 `infra`、`app resource`、`app`、`ingress` |
| `task-entry` | 面向 Agent 的正式任务入口，不等价于底层对象 CRUD |
| `workflow` | 跨多个对象或多个阶段的正式编排动作 |
| `ledger` | 围绕某类对象或某次验证生成的机器派生记录 |
| `live state` | 通过现场命令、API、文件读取等方式获得的当前真实状态 |

## 📌 核心原则

### CLI-first

正式执行真源固定为 `agentplane ...`。新增能力时，先补正式 CLI，再补 skill、runbook、测试与索引。

`infra` 当前默认入口已经收口到 `agentplane infra ...`，公开动作固定为 `inventory`、`audit`、`cleanup`、`automation`、`network`、`remote bash`、`secrets`。其中 `automation` 已并入 `infra`，`network` 已并入 `infra`；`panel / firewall` 仍保留在 `onepanel` 域。

`infra` 内部按职责划分为 6 个子域：基座治理（inventory / audit / live-gate）、执行通道（remote bash）、安全配置（secrets）、网络治理（network）、周期调度（automation）、生命周期（cleanup）。子域边界用于文档分组和 help 组织，不改变 CLI 命令形态。

`service` 当前默认入口已经开放到 `agentplane service ...`，公开动作为 `search`、`get`、`verify`、`plan`、`apply`、`materialize`，以及 `service public-endpoint verify|plan|apply`。formal service 只接受 inventory 中已声明的受管运行服务对象；固定对象保留 `postgres`、`redis`、`minio`、`mihomo`、`onepanel_openresty`，同时扩展到 inventory 中声明且 `control_plane` 为 `compose`、`onepanel-app`、`onepanel-compose` 的 tracked runtime service。对外客户端交付物如 Clash Local Profile，应作为 service 附着产物由 `service materialize` 渲染；非 HTTP 公网端点的 DNS/证书续期对账应作为 service 附着事实由 `service public-endpoint` 处理，不再新开专题脚本域。`onepanel container / app / project` 已退出公开默认入口。

`ingress` 当前默认入口已经开放到 `agentplane ingress ...`，公开动作为 `search`、`get`、`verify`、`plan`、`apply`、`refresh-ledger`、`publish`。`ingress` 聚合 `inventory.services.public_ingresses` 与 provider live state 做公网入口对象核验；`ingress publish` 是 Cloudflare + 1Panel 公网入口的正式任务入口，继续以配置文件作为外部输入，不公开 raw onepanel / cloudflare 参数。非 HTTP 协议入口继续附着在 `service` 事实中，不进入 `ingress publish`。

`app resource` 当前默认入口已经开放到 `agentplane app resource ...`，第一版公开动作为 `search`、`get`、`verify`、`refresh-ledger`。第一版只负责 app resource declaration truth、secret scope 与 projection consistency 的正式对象校验；不进入应用运行时 env 投影，也不把 live 资源写面混入 `app resource verify`。

`app` 当前默认入口已经开放到 `agentplane app ...`，分成 `object`、`resource` 与 `delivery` 三面。`app object` 只负责 `inventory/apps/catalog.json` 中登记的 catalog object；`app resource` 只负责正式资源归属 truth 与 projection consistency 核验；`app delivery` 只负责合同、构建、部署、验证与回滚，不重新公开 raw installed-app CRUD。

`projection` 当前默认入口已经开放到 `agentplane projection ...`，统一承接 `runtime-env`、`verification`、`fixture`、`ledger` 四个 surface。`verification run` 包装只读验证套件，`fixture plan/apply/cleanup` 包装 WSL fixture 生命周期，`ledger refresh` 负责 ledgers 与 inventory 投影刷新；它们继续保持 `command=projection` 的正式输出合同。

`onepanel` 当前只保留 provider/debug 低层对象面：`panel`、`firewall`、`cronjob`、`task`。其余公开能力全部迁出到 `ingress`、`service`、`app`、`projection`；内部 object API 只作为 substrate，不充当公开命令面。`onepanel` 已从默认 `agentplane --help` 中隐藏，执行时输出调试警告，仅用于排查 provider 底层问题。

### Task-Entry First

Agent 的默认操作语言应是 `task-entry`，不是底层对象 CRUD、更不是 ad-hoc shell。对象模型回答“系统里有什么”，任务入口回答“Agent 该怎么做”。

### Skill Routing, Not Second Implementation

skill 负责路由正式入口、提示前置检查、说明验证与回写；skill 不得绕过 `agentplane.cli` 演化成第二实现。

### Live-State Verification

任何影响正式状态的动作，都必须把 `live state` 验证当成流程组成部分。现场验证结果优先级高于历史文档、旧台账与记忆性说明。

### Inventory / Ledger Projection

正式控制面不仅要执行，还要留下可回溯的机器派生记录。`inventory`、对象级 `ledger` 与应用摘要应形成稳定投影链，支撑对账、审计与后续回写。

### Runbook Boundary

runbook 负责专题步骤、人工接力点与风险解释，不承载第二份执行实现。根 `README.md` 与 `AGENTS.md` 只做稳定导航，不堆专题细节。

### Path Policy: 逻辑路径优先

tracked truth 只保存与平台无关的**逻辑路径**，例如 `apps/<app>`、`apps/<app>/contracts/<target>`、`inventory/servers/<target>/inventory.json`。Windows 盘符、WSL UNC、`/mnt/...`、`/root/...` 这类**物理路径**只能出现在 runtime resolution 或 verification evidence 中。

resolver / backend 可以把逻辑路径解析成当前宿主可访问的 `resolved_path`（物理路径），但 `resolved_path` 不是 tracked truth。`ledger` 可以保存稳定摘要，`verification` 才允许记录现场观察值（含物理路径）。

> 详见 [control-plane-naming-registry.md](../reference/control-plane-naming-registry.md)

### Automation And Projection Boundary

`infra automation` 管“何时执行、执行什么周期任务”；`projection` 管“执行后如何验证并把机器证据写回结构化投影”。二者都不替代 `app delivery`、`service` 或 `ingress` 的业务执行。

标准协作顺序：

1. 先完成业务动作。
2. 需要周期任务时，进入 `agentplane infra automation ...`。
3. 需要状态投影回写时，进入 `agentplane projection verification ...` 或 `projection ledger refresh ...`。
4. 人类摘要与文档同步只消费投影结果，不反向充当真源。

## 🛠️ CLI 合同

### Command Shape

目标命令形态：

```bash
agentplane <domain> <surface> <verb> [flags]
```

其中：

- `<surface>` 可以是 `object`，也可以是更高层的任务面或工作流面
- 新增能力时优先向统一语法收敛，不继续扩大旧命名差异
- 内部执行资产、raw shell 只能作为实现层或现场诊断手段，不是第一命令面

### Verbs

对象面优先复用以下 verbs：

- `search`
- `get`
- `plan`
- `apply`
- `verify`
- `refresh-ledger`

工作流面优先复用以下 verbs：

- `suite`
- `run`
- `fixture`
- `onboard`
- `migrate`
- `doctor`

### Common Flags

所有正式控制面命令应尽量复用以下公共 flags：

- `--target` 或 `--env`
- `--repo-root`
- `--json`
- `--write`
- `--dry-run`
- `--execute`

约束如下：

1. `--dry-run` 与 `--execute` 互斥。
2. `--json` 代表结构化输出，不代表跳过验证。
3. `--write` 只用于写回 tracked 派生产物，如 `inventory`、`ledger`、文档摘要。
4. `--repo-root` 默认当前仓库根，但在跨工作树或跨仓库场景下必须可显式指定。

### Output Contract

统一要求如下：

1. 机器可解析结果写 `stdout`。
2. 诊断、提示、警告、身份、计划说明与错误摘要写 `stderr`。
3. 默认文本模式面向人类；`--json` 模式面向 Agent、插件与自动化。
4. 文本模式与 JSON 模式必须共享同一语义，只改变表现形式，不改变结果含义。

### Error Envelope

目标错误 envelope：

```json
{
  "ok": false,
  "error": {
    "code": "onepanel.object_not_found",
    "hint": "use search first",
    "message": "website token not found"
  },
  "payload": null,
  "evidence": [],
  "artifacts": []
}
```

最低要求：

- `ok`
- `error.code`
- `error.message`
- `error.hint`
- `payload`
- `evidence`
- `artifacts`

错误码应带域名前缀，避免跨域含义冲突。

### Object Surface And Workflow Surface

适合声明式对象面的场景：

- 对象边界稳定
- 选择器稳定
- 动作集合清晰
- 结果可验证
- 输入输出可结构化

典型对象：

- `infra`
- `app resource`
- `app`
- `service`
- `ingress`
- `panel`
- `cronjob`
- `inventory-record`

当前边界快照：

| 域 | 管什么 | 不管什么 |
| --- | --- | --- |
| `ingress` | 公网入口对象与发布任务 | provider/debug 原生对象 |
| `service` | 受管运行服务对象与稳定运行态操作 | raw provider id/name、未登记对象 |
| `app` | catalog object 与正式交付流程 | 运行态 restart/reconcile |
| `projection` | runtime-env、verification、fixture、ledger | 业务真源对象 |
| `onepanel` | 1Panel provider/debug 对象，仅保留 panel、firewall、cronjob、task | 正式 website/service/app/projection 入口 |

适合工作流面的场景：

- 跨主机
- 多阶段切换
- 依赖现场判断
- 失败补偿复杂
- 人工接力点明确存在

典型动作：

- `migrate`
- `repair`
- `bootstrap`
- `cutover`
- `doctor`

## 🎯 任务入口模型

### Definition

`task-entry` 是面向 Agent 的正式任务入口，应满足以下特征：

1. 名称表达任务结果，而不是底层实现。
2. 输入优先使用稳定业务引用，而不是随机 ID 或临时文件路径。
3. 内部可以解析并操作多个对象。
4. 输出必须是 Agent 可继续消费的稳定结果。

### Relationship With Objects

`object` 是控制面真实资源，`task-entry` 是围绕结果组织的正式操作语言。

- `object` 回答“系统里有什么”
- `task-entry` 回答“下一步该怎么做”

好的控制面不是让 Agent 直接操纵容器、证书文件或配置片段，而是让稳定入口去编排对象。

### Recommended Public Task Families

| 域 | 目标 | 建议公开动作 |
| --- | --- | --- |
| `infra` | 基础设施治理（主机、网络、Secrets、自动化） | `baseline`、`ssh-secure`、`mount-data`、`inventory-refresh` |
| `infra` | 跨服务基础设施组件 | `network-ensure`、`volume-ensure`、`firewall-apply`、`secret-project` |
| `service` | 单服务生命周期 | `restart`、`reconcile`、`verify` |
| `app resource` | app resource 真源与投影校验 | `bind-secret`、`registry-verify`、`ownership-audit` |
| `projection` | 派生产物与薄层投影 | `runtime-env-plan`、`runtime-env-verify`、`verification-run`、`fixture-plan`、`ledger-refresh` |
| `ingress` | 公网入口与站点对象 | `publish`、`reconcile`、`origin-verify` |
| `app` | 应用交付合同与正式切换 | `build-delivery`、`ship`、`deploy`、`rollback`、`smoke` |

### Input And Output

输入原则：

1. 优先使用稳定引用，如 `target`、`app_id`、`website alias`。
2. 高风险动作必须有风险表达和显式确认阶段。
3. 输入必须能映射回真实对象。

输出至少应包含：

- 规范化对象引用
- 当前状态或结果状态
- 可继续执行的下一步引用
- `warning`
- `evidence` 或 `artifacts`

### What Should Be Public

适合公开的入口应同时满足：

- 高频
- 高价值
- 合同稳定
- 风险边界清晰
- 存在最小验证路径

只适合内部 helper 的动作通常具有以下特征：

- 只是中间步骤
- 用户很少单独调用
- 缺少前置上下文就不安全

## 📊 投影模型

### Three Projection Layers

| 层级 | 作用 | 回答的问题 |
| --- | --- | --- |
| Host Inventory | 目标环境的正式非敏感台账 | 该 `target` 受管对象有哪些、摘要状态是什么、对象 ledger 在哪里 |
| Object Ledgers | 对象级验证、搜索、计划、执行或报告结果 | 最近一次验证结果是什么、证据来自哪里、需要回写哪些摘要 |
| App Summaries | 面向应用项目或主机摘要的非敏感结果 | 当前正式口径是什么、哪些对象已验证、哪些待人工跟进 |

### Minimum Key Model

每个对象记录至少应具备以下字段：

- `target`
- `kind`
- `name_or_alias`
- `source_of_truth`
- `status`
- `last_verified_at`
- `evidence_refs`
- `owned_by`

可选扩展字段：

- `artifacts`
- `warnings`
- `last_operation_id`

### Source-Of-Truth Rules

1. `live state` 优先级最高。
2. 正式 `inventory` 是受管对象与摘要真源。
3. `ledger` 是机器派生证据，不替代 `inventory` 总表。
4. runbook 与 README 负责解释规则，不作为事实真源。
5. tracked truth 不写宿主访问路径；宿主观察值只进入 runtime resolution 或 verification evidence。

### Refresh And Write-Back Order

推荐顺序如下：

1. 执行正式命令。
2. 验证 `live state`。
3. 刷新对象级 `ledger`。
4. 将必要摘要投影回 `inventory`。
5. 在需要时更新应用摘要或主机摘要生成区块。

## ✅ 必须遵守的规则

1. 正式入口必须写成 `agentplane ...`。
2. 新增能力前必须先定义：对象、任务入口、输入、输出、验证与回写位置。
3. Agent 不得把底层文件改动、脚本调用或 ad-hoc shell 当成默认控制面。
4. 所有写操作都必须具备至少一种正式验证路径。
5. 高风险写命令必须将计划阶段与执行阶段分开。
6. `inventory` 与 `ledger` 必须服务事实回写，不能只做展示。
7. runbook 只能解释正式流程，不能变成实现副本。
8. 新文档、新 skill、新测试都必须与本文术语和边界对齐。

## ⚠️ 反模式

常见反模式：

- 把内部执行资产长期维持为第一入口
- 让 skill 直接拼 SSH、Docker、API 调用并跳过 `agentplane.cli`
- 用 runbook 代替正式控制面
- 让 `inventory` 长期靠手工维护
- 让 Agent 直接围绕底层对象 CRUD 思考，而没有任务级入口
- 只更新文档、不更新 `ledger` 或必要的 `inventory` 摘要

禁止行为：

1. 禁止把 raw shell、远端脚本或临时命令描述成正式主路径。
2. 禁止让多个文档对同一真源给出冲突定义。
3. 禁止在 skill 中复制整段 runbook 步骤。
4. 禁止只实现 `apply` 而没有计划阶段或验证阶段。
5. 禁止在没有正式证据的情况下写入“已验证”状态。

## 💻 命令示例

当前正式入口示例：

```bash
agentplane --help
agentplane infra inventory <target> --repo-root <repo-root>
agentplane infra audit <target> --repo-root <repo-root>
agentplane infra automation search <target> --repo-root <repo-root>
agentplane infra network audit <target> --repo-root <repo-root>
agentplane infra remote bash <target> -- whoami
agentplane infra secrets sync-layout <target> --repo-root <repo-root>
agentplane service search --target <target> --repo-root <repo-root>
agentplane service verify --target <target> --name <service> --repo-root <repo-root>
agentplane ingress search --target <target> --repo-root <repo-root>
agentplane ingress verify --target <target> --alias <alias> --repo-root <repo-root>
agentplane ingress publish plan --target <target> --config-file <config-file> --cloudflare-env-file <cloudflare-env-file> --repo-root <repo-root>
agentplane app resource search --target <target> --repo-root <repo-root>
agentplane app resource verify --target <target> --app <app> --repo-root <repo-root>
agentplane projection runtime-env plan --target <target> --app <app> --repo-root <repo-root>
agentplane projection verification run --target <target> --profile <profile> --repo-root <repo-root>
agentplane projection fixture plan --target <target> --profile <profile> --repo-root <repo-root>
agentplane projection ledger refresh --target <target> --repo-root <repo-root> --write
agentplane onepanel --env <target> panel get --json
```

说明：

- `infra` 当前公开动作包括主机 inventory、审计、cleanup、automation、网络治理、远端 Bash 与主机 secrets。
- `automation` 已并入 `infra`，`network` 已并入 `infra`；`panel / firewall` 仍保留在 `onepanel` 域。
- `service` 当前默认入口已经开放到 `agentplane service ...`。
- formal service 只接受 inventory 中已声明的受管运行服务对象。
- `onepanel container / app / project` 已退出公开默认入口。
- `ingress` 第一版以 `inventory.services.public_ingresses` 为声明真源，正式对象面独立于 `onepanel website` 原生 API。
- `ingress publish` 是 Cloudflare + 1Panel 公网入口的正式任务入口。
- `app resource` 第一版以正式 declaration truth 为对象基线，正式对象面只覆盖 app resource 真源与 projection 校验；`app resource audit-live` 等历史专题动作不属于 `app resource v1` 默认对象入口。
- `projection` 已不止 `runtime-env`，还包括 `verification`、`fixture`、`ledger`。
- `onepanel` 只保留 provider/debug 低层对象面：`panel`、`firewall`、`cronjob`、`task`。

目标命令形态示例：

```bash
agentplane ingress verify --target <target> --alias <alias> --json
agentplane ingress plan --target <target> --alias <alias> --operation reconcile --json
agentplane ingress publish plan --target <target> --config-file <config-file> --cloudflare-env-file <cloudflare-env-file> --repo-root <repo-root>
agentplane app object get --target <target> --app <app> --repo-root <repo-root> --json
agentplane app delivery deploy --target <target> --app <app> --repo-root <repo-root> --dry-run --json
agentplane app delivery verify --target <target> --app <app> --repo-root <repo-root> --execute --json
agentplane projection verification run --target <target> --profile <profile> --repo-root <repo-root>
agentplane projection fixture plan --target <target> --profile <profile> --repo-root <repo-root>
agentplane projection ledger refresh --target <target> --repo-root <repo-root> --write
```

## Related Documents

- [control-plane-authoring.md](../maintainers/control-plane-authoring.md)
- [control-plane-naming-registry.md](../reference/control-plane-naming-registry.md)
- [control-plane-agent-execution-flow.md](../runbooks/control-plane-agent-execution-flow.md)
- [linux-governance.md](linux-governance.md)
- [agentplane-app-collaboration.md](agentplane-app-collaboration.md)
