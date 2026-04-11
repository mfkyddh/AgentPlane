# Prod1 Retirement Cleanup Design

> **Status:** Drafted for user review before implementation

**Goal:** Remove all repository-tracked inventory, runbook, architecture, and reference material related to the retired production host `prod1-backup`, leaving only current hosts and valid control-plane guidance.

**Scope:**
- Delete the dedicated inventory tree at `inventory/servers/prod1-backup/`.
- Remove or rewrite all repository documentation that treats `prod1-backup` as an active, supported, or reference host.
- Preserve still-valid procedures by rewriting them around remaining hosts instead of leaving broken multi-host wording.

**Out of Scope:**
- Secrets under `secrets/` and any untracked local files.
- Runtime changes on real hosts.
- Historical git history.

**Approach:**
1. Enumerate tracked references to `prod1-backup` and production-host-1 wording.
2. Delete the dedicated inventory subtree for the retired host.
3. Rewrite docs and repo guidance so only active hosts remain in architecture, runbooks, and examples.
4. Re-run repository search to ensure no tracked references remain.

**Validation:**
- `rg -n --hidden --glob "!/.git" "prod1-backup|1号生产机|1 号生产机|生产机1|生产机 1"` returns no hits in tracked content.
- Review git diff to confirm removals are limited to retired-host material.
