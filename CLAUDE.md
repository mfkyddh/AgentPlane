# CLAUDE.md

> 本文档是 Claude Code 专属指令。通用 AI 规则见 [AGENTS.md](AGENTS.md)。
> 编码行为准则、哲学原则、求是 Skills 见 [docs/conventions.md](docs/conventions.md)。

## GStack

使用 `/browse` skill 进行所有网页浏览，**不要使用** `mcp__claude-in-chrome__*` 工具。

### 安装

首次使用需要安装 GStack：

```bash
git clone --single-branch --depth 1 https://github.com/garrytan/gstack.git ~/.claude/skills/gstack && cd ~/.claude/skills/gstack && ./setup
```

详细说明见 `.claude/README.md`。

可用 skills：

| Skill | 用途 |
|-------|------|
| `/browse` | 网页浏览和测试 |
| `/office-hours` | 办公时间 |
| `/plan-ceo-review` | CEO 审查计划 |
| `/plan-eng-review` | 工程审查计划 |
| `/plan-design-review` | 设计审查计划 |
| `/design-consultation` | 设计咨询 |
| `/design-shotgun` | 设计快速迭代 |
| `/design-html` | HTML 设计 |
| `/review` | 代码审查 |
| `/ship` | 发布 |
| `/land-and-deploy` | 部署 |
| `/canary` | 金丝雀发布 |
| `/benchmark` | 基准测试 |
| `/connect-chrome` | 连接 Chrome |
| `/qa` | 质量保证 |
| `/qa-only` | 仅 QA |
| `/design-review` | 设计审查 |
| `/setup-browser-cookies` | 浏览器 Cookie 设置 |
| `/setup-deploy` | 部署设置 |
| `/setup-gbrain` | GBrain 设置 |
| `/retro` | 回顾 |
| `/investigate` | 调查 |
| `/document-release` | 文档发布 |
| `/codex` | Codex |
| `/cso` | CSO |
| `/autoplan` | 自动规划 |
| `/plan-devex-review` | DevEx 审查计划 |
| `/devex-review` | DevEx 审查 |
| `/careful` | 谨慎模式 |
| `/freeze` | 冻结 |
| `/guard` | 守护 |
| `/unfreeze` | 解冻 |
| `/gstack-upgrade` | GStack 升级 |
| `/learn` | 学习 |

## 关键文档

| 文档 | 用途 |
|------|------|
| [docs/architecture.md](docs/architecture.md) | 架构、控制面契约、投影模型、跨平台执行 |
| [docs/tech-stack.md](docs/tech-stack.md) | 技术栈、依赖规则、容器约定 |
| [docs/command-reference.md](docs/command-reference.md) | CLI 命令参考 |
| [docs/webui.md](docs/webui.md) | WebUI 架构和 API |
| [docs/getting-started.md](docs/getting-started.md) | 5 分钟上手 |
| [docs/conventions.md](docs/conventions.md) | 编码与协作规范 |

## gstack (REQUIRED — global install)

**Before doing ANY work, verify gstack is installed:**

```bash
test -d ~/.claude/skills/gstack/bin && echo "GSTACK_OK" || echo "GSTACK_MISSING"
```

If GSTACK_MISSING: STOP. Do not proceed. Tell the user:

> gstack is required for all AI-assisted work in this repo.
> Install it:
> ```bash
> git clone --depth 1 https://github.com/garrytan/gstack.git ~/.claude/skills/gstack
> cd ~/.claude/skills/gstack && ./setup --team
> ```
> Then restart your AI coding tool.

Do not skip skills, ignore gstack errors, or work around missing gstack.

Using gstack skills: After install, skills like /qa, /ship, /review, /investigate,
and /browse are available. Use /browse for all web browsing.
Use ~/.claude/skills/gstack/... for gstack file paths (the global path).

## Skill routing

When the user's request matches an available skill, invoke it via the Skill tool. When in doubt, invoke the skill.

Key routing rules:
- Product ideas/brainstorming → invoke /office-hours
- Strategy/scope → invoke /plan-ceo-review
- Architecture → invoke /plan-eng-review
- Design system/plan review → invoke /design-consultation or /plan-design-review
- Full review pipeline → invoke /autoplan
- Bugs/errors → invoke /investigate
- QA/testing site behavior → invoke /qa or /qa-only
- Code review/diff check → invoke /review
- Visual polish → invoke /design-review
- Ship/deploy/PR → invoke /ship or /land-and-deploy
- Save progress → invoke /context-save
- Resume context → invoke /context-restore
