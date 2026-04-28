---
status: active
owner: AgentPlane maintainers
last_verified: 2026-04-29
superseded_by: null
audience: agent

---

# Skill Surface Audit

结论：AgentPlane 的核心卖点已从“AI 友好 CLI”升级为“Skill 暴露意图入口，CLI 执行正式闭环”。当前公开 Skill 面已按能力域重组；旧 provider/服务碎片入口只保留为 catalog alias 或 ignored 本地材料。

## 审计范围

本次核查覆盖 `.agents/skills` 当前工作区内容：

| 项 | 结果 |
| --- | --- |
| 公开 tracked skill | 12 |
| `.agents/skills/catalog.yaml` 登记数 | 12 |
| ignored 本地/维护者 skill | 4 |
| catalog 版本 | 2 |

目录与 catalog 的差异只允许来自 ignored 本地 skill：`nginxui-letsencrypt-cloudflare-dns01`、`tencent-cloud-service-migration`、`tencent-host-mihomo-openai-tuning`、`windows-mihomo-cloudflare-latency-debug`。如果这些能力要对外复用，必须先清理为通用模板；否则保留在本地 catalog 之外。

## 当前公开 Skill 面

| 分组 | 当前 skill | 职责 |
| --- | --- | --- |
| 领域 skill | `agentplane-infra-ops`、`agentplane-service-ops`、`agentplane-ingress-ops`、`agentplane-app-ops`、`agentplane-projection-ops`、`agentplane-repo-ops` | 稳定对象域和仓库治理入口 |
| Delivery workflow | `app-delivery-ops` | 应用接入、合同、构建、部署、验证、回写 |
| Host workflow | `host-onboarding-ops`、`toolchain-setup` | 主机纳管、安全基线、支撑工具链 |
| Service workflow | `docker-service-setup`、`openclaw-ops` | 初始服务安装、OpenClaw lane 选择与验证 |
| Ingress workflow | `site-migration-ops` | 单站迁移、并行验证、切换门禁 |
| ignored 本地专题 | 4 个本地 skill | 不进入公开 catalog；如要共享，先脱敏并模板化 |

## 已处理的问题

1. README 和顶层规范已明确 Skill 是 AI Agent 的能力入口。
2. catalog 已升级到 version 2，并由仓库测试强制 tracked Skill 与 catalog 双向一致。
3. 公开主入口已从 `onepanel-*` provider 视角收敛到 `agentplane-*` 对象域视角。
4. 多个 Docker 服务安装 skill 已合并为 `docker-service-setup`。
5. root/password SSH 入口已降级为 `host-onboarding-ops` 的 break-glass 说明，不再是默认公开 skill。
6. Node.js 与 Maven 工具链入口已合并为 `toolchain-setup`。
7. OpenClaw 三条路径已合并为 `openclaw-ops` lane 选择。

## 重构结果

公开 Skill 面重组为三层。

### 1. 领域 skill

| Skill | 合并来源 | 职责 |
| --- | --- | --- |
| `agentplane-infra-ops` | `host-ops`、`onepanel-panel-ops`、`onepanel-firewall-ops` 的正式入口部分 | 主机、网络、secrets、panel/firewall 的对象路由 |
| `agentplane-service-ops` | `onepanel-container-ops`、Docker 服务运行态片段 | 服务 search/get/verify/plan/apply |
| `agentplane-ingress-ops` | `onepanel-website-ops` | 网站入口、证书绑定、发布验证 |
| `agentplane-app-ops` | `onepanel-app-ops`、`app-resource-ops` | app object、app resource、catalog 和资源投影 |
| `agentplane-projection-ops` | `projection-ops`、`inventory-ledger-ops` | runtime env、ledger、inventory、doc-sync |
| `agentplane-repo-ops` | 新增 | repo health-check、docs-sanity、privacy-scan、release-check、fast test |

### 2. Workflow skill

| Skill | 合并来源 | 职责 |
| --- | --- | --- |
| `app-delivery-ops` | 保留并瘦身 | 应用接入、构建、部署、验证、回写 |
| `host-onboarding-ops` | `onepanel-host-setup`、`ubuntu-ssh-security-baseline` | 新主机纳管、1Panel 安装、安全基线 |
| `docker-service-setup` | Postgres、Redis、MinIO、nginx-ui、CLIProxyAPI、OpenClaw Docker skill | 通用 compose 服务落库、启动、健康检查、持久化验证 |
| `site-migration-ops` | `onepanel-openresty-site-migration` | 单站迁移、证书、并行验证、切换门禁 |
| `openclaw-ops` | 3 个 OpenClaw skill | Docker/official/Chrome bridge 三条路径的选择与验证 |
| `toolchain-setup` | `nodejs-lts-setup`、`maven-setup` | Node.js、npm/pnpm、Java、Maven 等支撑工具链 |

### 3. Reference / Local-only

| 类型 | 去向 |
| --- | --- |
| 服务专属 compose 参数 | `docs/reference/` 或 skill `references/` |
| 历史坑和现场经验 | `docs/runbooks/`、`docs/history/` 或 ignored local docs |
| 维护者专用云迁移、链路调优 | ignored local skill，不进入公开 catalog |
| root/password SSH 例外 | break-glass reference，不作为默认安全入口 |

## 后续执行顺序

| 阶段 | 动作 | 完成标准 |
| --- | --- | --- |
| P0 | 建立同步门禁 | 已完成 |
| P1 | catalog 收敛 | 已完成 |
| P2 | 领域重命名 | 已完成 |
| P3 | Docker skill 合并 | 已完成 |
| P4 | 安全入口分级 | 已完成 |
| P5 | 长文瘦身 | 已完成首轮；后续按实际 workflow 补 reference |

## 建议新增门禁

1. `catalog.yaml` 中每个 `source_path` 必须存在。
2. 每个 tracked `SKILL.md` 必须在 catalog 中登记。
3. 每个 skill frontmatter 的 `name` 必须等于目录名。
4. 每个 catalog `frontmatter_name` 必须与 skill frontmatter 一致。
5. 修改 `agentplane/cli`、`agentplane/domain`、`agentplane/runtime`、`infra/compose` 或 `templates` 时，PR 必须说明 skill 是否同步。

## 关联文档

- [control-plane-authoring.md](control-plane-authoring.md)
- [../reference/repository-structure.md](../reference/repository-structure.md)
- [../runbooks/control-plane-domain-onboarding.md](../runbooks/control-plane-domain-onboarding.md)
- [../architecture/decisions/0001-cli-first-control-plane.md](../architecture/decisions/0001-cli-first-control-plane.md)
