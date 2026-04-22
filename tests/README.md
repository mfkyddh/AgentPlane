# Test Suite

Run the default gate with:

```bash
uv run python -m pytest
```

The default gate is offline and excludes live WSL, Docker, SSH, remote provider, and external application checks through pytest markers declared in `pyproject.toml`.

Shared helpers belong in `tests/support/`. Add new shared CLI runners, path helpers, marker rules, or app resource fixtures there instead of importing from large test modules.

Use explicit markers for tests that require real infrastructure:

- `live_gate`
- `integration_wsl`
- `integration_remote`
- `docker_required`
- `ssh_required`
- `external_app`

