# Repository Working Rules

## Scope

- These rules apply to the AgentPlane control roots, with `D:\Projects\AgentPlane` as the formal Windows host entry and `/root/work/AgentPlane` retained as the WSL/Linux backend path during migration.
- Default to Chinese when replying to the repository owner unless explicitly requested otherwise.
- Keep root `AGENTS.md` short and durable; place operational details in `docs/` runbooks and reference docs.
- Child `AGENTS.md` files override this file when they are closer to the working directory.

## Repo Map

- `README.md`: repository entry, common commands, active navigation.
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
- Use `root` by default; switch user only when user-scoped environment or ownership constraints require it.
- Verify `whoami`, `$HOME`, and repository root before installing tools or writing runtime files.
- Real secrets stay in `secrets/`; tracked examples stay in `templates/`.
- Use project SSH aliases in `secrets/ssh/config`: `prod0-main`, `prod2-main`.
- New PEM files must be `chmod 600` before use.
- Keep repository ownership aligned with the working Linux user.
- Configure `user.name` and `user.email` before commit if absent.
- If Git reports dubious ownership, fix ownership first and add `safe.directory` only when necessary.
- Avoid parallel writes to Git config files.
- For AgentPlane-managed application repositories, default Git worktrees must live under `<repo>/.worktrees/`.
- Before creating a project-local worktree, the application repository `.gitignore` must ignore `.worktrees/`; do not default to `~/.config/superpowers/worktrees/...` unless the repository explicitly documents an override.
- Service assets live under `infra/compose/<service>/`; local runtime secrets under `secrets/services/`; templates under `templates/services/`.
- Repository-managed compose services keep both `docker-compose.wsl.yml` and `docker-compose.prod0.yml`.
- Container naming rule: WSL test containers end with `-dev`; production containers end with `-prod`.
- In production, project-managed containers and 1Panel app containers must attach to `zqf_network`; dedicated networks can only be additive.
- Exception: `openresty`-related 1Panel containers must use Docker `host` networking.
- Persistent host data should prefer `/data/<service>/...`.
- Complex or behavior-changing work should be planned before implementation.

## Definition Of Done

- Run the smallest relevant verification after each change.
- Prefer live state checks such as `docker ps`, `docker inspect`, direct file reads, and CLI verify commands over stale docs.
- For Cloudflare-fronted services, benchmark loopback/direct IP paths before proxy or fake-IP/TUN paths.
- For IPv6 verification, confirm both IPv4/IPv6 `listen` directives and validate with forced IPv6 requests.
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
