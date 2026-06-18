---
status: active
owner: AgentPlane maintainers
last_verified: 2026-06-18
audience: human
---

# 入门指南

> 结论：5 分钟完成安装、体检、第一个操作。不需要理解架构——跑起来再说。

---

## 安装

### 方式一：从 PyPI 安装（推荐）

```bash
pip install agentplane-cli
```

### 方式二：从源码安装

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

## 第一个完整操作（5 分钟）

### 1. 体检

```bash
agentplane infra bootstrap inspect-local --repo-root .
agentplane infra bootstrap doctor --repo-root .
```

体检通过，说明环境就绪。

### 2. 查看可用 Target

```bash
# 本地环境会显示 wsl（Windows Subsystem for Linux）
agentplane infra bootstrap inspect-local --repo-root .
```

输出示例：
```
Available targets:
  - wsl (local Windows Subsystem for Linux)
```

### 3. 查看本地服务（以 wsl 为例）

```bash
agentplane service search --target wsl --repo-root .
```

### 4. 查看应用

```bash
agentplane app object search --target wsl --repo-root .
```

### 5. 验证一个服务

从上一步获取服务名称，然后验证：

```bash
agentplane service verify --target wsl --name <服务名称> --repo-root .
```

**恭喜！** 你已经完成了第一个完整操作。

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
