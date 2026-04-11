# Redis

- Tracked templates live here: `docker-compose.wsl.yml`, `docker-compose.prod0.yml`, and `docker-compose.prod2.yml`.
- Real Redis config with the active password lives in `secrets/services/redis/admin.<target>.conf`.
- Canonical admin template: `templates/services/redis/admin.env.example`.
- Legacy flat template `templates/services/redis.conf.example` is projection-only migration context, not the active prod0 admin source.
- Bootstrap command:
  `uv run python -m ops.cli secrets init-data-services --target <wsl|prod0-main|prod2-main>`
- Redis admin `.conf` files are mounted read-only into the container and must remain world-readable on the host copy, typically `0644`, or Redis will fail to start.
- `prod0-main` currently uses shared runtime Redis credentials for app traffic; tenant Redis secrets are still authoritative for ACL reconciliation and ledger metadata.
