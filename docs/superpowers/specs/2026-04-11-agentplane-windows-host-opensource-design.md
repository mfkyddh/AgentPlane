# AgentPlane Windows Host And Open-Source Design

## Goal

把本机正式控制面从当前 WSL 仓库迁移到 `D:\Projects\AgentPlane\`，同时把项目从“面向当前作者的 WSL-first 仓库”收敛成“可在 Windows、WSL、Linux、macOS 上使用的开源控制面”。

本设计必须同时满足以下约束：

- 保持 `AgentPlane` 作为统一控制面。
- 保持 `CLI-First`，正式入口固定为 `uv run python -m agentplane.cli ...`。
- Skill 只调用正式 CLI，不派生第二控制面。
- Windows 环境必须依赖 WSL 作为 Linux backend。
- 远端服务器默认通过 SSH 连接。
- 应用层默认采用 `Artifact-First`：先在应用层最合适的宿主环境构建产物，再交给 Linux backend 做装箱和部署准备。
- 本机迁移阶段把当前仓库代码与本地私有目录一并复制到 `D:\Projects\AgentPlane\`，并做真实环境验证；旧 WSL 仓库先保留，不立即删除。
- `sub2api` 作为首个适配对象纳入本次改造；其源码当前仍留在 WSL。

## Scope

- 定义 Windows 主控制面、WSL Linux backend、SSH 远端执行三层职责。
- 定义仓库根目录、私有目录、应用源码目录、artifact 目录、Linux staging 目录的统一抽象。
- 定义开源化后各平台的正式运行模型。
- 定义本机迁移与 `sub2api` 试点适配的阶段性路线。
- 定义文档、Skill、CLI 契约需要同步调整的方向。

## Non-Goals

- 本设计不直接实现所有代码改造。
- 本设计不要求在本轮把 `sub2api` 源码迁到 Windows。
- 本设计不要求立即删除 `/root/work/AgentPlane`。
- 本设计不把 Docker 变成 build machine；不采用“在 Docker 里重新编译业务代码”的路线。
- 本设计不改变远端 Linux / 生产服务器以 Linux 为最终运行环境的事实。

## Problem Statement

当前仓库已经具备 Python CLI、SSH target 解析、正式命令面和一定程度的跨脚本能力，但整体仍带有明显的私有 WSL 前提：

- 文档和示例大量写死 `/root/work/AgentPlane`。
- Windows 入口目前只是提示“去 WSL 内执行”，还不是正式宿主入口。
- 本地执行路径默认直接依赖 `bash` / Linux shell。
- 多处规则把 `WSL-first` 写成默认工作流，而不是“Windows 下的 Linux backend”。
- 现有测试与规范更关注 WSL 路径一致性，而不是多平台控制面一致性。

这会带来三个直接问题：

1. `D:\Projects\AgentPlane\` 无法成为自然的一等宿主路径。
2. Windows 与开源场景下的路径、执行器、文档契约没有统一抽象。
3. `sub2api` 这类应用仓库即使能被控制面接管，也还没有被纳入“宿主先产物化、Linux backend 再装箱”的统一模型。

## Decision Summary

长期标准采用以下路线：

1. `D:\Projects\AgentPlane\` 成为本机唯一正式控制面根目录。
2. Windows 负责承载控制面、CLI、Skill、文档、inventory、非敏感模板与本地私有配置管理。
3. WSL 负责本机 Linux backend：Docker、Linux shell、Linux 打包、权限语义、临时 staging、与位于 WSL 的应用源码交互。
4. Linux / macOS 保持可直接本地运行控制面；Windows 则通过统一 backend 适配层把 Linux 动作委托给 WSL。
5. 远端服务器统一走 SSH，不为 Windows 引入新的远端管理协议。
6. 应用层默认采用 `Artifact-First`：
   - 源码在 Windows，优先在 Windows 用项目自己的工具链构建 artifact。
   - 源码在 WSL，优先在 WSL 用项目自己的工具链构建 artifact。
   - 只有当产物不能稳定变成 Linux 可运行制品时，才回退到 WSL / Linux 本地构建。
   - 无论哪种情况，都不在 Docker 里编译业务代码。

## Architecture

### 1. Control Plane Layers

控制面拆成三层：

- `Control Plane Core`
  - `agentplane.cli`
  - inventory / ledgers / docs / contracts
  - Skill 到 CLI 的正式映射
- `Execution Backend`
  - `native-posix`
  - `wsl-linux`
  - `ssh-linux`
- `Workspace Resolver`
  - 解析本机仓库根、WSL backend 工作区、应用源码根、artifact 根、私有目录根、staging 根

原则是：业务语义留在控制面核心，平台差异留在 backend 与 workspace resolver，不允许在上层命令里继续散落 `/root/...`、`bash -lc`、`wsl.exe` 拼接逻辑。

### 2. Platform Roles

| 平台 | 控制面角色 | Linux backend 角色 | 正式定位 |
| --- | --- | --- | --- |
| Windows | 主控制面宿主 | 通过 WSL 提供 | 本机正式默认入口 |
| WSL | 可兼容运行控制面，但本方案里不再是长期主入口 | 是 | Windows 的 Linux backend |
| Linux | 本地直接运行控制面 | 本地即 backend | 开源一等平台 |
| macOS | 本地直接运行控制面 | 本地 shell + SSH；若需 Linux Docker 装箱则接远端或其他 Linux backend | 开源一等平台 |

说明：

- macOS 因为自带 POSIX shell，控制面适配成本低。
- 但最终部署仍是 Linux，因此凡是依赖 Linux Docker 语义的动作，macOS 也要通过 Linux backend 完成；只是它不强制依赖 WSL。
- Windows 的特殊点不是“不能运行 CLI”，而是“不能直接承担 Linux 打包 backend”。

### 3. Workspace Model

控制面必须从“固定路径”改成“角色路径”：

- `control_root`
  - Windows 主控制面根目录，固定为 `D:\Projects\AgentPlane\`
- `legacy_control_root`
  - 迁移观察期内的旧目录 `/root/work/AgentPlane`
- `private_root`
  - 当前仓库下的本地私有目录，首要对象是 `secrets/`
  - 若迁移审计发现其他 git-ignore 的本地真实配置文件，也一并按私有目录迁移
- `linux_backend_root`
  - WSL 中供本机 Linux backend 使用的工作区根目录
- `artifact_staging_root`
  - artifact 从宿主进入 Linux backend 后的统一 staging 目录
- `app_source_root`
  - 应用仓库源码真实所在位置；可位于 Windows，也可位于 WSL

控制面只消费这些角色路径，不再默认“仓库一定在 Linux 根目录下”。

### 4. Execution Backend Contract

所有会触发平台差异的命令，内部都应解析为统一 backend 契约：

- `backend_type`
  - `native-posix`
  - `wsl-linux`
  - `ssh-linux`
- `working_directory`
- `environment_file_inputs`
- `stdin_mode` / `script_file_mode`
- `artifact_inputs`
- `expected_outputs`

其中：

- `native-posix` 用于 Linux / macOS 本地执行控制面相关动作。
- `wsl-linux` 用于 Windows 主控制面把 Linux 动作下发到 WSL。
- `ssh-linux` 用于远端服务器操作。

`wsl-linux` 与 `ssh-linux` 是同类问题：都是“把 Linux 动作下发给另一个 Linux 执行面”，只是传输边界不同。

### 5. Artifact-First Delivery Contract

应用层与控制面之间新增正式 artifact 契约。最小字段应包括：

- `app`
- `target`
- `artifact_type`
  - 例如 `zip`、`tar.gz`、`binary`、`jar`、`directory`
- `artifact_path`
- `builder_platform`
  - `windows` / `wsl` / `linux` / `macos`
- `runtime_os`
  - 当前阶段正式要求能落到 `linux`
- `runtime_arch`
- `packaging_backend`
  - 当前 Windows 场景下默认是 `wsl-linux`
- `integrity`
  - 校验值、大小、生成时间

控制面只接收“已经过应用层构建完成的 artifact”，再负责：

- 校验 artifact 是否满足目标运行环境
- 同步 artifact 到 Linux backend staging
- 生成镜像上下文
- 进行 Linux 装箱
- 继续后续 verify / deploy / ledger / doc-sync

## Local Migration Design

### Phase 0: Migration Audit

在正式切换前，先审计当前 WSL 仓库中需要迁移的对象：

- tracked 代码与文档
- `secrets/`
- 其他 git-ignore 且确认为本地真实配置的目录或文件
- `.codex/` 下的仓库自有配置与 Skill

这一步的目标不是立刻删除旧目录，而是明确“哪些内容必须完整进入 `D:\Projects\AgentPlane\` 才能使 Windows 主控制面具备真实运行能力”。

### Phase 1: Duplicate To Windows Host

第一轮切换采用“复制 + 验证”而不是“原地移动 + 替换”：

- 将仓库工作树复制到 `D:\Projects\AgentPlane\`
- 将本地私有目录一并复制到 `D:\Projects\AgentPlane\`
- 保留旧 WSL 仓库 `/root/work/AgentPlane`
- 不在这一步切换生产，不在这一步删除旧目录

这样做的原因是：

- 便于逐项对比 Windows 主控制面与旧 WSL 控制面的行为差异
- 便于真实环境测试失败时快速回退
- 避免一次性切换导致控制面真源、私有目录、SSH 配置同时失联

### Phase 2: Promote Windows Control Root

当 Windows 侧复制完成后，CLI、文档、Skill、环境脚本开始统一以 `D:\Projects\AgentPlane\` 为本机正式控制面根目录表达。

旧 WSL 仓库在观察期内只承担两种职责：

- 兼容对照样本
- 紧急回退样本

观察期结束前，不删除旧 WSL 仓库。

### Phase 3: Real Environment Validation

必须做真实环境验证，而不是只跑单元测试。最低验证应覆盖：

- Windows 主控制面能启动正式 CLI
- Windows 主控制面能解析并调用 WSL backend
- Windows 主控制面能读取本地私有目录
- Windows 主控制面能解析 SSH 配置并连接远端
- 关键 formal CLI 至少完成一次 dry-run 与一次真实 read-only / verify 级动作
- `sub2api` 试点链路能从应用源码所在环境产出 artifact，并进入 Linux backend 完成装箱前验证

在这些验证通过前，Windows 侧不能宣称已经完成切换。

## Open-Source Adaptation Design

### 1. Public Contract

开源化后的公开承诺应该是：

- AgentPlane 是统一控制面，不是单一宿主脚本集合。
- 正式入口是 `agentplane.cli`。
- Skill 只负责把任务路由进正式 CLI。
- 服务器连接默认走 SSH。
- Windows 需要 WSL 作为 Linux backend。
- Linux / macOS 可以直接运行控制面。
- Docker 装箱不承担业务代码编译。

### 2. Remove Path-Coupled Documentation

文档与 Skill 的表达要从“仓库作者自己的固定路径”改成：

- 平台角色说明
- 必要前置条件说明
- 可替换的路径角色说明
- 示例路径与正式契约分离

例如 `/root/work/AgentPlane` 可以保留为历史迁移资料或示例，但不能继续作为默认正式真源表达。

### 3. Package As Standard CLI

开源化后，项目应更像标准 Python CLI 包：

- 暴露稳定 console entry
- 文档说明如何在 Windows / Linux / macOS 安装与调用
- backend 差异通过命令参数或配置解析，不通过文档口头暗示

### 4. Keep Skill As Thin Formal Bridges

Skill 在开源化后仍然重要，但定位必须收敛：

- 解释何时该用哪个 formal domain
- 生成/调用正式 CLI 命令
- 不在 Skill 里硬编码宿主特有路径
- 不把 Skill 变成第二套 orchestration engine

## Sub2api Pilot Design

`sub2api` 是本次迁移的首个试点对象，约束如下：

- 源码当前继续留在 WSL
- Windows 主控制面必须能够识别该应用的源码位置不在 Windows
- 应用层构建仍在 `sub2api` 自己的源码环境完成
- 构建产物完成后，再进入 Linux backend 的 artifact staging / packaging 流程

这意味着 `sub2api` 试点要验证两层适配：

1. 控制面从 Windows 宿主出发，能正确调用位于 WSL 的应用源码构建动作。
2. 构建完成的 artifact 能继续被 AgentPlane 的 formal delivery 流程消费，而不要求 Docker 内二次编译。

`sub2api` 试点通过后，才能证明这套方案不仅适合“源码也在 Windows”的项目，也适合“控制面在 Windows、应用源码在 WSL”的混合形态。

## Risks And Trade-Offs

### Risk 1: Path Drift

如果代码、文档、Skill、测试仍有大量 `/root/...` 固定路径残留，Windows 主控制面会出现“部分命令可用、部分命令暗中跳回旧路径”的漂移。

处理方式：

- 把路径抽象提升为正式契约
- 为关键文档、Skill、CLI 输出补回归测试

### Risk 2: Backend Leakage

如果上层命令继续直接拼 `bash -lc`、`wsl.exe`、平台专属路径，backend 抽象会失效。

处理方式：

- 把平台分支收口到统一 backend 层
- 上层命令只声明动作，不声明宿主细节

### Risk 3: Artifact Contract Too Weak

如果 artifact 只是一串路径，没有目标 OS/arch、校验信息和生成元数据，就无法保证 Linux 装箱稳定性。

处理方式：

- 把 artifact metadata 升级为正式契约
- 在装箱前执行 artifact verify

### Risk 4: Dual-Control-Plane Drag

如果旧 WSL 仓库长期不退役，容易演化成双主控制面。

处理方式：

- 明确 `D:\Projects\AgentPlane\` 是迁移完成后的唯一正式本机控制面
- 旧 WSL 仓库只保留到观察期结束

## Acceptance Criteria

当以下条件同时满足时，才算本设计落地成功：

1. `D:\Projects\AgentPlane\` 成为本机正式控制面根目录。
2. 当前仓库代码与本地私有目录已复制到 Windows 新目录，且旧 WSL 仓库仍保留作观察期回退样本。
3. formal CLI 在 Windows 主控制面下可运行，并能把 Linux 动作稳定委托给 WSL backend。
4. 远端正式服务器操作默认走 SSH。
5. 开源文档不再把 `/root/work/AgentPlane` 与纯 `WSL-first` 叙述当作默认正式契约。
6. `sub2api` 已被纳入新模型，且至少完成一条真实可验证的 artifact-first 交付链路。
7. 整个链路仍保持“统一控制面、CLI-First、Skill 调正式 CLI”的原则不变。

## Recommended Next Step

本设计确认后，下一步进入 implementation plan，按以下顺序展开：

1. 平台与路径抽象
2. Windows 主控制面迁移
3. WSL backend 桥接正式化
4. `sub2api` 试点适配
5. 文档、Skill、测试与收口
