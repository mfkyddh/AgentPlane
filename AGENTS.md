# Repository Working Rules

## Scope

- This repository is an Agent-first control plane template repository.
- Default to Chinese when replying to the repository owner unless explicitly requested otherwise.
- Keep root `AGENTS.md` short and durable; place operational details in `docs/` runbooks and reference docs.
- Child `AGENTS.md` files override this file when they are closer to the working directory.

## Repo Map

- `README.md`: repository entry, bootstrap path, active navigation.
- `docs/architecture/`: long-term control-plane contracts.
- `docs/runbooks/`: active operating procedures.
- `docs/reference/`: stable lookup docs such as app repo standards, versioning, naming, and compat ledgers.
- `docs/maintainers/`: maintainer-only authoring and governance rules.
- `infra/compose/`: tracked compose assets.
- `inventory/`: tracked non-sensitive state projections.
- `agentplane/`: Python CLI and internal automation code.
- `templates/`: tracked example files.
- `secrets/`: local real secrets; never commit.
- `.codex/`: repository-owned Codex skills and environment actions.

## Standard Commands

- Command discovery must start from `uv run python -m agentplane.cli --help`.
- Formal host-scoped cleanup operations must prefer `uv run python -m agentplane.cli host cleanup ...`.
- Formal host-scoped automation operations must prefer `uv run python -m agentplane.cli host automation ...`.
- Formal host-scoped network governance must prefer `uv run python -m agentplane.cli host network ...`; do not route active workflows through a top-level `uv run python -m agentplane.cli network ...` entry.
- Formal host-scoped remote execution must prefer `uv run python -m agentplane.cli host remote bash ...`.
- Formal host-scoped secrets operations must prefer `uv run python -m agentplane.cli host secrets ...`.
- Daily automation entry must prefer `uv run python -m agentplane.cli ...`.
- Python projects managed by AgentPlane should prefer `uv` for dependency installation, virtualenv management, and command execution.
- Node.js projects managed by AgentPlane should prefer `pnpm` for dependency installation and script execution.
- Temporary Node binaries should prefer `pnpm dlx ...`; only fall back to `npx` when incompatible.
- Docker Compose runtime commands must use `docker compose`; do not rely on the legacy `docker-compose` executable.

## Working Rules

- Default to a host-entry-first, backend-aware workflow.
- On Windows hosts, use `pwsh` as the default local entry shell.
- If the control plane and source tree both live on Windows, run `git`, `uv`, `pnpm`, tests, and other host-native commands directly in `pwsh`.
- If the control plane is on Windows but the source tree lives in WSL, keep `pwsh` as the entry shell and route build, test, package-manager, and other source-bound commands to the matching WSL source root.
- On Windows, Linux-only actions should prefer `wsl.exe -e <program> <args...>`; only fall back to `sh -lc` or `bash -lc` when WSL-side shell features are required.
- Remote Linux operations should prefer `pwsh -> agentplane.cli -> WSL/SSH backend`; do not hand-build multi-layer shell commands.
- On Linux/macOS, continue using the native POSIX shell for local execution.
- Desktop-browser validation is the main companion exception; use the host browser when a real GUI browser is required.
- Control plane location determines the entry host; source location determines the local execution host.
- Real secrets stay in `secrets/`; tracked examples stay in `templates/`.
- Template bootstrap truth lives under `secrets/local/control-plane/` and `secrets/targets/<target>/`.
- Use target SSH aliases from `secrets/ssh/config`; avoid hard-coding environment-specific aliases in shared docs.
- New PEM files must be `chmod 600` before use.
- Configure `user.name` and `user.email` before commit if absent.
- Avoid parallel writes to Git config files.
- For AgentPlane-managed application repositories, default Git worktrees must live under `<repo>/.worktrees/`.
- Before creating a project-local worktree, the application repository `.gitignore` must ignore `.worktrees/`; do not default to `~/.config/superpowers/worktrees/...` unless the repository explicitly documents an override.
- Service assets live under `infra/compose/<service>/`; local runtime secrets under `secrets/services/`; templates under `templates/services/`.
- Repository-managed compose services may keep `docker-compose.wsl.yml` and `docker-compose.<target>.yml` when backend-specific variants are required.
- Container naming rule: test containers end with `-dev`; production containers end with `-prod`.
- In production, project-managed containers and 1Panel app containers should attach to the intended shared network declared by tracked truth; dedicated networks can only be additive.
- Persistent host data should prefer `/data/<service>/...`.
- Complex or behavior-changing work should be planned before implementation.

## Definition Of Done

- Run the smallest relevant verification after each change.
- Prefer live state checks such as `docker ps`, `docker inspect`, direct file reads, and CLI verify commands over stale docs.
- When work changes docs, skills, or repo-owned Codex configuration, run the matching doc or contract tests.
- If something cannot be verified, state exactly what was not verified and why.

## Docs

- Repository entry and active docs: `README.md`.
- Architecture contracts index: `docs/architecture/README.md`.
- Generic app onboarding standard: `docs/reference/app-repository-standard.md`.
- AgentPlane and app boundary contract: `docs/architecture/agentplane-app-collaboration.md`.
- App delivery versioning reference: `docs/reference/app-delivery-versioning.md`.
- Compat retirement ledger: `docs/reference/compat-retirement-ledger.md`.
- Naming registry: `docs/reference/control-plane-naming-registry.md`.
- Maintainer authoring rules: `docs/maintainers/control-plane-authoring.md`.
