# MinIO

- Tracked templates live here: `docker-compose.wsl.yml` and `docker-compose.prod0.yml`.
- Real root credentials live in `secrets/services/minio/admin.<target>.env`.
- 正式管理模板: `templates/services/minio/admin.env.example`.
- Legacy flat template `templates/services/minio.env.example` is projection-only migration context, not the active prod0 admin source.
- Bootstrap command:
  `uv run python -m ops.cli secrets init-data-services --target <wsl|prod0-main>`
