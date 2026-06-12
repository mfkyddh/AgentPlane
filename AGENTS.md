---
status: active
owner: AgentPlane maintainers
last_verified: 2026-06-11
superseded_by: null
audience: ai
---

# AI 助手工作规范

> 本文档面向 AI Agent。人类入口见 [docs/getting-started.md](docs/getting-started.md)。
> 完整规范见 [docs/conventions.md](docs/conventions.md)。

---

## 必读摘要

- 所有操作通过 `agentplane <domain> <surface> <verb> [flags]` 进入，不要绕过 CLI
- Secrets 只放 `secrets/` 目录，绝不提交到仓库
- 测试必须标记 `unit`/`integration`/`e2e`，默认排除 `live_gate`/`integration_wsl`/`ssh_required`
- Conventional Commits 格式：`type(scope): description`，subject ≤ 72 字符
- 每次推送后必须检查 CI，失败必须修复后再继续

---

## 安全约束

- 敏感信息（密码、token、API key）只放 `secrets/` 目录，被 `.gitignore` 保护
- 禁止在代码中硬编码 IP 地址、域名、凭证
- SSH 密钥和连接信息通过 `agentplane infra secrets` 管理
- `uv run agentplane project secret-scan --repo-root .` 检查泄露

---

## 项目概述

AgentPlane 是 Agent-first 控制面 CLI。所有操作通过 `agentplane <domain> <surface> <verb> [flags]` 进入，提供 Plan → Apply → Verify → Record 执行闭环。Skill 是 AI 入口，路由到 CLI——永远不要绕过 CLI。

**入口**: `agentplane/cli/app.py` → `main()`（也可 `python -m agentplane`）。

---

## 关键命令

```bash
# 开发环境
uv sync                                    # 安装依赖
uv run agentplane --help                   # 查看所有命令

# 测试
uv run pytest                              # 运行默认测试（离线、确定性）
uv run pytest tests/path/to/test.py        # 运行单个测试文件
uv run pytest tests/path/to/test.py::TestClass::test_method  # 运行单个测试
uv run pytest -m unit                      # 只运行 unit 测试
uv run pytest -m integration               # 只运行 integration 测试
uv run pytest -m e2e                       # 只运行 e2e 测试（需要浏览器）
uv run pytest --co -q                      # 收集测试但不运行（检查标记分布）
uv run pytest --cov=agentplane --cov-report=term-missing  # 带覆盖率

# Lint 和格式化
uv run ruff check .                        # 检查 lint 错误
uv run ruff check . --fix                  # 自动修复 lint 错误
uv run ruff format .                       # 格式化代码

# 项目健康检查
uv run agentplane project health-check --repo-root .
uv run agentplane project docs-sanity --repo-root .
uv run agentplane project secret-scan --repo-root .
uv run agentplane project skills check --repo-root .

# 测试门禁（pre-push hook）
uv run agentplane test fast --tb=short
```

---

## 必读规则

| # | 规则 | 级别 |
|---|------|------|
| 1 | **统一入口**：所有正式操作必须从 `agentplane ...` 进入 | 🔴 |
| 2 | **Secrets 绝不提交**：敏感信息只放 `secrets/` 目录 | 🔴 |
| 3 | **单份源码**：Windows 和 WSL 共用同一个仓库目录 | 🔴 |
| 4 | **单虚拟环境**：只使用根目录 `.venv`，不创建平台变种 | 🔴 |
| 5 | **原子提交**：每个逻辑变更单元独立提交 | 🔴 |
| 6 | **Conventional Commits**：`type(scope): description` 格式 | 🔴 |
| 7 | **执行后必验证**：每次变更都运行最小验证 | 🟡 |
| 8 | **用 `pwsh` 而非 `cmd`**：Windows 上默认用 PowerShell | 🟡 |
| 9 | **测试分层**：新增测试必须标记 unit/integration/e2e | 🔴 |
| 10 | **Skill 同步**：正式能力变更必须同步 `.agents/skills` | 🔴 |

---

## 测试金字塔

| 层级 | 标记 | 占比 | 耗时 |
|------|------|------|------|
| unit | `@pytest.mark.unit` | 72% | <10ms |
| integration | `@pytest.mark.integration` | 29% | <100ms |
| e2e | `@pytest.mark.e2e` | 1% | >1s |

**默认排除**：`live_gate`, `integration_wsl`, `integration_remote`, `external_app`, `docker_required`, `ssh_required`

**文件级标记**（在文件顶部）：
```python
pytestmark = pytest.mark.integration
```

**测试风格**：新测试用 pytest-native 风格（不继承 `unittest.TestCase`），用 `assert` 不用 `self.assertEqual`。

**测试文件上限**：500 行，超限必须拆分。

**测试常量**：fixture 输入值放 `tests/support/constants.py`，断言期望值留在测试内。

**CLI 测试模式**：用 `tests/support/cli.py` 的 `run_agentplane_cli()` 或 `run_cli_json()`，不要直接 `subprocess.run`。

---

## 架构要点

**五域分层**：`infra`（配置）→ `service`（运行时）→ `app`（交付）→ `ingress`（入口）→ `project`（治理）

**投影模型**：
- Layer 1: Host Inventory（台账）— `inventory/servers/<target>/inventory.json`
- Layer 2: Object Ledgers（证据）— `inventory/servers/<target>/ledgers/*.json`
- Layer 3: App Summary（摘要）— 从台账+证据派生

**Provider 抽象**：domain 层通过 `ProviderProtocol`（`agentplane/providers/protocol.py`）与基础设施交互，不直接依赖 1Panel。方法数 ≤ 15。

**SSH 连接层**：通过 `SSHConnectionProtocol`（`agentplane/ssh.py`）交互，方法数 ≤ 5。

**WebUI 定位**：控制面的可视化视图，不是新的控制面入口。FastAPI + Vue 3 CDN。

---

## 跨平台约束

- Windows 默认 `pwsh`，需 Linux 时 `wsl.exe -e <程序>`
- 远程 Linux 走 `agentplane infra remote bash`，禁止手写多层 SSH
- Python 用 `uv`，禁止 `UV_PROJECT_ENVIRONMENT` 指向平台路径
- `.gitattributes` 为换行符唯一权威（`* text=auto eol=lf`）

---

## Git 约束

- Conventional Commits：`type(scope): description`，type 仅限 `feat|fix|refactor|docs|test|chore|style|perf`
- 超过 3 个文件或跨模块变更时必须有 body
- 单人维护默认完成小任务后自动 commit、合入本地 `main`、推送 `origin main`
- 禁止 `push --force` 到 main

---

## 文档索引

完整地图见 [docs/README.md](docs/README.md)。最常用：
- [架构](docs/core/architecture.md) — 五域、投影模型、CLI 接口
- [命令参考](docs/command-reference.md) — 所有 CLI 命令
- [编码与协作规范](docs/conventions.md) — 技术栈、测试工程、编码规则
- [Maintainer 指南](docs/maintainer-guide.md) — 治理资产约束、Skill 同步门禁
- [原则](docs/core/principles.md) — 道法术三层原则体系

---

## 关联文档

- [CLAUDE.md](CLAUDE.md) — Claude Code 专属指令
- [CONTRIBUTING.md](CONTRIBUTING.md) — 贡献者指南
- [CHANGELOG.md](CHANGELOG.md) — 版本里程碑
- [PROGRESS.md](PROGRESS.md) — 主线追踪器
