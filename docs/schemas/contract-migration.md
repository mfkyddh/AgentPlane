# Contract Schema 迁移指南

> 本文档记录 contract.yaml v1 到 v2 的迁移路径和废弃时间表。

---

## 版本历史

| 版本 | 状态 | 说明 |
|------|------|------|
| v1 | 已废弃（2026-08-11） | 旧版 artifact-first 格式 |
| v2 | 当前 | 新版 packaging-first 格式 |

---

## v1 vs v2 字段差异

### 新增字段（v2）

| 字段路径 | 类型 | 说明 |
|----------|------|------|
| `schema_version` | string | 必须为 `"v2"` |
| `artifact.output_path` | string | 构建产物输出路径 |
| `artifact.runtime_os` | string | 运行时操作系统（如 `linux`） |
| `artifact.runtime_arch` | string | 运行时架构（如 `amd64`） |
| `packaging.backend` | string | 打包后端：`native-posix` / `wsl-linux` / `ssh-linux` |
| `packaging.image_name` | string | 镜像名称 |
| `packaging.image_tag_rule` | string | 镜像 tag 规则 |
| `packaging.package_command` | string | 打包命令 |

### 移除字段（v1）

| 字段路径 | 说明 |
|----------|------|
| `artifact.image_name` | 已移至 `packaging.image_name` |
| `artifact.image_tag_rule` | 已移至 `packaging.image_tag_rule` |

### 保留字段

| 字段路径 | 说明 |
|----------|------|
| `app_id` | 应用 ID |
| `runtime.*` | 运行时配置 |
| `infra.*` | 基础设施配置 |
| `data.*` | 数据挂载配置 |
| `rollback.*` | 回滚配置 |
| `ingress.*` | 入口配置 |
| `artifact.build_command` | 构建命令 |

---

## 迁移步骤

### Step 1: 添加 schema_version

```yaml
schema_version: "v2"
```

### Step 2: 迁移 artifact 字段

**v1 格式：**
```yaml
artifact:
  build_command: "npm run build"
  image_name: "my-app"
  image_tag_rule: "<upstream>-zzz.<yyyymmdd>.v<n>.g<gitsha>"
```

**v2 格式：**
```yaml
artifact:
  build_command: "npm run build"
  output_path: "./dist"
  runtime_os: "linux"
  runtime_arch: "amd64"
```

### Step 3: 添加 packaging 配置

```yaml
packaging:
  backend: "native-posix"  # 或 "wsl-linux" / "ssh-linux"
  image_name: "my-app"
  image_tag_rule: "<upstream>-zzz.<yyyymmdd>.v<n>.g<gitsha>"
  package_command: "docker build -t {image_name}:{image_tag} ."
```

### Step 4: 验证合同

```bash
# 独立验证（不依赖 inventory）
agentplane app delivery validate-contract --standalone --contract-path deploy/agentplane/contract.yaml

# 完整验证（需要 inventory）
agentplane app delivery validate-contract --target prod0-main --app my-app
```

---

## 完整示例

### v1 合同

```yaml
app_id: "my-app"
runtime:
  container_name: "my-app-prod"
  container_port: 3000
  healthcheck:
    path: "/health"
  env_template: ".env"
  kind: "compose"
artifact:
  build_command: "npm run build"
  image_name: "my-app"
  image_tag_rule: "<upstream>-zzz.<yyyymmdd>.v<n>.g<gitsha>"
infra:
  depends_on_containers:
    - "postgres-main"
    - "redis-main"
data:
  mounts:
    - host_path: "/data/my-app/uploads"
      container_path: "/app/uploads"
rollback:
  previous_control_plane:
    kind: "systemd"
    service_name: "my-app"
ingress:
  mode: "public"
  public_sites:
    - domain: "my-app.example.com"
      port: 80
```

### v2 合同

```yaml
schema_version: "v2"
app_id: "my-app"
runtime:
  container_name: "my-app-prod"
  container_port: 3000
  healthcheck:
    path: "/health"
  env_template: ".env"
  kind: "compose"
artifact:
  build_command: "npm run build"
  output_path: "./dist"
  runtime_os: "linux"
  runtime_arch: "amd64"
packaging:
  backend: "native-posix"
  image_name: "my-app"
  image_tag_rule: "<upstream>-zzz.<yyyymmdd>.v<n>.g<gitsha>"
  package_command: "docker build -t {image_name}:{image_tag} ."
infra:
  depends_on_containers:
    - "postgres-main"
    - "redis-main"
data:
  mounts:
    - host_path: "/data/my-app/uploads"
      container_path: "/app/uploads"
rollback:
  previous_control_plane:
    kind: "systemd"
    service_name: "my-app"
ingress:
  mode: "public"
  public_sites:
    - domain: "my-app.example.com"
      port: 80
```

---

## 废弃时间表

| 日期 | 事件 |
|------|------|
| 2026-05-11 | v2 发布，v1 标记为废弃 |
| 2026-08-11 | v1 废弃，不再支持 |
| 2026-09-11 | v1 代码移除 |

---

## 常见问题

### Q: 如何确定当前合同版本？

检查合同文件中是否有 `schema_version` 字段：
- 有 `schema_version: "v2"` → v2
- 无 `schema_version` 字段 → v1

### Q: 迁移后需要更新 inventory 吗？

不需要。inventory 格式未变化，只需更新合同文件。

### Q: 打包后端如何选择？

| 后端 | 适用场景 |
|------|---------|
| `native-posix` | Linux 裸机部署 |
| `wsl-linux` | Windows WSL 环境 |
| `ssh-linux` | 远程 SSH 部署 |

### Q: 验证失败怎么办？

使用 `--standalone` 模式进行独立验证，可以定位合同本身的错误：

```bash
agentplane app delivery validate-contract --standalone --contract-path deploy/agentplane/contract.yaml
```

---

## 相关文档

- [Contract Schema v2](app-delivery-contract-v2.schema.json) — JSON Schema 定义
- [架构文档](../core/architecture.md) — 应用交付架构
- [命令参考](../command-reference.md) — CLI 命令说明
