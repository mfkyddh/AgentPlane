---
name: agentplane-control-plane-firewall
description: Generated plugin skill group for firewall; routes to AgentPlane CLI-first commands.
generated_from: .codex/skills/catalog.yaml
group: firewall
domains:
  - host
source_skills:
  - onepanel-firewall-ops
---

# Firewall

Generated from `.codex/skills/catalog.yaml`.

This plugin group is a thin distribution layer over the repository-owned skills and CLI.

- Source repo skills: `onepanel-firewall-ops`
- Primary domains: `infra`
- Stable entrypoint: `agentplane onepanel --env <target> ... --json`
