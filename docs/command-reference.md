---
status: active
owner: AgentPlane maintainers
last_verified: 2026-05-07
audience: both
---

# 命令参考

> 结论：所有正式操作通过 `agentplane <domain> <surface> <verb> [flags]` 进入。本文列出所有可用命令，按域组织。命令形态的详细说明见 [架构 > CLI 接口规范](core/architecture.md#cli-接口规范)。

---

## 命令形态

```bash
agentplane <domain> <surface> <verb> [flags]
```

| 部分 | 说明 | 示例 |
|------|------|------|
| `<domain>` | 域 | `infra`、`service`、`app`、`ingress`、`project` |
| `<surface>` | 对象面或工作流面 | `service`、`app delivery` |
| `<verb>` | 动作 | `search`、`get`、`plan`、`apply`、`verify` |
| `[flags]` | 可选参数 | `--target`、`--repo-root`、`--json` |

---

## infra 域：Target 配置

管理 Target（目标环境）的主机、网络、Secrets。

```bash
# 主机纳管、资产盘点
agentplane infra inventory <target> --repo-root <repo-root>

# 安全审计
agentplane infra audit <target> --repo-root <repo-root>

# 远程命令执行
agentplane infra remote bash <target> -- uname -a

# 网络检查、防火墙
agentplane infra network audit <target> --repo-root <repo-root>
agentplane infra network firewall plan <target> --repo-root <repo-root>
agentplane infra network firewall apply <target> --repo-root <repo-root> --execute

# 定时任务管理
agentplane infra automation search <target> --repo-root <repo-root>
agentplane infra automation plan <target> --repo-root <repo-root>
agentplane infra automation apply <target> --repo-root <repo-root> --execute

# Secrets 管理
agentplane infra secrets sync-layout <target> --repo-root <repo-root>

# 健康检查
agentplane infra health <target> --repo-root <repo-root>

# Bootstrap
agentplane infra bootstrap doctor --repo-root .
agentplane infra bootstrap inspect-local --repo-root .
agentplane infra bootstrap init-secrets --repo-root .
agentplane infra bootstrap verify-secrets --repo-root .
```

---

## service 域：运行时管理

管理所有 Docker 容器的健康、重启、日志（包括基础设施容器和业务容器）。

```bash
# 搜索服务
agentplane service search --target <target> --repo-root <repo-root>

# 查看服务状态
agentplane service get --target <target> --name <service> --repo-root <repo-root>

# 验证服务健康
agentplane service verify --target <target> --name <service> --repo-root <repo-root>

# 计划操作
agentplane service plan --target <target> --name <service> --operation restart --repo-root <repo-root>

# 执行操作
agentplane service apply --target <target> --name <service> --execute --repo-root <repo-root>

# 公网端点验证
agentplane service public-endpoint verify --target <target> --name <service> --repo-root <repo-root>
```

---

## app 域：应用交付生命周期

管理应用的 catalog、构建、部署、回滚。

### 应用对象 (app object)

```bash
# 搜索应用
agentplane app object search --target <target> --repo-root <repo-root>

# 获取应用详情
agentplane app object get --target <target> --app <app> --repo-root <repo-root>

# 发现未纳管应用
agentplane app object discover --target <target> --repo-root <repo-root>
```

### 应用资源 (app resource)

```bash
# 搜索资源
agentplane app resource search --target <target> --repo-root <repo-root>

# 获取资源详情
agentplane app resource get --target <target> --app <app> --repo-root <repo-root>

# 验证资源
agentplane app resource verify --target <target> --app <app> --repo-root <repo-root>

# 刷新台账
agentplane app resource refresh-ledger --target <target> --app <app> --repo-root <repo-root> --write
```

### 应用交付 (app delivery)

```bash
# 合约验证
agentplane app delivery validate-contract --target <target> --app <app> --repo-root <repo-root>

# 构建产物
agentplane app delivery build-artifact --target <target> --app <app> --repo-root <repo-root> --image-tag <tag>

# 推送镜像
agentplane app delivery ship-image --target <target> --app <app> --repo-root <repo-root> --image-ref <image:tag>

# 渲染运行时
agentplane app delivery render-runtime --target <target> --app <app> --repo-root <repo-root> --image-ref <image:tag>

# 预览部署
agentplane app delivery deploy --target <target> --app <app> --repo-root <repo-root> --image-ref <image:tag> --dry-run

# 执行部署
agentplane app delivery deploy --target <target> --app <app> --repo-root <repo-root> --image-ref <image:tag> --execute

# 部署验证
agentplane app delivery verify --target <target> --app <app> --repo-root <repo-root> --execute

# 回滚
agentplane app delivery deploy --target <target> --app <app> --repo-root <repo-root> --image-ref <image:tag> --rollback

# 刷新 inventory
agentplane app delivery inventory-refresh --target <target> --app <app> --repo-root <repo-root> --write

# 文档同步
agentplane app delivery doc-sync --target <target> --app <app> --repo-root <repo-root> --write
```

---

## ingress 域：公网入口

管理域名、SSL、路由。

```bash
# 搜索入口
agentplane ingress search --target <target> --repo-root <repo-root>

# 查看入口详情
agentplane ingress get --target <target> --alias <alias> --repo-root <repo-root>

# 验证公网访问
agentplane ingress verify --target <target> --alias <alias> --repo-root <repo-root>

# 刷新台账
agentplane ingress refresh-ledger --target <target> --repo-root <repo-root> --write

# 发布计划
agentplane ingress publish plan --target <target> --config-file <config-file> --cloudflare-env-file <cloudflare-env-file> --repo-root <repo-root>

# 执行发布
agentplane ingress publish apply --target <target> --config-file <config-file> --cloudflare-env-file <cloudflare-env-file> --repo-root <repo-root> --execute
```

---

## project 域：项目治理

管理仓库健康、投影验证、Skill 治理。

```bash
# 仓库状态
agentplane project status --repo-root . --html tmp/agentplane-status.html

# 健康检查
agentplane project health-check --repo-root .

# 文档检查
agentplane project docs-sanity --repo-root .
agentplane project doc-layer --repo-root .

# 安全扫描
agentplane project secret-scan --repo-root .
agentplane project privacy-scan --repo-root .

# Skill 治理
agentplane project skills check --repo-root .
agentplane project skills list --repo-root .

# 投影管理
agentplane project projection runtime-env plan --target <target> --app <app> --repo-root <repo-root>
agentplane project projection runtime-env verify --target <target> --app <app> --repo-root <repo-root>
agentplane project projection verification run --target <target> --profile <profile> --repo-root <repo-root>
agentplane project projection fixture plan --target <target> --profile <profile> --repo-root <repo-root>
agentplane project projection ledger refresh --target <target> --repo-root <repo-root> --write
```

---

## 工具命令

### WebUI

```bash
# 启动 WebUI
agentplane web --host 127.0.0.1 --port 8080

# 带认证的生产部署
agentplane web --host 0.0.0.0 --port 8080 --token <your-token>
```

### 测试

```bash
# 快速测试
agentplane test fast --tb=short

# 完整测试
agentplane test full
```

---

## 公共 Flags

| Flag | 说明 |
|------|------|
| `--target` / `--env` | 目标环境 |
| `--repo-root` | 仓库根目录 |
| `--json` | 结构化输出 |
| `--write` | 写回派生产物 |
| `--dry-run` | 预览模式 |
| `--execute` | 执行模式（与 `--dry-run` 互斥） |

---

## 关联文档

- [架构](core/architecture.md) — 域、投影模型、CLI 接口规范
- [愿景](core/vision.md) — 项目定位、项目模型
- [编码与协作规范](conventions.md) — 技术栈、编码规则
- [术语表](glossary.md) — 术语定义
