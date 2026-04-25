---
name: app-resource-ops
description: App resource truth, projection verification, and ledger refresh guidance that routes to the formal CLI.
---

# App Resource Ops

## Overview

`app-resource-ops` routes to the canonical `uv run python -m agentplane.cli app resource ...` commands for resource truth, projection verification, and ledger refresh. The canonical entry is `uv run python -m agentplane.cli app resource ...`. Keep this skill focused on the formal surface and do not recreate a second implementation.

## Commands

```bash
uv run python -m agentplane.cli app resource search --target <target> --repo-root <repo-root>
uv run python -m agentplane.cli app resource get --target <target> --app <app> --repo-root <repo-root>
uv run python -m agentplane.cli app resource verify --target <target> --app <app> --repo-root <repo-root>
uv run python -m agentplane.cli app resource refresh-ledger --target <target> --repo-root <repo-root> --write
uv run python -m agentplane.cli infra secrets sync-layout <target> --repo-root <repo-root> --write
```
