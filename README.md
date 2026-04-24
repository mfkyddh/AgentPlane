# 🛫 AgentPlane

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

> **让 AI Agent 安全、规范地接管你的基础设施。**

AgentPlane 是一个 Agent-first control plane template repository。简单说：它给 AI 提供了一套**标准化的"遥控器"**，让 AI 能够帮你管理服务器、部署应用、配置服务，而且所有操作都有记录、可审计、可回滚。

核心模型是 Git tracked truth + local secrets：普通配置放在 Git 中，真实 secrets 留在本地；Windows / Linux / macOS 只在 `resolver / backend` 层分叉，同一个项目只保留 single checkout。Windows 入口 shell 使用 `pwsh`，需要封装 `uv` 时使用 `invoke-agentplane-windows-uv.ps1`。人类输入面只剩 `secrets` 和少量 `identity`，不再默认引用作者现场目录。

完成 bootstrap 体检后，就可以让 Agent 接管后续 `infra`、`service`、`ingress`、`app` 与 `projection` 动作。

---

<p align="center">
  <a href="#快速开始">🚀 快速开始</a> •
  <a href="#能做什么">✨ 能做什么</a> •
  <a href="#项目结构">📁 项目结构</a> •
  <a href="#核心概念">🧠 核心概念</a> •
  <a href="#文档导航">📖 文档</a>
</p>

---

## ✨ 能做什么

| 能力 | 说明 | 示例 |
|------|------|------|
| 🖥️ **主机管理** | 盘点服务器资产、执行审计、远程操作 | 一键查看所有受管服务器状态 |
| 🐳 **服务管控** | 管理 Docker 服务生命周期 | 验证 PostgreSQL、Redis 是否正常运行 |
| 🌐 **网站发布** | 自动化公网入口配置 | 一键发布网站到 Cloudflare + 1Panel |
| 📦 **应用交付** | 规范化的应用部署流程 | 构建 → 部署 → 验证 → 回滚 |
| ✅ **状态验证** | 持续验证实际状态与预期是否一致 | 自动检测配置漂移 |
| 📝 **台账投影** | 自动生成审计记录和状态报告 | 每次操作留下可追溯的证据 |

**核心设计原则**：
- ✅ **配置即代码** — 所有基础设施配置放在 Git 中管理
- 🔐 **敏感信息分离** — 密码、密钥单独存放，不提交到 Git
- 🤖 **AI 友好** — 统一的 CLI 入口，让 AI 能规范操作而非随意执行 Shell
- 🖥️ **跨平台** — Windows、macOS、Linux 共用同一份源码

---

## 🚀 快速开始

### 环境要求

- Python 3.11+
- [uv](https://docs.astral.sh/uv/)（Python 包管理器）
- Git

### 第一步：fork / clone 仓库

```bash
git clone <你的仓库地址>
cd AgentPlane
```

### 第二步：运行体检（Doctor）

Doctor 会检查你的环境是否就绪，并报告：
- ✅ 宿主环境状态
- ✅ 工作区绑定
- ✅ Backend（WSL/SSH/Docker）可用性
- ✅ Secrets 配置状态

### Windows
```powershell
uv run python -m agentplane.cli bootstrap inspect-local --repo-root .
uv run python -m agentplane.cli bootstrap doctor --repo-root .
```

### macOS / Linux
```bash
uv run python -m agentplane.cli bootstrap inspect-local --repo-root .
uv run python -m agentplane.cli bootstrap doctor --repo-root .
```

> 💡 **预期输出**：你应该看到类似 `host: ok`、`backend: wsl available` 的状态报告。如果有 ❌，按照提示修复即可。

### 第三步：全局安装 CLI（推荐）

安装到系统 PATH 后，你就可以直接用 `agentplane` 命令，无需每次都加 `uv run` 前缀：

```bash
uv tool install -e .
```

> 📝 安装完成后，本文档中所有命令都可以省略 `uv run` 前缀。如果之后代码更新了，运行 `uv tool upgrade agentplane` 即可同步。

### 第四步：初始化 Secrets

```bash
# 创建 secrets 目录结构
uv run python -m agentplane.cli bootstrap init-secrets --repo-root .

# 验证 secrets 配置
uv run python -m agentplane.cli bootstrap verify-secrets --repo-root .
```

> 🔐 **说明**：`secrets/` 目录已被 `.gitignore` 排除，你的密码和密钥不会意外提交到 Git。

### 第五步：查看全部命令

```bash
uv run python -m agentplane.cli --help
```

### 第六步：运行测试（可选）

```bash
uv run python -m pytest
```

> 默认只跑离线测试，不会触碰真实的 WSL/SSH/Docker。

### Live Gate

真实 WSL、SSH、Docker 或远端 provider 验证必须显式进入 live gate，先 `plan`，需要执行时再加 `--execute`：

```bash
uv run python -m agentplane.cli infra live-gate plan --profile wsl --repo-root .
```

---

## 📁 项目结构

```
AgentPlane/
├── 📚 docs/                  # 文档中心
│   ├── architecture/         # 架构设计（长期稳定的规范）
│   ├── runbooks/             # 操作手册（日常运维指南）
│   └── reference/            # 参考文档（命名规范、测试架构等）
│
├── 🤖 agentplane/            # 核心代码（Python CLI 工具）
│   ├── cli/                  # 命令行入口
│   ├── adapters/             # 适配器（连接各种后端）
│   └── scripts/              # 内部脚本
│
├── 📋 inventory/             # 资产台账（服务器、服务、网站清单）
│
├── 🏗️ infra/compose/         # Docker Compose 配置文件
│
├── 📄 templates/             # 配置模板（不含敏感信息）
│
├── 🔐 secrets/               # 敏感信息（密码、密钥、证书）
│   └── 被 .gitignore 保护，不会提交
│
└── ✅ tests/                 # 自动化测试
```

**一句话理解每个目录**：
- `docs/` = 说明书和操作手册
- `agentplane/` = AI 的操作工具箱（Python 程序）
- `inventory/` = 资产清单（我家有哪些服务器、跑什么服务）
- `infra/compose/` = 服务搭建图纸（Docker 配置）
- `templates/` = 可以复用的模板
- `secrets/` = 保险箱（密码放这里，安全）
- `tests/` = 质检程序

---

## 🧠 核心概念

> 📖 **详细解释见**：[核心概念与工作流程](docs/getting-started/core-concepts-and-workflow.md) —— 包含完整的流程图、术语速查表和每个概念的深入解读。

### 🤖 Task-Entry（标准化任务入口）

AgentPlane 不直接让 AI 执行原始 Shell 命令，而是通过**高层语义化的标准化入口**操作基础设施。

**传统方式的问题**：
- AI 直接执行 `ssh user@server "docker restart xxx"` —— 没有前置检查、没有错误处理、没有审计记录

**AgentPlane 的方式**：

```bash
agentplane <领域> <动作> [参数]
```

每个入口都封装了：前置检查 → 后端路由 → 错误处理 → 审计记录。

| 对象域 | 管理内容 | 典型命令 |
|--------|---------|---------|
| `infra` | 主机资产、SSH、网络治理 | `infra inventory`、`infra audit` |
| `service` | 运行中的服务（容器、数据库等） | `service verify`、`service apply` |
| `ingress` | 公网入口、域名、证书 | `ingress publish plan`、`ingress verify` |
| `app` | 应用交付（构建、部署、回滚） | `app delivery deploy`、`app delivery verify` |
| `projection` | 派生数据、验证、台账 | `projection verification run`、`projection ledger refresh` |

### 📋 真源与三层状态模型

AgentPlane 的真源只有一类——**配置真源**（Desired State），即 Git 管理的配置定义：

- 普通配置：`docs/`、`infra/compose/`、`templates/`、`inventory/` —— Git 版本控制
- 敏感配置：`secrets/` —— 本地管理，不提交 Git

AgentPlane 的核心工作是**持续对比以下三层状态**，发现配置漂移时及时报告：

| 状态层级 | 来源 | 回答的问题 |
|---------|------|-----------|
| **期望状态（Desired）** | 真源：Git 中的配置 | "系统应该是什么样？" |
| **实际状态（Actual）** | 现场实时查询 | "系统实际是什么样？" |
| **观测状态（Observed）** | Inventory / Ledger | "上次验证时记录的状态是什么？" |

### 🔄 执行闭环（Execution Loop）

任何影响正式状态的操作，都必须经过完整的 **6 步闭环**：

```
Plan（计划）→ Apply（执行）→ Verify（验证）→ Ledger（记录）→ Inventory Refresh（刷新台账）→ Doc-Sync（同步文档）
```

| 步骤 | 作用 | 关键标志 |
|------|------|---------|
| **Plan** | 预览变更，不真正执行 | `--dry-run` |
| **Apply** | 在计划确认后执行变更 | `--execute` |
| **Verify** | 检查系统是否达到预期状态 | `verify` |
| **Ledger** | 写入机器证据 | 自动写入 `tmp/operation-ledger/` |
| **Inventory Refresh** | 更新结构化台账 | `--write` |
| **Doc-Sync** | 回写人类可读摘要 | `--write` |

> ⚠️ **禁止**：跳过计划直接执行、执行后不验证、只改文档不改真源。

### 🔐 Secrets 分离

| 类型 | 存放位置 | 是否提交 Git | 示例 |
|------|----------|-------------|------|
| 非敏感配置 | `infra/compose/`、`templates/` | ✅ 是 | Docker Compose 文件 |
| 敏感信息 | `secrets/` | ❌ 否 | API Key、数据库密码 |

---

## 🛠️ 常用命令速查

### 主机管理
```bash
# 查看服务器资产清单
agentplane infra inventory <target>

# 主机审计
agentplane infra audit <target>

# 远程执行命令
agentplane infra remote bash <target> -- whoami
```

### 服务管理
```bash
# 查看所有服务
agentplane service search --target <target>

# 验证服务状态
agentplane service verify --target <target> --name <service>
```

### 网站发布
```bash
# 发布计划（先预览，不执行）
agentplane ingress publish plan \
  --target <target> \
  --config-file <config-file> \
  --cloudflare-env-file <env-file>

# 实际发布（加 --execute）
agentplane ingress publish plan --execute ...
```

### 验证与台账
```bash
# 运行验证套件
agentplane projection verification run --target <target> --profile <profile>

# 刷新台账（带 --write 才会写入）
agentplane projection ledger refresh --target <target> --write
```

---

## 📖 文档导航

### 🎓 入门必读（从这里开始）
- [core-concepts-and-workflow.md](docs/getting-started/core-concepts-and-workflow.md) — **核心概念与工作流程** ⭐ **第一次看请先读这个**
  - 包含：真源模型、Task-Entry、执行闭环、应用交付全流程、术语速查表、Mermaid 流程图
- [README.md](README.md) — 仓库入口、快速开始
- [current-state-and-validation.md](docs/runbooks/current-state-and-validation.md) — 当前状态与验证报告

### 🏗️ 架构设计
- [control-plane.md](docs/architecture/control-plane.md) — 控制面核心架构
- [linux-governance.md](docs/architecture/linux-governance.md) — Linux 治理规范
- [agentplane-app-collaboration.md](docs/architecture/agentplane-app-collaboration.md) — AgentPlane 与应用仓库协作规范

### 📋 操作手册
- [bootstrap-secrets.md](docs/runbooks/bootstrap-secrets.md) — Secrets 初始化指南
- [wsl-host-governance.md](docs/runbooks/wsl-host-governance.md) — WSL 环境管理
- [app-project-delivery-workflow.md](docs/runbooks/app-project-delivery-workflow.md) — 应用交付流程
- [live-integration-gate.md](docs/runbooks/live-integration-gate.md) — 现场集成验证

### 📚 参考文档
- [app-repository-standard.md](docs/reference/app-repository-standard.md) — 应用仓库标准
- [testing-architecture.md](docs/reference/testing-architecture.md) — 测试架构
- [compat-retirement-ledger.md](docs/reference/compat-retirement-ledger.md) — 兼容入口退役台账
- [control-plane-naming-registry.md](docs/reference/control-plane-naming-registry.md) — 命名规范
- [docs/history/index.md](docs/history/index.md) — 历史说明索引
- [docs/archive/README.md](docs/archive/README.md) — 已退出主流程的归档索引

---

## 🤝 参与项目

AgentPlane 采用 **MIT 许可证** 开源，欢迎社区贡献。

| 文档 | 说明 |
|------|------|
| [LICENSE](LICENSE) | MIT 开源许可证 |
| [CONTRIBUTING.md](CONTRIBUTING.md) | 贡献指南 — 如何参与开发、提交 PR |
| [SECURITY.md](SECURITY.md) | 安全策略 — 如何报告漏洞、安全最佳实践 |
| [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) | 行为准则 — 社区交流规范 |
| [SUPPORT.md](SUPPORT.md) | 支持指南 — 如何获取帮助、提交问题 |

---

<p align="center">
  Made with 🤖 for Agents
</p>
