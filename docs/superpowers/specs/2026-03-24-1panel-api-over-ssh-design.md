# 1Panel API Over SSH Design

**Date:** 2026-03-24

## Goal

建立仓库标准做法：所有针对 `prod0-main` 的 1Panel API 调用，默认先通过 SSH 登录到目标主机，再在主机本机回环地址 `127.0.0.1:2096` 上发起签名请求；把 API Key 与相关参数写入本地仓库和生产机仓库的专用 env，并在验证成功后把 1Panel API 白名单收敛为仅 `127.0.0.1`。

## Current State

- 1Panel 面板已开启 API 接口。
- 用户已经提供可用 API Key。
- 当前仓库已有通用 1Panel API 技能，但默认文档仍以“直接访问面板地址”作为主要描述，没有把“SSH 到主机后本机回环调用”提升为本仓库优先策略。
- `prod0-main` 的 1Panel 当前可通过本机 `http://127.0.0.1:2096` 访问，也可经 `https://1panel.zzzai.cloud:8443/0f0e8602e3` 对外访问。

## Constraints

- 不引入 OpenClaw 运行时依赖；本次只处理 1Panel API 本身。
- 本地和生产机都需要保留同一口径的真实 env 文件，便于后续通过仓库资产复用。
- API 白名单最终只允许 `127.0.0.1`，因此后续默认调用方式必须是“SSH 上主机后由主机自己调用”。
- 本次必须通过 API 完成白名单收敛，而不是手工点击面板或直接改数据库。

## Options

### Option A: 继续从工作站直连 1Panel API

实现最少，但白名单需要持续暴露给工作站出口 IP，且当出口 IP、代理路径、Referer/Origin 条件变化时容易失效，不符合“更稳定高效”的目标。

### Option B: SSH to host, then call loopback API

把 `ONEPANEL_BASE_URL` 固定为 `http://127.0.0.1:2096`，配合 `ONEPANEL_SECURITY_ENTRANCE` 生成正确的 `Origin` / `Referer`，所有真实 API 调用都在 `prod0-main` 本机完成，再通过 SSH 带回结果。白名单可以收敛到 `127.0.0.1`，这是推荐方案。

### Option C: 额外再做一套专用 API 管理服务

长期可行，但当前仓库已经有可复用的 1Panel CLI/签名客户端，继续加一层服务超出这次目标。

## Approved Design

### Env Layout

- 新增模板：`templates/services/onepanel-api.env.example`
- 新增真实文件：`secrets/services/onepanel-api.env`
- 远端同步到：`/opt/env_ubuntu/secrets/services/onepanel-api.env`
- 文件包含：
  - `ONEPANEL_BASE_URL=https://1panel.zzzai.cloud:8443`
  - `ONEPANEL_CONNECT_BASE_URL=http://127.0.0.1:2096`
  - `ONEPANEL_API_KEY=<provided>`
  - `ONEPANEL_SECURITY_ENTRANCE=0f0e8602e3`
  - `ONEPANEL_TIMEOUT_MS=30000`
  - `ONEPANEL_SKIP_TLS_VERIFY=false`

### API Workflow

- 所有对 `prod0-main` 的 1Panel API 调用默认通过 SSH 执行。
- 在生产机上加载 `onepanel-api.env` 后，使用现有签名客户端或等效脚本发起 API 请求。
- 当 1Panel 启用了 `BindDomain` 时，逻辑 origin 仍使用绑定域名，真实连接地址改走 `ONEPANEL_CONNECT_BASE_URL=http://127.0.0.1:2096`。
- 先完成一次只读成功校验，再调用 API 更新 API 配置，将白名单收敛为仅 `127.0.0.1`。

### Skill Update

- 更新 `.codex/skills/openclaw-1panel/` 下的技能说明和中文 README。
- 明确本仓库优先实践：
  - 使用 `secrets/services/onepanel-api.env`
  - SSH 到目标主机后调用 `127.0.0.1:2096`
  - 不优先从工作站直连
  - 白名单收敛后更应坚持该模式

## Validation

- 本地仓库存在 `secrets/services/onepanel-api.env`
- 生产机仓库存在 `/opt/env_ubuntu/secrets/services/onepanel-api.env`
- 在 `prod0-main` 本机通过 env 发起至少一个只读 API 请求并返回成功
- 通过 API 更新后，再次读取 API 配置，确认白名单仅 `127.0.0.1`
- 记录白名单边界：这会收紧 1Panel 直连监听口，但不会自动阻断同机反代后的 API 访问
- 技能文档与模板可检索到新规则

## Non-Goals

- 不部署 OpenClaw
- 不修改 1Panel 面板登录方式
- 不改变 1Panel 现有公网反代路径
