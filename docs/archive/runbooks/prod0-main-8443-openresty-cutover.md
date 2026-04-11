# [ARCHIVED] prod0-main 8443 OpenResty 配置切换手册

> 历史窗口快照。该文档仅保留当时 `8443` 切换窗口的操作记录，不是当前正式入口。
> 当前决策请回到 `inventory/servers/prod0-main/`、active runbook，以及 `uv run python -m ops.cli ...` 的现行控制面口径。

## Historical Scope

- 本手册仅处理 `1panel-openresty-prod` 的 `8443` 配置更新。
- 正式链路固定为：`1Panel 网站对象 -> 1panel-openresty-prod:8443 -> 站点 upstream`。
- 证书仅允许来自 `/data/1panel/www/certs/`（容器内 `/www/certs/`）。
- 不包含任何已退役 legacy 入口组件的回退链路；相关历史远程脚本已退役。

## Historical Preconditions

1. `docs/runbooks/prod0-main-openresty-certificate-management.md` 已标记“证书治理通过”。
2. `1panel-openresty-prod` 运行中，且容器可读：
   - `/www/certs/zzzai-cloud/fullchain.pem`
   - `/www/certs/zzzai-cloud/privkey.pem`
   - `/www/certs/1panel-zzzai-cloud/fullchain.pem`
   - `/www/certs/1panel-zzzai-cloud/privkey.pem`
3. 1Panel 网站对象中至少存在：`1panel`、`newapi`、`pay`、`token`。

## Historical Change Procedure

1. 在 `prod0-main` 生成 bundle：

```bash
bash /root/8443-cutover/remote_prepare_prod0_openresty_8443_bundle.sh cutover
```

2. 执行切换脚本（OpenResty-only）：

```bash
bash /root/8443-cutover/remote_cutover_prod0_8443_to_openresty.sh
```

3. 采集结果并核对：

```bash
ss -ltnp | grep ':8443'
curl -skI https://1panel.zzzai.cloud:8443/0f0e8602e3
curl -skI https://newapi.zzzai.cloud:8443/
curl -skI https://pay.zzzai.cloud:8443/pay
curl -skI https://token.zzzai.cloud:8443/
curl -sS -o /tmp/newapi_models.out -w '%{http_code}\n' \
  https://newapi.zzzai.cloud:8443/v1/models
```

历史预期：

- `1panel/newapi/pay/token` 返回 `2xx`
- `newapi /v1/models` 未带令牌返回 `401`
- `ss -ltnp` 中 OpenResty 监听 `8443`

## Historical Rollback

- 回退只允许回退到“前一版 OpenResty 配置”（`/root/8443-cutover/backups/<timestamp>/rollback/`）。
- 执行方式：把备份的 `conf.d` 与 `sites` 恢复进 `1panel-openresty-prod` 后 `nginx -t && nginx -s reload`。
- 禁止把任何已退役 legacy 入口组件恢复为正式公网入口。
