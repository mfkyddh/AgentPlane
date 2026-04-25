# AgentPlane 文档地图

结论：这里是人类和 AI 的文档导航页。第一次阅读先走 🧭 入门路径；执行任务时按 🛠️ runbook；维护规范时看 📚 reference。

## 🧭 推荐阅读

| 你想做什么 | 从这里开始 |
| --- | --- |
| 了解项目 | [../README.md](../README.md) |
| 理解核心概念 | [getting-started/core-concepts-and-workflow.md](getting-started/core-concepts-and-workflow.md) |
| 查看当前状态 | [runbooks/current-state-and-validation.md](runbooks/current-state-and-validation.md) |
| 执行正式任务 | [runbooks/control-plane-agent-execution-flow.md](runbooks/control-plane-agent-execution-flow.md) |
| 维护文档规范 | [reference/documentation-governance.md](reference/documentation-governance.md) |
| 编写控制面资产 | [maintainers/control-plane-authoring.md](maintainers/control-plane-authoring.md) |

## 🧠 架构合同

| 文档 | 说明 |
| --- | --- |
| [architecture/README.md](architecture/README.md) | 架构目录索引 |
| [architecture/control-plane.md](architecture/control-plane.md) | 控制面、task-entry、truth / projection 核心合同 |
| [architecture/linux-governance.md](architecture/linux-governance.md) | Linux / WSL backend 长期治理 |
| [architecture/agentplane-app-collaboration.md](architecture/agentplane-app-collaboration.md) | 控制面仓库与应用仓库边界 |

## 📚 Reference

| 文档 | 说明 |
| --- | --- |
| [reference/documentation-governance.md](reference/documentation-governance.md) | 文档分层、emoji、链接和门禁规范 |
| [reference/repository-structure.md](reference/repository-structure.md) | 顶层目录和新文件放置规则 |
| [reference/code-style.md](reference/code-style.md) | 代码和文档风格基线 |
| [reference/tech-stack.md](reference/tech-stack.md) | 技术栈约束 |
| [reference/cross-platform.md](reference/cross-platform.md) | Windows / WSL / Linux 跨平台规则 |
| [reference/git-conventions.md](reference/git-conventions.md) | Git 与 commit message 规范 |
| [reference/release-process.md](reference/release-process.md) | 发布和健康检查流程 |
| [reference/testing-architecture.md](reference/testing-architecture.md) | 默认测试与 live gate 分层 |
| [reference/container-conventions.md](reference/container-conventions.md) | Docker Compose 与容器约束 |
| [reference/app-repository-standard.md](reference/app-repository-standard.md) | 应用仓库接入标准 |
| [reference/app-delivery-versioning.md](reference/app-delivery-versioning.md) | 应用版本与镜像 tag 规范 |
| [reference/app-runtime-decomposition.md](reference/app-runtime-decomposition.md) | App runtime 拆分路线 |
| [reference/onepanel-api-contract.md](reference/onepanel-api-contract.md) | 1Panel API 与 provider 合同 |
| [reference/control-plane-path-policy.md](reference/control-plane-path-policy.md) | 逻辑路径与物理路径规则 |
| [reference/control-plane-naming-registry.md](reference/control-plane-naming-registry.md) | 控制面命名注册表 |
| [reference/open-source-readiness.md](reference/open-source-readiness.md) | 开源准备度基线 |

## 🛠️ Runbooks

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
| [runbooks/wsl-secrets-backup.md](runbooks/wsl-secrets-backup.md) | WSL secrets 备份 |
| [runbooks/wsl-zzz-skills-sync.md](runbooks/wsl-zzz-skills-sync.md) | zzz skills 同步 |
| [runbooks/prod0-main-governance.md](runbooks/prod0-main-governance.md) | prod0-main 治理 |
| [runbooks/prod0-main-1panel-public-access.md](runbooks/prod0-main-1panel-public-access.md) | prod0-main 公网入口 |
| [runbooks/prod2-main-1panel-public-access.md](runbooks/prod2-main-1panel-public-access.md) | prod2-main 公网入口 |
| [runbooks/prod2-main-relay-trojan.md](runbooks/prod2-main-relay-trojan.md) | prod2-main relay-trojan |
| [runbooks/current-state-and-validation.md](runbooks/current-state-and-validation.md) | 当前状态和验证快照 |

## 🧑‍🔧 Maintainers

| 文档 | 说明 |
| --- | --- |
| [maintainers/control-plane-authoring.md](maintainers/control-plane-authoring.md) | control plane authoring 规则 |

## 🕰️ History And Archive

| 文档 | 说明 |
| --- | --- |
| [history/index.md](history/index.md) | 历史材料索引 |
| [archive/README.md](archive/README.md) | 退役材料索引 |

## ✅ 文档门禁

新增或移动文档后运行：

```bash
uv run python -m agentplane.cli repo docs-sanity --repo-root .
```

`docs-sanity` 会检查 active 文档断链、旧入口引用和孤立文档。
