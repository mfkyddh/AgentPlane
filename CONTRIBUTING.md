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

Detailed guide: [docs/tech-stack.md](docs/tech-stack.md)

## Before Opening A PR

Run:

```bash
agentplane project health-check --repo-root .
```

For docs or contract changes, also run the relevant focused tests under `tests/`.

Full architecture and conventions: [docs/architecture.md](docs/architecture.md).

---

## Security Policy

### Supported Versions

Security fixes target the current `main` branch until formal releases are introduced.

### Reporting A Vulnerability

Please avoid publishing sensitive details before maintainers have a chance to investigate. Open a private security advisory when the hosting platform supports it, or contact the maintainers through the repository's published contact channel.

Never include real credentials, private keys, production hostnames, or live target inventory in a public report. Use redacted examples and attach exact reproduction steps.

### Secret Handling

AgentPlane treats `secrets/` as local-only material. Public examples belong under `templates/`; tests should generate temporary secrets instead of committing real values.

---

## Support

Use GitHub issues for reproducible bugs, documentation gaps, and feature requests.

For questions, include:

- Operating system and shell.
- `agentplane --help` result if CLI startup is involved.
- The exact command you ran.
- Redacted logs or JSON output.
- Whether the issue requires live WSL, Docker, SSH, or a remote provider.

Do not post real secrets, PEM files, provider tokens, or production credentials.

---

## Code Of Conduct

### Our Standard

This project expects respectful, constructive collaboration. Be direct about technical problems, but keep discussion focused on the work and its impact.

### Unacceptable Behavior

- Harassment, threats, or personal attacks.
- Publishing private information without explicit permission.
- Repeatedly derailing technical discussion after maintainers have redirected it.

### Enforcement

Maintainers may edit, hide, or remove comments and may restrict participation when behavior makes collaboration unsafe or unproductive.
