---
status: active
owner: AgentPlane maintainers
last_verified: 2026-04-24
superseded_by: null
---

# 发布与持续健康规范

本文定义 AgentPlane 长期健康运行所需的发布、验证和维护节奏。当前项目仍处于早期阶段，因此规则以轻量、可执行为主。

## 日常变更 Definition of Done

普通代码或文档变更完成前至少满足：

| 场景 | 必做检查 |
| --- | --- |
| Python 代码 | `uv run python -m agentplane.cli repo health-check --repo-root .`、相关聚焦测试 |
| CLI 行为 | 相关 CLI 测试、`uv run python -m agentplane.cli --help` |
| 默认门禁相关 | `uv run python -m pytest` |
| 文档规范 | 链接指向 active 文档，命令示例使用 `agentplane ...` |
| secrets / inventory / projection | 确认真实 secrets 未入库，必要时刷新台账 |

无法验证时必须在提交或 PR 说明里写清楚：没验证什么、为什么、剩余风险是什么。

默认统一入口：

```bash
uv run python -m agentplane.cli repo health-check --repo-root .
```

Secret scan 例外必须写入仓库根目录 `.secret-scan-allowlist`。优先修正文档或测试样例，只有确认为合法样例且无法改写时才加入 allowlist。

## 生产变更闭环

影响真实 WSL、Docker、SSH、远端 provider、域名、证书或运行服务的操作，必须走：

```text
plan -> apply -> verify -> ledger -> inventory refresh -> doc-sync
```

执行要求：

- `plan` 阶段不改变真实状态。
- `apply` 必须有明确 `--execute` 或等价显式开关。
- `verify` 通过前，不刷新 inventory 宣称状态已达成。
- ledger 记录必须能回答：谁、何时、对哪个 target、做了什么、证据是什么。
- 回滚材料要在切换正式流量前准备好。

## 发布流程

首次公开 tag 前，使用轻量发布流程：

1. 运行 `uv run python -m agentplane.cli repo release-check --repo-root .`。
2. 确认 open source readiness 中没有阻塞项。
3. 更新 README、CHANGELOG 或 release notes。
4. 创建版本 tag，例如 `v0.1.0`。
5. 发布后运行一次最小 smoke check：安装 CLI、`agentplane --help`、默认 pytest。

正式发布稳定后，再补自动 changelog、构建制品和签名流程。

## 健康周检

每周或每个较大迭代后执行一次：

```bash
git status --short
uv run python -m agentplane.cli repo health-check --repo-root .
```

同时人工扫一遍：

- 是否有新增长文件超过约 `600` 行，需要列入拆分计划。
- 是否有新正式操作绕过 `agentplane ...`。
- 是否有 docs/runbooks 指向退役入口。
- 是否有 live gate 应跑未跑。
- 是否有 secrets、证书、私钥、真实 `.env` 被误加入 Git。

## 核心模块减重策略

对于 `agentplane/domain/app/runtime.py`、大型测试辅助等高变更文件，采用滚动治理：

- 不为“变小”单独大重构。
- 每次触碰一个行为点，就把该行为点抽到更窄的模块或 support helper。
- 拆分提交必须包含行为不变的测试证明。
- 旧函数退役时同步更新 reference 文档或 compat ledger。
