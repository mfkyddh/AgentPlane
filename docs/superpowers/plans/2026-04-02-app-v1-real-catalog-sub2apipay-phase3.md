# App V1 Real Catalog Sub2ApiPay Phase 3 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `sub2apipay` as the third real tracked app catalog entry for `prod0-main` only, and sync the corresponding `app object`, `app delivery validate-contract`, and tracked `apps` ledger surfaces without entering any app runtime surface.

**Architecture:** Keep this phase data-only. First freeze the prod0-only scope in a design note, then add failing tests that pin the exact tracked catalog shape, `sub2apipay` object resolution, `prod0-main` contract resolution, and the prod0 tracked `apps` ledger entry while asserting that `prod2-main` and `wsl` still do not resolve `sub2apipay`. After the red phase, apply the minimal tracked JSON/Markdown updates so the existing `app` handlers resolve the real contract through `inventory/apps/catalog.json` without any new compat path, alias, or wrapper.

**Tech Stack:** Python stdlib tests, existing `ops.cli app` surface, tracked JSON catalog and ledgers, Markdown plan/spec docs

---

### Task 1: Freeze The Phase 3 Scope

**Files:**
- Create: `docs/superpowers/specs/2026-04-02-app-v1-real-catalog-sub2apipay-phase3-design.md`
- Modify: `docs/superpowers/plans/2026-04-02-app-v1-real-catalog-sub2apipay-phase3.md`

- [ ] **Step 1: Write the design freeze for `sub2apipay`**

Expected content:

```md
- `sub2apipay` only maps to `prod0-main`
- contract source is `/root/work/sub2apipay/deploy/op/contract.yaml`
- `prod2-main` and `wsl` remain unmapped in tracked catalog
- tracked `prod0-main` apps ledger gains one new `sub2apipay` item
- no runtime, deploy flow, or app repo behavior changes in this phase
```

- [ ] **Step 2: Keep this plan aligned with the design freeze**

Run: `sed -n '1,120p' docs/superpowers/plans/2026-04-02-app-v1-real-catalog-sub2apipay-phase3.md`

Expected: plan scope still says `prod0-main` only and lists `prod2-main` / `wsl` as explicit non-goals.

### Task 2: Add Failing Tests For The Real `sub2apipay` Entry

**Files:**
- Modify: `tests/test_app_object_cli.py`

- [ ] **Step 1: Freeze `inventory/apps/catalog.json` to exactly three real entries**

Add assertions like:

```python
self.assertEqual(
    ["sub2api", "newapi", "sub2apipay"],
    [item["app"] for item in payload["apps"]],
)
self.assertEqual(
    {"prod0-main": "deploy/op/contract.yaml"},
    payload["apps"][2]["contracts"],
)
```

- [ ] **Step 2: Run the focused catalog-shape test and confirm it fails**

Run: `uv run python -m pytest tests/test_app_object_cli.py -q -k sub2apipay`

Expected: FAIL because tracked catalog still has only `sub2api` and `newapi`.

- [ ] **Step 3: Add a failing prod0 object-resolution test**

Add assertions like:

```python
payload_json = json.loads(
    run_cli("app", "object", "get", "--target", "prod0-main", "--app", "sub2apipay").stdout
)
self.assertEqual("sub2apipay", payload_json["payload"]["app"]["app"])
self.assertEqual("/root/work/sub2apipay/deploy/op/contract.yaml", payload_json["payload"]["app"]["contract_file"])
```

- [ ] **Step 4: Add a failing `prod2-main` / `wsl` exclusion test**

Add assertions like:

```python
prod2_json = json.loads(run_cli("app", "object", "search", "--target", "prod2-main").stdout)
wsl_json = json.loads(run_cli("app", "object", "search", "--target", "wsl").stdout)
self.assertEqual([], [item for item in prod2_json["payload"]["items"] if item["app"] == "sub2apipay"])
self.assertEqual([], [item for item in wsl_json["payload"]["items"] if item["app"] == "sub2apipay"])
```

- [ ] **Step 5: Add a failing prod0 delivery-contract resolution test**

Add assertions like:

```python
payload_json = json.loads(
    run_cli(
        "app", "delivery", "validate-contract",
        "--target", "prod0-main",
        "--app", "sub2apipay",
        "--repo-root", str(REPO_ROOT),
    ).stdout
)
self.assertEqual("sub2apipay", payload_json["payload"]["app_id"])
self.assertEqual("sub2apipay", payload_json["payload"]["inventory"]["service_key"])
```

- [ ] **Step 6: Add a failing prod0 tracked-ledger freeze**

Add assertions like:

```python
items = json.loads((REPO_ROOT / "inventory" / "servers" / "prod0-main" / "ledgers" / "apps.json").read_text(encoding="utf-8"))["items"]
self.assertEqual(["sub2api", "newapi", "sub2apipay"], [item["app"] for item in items])
self.assertEqual("https://pay.zzzai.cloud:8443", items[2]["public_url"])
```

- [ ] **Step 7: Run the focused tests and confirm they fail for the new reasons**

Run: `uv run python -m pytest tests/test_app_object_cli.py -q -k sub2apipay`

Expected: FAIL because tracked catalog and prod0 ledger do not yet include `sub2apipay`.

### Task 3: Apply The Minimal Tracked Data Changes

**Files:**
- Modify: `inventory/apps/catalog.json`
- Modify: `inventory/servers/prod0-main/ledgers/apps.json`
- Modify: `inventory/servers/prod0-main/ledgers/apps.md`

- [ ] **Step 1: Add the real `sub2apipay` catalog entry**

Expected tracked entry:

```json
{
  "app": "sub2apipay",
  "repo_name": "sub2apipay",
  "repo_root": "/root/work/sub2apipay",
  "service_key": "sub2apipay",
  "contracts": {
    "prod0-main": "deploy/op/contract.yaml"
  }
}
```

- [ ] **Step 2: Add the prod0 tracked `apps` ledger item**

Expected JSON item:

```json
{
  "app": "sub2apipay",
  "service_key": "sub2apipay",
  "contract_file": "/root/work/sub2apipay/deploy/op/contract.yaml",
  "control_plane": "compose",
  "public_url": "https://pay.zzzai.cloud:8443"
}
```

- [ ] **Step 3: Add the matching Markdown ledger row**

Expected row:

```md
- `sub2apipay` / `compose` / `https://pay.zzzai.cloud:8443`
```

- [ ] **Step 4: Re-run the focused `sub2apipay` tests and confirm they pass**

Run: `uv run python -m pytest tests/test_app_object_cli.py -q -k sub2apipay`

Expected: PASS for catalog shape, prod0 object resolution, prod0 validate-contract, and prod0 ledger freeze.

### Task 4: Run Minimal Verification

**Files:**
- Reference: `inventory/apps/catalog.json`
- Reference: `inventory/servers/prod0-main/ledgers/apps.json`
- Reference: `inventory/servers/prod0-main/ledgers/apps.md`

- [ ] **Step 1: Run the full app object regression file**

Run: `uv run python -m pytest tests/test_app_object_cli.py -q`

Expected: PASS.

- [ ] **Step 2: Verify prod0 search/get resolution**

Run:

```bash
uv run python -m ops.cli app object search --target prod0-main --repo-root /root/work/OP_Linux/.worktrees/codex-app-v1-real-catalog-sub2apipay-phase3
uv run python -m ops.cli app object get --target prod0-main --app sub2apipay --repo-root /root/work/OP_Linux/.worktrees/codex-app-v1-real-catalog-sub2apipay-phase3
```

Expected: `sub2apipay` appears in `prod0-main` search and `get` resolves `/root/work/sub2apipay/deploy/op/contract.yaml`.

- [ ] **Step 3: Verify prod2/wsl remain unmapped**

Run:

```bash
uv run python -m ops.cli app object search --target prod2-main --repo-root /root/work/OP_Linux/.worktrees/codex-app-v1-real-catalog-sub2apipay-phase3
uv run python -m ops.cli app object search --target wsl --repo-root /root/work/OP_Linux/.worktrees/codex-app-v1-real-catalog-sub2apipay-phase3
```

Expected: neither payload contains `sub2apipay`.

- [ ] **Step 4: Verify prod0 delivery contract resolution**

Run: `uv run python -m ops.cli app delivery validate-contract --target prod0-main --app sub2apipay --repo-root /root/work/OP_Linux/.worktrees/codex-app-v1-real-catalog-sub2apipay-phase3`

Expected: PASS with `app_id=sub2apipay` and `service_key=sub2apipay`.

### Task 5: Final Self-Check And Commit

**Files:**
- Modify: `inventory/apps/catalog.json`
- Modify: `inventory/servers/prod0-main/ledgers/apps.json`
- Modify: `inventory/servers/prod0-main/ledgers/apps.md`
- Modify: `tests/test_app_object_cli.py`

- [ ] **Step 1: Verify no out-of-scope files changed**

Run: `git status --short`

Expected: only the tracked catalog, prod0 apps ledger files, tests, and the new design/plan docs are modified.

- [ ] **Step 2: Commit the phase 3 slice**

Run:

```bash
git add docs/superpowers/specs/2026-04-02-app-v1-real-catalog-sub2apipay-phase3-design.md \
        docs/superpowers/plans/2026-04-02-app-v1-real-catalog-sub2apipay-phase3.md \
        inventory/apps/catalog.json \
        inventory/servers/prod0-main/ledgers/apps.json \
        inventory/servers/prod0-main/ledgers/apps.md \
        tests/test_app_object_cli.py
git commit -m "feat: onboard sub2apipay into real app catalog"
```

Expected: one commit containing only the phase 3 tracked-data and test freeze changes.
