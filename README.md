# 🛫 AgentPlane

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

> **让 AI Agent 安全、规范地接管你的基础设施。**

AgentPlane 是一个 Agent-first control plane template repository。它给 AI 提供了一套**标准化的"遥控器"**，让 AI 能帮你管理服务器、部署应用、配置服务，所有操作有记录、可审计、可回滚。

---

<p align="center">
  <a href="#-快速开始">🚀 快速开始</a> •
  <a href="#-能做什么">✨ 能做什么</a> •
  <a href="#-项目结构">📁 项目结构</a> •
  <a href="#-文档导航">📖 文档</a>
</p>

---

## ✨ 能做什么

| 能力 | 说明 |
|------|------|
| 🖥️ **主机管理** | 盘点服务器资产、执行审计、远程操作 |
| 🐳 **服务管控** | 管理 Docker 服务生命周期 |
| 🌐 **网站发布** | 自动化公网入口配置（Cloudflare + 1Panel） |
| 📦 **应用交付** | 构建 → 部署 → 验证 → 回滚 |
| ✅ **状态验证** | 持续检测配置漂移 |
| 📝 **台账投影** | 每次操作留下可追溯的审计证据 |

**核心设计**：✅ 配置即代码 • 🔐 敏感信息分离 • 🤖 AI 友好 CLI • 🖥️ 跨平台

---

## 🚀 快速开始

### 1️⃣ 环境要求

- Python 3.12+、[uv](https://docs.astral.sh/uv/)、Git

### 2️⃣ 安装 & 体检

```bash
git clone <你的仓库地址> && cd AgentPlane

# 全局安装 CLI（推荐，之后可直接用 agentplane 命令）
uv tool install -e .

# 环境体检
agentplane bootstrap inspect-local --repo-root .
agentplane bootstrap doctor --repo-root .

# 初始化 Secrets
agentplane bootstrap init-secrets --repo-root .
agentplane bootstrap verify-secrets --repo-root .
```

> 💡 体检通过后，Agent 就可以接管后续操作了。

### 3️⃣ 下一步

```bash
agentplane --help              # 查看全部命令
agentplane repo health-check --repo-root .   # 仓库健康检查
```

📖 理解核心概念 → [core-concepts-and-workflow.md](docs/getting-started/core-concepts-and-workflow.md)

---

## 📁 项目结构

```
AgentPlane/
├── agentplane/          🤖 唯一生产代码：CLI、domain、runtime、provider
├── tests/               🧪 自动化测试，按业务域组织
├── docs/                📖 人读文档：architecture / reference / runbooks
├── infra/compose/       🐳 Docker Compose 资产
├── inventory/           📋 非敏感状态台账和逻辑真源
├── templates/           📄 非敏感模板和 .example 文件
├── plugins/             🔌 插件分发资产
├── secrets/             🔐 本地真实 secrets（.gitignore 保护）
└── local/               🏠 本地态，不纳入仓库
```

> 正式执行入口只有 `agentplane ...`。完整规则见 [repository-structure.md](docs/reference/repository-structure.md)。

---

## 🧠 核心概念（速览）

AgentPlane 的核心是三个想法：

- **🎯 Task-Entry**：AI 不直接执行 Shell，而是通过 `agentplane <领域> <动作>` 标准化入口操作
- **📋 真源模型**：Git 管配置，本地管 secrets，现场状态只做验证基准
- **🔄 执行闭环**：Plan → Apply → Verify → Ledger → Inventory → Doc-Sync

📖 **详细解读** → [core-concepts-and-workflow.md](docs/getting-started/core-concepts-and-workflow.md)

---

## 📖 文档导航

| 你想做什么 | 去哪里 |
|-----------|--------|
| 第一次了解项目 | [core-concepts-and-workflow.md](docs/getting-started/core-concepts-and-workflow.md) ⭐ |
| 查看当前状态 | [current-state-and-validation.md](docs/runbooks/current-state-and-validation.md) |
| 架构设计 | [control-plane.md](docs/architecture/control-plane.md) |
| 操作手册 | [docs/runbooks/](docs/runbooks/) |
| 规范参考 | [docs/reference/](docs/reference/) |
| 完整文档地图 | [docs/README.md](docs/README.md) |

---

## 🤝 参与项目

| 文档 | 说明 |
|------|------|
| [LICENSE](LICENSE) | MIT 开源许可证 |
| [CONTRIBUTING.md](CONTRIBUTING.md) | 如何参与开发 |
| [SECURITY.md](SECURITY.md) | 安全策略 |
| [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) | 行为准则 |
| [SUPPORT.md](SUPPORT.md) | 获取帮助 |

---

<p align="center">
  Made with 🤖 for Agents
</p>
