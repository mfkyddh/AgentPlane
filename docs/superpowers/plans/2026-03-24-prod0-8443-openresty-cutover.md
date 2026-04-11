# Prod0 8443 OpenResty Cutover Implementation Plan

## 背景
原先把 `rehearsal→cutover` 作为启动顺序的做法忽略了证书治理的复杂性。新的“证书治理优先”方案要确保所有 HTTPS 资产都依赖统一的托管路径、自动续签以及可追踪的状态，再在其上叠加 `2443`/`8443` 入口切换。

## 执行顺序
1. **证书目录迁移并让 1Panel + Cloudflare DNS-01 自动续签接管**：在宿主机 `/data/1panel/www/certs/` 内创建 `zzzai-cloud` 与 `1panel-zzzai-cloud` 子目录，迁移旧 `nginx-ui` 证书并用自动化流程（Certbot/1Panel DNS-01）周期性地更新这一目录，直到续签任务稳定写入新目录。
2. **更新 2053 站点配置**：在 OpenResty 容器的 `/www/certs/<site>/fullchain.pem`（由 host `/data/1panel/www/certs/<site>/fullchain.pem` 挂载）中引用新的证书，确保 `token.zzzai.cloud`/`pay.zzzai.cloud`/`nginx.zzzai.cloud` 等 2053 站点成功使用新路径并通过 `curl --resolve ...:2053` 校验。
3. **证书治理通过后才允许 2443/8443 入口**：只有确认前两步完成、且 `prod0-main-openresty-certificate-management.md` 标注“证书治理通过”后，才重新部署 rehearsal/cutover bundle 和脚本；这些资产必须只引用 `/data/1panel/www/certs/<site>/...`（容器内 `/www/certs/<site>/...`），旧 `nginx-ui` 目录仅留作回退。

---

### Task 1: 证书目录迁移与 DNS-01 自动续签接管
- 创建设计好的目录结构并固定权限：`/data/1panel/www/certs/zzzai-cloud/`、`/data/1panel/www/certs/1panel-zzzai-cloud/`，`fullchain.pem` 与 `privkey.pem` 部署到各自子目录。
- 把现有 nginx-ui 证书（如 `/data/apps/nginx-ui-official/nginx/certs/*.pem`）以只读方式复制到新目录，进行一次 `openssl x509 -noout -text` 验证，并记录文件归属为 `root:root`（或 `1panel`）与 `0440` 权限。
- 在新目录中演练将 `/data/1panel/www/certs/zzzai-cloud/fullchain.pem`、`/data/1panel/www/certs/zzzai-cloud/privkey.pem`、`/data/1panel/www/certs/1panel-zzzai-cloud/fullchain.pem`、`/data/1panel/www/certs/1panel-zzzai-cloud/privkey.pem` 供应用读取的流程，避免老目录仍在生效。
- 在 1Panel 的证书配置里把保存路径改为 `/data/1panel/www/certs/<site>/`，并通过 Cloudflare DNS-01（`certbot renew --dry-run --dns-cloudflare` 或等效 1Panel 调用）确认 TXT 记录可写入/清理，自动续签任务能把证书写入新目录；完成后把这一验证记录在 `prod0-main-openresty-certificate-management.md`，说明旧 `/data/apps/nginx-ui-official/nginx/certs/` 仅用于回退。

### Task 2: 2053 入口改指向新目录
- 修改 `/usr/local/openresty/nginx/conf/conf.d/*.conf` 中指向证书的 `ssl_certificate` / `ssl_certificate_key` 为 `/data/1panel/www/certs/<site>/fullchain.pem` 与对应 `privkey.pem`，容器内角度写成 `/www/certs/<site>/fullchain.pem`。
- 重新加载 OpenResty 本地 `2053` 配置并验证：`curl --resolve token.zzzai.cloud:2053:127.0.0.1 https://token.zzzai.cloud:2053/` 等，确保所有 SNI/AEAD 走的是新目录，并用 `docker exec 1panel-openresty-prod nginx -T | grep ssl_certificate` 记录新路径。
- 2053 入口容许回滚：旧目录保留，在需要时重新加载旧证书，并在 runbook 中注明该逻辑与 `nxinx-ui` 目录之间的界面关系。

### Task 3: 2443/8443 脚本与演练（证书治理完成后）
- 依据 `prod0-main-openresty-certificate-management.md` 中的“证书治理通过”状态，再部署 reheasal/cutover bundle 与脚本；`remote_prepare*`、`remote_cutover*`、`remote_rollback*` 等脚本必须只引用 `/data/1panel/www/certs/<site>/fullchain.pem`（容器内路径为 `/www/certs/<site>/fullchain.pem`），旧 `nginx-ui` 目录仅保留给回退用途。
- 重新梳理 `docs/runbooks/prod0-main-8443-openresty-cutover.md` 的 precondition，把 reheasal/`2443` 作为证书治理通过后的演练，并带上 `curl --resolve ...:2443` / `:8443` 验证新目录。
- 安排 `2443` reheasal 与 `8443` cutover 的具体步骤，确认 `nginx.zzzai.cloud` 入口在 down 状态、`1panel`/`token`/`pay` 使用的是 `/data/1panel/www/certs/<site>/fullchain.pem`（或容器 `/www/certs/...`）并记录 curl 输出。
- 切换完成后更新 inventory/README，明确 `8443` 仍在 `nginx-ui-prod` 观察窗口控制，但其证书来源为 `/data/1panel/www/certs/`，并让监控/日志团队知晓新的证书路径。
