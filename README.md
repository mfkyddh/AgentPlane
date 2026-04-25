---
status: active
owner: AgentPlane maintainers
last_verified: 2026-04-25
superseded_by: null
audience: both
---

# 🛫 AgentPlane

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

> **你的基础设施"自动驾驶仪"**——你告诉它目标，它自动检查、执行、验证、留痕。
>
> AgentPlane 是一个 Agent-first control plane template repository。

---

## ❌ 没有 AgentPlane 时

AI 直接执行 `ssh prod "docker restart myapp"`：

- SSH 连不上？失败后才知
- 容器起不来？错误淹没在输出中
- 服务真的好了吗？没有验证
- 谁执行的？什么时候？查不到

## ✅ 有了 AgentPlane

```bash
$ agentplane service apply --target prod --name myapp --execute
[检查] 主机在线 ✓
[执行] 重启容器 myapp ✓
[验证] HTTP 探针 200 OK ✓
[记录] 操作已保存，可随时回查
```

同样的操作，不同的体验：**有计划、有验证、有记录、可回滚**。

---

## 🚀 5 分钟上手

### 1️⃣ 安装

```bash
git clone <你的仓库地址> && cd AgentPlane
uv tool install -e .
```

### 2️⃣ 体检

```bash
agentplane bootstrap inspect-local --repo-root .
agentplane bootstrap doctor --repo-root .
agentplane bootstrap init-secrets --repo-root .
agentplane bootstrap verify-secrets --repo-root .
```

### 3️⃣ 查看状态

```bash
agentplane repo health-check --repo-root .
```

> 💡 体检通过后，Agent 就可以接管后续操作了。

📖 **第一次用？** → [5 分钟了解 AgentPlane](docs/getting-started/5-minute-overview.md)

---

## 📦 能做什么

| 场景 | 说明 |
|------|------|
| 🚀 **一键部署** | 构建 → 上传 → 部署 → 验证 → 回滚，全程标准化 |
| 🖥️ **主机管理** | 盘点服务器资产、执行审计、远程操作 |
| 🐳 **服务管控** | 管理 Docker 服务生命周期，自动健康检查 |
| 🌐 **网站发布** | 自动化公网入口配置（Cloudflare + 1Panel） |
| ✅ **状态验证** | 持续检测配置漂移，发现问题及时报告 |
| 📝 **操作留痕** | 每次操作留下可追溯的审计证据 |

**核心设计**：配置即代码 • 敏感信息分离 • AI 友好 CLI • 跨平台

---

## 📁 项目结构

```
AgentPlane/
├── agentplane/          🤖 CLI 与自动化代码
├── tests/               🧪 自动化测试
├── docs/                📖 文档（人类 + AI）
├── infra/compose/       🐳 Docker Compose 资产
├── inventory/           📋 非敏感状态台账
├── templates/           📄 非敏感模板
├── secrets/             🔐 本地敏感信息（不提交 Git）
└── local/               🏠 本地协作（不提交 Git）
```

> 正式入口只有 `agentplane ...`。

---

## 📖 文档导航

**👤 人类入口**

| 你想做什么 | 看这里 |
|-----------|--------|
| 第一次了解项目 | [5 分钟速览](docs/getting-started/5-minute-overview.md) |
| 理解核心概念 | [核心概念](docs/getting-started/core-concepts.md) |
| 部署一个应用 | [应用交付流程](docs/runbooks/app-project-delivery-workflow.md) |
| 查看当前状态 | [状态与验证](docs/runbooks/current-state-and-validation.md) |
| 了解 AI 怎么工作 | [AI 执行流程](docs/getting-started/how-agent-works.md) |

**🤖 AI 入口**

| 你需要什么 | 看这里 |
|-----------|--------|
| 工作规范（每次注入） | [AGENTS.md](AGENTS.md) |
| 控制面架构合同 | [control-plane.md](docs/architecture/control-plane.md) |
| 执行闭环规范 | [execution-flow.md](docs/runbooks/control-plane-agent-execution-flow.md) |
| 文档治理规范 | [documentation-governance.md](docs/reference/documentation-governance.md) |

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
