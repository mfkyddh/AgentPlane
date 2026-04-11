# MinIO

- Tracked templates live here: `docker-compose.wsl.yml`, `docker-compose.prod0.yml`, and `docker-compose.prod2.yml`.
- Real root credentials live in `secrets/services/minio/admin.<target>.env`.
- Canonical admin template: `templates/services/minio/admin.env.example`.
- Legacy flat template `templates/services/minio.env.example` is projection-only migration context, not the active prod0 admin source.
- Bootstrap command:
  `uv run python -m ops.cli secrets init-data-services --target <wsl|prod0-main|prod2-main>`
