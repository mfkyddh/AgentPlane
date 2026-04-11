# Prod0 Tenant Remediation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 `prod0-main` 上 PostgreSQL、Redis、MinIO 的管理员级 secrets、应用租户级 secrets、运行时投影和 `inventory` 台账统一到已批准的租户隔离规范，并在验证通过后删除被新结构替代的旧扁平 secret 文件。

**Architecture:** 实施分四段推进。第一段先锁定测试和账本行为，避免继续把目标状态误写成现状。第二段把管理员真源与租户真源补齐到仓库和远端正式目录，并在生产机创建缺失的 PG/Redis/MinIO 租户资源。第三段切换 `newapi`、`sub2api` 运行时投影到新租户口径并逐项验证。第四段删除旧扁平 secret 和旧引用，完成最终审计。

**Tech Stack:** Python (`uv` + `pytest`), Bash, SSH, Docker, PostgreSQL 18, Redis 7 ACL, MinIO, OP_Linux `ops.cli`

---

### Task 1: Lock Repository Expectations Before Touching Production

**Files:**
- Modify: `/root/work/OP_Linux/.worktrees/codex-prod0-tenant-reconcile/tests/test_secrets_cli.py`
- Modify: `/root/work/OP_Linux/.worktrees/codex-prod0-tenant-reconcile/tests/test_prod0_postgres_app_resource_audit.py`
- Modify: `/root/work/OP_Linux/.worktrees/codex-prod0-tenant-reconcile/tests/test_prod0_audit.py`
- Modify: `/root/work/OP_Linux/.worktrees/codex-prod0-tenant-reconcile/ops/cli/audit.py` (only if tests expose a real audit gap)
- Modify: `/root/work/OP_Linux/.worktrees/codex-prod0-tenant-reconcile/ops/cli/prod0_postgres_app_resource_audit.py` (only if tests expose a real validation gap)
- Test: `/root/work/OP_Linux/.worktrees/codex-prod0-tenant-reconcile/tests/test_secrets_cli.py`
- Test: `/root/work/OP_Linux/.worktrees/codex-prod0-tenant-reconcile/tests/test_prod0_postgres_app_resource_audit.py`
- Test: `/root/work/OP_Linux/.worktrees/codex-prod0-tenant-reconcile/tests/test_prod0_audit.py`

- [ ] **Step 1: Write the failing tests for the approved prod0 secret layout and live-state drift checks**

Add or update tests so they explicitly require:

- target-scoped admin secret paths under `secrets/services/postgres/`, `secrets/services/redis/`, `secrets/services/minio/`
- tenant registry entries for `newapi` and `sub2api` to be complete and internally consistent
- `inventory.json` to contain exactly one `app_resource_summary` block per formal app
- filesystem audit output to detect legacy flat-file drift when formal prod0 files are still mounted or referenced

- [ ] **Step 2: Run the focused test set and confirm the new assertions fail for the expected reasons**

Run:

```bash
wsl.exe -u root -e bash -lc 'cd /root/work/OP_Linux/.worktrees/codex-prod0-tenant-reconcile && uv run pytest tests/test_secrets_cli.py tests/test_prod0_postgres_app_resource_audit.py tests/test_prod0_audit.py -q'
```

Expected:

- At least one new assertion fails because the repository still tolerates current drift.
- Failures must point to the newly introduced expectations, not unrelated baseline breakage.

- [ ] **Step 3: Implement the minimal audit/validation changes only if the new tests reveal missing enforcement**

If the new tests fail because `ops.cli audit` or `ops.cli tenant` does not yet enforce an approved rule, update only the smallest necessary paths in `ops/cli/audit.py` or `ops/cli/prod0_postgres_app_resource_audit.py`.

- [ ] **Step 4: Re-run the focused test set to verify the repository rules are locked**

Run:

```bash
wsl.exe -u root -e bash -lc 'cd /root/work/OP_Linux/.worktrees/codex-prod0-tenant-reconcile && uv run pytest tests/test_secrets_cli.py tests/test_prod0_postgres_app_resource_audit.py tests/test_prod0_audit.py -q'
```

Expected:

- All focused tests pass.

- [ ] **Step 5: Commit the rule lock before production-facing changes**

```bash
wsl.exe -u root -e bash -lc 'cd /root/work/OP_Linux/.worktrees/codex-prod0-tenant-reconcile && git add tests/test_secrets_cli.py tests/test_prod0_postgres_app_resource_audit.py tests/test_prod0_audit.py ops/cli/audit.py ops/cli/prod0_postgres_app_resource_audit.py && git commit -m "test: lock prod0 tenant remediation rules"'
```

### Task 2: Normalize the Repository Secret and Ledger Layout

**Files:**
- Create: `/root/work/OP_Linux/.worktrees/codex-prod0-tenant-reconcile/templates/services/postgres/admin.env.example`
- Create: `/root/work/OP_Linux/.worktrees/codex-prod0-tenant-reconcile/templates/services/redis/admin.env.example`
- Create: `/root/work/OP_Linux/.worktrees/codex-prod0-tenant-reconcile/templates/services/minio/admin.env.example`
- Modify: `/root/work/OP_Linux/.worktrees/codex-prod0-tenant-reconcile/templates/services/postgres.env.example`
- Modify: `/root/work/OP_Linux/.worktrees/codex-prod0-tenant-reconcile/templates/services/redis.conf.example`
- Modify: `/root/work/OP_Linux/.worktrees/codex-prod0-tenant-reconcile/templates/services/minio.env.example`
- Modify: `/root/work/OP_Linux/.worktrees/codex-prod0-tenant-reconcile/inventory/servers/prod0-main/app-resources.json`
- Modify: `/root/work/OP_Linux/.worktrees/codex-prod0-tenant-reconcile/inventory/servers/prod0-main/app_resources.md`
- Modify: `/root/work/OP_Linux/.worktrees/codex-prod0-tenant-reconcile/inventory/servers/prod0-main/inventory.json`
- Modify: `/root/work/OP_Linux/.worktrees/codex-prod0-tenant-reconcile/inventory/servers/prod0-main/README.md`
- Test: `/root/work/OP_Linux/.worktrees/codex-prod0-tenant-reconcile/tests/test_secrets_cli.py`
- Test: `/root/work/OP_Linux/.worktrees/codex-prod0-tenant-reconcile/tests/test_prod0_audit.py`

- [ ] **Step 1: Write the failing assertions for canonical admin templates and non-duplicated tenant ledgers**

Extend or add tests so they require:

- new admin template files to exist
- old flat templates to be marked as legacy or projection-only rather than canonical admin sources
- `inventory/servers/prod0-main/inventory.json` to serialize a single `app_resource_summary` block per app

- [ ] **Step 2: Run the focused tests and confirm they fail before changing tracked files**

Run:

```bash
wsl.exe -u root -e bash -lc 'cd /root/work/OP_Linux/.worktrees/codex-prod0-tenant-reconcile && uv run pytest tests/test_secrets_cli.py tests/test_prod0_audit.py -q'
```

Expected:

- Tests fail because admin templates are missing and current ledgers still contain drift.

- [ ] **Step 3: Update the tracked templates and ledgers to reflect the approved structure**

Make the repository express the intended structure clearly:

- add `templates/services/*/admin.env.example` files
- keep legacy flat templates only when still needed for migration context, and document them as transitional
- fix `inventory.json` duplicate `app_resource_summary` blocks
- update `app-resources.json` and `app_resources.md` so they describe the remediation target without silently implying that already-missing secrets exist locally

- [ ] **Step 4: Re-run the focused tests to verify the tracked layout is coherent**

Run:

```bash
wsl.exe -u root -e bash -lc 'cd /root/work/OP_Linux/.worktrees/codex-prod0-tenant-reconcile && uv run pytest tests/test_secrets_cli.py tests/test_prod0_audit.py -q'
```

Expected:

- The template and ledger expectations pass.

- [ ] **Step 5: Commit the tracked-layout cleanup**

```bash
wsl.exe -u root -e bash -lc 'cd /root/work/OP_Linux/.worktrees/codex-prod0-tenant-reconcile && git add templates/services inventory/servers/prod0-main tests/test_secrets_cli.py tests/test_prod0_audit.py && git commit -m "feat: normalize prod0 tenant secret ledger layout"'
```

### Task 3: Capture Canonical Admin Secrets and Prepare Tenant Secret Sources

**Files:**
- Create: `/root/work/OP_Linux/secrets/services/postgres/admin.prod0.env`
- Create: `/root/work/OP_Linux/secrets/services/redis/admin.prod0.conf`
- Create: `/root/work/OP_Linux/secrets/services/minio/admin.prod0.env`
- Create: `/root/work/OP_Linux/secrets/app-resources/prod0-main/newapi/minio.env`
- Create: `/root/work/OP_Linux/secrets/app-resources/prod0-main/sub2api/postgres.env`
- Create: `/root/work/OP_Linux/secrets/app-resources/prod0-main/sub2api/redis.env`
- Create: `/root/work/OP_Linux/secrets/app-resources/prod0-main/sub2api/minio.env`
- Modify: `/root/work/OP_Linux/secrets/app-resources/prod0-main/newapi/postgres.env`
- Modify: `/root/work/OP_Linux/secrets/app-resources/prod0-main/newapi/redis.env`
- Verify remote: `/opt/env_ubuntu/secrets/services/postgres/admin.prod0.env`
- Verify remote: `/opt/env_ubuntu/secrets/services/redis/admin.prod0.conf`
- Verify remote: `/opt/env_ubuntu/secrets/services/minio/admin.prod0.env`
- Verify remote: `/opt/env_ubuntu/secrets/app-resources/prod0-main/newapi/*.env`
- Verify remote: `/opt/env_ubuntu/secrets/app-resources/prod0-main/sub2api/*.env`

- [ ] **Step 1: Snapshot the current live credentials from prod0-main into a temporary operator note**

Run read-only probes to capture the current PG admin login, Redis default password, MinIO root credentials, and the already-existing `newapi` tenant values before writing any new local files.

- [ ] **Step 2: Write canonical local admin secret files using the current live values**

Create:

- `secrets/services/postgres/admin.prod0.env`
- `secrets/services/redis/admin.prod0.conf`
- `secrets/services/minio/admin.prod0.env`

using the credentials that are already live on `prod0-main`. Do not rotate passwords in this task.

- [ ] **Step 3: Prepare the tenant secret sources for remediation**

Write or update:

- `secrets/app-resources/prod0-main/newapi/postgres.env`
- `secrets/app-resources/prod0-main/newapi/redis.env`
- `secrets/app-resources/prod0-main/newapi/minio.env`
- `secrets/app-resources/prod0-main/sub2api/postgres.env`
- `secrets/app-resources/prod0-main/sub2api/redis.env`
- `secrets/app-resources/prod0-main/sub2api/minio.env`

with real values only after the corresponding resources are confirmed to exist. For `sub2api`, do not invent credentials; wait until Task 4 creates them on the host.

- [ ] **Step 4: Sync the canonical files to the formal prod0 remote secret directories**

Copy the canonical local files to `/opt/env_ubuntu/secrets/services/...` and `/opt/env_ubuntu/secrets/app-resources/prod0-main/...`, preserving `600` permissions.

- [ ] **Step 5: Verify the remote secret file set matches the local canonical set**

Run:

```bash
wsl.exe -u root -e bash -lc 'ssh -F /root/work/OP_Linux/secrets/ssh/config prod0-main "find /opt/env_ubuntu/secrets/services /opt/env_ubuntu/secrets/app-resources/prod0-main -maxdepth 3 -type f | sort"'
```

Expected:

- The new admin files exist remotely.
- `newapi` and `sub2api` tenant secret files exist only after their values are real.

### Task 4: Create or Correct Tenant Resources on prod0-main

**Files:**
- Use: `/root/work/OP_Linux/secrets/services/postgres/admin.prod0.env`
- Use: `/root/work/OP_Linux/secrets/services/redis/admin.prod0.conf`
- Use: `/root/work/OP_Linux/secrets/services/minio/admin.prod0.env`
- Use: `/root/work/OP_Linux/secrets/app-resources/prod0-main/newapi/minio.env`
- Use: `/root/work/OP_Linux/secrets/app-resources/prod0-main/sub2api/postgres.env`
- Use: `/root/work/OP_Linux/secrets/app-resources/prod0-main/sub2api/redis.env`
- Use: `/root/work/OP_Linux/secrets/app-resources/prod0-main/sub2api/minio.env`
- Verify remote runtime: `postgres18-prod`, `redis7-prod`, `minio-prod`

- [ ] **Step 1: Write the operator verification checklist for the missing prod0 tenant resources**

List the exact target resources that must exist before cutover:

- PostgreSQL role/database `sub2api_prod0`
- Redis ACL user/password/prefix for `sub2api_prod0`
- MinIO bucket and credentials for `newapi_prod0`
- MinIO bucket and credentials for `sub2api_prod0`

- [ ] **Step 2: Create or reconcile PostgreSQL tenant resources**

Run controlled `psql` commands against `postgres18-prod` to:

- keep current admin login unchanged
- create `sub2api_prod0` role if missing
- create `sub2api_prod0` database if missing
- grant only the required ownership/privileges

Do not rename or remove the legacy `app` role in this task.

- [ ] **Step 3: Create or reconcile Redis tenant resources**

Run controlled `redis-cli` ACL commands against `redis7-prod` to:

- create `sub2api_prod0` ACL user with its own password
- keep `newapi_prod0` aligned with the canonical tenant secret
- verify `default` remains available only until cutover completes

- [ ] **Step 4: Create or reconcile MinIO tenant resources**

Use `mc` or an equivalent admin flow against `minio-prod` to:

- create `prod0-newapi` and `prod0-sub2api` buckets if missing
- create dedicated access key / secret key pairs for `newapi_prod0` and `sub2api_prod0`
- record the real values into the corresponding tenant secret files

- [ ] **Step 5: Verify the new tenant resources exist before touching app runtime projections**

Run:

```bash
wsl.exe -u root -e bash -lc 'ssh -F /root/work/OP_Linux/secrets/ssh/config prod0-main "docker exec -e PGPASSWORD=$(awk -F= '\''/^POSTGRES_PASSWORD=/{print \$2}'\'' /opt/env_ubuntu/secrets/services/postgres/admin.prod0.env) postgres18-prod psql -U $(awk -F= '\''/^POSTGRES_USER=/{print \$2}'\'' /opt/env_ubuntu/secrets/services/postgres/admin.prod0.env) -d $(awk -F= '\''/^POSTGRES_DB=/{print \$2}'\'' /opt/env_ubuntu/secrets/services/postgres/admin.prod0.env) -At -c \"SELECT rolname FROM pg_roles WHERE rolname IN ('\''sub2api_prod0'\'','\''newapi_prod0'\'') ORDER BY rolname;\""' 
```

and equivalent Redis/MinIO checks.

Expected:

- The required PG roles/databases exist.
- Redis ACL users exist for both apps.
- MinIO buckets and non-root app credentials exist for both apps.

### Task 5: Render and Cut Over Runtime Projection Files

**Files:**
- Modify: `/root/work/OP_Linux/secrets/services/newapi.prod0.env`
- Modify: `/root/work/OP_Linux/secrets/services/sub2api.prod0.env`
- Modify: `/root/work/OP_Linux/.worktrees/codex-prod0-tenant-reconcile/inventory/servers/prod0-main/app-resources.json`
- Modify: `/root/work/OP_Linux/.worktrees/codex-prod0-tenant-reconcile/inventory/servers/prod0-main/app_resources.md`
- Modify: `/root/work/OP_Linux/.worktrees/codex-prod0-tenant-reconcile/inventory/servers/prod0-main/inventory.json`
- Verify remote: `/opt/env_ubuntu/secrets/services/newapi.prod0.env`
- Verify remote: `/opt/env_ubuntu/secrets/services/sub2api.prod0.env`

- [ ] **Step 1: Write failing assertions for rendered prod0 service projections**

Add or update tests so `tenant render-env --target prod0-main --app newapi --write` and the corresponding `sub2api` command must emit service env files that exactly consume the tenant secret sources.

- [ ] **Step 2: Run the focused projection tests and confirm they fail before rendering**

Run:

```bash
wsl.exe -u root -e bash -lc 'cd /root/work/OP_Linux/.worktrees/codex-prod0-tenant-reconcile && uv run pytest tests/test_prod0_postgres_app_resource_audit.py tests/test_app_cli.py -q -k "render_env or tenant"'
```

Expected:

- At least one assertion fails because the current projection inputs are incomplete or stale.

- [ ] **Step 3: Render the prod0 runtime projections from tenant secrets and sync them to the host**

Run:

```bash
wsl.exe -u root -e bash -lc 'cd /root/work/OP_Linux && uv run python -m ops.cli projection runtime-env apply --target prod0-main --app newapi --write'
wsl.exe -u root -e bash -lc 'cd /root/work/OP_Linux && uv run python -m ops.cli projection runtime-env apply --target prod0-main --app sub2api --write'
```

Then copy the resulting `secrets/services/newapi.prod0.env` and `secrets/services/sub2api.prod0.env` to `/opt/env_ubuntu/secrets/services/`.

- [ ] **Step 4: Restart the affected applications one at a time and verify health**

Restart `newapi-prod` first, then `sub2api-prod`, validating after each restart that:

- container status is healthy
- app login / key endpoints still work
- PG/Redis connectivity uses the new tenant credentials

- [ ] **Step 5: Update ledgers to match the cutover state**

After both services run on tenant credentials, update:

- `app-resources.json`
- `app_resources.md`
- `inventory.json`

so they describe the real live state, not a mix of live state and future intent.

- [ ] **Step 6: Commit the tenant cutover state**

```bash
wsl.exe -u root -e bash -lc 'cd /root/work/OP_Linux/.worktrees/codex-prod0-tenant-reconcile && git add inventory/servers/prod0-main tests/test_prod0_postgres_app_resource_audit.py tests/test_app_cli.py && git commit -m "feat: cut prod0 apps to isolated tenant secrets"'
```

### Task 6: Remove Replaced Flat Secrets and Finalize Verification

**Files:**
- Delete: `/root/work/OP_Linux/secrets/services/postgres.env`
- Delete: `/root/work/OP_Linux/secrets/services/redis.conf`
- Delete: `/root/work/OP_Linux/secrets/services/minio.env`
- Delete remote: `/opt/env_ubuntu/secrets/services/postgres.env`
- Delete remote: `/opt/env_ubuntu/secrets/services/redis.conf`
- Delete remote: `/opt/env_ubuntu/secrets/services/minio.env`
- Modify: `/root/work/OP_Linux/.worktrees/codex-prod0-tenant-reconcile/docs/runbooks/bootstrap-secrets.md`
- Modify: `/root/work/OP_Linux/.worktrees/codex-prod0-tenant-reconcile/infra/compose/postgres/README.md`
- Modify: `/root/work/OP_Linux/.worktrees/codex-prod0-tenant-reconcile/infra/compose/redis/README.md`
- Modify: `/root/work/OP_Linux/.worktrees/codex-prod0-tenant-reconcile/infra/compose/minio/README.md`
- Test: `/root/work/OP_Linux/.worktrees/codex-prod0-tenant-reconcile/tests/test_secrets_cli.py`
- Test: `/root/work/OP_Linux/.worktrees/codex-prod0-tenant-reconcile/tests/test_prod0_postgres_app_resource_audit.py`
- Test: `/root/work/OP_Linux/.worktrees/codex-prod0-tenant-reconcile/tests/test_prod0_audit.py`

- [ ] **Step 1: Verify there are no remaining production references to the old flat files**

Run repository grep plus remote host grep to ensure:

- no compose file
- no deploy script
- no runtime projection
- no remote mounted container

still references `secrets/services/postgres.env`, `secrets/services/redis.conf`, or `secrets/services/minio.env` as the active prod0 source.

- [ ] **Step 2: Delete the replaced local and remote flat files**

Delete the old files only after Step 1 passes:

- local canonical flat files under `/root/work/OP_Linux/secrets/services/`
- remote prod0 flat files under `/opt/env_ubuntu/secrets/services/`

- [ ] **Step 3: Update runbooks and compose READMEs so the old flat files are no longer documented as current**

Refresh `bootstrap-secrets.md` and the data-service READMEs so they point only at the target-scoped admin files and tenant secret workflow.

- [ ] **Step 4: Run the final verification suite**

Run:

```bash
wsl.exe -u root -e bash -lc 'cd /root/work/OP_Linux/.worktrees/codex-prod0-tenant-reconcile && uv run pytest tests/test_secrets_cli.py tests/test_prod0_postgres_app_resource_audit.py tests/test_prod0_audit.py -q'
wsl.exe -u root -e bash -lc 'cd /root/work/OP_Linux/.worktrees/codex-prod0-tenant-reconcile && uv run python -m ops.cli app resource verify --target prod0-main'
wsl.exe -u root -e bash -lc 'cd /root/work/OP_Linux/.worktrees/codex-prod0-tenant-reconcile && uv run python -m ops.cli app resource verify --target prod0-main'
```

Expected:

- Focused tests pass.
- `tenant validate --target prod0-main` returns `ok: true`.
- `tenant audit --target prod0-main` reports no missing prod0 tenant secret files.

- [ ] **Step 5: Commit the cleanup and final documentation state**

```bash
wsl.exe -u root -e bash -lc 'cd /root/work/OP_Linux/.worktrees/codex-prod0-tenant-reconcile && git add docs/runbooks/bootstrap-secrets.md infra/compose/postgres/README.md infra/compose/redis/README.md infra/compose/minio/README.md tests/test_secrets_cli.py tests/test_prod0_postgres_app_resource_audit.py tests/test_prod0_audit.py && git add -u /root/work/OP_Linux/secrets/services && git commit -m "feat: finalize prod0 tenant secret migration"'
```
