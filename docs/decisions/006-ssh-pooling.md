---
status: active
owner: AgentPlane maintainers
last_verified: 2026-05-09
date: 2026-05-09
---

# 006. 远程执行采用 SSH ControlMaster 连接池化

## 背景

每次远程 API 调用或 SSH 命令执行都需要建立完整的 SSH 连接（~200ms 握手时间）。当管理 5-10 个应用时，部署流程中的多次 SSH 调用累积延迟显著。此外，每次连接独立建立导致资源浪费。

## 决策

引入 `SSHConnectionPool`，使用 SSH 原生的 `ControlMaster`/`ControlPersist` 机制实现连接复用：

- 首次连接时建立 ControlMaster，后续调用通过 ControlSocket 复用
- `ControlPersist=600s`（10 分钟空闲后自动关闭）
- 线程安全：`ensure_connection()` 使用 `threading.Lock` 保护

## 理由

- ControlMaster 是 SSH 原生功能，不引入新依赖
- 后续调用握手时间从 ~200ms 降到 ~0ms
- 与现有 WSL SSH 架构完全兼容
- 单人可理解和维护

## 替代方案

| 方案 | 为什么放弃 |
|------|-----------|
| 远程 Agent daemon + HTTP API | 违反"SSH 作为唯一远程通道"约束；引入运维负担 |
| 保持直连 SSH | 性能问题随应用数量增长线性恶化 |
| Paramiko 纯 Python SSH | 引入新依赖；失去 SSH 配置文件兼容性 |

## 影响

- 所有 SSH 调用自动获得连接复用，无需修改调用方代码
- `SshTarget` 新增可选 `connection_pool` 字段，向后兼容
- Windows 环境下通过 WSL SSH 中转，与现有架构一致

## 相关决策

- [009](009-execution-layers.md) — CommandSpec 统一数据类

## 关联文档

- [架构](../core/architecture.md) — 跨平台执行模型
