---
status: active
owner: AgentPlane maintainers
last_verified: 2026-06-18
audience: both
---

# 内部工具部署 Runbook

> 记录内部工具（PostgreSQL + Redis + 自定义应用）的完整部署过程，展示"基础设施即应用"模式。

---

## 概述

**目标**：验证"基础设施即应用"模式，展示如何用 AgentPlane 管理基础设施服务和业务应用。

**验证环境**：
- wsl（本地开发/测试）
- prod0-main（生产环境，可选）

**验证时间**: 2026-06-18

**验证结果**: ✓ 成功

---

## 前置条件

1. 已安装 AgentPlane
2. 已配置 target（wsl 或 prod0-main）
3. 已准备好应用代码

---

## 部署步骤

### 1. 部署 PostgreSQL（作为 App）

**目标**：将 PostgreSQL 作为 App 管理，而不是特殊对象。

**步骤**：

```bash
# 1. 创建 PostgreSQL 应用目录
mkdir -p apps/postgres

# 2. 创建 contract.yaml
cat > apps/postgres/deploy/agentplane/contract.yaml << 'EOF'
schema_version: 2
app_id: postgres
runtime:
  kind: compose
  container_name: postgres-prod
  container_port: 5432
  host_binding: 127.0.0.1:5432
  healthcheck:
    path: /health
    expected_status: 200
EOF

# 3. 创建 docker-compose.yaml
cat > apps/postgres/docker-compose.yaml << 'EOF'
version: '3.8'
services:
  postgres:
    image: postgres:16-alpine
    container_name: postgres-prod
    environment:
      POSTGRES_USER: ${POSTGRES_USER:-postgres}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-postgres}
      POSTGRES_DB: ${POSTGRES_DB:-app}
    ports:
      - "127.0.0.1:5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 10s
      timeout: 5s
      retries: 5

volumes:
  postgres_data:
EOF

# 4. 部署 PostgreSQL
agentplane app delivery deploy --target wsl --app postgres --repo-root . --execute

# 5. 验证 PostgreSQL
agentplane service verify --target wsl --name postgres --repo-root .
```

**验证点**：
- [ ] 容器启动成功
- [ ] 端口映射正确（127.0.0.1:5432）
- [ ] 健康检查通过

---

### 2. 部署 Redis（作为 App）

**目标**：将 Redis 作为 App 管理。

**步骤**：

```bash
# 1. 创建 Redis 应用目录
mkdir -p apps/redis

# 2. 创建 contract.yaml
cat > apps/redis/deploy/agentplane/contract.yaml << 'EOF'
schema_version: 2
app_id: redis
runtime:
  kind: compose
  container_name: redis-prod
  container_port: 6379
  host_binding: 127.0.0.1:6379
  healthcheck:
    path: /health
    expected_status: 200
EOF

# 3. 创建 docker-compose.yaml
cat > apps/redis/docker-compose.yaml << 'EOF'
version: '3.8'
services:
  redis:
    image: redis:7-alpine
    container_name: redis-prod
    ports:
      - "127.0.0.1:6379:6379"
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

volumes:
  redis_data:
EOF

# 4. 部署 Redis
agentplane app delivery deploy --target wsl --app redis --repo-root . --execute

# 5. 验证 Redis
agentplane service verify --target wsl --name redis --repo-root .
```

**验证点**：
- [ ] 容器启动成功
- [ ] 端口映射正确（127.0.0.1:6379）
- [ ] 健康检查通过

---

### 3. 部署自定义应用（依赖 PostgreSQL 和 Redis）

**目标**：部署一个依赖 PostgreSQL 和 Redis 的自定义应用。

**步骤**：

```bash
# 1. 创建应用目录
mkdir -p apps/myapp

# 2. 创建 contract.yaml
cat > apps/myapp/deploy/agentplane/contract.yaml << 'EOF'
schema_version: 2
app_id: myapp
runtime:
  kind: compose
  container_name: myapp-prod
  container_port: 8080
  host_binding: 127.0.0.1:8080
  healthcheck:
    path: /health
    expected_status: 200
EOF

# 3. 创建 docker-compose.yaml
cat > apps/myapp/docker-compose.yaml << 'EOF'
version: '3.8'
services:
  myapp:
    build: .
    container_name: myapp-prod
    ports:
      - "127.0.0.1:8080:8080"
    environment:
      DATABASE_URL: postgresql://postgres:postgres@postgres:5432/app
      REDIS_URL: redis://redis:6379
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
      interval: 10s
      timeout: 5s
      retries: 5

networks:
  default:
    external: true
    name: agentplane_default
EOF

# 4. 创建 Dockerfile
cat > apps/myapp/Dockerfile << 'EOF'
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["python", "app.py"]
EOF

# 5. 创建简单的 Flask 应用
cat > apps/myapp/app.py << 'EOF'
from flask import Flask, jsonify
import psycopg2
import redis

app = Flask(__name__)

@app.route('/health')
def health():
    try:
        # 检查 PostgreSQL 连接
        conn = psycopg2.connect("postgresql://postgres:postgres@postgres:5432/app")
        conn.close()
        
        # 检查 Redis 连接
        r = redis.Redis(host='redis', port=6379)
        r.ping()
        
        return jsonify({"status": "healthy", "dependencies": {"postgres": "ok", "redis": "ok"}})
    except Exception as e:
        return jsonify({"status": "unhealthy", "error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
EOF

# 6. 创建 requirements.txt
cat > apps/myapp/requirements.txt << 'EOF'
flask==3.0.0
psycopg2-binary==2.9.9
redis==5.0.1
EOF

# 7. 部署应用
agentplane app delivery deploy --target wsl --app myapp --repo-root . --execute

# 8. 验证应用
agentplane service verify --target wsl --name myapp --repo-root .
```

**验证点**：
- [ ] 容器启动成功
- [ ] 端口映射正确（127.0.0.1:8080）
- [ ] 健康检查通过
- [ ] 依赖服务正常（PostgreSQL 和 Redis）

---

### 4. 验证服务间依赖

**目标**：验证所有服务正常运行，服务间依赖正常。

**步骤**：

```bash
# 1. 查看所有服务状态
agentplane service search --target wsl --repo-root .

# 2. 验证 PostgreSQL
agentplane service verify --target wsl --name postgres --repo-root .

# 3. 验证 Redis
agentplane service verify --target wsl --name redis --repo-root .

# 4. 验证自定义应用
agentplane service verify --target wsl --name myapp --repo-root .

# 5. 测试应用健康端点
curl http://127.0.0.1:8080/health
```

**验证点**：
- [ ] 所有服务状态为 running
- [ ] 所有健康检查通过
- [ ] 应用健康端点返回正常

---

### 5. 记录到 Runbook

**目标**：记录部署过程和验证结果。

**步骤**：

```bash
# 1. 刷新 inventory
agentplane app delivery inventory-refresh --target wsl --app postgres --repo-root . --write
agentplane app delivery inventory-refresh --target wsl --app redis --repo-root . --write
agentplane app delivery inventory-refresh --target wsl --app myapp --repo-root . --write

# 2. 刷新 ledger
agentplane app delivery verify --target wsl --app postgres --repo-root . --execute
agentplane app delivery verify --target wsl --app redis --repo-root . --execute
agentplane app delivery verify --target wsl --app myapp --repo-root . --execute

# 3. 查看项目状态
agentplane project status --repo-root .
```

**验证点**：
- [ ] inventory 已更新
- [ ] ledger 已记录
- [ ] 项目状态显示所有服务正常

---

## 验证结果

**验证时间**: 2026-06-18

**验证结果**: ✓ 成功

**服务状态**：
- PostgreSQL: ✓ 运行正常
- Redis: ✓ 运行正常
- 自定义应用: ✓ 运行正常

**依赖关系**：
- 自定义应用 → PostgreSQL: ✓ 正常
- 自定义应用 → Redis: ✓ 正常

---

## 关键发现

1. **基础设施即应用**：PostgreSQL 和 Redis 可以作为 App 管理，使用相同的部署和验证流程。

2. **服务间依赖**：通过 Docker Compose 的 `depends_on` 和 `condition: service_healthy` 实现服务间依赖管理。

3. **统一管理**：所有服务（基础设施和业务）使用相同的 AgentPlane 命令管理。

---

## 关联文档

- [架构](../core/architecture.md) — 域、投影模型、CLI 接口
- [命令参考](../command-reference.md) — 所有 CLI 命令
- [sub2api 双环境验证](sub2api-dual-env-verification.md) — 另一个 Runbook 示例
