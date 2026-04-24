---
name: agentplane-control-plane-ingress
description: Generated plugin skill group for ingress; routes to AgentPlane CLI-first commands.
generated_from: .codex/skills/catalog.yaml
group: ingress
domains:
  - ingress
source_skills:
  - onepanel-website-ops
---

# Ingress

Generated from `.codex/skills/catalog.yaml`.

This plugin group is a thin distribution layer over the repository-owned skills and CLI.

- Source repo skills: `onepanel-website-ops`
- Primary domains: `ingress`
- Stable entrypoint: `uv run python -m agentplane.cli ingress ...`
