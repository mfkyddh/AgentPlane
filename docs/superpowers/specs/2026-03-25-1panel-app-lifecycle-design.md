# 1Panel App Lifecycle Design

**Date:** 2026-03-25

## Goal

为本仓库建立一套统一的 1Panel 应用生命周期工具链，覆盖 `prod0-main` 与 WSL 测试环境，并把 `zqf_network` 作为所有项目内 Docker 容器和 1Panel 应用容器的强制网络基线。

## Current State

- 仓库已经有 `ops/scripts/onepanel/api_request.py`，可以通过签名 API 调用 1Panel。
- 仓库已经有通用 `openclaw-1panel` 技能，但它目前偏向通用读写，不负责本项目的网络强制策略。
- `prod0-main` 上 `newapi-prod` 已验证可以通过 `editCompose=true` 的安装请求，把 1Panel 应用商店模板中的 `1panel-network` 改为 `zqf_network`。
- 仓库根规则已经更新为：生产环境中所有项目管理的 Docker 容器与 1Panel 应用容器必须挂载 `zqf_network`。

## Constraints

- 后续所有 1Panel 应用安装默认由我通过仓库内技能和脚本执行，不再接受“直接在面板里按默认模板安装”。
- 第一版覆盖范围为 `prod0-main` 与 WSL 测试环境。
- 工具链必须同时支持脚本直调和技能封装，两者共享同一执行真源。
- 尽量复用现有 `api_request.py` 的签名与 env 约定，避免引入额外第三方依赖。
- `zqf_network` 是强制基线；如果某个应用确实需要额外网络，也只能在保留 `zqf_network` 的前提下附加。

## Options

### Option A: 继续依赖通用 1Panel 技能，按次手工编辑 Compose

实现成本最低，但规则分散在人和会话里，不可审计，也无法保证以后每次都落到 `zqf_network`。

### Option B: 只做脚本，不做技能

脚本可以成为强制真源，但无法把“以后都由我来安装”的仓库内操作习惯同步固化，用户也较难从技能目录发现正确入口。

### Option C: 脚本为执行真源，技能封装脚本

这是推荐方案。脚本承担所有真实生命周期动作与网络策略，技能只负责引导未来的 1Panel 操作都走这套脚本，规则集中且可复用。

## Approved Design

### Execution Model

- 新增统一 CLI：`ops/scripts/onepanel/app_lifecycle.py`
- 所有 install / reinstall / upgrade / uninstall / status / audit-network 动作都从这个入口进入。
- CLI 内部统一调用共享 1Panel 客户端和 Compose 策略模块。

### Module Layout

- `ops/scripts/onepanel/client.py`
  - 复用现有 env 口径，提供可复用的签名请求客户端。
- `ops/scripts/onepanel/env_targets.py`
  - 维护 `prod0-main` 与 WSL 测试环境的目标配置和默认 env 文件路径。
- `ops/scripts/onepanel/compose_policy.py`
  - 专门负责把应用商店返回的 Compose 模板规范化到 `zqf_network`。
  - 规则：最终部署 Compose 必须包含 `zqf_network`，且不得只剩 `1panel-network`。
- `ops/scripts/onepanel/app_lifecycle.py`
  - 对外 CLI。
  - 支持应用商店读取、安装、重装、升级、卸载、状态检查、网络审计。

### Compose Policy

- 安装与升级前，总是先读取 1Panel 应用详情里的 `dockerCompose`。
- 若请求方没有显式传入编辑后的 Compose，则默认由策略模块自动生成规范化版本。
- 规范化结果至少满足：
  - 顶层 `networks` 包含 `zqf_network: external: true`
  - 各服务 `networks` 至少包含 `zqf_network`
  - 若上游模板只写了 `1panel-network`，则替换为 `zqf_network`
  - 若上游模板本来还有额外专用网络，则保留这些额外网络，但不得移除 `zqf_network`

### Lifecycle Coverage

- `catalog get`
  - 读取应用商店条目与版本详情
- `install`
  - 读取模板，应用网络策略，提交 `editCompose=true` 安装
- `reinstall`
  - 读取已安装实例信息，必要时备份应用目录，卸载后按同参数重装
- `upgrade`
  - 读取目标版本模板，应用网络策略后升级
- `uninstall`
  - 通过 1Panel API 卸载，并支持显式的删除镜像/备份选项
- `status`
  - 读取 1Panel 安装态、容器状态、容器网络、可选健康检查
- `audit-network`
  - 检查目标环境中由 1Panel 管理的应用容器是否都挂载 `zqf_network`

### Skill Contract

- 新增项目技能：`.codex/skills/onepanel-app-lifecycle/SKILL.md`
- 触发场景：
  - 用户要求安装、升级、重装、卸载、检查 1Panel 应用
  - 用户要求从 1Panel 应用商店读取模板
  - 用户要求审计 1Panel 应用的 Docker 网络
- 技能要求未来代理默认调用 `app_lifecycle.py`，而不是裸调安装接口。

### Documentation

- 新增运行手册：`docs/runbooks/onepanel-app-lifecycle.md`
- 记录：
  - 支持的命令
  - `prod0-main` 与 WSL 的目标参数
  - `zqf_network` 强制规则
  - 常见失败场景与恢复方式

## Validation

- 单元测试覆盖 Compose 策略最小行为：
  - `1panel-network` 被改写为 `zqf_network`
  - 已包含 `zqf_network` 的 Compose 不被破坏
  - 额外网络不会丢失
- CLI 能在本地输出帮助并通过最小参数校验。
- `prod0-main` 上至少能完成一次读取应用详情与网络审计。
- WSL 环境至少能完成目标配置解析与 Compose 规范化的离线验证。

## Non-Goals

- 不修改 1Panel 上游源码或官方应用商店远端模板。
- 不把所有历史 1Panel 应用一次性批量重建。
- 不替代 1Panel 网站、OpenResty、证书等现有专用技能。
