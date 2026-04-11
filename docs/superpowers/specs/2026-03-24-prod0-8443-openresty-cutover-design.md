# Prod0 8443 OpenResty Cutover Design

**Date:** 2026-03-24

## Goal

为 `prod0-main` 设计一套新的实施方案：先把 `1panel-openresty-prod` 现在和未来使用的所有站点证书统一收口到宿主机目录 `/data/1panel/www/certs/`，由 `1Panel` 自己通过 `Cloudflare DNS-01` 负责签发与自动续签；在证书主目录和续签链路稳定后，再把公网 `8443` 入口从 `nginx-ui-prod` 平滑切换到 `1panel-openresty-prod`。

## Current State

- `prod0-main` 当前的 `8443` 监听者是 `nginx-ui-prod`，容器使用 `host` 网络，宿主机 `0.0.0.0:8443` 与 `[::]:8443` 均由该容器内的 `nginx` 进程占用。
- `1panel-openresty-prod` 同样使用 `host` 网络，容器的 `/www` 实际挂载宿主机 `/data/1panel/www`，当前已在 `2053` 上承载 `token.zzzai.cloud` 与 `pay.zzzai.cloud`。
- 现有证书来源是分裂的：
  - `nginx-ui-prod` 当前使用 `/data/apps/nginx-ui-official/nginx/certs/` 下的证书材料
  - `1panel-openresty-prod` 现网站点证书目前仍沿用 1Panel/OpenResty 自己的站点目录口径
- 当前还没有一个统一的宿主机证书主目录，也没有把“现有与未来所有 OpenResty 站点证书”统一纳入同一套 1Panel 自动续签链路。
- `8443` 当前至少承载以下四个入口：
  - `1panel.zzzai.cloud`
  - `nginx.zzzai.cloud`
  - `token.zzzai.cloud`
  - `pay.zzzai.cloud`
- `1panel.zzzai.cloud:8443` 当前由 `nginx-ui-prod` 反代到 `127.0.0.1:2096`。
- `nginx.zzzai.cloud:8443` 当前由 `nginx-ui-prod` 反代到 `127.0.0.1:19000`，用户已确认本次切换后该公网入口可以先下线。
- `token.zzzai.cloud:8443` 与 `pay.zzzai.cloud:8443/pay` 当前也都由 `nginx-ui-prod` 承载；与之并行的 `2053` 入口已经在 `1panel-openresty-prod` 上运行。

## Constraints

- 必须同时迁移 `1panel.zzzai.cloud:8443`，不能只迁 `token` / `pay`。
- `nginx.zzzai.cloud:8443` 在切换后可以下线，但用户希望暂时保留 `nginx-ui-prod` 容器几天，以便回退。
- 用户已经明确要求：
  - `1panel-openresty-prod` 现在和以后用到的所有站点证书，都统一由宿主机目录 `/data/1panel/www/certs/` 管理
  - 证书签发与自动续签一并切到 `1Panel/OpenResty` 自己管理
  - 自动续签链路继续使用 `Cloudflare DNS-01`
- 两个入口容器都使用 `host` 网络，因此 `8443` 不能由两个进程同时抢占；切换动作本质上是宿主机监听权交接。
- 本次要把“证书治理”和“入口迁移”拆成两个阶段：先收口证书与续签，再推进 `2443` 预演和正式 `8443` 切换。
- 本次不引入每日巡检，只要求切换完成后立即密集验活，并在 `24-72` 小时内做一次复检。

## Options

### Option A: Keep current certificate sources, only switch ingress

优点是路径最短。缺点是继续保留“nginx-ui 证书目录”和“OpenResty 站点证书目录”双轨口径，与用户新要求直接冲突，也会让后续新增站点继续积累历史包袱。

### Option B: First unify certificates under `/data/1panel/www/certs/`, then switch ingress

先把 `1panel-openresty-prod` 现在与未来所有站点证书统一收口到宿主机目录 `/data/1panel/www/certs/`，由 `1Panel` 通过 `Cloudflare DNS-01` 负责签发和自动续签；等 `2053` 现网站点也稳定吃新目录后，再做 `2443` 预演和正式 `8443` 切换。这是推荐方案，因为证书主目录、续签链路和流量入口三者的职责边界最清晰，也最符合“以后都统一管理”的目标。

### Option C: Keep host cert directory, but retain nginx-ui renewal as the producer

可以把证书复制到 `/data/1panel/www/certs/`，但仍沿用旧的 `nginx-ui` 续期脚本和同步逻辑。短期能跑，但长期会变成“OpenResty 用一套目录，续期却靠另一套系统”，不满足“由 1Panel/OpenResty 自己管理”的要求。

## Approved Design

### High-Level Approach

采用 Option B，拆成两个阶段：

- 第一阶段：证书治理
  - 建立宿主机统一证书主目录 `/data/1panel/www/certs/`
  - 把 `1panel-openresty-prod` 现在和未来所有站点证书都切到这个主目录
  - 让 `1Panel` 通过 `Cloudflare DNS-01` 负责签发与自动续签
  - 先在 `2053` 现网站点上验证新证书目录与新续签链路
- 第二阶段：入口迁移
  - 在 `1panel-openresty-prod` 建立四个 `2443` 验证入口
  - 只在所有 `2443` 验证通过后，才进入正式 `8443` 切换窗口
  - 正式窗口只做：备份、停旧监听、启新监听、立即验活

### Certificate Architecture

- 统一证书根目录：`/data/1panel/www/certs/`
- 每张证书一个独立子目录，OpenResty 站点只引用这里，不再各站点自己维护一份 `ssl/` 副本。
- 推荐结构：
  - `/data/1panel/www/certs/zzzai-cloud/fullchain.pem`
  - `/data/1panel/www/certs/zzzai-cloud/privkey.pem`
  - `/data/1panel/www/certs/1panel-zzzai-cloud/fullchain.pem`
  - `/data/1panel/www/certs/1panel-zzzai-cloud/privkey.pem`
- 以后新增站点也按同一口径接入，不再从 `nginx-ui` 证书目录或容器内现状文件反推来源。

### Certificate Issuance And Renewal

- 统一由 `1Panel` 调用 `Cloudflare DNS-01` 签发与自动续签。
- 续签成功后的产物固定写入 `/data/1panel/www/certs/<cert-id>/`。
- OpenResty 站点只引用这些固定路径，因此续签后不再需要“先签发、再同步到站点目录”的第二条链路。
- 续签后的 reload 由 `1Panel/OpenResty` 自己触发，不再依赖 `nginx-ui` 侧脚本和 cron。

### Migration Strategy

1. 在宿主机创建并规范化 `/data/1panel/www/certs/`。
2. 在 `1Panel` 中为现有证书建立或重建 `Cloudflare DNS-01` 管理项。
3. 将签发产物统一落到 `/data/1panel/www/certs/`。
4. 先修改 `2053` 现网站点证书引用到新目录，验证现网业务不受影响。
5. 停用旧的 `nginx-ui` 证书同步链路，但保留旧目录作为迁移期回退资产。
6. 之后再进入 `2443` 预演与正式 `8443` 切换。

### OpenResty Preparation For 8443

在证书主目录和续签链路稳定后，再在 `1panel-openresty-prod` 中新增或补齐以下验证入口：

- `1panel.zzzai.cloud:2443`
  - 反代 `http://127.0.0.1:2096`
  - 读取 `/data/1panel/www/certs/` 下统一证书路径
- `nginx.zzzai.cloud:2443`
  - 反代 `http://127.0.0.1:19000`
  - 正式切换后改为明确拒绝结果（推荐 `403`）
- `token.zzzai.cloud:2443`
  - 行为镜像当前 `8443` 入口
  - 保留 `/setup` 的本机访问限制
- `pay.zzzai.cloud:2443`
  - 行为镜像当前 `8443` 入口

### Formal Cutover

正式窗口按以下顺序执行：

1. 备份 `nginx-ui-prod` 当前运行态、`nginx -T` 输出、相关站点配置和当前证书引用。
2. 备份 `1panel-openresty-prod` 切换前的 `nginx -T` 输出和目标站点配置。
3. 对四个 `2443` 验证入口执行最后一次本机 `curl --resolve` 预检。
4. 停止 `nginx-ui-prod`。
5. 确认宿主机 `8443` 已释放。
6. 让 OpenResty 切到正式 `8443` 口径，执行 `nginx -t` 与 `reload`。
7. 按顺序验活：
  - `https://1panel.zzzai.cloud:8443/`
  - `https://token.zzzai.cloud:8443/`
  - `https://pay.zzzai.cloud:8443/pay`
  - `https://nginx.zzzai.cloud:8443/` 应明确表现为拒绝结果，而不是误路由到其它站点

### Rollback Strategy

回退原则拆成两层：

- 证书治理失败时：
  - 不推进 `8443` 切换
  - 保留现有 `nginx-ui` 证书与同步链路
  - 站点证书引用回退到旧路径或旧配置快照
- 入口切换失败时：
  - 只回退入口监听，不回退已经完成的宿主机证书主目录
  - 回退动作为：恢复 OpenResty 旧监听配置、重新启动 `nginx-ui-prod`、验证原有四个 `8443` 入口恢复旧行为

## Validation

### Certificate-Phase Validation

- `1Panel` 中现有证书都已切到 `Cloudflare DNS-01` 管理。
- 宿主机目录 `/data/1panel/www/certs/` 下存在统一证书目录与文件。
- `2053` 现网站点切到新证书路径后继续返回成功。
- 自动续签测试或演练能证明：
  - 续签产物会更新到 `/data/1panel/www/certs/<cert-id>/`
  - OpenResty 会在证书变化后正确 reload
- `nginx-ui` 旧证书目录不再被 OpenResty 配置引用。

### Pre-Cutover Validation

- `docker ps` 确认：
  - `nginx-ui-prod` 仍在运行
  - `1panel-openresty-prod` 仍在运行
- `ss -ltnp` 确认：
  - `8443` 当前由 `nginx-ui-prod` 占用
  - `2443` 已由 `1panel-openresty-prod` 占用
- 对四个域名执行本机预检：
  - `curl -kI --resolve 1panel.zzzai.cloud:2443:127.0.0.1 https://1panel.zzzai.cloud:2443/`
  - `curl -kI --resolve token.zzzai.cloud:2443:127.0.0.1 https://token.zzzai.cloud:2443/`
  - `curl -kI --resolve pay.zzzai.cloud:2443:127.0.0.1 https://pay.zzzai.cloud:2443/pay`
  - `curl -kI --resolve nginx.zzzai.cloud:2443:127.0.0.1 https://nginx.zzzai.cloud:2443/`

### Post-Cutover Validation

- `ss -ltnp | grep ':8443 '` 显示 `8443` 已由 OpenResty 接管。
- 四个目标 URL 的本机 `--resolve` 验证符合预期。
- `nginx.zzzai.cloud:8443` 不应误命中 `1panel`、`token` 或 `pay`。
- `nginx-ui-prod` 已停止但容器仍存在，可随时 `docker start`。

### Observation Window

- 切换完成后立即做一轮密集验活。
- 在 `24-72` 小时内补一轮复检即可，不设置每日巡检任务。
- 观察期内保留 `nginx-ui-prod` 容器和旧证书目录，不执行删除动作。

## Rollback Script Skeleton

以下脚本骨架用于在生产机本机执行，目的是把切换与回退动作固定化，而不是在故障时重新手敲命令。

### `switch-8443-to-openresty.sh`

```bash
#!/usr/bin/env bash
set -euo pipefail

ts="$(date +%Y%m%d-%H%M%S)"
base="/root/8443-cutover"
bak="$base/backups/$ts"
mkdir -p "$bak"

docker inspect nginx-ui-prod > "$bak/nginx-ui.inspect.json"
docker inspect 1panel-openresty-prod > "$bak/openresty.inspect.json"
docker exec nginx-ui-prod nginx -T > "$bak/nginx-ui.nginx-T.txt"
docker exec 1panel-openresty-prod nginx -T > "$bak/openresty.before.nginx-T.txt"
docker cp 1panel-openresty-prod:/usr/local/openresty/nginx/conf/conf.d "$bak/openresty-conf.d"
docker cp 1panel-openresty-prod:/www/sites "$bak/openresty-sites"

curl -kI --resolve 1panel.zzzai.cloud:2443:127.0.0.1 https://1panel.zzzai.cloud:2443/ > "$bak/preflight-1panel.txt"
curl -kI --resolve token.zzzai.cloud:2443:127.0.0.1 https://token.zzzai.cloud:2443/ > "$bak/preflight-token.txt"
curl -kI --resolve pay.zzzai.cloud:2443:127.0.0.1 https://pay.zzzai.cloud:2443/pay > "$bak/preflight-pay.txt"
curl -kI --resolve nginx.zzzai.cloud:2443:127.0.0.1 https://nginx.zzzai.cloud:2443/ > "$bak/preflight-nginx-ui.txt"

# 这里应把预先准备好的 cutover 配置包部署进 OpenResty 容器，
# 使其目标站点改为监听 8443，并让 nginx.zzzai.cloud 返回明确下线结果。
# 例如：
# docker cp "$base/bundles/openresty-conf.d/." 1panel-openresty-prod:/usr/local/openresty/nginx/conf/conf.d/
# docker cp "$base/bundles/openresty-sites/." 1panel-openresty-prod:/www/sites/

docker stop nginx-ui-prod

timeout 15 sh -c 'while ss -ltn | grep -q ":8443 "; do sleep 1; done'

docker exec 1panel-openresty-prod sh -lc 'nginx -t'
docker exec 1panel-openresty-prod sh -lc 'nginx -s reload'

curl -kI --resolve 1panel.zzzai.cloud:8443:127.0.0.1 https://1panel.zzzai.cloud:8443/
curl -kI --resolve token.zzzai.cloud:8443:127.0.0.1 https://token.zzzai.cloud:8443/
curl -kI --resolve pay.zzzai.cloud:8443:127.0.0.1 https://pay.zzzai.cloud:8443/pay
curl -kI --resolve nginx.zzzai.cloud:8443:127.0.0.1 https://nginx.zzzai.cloud:8443/
```

### `rollback-8443-to-nginx-ui.sh`

```bash
#!/usr/bin/env bash
set -euo pipefail

base="/root/8443-cutover"
latest_backup="${1:-$(ls -1dt "$base"/backups/* 2>/dev/null | head -n1)}"

test -n "$latest_backup"
test -d "$latest_backup/openresty-conf.d"
test -d "$latest_backup/openresty-sites"

docker cp "$latest_backup/openresty-conf.d/." 1panel-openresty-prod:/usr/local/openresty/nginx/conf/conf.d/
docker cp "$latest_backup/openresty-sites/." 1panel-openresty-prod:/www/sites/

docker exec 1panel-openresty-prod sh -lc 'nginx -t'
docker exec 1panel-openresty-prod sh -lc 'nginx -s reload'

timeout 15 sh -c 'while ss -ltn | grep -q ":8443 "; do sleep 1; done'

docker start nginx-ui-prod

timeout 20 sh -c 'until ss -ltnp | grep -q ":8443 .*nginx"; do sleep 1; done'

curl -kI --resolve 1panel.zzzai.cloud:8443:127.0.0.1 https://1panel.zzzai.cloud:8443/
curl -kI --resolve token.zzzai.cloud:8443:127.0.0.1 https://token.zzzai.cloud:8443/
curl -kI --resolve pay.zzzai.cloud:8443:127.0.0.1 https://pay.zzzai.cloud:8443/pay
curl -kI --resolve nginx.zzzai.cloud:8443:127.0.0.1 https://nginx.zzzai.cloud:8443/
```

## Non-Goals

- 本次不直接删除 `nginx-ui-prod` 容器、镜像或其数据目录。
- 本次不在同一个窗口里处理 `2053` 入口的退役与合并策略。
- 本次不把切换后的复检变成每日巡检或自动化任务。
