# 1Panel OpenResty Container Naming Design

**Date:** 2026-03-24

## Goal

把 `prod0-main` 上由 1Panel 管理的 OpenResty 容器从历史名称 `1Panel-openresty-engw` 规范化为生产环境标准名 `1panel-openresty-prod`，并把同一规则纳入仓库规范，约定未来 WSL 测试环境对应名称为 `1panel-openresty-dev`。

## Current State

- 仓库根规则已经要求仓库管理的 Docker 容器在生产环境统一以 `-prod` 结尾，WSL 测试环境统一以 `-dev` 结尾。
- `prod0-main` 当前唯一明显偏离该规则的生产容器是 1Panel 官方 OpenResty，现名为 `1Panel-openresty-engw`。
- 该容器不是手工启动，而是由 1Panel 应用目录 `/data/1panel/apps/openresty/openresty/` 下的 Compose 资产管理。
- `docker-compose.yml` 通过 `container_name: ${CONTAINER_NAME}` 读取 `.env` 中的 `CONTAINER_NAME`，因此只执行 `docker rename` 不能持久化这次变更。

## Constraints

- 必须修改 1Panel OpenResty 应用源配置，而不是只修改运行态容器名。
- 改名过程中不能破坏当前 `token.zzzai.cloud:2053` 和 `pay.zzzai.cloud:2053/pay` 的服务可用性。
- 仓库中的规范文档、inventory 和现状说明必须同步更新，避免后续运维继续引用旧名。
- 仅规范容器名，不调整镜像名、网站名、域名、端口、数据目录或网络模式。

## Options

### Option A: Direct `docker rename`

优点是操作快，停机窗口最短。缺点是下一次 1Panel 或 Compose 重建时会回滚到旧名，不满足“纳入项目规范”的目标。

### Option B: Update 1Panel app `.env` and recreate

修改 `/data/1panel/apps/openresty/openresty/.env` 中的 `CONTAINER_NAME`，然后使用该应用自身的 Compose 配置重建容器。这样运行态与管理态一致，后续 1Panel 重启或重建仍会保持新名称。这是推荐方案。

### Option C: Rename via 1Panel UI or API

理论上更接近面板操作路径，但当前已确认容器名源头就在本机应用目录的 `.env` 文件，额外走 UI 或 API 会增加复杂度而不提升可靠性。

## Approved Design

### Remote Change

- 在 `prod0-main` 把 1Panel OpenResty 应用的 `CONTAINER_NAME` 从 `1Panel-openresty-engw` 修改为 `1panel-openresty-prod`。
- 使用 `/data/1panel/apps/openresty/openresty/docker-compose.yml` 和 `.env` 进行受控重建。
- 重建后验证：
  - `docker ps` 中容器名已变为 `1panel-openresty-prod`
  - 主机回环与公网对 `token` / `pay` 的 HTTPS 检查继续返回成功

### Repository Alignment

- 在仓库规则中补充 1Panel 官方 OpenResty 的标准命名约定：
  - production: `1panel-openresty-prod`
  - WSL/dev: `1panel-openresty-dev`
- 更新 `inventory/servers/prod0-main/README.md`
- 更新 `inventory/servers/prod0-main/inventory.json`

## Validation

- 远端：
  - `docker ps --format '{{.Names}}'`
  - `docker inspect <new-name>`
  - `curl -k --resolve ... https://token.zzzai.cloud:2053/`
  - `curl -k --resolve ... https://pay.zzzai.cloud:2053/pay`
- 本地仓库：
  - `rg '1Panel-openresty-engw|1panel-openresty-prod|1panel-openresty-dev'`
  - `git diff --stat`

## Non-Goals

- 不迁移 OpenResty 的 2053 流量入口。
- 不调整 1Panel 站点配置、证书、上游反代或主机防火墙。
- 不把 1Panel 本体的 systemd 服务或应用安装方式改成仓库托管 Compose。
