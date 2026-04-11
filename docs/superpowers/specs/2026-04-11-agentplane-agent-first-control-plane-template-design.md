# AgentPlane Agent-First Control Plane Template Design

**Date:** 2026-04-11

**Status:** Approved for implementation planning

## Goal

把 `AgentPlane` 从“当前作者自用的控制面仓库”收敛成“面向 Agent 的控制面模板仓库”。

长期目标不是发布一组宿主相关脚本，而是提供一个可 fork 的控制面模板，让使用者只需要：

1. fork / clone 仓库；
2. 填写本地私密数据；
3. 让 Agent 通过 formal CLI 读取 truth、执行动作、校验结果、回写投影。

本设计必须同时满足以下约束：

- Git 保存正式真源，`secrets/` 保存本地私密数据。
- Agent 是主要操作者，人类用户默认只做最少量的私密数据填写。
- 正式入口保持 `uv run python -m agentplane.cli ...`。
- Skill 只调用正式 CLI，不派生第二控制面。
- 默认执行拓扑固定为“本地控制面 + 本地 Linux backend + SSH 远端”。
- Windows 默认通过 `WSL` 提供本地 Linux backend。
- Linux 默认直接作为本地 Linux backend。
- macOS 默认通过本地 shell + 一个显式的 Linux backend provider 工作；不再假设 macOS 本机直接承担 Linux Docker 语义。
- Truth、ledger、verification 必须显式分层，运行态观察结果不能污染真源。

## Background

当前仓库已经具备：

- 一套可运行的 Python CLI；
- 一部分 host / service / website / app / projection formal surface；
- Windows 主控制面迁移的初步抽象；
- 一套以 `inventory/`、`docs/`、`.codex/skills/` 为核心的控制面工作树。

但它仍然带着明显的“单作者现场仓库”特征：

- 大量 active 文档、skill、规则仍然默认 `/root/work/AgentPlane`。
- 多处命令虽然名义上支持 Windows，但执行时仍直接依赖本机 `bash`、`docker`、`curl`、`python3`。
- catalog / ledger / object 输出里已经开始泄露宿主相关路径，例如 `\\wsl.localhost\...`。
- `inventory`、`ledgers`、`verification` 的边界仍不够清晰，部分 observed state 会反向污染 tracked 数据。
- 当前 bootstrap 更像“作者知道怎么操作的工作习惯”，而不是“别人 fork 后就能用的模板入口”。

如果继续沿着宿主环境逐点补兼容，会快速演化成：

1. 领域逻辑到处散落宿主特判；
2. Windows / Linux / macOS 行为持续分叉；
3. Git 真源混入作者现场路径；
4. 开源后使用者必须理解你的个人环境，难以真正复用。

## Problem Statement

要把 `AgentPlane` 做成可开源、可 fork、面向 Agent 的控制面模板仓库，当前必须同时解决五类问题：

1. **真源问题**
   - Git 中保存的内容必须是 canonical truth，而不是某台机器的访问路径。

2. **执行问题**
   - 领域层必须只表达动作意图，不能继续直接拼 `bash -lc`、`docker`、`ssh`、`wsl.exe`。

3. **解析问题**
   - 同一逻辑对象必须在 Windows、Linux、macOS 上解析成各自可访问的路径，但外部合同仍保持同一个 canonical ref。

4. **模板问题**
   - fork 用户默认不是控制面作者本人，不能要求他们理解当前现场目录、迁移史和大量手工步骤。

5. **Agent 问题**
   - 既然 Agent 是主要操作者，正式 CLI 和仓库结构就必须面向 Agent 设计，而不是面向人类随手 shell。

## Non-Goals

- 本设计不要求本轮直接完成全部代码改造。
- 本设计不要求保留现有的兼容入口或兼容输出。
- 本设计不尝试把 AgentPlane 变成“无仓库状态的纯 CLI 工具”。
- 本设计不把 live discovery 升格为真源；仓库 truth 仍然是正式源。
- 本设计不把 Docker 变成 build machine；应用产物仍遵守 `Artifact-First`。
- 本设计不要求人类用户理解全部内部抽象；人类默认只需要填写 secrets 和极少量 target identity。

## Decision Summary

采用“Agent-first template repository”方案，而不是“跨平台脚本集合”方案。

长期标准如下：

1. `AgentPlane` 是一个可 fork 的控制面模板仓库。
2. Git tracked 内容只保存正式真源、模板、规则、文档、技能和投影产物。
3. 本地私密数据只保存在 `secrets/`，不提交 Git。
4. 领域模型与宿主执行彻底分层。
5. 所有正式动作都先编译成统一执行计划，再交给 backend runner。
6. CLI 输出同时区分：
   - canonical truth / ref
   - resolved host path / evidence
7. active 文档和 repo-owned skills 只描述 formal CLI 与模板约定，不再默认作者现场路径。

## Architecture

### 1. Layer Model

长期架构拆成六层：

| 层 | 责任 | 对外产物 |
| --- | --- | --- |
| `Truth Layer` | 声明目标对象与正式意图 | tracked truth files |
| `Secret Layer` | 保存本地敏感数据 | local-only secret files |
| `Resolution Layer` | 将逻辑引用解析成宿主可访问对象 | resolved paths / bindings |
| `Execution Layer` | 执行动作 | execution results |
| `Observation Layer` | 产出验证证据和投影 | ledgers / verification reports |
| `Agent Surface` | 给 Agent 的正式命令面 | formal CLI JSON contract |

关键原则：

- 真源只在 `Truth Layer`。
- 私密数据只在 `Secret Layer`。
- 宿主差异只在 `Resolution Layer` 和 `Execution Layer`。
- 运行观察结果只在 `Observation Layer`。
- Agent 只能通过 `Agent Surface` 工作。

### 2. Truth Layer

Git 真源必须只表达真实意图，不表达当前宿主如何访问。

建议长期结构：

- `inventory/catalog/apps.yaml`
- `inventory/targets/<target>/truth/host.yaml`
- `inventory/targets/<target>/truth/services.yaml`
- `inventory/targets/<target>/truth/apps.yaml`
- `inventory/targets/<target>/truth/websites.yaml`
- `inventory/targets/<target>/truth/automations.yaml`
- `inventory/targets/<target>/truth/network.yaml`

这些 truth 文件中允许出现：

- `target`
- `service_key`
- `app`
- `contract_ref`
- `secret_ref`
- `runtime_kind`
- `depends_on`
- `public_endpoint`

这些 truth 文件中禁止出现：

- `D:\...`
- `/root/...`
- `\\wsl.localhost\...`
- `/mnt/c/...`
- 任意由某一宿主机推导出来的“当前访问路径”

### 3. Secret Layer

`secrets/` 是本地真实私密数据目录，不承担领域真源职责。

建议结构：

- `templates/secrets/local/control-plane/*.example`
- `templates/secrets/targets/<target>/*.example`
- `templates/secrets/apps/<app>/*.example`
- `secrets/local/control-plane/...`
- `secrets/targets/<target>/...`
- `secrets/apps/<app>/...`

Truth 里只出现 `secret_ref`，例如：

- `local/control-plane/cloudflare`
- `targets/prod0-main/ssh`
- `apps/sub2api/runtime-env`

解析后的实际 secret path 只能在运行时出现，不能反写进 truth。

### 4. Resolution Layer

这是宿主无关性的核心层。

必须引入以下正式对象：

- `HostProfile`
  - 当前宿主机 OS、backend provider、tool capability、path policy
- `WorkspaceResolver`
  - 解析 control repo、app repo、artifact staging、private root
- `SecretResolver`
  - 把 `secret_ref` 解析成当前宿主可访问文件
- `TargetResolver`
  - 解析 target 对应的 SSH、backend、host truth 和 execution policy

Resolution Layer 的核心输出必须同时包含两类值：

1. `canonical_ref`
2. `resolved_path`

例如 `sub2api` 的合同：

- `canonical_ref`: `apps/sub2api/contracts/prod0-main`
- `resolved_path` on Windows: `\\wsl.localhost\Ubuntu\root\work\sub2api\deploy\agentplane\contract.yaml`
- `resolved_path` on Linux: `/root/work/sub2api/deploy/agentplane/contract.yaml`

CLI 和 ledger 不得把 `resolved_path` 错当作 `canonical_ref`。

### 5. Execution Layer

所有正式动作必须先编译成统一 `ExecutionPlan`，再由 backend runner 执行。

最小字段：

- `backend_type`
- `cwd_ref`
- `argv`
- `env_refs`
- `input_refs`
- `expected_outputs`
- `capabilities`
- `timeout`

支持的 backend 固定为：

- `linux-native`
- `windows-wsl`
- `macos-lima`
- `ssh-linux`

说明：

- `windows-wsl` 是 Windows 的正式本地 Linux backend。
- `linux-native` 是 Linux 的正式本地 backend。
- `macos-lima` 表示 macOS 需要一个显式 Linux backend provider，而不是把 Linux Docker 语义偷偷放在 macOS 本机里。
- `ssh-linux` 用于远端主机动作。

领域层禁止直接执行：

- `bash`
- `docker`
- `curl`
- `python3`
- `ssh`
- `wsl.exe`

这些都只能由 backend runner 负责。

### 6. Observation Layer

必须明确区分：

- `truth`
- `ledger`
- `verification`

约束如下：

1. `truth`
   - 正式真源
   - 只能由受控 plan/apply 改写

2. `ledger`
   - 结构化投影
   - 反映 truth 的可消费摘要
   - 可以从 truth 计算生成
   - 不应反向引入宿主机路径噪声

3. `verification`
   - 运行时证据
   - 允许携带宿主机实际观察值
   - 不得直接回写为 truth

因此：

- refresh ledger 只刷新 projection
- verify 只刷新 evidence / report
- observed runtime path 不得写回 truth 或 canonical ledger fields

### 7. Agent Surface

所有正式 surface 必须统一为：

- `search`
- `get`
- `verify`
- `plan`
- `apply`

所有 Agent-facing 命令必须满足：

- 默认 JSON 输出
- 稳定 exit code
- 非交互
- 幂等
- 可重复执行

Agent 不能依赖 repo 内部脚本路径；repo 内部脚本只能作为 backend 实现细节。

## Repository Template Model

开源后的仓库产品形态，不是“一个命令工具箱”，而是“一个控制面模板”。

fork 用户面对的默认操作应该收敛为：

1. clone/fork 仓库；
2. 运行本地 inspect/bootstrap；
3. 填写 `secrets/`；
4. 让 Agent 接管。

因此模板仓库必须自带：

- truth schema
- app catalog schema
- target schema
- secrets template
- bootstrap command
- doctor command
- active runbook
- repo-owned skills

其中，fork 用户不应该被要求理解：

- 旧迁移历史
- 作者个人目录布局
- 临时兼容逻辑
- 非正式脚本入口

## Bootstrap Model

长期 bootstrap 只保留四个正式动作：

- `bootstrap inspect-local`
- `bootstrap init-secrets`
- `bootstrap verify-secrets`
- `bootstrap doctor`

职责如下：

1. `inspect-local`
   - 检测当前宿主机 profile
   - 输出 backend provider、workspace binding、path policy

2. `init-secrets`
   - 按模板生成本地 secrets 空壳
   - 不填充敏感值

3. `verify-secrets`
   - 校验必填 secret 是否完整
   - 不输出 secret 明文

4. `doctor`
   - 汇总当前仓库能否被 Agent 接管

人类默认只需要处理 bootstrap 和 secret 填写，不需要直接操纵 domain 动作。

## Compatibility Policy

本路线不以“兼容旧现场”为长期目标。

允许的唯一短期兼容原则是：

- 在迁移阶段，为了完成 phased rollout，可以保留临时桥接实现；
- 但每一阶段的终点都必须减少一类兼容路径，而不是继续积累新的兼容层。

长期目标是：

- truth 不保留旧路径口径
- active docs 不保留旧入口口径
- repo-owned skills 不保留旧执行习惯
- CLI 输出不保留宿主污染字段

## Risks

### Risk 1: 宿主路径继续污染 tracked data

如果 catalog、ledger、object output 继续把宿主解析路径写进 Git，仓库就不再是模板，而是某台机器的现场快照。

处理方式：

- 统一 `canonical_ref` / `resolved_path` 模型；
- 为 truth 和 ledger 增加 host path gate tests。

### Risk 2: backend 抽象只停留在部分命令

如果只有少数命令使用 backend runner，而其他动作继续直接调 shell，平台分叉仍会持续。

处理方式：

- 所有 Linux 动作统一走 `ExecutionPlan`；
- 领域层直接执行 shell 的行为视为违约。

### Risk 3: fork 用户仍需要理解作者现场

如果 bootstrap 不能收敛成“填 secrets 即可”，开源模板仍然不可用。

处理方式：

- 收紧 bootstrap surface；
- 用模板和 doctor 替代 runbook 里的人工迁移知识。

### Risk 4: observation 继续反向修改 truth

如果 verification / live discovery 继续改写 truth，就会让 Agent 行为失去可预测性。

处理方式：

- truth、ledger、verification 三层硬隔离；
- 明确每个 surface 的写入边界。

## Success Criteria

满足以下条件，才算本设计落地成功：

1. 仓库被定义为 Agent-first control plane template repository。
2. Git tracked truth 中不再出现宿主相关绝对路径。
3. 任何正式 Linux 动作都通过 backend runner 执行。
4. CLI 输出明确区分 canonical ref 与 resolved path。
5. fork 用户只需填写 secrets，就能让 Agent 完成最小接管。
6. active docs、AGENTS、repo-owned skills 全部以模板口径描述，不再以作者现场为默认。
7. Windows、Linux、macOS 的差异只存在于 resolver 和 backend 层，而不进入领域真源与领域命令合同。

## Phased Rollout

### Phase 1: Canonical Truth Cut

目标：

- 固定 truth / ledger / verification 三层结构；
- 建立 path policy；
- 建立宿主绝对路径禁入真源的门禁测试。

完成后必须成立：

- truth 不再接受宿主绝对路径；
- 当前 repo 中“会污染真源的输出面”被识别并纳入收口范围。

### Phase 2: Resolver Introduction

目标：

- 引入 `HostProfile`、`WorkspaceResolver`、`SecretResolver`；
- 建立 `canonical_ref -> resolved_path` 模型。

完成后必须成立：

- 同一逻辑对象可在 Windows / Linux / macOS 上解析；
- CLI 不再把 resolved path 错当 canonical truth。

### Phase 3: Backend Contract Unification

目标：

- 引入 `ExecutionPlan`；
- 建立 `linux-native / windows-wsl / macos-lima / ssh-linux` backend runner。

完成后必须成立：

- 领域层不再直接调用宿主 shell / docker / ssh。

### Phase 4: Domain Surface Refactor

目标：

- 重构 `host / app delivery / service / website / projection`；
- 所有 Linux 动作都走 backend runner。

完成后必须成立：

- `host inventory/audit wsl` 真正通过 WSL backend 工作；
- app delivery 主链路不再依赖宿主随机 PATH 和手拼命令。

### Phase 5: Bootstrap Productization

目标：

- 建立 fork 用户可直接使用的 bootstrap 流程；
- 把人类输入缩减到 secrets。

完成后必须成立：

- fork 用户只需填 secrets，就能让 Agent 接管模板仓库。

### Phase 6: Observation Isolation

目标：

- 完全切断 truth、ledger、verification 的相互污染。

完成后必须成立：

- verification 结果只能作为证据和报告；
- ledger 不再携带宿主机污染字段。

### Phase 7: Open-Source Template Closure

目标：

- 重写 README、AGENTS、skills、runbooks；
- 建立模板化的 active docs；
- 完成门禁测试。

完成后必须成立：

- 仓库可以作为模板对外发布；
- active assets 全部按模板口径表达。

## Phase Completion Protocol

每个阶段结束后，必须遵守固定收口规则：

1. 先提交本阶段全部变更。
2. 再做最小必要验证。
3. 再输出阶段总结。
4. 不在同一会话进入下一阶段。
5. 开启新会话再继续后续阶段。

每阶段总结必须包含：

1. 目标完成情况
2. 问题回顾与处理
3. 后续规划（不考虑兼容方案，如何一步到位）

## Execution Mode Policy

后续执行阶段默认遵循以下原则：

- 新会话继续下一阶段；
- 强制加载 `pua` skill；
- 默认减少低效 review；
- 优先主线程直接实现；
- 只做最小必要验证；
- 阶段结束前必须先提交再收口。

建议的新会话启动指令格式：

```text
先加载 `pua` skill。

执行 Phase <N>。
要求：
1. 优先主线程直接实现，不做低效 review。
2. 只做最小必要验证，但验证必须真实。
3. 本阶段结束前必须先提交变更，再输出阶段收口总结。
4. 阶段完成后停止，不进入下一阶段。
```

## Recommended Next Step

本设计确认后，下一步应进入 implementation plan，按以下顺序展开：

1. Phase 1 的 truth / ledger / verification 分层与 path policy；
2. Phase 2 的 resolver 模型；
3. Phase 3 的 backend contract；
4. Phase 4 的 domain surface 重构；
5. Phase 5-7 的 bootstrap、observation isolation 和开源模板收口。
