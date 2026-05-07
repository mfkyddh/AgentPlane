---
status: archived
owner: AgentPlane maintainers
last_verified: 2026-04-24
superseded_by: null
audience: agent
layer: engineering
---


# 容器与服务规范

结论：Docker Compose 与容器命名、网络、持久化的统一规范。

> 本文档定义 AgentPlane 管理的 Docker 容器和服务的工作规范。核心约束见 `AGENTS.md` 必读摘要。

---

## 📋 Docker Compose

| # | 规则 | 级别 | 原因 |
|---|------|------|------|
| 1 | 运行时命令统一使用 `docker compose`（空格） | 🔴 | 旧版 `docker-compose`（连字符）已弃用 |
| 2 | 服务资产放在 `infra/compose/<service>/` | 🟡 | 统一存放，便于查找 |
| 3 | 本地运行时 Secrets 放在 `secrets/services/` | 🟡 | 与 compose 文件分离 |
| 4 | 服务模板放在 `templates/services/` | 🟡 | 非敏感模板可复用 |
| 5 | 可按需保留 `docker-compose.wsl.yml` 或 `docker-compose.<target>.yml` | 🟢 | 特定后端需要差异化配置时 |

---

## 📌 容器命名

| # | 规则 | 级别 | 原因 |
|---|------|------|------|
| 1 | 测试环境容器名以 `-dev` 结尾 | 🔴 | 明确区分环境，防止误删生产 |
| 2 | 生产环境容器名以 `-prod` 结尾 | 🔴 | 同上 |

命名格式：`<服务名>-<环境>`，例如 `sub2api-prod`、`postgres-dev`。

---

## 📌 网络与数据

| # | 规则 | 级别 | 原因 |
|---|------|------|------|
| 1 | 生产环境中，项目管理的容器和 1Panel 应用容器应接入 tracked truth 中声明的共享网络 | 🔴 | 保证服务间通信 |
| 2 | 专用网络只能作为附加（additive），不能替代共享网络 | 🟡 | 避免网络隔离导致服务不可达 |
| 3 | 持久化数据优先放在 `/data/<service>/...` | 🟡 | 统一数据盘路径，便于备份 |

---

## 📋 Docker 应用打包规范

Docker 类应用接入时，采用"宿主机构建 + runtime-only Dockerfile"模式。

### 核心原则

1. **宿主机构建**：在 WSL 宿主机完成前端构建、后端编译，产物放到 `dist/oplinux/`
2. **Runtime-only Dockerfile**：只复制 `dist/oplinux/` 中的产物，不在 Docker 内重新源码编译
3. **正式交付链路**：`build-artifact → ship-image → render-runtime → plan/apply/verify → inventory/doc-sync`

### 推荐目录结构

```
deploy/
  build-runtime-artifacts.sh    # 宿主机构建脚本
  package-runtime-image.sh      # 打包脚本
  Dockerfile.runtime            # Runtime-only Dockerfile
  docker-entrypoint.sh
  op/
    contract.yaml               # 应用合同
dist/
  oplinux/
    <app-binary>
    resources/
```

### 合同模板要点

```yaml
schema_version: 2
app_id: demo
artifact:
  build_command: bash deploy/build-runtime-artifacts.sh
  output_path: dist/oplinux
packaging:
  image_name: demo-prod
  package_command: bash deploy/package-runtime-image.sh
runtime:
  kind: compose
  container_name: demo-prod
```

### 不要这样做

- 不要把依赖安装和编译全部塞进正式 Docker build 主路径
- 不要让 runtime Dockerfile 依赖整个源码树
- 不要在应用仓库里复制一套正式生产控制面脚本
