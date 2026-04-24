# Test Suite

Run the default gate with:

```bash
uv run python -m pytest
```

The default gate is offline and excludes live WSL, Docker, SSH, remote provider, and external application checks through pytest markers declared in `pyproject.toml`.

## Layout

- `app/`: app object, resource, delivery, contract, build, render, deploy, verify, inventory, and doc-sync tests.
- `infra/`: infra governance, WSL boundary, SSH, remote command, and live-gate contract tests.
- `onepanel/`: provider substrate, object API plans, fixture, verification, plugin, and target-specific audit tests.
- `projection/`: formal projection CLI tests.
- `runtime/`: platform, workspace, backend runner, and resolver tests.
- `service/`: service object and lifecycle tests.
- `ingress/`: ingress object and publish workflow tests.
- `inventory/`: inventory generation and observation payload tests.
- `repository/`: repo-wide docs, CLI entrypoints, snapshot, bootstrap, pyproject, and readiness tests.
- `secret_management/`: secrets layout and backup tests.
- `compose/`: compose-template and external-app layout tests.
- `support/`: shared helpers only.

Shared helpers belong in `tests/support/`. Add new shared CLI runners, path helpers, marker rules, or app resource fixtures there instead of importing from large test modules.

Use explicit markers for tests that require real infrastructure:

- `live_gate`
- `integration_wsl`
- `integration_remote`
- `docker_required`
- `ssh_required`
- `external_app`
