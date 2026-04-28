# 1Panel v2.1.5 项目文档

本文保存 `2026-03-25` 时点围绕 `prod0-main` 与上游 `1Panel v2.1.5` 的对齐关系快照。它只用于历史追溯、排查与二开比对，不代表当前 active architecture baseline。

## 目标与结论

- 文档编写时间：`2026-03-25`
- 线上生产环境：`prod0-main`
- 线上实测版本：`v2.1.5`
- 线上实测模式：`stable`
- 线上安装基目录：`/data`
- 线上面板监听：`*:2096`
- 本地源码路径：`/root/github/1Panel`
- 本地源码状态：`tag v2.1.5`、提交 `142c9b9a712b975178e57582828459b1c53569db`
- 克隆深度：shallow repository，当前历史深度为 `1`

这份文档的用途不是重复上游 README，而是把“当前生产机正在跑的 1Panel 版本”和“本地对齐的上游源码”做一一对应，便于后续排查、二次开发和运维变更时快速定位代码。

## 版本对齐记录

生产机通过 SSH 实测：

```bash
printf '%s\n' \
  'set -euo pipefail' \
  '1panel version' \
| agentplane remote bash prod0-main
```

返回：

```text
version: v2.1.5
mode: stable
```

随后按相同 tag 做最浅克隆：

```bash
git clone --depth 1 --branch v2.1.5 https://github.com/1Panel-dev/1Panel.git /root/github/1Panel
```

当前本地仓库核验：

```bash
git -C /root/github/1Panel describe --tags --exact-match
git -C /root/github/1Panel rev-parse HEAD
git -C /root/github/1Panel rev-parse --is-shallow-repository
git -C /root/github/1Panel rev-list --count HEAD
```

期望结果：

- tag 为 `v2.1.5`
- HEAD 为 `142c9b9a712b975178e57582828459b1c53569db`
- shallow repository 为 `true`
- 提交数为 `1`

如果后续生产机版本变化，优先重新实测生产版本，再按新 tag 更新本地源码，不要直接跟踪 `main`。

## 上游仓库顶层结构

`/root/github/1Panel` 当前顶层关键目录如下：

- `frontend/`：Vue 3 + Vite 前端控制台源码。
- `core/`：面板主服务，负责登录、设置、任务、升级、API、会话、数据库和静态资源分发。
- `agent/`：宿主机执行代理，负责应用市场、Docker、网站、数据库、备份、证书、运行时和主机侧操作。
- `docs/`：上游多语言文档。
- `ci/`：CI 相关脚本和配置。

对当前版本最关键的入口文件：

- `core/cmd/server/main.go`：`1panel-core` 入口。
- `core/cmd/server/cmd/root.go`：CLI 根命令，默认启动 core 服务。
- `core/server/server.go`：core 初始化顺序、HTTP/TLS/mux 监听逻辑。
- `core/init/viper/viper.go`：core 配置加载逻辑，决定是读 `/opt/1panel/conf/app.yaml` 还是读 `1pctl` 注入参数。
- `agent/cmd/server/main.go`：`1panel-agent` 入口。
- `agent/server/server.go`：agent 启动逻辑，区分 master 节点的 unix socket 模式和非 master 节点的 mTLS 模式。
- `agent/init/viper/viper.go`：agent 配置加载逻辑。
- `agent/init/dir/dir.go`：agent 启动时创建的标准目录结构。
- `core/cmd/server/web/web.go`：前端构建产物嵌入 `1panel-core` 的入口。
- `Makefile`：前端构建、core/agent 编译入口。

## 架构与运行方式

### 1. 前端

- 技术栈：`Vue 3`、`TypeScript`、`Vite`、`Pinia`、`Vue Router`、`Element Plus`
- 代码位置：`frontend/`
- 构建命令定义在 `frontend/package.json`
- `Makefile` 的 `build_frontend` 会先构建前端，再由 core 通过 `embed` 打包静态资源

这意味着线上 `1Panel` 面板不是单独的 Node 服务，而是前端静态资源被编译后嵌入到 `1panel-core` 二进制中，由 core 统一对外提供。

### 2. Core

`core/server/server.go` 的启动顺序是：

1. 初始化正则、配置、日志、数据库、迁移、国际化、校验器
2. 初始化 Geo、cron、session、hook
3. 初始化其他运行依赖
4. 注册 HTTP 路由
5. 根据配置以 `http`、`https` 或 `http/https mux` 模式监听

core 负责的主要内容：

- 面板登录与认证
- API 路由与 Swagger
- 设置、升级、恢复、用户信息、MFA、入口地址等控制面逻辑
- `core.db`、`task.db`、`agent.db`、`alert.db`、`session.db` 等数据库接入
- 前端静态资源与欢迎页分发

### 3. Agent

`agent/server/server.go` 明确区分两类模式：

- master 节点：监听 unix socket `/etc/1panel/agent.sock`
- 非 master 节点：监听 `0.0.0.0:<port>`，并启用双向 TLS 认证

从当前生产机日志现象看，`prod0-main` 作为主节点运行的是 master 口径，这也解释了日志里请求来源地址为空。

agent 负责的主要内容：

- 应用市场安装与升级
- Docker / Compose 编排
- 网站、OpenResty、证书、反代
- 数据库运行时管理
- 备份、恢复、文件与宿主机工具操作
- 运行目录初始化与资源下发

## 配置加载与 `/data/1panel` 的关系

源码里有一个容易误判的点：上游代码默认把 `/opt/1panel/conf/app.yaml` 作为 dev 模式配置入口，但 stable 安装并不依赖这个路径作为唯一真实来源。

`core/init/viper/viper.go` 在非 dev 路径下会从 `/usr/local/bin/1pctl` 读取这些参数：

- `BASE_DIR`
- `ORIGINAL_PORT`
- `ORIGINAL_VERSION`
- `ORIGINAL_USERNAME`
- `ORIGINAL_PASSWORD`
- `ORIGINAL_ENTRANCE`
- `LANGUAGE`
- `PANEL_EDITION`

当前生产机实测：

```text
BASE_DIR=/data
ORIGINAL_PORT=2096
ORIGINAL_VERSION=v2.1.5
ORIGINAL_ENTRANCE=<onepanel-safe-entrance>
LANGUAGE=zh
PANEL_EDITION=cn
```

所以线上安装在 `/data/1panel` 不是偏离上游设计，而是通过 `1pctl` 的参数注入，把上游默认安装基目录从 `/opt` 切换到了 `/data`。

## 当前生产机目录映射

结合源码 `agent/init/dir/dir.go` 与生产机实测，当前 `prod0-main` 的 1Panel 目录职责如下：

- `/data/1panel/db`：核心数据库、任务数据库、agent 数据库等
- `/data/1panel/log`：面板日志
- `/data/1panel/log/task`：任务日志
- `/data/1panel/tmp`：临时文件、升级与脚本目录
- `/data/1panel/apps`：应用安装目录
- `/data/1panel/resource/apps`：应用市场资源与模板
- `/data/1panel/runtime`：运行时相关内容
- `/data/1panel/www`：网站相关配置与站点目录
- `/data/1panel/www/conf.d`：OpenResty/Nginx 虚拟主机配置
- `/data/1panel/www/sites`：站点目录
- `/data/1panel/www/certs`：当前生产机证书主目录
- `/data/1panel/docker/compose`：Compose 生成目录
- `/data/1panel/mcp`：MCP 相关目录
- `/data/1panel/firewall`：防火墙相关目录
- `/data/1panel/ai/tensorrt_llm`：AI 模块数据目录

当前生产机实际存在的部分目录：

- `/data/1panel/apps/openresty`
- `/data/1panel/apps/new-api`
- `/data/1panel/www/certs`
- `/data/1panel/www/conf.d`
- `/data/1panel/www/sites`

这与我们近期在 `prod0-main` 上对 OpenResty、证书和 8443 切换的实际操作是一致的。

## 构建与发布要点

上游 `Makefile` 当前定义：

- `build_frontend`：在 `frontend/` 下安装依赖并执行生产构建
- `build_core_on_linux`：编译 `1panel-core`
- `build_agent_on_linux`：编译 `1panel-agent`
- `build_all`：前端 + core + agent 全量构建

发布形态是：

- 前端静态资源先构建
- 产物打进 `core/cmd/server/web/` 的嵌入资源
- 最终运行核心是两个 Go 二进制：`1panel-core` 和 `1panel-agent`

当前生产机 systemd 服务实测为：

- `1panel-core.service`
- `1panel-agent.service`

没有名为 `1panel.service` 的聚合 unit。

## 对当前生产环境最相关的源码理解

结合仓库现状，后续最常需要读的不是整个 1Panel，而是下面几个区域：

- `core/app/api/v2/`：面板 API 的入口层
- `core/app/service/`：设置、升级、脚本、认证等控制面逻辑
- `agent/app/service/`：网站、容器、数据库、证书、应用安装等宿主机操作逻辑
- `agent/cmd/server/nginx_conf/`：OpenResty/Nginx 模板
- `agent/init/dir/dir.go`：标准目录生成规则

对我们现在这台生产机，最直接相关的是：

- 1Panel API over SSH
- OpenResty 应用目录与容器命名
- `www/certs` 证书主目录
- `www/conf.d` / `www/sites` 的站点配置

## 后续更新源码的标准动作

当生产机版本变化时，建议按这个顺序更新：

1. 先实测生产机版本  
   `printf '%s\n' 'set -euo pipefail' '1panel version' | agentplane remote bash prod0-main`
2. 看本地 `/root/github/1Panel` 是否已是相同 tag
3. 如果不一致，直接按目标 tag 重新做浅克隆，或在现有仓库上只抓对应 tag

示例：

```bash
rm -rf /root/github/1Panel
git clone --depth 1 --branch <target-tag> https://github.com/1Panel-dev/1Panel.git /root/github/1Panel
```

如果不想删目录，也可以：

```bash
git -C /root/github/1Panel fetch --depth 1 origin tag <target-tag>
git -C /root/github/1Panel checkout --detach FETCH_HEAD
```

原则只有一个：本地只保留与线上一致的 tag 快照，不默认追踪上游最新主分支。
