---
status: active
owner: AgentPlane maintainers
last_verified: 2026-04-29
superseded_by: null
audience: agent

---

# Skill Surface Audit

结论：AgentPlane 的核心卖点应从“AI 友好 CLI”升级为“Skill 暴露意图入口，CLI 执行正式闭环”。当前 skill 已覆盖主要经验，但存在 catalog 漂移、命名碎片化、重复流程和部分 raw shell 主路径，需要按能力域重构。

## 审计范围

本次核查覆盖 `.agents/skills` 当前工作区内容：

| 项 | 结果 |
| --- | --- |
| skill 目录数 | 29 |
| 含 `SKILL.md` 的目录数 | 29 |
| `.agents/skills/catalog.yaml` 登记数 | 25 |
| Git 跟踪的 skill | 25 |
| ignored 本地/维护者 skill | 4 |

catalog 与目录差异来自 ignored 本地 skill：`nginxui-letsencrypt-cloudflare-dns01`、`tencent-cloud-service-migration`、`tencent-host-mihomo-openai-tuning`、`windows-mihomo-cloudflare-latency-debug`。如果这些能力要对外复用，必须先清理为通用模板；否则应保留在本地 catalog 之外。

## 当前分组

| 分组 | 当前 skill | 判断 |
| --- | --- | --- |
| 控制面核心 | `app-delivery-ops`、`app-resource-ops`、`host-ops`、`inventory-ledger-ops`、`projection-ops` | 最接近长期形态，保留并补齐同步门禁 |
| 1Panel 对象 | `onepanel-app-ops`、`onepanel-container-ops`、`onepanel-cronjob-ops`、`onepanel-firewall-ops`、`onepanel-panel-ops`、`onepanel-website-ops` | 过度按 provider 命名，和 `app/service/ingress/infra` 域有重复 |
| 1Panel workflow | `onepanel-host-setup`、`onepanel-openresty-site-migration` | workflow 价值明确，但正文偏长，部分内容应下沉 reference |
| Docker 服务安装 | `postgres-docker-setup`、`redis-docker-setup`、`minio-docker-setup`、`nginxwebui-docker-setup`、`cliproxyapi-docker-setup`、`openclaw-docker-setup` | 模式高度重复，应抽成通用 Docker service skill 加服务引用 |
| 主机/工具链 | `nodejs-lts-setup`、`maven-setup`、`ssh-root-login-setup`、`ubuntu-ssh-security-baseline` | 有通用运维价值，但不都属于 AgentPlane 控制面核心 |
| OpenClaw 专题 | `openclaw-official-wsl-setup`、`openclaw-docker-setup`、`openclaw-windows-chrome-bridge` | 经验很细，但重复 WSL、代理、脚本路由细节，应重组为产品专题 |
| ignored 本地专题 | 4 个本地 skill | 不应进入公开主 catalog；如要共享，先脱敏并模板化 |

## 主要问题

1. **项目定位没有把 Skill 放在第一层**：README 和顶层规范过去强调 CLI，但没有明确“Skill 是 AI Agent 的主要能力入口”。
2. **catalog 缺少机械门禁**：目前能看到 tracked skill 与 catalog 对齐，但没有测试强制未来保持一致。
3. **1Panel skill 与对象域重复**：同一能力在 `onepanel-*`、`app`、`service`、`ingress`、`infra` 之间来回映射，Agent 触发时容易选 provider 视角而不是对象域视角。
4. **Docker 安装 skill 大量重复**：镜像 pin、`infra/compose/<service>`、`/data/<service>`、health check、compose up、持久化验证几乎是同一模板。
5. **安全基线存在方向冲突**：`ssh-root-login-setup` 允许 root/password 场景，`ubuntu-ssh-security-baseline` 强制 key-only、禁 root。二者都合理，但不应并列为同等级默认入口。
6. **部分 skill 仍以 raw shell / Docker Compose 为主路径**：这和 CLI-first 方向冲突。短期可作为 workflow skill，长期应推动 CLI 或 provider surface 接管。
7. **专题 skill 过长**：一些 skill 包含大量历史经验、现场坑和完整操作手册，已接近 runbook。Skill 应保留触发、路由、边界和验证，细节下沉到 reference/runbook。

## 重构建议

不考虑兼容性时，建议把 skill 面重组为三层。

### 1. 领域 skill

| 新 skill | 合并来源 | 职责 |
| --- | --- | --- |
| `agentplane-infra-ops` | `host-ops`、`onepanel-panel-ops`、`onepanel-firewall-ops` 的正式入口部分 | 主机、网络、secrets、panel/firewall 的对象路由 |
| `agentplane-service-ops` | `onepanel-container-ops`、Docker 服务运行态片段 | 服务 search/get/verify/plan/apply |
| `agentplane-ingress-ops` | `onepanel-website-ops` | 网站入口、证书绑定、发布验证 |
| `agentplane-app-ops` | `onepanel-app-ops`、`app-resource-ops` | app object、app resource、catalog 和资源投影 |
| `agentplane-projection-ops` | `projection-ops`、`inventory-ledger-ops` | runtime env、ledger、inventory、doc-sync |
| `agentplane-repo-ops` | 新增 | repo health-check、docs-sanity、privacy-scan、release-check |

### 2. Workflow skill

| 新 skill | 合并来源 | 职责 |
| --- | --- | --- |
| `app-delivery-ops` | 保留并瘦身 | 应用接入、构建、部署、验证、回写 |
| `host-onboarding-ops` | `onepanel-host-setup`、`ubuntu-ssh-security-baseline` | 新主机纳管、1Panel 安装、安全基线 |
| `docker-service-setup` | Postgres、Redis、MinIO、nginx-ui、CLIProxyAPI、OpenClaw Docker skill | 通用 compose 服务落库、启动、健康检查、持久化验证 |
| `site-migration-ops` | `onepanel-openresty-site-migration` | 单站迁移、证书、并行验证、切换门禁 |
| `openclaw-ops` | 3 个 OpenClaw skill | Docker/official/Chrome bridge 三条路径的选择与验证 |

### 3. Reference / Local-only

| 类型 | 去向 |
| --- | --- |
| 服务专属 compose 参数 | `docs/reference/` 或 skill `references/` |
| 历史坑和现场经验 | `docs/runbooks/`、`docs/history/` 或 ignored local docs |
| 维护者专用云迁移、链路调优 | ignored local skill，不进入公开 catalog |
| root/password SSH 例外 | break-glass reference，不作为默认安全入口 |

## 推荐执行顺序

| 阶段 | 动作 | 完成标准 |
| --- | --- | --- |
| P0 | 建立同步门禁 | AGENTS、authoring 文档和 README 明确 Skill 是入口；新增 catalog/skill sanity 测试 |
| P1 | catalog 收敛 | tracked skill 与 catalog 双向一致；ignored local skill 有单独本地说明 |
| P2 | 领域重命名 | 把 provider 命名从主入口移到 reference，主 skill 改为 `agentplane-*` 域 |
| P3 | Docker skill 合并 | 6 个服务安装 skill 合为 `docker-service-setup` + 服务 reference |
| P4 | 安全入口分级 | 默认使用 `host-onboarding-ops` + 安全基线；root 登录只保留 break-glass |
| P5 | 长文瘦身 | 每个 skill 控制在触发、边界、命令、验证和下钻链接；长流程下沉 runbook/reference |

## 建议新增门禁

1. `catalog.yaml` 中每个 `source_path` 必须存在。
2. 每个 tracked `SKILL.md` 必须在 catalog 中登记，除非明确标记 ignored/private。
3. 每个 skill frontmatter 的 `name` 必须等于目录名。
4. 每个正式 skill 必须出现至少一个 `agentplane` 命令，或显式标记为 bootstrap/break-glass/local-only。
5. 修改 `agentplane/cli`、`agentplane/domain`、`agentplane/runtime`、`infra/compose` 或 `templates` 时，PR 必须说明 skill 是否同步。

## 关联文档

- [control-plane-authoring.md](control-plane-authoring.md)
- [../reference/repository-structure.md](../reference/repository-structure.md)
- [../runbooks/control-plane-domain-onboarding.md](../runbooks/control-plane-domain-onboarding.md)
- [../architecture/decisions/0001-cli-first-control-plane.md](../architecture/decisions/0001-cli-first-control-plane.md)
