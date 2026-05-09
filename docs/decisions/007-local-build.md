---
status: active
owner: AgentPlane maintainers
last_verified: 2026-05-09
date: 2026-05-09
---

# 007. Docker 镜像保持本地构建 + 流式传输

## 背景

Docker 镜像从构建环境传输到部署目标的流程需要优化。原始流程是 `docker save` → `scp` → `docker load` 三步串行，每步独立 SSH 连接，且产生临时 `.tar` 文件。

## 决策

保持 Docker 镜像在本地构建（WSL 或 CI 环境），通过流式管道传输到远程：

```bash
docker save <image> | ssh <remote> docker load
```

不引入 Docker Registry，不使用远程构建。

## 理由

- 当前规模（1-2 台服务器）不需要 Docker Registry
- 流式传输避免临时 `.tar` 文件，节省磁盘 IO
- 管道方式减少 30%+ 传输耗时（省去写盘 + 读盘）
- 与 SSH 连接池复用，无额外握手开销

## 替代方案

| 方案 | 为什么放弃 |
|------|-----------|
| Docker Registry + 远程 pull | 违反"不引入 Docker Registry"约束；当前规模不需要 |
| 保持 scp 传输 | 磁盘 IO 开销大；三步串行耗时长 |
| 远程构建 (docker build on server) | 构建环境不一致风险；CI 环境优势丧失 |

## 影响

- `ship_image()` 从三步串行改为单步流式
- `deploy` 命令自动集成镜像传输，无需单独 `ship-image`
- 不产生临时 `.tar` 文件

## 相关决策

- [006](006-ssh-pooling.md) — SSH 连接池化（流式传输复用池化连接）

## 关联文档

- [架构](../core/architecture.md) — 部署流程
