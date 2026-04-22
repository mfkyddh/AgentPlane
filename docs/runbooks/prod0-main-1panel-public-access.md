# prod0-main 1Panel 公网接入口径（正式）

## 定位

- 本手册定义 `prod0-main` 当前 active 的公网入口、证书真源和只读审计口径。
- AgentPlane 的正式运维控制面是 `uv run python -m agentplane.cli ...`；本手册解释专题流程、风险与人工接力点，不替代正式实现。
- `prod0-main` 当前仍以升级前只读预检和现网核对为主，不把高风险对象写操作写成默认流程。

## 正式链路

- 主机：`prod0-main`（`175.178.114.192`）
- 正式公网入口基础设施层：`1panel-openresty-prod`
- OpenResty 网络模式：Docker `host`
- 当前现网正式公网 HTTPS 端口：`8443`
- 公网站点治理：必须先创建为 1Panel 网站对象，再由 OpenResty 承载
- 证书目录真源：`/data/1panel/www/certs/`
- 容器内证书路径：`/www/certs/`
- 证书托管：1Panel 证书 `id=4 (zzzai-cloud)`、`id=5 (1panel-zzzai-cloud)`，通过 Cloudflare DNS-01 自动续签

`8443` 仅是 `prod0-main` 现网特例，不是仓库级默认端口。

## 当前正式网站对象

| 域名 | 当前反代目标 |
| --- | --- |
| `1panel.zzzai.cloud` | `http://127.0.0.1:2096` |
| `token.zzzai.cloud` | `http://127.0.0.1:18080` |

1Panel 生成配置位于：

- `/data/1panel/www/conf.d/1panel.conf`
- `/data/1panel/www/conf.d/token.conf`

## 正式主入口

标准只读预检：

```bash
env -C <repo-root> uv run python -m agentplane.cli projection verification run \
  --target prod0-main \
  --profile prod0-readonly \
  --repo-root <repo-root> \
  --write-report

env -C <repo-root> uv run python -m agentplane.cli projection ledger refresh \
  --target prod0-main \
  --repo-root <repo-root> \
  --write
```

如需补充读取 provider/debug 事实，可只读执行 `uv run python -m agentplane.cli onepanel --env prod0-main panel get`，但不要把它当默认预检主入口。

如需定点核对某个站点对象，用正式 `website` 对象面，而不是页面点击或 raw provider workflow：

```bash
env -C <repo-root> uv run python -m agentplane.cli website get \
  --target prod0-main \
  --alias token \
  --repo-root <repo-root>

env -C <repo-root> uv run python -m agentplane.cli website verify \
  --target prod0-main \
  --alias token \
  --repo-root <repo-root>
```

## 证书治理

正式证书对象：

- `id=4`：`zzzai-cloud`
  - `/data/1panel/www/certs/zzzai-cloud/fullchain.pem`
  - `/data/1panel/www/certs/zzzai-cloud/privkey.pem`
- `id=5`：`1panel-zzzai-cloud`
  - `/data/1panel/www/certs/1panel-zzzai-cloud/fullchain.pem`
  - `/data/1panel/www/certs/1panel-zzzai-cloud/privkey.pem`

治理基线：

- OpenResty 配置中的 `ssl_certificate` 与 `ssl_certificate_key` 只引用 `/www/certs/<site>/...`
- 续签完成后必须执行 reload hook：

```bash
docker exec 1panel-openresty-prod nginx -t && \
docker exec 1panel-openresty-prod nginx -s reload
```

- 如证书对象、目录映射或网站 HTTPS 绑定发生漂移，在受控窗口内回到 1Panel 网站对象与证书对象处理，不要把历史外部脚本当正式实现

## Live-State 验证

```bash
ss -ltnp | grep ':8443'

curl -skI https://1panel.zzzai.cloud:8443/0f0e8602e3
curl -skI https://token.zzzai.cloud:8443/

docker exec 1panel-openresty-prod nginx -T | grep ssl_certificate
```

通过标准：

- `projection verification run --target prod0-main --profile prod0-readonly` 与现场 live-state 结论一致
- `projection ledger refresh --target prod0-main --repo-root <repo-root> --write` 产出的机器报告与 live-state 结论不冲突
- `website verify --target prod0-main --alias token --repo-root <repo-root>` 返回站点对象与反代事实一致
- `8443` 对外响应正常
- `nginx -T` 中证书路径只落在 `/www/certs/`
- 1Panel 证书对象与宿主 `/data/1panel/www/certs/` 中的文件一致

## 风险与人工接力

- `prod0-main` 目前不是常态写操作目标；如需调整网站对象、证书绑定或 OpenResty 入口，先确认升级窗口和变更审批。
- 现场如果必须查看 1Panel 页面、直调 `api_request.py` 或检查旧 cutover 资料，只能作为只读辅助，结论要回写到 formal `projection` / `website` 结果与 live-state 验证上。
- 历史 `8443` 切换细节已归档到 `docs/archive/runbooks/prod0-main-8443-openresty-cutover.md`，不要把历史窗口步骤继续当 active 主流程。

## 禁止事项

- 不允许把手工 `conf.d` vhost 当最终交付
- 不允许恢复任何历史迁移端口作为正式公网入口
- 不允许把 legacy 证书路径或历史入口组件恢复成正式链路
