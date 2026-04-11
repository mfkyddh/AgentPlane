# PostgreSQL

- Tracked templates live here: `docker-compose.wsl.yml`, `docker-compose.prod0.yml`, and `docker-compose.prod2.yml`.
- Real database bootstrap values live in `secrets/services/postgres/admin.<target>.env`.
- Canonical admin template: `templates/services/postgres/admin.env.example`.
- Legacy flat template `templates/services/postgres.env.example` is projection-only migration context, not the active prod0 admin source.
- Bootstrap command:
  `uv run python -m ops.cli secrets init-data-services --target <wsl|prod0-main|prod2-main>`
- Before cutting a stateful app to a tenant PostgreSQL database, migrate the source data first. Rendering a new runtime env without data migration is not a valid cutover.
