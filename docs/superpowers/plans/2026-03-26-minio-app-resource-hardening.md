# Prod0 MinIO Tenant Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 `prod0-main` 的 MinIO 正式租户从“独立 bucket + 独立 access key”收敛到“独立 bucket + 独立 access key + 独立 bucket-scoped policy”，并把该隔离语义纳入 OP_Linux 台账、审计和远端验证。

**Architecture:** 先用测试锁定新的台账和审计语义，再扩展 `tenant_state` / `audit` / `apps` 对 MinIO policy 元数据的表达，随后在生产机创建并绑定 bucket-scoped policy，最后回写台账并做本地与远端双重验证。整个过程保持单实例 `minio-prod` 不变，不引入多实例拆分。

**Tech Stack:** Python (`uv`, `pytest`), OP_Linux `ops.cli`, JSON inventory ledgers, Bash, SSH, Docker, MinIO `mc`

---

### Task 1: Lock MinIO Policy Metadata In Tests

**Files:**
- Modify: `/root/work/OP_Linux/.worktrees/codex/minio-tenant-hardening/tests/test_prod0_postgres_app_resource_audit.py`
- Modify: `/root/work/OP_Linux/.worktrees/codex/minio-tenant-hardening/tests/test_prod0_audit.py`
- Modify: `/root/work/OP_Linux/.worktrees/codex/minio-tenant-hardening/tests/test_app_cli.py`
- Test: `/root/work/OP_Linux/.worktrees/codex/minio-tenant-hardening/tests/test_prod0_postgres_app_resource_audit.py`
- Test: `/root/work/OP_Linux/.worktrees/codex/minio-tenant-hardening/tests/test_prod0_audit.py`
- Test: `/root/work/OP_Linux/.worktrees/codex/minio-tenant-hardening/tests/test_app_cli.py`

- [ ] **Step 1: Write failing tests for MinIO policy-aware tenant summaries**

```python
def test_build_app_resource_summary_keeps_minio_policy_metadata(self) -> None:
    resources = {
        "minio": {
            "bucket": "prod0-sub2api",
            "access_key": "sub2api_prod0",
            "policy_name": "prod0-sub2api-rw",
            "policy_scope": "bucket-only",
            "isolation_level": "bucket-scoped-rw",
            "secret_file": "secrets/app-resources/prod0-main/sub2api/minio.env",
        }
    }

    summary = build_app_resource_summary(resources)

    self.assertEqual(
        {
            "bucket": "prod0-sub2api",
            "access_key": "sub2api_prod0",
            "policy_name": "prod0-sub2api-rw",
            "policy_scope": "bucket-only",
            "isolation_level": "bucket-scoped-rw",
            "secret_file": "secrets/app-resources/prod0-main/sub2api/minio.env",
        },
        summary["minio"],
    )
```

- [ ] **Step 2: Write failing audit tests for MinIO policy drift detection**

```python
def test_tenant_audit_detects_minio_policy_drift_between_inventory_and_registry(self) -> None:
    payload = baseline_payload(include_app_resource_summary=True)
    payload["services"]["sub2api"]["app_resource_summary"]["minio"]["policy_name"] = "legacy-readwrite"
    payload["services"]["sub2api"]["app_resource_summary"]["minio"]["policy_scope"] = "global"
    payload["services"]["sub2api"]["app_resource_summary"]["minio"]["isolation_level"] = "shared-readwrite"

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        write_prod0_inventory(root, payload)
        write_tenant_registry(root, baseline_tenant_registry())

        result = audit_filesystem(root, "prod0-main")
        codes = {item["id"] for item in result["violations"]}

        self.assertIn("prod0.tenant.drift", codes)
```

- [ ] **Step 3: Run the focused tests and verify RED**

Run:

```bash
wsl.exe -u root -e bash -lc 'cd /root/work/OP_Linux/.worktrees/codex/minio-tenant-hardening && uv run pytest tests/test_prod0_postgres_app_resource_audit.py tests/test_prod0_audit.py tests/test_app_cli.py -q -k "minio and (policy or isolation_level or policy_scope)"'
```

Expected: FAIL because the current tenant summary field set only keeps `bucket` and `access_key`, and the current baseline fixtures do not include MinIO policy metadata.

- [ ] **Step 4: Implement the minimal fixture/test updates to express the approved MinIO model**

```python
def baseline_tenant_registry() -> dict:
    return {
        "sub2api": {
            # ...
            "minio": {
                "bucket": "prod0-sub2api",
                "access_key": "sub2api_prod0",
                "policy_name": "prod0-sub2api-rw",
                "policy_scope": "bucket-only",
                "isolation_level": "bucket-scoped-rw",
            },
        },
        "newapi": {
            # ...
            "minio": {
                "bucket": "prod0-newapi",
                "access_key": "newapi_prod0",
                "policy_name": "prod0-newapi-rw",
                "policy_scope": "bucket-only",
                "isolation_level": "bucket-scoped-rw",
            },
        },
    }
```

- [ ] **Step 5: Re-run the focused tests and verify GREEN**

Run:

```bash
wsl.exe -u root -e bash -lc 'cd /root/work/OP_Linux/.worktrees/codex/minio-tenant-hardening && uv run pytest tests/test_prod0_postgres_app_resource_audit.py tests/test_prod0_audit.py tests/test_app_cli.py -q -k "minio and (policy or isolation_level or policy_scope)"'
```

Expected: PASS with the new test cases green.

### Task 2: Extend Tenant Summary, Audit, And Generated Docs

**Files:**
- Modify: `/root/work/OP_Linux/.worktrees/codex/minio-tenant-hardening/ops/cli/app_resource_state.py`
- Modify: `/root/work/OP_Linux/.worktrees/codex/minio-tenant-hardening/ops/cli/audit.py`
- Modify: `/root/work/OP_Linux/.worktrees/codex/minio-tenant-hardening/ops/cli/apps.py`
- Test: `/root/work/OP_Linux/.worktrees/codex/minio-tenant-hardening/tests/test_prod0_postgres_app_resource_audit.py`
- Test: `/root/work/OP_Linux/.worktrees/codex/minio-tenant-hardening/tests/test_prod0_audit.py`
- Test: `/root/work/OP_Linux/.worktrees/codex/minio-tenant-hardening/tests/test_app_cli.py`

- [ ] **Step 1: Update the failing tests so generated docs require MinIO bucket-scoped wording**

```python
def test_render_server_readme_mentions_bucket_scoped_minio_isolation(self) -> None:
    readme = _render_server_readme("prod0-main", inventory_payload)

    self.assertIn("bucket-scoped-rw", readme)
    self.assertIn("policy_name", readme)
    self.assertIn("policy_scope", readme)
```

- [ ] **Step 2: Run the focused app/audit tests and verify RED**

Run:

```bash
wsl.exe -u root -e bash -lc 'cd /root/work/OP_Linux/.worktrees/codex/minio-tenant-hardening && uv run pytest tests/test_app_cli.py tests/test_prod0_audit.py tests/test_prod0_postgres_app_resource_audit.py -q'
```

Expected: FAIL on the new MinIO metadata assertions before the production code is updated.

- [ ] **Step 3: Extend `TENANT_SUMMARY_FIELDS` and summary rendering with the minimal approved MinIO metadata**

```python
TENANT_SUMMARY_FIELDS: dict[str, tuple[str, ...]] = {
    "postgres": ("database", "user"),
    "redis": ("db", "key_prefix"),
    "minio": ("bucket", "access_key", "policy_name", "policy_scope", "isolation_level"),
}
```

- [ ] **Step 4: Keep audit drift comparison and generated docs aligned with the new MinIO metadata**

```python
lines.append(
    "- `app_resource_summary` 供 prod0 台账与对账使用；Redis 为共享 runtime 凭据，PostgreSQL/MinIO 继续记录各自租户凭据标识，其中 MinIO 额外登记 bucket-scoped policy 元数据。"
)
```

- [ ] **Step 5: Re-run the full local test slice and verify GREEN**

Run:

```bash
wsl.exe -u root -e bash -lc 'cd /root/work/OP_Linux/.worktrees/codex/minio-tenant-hardening && uv run pytest tests/test_prod0_postgres_app_resource_audit.py tests/test_app_cli.py tests/test_prod0_audit.py -q'
```

Expected: PASS.

### Task 3: Update Prod0 Ledgers And Inventory

**Files:**
- Modify: `/root/work/OP_Linux/.worktrees/codex/minio-tenant-hardening/inventory/servers/prod0-main/app-resources.json`
- Modify: `/root/work/OP_Linux/.worktrees/codex/minio-tenant-hardening/inventory/servers/prod0-main/app_resources.md`
- Modify: `/root/work/OP_Linux/.worktrees/codex/minio-tenant-hardening/inventory/servers/prod0-main/inventory.json`
- Test: `/root/work/OP_Linux/.worktrees/codex/minio-tenant-hardening/tests/test_prod0_audit.py`
- Test: `/root/work/OP_Linux/.worktrees/codex/minio-tenant-hardening/tests/test_app_cli.py`

- [ ] **Step 1: Write a failing test that tracked prod0 ledgers expose MinIO policy metadata**

```python
def test_tracked_prod0_registry_exposes_bucket_scoped_minio_metadata(self) -> None:
    registry = json.loads((REPO_ROOT / "inventory" / "servers" / "prod0-main" / "app-resources.json").read_text(encoding="utf-8"))

    self.assertEqual("prod0-sub2api-rw", registry["sub2api"]["minio"]["policy_name"])
    self.assertEqual("bucket-only", registry["sub2api"]["minio"]["policy_scope"])
    self.assertEqual("bucket-scoped-rw", registry["sub2api"]["minio"]["isolation_level"])
```

- [ ] **Step 2: Run the tracked-ledger tests and verify RED**

Run:

```bash
wsl.exe -u root -e bash -lc 'cd /root/work/OP_Linux/.worktrees/codex/minio-tenant-hardening && uv run pytest tests/test_prod0_audit.py tests/test_app_cli.py -q -k "tracked_prod0 or bucket_scoped or policy_name"'
```

Expected: FAIL because the tracked prod0 ledgers still expose only `bucket` and `access_key`.

- [ ] **Step 3: Update the tracked prod0 ledgers with the approved MinIO isolation metadata**

```json
"minio": {
  "bucket": "prod0-sub2api",
  "access_key": "sub2api_prod0",
  "policy_name": "prod0-sub2api-rw",
  "policy_scope": "bucket-only",
  "isolation_level": "bucket-scoped-rw"
}
```

- [ ] **Step 4: Re-run the tracked-ledger tests and verify GREEN**

Run:

```bash
wsl.exe -u root -e bash -lc 'cd /root/work/OP_Linux/.worktrees/codex/minio-tenant-hardening && uv run pytest tests/test_prod0_audit.py tests/test_app_cli.py -q -k "tracked_prod0 or bucket_scoped or policy_name"'
```

Expected: PASS.

### Task 4: Reconcile MinIO Policies On `prod0-main`

**Files:**
- Use: `/root/work/OP_Linux/secrets/services/minio/admin.prod0.env`
- Use: `/root/work/OP_Linux/secrets/app-resources/prod0-main/sub2api/minio.env`
- Use: `/root/work/OP_Linux/secrets/app-resources/prod0-main/newapi/minio.env`
- Verify remote: `minio-prod`
- Verify remote: `/opt/env_ubuntu/secrets/services/sub2api.prod0.env`
- Verify remote: `/opt/env_ubuntu/secrets/services/newapi.prod0.env`

- [ ] **Step 1: Capture a read-only MinIO baseline before changing IAM**

Run:

```bash
wsl.exe -u root -e bash -lc '
cd /root/work/OP_Linux &&
source secrets/services/minio/admin.prod0.env &&
ssh -F secrets/ssh/config prod0-main "docker run --rm --network host -e MC_HOST_prod0=http://$MINIO_ROOT_USER:$MINIO_ROOT_PASSWORD@127.0.0.1:9000 minio/mc admin user list prod0" &&
ssh -F secrets/ssh/config prod0-main "docker run --rm --network host -e MC_HOST_prod0=http://$MINIO_ROOT_USER:$MINIO_ROOT_PASSWORD@127.0.0.1:9000 minio/mc admin policy list prod0" &&
ssh -F secrets/ssh/config prod0-main "docker run --rm --network host -e MC_HOST_prod0=http://$MINIO_ROOT_USER:$MINIO_ROOT_PASSWORD@127.0.0.1:9000 minio/mc ls prod0"
'
```

Expected: both app users exist, both buckets exist, and the current policy list still includes global `readwrite`.

- [ ] **Step 2: Create bucket-scoped MinIO policy documents on the remote host**

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["s3:ListBucket", "s3:GetBucketLocation"],
      "Resource": ["arn:aws:s3:::prod0-sub2api"]
    },
    {
      "Effect": "Allow",
      "Action": ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"],
      "Resource": ["arn:aws:s3:::prod0-sub2api/*"]
    }
  ]
}
```

- [ ] **Step 3: Attach the new MinIO policies to the app users**

Run:

```bash
wsl.exe -u root -e bash -lc '
cd /root/work/OP_Linux &&
source secrets/services/minio/admin.prod0.env &&
ssh -F secrets/ssh/config prod0-main "docker run --rm --network host -v /tmp:/tmp -e MC_HOST_prod0=http://$MINIO_ROOT_USER:$MINIO_ROOT_PASSWORD@127.0.0.1:9000 minio/mc admin policy create prod0 prod0-sub2api-rw /tmp/prod0-sub2api-rw.json" &&
ssh -F secrets/ssh/config prod0-main "docker run --rm --network host -v /tmp:/tmp -e MC_HOST_prod0=http://$MINIO_ROOT_USER:$MINIO_ROOT_PASSWORD@127.0.0.1:9000 minio/mc admin policy create prod0 prod0-newapi-rw /tmp/prod0-newapi-rw.json" &&
ssh -F secrets/ssh/config prod0-main "docker run --rm --network host -e MC_HOST_prod0=http://$MINIO_ROOT_USER:$MINIO_ROOT_PASSWORD@127.0.0.1:9000 minio/mc admin policy attach prod0 prod0-sub2api-rw --user sub2api_prod0" &&
ssh -F secrets/ssh/config prod0-main "docker run --rm --network host -e MC_HOST_prod0=http://$MINIO_ROOT_USER:$MINIO_ROOT_PASSWORD@127.0.0.1:9000 minio/mc admin policy attach prod0 prod0-newapi-rw --user newapi_prod0"
'
```

Expected: both users now report the bucket-scoped policy instead of global `readwrite`.

- [ ] **Step 4: Rotate tenant S3 secret keys only if the live users still rely on pre-hardening shared semantics**

Run:

```bash
wsl.exe -u root -e bash -lc '
cd /root/work/OP_Linux &&
source secrets/services/minio/admin.prod0.env &&
ssh -F secrets/ssh/config prod0-main "docker run --rm --network host -e MC_HOST_prod0=http://$MINIO_ROOT_USER:$MINIO_ROOT_PASSWORD@127.0.0.1:9000 minio/mc admin user info prod0 sub2api_prod0" &&
ssh -F secrets/ssh/config prod0-main "docker run --rm --network host -e MC_HOST_prod0=http://$MINIO_ROOT_USER:$MINIO_ROOT_PASSWORD@127.0.0.1:9000 minio/mc admin user info prod0 newapi_prod0"
'
```

Expected: if policy hardening alone is sufficient for this window, keep existing keys; if a key rotation is required, update the corresponding local tenant secrets before any runtime projection refresh.

- [ ] **Step 5: Verify negative access expectations**

Run:

```bash
wsl.exe -u root -e bash -lc '
cd /root/work/OP_Linux &&
source secrets/app-resources/prod0-main/sub2api/minio.env &&
ssh -F secrets/ssh/config prod0-main "docker run --rm --network host -e MC_HOST_sub2=http://$S3_ACCESS_KEY:$S3_SECRET_KEY@127.0.0.1:9000 minio/mc ls sub2/prod0-newapi"
'
```

Expected: FAIL with access denied. Repeat symmetrically for `newapi_prod0` against `prod0-sub2api`.

### Task 5: Final Validation And Evidence Capture

**Files:**
- Modify: `/root/work/OP_Linux/.worktrees/codex/minio-tenant-hardening/docs/runbooks/prod0-main-governance.md`
- Test: `/root/work/OP_Linux/.worktrees/codex/minio-tenant-hardening/tests/test_prod0_postgres_app_resource_audit.py`
- Test: `/root/work/OP_Linux/.worktrees/codex/minio-tenant-hardening/tests/test_app_cli.py`
- Test: `/root/work/OP_Linux/.worktrees/codex/minio-tenant-hardening/tests/test_prod0_audit.py`

- [ ] **Step 1: Update the prod0 governance runbook to describe the new MinIO isolation model**

```markdown
- MinIO formal tenants use bucket-scoped policies on `minio-prod`.
- App users must not retain the built-in global `readwrite` policy.
- `app-resources.json` and `inventory.json` are the non-sensitive source of truth for bucket / access key / policy metadata.
```

- [ ] **Step 2: Run the full local validation suite**

Run:

```bash
wsl.exe -u root -e bash -lc 'cd /root/work/OP_Linux/.worktrees/codex/minio-tenant-hardening && uv run pytest tests/test_prod0_postgres_app_resource_audit.py tests/test_app_cli.py tests/test_prod0_audit.py -q'
wsl.exe -u root -e bash -lc 'cd /root/work/OP_Linux/.worktrees/codex/minio-tenant-hardening && uv run python -m ops.cli app resource verify --target prod0-main'
wsl.exe -u root -e bash -lc 'cd /root/work/OP_Linux/.worktrees/codex/minio-tenant-hardening && uv run python -m ops.cli app resource verify --target prod0-main'
wsl.exe -u root -e bash -lc 'cd /root/work/OP_Linux/.worktrees/codex/minio-tenant-hardening && uv run python -m ops.cli audit filesystem --env prod0-main'
```

Expected: all commands succeed.

- [ ] **Step 3: Run the live MinIO verification slice**

Run:

```bash
wsl.exe -u root -e bash -lc '
cd /root/work/OP_Linux &&
source secrets/services/minio/admin.prod0.env &&
ssh -F secrets/ssh/config prod0-main "docker run --rm --network host -e MC_HOST_prod0=http://$MINIO_ROOT_USER:$MINIO_ROOT_PASSWORD@127.0.0.1:9000 minio/mc admin user info prod0 sub2api_prod0" &&
ssh -F secrets/ssh/config prod0-main "docker run --rm --network host -e MC_HOST_prod0=http://$MINIO_ROOT_USER:$MINIO_ROOT_PASSWORD@127.0.0.1:9000 minio/mc admin user info prod0 newapi_prod0" &&
ssh -F secrets/ssh/config prod0-main "docker run --rm --network host -e MC_HOST_prod0=http://$MINIO_ROOT_USER:$MINIO_ROOT_PASSWORD@127.0.0.1:9000 minio/mc admin policy info prod0 prod0-sub2api-rw" &&
ssh -F secrets/ssh/config prod0-main "docker run --rm --network host -e MC_HOST_prod0=http://$MINIO_ROOT_USER:$MINIO_ROOT_PASSWORD@127.0.0.1:9000 minio/mc admin policy info prod0 prod0-newapi-rw"
'
```

Expected: each app user reports only its bucket-scoped policy, and each policy references only the matching bucket ARN.

- [ ] **Step 4: Commit the non-secret repository changes**

Run:

```bash
wsl.exe -u root -e bash -lc 'cd /root/work/OP_Linux/.worktrees/codex/minio-tenant-hardening && git add ops/cli/app_resource_state.py ops/cli/audit.py ops/cli/apps.py tests/test_prod0_postgres_app_resource_audit.py tests/test_app_cli.py tests/test_prod0_audit.py inventory/servers/prod0-main/app-resources.json inventory/servers/prod0-main/app_resources.md inventory/servers/prod0-main/inventory.json docs/runbooks/prod0-main-governance.md docs/superpowers/plans/2026-03-26-minio-app-resource-hardening.md && git commit -m "feat: harden prod0 minio tenant isolation"'
```

Expected: commit succeeds without staging secret files.
