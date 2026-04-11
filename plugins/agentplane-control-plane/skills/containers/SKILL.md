---
name: agentplane-control-plane-containers
description: Generated plugin skill group for containers; routes to AgentPlane CLI-first commands.
generated_from: .codex/skills/catalog.yaml
group: containers
domains:
  - service
source_skills:
  - onepanel-container-ops
---

# Containers

Generated from `.codex/skills/catalog.yaml`.

This plugin group is a thin distribution layer over the repository-owned skills and CLI.

- Source repo skills: `onepanel-container-ops`
- Primary domains: `service`
- Stable entrypoint: `uv run python -m agentplane.cli service ...`
