# Prod0 PostgreSQL Admin Cutover Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不打断 `newapi`、`sub2api`、`sub2apipay` 现网服务的前提下，把 `prod0-main` 的 PostgreSQL 管理员默认连接从 `POSTGRES_DB=app`、`POSTGRES_USER=app` 切换到 `POSTGRES_DB=postgres`、`POSTGRES_USER=postgres`，并在完成 `sub2apipay` 迁移后安全退役 `app` 角色与可选的 `app` 数据库。

**Architecture:** 本计划分五段执行。第一段只做快照与备份，锁定回滚点。第二段在线补齐 `postgres` 管理员角色并切换管理员配置，不碰业务应用连接。第三段将 `sub2apipay` 单独迁到专用 PostgreSQL 角色。第四段在观察与审计通过后退役 `app` 角色。第五段根据实际使用情况决定是否删除 `app` 数据库。

**Tech Stack:** Bash, SSH, Docker Compose, PostgreSQL 18, `psql`, `sed`, `curl`, OP_Linux secrets layout

---

### Task 1: Snapshot Live State And Backup Cutover Inputs

**Files:**
- Modify: `/root/work/OP_Linux/secrets/services/postgres/admin.prod0.env`
- Verify remote: `/opt/env_ubuntu/secrets/services/postgres/admin.prod0.env`
- Verify remote: `/data/sub2apipay/config/sub2apipay-prod.env`
- Verify remote: `postgres18-prod`

- [ ] **Step 1: Back up the local admin secret file**

Run:

```bash
wsl.exe -u root -e bash -lc 'cd /root/work/OP_Linux && cp secrets/services/postgres/admin.prod0.env secrets/services/postgres/admin.prod0.env.bak-20260326-pre-cutover'
```

Expected:

- A new local backup file `secrets/services/postgres/admin.prod0.env.bak-20260326-pre-cutover` exists.

- [ ] **Step 2: Back up the remote admin secret file and sub2apipay env file**

Run:

```bash
wsl.exe -u root -e bash -lc 'ssh -F /root/work/OP_Linux/secrets/ssh/config prod0-main '"'"'
set -euo pipefail
ts=$(date +%Y%m%d%H%M%S)
cp /opt/env_ubuntu/secrets/services/postgres/admin.prod0.env /opt/env_ubuntu/secrets/services/postgres/admin.prod0.env.bak-$ts
cp /data/sub2apipay/config/sub2apipay-prod.env /data/sub2apipay/config/sub2apipay-prod.env.bak-$ts
echo "backup_ts=$ts"
'"'"''
```

Expected:

- Remote backup copies are created for both files.
- The command prints one `backup_ts=...` line.

- [ ] **Step 3: Snapshot current databases, roles, and active PostgreSQL connections**

Run:

```bash
wsl.exe -u root -e bash -lc 'ssh -F /root/work/OP_Linux/secrets/ssh/config prod0-main '"'"'
set -euo pipefail
pg_user=$(awk -F= "/^POSTGRES_USER=/{print \$2; exit}" /opt/env_ubuntu/secrets/services/postgres/admin.prod0.env)
pg_db=$(awk -F= "/^POSTGRES_DB=/{print \$2; exit}" /opt/env_ubuntu/secrets/services/postgres/admin.prod0.env)
export PGPASSWORD=$(awk -F= "/^POSTGRES_PASSWORD=/{print \$2; exit}" /opt/env_ubuntu/secrets/services/postgres/admin.prod0.env)
echo "===DATABASES==="
docker exec -e PGPASSWORD="$PGPASSWORD" postgres18-prod psql -U "$pg_user" -d "$pg_db" -At -F "|" -c "SELECT datname, pg_get_userbyid(datdba) AS owner FROM pg_database WHERE datistemplate = false ORDER BY datname;"
echo "===ROLES==="
docker exec -e PGPASSWORD="$PGPASSWORD" postgres18-prod psql -U "$pg_user" -d "$pg_db" -At -F "|" -c "SELECT rolname, rolcanlogin, rolsuper, rolcreatedb, rolcreaterole, rolreplication FROM pg_roles ORDER BY rolname;"
echo "===ACTIVITY==="
docker exec -e PGPASSWORD="$PGPASSWORD" postgres18-prod psql -U "$pg_user" -d "$pg_db" -At -F "|" -c "SELECT usename, datname, application_name, state FROM pg_stat_activity WHERE datname IS NOT NULL ORDER BY usename, datname;"
'"'"''
```

Expected:

- The output shows current database owners.
- The output shows whether a `postgres` role already exists.
- The activity list confirms whether any connection still uses `app`.

- [ ] **Step 4: Confirm current production app env files before any write**

Run:

```bash
wsl.exe -u root -e bash -lc 'ssh -F /root/work/OP_Linux/secrets/ssh/config prod0-main '"'"'
set -euo pipefail
echo "===NEWAPI==="
sed -n "1,40p" /opt/env_ubuntu/secrets/services/newapi.prod0.env | sed -E "s/(PASSWORD|SECRET|TOKEN|KEY)=.*/\1=REDACTED/"
echo "===SUB2API==="
sed -n "1,60p" /opt/env_ubuntu/secrets/services/sub2api.prod0.env | sed -E "s/(PASSWORD|SECRET|TOKEN|KEY)=.*/\1=REDACTED/"
echo "===SUB2APIPAY==="
sed -n "1,30p" /data/sub2apipay/config/sub2apipay-prod.env | sed -E "s/((PASSWORD|SECRET|TOKEN|KEY|DATABASE_URL)=).*/\1REDACTED/"
'"'"''
```

Expected:

- `newapi` still points to `newapi_prod0`.
- `sub2api` still points to `sub2api_prod0`.
- `sub2apipay` still points to `app`.

- [ ] **Step 5: Record the pre-cutover container baseline**

Run:

```bash
wsl.exe -u root -e bash -lc 'ssh -F /root/work/OP_Linux/secrets/ssh/config prod0-main "docker ps --format \"table {{.Names}}\t{{.Status}}\" | sed -n \"1,20p\""'
```

Expected:

- `postgres18-prod`, `newapi-prod`, `sub2api-prod`, and `sub2apipay-prod` all appear as running before cutover starts.

### Task 2: Create And Validate The `postgres` Administrator Role

**Files:**
- Use: `/root/work/OP_Linux/secrets/services/postgres/admin.prod0.env`
- Verify remote: `postgres18-prod`

- [ ] **Step 1: Create or normalize the `postgres` login role without removing `app`**

Run:

```bash
wsl.exe -u root -e bash -lc 'ssh -F /root/work/OP_Linux/secrets/ssh/config prod0-main '"'"'
set -euo pipefail
pg_user=$(awk -F= "/^POSTGRES_USER=/{print \$2; exit}" /opt/env_ubuntu/secrets/services/postgres/admin.prod0.env)
pg_db=$(awk -F= "/^POSTGRES_DB=/{print \$2; exit}" /opt/env_ubuntu/secrets/services/postgres/admin.prod0.env)
CURRENT_ADMIN_PASSWORD=$(awk -F= "/^POSTGRES_PASSWORD=/{print \$2; exit}" /opt/env_ubuntu/secrets/services/postgres/admin.prod0.env)
export PGPASSWORD="$CURRENT_ADMIN_PASSWORD"
docker exec -i -e PGPASSWORD="$PGPASSWORD" postgres18-prod psql -U "$pg_user" -d "$pg_db" -v ON_ERROR_STOP=1 -v new_password="$CURRENT_ADMIN_PASSWORD" <<'"'"'SQL'"'"'
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'postgres') THEN
    EXECUTE format('CREATE ROLE postgres LOGIN SUPERUSER CREATEDB CREATEROLE REPLICATION PASSWORD %L', :'new_password');
  ELSE
    EXECUTE format('ALTER ROLE postgres WITH LOGIN SUPERUSER CREATEDB CREATEROLE REPLICATION PASSWORD %L', :'new_password');
  END IF;
END
$$;
SQL
'"'"''
```

Expected:

- The SQL block exits successfully.
- `app` remains untouched.

- [ ] **Step 2: Verify that the new `postgres` role can connect to both `postgres` and `app`**

Run:

```bash
wsl.exe -u root -e bash -lc 'ssh -F /root/work/OP_Linux/secrets/ssh/config prod0-main '"'"'
set -euo pipefail
export PGPASSWORD=$(awk -F= "/^POSTGRES_PASSWORD=/{print \$2; exit}" /opt/env_ubuntu/secrets/services/postgres/admin.prod0.env)
docker exec -e PGPASSWORD="$PGPASSWORD" postgres18-prod psql -U postgres -d postgres -tAc "SELECT current_user, current_database();"
docker exec -e PGPASSWORD="$PGPASSWORD" postgres18-prod psql -U postgres -d app -tAc "SELECT current_user, current_database();"
'"'"''
```

Expected:

- The first query returns `postgres|postgres`.
- The second query returns `postgres|app`.

- [ ] **Step 3: Confirm the `postgres` role is visible in pg_roles**

Run:

```bash
wsl.exe -u root -e bash -lc 'ssh -F /root/work/OP_Linux/secrets/ssh/config prod0-main '"'"'
set -euo pipefail
export PGPASSWORD=$(awk -F= "/^POSTGRES_PASSWORD=/{print \$2; exit}" /opt/env_ubuntu/secrets/services/postgres/admin.prod0.env)
docker exec -e PGPASSWORD="$PGPASSWORD" postgres18-prod psql -U postgres -d postgres -At -F "|" -c "SELECT rolname, rolcanlogin, rolsuper FROM pg_roles WHERE rolname IN ('"'"''"'"'app'"'"''"'"','"'"''"'"'postgres'"'"''"'"') ORDER BY rolname;"
'"'"''
```

Expected:

- The output includes both `app` and `postgres`.
- `postgres` has `rolcanlogin = t` and `rolsuper = t`.

- [ ] **Step 4: Verify that current production apps still have live PostgreSQL sessions**

Run:

```bash
wsl.exe -u root -e bash -lc 'ssh -F /root/work/OP_Linux/secrets/ssh/config prod0-main '"'"'
set -euo pipefail
export PGPASSWORD=$(awk -F= "/^POSTGRES_PASSWORD=/{print \$2; exit}" /opt/env_ubuntu/secrets/services/postgres/admin.prod0.env)
docker exec -e PGPASSWORD="$PGPASSWORD" postgres18-prod psql -U postgres -d postgres -At -F "|" -c "SELECT usename, datname FROM pg_stat_activity WHERE usename IN ('"'"''"'"'newapi_prod0'"'"''"'"','"'"''"'"'sub2api_prod0'"'"''"'"','"'"''"'"'app'"'"''"'"') ORDER BY usename, datname;"
'"'"''
```

Expected:

- `newapi_prod0`, `sub2api_prod0`, and `app` activity can still be observed if the corresponding apps are connected.

- [ ] **Step 5: Stop here if the role checks fail**

Gate:

- If any query in this task fails, do not edit `admin.prod0.env`.
- Use the backup files from Task 1 and investigate before proceeding.

### Task 3: Switch The PostgreSQL Admin Secret To `postgres/postgres`

**Files:**
- Modify: `/root/work/OP_Linux/secrets/services/postgres/admin.prod0.env`
- Verify remote: `/opt/env_ubuntu/secrets/services/postgres/admin.prod0.env`
- Verify remote: `postgres18-prod`
- Verify remote: `/opt/env_ubuntu/infra/compose/postgres/docker-compose.prod0.yml`

- [ ] **Step 1: Update the local admin secret file to the new administrator identity**

Run:

```bash
wsl.exe -u root -e bash -lc 'cd /root/work/OP_Linux && python3 - <<'"'"'PY'"'"'
from pathlib import Path
path = Path("secrets/services/postgres/admin.prod0.env")
lines = path.read_text(encoding="utf-8").splitlines()
updated = []
for line in lines:
    if line.startswith("POSTGRES_DB="):
        updated.append("POSTGRES_DB=postgres")
    elif line.startswith("POSTGRES_USER="):
        updated.append("POSTGRES_USER=postgres")
    else:
        updated.append(line)
path.write_text("\\n".join(updated) + "\\n", encoding="utf-8")
PY'
```

Expected:

- The local `secrets/services/postgres/admin.prod0.env` now points to `postgres/postgres`.

- [ ] **Step 2: Sync the updated admin secret file to prod0-main**

Run:

```bash
wsl.exe -u root -e bash -lc 'scp -F /root/work/OP_Linux/secrets/ssh/config /root/work/OP_Linux/secrets/services/postgres/admin.prod0.env prod0-main:/opt/env_ubuntu/secrets/services/postgres/admin.prod0.env'
```

Expected:

- The remote admin secret file is replaced with the local canonical file.

- [ ] **Step 3: Recreate the PostgreSQL container so the new env values become active**

Run:

```bash
wsl.exe -u root -e bash -lc 'ssh -F /root/work/OP_Linux/secrets/ssh/config prod0-main '"'"'
set -euo pipefail
cd /opt/env_ubuntu/infra/compose/postgres
docker compose -f docker-compose.prod0.yml up -d
'"'"''
```

Expected:

- Docker reports `postgres18-prod` as recreated or kept up to date.

- [ ] **Step 4: Verify health and administrator connectivity through the new env file**

Run:

```bash
wsl.exe -u root -e bash -lc 'ssh -F /root/work/OP_Linux/secrets/ssh/config prod0-main '"'"'
set -euo pipefail
for _ in $(seq 1 15); do
  status=$(docker inspect -f "{{.State.Health.Status}}" postgres18-prod 2>/dev/null || true)
  if [ "$status" = "healthy" ]; then
    break
  fi
  sleep 2
done
echo "health=$(docker inspect -f "{{.State.Health.Status}}" postgres18-prod)"
pg_user=$(awk -F= "/^POSTGRES_USER=/{print \$2; exit}" /opt/env_ubuntu/secrets/services/postgres/admin.prod0.env)
pg_db=$(awk -F= "/^POSTGRES_DB=/{print \$2; exit}" /opt/env_ubuntu/secrets/services/postgres/admin.prod0.env)
export PGPASSWORD=$(awk -F= "/^POSTGRES_PASSWORD=/{print \$2; exit}" /opt/env_ubuntu/secrets/services/postgres/admin.prod0.env)
docker exec -e PGPASSWORD="$PGPASSWORD" postgres18-prod psql -U "$pg_user" -d "$pg_db" -tAc "SELECT version();"
'"'"''
```

Expected:

- `health=healthy`
- `SELECT version();` returns the PostgreSQL version string.

- [ ] **Step 5: Confirm that newapi and sub2api were not impacted by the admin cutover**

Run:

```bash
wsl.exe -u root -e bash -lc 'ssh -F /root/work/OP_Linux/secrets/ssh/config prod0-main '"'"'
set -euo pipefail
docker ps --format "table {{.Names}}\t{{.Status}}" | grep -E "^(newapi-prod|sub2api-prod)[[:space:]]"
'"'"''
```

Expected:

- `newapi-prod` remains healthy.
- `sub2api-prod` remains healthy.

### Task 4: Migrate Sub2apipay Off The Shared `app` Role

**Files:**
- Modify remote: `/data/sub2apipay/config/sub2apipay-prod.env`
- Verify remote: `sub2apipay-prod`
- Verify remote: `postgres18-prod`

- [ ] **Step 1: Create a dedicated PostgreSQL role for sub2apipay**

Run:

```bash
wsl.exe -u root -e bash -lc 'ssh -F /root/work/OP_Linux/secrets/ssh/config prod0-main '"'"'
set -euo pipefail
mkdir -p /opt/env_ubuntu/tmp
SUB2APIPAY_PG_PASSWORD=$(openssl rand -hex 24)
install -m 600 /dev/null /opt/env_ubuntu/tmp/sub2apipay_prod0.pgpass
printf "%s\n" "$SUB2APIPAY_PG_PASSWORD" > /opt/env_ubuntu/tmp/sub2apipay_prod0.pgpass
export PGPASSWORD=$(awk -F= "/^POSTGRES_PASSWORD=/{print \$2; exit}" /opt/env_ubuntu/secrets/services/postgres/admin.prod0.env)
docker exec -i -e PGPASSWORD="$PGPASSWORD" postgres18-prod psql -U postgres -d postgres -v ON_ERROR_STOP=1 -v new_password="$SUB2APIPAY_PG_PASSWORD" <<'"'"'SQL'"'"'
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'sub2apipay_prod0') THEN
    EXECUTE format('CREATE ROLE sub2apipay_prod0 LOGIN PASSWORD %L NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION', :'new_password');
  ELSE
    EXECUTE format('ALTER ROLE sub2apipay_prod0 LOGIN PASSWORD %L NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION', :'new_password');
  END IF;
END
$$;
SQL
'"'"''
```

Expected:

- `sub2apipay_prod0` exists as a login role.
- The generated password is stored temporarily at `/opt/env_ubuntu/tmp/sub2apipay_prod0.pgpass`.

- [ ] **Step 2: Move sub2apipay database ownership and owned objects to the new role**

Run:

```bash
wsl.exe -u root -e bash -lc 'ssh -F /root/work/OP_Linux/secrets/ssh/config prod0-main '"'"'
set -euo pipefail
export PGPASSWORD=$(awk -F= "/^POSTGRES_PASSWORD=/{print \$2; exit}" /opt/env_ubuntu/secrets/services/postgres/admin.prod0.env)
docker exec -e PGPASSWORD="$PGPASSWORD" postgres18-prod psql -U postgres -d postgres -v ON_ERROR_STOP=1 -c "ALTER DATABASE sub2apipay OWNER TO sub2apipay_prod0;"
docker exec -e PGPASSWORD="$PGPASSWORD" postgres18-prod psql -U postgres -d sub2apipay -v ON_ERROR_STOP=1 -c "REASSIGN OWNED BY app TO sub2apipay_prod0;"
docker exec -e PGPASSWORD="$PGPASSWORD" postgres18-prod psql -U postgres -d sub2apipay -v ON_ERROR_STOP=1 -c "ALTER SCHEMA public OWNER TO sub2apipay_prod0;"
'"'"''
```

Expected:

- The database owner changes to `sub2apipay_prod0`.
- Objects previously owned by `app` inside `sub2apipay` are reassigned.

- [ ] **Step 3: Update sub2apipay production env to use the dedicated role**

Run:

```bash
wsl.exe -u root -e bash -lc 'ssh -F /root/work/OP_Linux/secrets/ssh/config prod0-main '"'"'
set -euo pipefail
SUB2APIPAY_PG_PASSWORD=$(cat /opt/env_ubuntu/tmp/sub2apipay_prod0.pgpass)
python3 - <<'"'"'PY'"'"'
from pathlib import Path
import os
from urllib.parse import urlsplit, urlunsplit
path = Path("/data/sub2apipay/config/sub2apipay-prod.env")
text = path.read_text(encoding="utf-8")
prefix = 'DATABASE_URL="'
for line in text.splitlines():
    if line.startswith(prefix):
        current = line[len(prefix):-1]
        break
else:
    raise SystemExit("DATABASE_URL not found")
parts = urlsplit(current)
new_netloc = f"sub2apipay_prod0:{os.environ['SUB2APIPAY_PG_PASSWORD']}@{parts.hostname}:{parts.port}"
new_value = urlunsplit((parts.scheme, new_netloc, parts.path, parts.query, parts.fragment))
path.write_text(text.replace(current, new_value), encoding="utf-8")
PY
'"'"''
```

Expected:

- The remote `sub2apipay-prod.env` contains the new `DATABASE_URL`.

- [ ] **Step 4: Restart sub2apipay and validate it with the new database role**

Run:

```bash
wsl.exe -u root -e bash -lc 'ssh -F /root/work/OP_Linux/secrets/ssh/config prod0-main '"'"'
set -euo pipefail
docker restart sub2apipay-prod
sleep 5
docker ps --format "table {{.Names}}\t{{.Status}}" | grep "^sub2apipay-prod[[:space:]]"
curl -kfsS https://pay.zzzai.cloud:8443/pay >/dev/null
echo "sub2apipay_http=ok"
'"'"''
```

Expected:

- `sub2apipay-prod` is running after restart.
- The public URL responds successfully.

- [ ] **Step 5: Confirm PostgreSQL activity now shows sub2apipay using the new role**

Run:

```bash
wsl.exe -u root -e bash -lc 'ssh -F /root/work/OP_Linux/secrets/ssh/config prod0-main '"'"'
set -euo pipefail
export PGPASSWORD=$(awk -F= "/^POSTGRES_PASSWORD=/{print \$2; exit}" /opt/env_ubuntu/secrets/services/postgres/admin.prod0.env)
docker exec -e PGPASSWORD="$PGPASSWORD" postgres18-prod psql -U postgres -d postgres -At -F "|" -c "SELECT usename, datname FROM pg_stat_activity WHERE datname = '"'"''"'"'sub2apipay'"'"''"'"' ORDER BY usename;"
'"'"''
```

Expected:

- `sub2apipay_prod0|sub2apipay` appears.
- `app|sub2apipay` no longer appears after traffic stabilizes.

### Task 5: Audit And Remove The Legacy `app` Role

**Files:**
- Verify remote: `postgres18-prod`
- Verify remote: `/opt/env_ubuntu/secrets`
- Verify remote: `/data`

- [ ] **Step 1: Wait for one full 24-hour observation window after the sub2apipay cutover**

Gate:

- Do not attempt to remove `app` on the same maintenance window as the `sub2apipay` credential switch.
- Only continue after at least 24 hours of stable production behavior.

- [ ] **Step 2: Search the managed filesystem for any remaining app PostgreSQL references**

Run:

```bash
wsl.exe -u root -e bash -lc 'ssh -F /root/work/OP_Linux/secrets/ssh/config prod0-main "grep -RInE \"postgresql://app:|PGUSER=app|POSTGRES_USER=app|DATABASE_URL=.*app@postgres18-prod\" /opt/env_ubuntu /data 2>/dev/null | head -n 200"'
```

Expected:

- No active runtime files remain that still point to `app`.
- Historical backups may appear, but active config files must not.

- [ ] **Step 3: Verify there are no active app-role sessions and no app-owned non-system objects outside the legacy app database**

Run:

```bash
wsl.exe -u root -e bash -lc 'ssh -F /root/work/OP_Linux/secrets/ssh/config prod0-main '"'"'
set -euo pipefail
export PGPASSWORD=$(awk -F= "/^POSTGRES_PASSWORD=/{print \$2; exit}" /opt/env_ubuntu/secrets/services/postgres/admin.prod0.env)
echo "===APP_ACTIVITY==="
docker exec -e PGPASSWORD="$PGPASSWORD" postgres18-prod psql -U postgres -d postgres -At -F "|" -c "SELECT usename, datname, application_name, state FROM pg_stat_activity WHERE usename = '"'"''"'"'app'"'"''"'"' ORDER BY datname;"
echo "===APP_DATABASE_OWNERS==="
docker exec -e PGPASSWORD="$PGPASSWORD" postgres18-prod psql -U postgres -d postgres -At -F "|" -c "SELECT datname, pg_get_userbyid(datdba) FROM pg_database WHERE pg_get_userbyid(datdba) = '"'"''"'"'app'"'"''"'"' ORDER BY datname;"
echo "===APP_OBJECTS_IN_SUB2APIPAY==="
docker exec -e PGPASSWORD="$PGPASSWORD" postgres18-prod psql -U postgres -d sub2apipay -At -F "|" -c "SELECT n.nspname, c.relname FROM pg_class c JOIN pg_roles r ON r.oid = c.relowner JOIN pg_namespace n ON n.oid = c.relnamespace WHERE r.rolname = '"'"''"'"'app'"'"''"'"' ORDER BY n.nspname, c.relname;"
'"'"''
```

Expected:

- No active `app` sessions remain.
- The only database potentially still owned by `app` is the legacy `app` database itself.
- No objects in `sub2apipay` remain owned by `app`.

- [ ] **Step 4: Remove the app role only after all dependency checks are empty**

Run:

```bash
wsl.exe -u root -e bash -lc 'ssh -F /root/work/OP_Linux/secrets/ssh/config prod0-main '"'"'
set -euo pipefail
export PGPASSWORD=$(awk -F= "/^POSTGRES_PASSWORD=/{print \$2; exit}" /opt/env_ubuntu/secrets/services/postgres/admin.prod0.env)
docker exec -e PGPASSWORD="$PGPASSWORD" postgres18-prod psql -U postgres -d postgres -v ON_ERROR_STOP=1 -c "DROP ROLE app;"
'"'"''
```

Expected:

- `DROP ROLE` succeeds with no dependency error.

- [ ] **Step 5: Validate that the role is gone and no application regressed**

Run:

```bash
wsl.exe -u root -e bash -lc 'ssh -F /root/work/OP_Linux/secrets/ssh/config prod0-main '"'"'
set -euo pipefail
export PGPASSWORD=$(awk -F= "/^POSTGRES_PASSWORD=/{print \$2; exit}" /opt/env_ubuntu/secrets/services/postgres/admin.prod0.env)
docker exec -e PGPASSWORD="$PGPASSWORD" postgres18-prod psql -U postgres -d postgres -At -F "|" -c "SELECT rolname FROM pg_roles WHERE rolname IN ('"'"''"'"'app'"'"''"'"','"'"''"'"'postgres'"'"''"'"','"'"''"'"'sub2apipay_prod0'"'"''"'"') ORDER BY rolname;"
docker ps --format "table {{.Names}}\t{{.Status}}" | grep -E "^(newapi-prod|sub2api-prod|sub2apipay-prod)[[:space:]]"
'"'"''
```

Expected:

- The role list shows `postgres` and `sub2apipay_prod0`, but not `app`.
- All three application containers remain running.

- [ ] **Step 6: Stop here if any dependency blocks the drop**

Gate:

- If `DROP ROLE app;` fails, do not force it with `DROP OWNED`.
- Record the exact dependency, reassign ownership, and re-run the audit instead.

### Task 6: Decide Whether To Drop Or Retain The Legacy `app` Database

**Files:**
- Verify remote: `postgres18-prod`

- [ ] **Step 1: Inspect whether the app database still contains user objects**

Run:

```bash
wsl.exe -u root -e bash -lc 'ssh -F /root/work/OP_Linux/secrets/ssh/config prod0-main '"'"'
set -euo pipefail
export PGPASSWORD=$(awk -F= "/^POSTGRES_PASSWORD=/{print \$2; exit}" /opt/env_ubuntu/secrets/services/postgres/admin.prod0.env)
echo "===APP_DB_OBJECTS==="
docker exec -e PGPASSWORD="$PGPASSWORD" postgres18-prod psql -U postgres -d app -At -F "|" -c "SELECT n.nspname, c.relname, c.relkind FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace WHERE n.nspname NOT IN ('"'"''"'"'pg_catalog'"'"''"'"','"'"''"'"'information_schema'"'"''"'"') ORDER BY n.nspname, c.relname;"
'"'"''
```

Expected:

- You can tell whether the `app` database still stores meaningful user objects.

- [ ] **Step 2: If the app database is intentionally retained, reassign its owner to postgres and stop**

Run:

```bash
wsl.exe -u root -e bash -lc 'ssh -F /root/work/OP_Linux/secrets/ssh/config prod0-main '"'"'
set -euo pipefail
export PGPASSWORD=$(awk -F= "/^POSTGRES_PASSWORD=/{print \$2; exit}" /opt/env_ubuntu/secrets/services/postgres/admin.prod0.env)
docker exec -e PGPASSWORD="$PGPASSWORD" postgres18-prod psql -U postgres -d postgres -v ON_ERROR_STOP=1 -c "ALTER DATABASE app OWNER TO postgres;"
'"'"''
```

Expected:

- The `app` database remains available, but no longer depends on the retired `app` role.

- [ ] **Step 3: If the app database is confirmed disposable, terminate sessions and drop it**

Run:

```bash
wsl.exe -u root -e bash -lc 'ssh -F /root/work/OP_Linux/secrets/ssh/config prod0-main '"'"'
set -euo pipefail
export PGPASSWORD=$(awk -F= "/^POSTGRES_PASSWORD=/{print \$2; exit}" /opt/env_ubuntu/secrets/services/postgres/admin.prod0.env)
docker exec -e PGPASSWORD="$PGPASSWORD" postgres18-prod psql -U postgres -d postgres -v ON_ERROR_STOP=1 -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '"'"''"'"'app'"'"''"'"' AND pid <> pg_backend_pid();"
docker exec -e PGPASSWORD="$PGPASSWORD" postgres18-prod psql -U postgres -d postgres -v ON_ERROR_STOP=1 -c "DROP DATABASE app;"
'"'"''
```

Expected:

- The `app` database is removed only after sessions are terminated.

- [ ] **Step 4: Verify the final database list**

Run:

```bash
wsl.exe -u root -e bash -lc 'ssh -F /root/work/OP_Linux/secrets/ssh/config prod0-main '"'"'
set -euo pipefail
export PGPASSWORD=$(awk -F= "/^POSTGRES_PASSWORD=/{print \$2; exit}" /opt/env_ubuntu/secrets/services/postgres/admin.prod0.env)
docker exec -e PGPASSWORD="$PGPASSWORD" postgres18-prod psql -U postgres -d postgres -At -F "|" -c "SELECT datname, pg_get_userbyid(datdba) FROM pg_database WHERE datistemplate = false ORDER BY datname;"
'"'"''
```

Expected:

- The output either omits `app`, or shows `app|postgres` if the database was intentionally retained.

- [ ] **Step 5: Update the operator record with the final disposition of the app database**

Record one of these outcomes:

- `app` database dropped on `prod0-main`
- `app` database retained for compatibility, owner changed to `postgres`

This record is required before calling the cutover complete.
