---
name: projection-ops
description: Use when the task is about app runtime env projection, projection drift verification, or moving runtime env generation out of object truth domains in AgentPlane.
---

# Projection Ops

## Overview

Projection truth is derived, not declared. Use the formal `projection runtime-env`, `projection verification`, `projection fixture`, and `projection ledger` entrypoints; do not route runtime env generation back through removed tenant wrappers or ad-hoc scripts.

## Commands

```bash
uv run python -m agentplane.cli projection runtime-env plan --target <target> --app <app> --repo-root <repo-root>
uv run python -m agentplane.cli projection runtime-env apply --target <target> --app <app> --repo-root <repo-root>
uv run python -m agentplane.cli projection runtime-env verify --target <target> --app <app> --repo-root <repo-root>
uv run python -m agentplane.cli projection verification run --target <target> --profile <profile> --repo-root <repo-root>
uv run python -m agentplane.cli projection fixture plan --target <target> --profile wsl-fixture --repo-root <repo-root>
uv run python -m agentplane.cli projection fixture apply --target <target> --profile wsl-fixture --repo-root <repo-root> --execute
uv run python -m agentplane.cli projection fixture cleanup --target <target> --profile wsl-fixture --repo-root <repo-root> --execute
uv run python -m agentplane.cli projection ledger refresh --target <target> --repo-root <repo-root> --write
```
