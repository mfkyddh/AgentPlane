---
status: active
owner: AgentPlane maintainers
last_verified: 2026-04-30
superseded_by: null
audience: both
layer: technical
---

# 📡 监控与告警指南

结论：AgentPlane 当前以 CLI 驱动的按需健康检查为主，尚未部署持续监控系统。本文定义监控目标、检查方法和未来告警集成路径，作为从"人工巡检"走向"自动监控"的过渡手册。

---

## 🎯 监控目标

| 目标 | 当前状态 | 优先级 |
| --- | --- | --- |
| 服务可用性 | 按需 CLI 验证 | 🔴 高 |
| 容器运行状态 | 按需 CLI 验证 | 🔴 高 |
| 健康探针响应 | 按需 CLI 验证 | 🔴 高 |
| 资源使用率 | 未覆盖 | 🟡 中 |
| 日志异常检测 | 未覆盖 | 🟡 中 |
| 证书过期预警 | 部分覆盖（cron renew） | 🟡 中 |
| 网络连通性 | 按需 CLI 验证 | 🟢 低 |

---

## 🛠️ 正式入口

所有监控检查通过 `agentplane ...` 执行，不绕过 CLI。

### 仓库级健康检查

```bash
agentplane repo health-check --repo-root .
```

**预期输出**：

```text
[PASS] 仓库结构检查
[PASS] docs-sanity 链接检查
[PASS] 入口漂移检查
```

### 目标环境清单与审计

```bash
# WSL 开发环境
agentplane infra inventory wsl --repo-root .
agentplane infra audit wsl --repo-root .

# 生产环境
agentplane infra inventory prod0-main --repo-root .
agentplane infra audit prod0-main --repo-root .
```

### 应用服务验证

```bash
# 容器级验证
agentplane app delivery verify --target wsl --app sub2api --repo-root . --execute

# 服务级验证
agentplane service verify --target wsl --name sub2api --repo-root .

# 公网入口验证
agentplane service public-endpoint verify --target prod0-main --name sub2api --cloudflare-env-file secrets/services/cloudflare.env
```

### 远端只读检查

```bash
# 容器状态
agentplane infra remote bash wsl --repo-root . -- docker ps -a

# 容器资源使用
agentplane infra remote bash wsl --repo-root . -- docker stats --no-stream

# 容器日志（最近 50 行）
agentplane infra remote bash wsl --repo-root . -- docker logs --tail 50 sub2api-prod
```

---

## ✅ 服务健康检查

### 健康探针端点

当前已注册的健康探针：

| 服务 | 目标 | 探针地址 | 验证方式 |
| --- | --- | --- | --- |
| sub2api | wsl | `http://127.0.0.1:18080/health` | `agentplane service verify` |
| sub2api | prod0-main (origin) | `http://127.0.0.1:18080/health` | `agentplane service verify` |
| sub2api | prod0-main (public) | `https://token.zzzai.cloud:8443/health` | `agentplane service public-endpoint verify` |

### 手动探针验证

```bash
# 本地回环探针
curl -sf http://127.0.0.1:18080/health && echo "OK" || echo "FAIL"

# 公网探针
curl -sf https://token.zzzai.cloud:8443/health && echo "OK" || echo "FAIL"

# 远端探针
agentplane infra remote bash prod0-main --repo-root . -- 'curl -sf http://127.0.0.1:18080/health'
```

**预期输出（正常时）**：

```json
{"status": "ok"}
```

### 探针失败排查

| 现象 | 可能原因 | 排查步骤 |
| --- | --- | --- |
| 连接拒绝 | 容器未启动或端口未映射 | `docker ps -a` 检查容器状态 |
| 超时 | 服务内部阻塞或资源耗尽 | `docker logs` 查看日志，`docker stats` 查看资源 |
| 5xx 响应 | 应用内部错误 | `docker logs` 查看 traceback |
| DNS 解析失败 | 域名配置错误 | 检查 Cloudflare DNS 记录 |

---

## 🐳 容器监控

### 容器状态检查

```bash
# 查看所有容器状态
agentplane infra remote bash wsl --repo-root . -- docker ps -a --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

# 查看特定容器详情
agentplane infra remote bash wsl --repo-root . -- docker inspect sub2api-prod --format '{{.State.Status}}'
```

**预期输出（正常时）**：

```text
NAMES             STATUS         PORTS
sub2api-prod      Up 2 hours     0.0.0.0:18080->8080/tcp
postgres18-prod   Up 2 hours     5432/tcp
redis7-prod       Up 2 hours     6379/tcp
```

### 容器资源监控

```bash
# 实时资源快照
agentplane infra remote bash wsl --repo-root . -- docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}\t{{.BlockIO}}"

# 容器重启次数（异常重启可能暗示问题）
agentplane infra remote bash wsl --repo-root . -- docker inspect sub2api-prod --format '{{.RestartCount}}'
```

**预期输出**：

```text
NAME              CPU %   MEM USAGE / LIMIT   NET I/O           BLOCK I/O
sub2api-prod      0.12%   128MiB / 512MiB     1.2MB / 800kB     10MB / 0B
postgres18-prod   0.05%   64MiB / 256MiB      500kB / 300kB     5MB / 0B
redis7-prod       0.01%   16MiB / 128MiB      100kB / 80kB      2MB / 0B
```

### 容器健康检查配置

在 `docker-compose.<target>.yml` 中为关键服务添加 Docker 原生健康检查：

```yaml
services:
  sub2api:
    image: sub2api:latest
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 15s
```

---

## 📋 日志监控

### 日志查看方法

```bash
# 最近 50 行日志
agentplane infra remote bash wsl --repo-root . -- docker logs --tail 50 sub2api-prod

# 带时间戳的日志
agentplane infra remote bash wsl --repo-root . -- docker logs --tail 50 --timestamps sub2api-prod

# 过滤错误日志
agentplane infra remote bash wsl --repo-root . -- docker logs --tail 200 sub2api-prod 2>&1 | grep -i 'error\|exception\|fatal'
```

### 关键日志模式

| 模式 | 含义 | 优先级 |
| --- | --- | --- |
| `ERROR` / `FATAL` | 应用级错误 | 🔴 立即处理 |
| `Exception` / `Traceback` | 未捕获异常 | 🔴 立即处理 |
| `Connection refused` | 依赖服务不可达 | 🟡 尽快排查 |
| `OOM` / `Out of memory` | 内存不足 | 🟡 尽快排查 |
| `WARN` | 非致命警告 | 🟢 定期巡检 |

### 日志持久化（推荐）

当前容器日志默认存储在 Docker 内部，容器删除后丢失。推荐配置日志驱动：

```yaml
services:
  sub2api:
    logging:
      driver: json-file
      options:
        max-size: "10m"
        max-file: "3"
```

---

## ⚠️ 告警规则配置

> 当前状态：AgentPlane 尚未集成 Prometheus/Grafana 等监控系统。以下规则作为未来实施的蓝图。

### 推荐告警规则

| 告警名称 | 条件 | 严重程度 | 处理方式 |
| --- | --- | --- | --- |
| 容器停止运行 | `docker ps` 显示容器 Exited | 🔴 Critical | 立即检查日志并重启 |
| 健康探针失败 | HTTP 探针返回非 200 或超时 | 🔴 Critical | 检查服务状态和日志 |
| 容器频繁重启 | 5 分钟内重启 > 3 次 | 🟡 Warning | 检查日志找根本原因 |
| CPU 使用率过高 | 容器 CPU > 80% 持续 5 分钟 | 🟡 Warning | 检查是否有异常进程 |
| 内存使用率过高 | 容器内存 > 85% | 🟡 Warning | 检查是否有内存泄漏 |
| 磁盘空间不足 | `/data` 分区使用率 > 90% | 🟡 Warning | 清理旧数据或扩容 |
| 证书即将过期 | 证书有效期 < 7 天 | 🟡 Warning | 手动触发证书续期 |

### 临时告警脚本

在正式监控系统就绪前，可用 cron + 脚本实现基础告警：

```bash
#!/bin/bash
# /opt/agentplane/scripts/health-check-alert.sh
# 放在 crontab 中每 5 分钟执行一次

set -euo pipefail

TARGET="prod0-main"
ALERT_FILE="/tmp/agentplane-alert-sent"

check_container() {
    local container="$1"
    local status
    status=$(docker inspect "$container" --format '{{.State.Status}}' 2>/dev/null || echo "missing")
    if [ "$status" != "running" ]; then
        echo "ALERT: Container $container is $status"
        # 这里接入告警通知渠道（邮件、Webhook 等）
        return 1
    fi
    return 0
}

check_health_probe() {
    local url="$1"
    if ! curl -sf --max-time 5 "$url" > /dev/null 2>&1; then
        echo "ALERT: Health probe failed for $url"
        return 1
    fi
    return 0
}

# 执行检查
check_container "sub2api-prod" || exit 1
check_container "postgres18-prod" || exit 1
check_container "redis7-prod" || exit 1
check_health_probe "http://127.0.0.1:18080/health" || exit 1

echo "All checks passed"
```

---

## 📬 告警通知渠道

### 推荐通知矩阵

| 严重程度 | 通知渠道 | 响应时间要求 |
| --- | --- | --- |
| 🔴 Critical | 电话/短信 + 即时通讯 | < 5 分钟 |
| 🟡 Warning | 即时通讯 + 邮件 | < 1 小时 |
| 🢢 Info | 邮件 / 日报 | 每日巡检 |

### 通知集成示例

#### 企业微信 / 钉钉 Webhook

```bash
# 发送告警到企业微信
send_wechat_alert() {
    local message="$1"
    local webhook_url="https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=YOUR_KEY"
    curl -s -X POST "$webhook_url" \
        -H 'Content-Type: application/json' \
        -d "{\"msgtype\": \"text\", \"text\": {\"content\": \"$message\"}}"
}
```

#### 邮件告警

```bash
# 使用 mailx 发送告警
send_email_alert() {
    local subject="$1"
    local body="$2"
    echo "$body" | mail -s "$subject" admin@example.com
}
```

---

## 📊 监控工具集成

> 以下为未来 Prometheus + Grafana 集成蓝图。当前阶段优先使用 CLI 按需检查。

### Prometheus 集成架构

```text
┌─────────────────────────────────────────────────────────────┐
│                        AgentPlane 监控架构                   │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────┐    ┌──────────────┐    ┌──────────────┐      │
│  │ 容器     │───▶│ cAdvisor     │───▶│ Prometheus   │      │
│  │ (Docker) │    │ (指标采集)    │    │ (指标存储)    │      │
│  └──────────┘    └──────────────┘    └──────┬───────┘      │
│                                              │              │
│  ┌──────────┐    ┌──────────────┐           │              │
│  │ 应用     │───▶│ /metrics     │───────────┘              │
│  │ (sub2api)│    │ (应用指标)    │                          │
│  └──────────┘    └──────────────┘                          │
│                                              │              │
│  ┌──────────┐    ┌──────────────┐           │              │
│  │ 系统     │───▶│ Node         │───────────┘              │
│  │ (宿主机) │    │ Exporter     │                          │
│  └──────────┘    └──────────────┘                          │
│                                              ▼              │
│                                     ┌──────────────┐       │
│                                     │   Grafana    │       │
│                                     │  (可视化)     │       │
│                                     └──────┬───────┘       │
│                                            │               │
│                                     ┌──────▼───────┐       │
│                                     │  Alertmanager│       │
│                                     │  (告警路由)   │       │
│                                     └──────────────┘       │
└─────────────────────────────────────────────────────────────┘
```

### Prometheus 配置示例

```yaml
# prometheus.yml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

rule_files:
  - "alert_rules.yml"

alerting:
  alertmanagers:
    - static_configs:
        - targets: ['alertmanager:9093']

scrape_configs:
  # cAdvisor - 容器指标
  - job_name: 'cadvisor'
    static_configs:
      - targets: ['cadvisor:8080']

  # Node Exporter - 系统指标
  - job_name: 'node'
    static_configs:
      - targets: ['node-exporter:9100']

  # 应用指标（如果 sub2api 暴露 /metrics）
  - job_name: 'sub2api'
    metrics_path: /metrics
    static_configs:
      - targets: ['sub2api:8080']
```

### Alertmanager 告警规则

```yaml
# alert_rules.yml
groups:
  - name: container_alerts
    rules:
      - alert: ContainerDown
        expr: absent(container_last_seen{name=~"sub2api-prod|postgres18-prod|redis7-prod"})
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "Container {{ $labels.name }} is down"

      - alert: ContainerRestarting
        expr: increase(container_restart_count{name=~".*-prod"}[5m]) > 3
        for: 2m
        labels:
          severity: warning
        annotations:
          summary: "Container {{ $labels.name }} restarting frequently"

      - alert: HighCPUUsage
        expr: rate(container_cpu_usage_seconds_total{name=~".*-prod"}[5m]) > 0.8
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Container {{ $labels.name }} CPU usage is high"

      - alert: HighMemoryUsage
        expr: container_memory_usage_bytes{name=~".*-prod"} / container_spec_memory_limit_bytes > 0.85
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Container {{ $labels.name }} memory usage is high"
```

### Grafana Dashboard 推荐面板

| 面板名称 | 数据源 | 用途 |
| --- | --- | --- |
| 容器概览 | cAdvisor | 所有容器状态、CPU、内存、网络 |
| 应用健康 | Prometheus | 健康探针响应时间、成功率 |
| 系统资源 | Node Exporter | 宿主机 CPU、内存、磁盘、网络 |
| 告警历史 | Alertmanager | 告警触发历史和处理状态 |

---

## ✅ 最小验证

每次巡检至少执行以下检查：

```bash
# 1. 仓库健康
agentplane repo health-check --repo-root .

# 2. 目标环境审计
agentplane infra audit wsl --repo-root .
agentplane infra audit prod0-main --repo-root .

# 3. 应用验证
agentplane app delivery verify --target prod0-main --app sub2api --repo-root . --execute

# 4. 公网入口验证
agentplane service public-endpoint verify --target prod0-main --name sub2api --cloudflare-env-file secrets/services/cloudflare.env
```

---

## 🔗 关联文档

| 文档 | 关系 |
| --- | --- |
| [当前状态与验证](./current-state-and-validation.md) | 本文的按需检查入口 |
| [容器与服务规范](../reference/container-conventions.md) | 容器命名、网络、持久化规范 |
| [发布与持续健康规范](../reference/release-process.md) | 健康周检和发布流程 |
| [App Delivery 失败处理](./app-delivery-failure-handling.md) | 部署失败时的排查和回滚 |
| [WSL Host Governance](./wsl-host-governance.md) | WSL 环境的治理和检查 |
| [prod0-main Governance](./prod0-main-governance.md) | 生产环境的治理和检查 |
| [排查失败部署](../tutorials/troubleshoot-failed-deployment.md) | 部署失败排查教程 |
