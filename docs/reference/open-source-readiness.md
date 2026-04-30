---
status: active
owner: AgentPlane maintainers
last_verified: 2026-04-22
superseded_by: null
audience: agent
layer: engineering
---

# Open Source Readiness

结论：开源准备度基线，仓库对外开放前的必须项检查清单。

This repository is being shaped as a one-checkout, cross-platform open source control plane template.

Public positioning lives in [vision.md](../strategy/vision.md). Release maturity and staged goals live in [roadmap.md](../strategy/roadmap.md).

## 📋 Baseline Requirements

- A single checkout works on macOS, Linux, and Windows.
- Windows can use WSL as a backend without requiring a second source checkout.
- No active docs, templates, inventory, or skills depend on maintainer-local paths.
- Default tests are offline and deterministic.
- Live WSL, Docker, SSH, and provider validation is explicit.
- Real secrets stay out of Git.
- Maintainer-local inventories, runbooks, rendered compose files, and private skills stay ignored and out of public Git.
- Contributor, security, support, license, code style, tech stack, release process, and test architecture documents are present at the repository root or under `docs/reference/`.
- Roadmap, changelog, issue templates, and architecture decision records exist for public collaboration.
- Tests are grouped by domain directory with shared helpers isolated under `tests/support/`.
- Repository health checks are available through `agentplane repo health-check`.
- Git-visible files are scanned for obvious secret material in CI.
- Git-visible files are scanned for private environment material through `agentplane repo privacy-scan`.
- Active docs are checked through `agentplane repo docs-sanity`.
- Release readiness is checked through `agentplane repo release-check`.

## 🛠️ Remaining Hard-Cut Work

- Keep provider helpers internal and route public workflows through the formal CLI.
- Move remaining direct `tests/onepanel` script substrate coverage behind provider-level contracts where practical.
- Run live gate with `--execute` only in an explicitly prepared WSL/SSH/Docker environment.
- Keep release automation current after the first public tag.

---

## 🔐 公开边界

### 可公开

| 类型 | 放置位置 | 要求 |
| --- | --- | --- |
| CLI 与通用 domain/runtime 代码 | `agentplane/` | 不写真实域名、公网 IP、safe entrance 或维护者账号信息 |
| 通用文档 | `docs/architecture/`、`docs/reference/`、`docs/tutorials/`、`docs/runbooks/` | 使用 `<target>`、`example.net`、`203.0.113.0/24` 等示例值 |
| 非敏感模板 | `templates/` | 文件名用 `.example`，值用 placeholder |
| 本地开发 compose | `infra/compose/**/docker-compose.wsl.yml` | 只表达可复用本地开发形态 |
| 离线测试 | `tests/` | 使用 example 域名和 RFC 5737 测试网段 |

### 只留本地

| 类型 | 默认忽略规则 |
| --- | --- |
| 真实 host inventory、ledger、probe 输出 | `inventory/servers/`、`inventory/state-snapshot.md` |
| 生产/个人 runbook | `docs/runbooks/prod*-*.md`、`docs/runbooks/wsl-secrets-backup.md`、`docs/runbooks/wsl-zzz-skills-sync.md` |
| 目标渲染 compose | `infra/compose/**/docker-compose.prod*.yml` |
| 维护者专用 skill | `.agents/skills/tencent-*` 等 `.gitignore` 已声明路径 |
| 一次性主机修复脚本 | `.gitignore` 已声明的 `agentplane/scripts/remote/remote_*prod0*` 等 |

### 禁止进入 Git 可见文件

- 真实公网域名、真实公网 IP、1Panel safe entrance、面板路径。
- `password_authentication: true`、`permit_root_login: true` 等真实 SSH 暴露状态。
- 云账号、DNS 账号、证书目录、代理端点、生产 cron 计划等可帮助定位维护者现场的信息。
- 真实 `.env`、密钥、证书、token、密码。
