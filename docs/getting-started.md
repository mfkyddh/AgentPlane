# AgentPlane 入门指南

> 5 分钟上手 AgentPlane。

---

## 安装

```bash
git clone <你的仓库地址> && cd AgentPlane
uv tool install -e .
```

如果 `agentplane` 仍不可用：
```bash
uv run agentplane ...    # 或
python -m agentplane ...
```

---

## 体检

```bash
agentplane bootstrap inspect-local --repo-root .
agentplane bootstrap doctor --repo-root .
agentplane bootstrap init-secrets --repo-root .
agentplane bootstrap verify-secrets --repo-root .
```

---

## 查看状态

```bash
agentplane repo status --repo-root . --html tmp/agentplane-status.html
agentplane repo health-check --repo-root .
```

体检通过后，Agent 就可以接管后续操作了。

---

## 第一个操作

```bash
# 查看所有服务器
agentplane infra inventory <target> --repo-root .

# 搜索服务
agentplane service search --target <target> --repo-root .

# 验证应用
agentplane app object search --target <target> --repo-root .
```

---

## AI Agent 协作

你不需要记命令，只需要说人话：

> "帮我部署这个应用" → 匹配 Skill，制定计划，执行部署
> "这个 bug 怎么回事" → 调查原因，修复，验证
> "停" → 立即停止所有操作

详细协作规则见 [AGENTS.md](../AGENTS.md)。

---

## 下一步

- [架构概览](core/architecture.md) — 理解三层投影模型
- [命令参考](command-reference.md) — 所有 CLI 命令
- [部署第一个应用](tutorials/deploy-first-app.md) — 动手教程
- [排查部署失败](tutorials/troubleshoot-failed-deployment.md) — 常见错误

---

## 关联文档

- [README.md](../README.md) — 项目入口
- [AGENTS.md](../AGENTS.md) — AI 工作规范
- [术语表](glossary.md) — 核心术语
