# 🛫 AgentPlane

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

> **给 AI Agent 的基础设施"自动驾驶仪"**
>
> 你告诉 AI 目标，AgentPlane 确保它安全地检查、执行、验证、留痕。
>
> 当前成熟度：Alpha。仓库治理、离线测试、文档治理和 secrets 边界已经可用；发布自动化、provider 合同和 app delivery schema 仍在收敛。

---

## 😰 你是否遇到过这些情况？

让 AI 帮你运维服务器，结果：

```bash
# AI 直接执行命令
ssh prod "docker restart myapp"
```

- **SSH 连不上？** 失败后才知
- **容器起不来？** 错误淹没在输出中
- **服务真的好了吗？** 没有验证
- **谁执行的？什么时候？** 查不到
- **想回滚？** 没有任何记录

---

## ✅ AgentPlane 的做法

同样的需求，不同的体验：

```bash
$ agentplane service apply --target prod --name myapp --execute

[检查] 主机在线 ✓
[执行] 重启容器 myapp ✓
[验证] HTTP 探针 200 OK ✓
[记录] 操作已保存，可随时回查
```

**每一步都有计划、有验证、有记录、可回滚。**

---

## 🆚 和直接 SSH 有什么不同？

| | 直接 SSH | **AgentPlane** |
|---|:---:|:---:|
| **AI 可直接使用** | ❌ 需要人写脚本 | ✅ **AI 说人话就行** |
| **执行前有计划** | ❌ | ✅ **默认先计划** |
| **执行后有验证** | ❌ | ✅ **自动验证** |
| **操作有记录** | ❌ | ✅ **完整审计证据** |
| **安全隔离** | ❌ secrets 在脚本里 | ✅ **secrets 分离设计** |

---

## 🎯 18 个 Skill 覆盖完整运维场景

AgentPlane 的核心是 **Skill 路由架构**：AI Agent 看到的是 Skill 能力，所有执行都通过 CLI 入口。

### 🖥️ 基础设施 (infra)

| 能力 | 示例命令 |
|------|----------|
| 主机纳管、资产盘点 | `agentplane infra inventory prod0-main` |
| 安全审计 | `agentplane infra audit prod0-main` |
| 远程命令执行 | `agentplane infra remote bash prod0-main -- uname -a` |
| 网络检查、防火墙 | `agentplane infra network audit prod0-main` |
| 定时任务管理 | `agentplane infra automation search prod0-main` |

### 🐳 服务管理 (service)

| 能力 | 示例命令 |
|------|----------|
| 搜索服务 | `agentplane service search --target prod0-main` |
| 查看服务状态 | `agentplane service get --target prod0-main --name myapp` |
| 验证服务健康 | `agentplane service verify --target prod0-main --name myapp` |
| 计划重启 | `agentplane service plan --target prod0-main --name myapp --operation restart` |
| 执行重启 | `agentplane service apply --target prod0-main --name myapp --execute` |

### 🚀 应用交付 (app)

| 能力 | 示例命令 |
|------|----------|
| 合约验证 | `agentplane app delivery validate-contract --target prod0-main --app myapp` |
| 构建产物 | `agentplane app delivery build-artifact --target prod0-main --app myapp` |
| 预览部署 | `agentplane app delivery deploy --target prod0-main --app myapp --dry-run` |
| 执行部署 | `agentplane app delivery deploy --target prod0-main --app myapp --execute` |
| 部署验证 | `agentplane app delivery verify --target prod0-main --app myapp --execute` |
| 回滚 | `agentplane app delivery deploy --target prod0-main --app myapp --rollback` |

### 🌐 入口管理 (ingress)

| 能力 | 示例命令 |
|------|----------|
| 搜索入口 | `agentplane ingress search --target prod0-main` |
| 查看入口详情 | `agentplane ingress get --target prod0-main --alias mysite` |
| 验证公网访问 | `agentplane ingress verify --target prod0-main --alias mysite` |
| 发布计划 | `agentplane ingress publish plan --target prod0-main --config-file ...` |
| 执行发布 | `agentplane ingress publish apply --target prod0-main --config-file ... --execute` |

### 🔄 工作流 Skills

| Skill | 用途 | 典型场景 |
|-------|------|----------|
| `app-delivery-ops` | 一键部署全流程 | "把 sub2api 部署到 prod0-main" |
| `host-onboarding-ops` | 新服务器纳管 | "接入这台新服务器" |
| `site-migration-ops` | 网站迁移 | "把网站从 A 迁到 B" |
| `docker-service-setup` | Docker 服务初始化 | "在这台机器上部署 Docker" |

---

## 🤖 AI Agent 怎么用？

你不需要记命令，只需要说人话：

> "把 sub2api 部署到 prod0-main，用最新镜像，先预览变更，确认后再执行，部署完验证健康状态。"

AI 会自动：

1. **找到对应的 Skill** — 识别这是应用交付任务
2. **调用 CLI 预览** — `agentplane app delivery deploy --dry-run`
3. **展示计划让你确认** — 人类在环
4. **执行并验证** — 自动检查部署结果
5. **写入部署摘要** — 留下审计证据

**这就是 Skill 路由的魔力：AI 看到能力，CLI 执行操作，人类掌控决策。**

---

## 🚀 5 分钟上手

### 1️⃣ 安装

```bash
git clone <你的仓库地址> && cd AgentPlane
uv tool install -e .
```

> 💡 如果 `agentplane` 仍不可用，可以改用 `uv run agentplane ...` 或 `python -m agentplane ...`

### 2️⃣ 体检

```bash
agentplane bootstrap inspect-local --repo-root .
agentplane bootstrap doctor --repo-root .
agentplane bootstrap init-secrets --repo-root .
agentplane bootstrap verify-secrets --repo-root .
```

### 3️⃣ 查看状态

```bash
agentplane repo status --repo-root . --html tmp/agentplane-status.html
agentplane repo health-check --repo-root .
```

> 💡 体检通过后，Agent 就可以接管后续操作了。

📖 **第一次用？** → [5 分钟了解 AgentPlane](docs/getting-started/5-minute-overview.md)
🚀 **想动手？** → [部署你的第一个应用](docs/tutorials/deploy-first-app.md)
🔍 **出错了？** → [排查部署失败](docs/tutorials/troubleshoot-failed-deployment.md)

---

## 🎯 项目边界

AgentPlane 不是 Terraform、Kubernetes controller 或 SSH 脚本集合。

**它更像一个给 AI Agent 使用的轻量控制面**：把正式操作收口到 `agentplane ...`，再把计划、执行、验证、证据、台账和文档回写串成闭环。

| 适合 | 不适合 |
|------|--------|
| 少量服务器和应用的 AI-assisted 运维 | 大型多租户平台控制器 |
| 需要公开仓库与生产 secrets 分离 | 把生产 secrets 放进 Git 管理 |
| 需要稳定任务入口和审计证据 | 只想保留一次性 SSH/Docker 命令 |
| 应用仓库只交付代码和合同 | 应用仓库自带第二套生产控制面 |

详细边界见 [项目定位](docs/reference/project-positioning.md)，演进计划见 [Roadmap](ROADMAP.md)。

---

## 📖 文档导航

**👤 人类入口**：
[5 分钟速览](docs/getting-started/5-minute-overview.md) ·
[核心概念](docs/getting-started/core-concepts.md) ·
[部署应用](docs/runbooks/app-project-delivery-workflow.md) ·
[AI 执行流程](docs/getting-started/how-agent-works.md)

**🤖 AI 入口**：
[AGENTS.md](AGENTS.md) ·
[Skill 盘点](docs/maintainers/skill-surface-audit.md) ·
[control-plane.md](docs/architecture/control-plane.md) ·
[execution-flow.md](docs/runbooks/control-plane-agent-execution-flow.md)

---

## 🤝 参与项目

| 文档 | 说明 |
|------|------|
| [LICENSE](LICENSE) | MIT 开源许可证 |
| [CONTRIBUTING.md](CONTRIBUTING.md) | 如何参与开发 |
| [Git 规范](docs/reference/git-conventions.md) | 分支、提交、PR 与 main 合并规则 |
| [SECURITY.md](SECURITY.md) | 安全策略 |
| [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) | 行为准则 |
| [SUPPORT.md](SUPPORT.md) | 获取帮助 |
| [ROADMAP.md](ROADMAP.md) | 项目成熟度与路线图 |
| [CHANGELOG.md](CHANGELOG.md) | 版本变更摘要 |

---

## 长期愿景

AgentPlane 的长期目标，是从 AI-assisted 运维控制面，演进为新项目从创建、开发、发布、部署到运维的统一控制面。

更多规划见 [Roadmap](ROADMAP.md) 和 [项目定位](docs/reference/project-positioning.md)。
