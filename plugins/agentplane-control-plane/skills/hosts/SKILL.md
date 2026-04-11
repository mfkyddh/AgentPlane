---
name: agentplane-control-plane-hosts
description: Generated plugin skill group for hosts; routes to AgentPlane CLI-first commands.
generated_from: .codex/skills/catalog.yaml
group: hosts
domains:
  - host
source_skills:
  - host-ops
---

# Hosts

Generated from `.codex/skills/catalog.yaml`.

This plugin group is a thin distribution layer over the repository-owned skills and CLI.

- Source repo skills: `host-ops`
- Primary domains: `host`
- Stable entrypoint: `uv run python -m agentplane.cli host ...`
