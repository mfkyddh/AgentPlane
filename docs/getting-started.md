---
status: active
owner: AgentPlane maintainers
last_verified: 2026-05-07
audience: human
---

# 入门指南

> 结论：5 分钟完成安装、体检、第一个操作。不需要理解架构——跑起来再说。

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

体检通过，说明环境就绪。

---

## 查看状态

```bash
agentplane repo status --repo-root . --html tmp/agentplane-status.html
agentplane repo health-check --repo-root .
```

---

## 第一个操作

```bash
# 查看所有服务器
agentplane infra inventory <target> --repo-root .

# 搜索服务
agentplane service search --target <target> --repo-root .

# 查看应用
agentplane app object search --target <target> --repo-root .
```

---

## AI Agent 协作

你不需要记命令，只需要说人话：

- "帮我部署这个应用" → 匹配 Skill，制定计划，执行部署
- "这个 bug 怎么回事" → 调查原因，修复，验证
- "停" → 立即停止所有操作

详细协作规则见 [AGENTS.md](../AGENTS.md)。

---

## 下一步

| 你想做什么 | 去哪里 |
|-----------|--------|
| 理解架构 | [架构](core/architecture.md) |
| 查命令 | [命令参考](command-reference.md) |
| 了解规则 | [编码与协作规范](conventions.md) |
| 了解术语 | [术语表](glossary.md) |

---

## 关联文档

- [愿景](core/vision.md) — AgentPlane 是什么、解决什么问题
- [架构](core/architecture.md) — 域、投影模型、CLI 接口
- [命令参考](command-reference.md) — 所有 CLI 命令
- [术语表](glossary.md) — 核心术语
