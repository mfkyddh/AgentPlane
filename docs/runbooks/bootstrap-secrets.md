# Bootstrap Secrets

1. Create local directory skeleton:
   `mkdir -p secrets/env secrets/ssh/keys secrets/services/{postgres,redis,minio}`
2. Copy templates into `secrets/` and fill real values:
   - `templates/env/prod-jump.env.example -> secrets/env/prod-jump.env`
   - `templates/ssh/config.example -> secrets/ssh/config`
   - `templates/services/postgres/admin.env.example -> secrets/services/postgres/admin.<target>.env`
   - `templates/services/redis/admin.env.example -> derive secrets/services/redis/admin.<target>.conf`
   - `templates/services/minio/admin.env.example -> secrets/services/minio/admin.<target>.env`
   - `templates/services/onepanel-login.env.example -> secrets/services/onepanel-login.<target>.env`
   - Legacy flat templates under `templates/services/*.example` are projection-only migration references, not canonical admin sources.
3. Bootstrap target-scoped PostgreSQL / Redis / MinIO admin secrets:
   - `uv run python -m agentplane.cli host secrets init-data-services wsl`
   - `uv run python -m agentplane.cli host secrets init-data-services prod0-main`
4. Put real PEM files in `secrets/ssh/keys/` with canonical names:
   - `prod0-main.pem`
   - `prod2-main.pem`
5. Tighten permissions:
   `chmod 700 secrets secrets/env secrets/ssh secrets/ssh/keys`
   `find secrets/services -type d -exec chmod 755 {} +`
   `chmod 600 secrets/env/prod-jump.env secrets/ssh/config secrets/ssh/keys/*.pem`
   `find secrets/services -type f -exec chmod 600 {} +`
   `find secrets/services/redis -type f -name "admin.*.conf" -exec chmod 644 {} +`
6. Verify SSH connectivity:
   - `ssh -F secrets/ssh/config prod0-main "hostname && whoami"` 期望 `prod0-main` 返回 `root`
   - `ssh -F secrets/ssh/config prod2-main "hostname && whoami"` 期望 `prod2-main` 返回 `root`
7. Switch to the unified daily entry after bootstrap:
   - `uv run python -m agentplane.cli --help`
   - `uv run python -m agentplane.cli host audit wsl --repo-root /root/work/AgentPlane`
   - `uv run python -m agentplane.cli host inventory prod0-main --repo-root /root/work/AgentPlane`

## Notes

- Daily operations should start from `uv run python -m agentplane.cli ...`.
- Direct script calls under `ops/scripts/` are compatibility or low-level debugging paths, not the primary workflow.
- `prod0-main` data-service admin secrets now live only under `secrets/services/<service>/admin.<target>.*`; the old flat files `secrets/services/postgres.env`, `secrets/services/redis.conf`, `secrets/services/minio.env` are retired.
- For stateful app resource cutovers, do not switch runtime `DATABASE_*` to a new app resource database until the source data has been migrated into that app resource DB and the app resource credentials have been verified with a real login.
- On `prod0-main`, Redis app resource metadata remains useful for ledgers and ACL provisioning, but the active runtime credential model is shared runtime password plus DB/key-prefix partitioning unless a service-specific cutover plan explicitly says otherwise.
- 1Panel 登录凭据（`secrets/services/onepanel-login.<target>.env`）也属于仓库 secrets 合同的一部分，文档中只保留模板与路径，不记录真实值。
