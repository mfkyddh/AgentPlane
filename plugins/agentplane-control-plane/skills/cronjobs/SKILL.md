---
name: agentplane-control-plane-cronjobs
description: Generated plugin skill group for cronjobs; routes to AgentPlane CLI-first commands.
generated_from: .codex/skills/catalog.yaml
group: cronjobs
domains:
  - service
source_skills:
  - onepanel-cronjob-ops
---

# Cronjobs

Generated from `.codex/skills/catalog.yaml`.

This plugin group is a thin distribution layer over the repository-owned skills and CLI.

- Source repo skills: `onepanel-cronjob-ops`
- Primary domains: `service`
- Stable entrypoint: `uv run python -m agentplane.cli onepanel --env <target> ... --json`
