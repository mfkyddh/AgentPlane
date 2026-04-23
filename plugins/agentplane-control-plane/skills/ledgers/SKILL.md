---
name: agentplane-control-plane-ledgers
description: Generated plugin skill group for ledgers; routes to AgentPlane CLI-first commands.
generated_from: .codex/skills/catalog.yaml
group: ledgers
domains:
  - projection
source_skills:
  - inventory-ledger-ops
  - projection-ops
---

# Ledgers

Generated from `.codex/skills/catalog.yaml`.

This plugin group is a thin distribution layer over the repository-owned skills and CLI.

- Source repo skills: `inventory-ledger-ops`, `projection-ops`
- Primary domains: `projection`
- Stable entrypoint: `agentplane projection ...`
