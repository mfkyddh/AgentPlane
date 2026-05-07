---
status: active
owner: AgentPlane maintainers
last_verified: 2026-05-07
audience: human
layer: strategy
---

# 决策记录：域模型与基础设施即应用

结论：定义 5 个业务能力域（infra、service、app、ingress、project），每个域对应项目模型的一层。基础设施服务作为 App 管理，没有特例。

---

## 状态

**接受**

## 日期

2026-05-07

## 背景

项目模型定义了三层实体：Project → App → Target。但域模型（AgentPlane 的职责划分）与项目模型的对应关系不清晰：

1. 原有 6 个域（infra、service、app、ingress、projection、onepanel）层次不协调
2. `projection` 是横切机制，不是业务域
3. `onepanel` 是 provider 实现细节，不是业务域
4. `service` 和 `app` 的边界模糊
5. Project 层没有对应域

## 决策

### 1. 定义 5 个业务能力域

**决策**：每个域对应项目模型的一层

| 域 | 管什么 | 管理阶段 | 对应项目模型 |
|---|---|---|---|
| `infra` | Target 配置（主机、网络、Secrets） | 配置层 | **Target** |
| `service` | 运行时管理（所有 Docker 容器的健康、重启、日志） | 运行层 | Target 上的**运行时** |
| `app` | 应用交付生命周期（catalog、构建、部署、回滚） | 交付层 | **App** |
| `ingress` | 公网入口（域名、SSL、路由） | 流量层 | App 的**对外访问** |
| `project` | 项目治理（分组、聚合状态、项目级配置） | 组织层 | **Project** |

**理由**：
- 每层项目模型都有对应的管理能力
- 职责清晰，不重叠
- 层次协调，在同一抽象层次

### 2. 基础设施也是应用

**决策**：PostgreSQL、Redis、MinIO 等基础设施服务，作为 App 管理在专门的基础设施项目中

```
Project: infrastructure          Project: mall-system
├── App: postgres                ├── App: order-service
├── App: redis                   ├── App: payment-gateway
├── App: minio                   └── App: user-service
└── App: nginx
```

**理由**：
- 没有特例：所有应用用同一套流程管理
- 代码复用：部署基础设施和部署业务应用用同一套逻辑
- 可版本化：基础设施可以像业务应用一样版本管理、回滚

### 3. 重新定义 service 域

**决策**：`service` 管理所有 Docker 容器的运行时，包括基础设施服务和业务应用

**理由**：
- PostgreSQL、Redis、nginx 和业务应用容器都是 Docker 容器
- 有共同的运行时操作（search、verify、restart、logs）
- 代码可以复用

### 4. 缩小 infra 域

**决策**：`infra` 只管 Target 配置（主机、网络、Secrets），不管具体服务

**理由**：
- 具体服务由 `service` 域管理
- 职责不重叠

## 替代方案

### 方案 A：4 个域（删除 service）

**描述**：将 service 拆分到 infra 和 app

**优点**：
- 域更少，更简单

**缺点**：
- Docker 运行时管理代码要写两遍
- 基础设施服务和业务应用的运行时管理被人为分开

### 方案 B：6 个域（保留 projection 和 onepanel）

**描述**：保持原有的 6 个域

**优点**：
- 与现有代码一致

**缺点**：
- 层次不协调（业务域 + 横切机制 + provider 细节混在一起）
- Project 层没有对应域

## 影响

### 对架构文档的影响

- 更新 architecture.md：定义 5 个域、域与项目模型对应关系
- 更新"应用层协作"章节：基础设施作为应用

### 对 CLI 设计的影响

```bash
# infra：管理 Target 配置
agentplane infra provision --target prod0-main

# service：管理运行时
agentplane service search --target prod0-main
agentplane service verify --target prod0-main --name nginx

# app：管理交付生命周期
agentplane app deploy --target prod0-main --app myapp

# project：管理项目
agentplane project status --project mall-system
```

### 对代码的影响

- 需要实现 `project` 域
- 需要重新定义 `service` 域的职责
- 需要缩小 `infra` 域的职责
- 基础设施服务迁移到专门的基础设施项目

## 相关决策

- [004-architecture.md](004-architecture.md) — 架构演进决策
- [001-positioning.md](001-positioning.md) — 项目定位

## 关联文档

- [架构](../core/architecture.md) — 域的详细说明
- [愿景](../core/vision.md) — 项目模型定义
