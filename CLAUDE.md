# CLAUDE.md

> 本文档是 Claude Code 专属指令。通用 AI 规则见 [AGENTS.md](AGENTS.md)。
> 编码行为准则、哲学原则、求是 Skills 见 [docs/conventions.md](docs/conventions.md)。

## 会话初始化

每次会话开始时，先读 [AGENTS.md](AGENTS.md) 中的规则，再开始工作。

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
| [docs/core/architecture.md](docs/core/architecture.md) | 架构、域、投影模型、CLI 接口 |
| [docs/command-reference.md](docs/command-reference.md) | CLI 命令参考 |
| [docs/getting-started.md](docs/getting-started.md) | 5 分钟上手 |
| [docs/conventions.md](docs/conventions.md) | 技术栈、编码规则、协作规范 |
| [docs/maintainer-guide.md](docs/maintainer-guide.md) | 治理资产约束、Skill 同步门禁 |

## 思维透明（强制）

**每次思考时，必须同步告知用户你使用了哪些 skill 和哪些哲学思想。**

输出格式（在回复开头或关键决策点）：

```
🧠 思维过程
- Skill: [使用的 skill，无则写"无"]
- 哲学: [应用的思想，无则写"无"]
- 理由: [为什么选择这些 skill/思想，一句话]
```

### 可用的 Skill

| Skill | 用途 |
|-------|------|
| agentplane-infra-ops | 基础设施操作（SSH、compose、bootstrap） |
| agentplane-app-ops | 应用生命周期（onboard、delivery、resource） |
| agentplane-service-ops | 服务层操作 |
| agentplane-ingress-ops | Ingress/网站管理 |
| agentplane-projection-ops | 投影层操作 |
| agentplane-project-ops | 项目/仓库操作 |
| app-delivery-ops | 应用交付 workflow |
| site-migration-ops | 站点迁移 |
| tencent-cloud-service-migration | 腾讯云服务迁移 |
| host-onboarding-ops | 主机 onboarding |
| docker-service-setup | Docker 服务部署 |
| toolchain-setup | 工具链安装 |
| openclaw-ops | OpenClaw 操作 |

### 可用的哲学思想

**道（根本信念）**：
- **实事求是** — 从客观事实出发，不凭想象设计
- **矛盾分析法** — 识别主要矛盾，集中解决

**法（思维方法）**：
- **调查研究** — 先调查再判断，通过实践验证
- **群众路线** — 收集多方意见，系统化后返回验证
- **集中兵力** — 聚焦核心，不分散精力
- **统筹兼顾** — 多目标平衡
- **持久战略** — 长期复杂任务的分阶段推进
- **奥卡姆剃刀** — 如无必要，勿增实体

**术（工程纪律）**：
- **证据优先** — 所有操作有记录、有验证
- **YAGNI** — 只实现当前需要的功能
- **DRY** — 消除重复代码
- **KISS** — 保持简单

**其他**：
- **费曼学习法** — 用简单语言解释复杂概念
- **苏格拉底式提问** — 通过提问引导思考
- **实践认识论** — 实践是检验真理的唯一标准
- **批评与自我批评** — 完成工作后结构化审视
- **星火燎原** — 从零开始、资源有限时的策略

> 完整体系见 [docs/core/principles.md](docs/core/principles.md)（道法术三层）和 [qiushi skills](.agents/skills/)。

## PROGRESS.md 维护

git post-commit hook 会自动将每次 commit 追加到 PROGRESS.md 的分支任务表。此外：

- **重要工作完成后**（重构、新功能、关键修复），手动更新 PROGRESS.md 对应条目的状态和说明
- **分支任务完成时**，将状态改为"已完成"
- **新阶段开始时**，在主线条件表中更新状态
- commit message 使用 conventional commits 前缀（feat/fix/refactor/docs/test/chore）以触发 hook

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
