# Prod0 Redis DB Isolation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 `prod0-main` 的 Redis 多租户运行时从 ACL 用户模型收敛为兼容现网应用的 DB 级逻辑分区模型，并同步修正 OP_Linux 的 env 渲染、校验、台账、文档和生产切换流程。

**Architecture:** 先用测试锁定新行为，再修改 `ops.cli tenant` 的 Redis URL/字段投影和重复校验逻辑，然后把 inventory/README 语义从 remediation target 切到 live state。最后在 `prod0-main` 重新渲染 `newapi`、`sub2api` 运行时 env，逐个验证并清理不再使用的 Redis ACL 用户。

**Tech Stack:** Python (`uv`, `pytest`), OP_Linux CLI (`ops.cli.tenant`, `ops.cli.app`), JSON inventory, Markdown docs, Bash/SSH, Docker, Redis 7

---

### Task 1: Lock Redis DB Isolation Expectations In Tests

**Files:**
- Modify: `/root/work/OP_Linux/.worktrees/codex-prod0-tenant-reconcile/tests/test_prod0_postgres_app_resource_audit.py`
- Modify: `/root/work/OP_Linux/.worktrees/codex-prod0-tenant-reconcile/tests/test_app_cli.py`
- Modify: `/root/work/OP_Linux/.worktrees/codex-prod0-tenant-reconcile/tests/test_prod0_audit.py`
- Test: `/root/work/OP_Linux/.worktrees/codex-prod0-tenant-reconcile/tests/test_prod0_postgres_app_resource_audit.py`
- Test: `/root/work/OP_Linux/.worktrees/codex-prod0-tenant-reconcile/tests/test_app_cli.py`
- Test: `/root/work/OP_Linux/.worktrees/codex-prod0-tenant-reconcile/tests/test_prod0_audit.py`

- [ ] **Step 1: Write the failing tests for the new Redis projection and live-state semantics**

Add or update assertions so they require:

- `sub2api` rendered env keeps `REDIS_ENABLE_TLS` but no longer keeps `REDIS_USER` or `REDIS_KEY_PREFIX`
- `newapi` rendered `REDIS_CONN_STRING` / `REDIS_URL` uses password-only auth (`redis://:<password>@.../<db>`)
- `tenant validate` for `prod0-main` passes when Redis tenant secrets omit `REDIS_USER`
- `tenant validate` for `prod0-main` fails when Redis tenant secret omits `REDIS_KEY_PREFIX`
- duplicate Redis validation fails on duplicate `db` or duplicate normalized `key_prefix`, not on `(user, db, key_prefix)`
- tracked prod0 ledger / README no longer says `remediation target`; it must say DB-level logical partition, shared runtime password, and no strong isolation claim

```python
self.assertNotIn("REDIS_USER", sub2api_env_values)
self.assertEqual("false", sub2api_env_values.get("REDIS_ENABLE_TLS"))
self.assertEqual(
    "redis://:<urlencoded-password>@redis7-prod:6379/2",
    newapi_env_values.get("REDIS_CONN_STRING"),
)
self.assertIn("REDIS_KEY_PREFIX", result.stdout + result.stderr)
```

- [ ] **Step 2: Run the focused tests and verify they fail for the new expectations**

Run:

```bash
wsl.exe -u root -e bash -lc 'cd /root/work/OP_Linux/.worktrees/codex-prod0-tenant-reconcile && uv run pytest tests/test_prod0_postgres_app_resource_audit.py tests/test_app_cli.py tests/test_prod0_audit.py -q'
```

Expected:

- New assertions fail because current code still emits ACL-shaped Redis config and current docs still describe remediation semantics.

- [ ] **Step 3: Tighten test fixtures so the failures point at Redis DB isolation behavior**

Adjust helper payloads and baseline fixtures in the same test files so that:

- prod0 tenant Redis fixtures can omit `REDIS_USER`
- missing-`REDIS_KEY_PREFIX` fixtures fail on the intended validation path
- normalization cases cover `key_prefix` with and without trailing `:`
- app/doc tests compare against stable live-state phrases rather than transient wording
- `newapi` fixtures include one exact password `p@ ss:#word` and assert it renders as `p%40%20ss%3A%23word`
- `newapi` fixtures include one `REDIS_ENABLE_TLS=false` case that must render `redis://`
- `newapi` fixtures include one `REDIS_ENABLE_TLS=true` case that must render `rediss://`
- both URL tests assert full connection strings, not only scheme fragments

- [ ] **Step 4: Re-run the same focused tests and confirm the failures are stable and relevant**

Run:

```bash
wsl.exe -u root -e bash -lc 'cd /root/work/OP_Linux/.worktrees/codex-prod0-tenant-reconcile && uv run pytest tests/test_prod0_postgres_app_resource_audit.py tests/test_app_cli.py tests/test_prod0_audit.py -q'
```

Expected:

- Failures remain, but they now isolate the intended behavior changes only.

- [ ] **Step 5: Commit the red-to-spec lock before implementation**

```bash
wsl.exe -u root -e bash -lc 'cd /root/work/OP_Linux/.worktrees/codex-prod0-tenant-reconcile && git add tests/test_prod0_postgres_app_resource_audit.py tests/test_app_cli.py tests/test_prod0_audit.py && git commit -m "test: lock prod0 redis db isolation expectations"'
```

### Task 2: Implement Redis DB Isolation In tenant CLI

**Files:**
- Modify: `/root/work/OP_Linux/.worktrees/codex-prod0-tenant-reconcile/ops/cli/prod0_postgres_app_resource_audit.py`
- Modify: `/root/work/OP_Linux/.worktrees/codex-prod0-tenant-reconcile/ops/cli/app_resource_state.py`
- Modify: `/root/work/OP_Linux/.worktrees/codex-prod0-tenant-reconcile/templates/services/newapi.prod0.env.example`
- Modify: `/root/work/OP_Linux/.worktrees/codex-prod0-tenant-reconcile/templates/services/sub2api.prod0.env.example`
- Modify: `/root/work/OP_Linux/.worktrees/codex-prod0-tenant-reconcile/templates/app-resources/redis.env.example`
- Test: `/root/work/OP_Linux/.worktrees/codex-prod0-tenant-reconcile/tests/test_prod0_postgres_app_resource_audit.py`

- [ ] **Step 1: Implement the failing test’s minimal Redis URL and projection helpers**

Update `ops/cli/prod0_postgres_app_resource_audit.py` so that:

- `_redis_url()` emits password-only URLs
- `REDIS_ENABLE_TLS=true` switches to `rediss://`
- password text is URL-encoded
- `_merge_sub2api_env()` manages `REDIS_ENABLE_TLS` and drops `REDIS_USER` / `REDIS_KEY_PREFIX`

```python
def _redis_url(redis_env: dict[str, str]) -> str:
    scheme = "rediss" if redis_env.get("REDIS_ENABLE_TLS", "").lower() == "true" else "redis"
    password = quote(redis_env.get("REDIS_PASSWORD", ""), safe="")
    return f"{scheme}://:{password}@{host}:{port}/{db}"
```

- [ ] **Step 2: Replace Redis duplicate validation with DB + normalized key-prefix rules**

Update `ops/cli/app_resource_state.py` so duplicate detection:

- normalizes `key_prefix` by trimming whitespace and forcing trailing `:`
- reports duplicate DB and duplicate normalized prefix even when `user` differs or is missing

```python
def _normalize_key_prefix(value: object) -> str | None:
    ...
```

- [ ] **Step 3: Update prod0 templates to match the runtime contract**

Make the example files express the new model:

- `newapi.prod0.env.example` shows password-only Redis URL
- `sub2api.prod0.env.example` no longer advertises `REDIS_USER`
- `templates/app-resources/redis.env.example` marks `REDIS_USER` optional / historical for `prod0-main`

- [ ] **Step 4: Run focused tenant tests to verify green**

Run:

```bash
wsl.exe -u root -e bash -lc 'cd /root/work/OP_Linux/.worktrees/codex-prod0-tenant-reconcile && uv run pytest tests/test_prod0_postgres_app_resource_audit.py -q'
```

Expected:

- `tests/test_prod0_postgres_app_resource_audit.py` passes with the new Redis DB isolation behavior.

- [ ] **Step 5: Commit the tenant CLI and template changes**

```bash
wsl.exe -u root -e bash -lc 'cd /root/work/OP_Linux/.worktrees/codex-prod0-tenant-reconcile && git add ops/cli/prod0_postgres_app_resource_audit.py ops/cli/app_resource_state.py templates/services/newapi.prod0.env.example templates/services/sub2api.prod0.env.example templates/app-resources/redis.env.example tests/test_prod0_postgres_app_resource_audit.py && git commit -m "fix: switch prod0 redis projection to db isolation"'
```

### Task 3: Move Ledgers And Generated Docs To Live DB-Partition Semantics

**Files:**
- Modify: `/root/work/OP_Linux/.worktrees/codex-prod0-tenant-reconcile/ops/cli/apps.py`
- Modify: `/root/work/OP_Linux/.worktrees/codex-prod0-tenant-reconcile/inventory/servers/prod0-main/app-resources.json`
- Modify: `/root/work/OP_Linux/.worktrees/codex-prod0-tenant-reconcile/inventory/servers/prod0-main/app_resources.md`
- Modify: `/root/work/OP_Linux/.worktrees/codex-prod0-tenant-reconcile/inventory/servers/prod0-main/inventory.json`
- Modify: `/root/work/OP_Linux/.worktrees/codex-prod0-tenant-reconcile/inventory/servers/prod0-main/README.md`
- Modify: `/root/work/OP_Linux/.worktrees/codex-prod0-tenant-reconcile/tests/test_app_cli.py`
- Modify: `/root/work/OP_Linux/.worktrees/codex-prod0-tenant-reconcile/tests/test_prod0_audit.py`
- Test: `/root/work/OP_Linux/.worktrees/codex-prod0-tenant-reconcile/tests/test_app_cli.py`
- Test: `/root/work/OP_Linux/.worktrees/codex-prod0-tenant-reconcile/tests/test_prod0_audit.py`

- [ ] **Step 1: Update the failing doc/inventory assertions**

Change tests so they require:

- `app-resources.json` describes Redis DB logical partition live state instead of `remediation-target`
- `app_resources.md` and generated README explicitly say shared runtime password, DB partition, and “not strong isolation”
- `app_resource_summary.redis.user` is either absent or clearly non-runtime / historical

```python
self.assertIn("逻辑分区", ledger_md)
self.assertIn("共享 runtime 凭据", server_readme_text)
self.assertNotIn("remediation target", server_readme_text)
```

- [ ] **Step 2: Implement the minimal doc-sync and inventory wording changes**

Update `ops/cli/apps.py` and tracked prod0 inventory files so generated output matches the new live-state semantics and no longer implies per-app Redis users are active runtime dependencies.

- [ ] **Step 3: Refresh tracked prod0 ledgers and generated README**

Use the updated code path and/or direct tracked edits so these files are coherent together:

- `app-resources.json`
- `app_resources.md`
- `inventory.json`
- `README.md`

- [ ] **Step 4: Run focused app/audit tests**

Run:

```bash
wsl.exe -u root -e bash -lc 'cd /root/work/OP_Linux/.worktrees/codex-prod0-tenant-reconcile && uv run pytest tests/test_app_cli.py tests/test_prod0_audit.py -q'
```

Expected:

- App doc generation and prod0 audit tests pass with live DB-partition wording.

- [ ] **Step 5: Commit the ledger and doc changes**

```bash
wsl.exe -u root -e bash -lc 'cd /root/work/OP_Linux/.worktrees/codex-prod0-tenant-reconcile && git add ops/cli/apps.py inventory/servers/prod0-main tests/test_app_cli.py tests/test_prod0_audit.py && git commit -m "fix: mark prod0 redis ledgers as db partitions"'
```

### Task 4: Re-render prod0 Runtime Env, Verify Apps, Then Remove Unused ACL Users

**Files:**
- Use: `/root/work/OP_Linux/secrets/services/redis/admin.prod0.conf`
- Use: `/root/work/OP_Linux/secrets/app-resources/prod0-main/newapi/redis.env`
- Use: `/root/work/OP_Linux/secrets/app-resources/prod0-main/sub2api/redis.env`
- Use: `/root/work/OP_Linux/secrets/services/newapi.prod0.env`
- Use: `/root/work/OP_Linux/secrets/services/sub2api.prod0.env`
- Verify remote: `/opt/env_ubuntu/secrets/services/newapi.prod0.env`
- Verify remote: `/opt/env_ubuntu/secrets/services/sub2api.prod0.env`
- Verify remote runtime: `newapi-prod`, `sub2api-prod`, `redis7-prod`

- [ ] **Step 1: Back up the current prod0 runtime env and ACL state**

Before any cutover, snapshot:

- `/opt/env_ubuntu/secrets/services/newapi.prod0.env`
- `/opt/env_ubuntu/secrets/services/sub2api.prod0.env`
- `docker exec redis7-prod redis-cli -a <default-pass> ACL LIST`

Store enough state to restore both app env files and any ACL users if verification fails.

- [ ] **Step 2: Run Redis preflight checks before re-rendering**

Verify live Redis still satisfies the plan assumptions:

- `CONFIG GET databases` returns at least the DB indexes used by `newapi` and `sub2api`
- `INFO cluster` reports `cluster_enabled:0`
- target app DB values in `app-resources.json` are within the configured DB count

```bash
wsl.exe -u root -e bash -lc 'ssh -F /root/work/OP_Linux/secrets/ssh/config prod0-main "docker exec redis7-prod redis-cli -a \"$(awk '\''/^requirepass /{print \$2}'\'' /opt/env_ubuntu/secrets/services/redis/admin.prod0.conf)\" --no-auth-warning CONFIG GET databases && docker exec redis7-prod redis-cli -a \"$(awk '\''/^requirepass /{print \$2}'\'' /opt/env_ubuntu/secrets/services/redis/admin.prod0.conf)\" --no-auth-warning INFO cluster | sed -n '\''1,20p'\''"'
```

Expected:

- `databases` is high enough for the tracked app DBs
- `cluster_enabled:0`

- [ ] **Step 3: Re-render and sync the prod0 service env files from the updated CLI**

Run:

```bash
wsl.exe -u root -e bash -lc 'cd /root/work/OP_Linux/.worktrees/codex-prod0-tenant-reconcile && uv run python -m ops.cli projection runtime-env apply --repo-root /root/work/OP_Linux --target prod0-main --app newapi --write && uv run python -m ops.cli projection runtime-env apply --repo-root /root/work/OP_Linux --target prod0-main --app sub2api --write'
```

This explicit `--repo-root /root/work/OP_Linux` is required so the rendered files land in the canonical secrets tree, not in the worktree shadow path.

Then copy the rendered files to `prod0-main` and preserve `600` permissions.

- [ ] **Step 4: Recreate newapi and sub2api one at a time**

Run controlled compose recreates:

```bash
wsl.exe -u root -e bash -lc 'ssh -F /root/work/OP_Linux/secrets/ssh/config prod0-main "cd /opt/env_ubuntu/infra/compose/newapi && docker compose -f docker-compose.prod0.yml up -d --force-recreate newapi"'
wsl.exe -u root -e bash -lc 'ssh -F /root/work/OP_Linux/secrets/ssh/config prod0-main "cd /opt/env_ubuntu/infra/compose/sub2api && docker compose -f docker-compose.prod0.yml up -d --force-recreate sub2api"'
```

- [ ] **Step 5: Verify the production runtime before touching ACL users**

Run:

```bash
wsl.exe -u root -e bash -lc 'ssh -F /root/work/OP_Linux/secrets/ssh/config prod0-main "REDIS_PASS=$(awk '\''/^requirepass /{print \$2}'\'' /opt/env_ubuntu/secrets/services/redis/admin.prod0.conf) && curl -fsS http://127.0.0.1:3000/api/status >/tmp/newapi.status && curl -fsS http://127.0.0.1:18080/health && docker logs --since 2m sub2api-prod 2>&1 | grep -n \"WRONGPASS\" || true && docker exec redis7-prod redis-cli -a \"$REDIS_PASS\" --no-auth-warning -n 1 PING"'
```

Expected:

- `newapi` health endpoint returns data
- `sub2api` health endpoint returns `{"status":"ok"}`
- recent `sub2api` logs contain no `WRONGPASS`
- Redis default password works on the expected DB

- [ ] **Step 6: Remove unused Redis ACL users and record final verification**

Only after Step 4 is clean, delete stale app ACL users that are no longer runtime dependencies, then verify:

- `ACL LIST` no longer contains removed users
- `newapi` and `sub2api` still stay healthy
- `tenant validate` and `tenant audit` pass from the updated worktree

```bash
wsl.exe -u root -e bash -lc 'cd /root/work/OP_Linux/.worktrees/codex-prod0-tenant-reconcile && uv run python -m ops.cli app resource verify --target prod0-main && uv run python -m ops.cli app resource verify --target prod0-main'
```

Commit:

```bash
wsl.exe -u root -e bash -lc 'cd /root/work/OP_Linux/.worktrees/codex-prod0-tenant-reconcile && git status --short'
```

If tracked files changed during the cutover, commit them with:

```bash
wsl.exe -u root -e bash -lc 'cd /root/work/OP_Linux/.worktrees/codex-prod0-tenant-reconcile && git add ops/cli inventory templates tests docs/superpowers/specs/2026-03-26-prod0-redis-db-isolation-design.md && git commit -m "fix: finalize prod0 redis db isolation rollout"'
```
