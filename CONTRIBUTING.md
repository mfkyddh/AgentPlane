---
status: active
owner: AgentPlane maintainers
last_verified: 2026-04-29
superseded_by: null
audience: both
---

# Contributing

Thanks for helping improve AgentPlane.

## Development Setup

1. Fork or clone the repository.
2. Install `uv`.
3. Run `agentplane --help`.
4. Run `uv run python -m pytest`.

Use one source checkout per machine. On Windows, the same checkout may be used by the WSL backend through resolver-managed path mapping. Do not create platform-specific virtualenvs such as `.venv-win` or `.venv-wsl`.

## Change Expectations

- Keep formal execution behind `agentplane ...`.
- Keep provider details inside provider or debug layers.
- Keep real secrets under `secrets/`; commit only examples under `templates/`.
- Add or update focused tests for behavior changes.
- Run `ruff` for Python style and obvious correctness checks.
- Keep default tests offline and deterministic. Real Docker, SSH, WSL, or provider checks must use explicit pytest markers or formal live-gate commands.

## Branch And Merge Flow

Use a short-lived branch for each logical change:

```bash
git switch main
git pull --ff-only origin main
git switch -c codex/<short-description>
```

Keep commits atomic and use Conventional Commits:

```bash
git commit -m "fix(scope): describe the change"
```

Push the branch, open a PR, wait for CI to pass, then squash merge into `main`. After merge, sync `main` and delete the completed branch:

```bash
git switch main
git pull --ff-only origin main
git branch -d codex/<short-description>
git push origin --delete codex/<short-description>
```

Do not force-push to `main`. Direct commits to `main` are reserved for maintainer-approved low-risk or urgent changes and still require the same validation discipline.

## Local Testing (Recommended)

Set up pre-commit hooks to catch errors before pushing to CI:

```bash
uv pip install pre-commit
pre-commit install
pre-commit install --hook-type pre-push
```

This runs the same checks as CI (`fast-gate`) locally:
- **pre-commit**: Ruff lint, commit message validation
- **pre-push**: Fast tests, docs sanity, secret scan

Detailed guide: [docs/reference/testing-conventions.md](docs/reference/testing-conventions.md)

## Before Opening A PR

Run:

```bash
agentplane repo health-check --repo-root .
```

For docs or contract changes, also run the relevant focused tests under `tests/`.

Full Git policy: [docs/reference/git-conventions.md](docs/reference/git-conventions.md).

To enable the local commit message check:

```bash
git config core.hooksPath .githooks
```
