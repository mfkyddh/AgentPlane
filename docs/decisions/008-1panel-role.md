---
status: active
owner: AgentPlane maintainers
last_verified: 2026-05-09
date: 2026-05-09
---

# 008. 1Panel 定位为可替换的可视化仪表盘

## 背景

1Panel 在 AgentPlane 中用于服务器管理和可视化操作。需要明确其定位：是核心组件还是可替换的工具。

## 决策

1Panel 定位为**可替换的可视化仪表盘**，不是核心依赖：

- AgentPlane 的核心逻辑不依赖 1Panel 的 API
- 1Panel 通过 `scripts/onepanel/` 目录封装，与核心域隔离
- 远程 API 访问通过 SSH 端口转发（`RemoteAPIClient`），不暴露 1Panel 端口
- 当 1Panel 不满足需求时，可按相同接口替换为其他 provider

## 理由

- 单人维护项目，核心组件越少越好
- 1Panel 是第三方项目，版本演进不可控
- 通过隔离层保护核心逻辑不受 1Panel API 变更影响

## 替代方案

| 方案 | 为什么放弃 |
|------|-----------|
| 深度集成 1Panel API | 增加耦合度；1Panel API 变更直接影响核心逻辑 |
| 完全不用 1Panel | 丢失可视化能力；服务器管理效率降低 |
| 自建管理面板 | 开发和维护成本过高 |

## 影响

- `scripts/onepanel/` 是隔离层，核心域不直接引用 1Panel
- 远程 API 通过 SSH 端口转发访问，安全且可审计
- 未来替换 1Panel 只需修改 `scripts/onepanel/` 层

## 相关决策

- [006](006-ssh-pooling.md) — SSH 连接池化（RemoteAPIClient 复用池化连接）

## 关联文档

- [架构](../core/architecture.md) — 五域分层
