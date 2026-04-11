# AgentPlane Control Plane Plugin

This plugin is intentionally thin.

- Execution truth stays in `uv run python -m agentplane.cli ...`
- Canonical skill content stays in `.codex/skills/`
- Generated projection metadata stays in `.codex/skills/catalog.yaml`
- Provider/debug 1Panel object operations stay behind `uv run python -m agentplane.cli onepanel ...`
- Skills decide when to route into the CLI
- The plugin is for discovery, grouped entrypoints, and team distribution

Current intended groups:

- Websites
- Containers
- Firewall
- Cronjobs
- Apps
- Ledgers
- Hosts

Every group skill under `skills/` is generated from `.codex/skills/catalog.yaml` and should prefer the routed `uv run python -m agentplane.cli ...` entrypoint, adding `--json` only where the formal CLI supports structured output.
