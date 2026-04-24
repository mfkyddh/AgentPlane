---
status: active
owner: AgentPlane maintainers
last_verified: 2026-04-22
superseded_by: null
---

# Testing Architecture

AgentPlane's test suite is organized around deterministic default tests and explicit live gates.

## Default Gate

`uv run python -m pytest` is the default local gate. It must not require:

- Docker daemon access
- SSH connectivity
- WSL availability
- Remote provider credentials
- External application repositories

The default gate is allowed to inspect tracked templates, render dry-run plans, and use temporary directories.

## Live Gates

Tests or commands that touch real WSL, Docker, SSH, or provider endpoints must be explicitly marked:

- `live_gate`
- `integration_wsl`
- `integration_remote`
- `docker_required`
- `ssh_required`
- `external_app`

Marker assignment lives in `tests/support/markers.py` so the policy is visible in one place.

## Shared Test Helpers

Shared helpers live under `tests/support/`:

- `paths.py`: repository and tests root constants
- `cli.py`: subprocess helpers for invoking `agentplane.cli`
- `app_resources.py`: app resource path fixtures
- `app_object.py`: app object CLI/catalog fixtures
- `service_cli.py`: service CLI fixture builders
- `markers.py`: pytest marker routing rules

Do not add new cross-file helpers to large test modules. Put shared behavior under `tests/support/` first, then import it from tests.

## File Shape

Tests are grouped by domain directory:

- `tests/app/`
- `tests/infra/`
- `tests/onepanel/`
- `tests/projection/`
- `tests/runtime/`
- `tests/service/`
- `tests/ingress/`
- `tests/inventory/`
- `tests/repository/`
- `tests/secret_management/`
- `tests/compose/`

Keep new test files focused by behavior. Large historical files should shrink by moving reusable fixtures into `tests/support/` and splitting new behavior into focused files.
