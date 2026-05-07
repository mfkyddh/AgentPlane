---
status: archived
owner: AgentPlane maintainers
last_verified: 2026-04-25
superseded_by: null
audience: human
layer: technical
---

# 📖 Runbook 导航

结论：Runbook 是"按场景查找"的操作手册，不是按分类罗列的文档列表。找到你想做的事，然后跟着步骤执行。

## 🚀 我想上手项目

| Runbook | 解决什么问题 |
|---------|-------------|
| [Bootstrap Secrets](./bootstrap-secrets.md) | 第一次安装 AgentPlane，生成 secrets 骨架并验证 |
| [Agent 执行流程](./control-plane-agent-execution-flow.md) | AI 收到指令后怎么一步步执行 |

## 📦 我想部署一个应用

| Runbook | 解决什么问题 |
|---------|-------------|
| [应用交付主流程](./app-project-delivery-workflow.md) | 从约定书校验到部署验证的完整 8 步流程 |
| [部署失败怎么办](./app-delivery-failure-handling.md) | 部署出错了，按阶段定位原因并回滚 |
| [容器规范](../reference/container-conventions.md) | Docker Compose、容器命名、打包规范 |

## 🔍 我想检查当前状态

| Runbook | 解决什么问题 |
|---------|-------------|
| [仓库健康检查](./current-state-and-validation.md) | 查看仓库结构、链接、入口是否健康 |
| [现场验证](./live-integration-gate.md) | 运行真实的 WSL/SSH/Docker 集成验证 |
| [监控与告警](./monitoring-and-alerting.md) | 监控目标、健康检查、容器监控、告警规则和工具集成 |

## 🖥️ 我想管理特定机器

| Runbook | 解决什么问题 |
|---------|-------------|
| [WSL 开发环境](./wsl-host-governance.md) | WSL 侧的配置、网络和日常运维 |

## 🛡️ 我想备份或恢复

| Runbook | 解决什么问题 |
|---------|-------------|
| [备份与恢复](./backup-and-recovery.md) | secrets、inventory 和配置的备份策略、恢复流程与灾难恢复 |

## 🔄 我想升级或迁移

| Runbook | 解决什么问题 |
|---------|-------------|
| [升级与迁移指南](./upgrade-and-migration.md) | 版本升级、Breaking change 处理、数据迁移和回滚 |

## 🔧 我想扩展或定制

| Runbook | 解决什么问题 |
|---------|-------------|
| [接入新管理领域](./control-plane-domain-onboarding.md) | 把新的基础设施领域纳入 AgentPlane 管理 |
| [PowerShell-WSL 远程 Bash](./powershell-wsl-remote-bash.md) | Windows 宿主通过 PowerShell 调用 WSL bash 的技巧 |

## 快速命令参考

### 查看仓库健康

```bash
agentplane repo health-check --repo-root .
```

**预期输出**：

```text
[PASS] 仓库结构检查
[PASS] docs-sanity 链接检查
[PASS] 入口漂移检查
```

### 查看目标环境状态

```bash
agentplane infra inventory wsl --repo-root .
agentplane infra audit wsl --repo-root .
```

### 查看应用交付状态

```bash
agentplane app delivery validate-contract --target wsl --app sub2api --repo-root .
```

> 📌 想要场景驱动的教程？看 [docs/tutorials/](../tutorials/)。
