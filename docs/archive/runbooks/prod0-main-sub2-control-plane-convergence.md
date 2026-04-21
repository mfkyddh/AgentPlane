# [ARCHIVED] prod0-main Sub2 Control-Plane Convergence History

> 历史窗口快照。该文档只保留 `2026-03-25` 收口窗口及 `2026-03-30` 后续补记，不是当前正式入口。
> 当前决策请回到 `inventory/servers/prod0-main/`、active runbook，以及 `uv run python -m agentplane.cli ...` 的现行控制面口径。

## 历史目标（2026-03-25 视角）

在不破坏现有 `pay.zzzai.cloud:8443/pay` 与 `token.zzzai.cloud:8443` 的前提下，把 `sub2api` 与 `sub2apipay` 的运行控制面进一步收口，减少 `systemd + 手工 compose + 网站对象` 并存的状态。

> 这份 runbook 保留为 `2026-03-25` 收口窗口的历史记录，不再代表当前正式真源。当前正式口径以 `inventory/servers/prod0-main/inventory.json`、`inventory/servers/prod0-main/README.md` 与最新应用交付 runbook 为准。
> 追加结果：`sub2apipay` 已于 `2026-03-30` 切换到 OP_Linux `compose`，旧 `sub2apipay-prod.service` 仅保留为 disabled rollback entry。

## 2026-03-25 现状

- `sub2api`
  - 运行模型：宿主机二进制 + `systemd`
  - 当时正式入口：1Panel 网站对象 `token`
  - 目录已收口：`/data/sub2api/{app,config,data}`
  - 兼容路径：`/opt/sub2api`、`/var/lib/sub2api`、`/etc/sub2api/sub2api-prod.env`
- `sub2apipay`
  - 运行模型：容器化运行，计划从 `systemd` 兼容层进一步收口到统一控制面
  - 当时正式入口：1Panel 网站对象 `pay`
  - 目录已收口：`/data/sub2apipay/{app,config}`
  - 兼容路径：`/opt/sub2apipay`、`/etc/sub2apipay/sub2apipay-prod.env`
  - 当时评估的 1Panel 项目目录：`/data/1panel/docker/compose/sub2apipay-prod`

## 当时建议顺序（历史）

1. 继续巩固 `sub2apipay` 的 1Panel Compose 项目口径
2. 再决定 `sub2api` 是否容器化

原因：

- `sub2apipay` 已经是容器形态，只差把生命周期从 `systemd` 切到 1Panel 编排。
- 按 `2026-03-25` 当时现场，`sub2api` 仍是宿主机二进制形态，若直接迁移为 1Panel 容器，相当于切换运行模型，风险明显更高。

## sub2apipay 历史记录中的已完成动作

- 目录与配置已收口到 `/data/sub2apipay/...`
- 仓库脚本已增加：
  `ops/scripts/onepanel/project_lifecycle.py`
- 已通过 1Panel `containers/compose` 接口创建项目目录：
  `/data/1panel/docker/compose/sub2apipay-prod`
- 当时计划中拟移除 `sub2apipay-prod.service`；实际现场直到 `2026-03-30` 迁移窗口前仍保留该 service 作为兼容入口
- 公网入口 `https://pay.zzzai.cloud:8443/pay` 切换后保持 `HTTP/2 200`
- 按 `2026-03-30` 迁移窗口后的历史记录，容器标签已刷新到：
  - `com.docker.compose.project.config_files=/data/1panel/docker/compose/sub2apipay-prod/docker-compose.yml`
  - `com.docker.compose.project.working_dir=/data/1panel/docker/compose/sub2apipay-prod`

## sub2apipay 当时规划的下一窗口方案

> 以下内容描述的是当时为下一迁移窗口准备的方案与回滚思路，保留为历史现场，不作为当前执行入口。

### 当时目标态（历史计划稿）

- 继续使用现有镜像 tag
- 继续绑定 `127.0.0.1:18091:3000`
- 继续接入 `zqf_network`
- 继续由 1Panel 网站对象 `pay` 对外暴露
- 生命周期控制从 `sub2apipay-prod.service` 切到 1Panel 编排对象

### 历史前置条件（计划时）

- `inventory/servers/prod0-main/inventory.json` 已反映 `/data/sub2apipay/...`
- `/data/sub2apipay/config/sub2apipay-prod.env`
- `/data/sub2apipay/config/.env.runtime`
- `/data/sub2apipay/app/current/docker-compose.prod.yml`
- 预先导出当前容器配置与镜像信息

### 历史切换步骤（计划稿）

> 下列命令与步骤仅用于保留当时计划中的操作快照，便于回看收口窗口的历史判断；它们不代表当前 CLI-first 正式入口，也不应替代最新 runbook 或 inventory 口径。

1. 用仓库脚本读取当前 compose 与 env，生成 1Panel Compose 草稿：

```bash
cd <legacy-op-linux-root>
python3 ops/scripts/onepanel/project_lifecycle.py \
  --env prod0-main \
  test-sub2apipay \
  --repo-root <legacy-op-linux-root>
```

2. 用仓库脚本同步/更新 1Panel 项目：

```bash
cd <legacy-op-linux-root>
python3 ops/scripts/onepanel/project_lifecycle.py \
  --env prod0-main \
  sync-sub2apipay \
  --repo-root <legacy-op-linux-root> \
  --disable-systemd
```

3. 确认编排内容：
   - `127.0.0.1:18091:3000`
   - `zqf_network`
   - env 文件只引用 `/data/sub2apipay/config/...`
4. 验证：
   - `docker ps`
   - `curl -skI https://pay.zzzai.cloud:8443/pay`
   - 回源 `http://127.0.0.1:18091`
5. 如仍保留 legacy unit，验证稳定后删除 unit 文件并 `daemon-reload`。

### 历史回滚步骤（计划稿）

- 停掉 1Panel 新编排
- `systemctl start sub2apipay-prod.service`
- 重新验证 `pay.zzzai.cloud`

## sub2api 当时规划的下一窗口方案

> 以下内容描述的是当时讨论的保守/激进路径，保留为历史现场，不作为当前执行入口。

### 历史讨论稿：保守方案

- 继续保留宿主机二进制 + `systemd`
- 维持 1Panel 只管理网站对象和证书
- 目录与配置已收口到 `/data/sub2api/...`，先不切运行模型

### 历史讨论稿：激进方案

- 基于独立 compose 把 `sub2api` 容器化
- 继续使用 `127.0.0.1:18080`
- 接入 `zqf_network`
- 对接现有 `postgres18-prod` 与 `redis7-prod`

### 历史讨论稿：当时不建议直接执行的原因

- 按 `2026-03-25` 当时生产现场，`sub2api` 仍是二进制发布包模型，不是容器模型
- 切换会同时影响：
  - 进程管理方式
  - 发布方式
  - 数据目录引用
  - 回滚路径

## 历史验收口径

- 网站对象仍由 1Panel 承接
- `/data/sub2api`、`/data/sub2apipay` 仍为唯一正式数据与配置根
- 不新增新的 `/opt`、`/etc`、`/var/lib` 实体目录散落
- 切换后公网入口继续返回成功
