---
status: active
owner: AgentPlane maintainers
last_verified: 2026-04-28
superseded_by: null
audience: both
---

# 公开边界规范

结论：公开仓库只保存可复用代码、模板、示例和离线测试；真实控制面状态、真实主机台账、生产 runbook、目标渲染文件和维护者专用 skill 必须保留在 ignored 本地工作区。

## 可公开

| 类型 | 放置位置 | 要求 |
| --- | --- | --- |
| CLI 与通用 domain/runtime 代码 | `agentplane/` | 不写真实域名、公网 IP、safe entrance 或维护者账号信息 |
| 通用文档 | `docs/architecture/`、`docs/reference/`、`docs/tutorials/`、`docs/runbooks/` | 使用 `<target>`、`example.net`、`203.0.113.0/24` 等示例值 |
| 非敏感模板 | `templates/` | 文件名用 `.example`，值用 placeholder |
| 本地开发 compose | `infra/compose/**/docker-compose.wsl.yml` | 只表达可复用本地开发形态 |
| 离线测试 | `tests/` | 使用 example 域名和 RFC 5737 测试网段 |

## 只留本地

| 类型 | 默认忽略规则 |
| --- | --- |
| 真实 host inventory、ledger、probe 输出 | `inventory/servers/`、`inventory/state-snapshot.md` |
| 生产/个人 runbook | `docs/runbooks/prod*-*.md`、`docs/runbooks/wsl-secrets-backup.md`、`docs/runbooks/wsl-zzz-skills-sync.md` |
| 目标渲染 compose | `infra/compose/**/docker-compose.prod*.yml` |
| 维护者专用 skill | `.agents/skills/tencent-*` 等 `.gitignore` 已声明路径 |
| 一次性主机修复脚本 | `.gitignore` 已声明的 `agentplane/scripts/remote/remote_*prod0*` 等 |

## 禁止进入 Git 可见文件

- 真实公网域名、真实公网 IP、1Panel safe entrance、面板路径。
- `password_authentication: true`、`permit_root_login: true` 等真实 SSH 暴露状态。
- 云账号、DNS 账号、证书目录、代理端点、生产 cron 计划等可帮助定位维护者现场的信息。
- 真实 `.env`、密钥、证书、token、密码。

## 门禁

每次准备提交或发布前运行：

```bash
agentplane repo privacy-scan --repo-root .
agentplane repo health-check --repo-root .
```

`privacy-scan` 与 `secret-scan` 分工不同：前者拦截公开情报泄露，后者拦截传统 secret。两者都必须通过。
