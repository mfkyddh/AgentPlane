---
status: active
owner: AgentPlane maintainers
last_verified: 2026-04-25
superseded_by: null
audience: both
---

# AgentPlane 文档地图

结论：这里是人类和 AI 的文档导航页。第一次阅读先走 👤 人类入口；执行任务时按 🛠️ runbook；维护规范时看 📚 reference。

---

## 👤 人类入口：按你想做什么

> 📌 所有 runbook 的完整列表和按场景分类见 [Runbook 导航](runbooks/README.md)。

| 你想做什么 | 从这里开始 |
| --- | --- |
| 第一次了解项目 | [5 分钟速览](getting-started/5-minute-overview.md) ⭐ |
| 理解核心概念 | [核心概念](getting-started/core-concepts.md) |
| 了解 AI 怎么工作 | [AI 执行流程](getting-started/how-agent-works.md) |
| 部署第一个应用 | [教程：部署 sub2api](tutorials/deploy-first-app.md) ⭐ |
| 排查部署失败 | [教程：排查失败](tutorials/troubleshoot-failed-deployment.md) ⭐ |
| 了解完整交付流程 | [应用交付流程](runbooks/app-project-delivery-workflow.md) |
| 部署失败了怎么办 | [失败处理](runbooks/app-delivery-failure-handling.md) |
| 查看当前状态 | [状态与验证](runbooks/current-state-and-validation.md) |
| 初始化 Secrets | [Secrets 引导](runbooks/bootstrap-secrets.md) |
| 管理 WSL 开发环境 | [WSL 治理](runbooks/wsl-host-governance.md) |
| 添加新服务器 | [纳入新服务器](tutorials/add-new-server.md) |

---

## 🤖 AI 入口：按执行域

| 域 | 架构合同 | 执行规范 | 命名注册 |
| --- | --- | --- | --- |
| `infra` | [control-plane.md](architecture/control-plane.md) | [execution-flow.md](runbooks/control-plane-agent-execution-flow.md) | [naming-registry.md](reference/control-plane-naming-registry.md) |
| `service` | [control-plane.md](architecture/control-plane.md) | [execution-flow.md](runbooks/control-plane-agent-execution-flow.md) | [naming-registry.md](reference/control-plane-naming-registry.md) |
| `ingress` | [control-plane.md](architecture/control-plane.md) | [execution-flow.md](runbooks/control-plane-agent-execution-flow.md) | [naming-registry.md](reference/control-plane-naming-registry.md) |
| `app` | [control-plane.md](architecture/control-plane.md) | [app-delivery-workflow.md](runbooks/app-project-delivery-workflow.md) | [naming-registry.md](reference/control-plane-naming-registry.md) |
| `projection` | [control-plane.md](architecture/control-plane.md) | [execution-flow.md](runbooks/control-plane-agent-execution-flow.md) | [naming-registry.md](reference/control-plane-naming-registry.md) |

AI 工作规范：[AGENTS.md](../AGENTS.md)；Skill 面盘点：[skill-surface-audit.md](maintainers/skill-surface-audit.md)

---

## 📚 完整索引（按类别）

### 🧠 架构合同

| 文档 | 说明 |
| --- | --- |
| [architecture/README.md](architecture/README.md) | 架构目录索引 |
| [architecture/control-plane.md](architecture/control-plane.md) | 控制面、task-entry、配置中心核心合同 |
| [architecture/linux-governance.md](architecture/linux-governance.md) | Linux / WSL backend 长期治理 |
| [architecture/agentplane-app-collaboration.md](architecture/agentplane-app-collaboration.md) | 控制面仓库与应用仓库边界 |
| [architecture/decisions/README.md](architecture/decisions/README.md) | 长期架构决策记录 |

### 📚 Reference

| 文档 | 说明 |
| --- | --- |
| [reference/documentation-governance.md](reference/documentation-governance.md) | 文档分层、emoji、链接和门禁规范 |
| [reference/project-positioning.md](reference/project-positioning.md) | 项目定位、非目标和工具边界 |
| [reference/repository-structure.md](reference/repository-structure.md) | 顶层目录和新文件放置规则 |
| [reference/code-style.md](reference/code-style.md) | 代码和文档风格基线 |
| [reference/tech-stack.md](reference/tech-stack.md) | 技术栈约束 |
| [reference/cross-platform.md](reference/cross-platform.md) | Windows / WSL / Linux 跨平台规则 |
| [reference/git-conventions.md](reference/git-conventions.md) | Git 与 commit message 规范 |
| [reference/release-process.md](reference/release-process.md) | 发布和健康检查流程 |
| [reference/testing-architecture.md](reference/testing-architecture.md) | 默认测试与 live gate 分层 |
| [reference/testing-conventions.md](reference/testing-conventions.md) | 测试 marker、并行和文件组织规则 |
| [reference/container-conventions.md](reference/container-conventions.md) | Docker Compose 与容器约束 |
| [reference/app-repository-standard.md](reference/app-repository-standard.md) | 应用仓库接入标准 |
| [reference/app-delivery-versioning.md](reference/app-delivery-versioning.md) | 应用版本与镜像 tag 规范 |
| [reference/app-runtime-decomposition.md](reference/app-runtime-decomposition.md) | App runtime 拆分路线 |
| [reference/onepanel-api-contract.md](reference/onepanel-api-contract.md) | 1Panel API 与 provider 合同 |
| [reference/control-plane-path-policy.md](reference/control-plane-path-policy.md) | 逻辑路径与物理路径规则 |
| [reference/control-plane-naming-registry.md](reference/control-plane-naming-registry.md) | 控制面命名注册表 |
| [reference/open-source-readiness.md](reference/open-source-readiness.md) | 开源准备度基线 |
| [reference/publication-boundary.md](reference/publication-boundary.md) | 公开仓库与本地私有材料边界 |
| [reference/schemas/README.md](reference/schemas/README.md) | 公开合同 schema 索引 |

### 🛠️ Runbooks

| 文档 | 说明 |
| --- | --- |
| [runbooks/control-plane-agent-execution-flow.md](runbooks/control-plane-agent-execution-flow.md) | Agent 执行闭环 |
| [runbooks/control-plane-domain-onboarding.md](runbooks/control-plane-domain-onboarding.md) | 新控制面领域接入 |
| [runbooks/bootstrap-secrets.md](runbooks/bootstrap-secrets.md) | secrets 初始化 |
| [runbooks/live-integration-gate.md](runbooks/live-integration-gate.md) | 真实环境验证门禁 |
| [runbooks/app-project-delivery-workflow.md](runbooks/app-project-delivery-workflow.md) | 应用接入与交付主路径 |
| [runbooks/app-delivery-failure-handling.md](runbooks/app-delivery-failure-handling.md) | 应用交付失败处理 |
| [runbooks/docker-host-runtime-packaging-template.md](runbooks/docker-host-runtime-packaging-template.md) | Docker host runtime 打包模板 |
| [runbooks/onepanel-cli-validation-workflow.md](runbooks/onepanel-cli-validation-workflow.md) | 1Panel CLI 验证流程 |
| [runbooks/powershell-wsl-remote-bash.md](runbooks/powershell-wsl-remote-bash.md) | PowerShell 到 WSL/remote bash 路由 |
| [runbooks/wsl-host-governance.md](runbooks/wsl-host-governance.md) | WSL 主机治理 |
| [runbooks/current-state-and-validation.md](runbooks/current-state-and-validation.md) | 当前状态和验证快照 |

### 🧑‍🔧 Maintainers

| 文档 | 说明 |
| --- | --- |
| [maintainers/control-plane-authoring.md](maintainers/control-plane-authoring.md) | control plane authoring 规则 |
| [maintainers/skill-surface-audit.md](maintainers/skill-surface-audit.md) | 当前 Skill 面盘点与重构建议 |

### 🕰️ History And Archive

| 文档 | 说明 |
| --- | --- |
| [history/index.md](history/index.md) | 历史材料索引 |
| [archive/README.md](archive/README.md) | 退役材料索引 |

---

## ✅ 文档门禁

新增或移动文档后运行：

```bash
uv run python -m agentplane.cli repo docs-sanity --repo-root .
uv run python -m agentplane.cli repo skills check --repo-root .
uv run python -m agentplane.cli repo status --repo-root . --html tmp/agentplane-status.html
uv run python -m agentplane.cli repo privacy-scan --repo-root .
```

`docs-sanity` 会检查 active 文档断链、旧入口引用、孤立文档、frontmatter 完整性、人类文档术语和长度。
`skills check` 会检查公开 Skill catalog、frontmatter、必备章节和正式 CLI 路由。
`status --html` 会生成本地静态控制面状态面板，默认写到 ignored 的 `tmp/`。
`privacy-scan` 会检查 Git 可见文件中是否误入真实控制面状态或维护者现场信息。
