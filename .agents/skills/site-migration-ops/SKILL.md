---
name: site-migration-ops
description: Use for migrating a single website or public ingress path into the AgentPlane-managed ingress model while preserving the current public entry until parallel validation passes.
---

# Site Migration Ops

## Overview

Use this workflow skill for site or domain migration. Keep the existing public entry online, create the new ingress path, validate it in parallel, then cut over only after the user accepts the evidence.

The common provider may be 1Panel OpenResty, nginx-ui, or Cloudflare, but provider details stay below the `agentplane ingress` workflow wherever possible.

## Commands

```bash
uv run python -m agentplane.cli ingress search --target <target> --repo-root <repo-root>
uv run python -m agentplane.cli ingress get --target <target> --alias <alias> --repo-root <repo-root>
uv run python -m agentplane.cli ingress plan --target <target> --alias <alias> --operation reconcile --repo-root <repo-root>
uv run python -m agentplane.cli ingress publish plan --target <target> --config-file <config-file> --cloudflare-env-file <cloudflare-env-file> --repo-root <repo-root>
uv run python -m agentplane.cli ingress publish apply --target <target> --config-file <config-file> --cloudflare-env-file <cloudflare-env-file> --repo-root <repo-root> --execute
uv run python -m agentplane.cli ingress publish verify --target <target> --config-file <config-file> --cloudflare-env-file <cloudflare-env-file> --repo-root <repo-root>
uv run python -m agentplane.cli ingress refresh-ledger --target <target> --repo-root <repo-root> --write
```

## Rules

- Never replace a working public entry before parallel validation succeeds.
- Patch provider-generated files only when the provider cannot express the required setting, and keep the patch minimal.
- Verify real listeners, served certificates, HTTP responses, and proxy behavior.
- Record the final non-sensitive state through ingress ledgers and docs, not by copying provider internals into runbooks.

## Downstream Docs

- `docs/runbooks/control-plane-domain-onboarding.md`
- `docs/reference/onepanel-api-contract.md`
