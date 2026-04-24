---
name: agentplane-control-plane-infra
description: Generated plugin skill group for infra; routes to AgentPlane CLI-first commands.
generated_from: .codex/skills/catalog.yaml
group: infra
domains:
  - infra
source_skills:
  - host-ops
---

# Infra

Generated from `.codex/skills/catalog.yaml`.

This plugin group is a thin distribution layer over the repository-owned skills and CLI.

- Source repo skills: `host-ops`
- Primary domains: `infra`
- Stable entrypoint: `uv run python -m agentplane.cli infra ...`
