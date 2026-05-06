---
status: active
owner: AgentPlane maintainers
last_verified: 2026-05-06
audience: both
---

# GStack 设置指南

结论：GStack 提供了强大的网页浏览、QA 测试和设计审查能力。团队成员需要安装 gstack 才能使用这些 skills。

---

## 安装步骤

### 1. 安装 bun（如果尚未安装）

```bash
BUN_VERSION="1.3.10"
tmpfile=$(mktemp)
curl -fsSL "https://bun.sh/install" -o "$tmpfile"
BUN_VERSION="$BUN_VERSION" bash "$tmpfile" && rm "$tmpfile"
```

添加到 PATH：

```bash
export BUN_INSTALL="$HOME/.bun"
export PATH="$BUN_INSTALL/bin:$PATH"
```

### 2. 克隆并安装 gstack

```bash
git clone --single-branch --depth 1 https://github.com/garrytan/gstack.git ~/.claude/skills/gstack
cd ~/.claude/skills/gstack
./setup
```

### 3. 配置项目

复制示例配置：

```bash
cp .claude/settings.example.json .claude/settings.json
```

---

## 可用 Skills

| Skill | 用途 |
|-------|------|
| `/browse` | 网页浏览和测试 |
| `/qa` | 质量保证测试 |
| `/review` | 代码审查 |
| `/ship` | 发布流程 |
| `/design-review` | 设计审查 |
| `/investigate` | 问题调查 |
| 更多... | 见 CLAUDE.md |

---

## 使用规范

**重要**：使用 `/browse` skill 进行所有网页浏览，**不要使用** `mcp__claude-in-chrome__*` 工具。

---

## 故障排查

### bun 未找到

确保 PATH 包含 bun：

```bash
export BUN_INSTALL="$HOME/.bun"
export PATH="$BUN_INSTALL/bin:$PATH"
```

### browse 二进制未构建

重新运行 setup：

```bash
cd ~/.claude/skills/gstack
./setup
```

---

## 关联文档

- [CLAUDE.md](../../CLAUDE.md) — GStack skills 列表
- [AGENTS.md](../../AGENTS.md) — AI 助手工作规范
