# App Delivery 失败处理 Runbook

## 适用范围

本文只处理 `agentplane app delivery ...` 主路径中的失败：

- `validate-contract`
- `build-artifact`
- `ship-image`
- `render-runtime`
- `deploy`
- `verify`
- `inventory-refresh`
- `doc-sync`

不覆盖 1Panel 兼容 helper、手写 SSH、手写 Docker 修复或绕过合同的现场补丁。

## 总原则

先停在失败阶段，不继续执行后续阶段。  
每一步都保留正式入口、目标、应用名、`op_id` 和输出中的 error id。  
不能为了让后续命令通过而改 inventory、doc 或 secrets 的结果文件。

## 快速定位

| 失败阶段 | 先看什么 | 处理方式 |
| --- | --- | --- |
| `validate-contract` | 合同字段、target inventory、app resource registry、secret 文件作用域 | 修合同或真源对象；未通过前不构建、不部署 |
| `build-artifact` | 应用仓库 git 状态、版本推荐、`artifact.build_command` 输出 | 修应用仓库构建脚本或版本来源；不要伪造 tag |
| `ship-image` | 本地 Docker image、SSH/SCP、远端 `docker load` | 重新确认 image ref 与目标 SSH；不要改 compose 掩盖镜像缺失 |
| `render-runtime` | compose 模板、env template、依赖容器、port 和 volume | 修模板或合同；不要直接编辑渲染产物当真源 |
| `deploy --execute` | network preflight、env 文件、远端 compose 目录、旧控制面 transition | 先执行 rollback 计划，再修正真源后重跑 deploy |
| `verify --execute` | 容器状态、宿主机回环健康探针、公网探针 | 先区分 origin 失败还是 public ingress 失败 |
| `inventory-refresh --write` | 合同 `_meta`、service key、target inventory | 修合同和 inventory 输入，再重新 refresh |
| `doc-sync --write` | registry truth drift、summary path、server README | 修 registry 或合同，重新生成文档 |

## 标准止损顺序

1. 记录失败命令和输出，不改现场。
2. 重新运行只读检查：

```bash
agentplane app delivery validate-contract --target <target> --app <app> --repo-root <repo-root>
agentplane app delivery render-runtime --target <target> --app <app> --repo-root <repo-root> --image-ref <image:tag>
```

3. 如果失败发生在 `deploy --execute` 之后，先生成回滚计划：

```bash
agentplane app delivery rollback --target <target> --app <app> --repo-root <repo-root> --dry-run
```

4. 确认回滚计划指向预期旧控制面后再执行：

```bash
agentplane app delivery rollback --target <target> --app <app> --repo-root <repo-root> --execute
```

5. 回滚后做最小验证：

```bash
agentplane app delivery verify --target <target> --app <app> --repo-root <repo-root> --execute
```

## 典型分流

### 合同或 app resource 失败

错误里出现 `app.resource.resources_required`、`app.resource.secret_file_scope`、`app.resource.secret_file_missing` 或 `app.resource.registry_mismatch` 时，只修这些真源：

- 应用合同 `infra.tenant_resources`
- `inventory/servers/<target>/app-resources.json`
- `secrets/hosts/<target>/apps/<app>/resources/*.env`

不要把真实 secret 写进 `inventory/`、`docs/` 或合同。

### 部署后 origin 探针失败

先确认远端容器是否存在、是否启动、是否绑定了合同里的端口。正式验证仍使用：

```bash
agentplane app delivery verify --target <target> --app <app> --repo-root <repo-root> --execute
```

如果需要远端排障，走正式远端入口：

```bash
agentplane infra remote bash <target> --repo-root <repo-root> --command '<readonly command>'
```

### 部署后 public ingress 失败

如果 origin 探针健康而公网失败，优先查 ingress 对象、证书、反代 upstream 和防火墙。不要重新打包镜像，也不要修改 app runtime env 掩盖入口问题。

## 收口验证

修复后按主路径从失败点之前的最近只读阶段重跑，并最终执行：

```bash
agentplane repo health-check --repo-root .
agentplane repo release-check --repo-root .
```

不能跑 live `--execute` 时，必须在变更记录里明确说明未验证的目标、命令和原因。
