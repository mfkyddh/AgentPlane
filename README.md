# AgentPlane

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

> **给 AI Agent 的运维控制面**
>
> 你告诉 AI 目标，AgentPlane 确保它安全地检查、执行、验证、留痕。

---

## 解决什么问题？

让 AI 帮你运维服务器，结果：

```bash
# AI 直接执行命令
ssh prod "docker restart myapp"
```

- SSH 连不上？失败后才知
- 容器起不来？错误淹没在输出中
- 服务真的好了吗？没有验证
- 谁执行的？什么时候？查不到
- 想回滚？没有任何记录

**AgentPlane 的做法**：同样的需求，每一步都有计划、有验证、有记录、可回滚。

```bash
$ agentplane service apply --target prod --name myapp --execute

[检查] 主机在线 ✓
[执行] 重启容器 myapp ✓
[验证] HTTP 探针 200 OK ✓
[记录] 操作已保存，可随时回查
```

---

## 和直接 SSH 有什么不同？

| | 直接 SSH | **AgentPlane** |
|---|:---:|:---:|
| AI 可直接使用 | 需要人写脚本 | **AI 说人话就行** |
| 执行前有计划 | | **默认先计划** |
| 执行后有验证 | | **自动验证** |
| 操作有记录 | | **完整审计证据** |
| 安全隔离 | secrets 在脚本里 | **secrets 分离设计** |

---

## 快速开始

```bash
git clone <你的仓库地址> && cd AgentPlane
uv tool install -e .
agentplane bootstrap doctor --repo-root .
```

详细步骤见 [入门指南](docs/getting-started.md)。

---

## 文档

| 文档 | 回答什么 |
|------|---------|
| [愿景](docs/core/vision.md) | AgentPlane 是什么、面向谁、解决什么问题 |
| [原则](docs/core/principles.md) | 怎么想、怎么做决策 |
| [路线图](docs/core/roadmap.md) | 往哪走、当前在什么阶段 |
| [架构](docs/core/architecture.md) | 怎么建、5 域模型、投影模型、CLI 接口 |
| [入门指南](docs/getting-started.md) | 5 分钟跑起来 |
| [命令参考](docs/command-reference.md) | 有什么命令、怎么用 |
| [编码与协作规范](docs/conventions.md) | 技术栈、编码规则、协作协议 |
| [术语表](docs/glossary.md) | 核心术语定义 |
| [主线追踪器](PROGRESS.md) | 当前在做什么、进度、分支任务 |
| [版本变更](CHANGELOG.md) | 做过什么、版本里程碑 |

完整导航见 [docs/README.md](docs/README.md)。

---

## 参与项目

| 文档 | 说明 |
|------|------|
| [LICENSE](LICENSE) | MIT 开源许可证 |
| [CONTRIBUTING.md](CONTRIBUTING.md) | 如何参与开发 |
| [CHANGELOG.md](CHANGELOG.md) | 版本变更摘要 |

AI 协作规则见 [AGENTS.md](AGENTS.md)。
