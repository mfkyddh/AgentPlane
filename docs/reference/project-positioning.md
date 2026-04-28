---
status: active
owner: AgentPlane maintainers
last_verified: 2026-04-29
superseded_by: null
audience: both
---

# 项目定位

结论：AgentPlane 是一个面向 AI Agent 的 CLI-first 基础设施控制面模板。它提供统一入口、计划执行验证闭环、secrets 分离、inventory / ledger 投影和跨平台执行约束。

## 解决什么

| 问题 | AgentPlane 的回答 |
| --- | --- |
| AI 直接 SSH 或 Docker 操作不可追溯 | 所有正式动作收口到 `agentplane ...`，输出结构化证据。 |
| 生产 secrets 和公开仓库容易混淆 | 真实 secrets 只在 ignored `secrets/`，公开仓库只保留模板和示例。 |
| Windows、WSL、Linux 路径和执行方式漂移 | 上层使用逻辑路径，runtime/backend 负责解析。 |
| 运维动作只执行不验证 | 正式动作遵循 plan -> apply -> verify -> ledger -> inventory refresh -> doc-sync。 |
| 应用仓库成为第二控制面 | 应用仓库只交付代码、构建资产和合同，生产控制面归 AgentPlane。 |

## 不解决什么

| 非目标 | 说明 |
| --- | --- |
| 替代 Terraform | AgentPlane 管操作闭环和轻量控制面，不声明云资源全生命周期。 |
| 替代 Kubernetes / GitOps controller | AgentPlane 不是常驻 reconciler，默认由 CLI 和 Agent 触发任务。 |
| 成为 secrets manager | AgentPlane 只定义本地 secret 边界和投影规则，不托管密钥服务。 |
| 托管平台 | 当前是一个可 fork、可扩展的仓库模板和 CLI，不是 SaaS。 |

## 与常见工具的边界

| 工具或模式 | 边界 |
| --- | --- |
| Shell scripts | 脚本可作为内部实现资产，但不能成为正式入口。 |
| Ansible | Ansible 偏配置执行编排；AgentPlane 偏 Agent 任务入口、证据、台账和文档回写。 |
| Terraform | Terraform 偏声明云资源；AgentPlane 偏已存在主机和应用交付闭环。 |
| 1Panel / Docker Compose | 这些是可被管理的 substrate；正式任务入口仍是 `agentplane ...`。 |
| 应用仓库 CI/CD | 应用仓库负责构建和测试自身；AgentPlane 负责正式部署、验证和控制面记录。 |

## 推荐使用者

| 使用者 | 是否适合 |
| --- | --- |
| 需要 AI 协助维护少量服务器和应用的个人或小团队 | 适合 |
| 希望公开仓库和生产 secrets 严格分离的维护者 | 适合 |
| 需要大型多租户平台治理的团队 | 需要二次设计 |
| 需要强一致持续调谐控制器的场景 | 不适合当前版本 |

## 成熟度口径

当前项目是 alpha。可依赖的是仓库治理、文档治理、离线门禁、CLI-first 约束和 secrets 边界；仍在收敛的是发布自动化、provider 合同、app delivery schema 和 live gate 自动化。

## 正式入口

```bash
agentplane --help
agentplane repo health-check --repo-root .
agentplane repo release-check --repo-root .
```

## 最小验证

```bash
uv run python -m agentplane.cli repo health-check --repo-root .
```

## 关联文档

- [控制面合同](../architecture/control-plane.md)
- [开源准备度](open-source-readiness.md)
- [公开边界](publication-boundary.md)
- [发布流程](release-process.md)

