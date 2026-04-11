# Prod0 PostgreSQL Tenant Optimization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 `prod0-main` 的 PostgreSQL 多租户治理补齐到可审计状态，使 `newapi`、`sub2api`、`sub2apipay` 三个正式应用都进入正式 tenant 台账并受同等 PostgreSQL 约束，同时完成管理员入口从 `app/app` 切换到 `postgres` 管理员口径，并提供 runtime/live state 对账能力。

**Architecture:** 这次实施分成两条主线。第一条是仓库侧，把 tracked tenant ledger、inventory、CLI 校验和审计测试补齐，让控制面先能正确描述三应用状态。第二条是生产侧，使用 `ops/scripts/remote/run_remote_bash.sh` 执行可回滚的远端 Bash 脚本，完成 `sub2apipay` 脱离历史 `app` 入口、管理员入口切换和 live audit 验证。当前仓库没有 `sub2apipay` 的 `deploy/op/contract.yaml`，因此本计划不强行把它接进 `app inventory-refresh` 合同链路，而是先通过 tracked inventory 和 tenant CLI 收口。

**Tech Stack:** Python 3.12+, `uv`, `pytest`, OP_Linux CLI, JSON inventory, Bash, SSH, PostgreSQL 18, Docker, `psql`

---

## File Map

- Modify: `inventory/servers/prod0-main/app-resources.json`
- Modify: `inventory/servers/prod0-main/app_resources.md`
- Modify: `inventory/servers/prod0-main/inventory.json`
- Modify: `inventory/servers/prod0-main/README.md`
- Modify: `ops/cli/prod0_postgres_app_resource_audit.py`
- Modify: `tests/test_prod0_postgres_app_resource_audit.py`
- Modify: `tests/test_prod0_audit.py`
- Create: `ops/scripts/remote/prod0-postgres-app-resource-live-audit.sh`
- Create: `ops/scripts/remote/prod0-postgres-app-resource-cutover.sh`
- Create: `docs/runbooks/prod0-postgres-app-resource-ops.md`

### Task 1: Formalize `sub2apipay` In The Tracked Prod0 Tenant Ledger

**Files:**
- Modify: `tests/test_prod0_audit.py`
- Modify: `inventory/servers/prod0-main/app-resources.json`
- Modify: `inventory/servers/prod0-main/app_resources.md`
- Modify: `inventory/servers/prod0-main/inventory.json`
- Modify: `inventory/servers/prod0-main/README.md`

- [ ] **Step 1: Write the failing prod0 audit expectations for a third formal PostgreSQL tenant**

Add the tracked-fixture coverage first in `tests/test_prod0_audit.py`:

```python
def baseline_tenant_registry() -> dict:
    payload = {
        "sub2api": {
            "owner_app": "sub2api",
            "ledger_status": {
                "intent": "live-db-partition-ledger",
                "runtime_credential_model": "shared-runtime-credentials",
                "tenant_isolation": "logical-db-partition-not-strong-isolation",
                "local_secret_presence": "not-materialized-by-repo",
            },
            "postgres": {"database": "sub2api_prod0", "user": "sub2api_prod0"},
            "redis": {"db": 1, "key_prefix": "sub2api:"},
            "minio": {"bucket": "prod0-sub2api", "access_key": "sub2api_prod0"},
            "secret_files": [
                "secrets/app-resources/prod0-main/sub2api/postgres.env",
                "secrets/app-resources/prod0-main/sub2api/redis.env",
                "secrets/app-resources/prod0-main/sub2api/minio.env",
            ],
        },
        "newapi": {
            "owner_app": "newapi",
            "ledger_status": {
                "intent": "live-db-partition-ledger",
                "runtime_credential_model": "shared-runtime-credentials",
                "tenant_isolation": "logical-db-partition-not-strong-isolation",
                "local_secret_presence": "not-materialized-by-repo",
            },
            "postgres": {"database": "newapi_prod0", "user": "newapi_prod0"},
            "redis": {"db": 2, "key_prefix": "newapi:"},
            "minio": {"bucket": "prod0-newapi", "access_key": "newapi_prod0"},
            "secret_files": [
                "secrets/app-resources/prod0-main/newapi/postgres.env",
                "secrets/app-resources/prod0-main/newapi/redis.env",
                "secrets/app-resources/prod0-main/newapi/minio.env",
            ],
        },
    }
    payload["sub2apipay"] = {
        "owner_app": "sub2apipay",
        "ledger_status": {
            "intent": "live-db-partition-ledger",
            "runtime_credential_model": "dedicated-runtime-credentials",
            "tenant_isolation": "dedicated-db-user-per-app",
            "local_secret_presence": "not-materialized-by-repo",
        },
        "postgres": {"database": "sub2apipay", "user": "sub2apipay_prod0"},
        "secret_files": [
            "secrets/app-resources/prod0-main/sub2apipay/postgres.env",
        ],
    }
    return payload

payload = baseline_payload(include_app_resource_summary=include_app_resource_summary)
payload["services"]["sub2apipay"] = {
    "control_plane": "1panel-compose",
    "container_name": "sub2apipay-prod",
    "depends_on_containers": ["postgres18-prod"],
    "runtime_root": "/data/sub2apipay/app/current",
    "config_files": [
        "/data/sub2apipay/config/sub2apipay-prod.env",
        "/data/sub2apipay/config/.env.runtime",
    ],
}
if include_app_resource_summary:
    payload["services"]["sub2apipay"]["app_resource_summary"] = {
        "postgres": {
            "database": "sub2apipay",
            "user": "sub2apipay_prod0",
            "secret_file": "secrets/app-resources/prod0-main/sub2apipay/postgres.env",
        }
    }
```

Also update the tracked-file assertions so the loops cover all three formal apps for PostgreSQL:

```python
for app in ("sub2api", "newapi", "sub2apipay"):
    summary = inventory_payload["services"][app]["app_resource_summary"]["postgres"]
    self.assertIsInstance(summary, dict)
    self.assertIn("database", summary)
    self.assertIn("user", summary)
    self.assertIn("secret_file", summary)
```

- [ ] **Step 2: Run the prod0 audit tests to confirm the current tracked files fail**

Run:

```bash
wsl.exe -u root -e bash -lc 'cd /root/work/OP_Linux/.worktrees/codex-prod0-pg-tenant-optimization && uv run pytest tests/test_prod0_audit.py -q'
```

Expected:

- FAIL because tracked `app-resources.json` and `inventory.json` do not yet contain `sub2apipay` tenant metadata.

- [ ] **Step 3: Update the tracked tenant ledger and inventory to match the approved design**

Apply the tracked data changes:

```json
{
  "sub2apipay": {
    "owner_app": "sub2apipay",
    "ledger_status": {
      "intent": "live-db-partition-ledger",
      "runtime_credential_model": "dedicated-runtime-credentials",
      "tenant_isolation": "dedicated-db-user-per-app",
      "local_secret_presence": "not-materialized-by-repo"
    },
    "postgres": {
      "database": "sub2apipay",
      "user": "sub2apipay_prod0"
    },
    "secret_files": [
      "secrets/app-resources/prod0-main/sub2apipay/postgres.env"
    ]
  }
}
```

And add the matching inventory summary:

```json
"sub2apipay": {
  "control_plane": "1panel-compose",
  "container_name": "sub2apipay-prod",
  "depends_on_containers": ["postgres18-prod"],
  "runtime_root": "/data/sub2apipay/app/current",
  "config_files": [
    "/data/sub2apipay/config/sub2apipay-prod.env",
    "/data/sub2apipay/config/.env.runtime"
  ],
  "app_resource_summary": {
    "postgres": {
      "database": "sub2apipay",
      "user": "sub2apipay_prod0",
      "secret_file": "secrets/app-resources/prod0-main/sub2apipay/postgres.env"
    }
  }
}
```

The prose files must describe the third PostgreSQL tenant explicitly:

```md
- `sub2apipay`
  - PostgreSQL: `sub2apipay` / `sub2apipay_prod0`
  - Secret files: `secrets/app-resources/prod0-main/sub2apipay/postgres.env`
```

- [ ] **Step 4: Re-run the prod0 audit tests and filesystem audit**

Run:

```bash
wsl.exe -u root -e bash -lc 'cd /root/work/OP_Linux/.worktrees/codex-prod0-pg-tenant-optimization && uv run pytest tests/test_prod0_audit.py -q && uv run python -m ops.cli audit filesystem --env prod0-main --repo-root /root/work/OP_Linux/.worktrees/codex-prod0-pg-tenant-optimization'
```

Expected:

- `tests/test_prod0_audit.py` PASS.
- The CLI audit JSON contains no `prod0.tenant.registry_missing`, `prod0.tenant.summary_missing`, or `prod0.tenant.drift` violations for tracked files.

- [ ] **Step 5: Commit the tracked tenant-ledger changes**

Run:

```bash
wsl.exe -u root -e bash -lc 'cd /root/work/OP_Linux/.worktrees/codex-prod0-pg-tenant-optimization && git add tests/test_prod0_audit.py inventory/servers/prod0-main/app-resources.json inventory/servers/prod0-main/app_resources.md inventory/servers/prod0-main/inventory.json inventory/servers/prod0-main/README.md && git commit -m "feat: formalize sub2apipay prod0 postgres tenant ledger"'
```

Expected:

- A commit exists containing only the tracked ledger and audit-fixture updates.

### Task 2: Extend Tenant Validation So `sub2apipay` Is Formal But PostgreSQL-Only

**Files:**
- Modify: `ops/cli/prod0_postgres_app_resource_audit.py`
- Modify: `tests/test_prod0_postgres_app_resource_audit.py`

- [ ] **Step 1: Write the failing tenant validation tests for `sub2apipay`**

Add two focused tests in `tests/test_prod0_postgres_app_resource_audit.py`:

```python
def test_tenant_validate_requires_sub2apipay_prod0_postgres_entry(self) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        write_inventory(root)
        payload = baseline_registry()
        write_registry(root, payload)
        result = run_cli("tenant", "validate", "--target", "prod0-main", "--repo-root", str(root))
        self.assertNotEqual(0, result.returncode)
        combined = result.stdout + result.stderr
        self.assertIn("sub2apipay", combined)


def test_tenant_validate_allows_sub2apipay_without_redis_or_minio(self) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        write_inventory(root)
        payload = baseline_registry()
        payload["sub2apipay"] = {
            "owner_app": "sub2apipay",
            "postgres": {"database": "sub2apipay", "user": "sub2apipay_prod0"},
            "secret_files": ["secrets/app-resources/prod0-main/sub2apipay/postgres.env"],
        }
        write_registry(root, payload)
        write_tenant_secret(root, "sub2apipay", "postgres.env", "PGDATABASE=sub2apipay\nPGUSER=sub2apipay_prod0\n")
        result = run_cli("tenant", "validate", "--target", "prod0-main", "--repo-root", str(root))
        self.assertEqual(0, result.returncode, msg=result.stderr)
```

- [ ] **Step 2: Run only the new tenant validation tests to verify they fail**

Run:

```bash
wsl.exe -u root -e bash -lc 'cd /root/work/OP_Linux/.worktrees/codex-prod0-pg-tenant-optimization && uv run pytest tests/test_prod0_postgres_app_resource_audit.py -q -k "sub2apipay and tenant_validate"'
```

Expected:

- FAIL because `ops/cli/prod0_postgres_app_resource_audit.py` currently hard-codes only `newapi` and `sub2api` as formal prod0 tenant apps.

- [ ] **Step 3: Replace the hard-coded formal-app loop with an explicit requirements map**

In `ops/cli/prod0_postgres_app_resource_audit.py`, replace the current `("newapi", "sub2api")` loop with a structured map so formal prod0 apps can require different tenant kinds:

```python
FORMAL_PROD0_TENANT_REQUIREMENTS = {
    "newapi": ("postgres", "redis", "minio"),
    "sub2api": ("postgres", "redis", "minio"),
    "sub2apipay": ("postgres",),
}


def _validate_formal_registry_entries(target: str, registry: dict[str, Any]) -> list[dict[str, Any]]:
    if target != "prod0-main":
        return []

    errors: list[dict[str, Any]] = []
    for app_id, required_kinds in FORMAL_PROD0_TENANT_REQUIREMENTS.items():
        raw_entry = registry.get(app_id)
        issues: list[str] = []
        if not isinstance(raw_entry, dict):
            issues.append("missing registry entry")
            errors.append(
                {
                    "id": "tenant.registry_entry_incomplete",
                    "app": app_id,
                    "issues": issues,
                    "message": "formal app tenant registry entry must be complete and internally consistent",
                }
            )
            continue

        owner_app = raw_entry.get("owner_app")
        if owner_app != app_id:
            issues.append(f"owner_app={owner_app!r} expected {app_id!r}")

        for kind in required_kinds:
            fields = TENANT_SUMMARY_FIELDS[kind]
            spec = raw_entry.get(kind)
            if not isinstance(spec, dict):
                issues.append(f"{kind} missing")
                continue
            for field in fields:
                value = spec.get(field)
                if value is None or value == "":
                    issues.append(f"{kind}.{field} missing")
            expected_secret_file = f"secrets/app-resources/{target}/{app_id}/{kind}.env"
            actual_secret_file = registry_secret_file(raw_entry, kind)
            if actual_secret_file != expected_secret_file:
                issues.append(f"{kind}.secret_file={actual_secret_file!r} expected {expected_secret_file!r}")
```

Keep the existing Redis canonical DB/key_prefix checks only inside the `kind == "redis"` branch.

- [ ] **Step 4: Re-run the targeted tenant validation tests and the full tenant CLI suite**

Run:

```bash
wsl.exe -u root -e bash -lc 'cd /root/work/OP_Linux/.worktrees/codex-prod0-pg-tenant-optimization && uv run pytest tests/test_prod0_postgres_app_resource_audit.py -q -k "tenant_validate or tenant_render_env"'
```

Expected:

- PASS, including the new `sub2apipay` validation tests.
- No regressions in `sub2api` / `newapi` render-env behavior.

- [ ] **Step 5: Commit the tenant validation refactor**

Run:

```bash
wsl.exe -u root -e bash -lc 'cd /root/work/OP_Linux/.worktrees/codex-prod0-pg-tenant-optimization && git add ops/cli/prod0_postgres_app_resource_audit.py tests/test_prod0_postgres_app_resource_audit.py && git commit -m "feat: validate sub2apipay as formal prod0 postgres tenant"'
```

Expected:

- A commit exists containing only the tenant validation and test updates.

### Task 3: Add Live Runtime And PostgreSQL State Audit For Prod0

**Files:**
- Modify: `ops/cli/prod0_postgres_app_resource_audit.py`
- Modify: `tests/test_prod0_postgres_app_resource_audit.py`
- Create: `ops/scripts/remote/prod0-postgres-app-resource-live-audit.sh`

- [ ] **Step 1: Write the failing tests for a new `tenant audit-live` command**

Add in `tests/test_prod0_postgres_app_resource_audit.py`:

```python
@mock.patch("ops.cli.tenant._prod0_live_audit_snapshot")
def test_tenant_audit_live_reports_runtime_and_catalog_drift(self, snapshot_mock: mock.Mock) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        write_inventory(root)
        payload = baseline_registry()
        payload["sub2apipay"] = {
            "owner_app": "sub2apipay",
            "postgres": {"database": "sub2apipay", "user": "sub2apipay_prod0"},
            "secret_files": ["secrets/app-resources/prod0-main/sub2apipay/postgres.env"],
        }
        write_registry(root, payload)
        write_tenant_secret(root, "sub2apipay", "postgres.env", "PGDATABASE=sub2apipay\nPGUSER=sub2apipay_prod0\n")
        snapshot_mock.return_value = {
            "apps": {
                "sub2apipay": {"database": "sub2apipay", "user": "app"},
            },
            "catalog": {
                "databases": {"sub2apipay": "app"},
                "roles": ["app", "postgres"],
            },
        }
        result = run_cli("tenant", "audit-live", "--target", "prod0-main", "--repo-root", str(root))
        self.assertEqual(0, result.returncode, msg=result.stderr)
        payload = json.loads(result.stdout)
        finding_ids = {item["id"] for item in payload["findings"]}
        self.assertIn("tenant.runtime_drift", finding_ids)
        self.assertIn("tenant.live_state_drift", finding_ids)
```

- [ ] **Step 2: Run the new live-audit tests and confirm failure**

Run:

```bash
wsl.exe -u root -e bash -lc 'cd /root/work/OP_Linux/.worktrees/codex-prod0-pg-tenant-optimization && uv run pytest tests/test_prod0_postgres_app_resource_audit.py -q -k "audit_live"'
```

Expected:

- FAIL because there is no `tenant audit-live` parser or implementation yet.

- [ ] **Step 3: Add the `audit-live` CLI action and the remote snapshot script**

Extend `ops/cli/prod0_postgres_app_resource_audit.py`:

```python
audit_live = tenant_subparsers.add_parser("audit-live", help="Audit live prod0 PostgreSQL runtime state")
audit_live.add_argument("--target", required=True, choices=("prod0-main",), help="Target environment")
audit_live.add_argument("--repo-root", default=".", help="Repository root")


def _prod0_live_audit_snapshot(repo_root: Path) -> dict[str, Any]:
    script = repo_root / "ops" / "scripts" / "remote" / "prod0-postgres-app-resource-live-audit.sh"
    result = subprocess.run(
        [str(repo_root / "ops" / "scripts" / "remote" / "run_remote_bash.sh"), "prod0-main", "--script-file", str(script)],
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "audit-live remote command failed")
    payload = json.loads(result.stdout)
    if not isinstance(payload, dict):
        raise ValueError("audit-live snapshot must be a JSON object")
    return payload


def tenant_audit_live(repo_root: Path, target: str) -> dict[str, Any]:
    _, registry = load_registry(repo_root, target)
    snapshot = _prod0_live_audit_snapshot(repo_root)
    findings: list[dict[str, Any]] = []
    for app_id, entry in registry.items():
        if not isinstance(app_id, str) or not isinstance(entry, dict):
            continue
        expected_pg = entry.get("postgres")
        if not isinstance(expected_pg, dict):
            continue
        expected_db = expected_pg.get("database")
        expected_user = expected_pg.get("user")
        runtime = snapshot.get("apps", {}).get(app_id, {})
        if runtime.get("database") != expected_db or runtime.get("user") != expected_user:
            findings.append(
                {
                    "id": "tenant.runtime_drift",
                    "app": app_id,
                    "expected": {"database": expected_db, "user": expected_user},
                    "actual": {"database": runtime.get("database"), "user": runtime.get("user")},
                }
            )
        owner = snapshot.get("catalog", {}).get("databases", {}).get(expected_db)
        if owner != expected_user:
            findings.append(
                {
                    "id": "tenant.live_state_drift",
                    "app": app_id,
                    "database": expected_db,
                    "expected_owner": expected_user,
                    "actual_owner": owner,
                }
            )
    return {
        "command": "tenant",
        "action": "audit-live",
        "ok": not findings,
        "findings": findings,
    }
```

Create `ops/scripts/remote/prod0-postgres-app-resource-live-audit.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail

set -a
source /opt/env_ubuntu/secrets/services/postgres/admin.prod0.env
set +a

apps_json="$(
docker inspect newapi-prod sub2api-prod sub2apipay-prod --format '{{.Name}} {{range .Config.Env}}{{println .}}{{end}}' | python3 - <<'PY'
import json
import sys
apps = {}
current = None
for raw in sys.stdin:
    line = raw.rstrip("\n")
    if line.startswith("/"):
        current = line.split()[0].lstrip("/")
        apps[current] = {}
        continue
    if "=" not in line or current is None:
        continue
    key, value = line.split("=", 1)
    if key in {"DATABASE_URL", "SQL_DSN", "DATABASE_HOST", "DATABASE_USER", "DATABASE_DBNAME"}:
        apps[current][key] = value
print(json.dumps(apps, ensure_ascii=False))
PY
)"

catalog_json="$(
docker exec -e PGPASSWORD="$POSTGRES_PASSWORD" postgres18-prod psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -At -F "|" -c "SELECT datname, pg_catalog.pg_get_userbyid(datdba) FROM pg_database WHERE datistemplate = false ORDER BY datname;" |
python3 - <<'PY'
import json
import sys
databases = {}
for raw in sys.stdin:
    name, owner = raw.strip().split("|", 1)
    databases[name] = owner
print(json.dumps({"databases": databases}, ensure_ascii=False))
PY
)"

python3 - <<'PY' "$apps_json" "$catalog_json"
import json
import sys
print(json.dumps({"apps": json.loads(sys.argv[1]), "catalog": json.loads(sys.argv[2])}, ensure_ascii=False))
PY
```

- [ ] **Step 4: Run the targeted tests and a dry live audit against prod0**

Run:

```bash
wsl.exe -u root -e bash -lc 'cd /root/work/OP_Linux/.worktrees/codex-prod0-pg-tenant-optimization && uv run pytest tests/test_prod0_postgres_app_resource_audit.py -q -k "audit_live" && uv run python -m ops.cli app resource verify-live --target prod0-main --repo-root /root/work/OP_Linux/.worktrees/codex-prod0-pg-tenant-optimization'
```

Expected:

- Tests PASS.
- The CLI returns JSON with `action = "audit-live"`.
- Before the production cutover, the output may still report drift for `sub2apipay` and/or `app` ownership. That is expected at this stage.

- [ ] **Step 5: Commit the new live-audit command and script**

Run:

```bash
wsl.exe -u root -e bash -lc 'cd /root/work/OP_Linux/.worktrees/codex-prod0-pg-tenant-optimization && git add ops/cli/prod0_postgres_app_resource_audit.py tests/test_prod0_postgres_app_resource_audit.py ops/scripts/remote/prod0-postgres-app-resource-live-audit.sh && git commit -m "feat: add prod0 postgres tenant live audit"'
```

Expected:

- A commit exists containing only the live audit command and its tests/script.

### Task 4: Execute The Production PostgreSQL Tenant Cutover

**Files:**
- Create: `secrets/app-resources/prod0-main/sub2apipay/postgres.env`
- Create: `docs/runbooks/prod0-postgres-app-resource-ops.md`
- Create: `ops/scripts/remote/prod0-postgres-app-resource-cutover.sh`
- Verify remote: `/opt/env_ubuntu/secrets/services/postgres/admin.prod0.env`
- Verify remote: `/data/sub2apipay/config/sub2apipay-prod.env`
- Verify remote: `postgres18-prod`

- [ ] **Step 1: Materialize the local tenant secret file for `sub2apipay`**

Generate the password and write the local secret file with `chmod 600`:

```bash
wsl.exe -u root -e bash -lc '
cd /root/work/OP_Linux
install -m 700 -d secrets/app-resources/prod0-main/sub2apipay
SUB2APIPAY_PG_PASSWORD="$(openssl rand -hex 24)"
cat > secrets/app-resources/prod0-main/sub2apipay/postgres.env <<EOF
PGHOST=postgres18-prod
PGPORT=5432
PGDATABASE=sub2apipay
PGUSER=sub2apipay_prod0
PGPASSWORD=$SUB2APIPAY_PG_PASSWORD
PGSSLMODE=disable
EOF
chmod 600 secrets/app-resources/prod0-main/sub2apipay/postgres.env
'
```

Expected:

- `secrets/app-resources/prod0-main/sub2apipay/postgres.env` exists locally with production-only PostgreSQL tenant credentials.

- [ ] **Step 2: Write the reusable remote cutover script**

Create `ops/scripts/remote/prod0-postgres-app-resource-cutover.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail

set -a
source /opt/env_ubuntu/secrets/services/postgres/admin.prod0.env
set +a

SUB2APIPAY_PG_PASSWORD="${SUB2APIPAY_PG_PASSWORD:?missing}"

docker exec -i -e PGPASSWORD="$POSTGRES_PASSWORD" postgres18-prod psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1 -v new_password="$SUB2APIPAY_PG_PASSWORD" <<'SQL'
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'postgres') THEN
    EXECUTE format('CREATE ROLE postgres LOGIN SUPERUSER CREATEDB CREATEROLE REPLICATION PASSWORD %L', current_setting('app.admin_password', true));
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'sub2apipay_prod0') THEN
    EXECUTE format('CREATE ROLE sub2apipay_prod0 LOGIN PASSWORD %L NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION', :'new_password');
  ELSE
    EXECUTE format('ALTER ROLE sub2apipay_prod0 LOGIN PASSWORD %L NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION', :'new_password');
  END IF;
END
$$;
SQL

docker exec -e PGPASSWORD="$POSTGRES_PASSWORD" postgres18-prod psql -U "$POSTGRES_USER" -d postgres -v ON_ERROR_STOP=1 -c "ALTER DATABASE sub2apipay OWNER TO sub2apipay_prod0;"
docker exec -e PGPASSWORD="$POSTGRES_PASSWORD" postgres18-prod psql -U "$POSTGRES_USER" -d sub2apipay -v ON_ERROR_STOP=1 -c "REASSIGN OWNED BY app TO sub2apipay_prod0;"
docker exec -e PGPASSWORD="$POSTGRES_PASSWORD" postgres18-prod psql -U "$POSTGRES_USER" -d sub2apipay -v ON_ERROR_STOP=1 -c "ALTER SCHEMA public OWNER TO sub2apipay_prod0;"
```

Also document the exact operator flow in `docs/runbooks/prod0-postgres-app-resource-ops.md`, including backup paths, rollback commands, and expected verification commands.

- [ ] **Step 3: Run the cutover script and switch the admin secret to `postgres`**

Run:

```bash
wsl.exe -u root -e bash -lc '
cd /root/work/OP_Linux/.worktrees/codex-prod0-pg-tenant-optimization
export SUB2APIPAY_PG_PASSWORD="$(awk -F= "/^PGPASSWORD=/{print \$2; exit}" /root/work/OP_Linux/secrets/app-resources/prod0-main/sub2apipay/postgres.env)"
./ops/scripts/remote/run_remote_bash.sh prod0-main --script-file /root/work/OP_Linux/.worktrees/codex-prod0-pg-tenant-optimization/ops/scripts/remote/prod0-postgres-app-resource-cutover.sh
scp -F /root/work/OP_Linux/secrets/ssh/config /root/work/OP_Linux/secrets/services/postgres/admin.prod0.env prod0-main:/opt/env_ubuntu/secrets/services/postgres/admin.prod0.env
ssh -F /root/work/OP_Linux/secrets/ssh/config prod0-main "cd /opt/env_ubuntu/infra/compose/postgres && docker compose -f docker-compose.prod0.yml up -d"
'
```

Expected:

- `postgres` administrator login is valid.
- `sub2apipay_prod0` owns database `sub2apipay`.
- `postgres18-prod` restarts healthy with the new admin env.

- [ ] **Step 4: Update the remote `sub2apipay` runtime env and recycle the container**

Run:

```bash
wsl.exe -u root -e bash -lc 'ssh -F /root/work/OP_Linux/secrets/ssh/config prod0-main '"'"'
set -euo pipefail
SUB2APIPAY_PG_PASSWORD=$(awk -F= "/^PGPASSWORD=/{print \$2; exit}" /root/work/OP_Linux/secrets/app-resources/prod0-main/sub2apipay/postgres.env)
python3 - <<'"'"'PY'"'"'
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit
import os
path = Path("/data/sub2apipay/config/sub2apipay-prod.env")
text = path.read_text(encoding="utf-8")
lines = []
for raw in text.splitlines():
    if raw.startswith("DATABASE_URL="):
        prefix, value = raw.split("=", 1)
        parts = urlsplit(value.strip().strip("\""))
        netloc = f"sub2apipay_prod0:{os.environ['SUB2APIPAY_PG_PASSWORD']}@{parts.hostname}:{parts.port}"
        raw = f'{prefix}="{urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))}"'
    lines.append(raw)
path.write_text("\\n".join(lines) + "\\n", encoding="utf-8")
PY
docker restart sub2apipay-prod
'"'"''
```

Expected:

- `/data/sub2apipay/config/sub2apipay-prod.env` now points at `sub2apipay_prod0`.
- `sub2apipay-prod` is running after restart.

- [ ] **Step 5: Verify the cutover and keep the rollback handle**

Run:

```bash
wsl.exe -u root -e bash -lc '
cd /root/work/OP_Linux/.worktrees/codex-prod0-pg-tenant-optimization &&
uv run python -m ops.cli app resource verify-live --target prod0-main --repo-root /root/work/OP_Linux/.worktrees/codex-prod0-pg-tenant-optimization &&
ssh -F /root/work/OP_Linux/secrets/ssh/config prod0-main "docker ps --format \"table {{.Names}}\t{{.Status}}\" | grep -E \"^(postgres18-prod|newapi-prod|sub2api-prod|sub2apipay-prod)[[:space:]]\""
'
```

Expected:

- `tenant audit-live` no longer reports `sub2apipay` runtime drift.
- All four containers are running.
- Keep the pre-cutover backups until the 24-hour observation window ends.

### Task 5: Final Verification, Observation Window, And Cleanup Gate

**Files:**
- Modify: `docs/runbooks/prod0-postgres-app-resource-ops.md`

- [ ] **Step 1: Run the full local regression suite for the touched code paths**

Run:

```bash
wsl.exe -u root -e bash -lc 'cd /root/work/OP_Linux/.worktrees/codex-prod0-pg-tenant-optimization && uv run pytest tests/test_prod0_postgres_app_resource_audit.py tests/test_prod0_audit.py tests/test_app_cli.py tests/test_onepanel_project_lifecycle.py -q'
```

Expected:

- PASS for all targeted suites.

- [ ] **Step 2: Run the local declaration audits and the live production audit together**

Run:

```bash
wsl.exe -u root -e bash -lc '
cd /root/work/OP_Linux/.worktrees/codex-prod0-pg-tenant-optimization &&
uv run python -m ops.cli app resource verify --target prod0-main --repo-root /root/work/OP_Linux/.worktrees/codex-prod0-pg-tenant-optimization &&
uv run python -m ops.cli audit filesystem --env prod0-main --repo-root /root/work/OP_Linux/.worktrees/codex-prod0-pg-tenant-optimization &&
uv run python -m ops.cli app resource verify-live --target prod0-main --repo-root /root/work/OP_Linux/.worktrees/codex-prod0-pg-tenant-optimization
'
```

Expected:

- `tenant validate` succeeds.
- `audit filesystem` reports no prod0 tenant drift.
- `tenant audit-live` reports no runtime drift for `newapi`, `sub2api`, or `sub2apipay`.

- [ ] **Step 3: Wait one full observation window before removing `app`**

Run after 24 hours:

```bash
wsl.exe -u root -e bash -lc 'ssh -F /root/work/OP_Linux/secrets/ssh/config prod0-main '"'"'
set -euo pipefail
set -a
source /opt/env_ubuntu/secrets/services/postgres/admin.prod0.env
set +a
docker exec -e PGPASSWORD="$POSTGRES_PASSWORD" postgres18-prod psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -At -F "|" -c "SELECT usename, datname FROM pg_stat_activity WHERE usename = '"'"''"'"'app'"'"''"'"' ORDER BY datname;"
docker exec -e PGPASSWORD="$POSTGRES_PASSWORD" postgres18-prod psql -U "$POSTGRES_USER" -d sub2apipay -At -F "|" -c "SELECT n.nspname, c.relname FROM pg_class c JOIN pg_roles r ON r.oid = c.relowner JOIN pg_namespace n ON n.oid = c.relnamespace WHERE r.rolname = '"'"''"'"'app'"'"''"'"' ORDER BY n.nspname, c.relname;"
'"'"''
```

Expected:

- No active connections use `app`.
- No owned objects remain under `app` in `sub2apipay`.

- [ ] **Step 4: Drop `app` only if every gate is empty; otherwise record why it remains**

Run only when Step 3 is clean:

```bash
wsl.exe -u root -e bash -lc 'ssh -F /root/work/OP_Linux/secrets/ssh/config prod0-main '"'"'
set -euo pipefail
set -a
source /opt/env_ubuntu/secrets/services/postgres/admin.prod0.env
set +a
docker exec -e PGPASSWORD="$POSTGRES_PASSWORD" postgres18-prod psql -U "$POSTGRES_USER" -d postgres -v ON_ERROR_STOP=1 -c "DROP ROLE app;"
'"'"''
```

Expected:

- `DROP ROLE` succeeds only when there are no remaining dependencies.
- If the command fails, keep `app` and record the blocking dependency in the runbook instead of forcing deletion.

- [ ] **Step 5: Commit the implementation plan artifacts**

Run:

```bash
wsl.exe -u root -e bash -lc 'cd /root/work/OP_Linux/.worktrees/codex-prod0-pg-tenant-optimization && git add docs/superpowers/plans/2026-03-26-prod0-postgres-app-resource-optimization.md docs/runbooks/prod0-postgres-app-resource-ops.md ops/scripts/remote/prod0-postgres-app-resource-live-audit.sh ops/scripts/remote/prod0-postgres-app-resource-cutover.sh && git commit -m "docs: add prod0 postgres tenant optimization plan"'
```

Expected:

- The implementation plan and its runbook/scripts are committed and ready for execution.
