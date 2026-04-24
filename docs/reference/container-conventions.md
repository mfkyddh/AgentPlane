---
status: active
owner: AgentPlane maintainers
last_verified: 2026-04-24
superseded_by: null
---

# 容器与服务规范

> 本文档定义 AgentPlane 管理的 Docker 容器和服务的工作规范。核心约束见 `AGENTS.md` 必读摘要。

---

## Docker Compose

| # | 规则 | 级别 | 原因 |
|---|------|------|------|
| 1 | 运行时命令统一使用 `docker compose`（空格） | 🔴 | 旧版 `docker-compose`（连字符）已弃用 |
| 2 | 服务资产放在 `infra/compose/<service>/` | 🟡 | 统一存放，便于查找 |
| 3 | 本地运行时 Secrets 放在 `secrets/services/` | 🟡 | 与 compose 文件分离 |
| 4 | 服务模板放在 `templates/services/` | 🟡 | 非敏感模板可复用 |
| 5 | 可按需保留 `docker-compose.wsl.yml` 或 `docker-compose.<target>.yml` | 🟢 | 特定后端需要差异化配置时 |

---

## 容器命名

| # | 规则 | 级别 | 原因 |
|---|------|------|------|
| 1 | 测试环境容器名以 `-dev` 结尾 | 🔴 | 明确区分环境，防止误删生产 |
| 2 | 生产环境容器名以 `-prod` 结尾 | 🔴 | 同上 |

命名格式：`<服务名>-<环境>`，例如 `sub2api-prod`、`postgres-dev`。

---

## 网络与数据

| # | 规则 | 级别 | 原因 |
|---|------|------|------|
| 1 | 生产环境中，项目管理的容器和 1Panel 应用容器应接入 tracked truth 中声明的共享网络 | 🔴 | 保证服务间通信 |
| 2 | 专用网络只能作为附加（additive），不能替代共享网络 | 🟡 | 避免网络隔离导致服务不可达 |
| 3 | 持久化数据优先放在 `/data/<service>/...` | 🟡 | 统一数据盘路径，便于备份 |
