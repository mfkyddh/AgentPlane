# Contributing

Thanks for helping improve AgentPlane.

## Development Setup

1. Fork or clone the repository.
2. Install `uv`.
3. Run `uv run python -m agentplane.cli --help`.
4. Run `uv run python -m pytest`.

Use one source checkout per machine. On Windows, the same checkout may be used by the WSL backend through resolver-managed path mapping. Do not create platform-specific virtualenvs such as `.venv-win` or `.venv-wsl`.

## Change Expectations

- Keep formal execution behind `uv run python -m agentplane.cli ...`.
- Keep provider details inside provider or debug layers.
- Keep real secrets under `secrets/`; commit only examples under `templates/`.
- Add or update focused tests for behavior changes.
- Keep default tests offline and deterministic. Real Docker, SSH, WSL, or provider checks must use explicit pytest markers or formal live-gate commands.

## Before Opening A PR

Run:

```bash
uv run python -m pytest
uv run python -m agentplane.cli --help
```

For docs or contract changes, also run the relevant focused tests under `tests/`.

