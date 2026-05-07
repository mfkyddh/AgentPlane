# AgentPlane 文档

---

## 快速导航

| 我想... | 去这里 |
|---------|--------|
| 快速上手 | [入门指南](getting-started.md) |
| 理解架构 | [架构](core/architecture.md) |
| 查找命令 | [命令参考](command-reference.md) |
| 了解技术栈 | [技术栈](tech-stack.md) |
| 使用 WebUI | [WebUI](webui.md) |
| 编码规范 | [编码与协作规范](conventions.md) |
| 部署应用 | [教程：部署第一个应用](tutorials/deploy-first-app.md) |
| 排查问题 | [教程：排查部署失败](tutorials/troubleshoot-failed-deployment.md) |
| 添加服务器 | [教程：添加新服务器](tutorials/add-new-server.md) |

---

## 战略文档（项目根基）

- [愿景](core/vision.md) — 项目定位、目标用户、项目模型、核心价值
- [原则](core/principles.md) — 道法术三层原则体系
- [路线图](core/roadmap.md) — Alpha → Beta → GA 三阶段推进
- [架构](core/architecture.md) — 5 域模型、投影模型、CLI 合同、执行闭环
- [决策记录](decisions/) — 关键决策追溯
- [术语表](glossary.md) — 唯一术语真源

## 战术文档（具体实现）

- [技术栈](tech-stack.md) — Python/uv/Docker Compose/跨平台约束
- [命令参考](command-reference.md) — 所有 CLI 命令
- [WebUI](webui.md) — WebUI 架构和使用
- [入门指南](getting-started.md) — 5 分钟上手
- [编码与协作规范](conventions.md) — 编码行为准则、文档编写规范、协作协议
- [Maintainer 指南](maintainer-guide.md) — 治理资产约束和协作规则

---

## 运维手册

- [应用交付流程](runbooks/app-project-delivery-workflow.md) — 应用接入与交付主路径
- [Agent 执行闭环](runbooks/control-plane-agent-execution-flow.md) — 执行 → 验证 → 记录
- [Secrets 引导](runbooks/bootstrap-secrets.md) — secrets 初始化
- [WSL 治理](runbooks/wsl-host-governance.md) — WSL 主机治理
- [生产环境治理](runbooks/prod0-main-governance.md) — 生产环境规范

---

## 归档文档

历史文档、旧 runbook、战略决策记录等已归档到 [archive/](archive/)。

---

## AI 入口

- [AGENTS.md](../AGENTS.md) — AI 工作规范
- [CLAUDE.md](../CLAUDE.md) — Claude 特有指令
