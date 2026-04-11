# App Object Aftercare Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `app object get / verify / refresh-ledger` return and validate real `summary_files` and `ledger_status` without expanding into runtime-depth auditing.

**Architecture:** Keep all changes inside the existing `app object` surface. `ops.domain.app.object_handlers` becomes the only place that resolves summary file paths and ledger pointer state; tests in `tests/test_app_object_cli.py` freeze the public JSON shape first, then the minimal handler changes make them pass. `ops.cli.apps` stays as the stable entrypoint and only provides existing helpers such as `_load_inventory` and contract path resolution.

**Tech Stack:** Python stdlib tests, existing `ops.cli app` command surface, tracked JSON inventory under `inventory/servers/<target>`, Markdown summary files in app repos

---

### Task 1: Freeze `get` Output For `summary_files` And `ledger_status`

**Files:**
- Modify: `tests/test_app_object_cli.py`
- Modify: `ops/domain/app/object_handlers.py`
- Reference: `ops/cli/apps.py`

- [ ] **Step 1: Write the failing test for `get` returning non-empty `summary_files` and structured `ledger_status`**

Add this test near the existing `test_app_object_get_returns_named_app_payload` case:

```python
    def test_app_object_get_returns_summary_files_and_ledger_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory_with_app(root)
            app_root = root / "sub2api"
            (app_root / "deploy" / "op").mkdir(parents=True, exist_ok=True)
            (app_root / "deploy" / "op" / "contract.yaml").write_text(
                json.dumps(
                    {
                        "docs": {"app_summary_files": {"prod0-main": "docs/OP_LINUX_DEPLOYMENT.prod0-main.md"}}
                    }
                ),
                encoding="utf-8",
            )
            summary_file = app_root / "docs" / "OP_LINUX_DEPLOYMENT.prod0-main.md"
            summary_file.parent.mkdir(parents=True, exist_ok=True)
            summary_file.write_text("# summary\n", encoding="utf-8")

            payload = run_cli(
                "app",
                "object",
                "get",
                "--target",
                "prod0-main",
                "--app",
                "sub2api",
                "--repo-root",
                str(root),
            )

            self.assertEqual(0, payload.returncode, msg=payload.stderr)
            payload_json = json.loads(payload.stdout)
            self.assertEqual(
                [
                    {
                        "target": "prod0-main",
                        "path": str(summary_file),
                        "source": "docs.app_summary_files",
                        "exists": True,
                    }
                ],
                payload_json["payload"]["summary_files"],
            )
            self.assertEqual(
                {
                    "json_file": str(root / "inventory" / "servers" / "prod0-main" / "ledgers" / "apps.json"),
                    "markdown_file": str(root / "inventory" / "servers" / "prod0-main" / "ledgers" / "apps.md"),
                    "inventory_pointer": "inventory/servers/prod0-main/ledgers/apps.json",
                    "json_exists": True,
                    "markdown_exists": False,
                    "inventory_pointer_ok": False,
                },
                payload_json["payload"]["ledger_status"],
            )
```

- [ ] **Step 2: Run the focused test and verify it fails because `summary_files` is empty and `ledger_status` is missing**

Run:

```bash
uv run pytest -q tests/test_app_object_cli.py -k returns_summary_files_and_ledger_status
```

Expected:

```text
FAIL ... 'summary_files'
```

or a mismatch showing `summary_files` is `[]` and `ledger_status` is absent.

- [ ] **Step 3: Implement minimal summary-file and ledger-status helpers in `ops/domain/app/object_handlers.py`**

Add these helpers above `search_apps()`:

```python
def _contract_payload(contract_file: Path) -> dict[str, Any]:
    import yaml

    payload = yaml.safe_load(contract_file.read_text(encoding="utf-8")) or {}
    return payload if isinstance(payload, dict) else {}


def _summary_files(obj: AppObject) -> list[dict[str, Any]]:
    from ops.cli.apps import _nested_get

    contract = _contract_payload(obj.contract_file)
    summary_paths = _nested_get(contract, "docs.app_summary_files")
    if isinstance(summary_paths, dict):
        target_path = summary_paths.get(obj.target)
        if isinstance(target_path, str) and target_path:
            resolved = (obj.repo_root / target_path).resolve()
            return [
                {
                    "target": obj.target,
                    "path": str(resolved),
                    "source": "docs.app_summary_files",
                    "exists": resolved.is_file(),
                }
            ]
    summary_path = _nested_get(contract, "docs.app_summary_file")
    if isinstance(summary_path, str) and summary_path:
        resolved = (obj.repo_root / summary_path).resolve()
        return [
            {
                "target": obj.target,
                "path": str(resolved),
                "source": "docs.app_summary_file",
                "exists": resolved.is_file(),
            }
        ]
    return []


def _ledger_status(repo_root: Path, target: str) -> dict[str, Any]:
    inventory_file = repo_root / "inventory" / "servers" / target / "inventory.json"
    payload = json.loads(inventory_file.read_text(encoding="utf-8")) if inventory_file.exists() else {}
    expected_pointer = f"inventory/servers/{target}/ledgers/apps.json"
    json_file = repo_root / expected_pointer
    markdown_file = repo_root / "inventory" / "servers" / target / "ledgers" / "apps.md"
    actual_pointer = (((payload.get("object_ledgers") or {}).get("apps")) if isinstance(payload, dict) else None)
    return {
        "json_file": str(json_file),
        "markdown_file": str(markdown_file),
        "inventory_pointer": expected_pointer,
        "json_exists": json_file.is_file(),
        "markdown_exists": markdown_file.is_file(),
        "inventory_pointer_ok": actual_pointer == expected_pointer,
    }
```

Update `get_app()` to return:

```python
    return {
        "app": {
            "app": obj.app,
            "target": obj.target,
            "repo_name": obj.repo_name,
            "service_key": obj.service_key,
            "contract_file": str(obj.contract_file),
            "control_plane": inventory_entry.get("control_plane", ""),
        },
        "inventory_entry": inventory_entry,
        "summary_files": _summary_files(obj),
        "ledger_status": _ledger_status(repo_root, target),
    }
```

- [ ] **Step 4: Re-run the focused `get` test and verify it passes**

Run:

```bash
uv run pytest -q tests/test_app_object_cli.py -k returns_summary_files_and_ledger_status
```

Expected:

```text
1 passed
```

- [ ] **Step 5: Commit the `get` output freeze**

Run:

```bash
git add tests/test_app_object_cli.py ops/domain/app/object_handlers.py
git commit -m "feat: add app object summary and ledger status"
```

### Task 2: Freeze `verify` For Missing Summary Files And Ledger Pointer Drift

**Files:**
- Modify: `tests/test_app_object_cli.py`
- Modify: `ops/domain/app/object_handlers.py`

- [ ] **Step 1: Write the failing test for `verify` rejecting a missing summary file**

Add this test:

```python
    def test_app_object_verify_fails_when_summary_file_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory_with_app(root)
            app_root = root / "sub2api"
            (app_root / "deploy" / "op").mkdir(parents=True, exist_ok=True)
            (app_root / "deploy" / "op" / "contract.yaml").write_text(
                json.dumps(
                    {
                        "docs": {"app_summary_files": {"prod0-main": "docs/OP_LINUX_DEPLOYMENT.prod0-main.md"}}
                    }
                ),
                encoding="utf-8",
            )

            payload = run_cli(
                "app",
                "object",
                "verify",
                "--target",
                "prod0-main",
                "--app",
                "sub2api",
                "--repo-root",
                str(root),
            )

            self.assertEqual(1, payload.returncode, msg=payload.stderr)
            payload_json = json.loads(payload.stdout)
            self.assertIn("summary_files", payload_json["payload"]["failures"])
            self.assertFalse(payload_json["payload"]["checks"]["summary_files"]["ok"])
```

- [ ] **Step 2: Write the failing test for `verify` rejecting ledger pointer drift**

Add this test:

```python
    def test_app_object_verify_fails_when_inventory_pointer_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory_with_app(root)
            app_root = root / "sub2api"
            (app_root / "deploy" / "op").mkdir(parents=True, exist_ok=True)
            (app_root / "deploy" / "op" / "contract.yaml").write_text(
                json.dumps({"docs": {"app_summary_files": {"prod0-main": "docs/OP_LINUX_DEPLOYMENT.prod0-main.md"}}}),
                encoding="utf-8",
            )
            summary_file = app_root / "docs" / "OP_LINUX_DEPLOYMENT.prod0-main.md"
            summary_file.parent.mkdir(parents=True, exist_ok=True)
            summary_file.write_text("# summary\n", encoding="utf-8")
            ledger_root = root / "inventory" / "servers" / "prod0-main" / "ledgers"
            (ledger_root / "apps.md").write_text("# apps\n", encoding="utf-8")

            payload = run_cli(
                "app",
                "object",
                "verify",
                "--target",
                "prod0-main",
                "--app",
                "sub2api",
                "--repo-root",
                str(root),
            )

            self.assertEqual(1, payload.returncode, msg=payload.stderr)
            payload_json = json.loads(payload.stdout)
            self.assertIn("ledger_status", payload_json["payload"]["failures"])
            self.assertFalse(payload_json["payload"]["checks"]["ledger_status"]["ok"])
```

- [ ] **Step 3: Run both focused `verify` tests and verify they fail for the new reasons**

Run:

```bash
uv run pytest -q tests/test_app_object_cli.py -k "summary_file_is_missing or inventory_pointer_is_missing"
```

Expected:

```text
FAIL ... 'summary_files'
FAIL ... 'ledger_status'
```

- [ ] **Step 4: Extend `verify_app_object()` to evaluate `summary_files` and `ledger_status`**

Replace the current body with this shape:

```python
def verify_app_object(repo_root: Path, target: str, app: str) -> dict[str, Any]:
    obj = _object_from_entry(repo_root, target, app)
    inventory_entry = _inventory_entry(repo_root, target, obj.service_key)
    summary_files = _summary_files(obj)
    ledger_status = _ledger_status(repo_root, target)
    failures: list[str] = []
    checks: dict[str, Any] = {}

    contract_exists = obj.contract_file.exists()
    checks["contract_file"] = {"ok": contract_exists, "path": str(obj.contract_file)}
    if not contract_exists:
        failures.append("contract_file")

    has_inventory = bool(inventory_entry)
    checks["inventory_projection"] = {"ok": has_inventory, "service_key": obj.service_key}
    if not has_inventory:
        failures.append("inventory_projection")

    summary_ok = all(bool(item.get("exists")) for item in summary_files)
    checks["summary_files"] = {"ok": summary_ok, "items": summary_files}
    if not summary_ok:
        failures.append("summary_files")

    ledger_ok = (
        bool(ledger_status.get("json_exists"))
        and bool(ledger_status.get("markdown_exists"))
        and bool(ledger_status.get("inventory_pointer_ok"))
    )
    checks["ledger_status"] = {"ok": ledger_ok, **ledger_status}
    if not ledger_ok:
        failures.append("ledger_status")

    return {
        "ok": not failures,
        "checks": checks,
        "failures": failures,
        "evidence": {
            "app": obj.app,
            "target": target,
            "summary_files": summary_files,
            "ledger_status": ledger_status,
        },
    }
```

- [ ] **Step 5: Re-run the focused `verify` tests and verify they pass**

Run:

```bash
uv run pytest -q tests/test_app_object_cli.py -k "summary_file_is_missing or inventory_pointer_is_missing"
```

Expected:

```text
2 passed
```

- [ ] **Step 6: Commit the `verify` strictness change**

Run:

```bash
git add tests/test_app_object_cli.py ops/domain/app/object_handlers.py
git commit -m "feat: verify app object summaries and ledgers"
```

### Task 3: Freeze `refresh-ledger` Writing The Inventory Pointer

**Files:**
- Modify: `tests/test_app_object_cli.py`
- Modify: `ops/domain/app/object_handlers.py`

- [ ] **Step 1: Write the failing test for `refresh-ledger --write` updating `inventory.object_ledgers.apps`**

Add this test:

```python
    def test_app_object_refresh_ledger_writes_inventory_pointer(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory_with_app(root)
            app_root = root / "sub2api"
            (app_root / "deploy" / "op").mkdir(parents=True, exist_ok=True)
            (app_root / "deploy" / "op" / "contract.yaml").write_text("{}", encoding="utf-8")

            payload = run_cli(
                "app",
                "object",
                "refresh-ledger",
                "--target",
                "prod0-main",
                "--repo-root",
                str(root),
                "--write",
            )

            self.assertEqual(0, payload.returncode, msg=payload.stderr)
            payload_json = json.loads(payload.stdout)
            self.assertEqual(
                "inventory/servers/prod0-main/ledgers/apps.json",
                payload_json["payload"]["inventory_pointer"],
            )
            inventory = json.loads((root / "inventory" / "servers" / "prod0-main" / "inventory.json").read_text(encoding="utf-8"))
            self.assertEqual(
                "inventory/servers/prod0-main/ledgers/apps.json",
                inventory["object_ledgers"]["apps"],
            )
```

- [ ] **Step 2: Run the focused `refresh-ledger` test and verify it fails because the pointer is not written**

Run:

```bash
uv run pytest -q tests/test_app_object_cli.py -k refresh_ledger_writes_inventory_pointer
```

Expected:

```text
FAIL ... 'inventory_pointer'
```

- [ ] **Step 3: Update `refresh_app_ledger()` to write and return the expected pointer**

Replace the tail of `refresh_app_ledger()` with:

```python
    inventory_file = server_root / "inventory.json"
    inventory_pointer = f"inventory/servers/{target}/ledgers/apps.json"
    if write:
        ledger_root.mkdir(parents=True, exist_ok=True)
        json_file.write_text(json.dumps(json_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        markdown_file.write_text(markdown_text, encoding="utf-8")
        inventory_payload = json.loads(inventory_file.read_text(encoding="utf-8")) if inventory_file.exists() else {}
        object_ledgers = inventory_payload.get("object_ledgers")
        if not isinstance(object_ledgers, dict):
            object_ledgers = {}
        object_ledgers["apps"] = inventory_pointer
        inventory_payload["object_ledgers"] = object_ledgers
        inventory_file.write_text(json.dumps(inventory_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {
        "target": target,
        "count": len(payload["items"]),
        "json_file": str(json_file),
        "markdown_file": str(markdown_file),
        "inventory_pointer": inventory_pointer,
    }
```

- [ ] **Step 4: Re-run the focused `refresh-ledger` test and verify it passes**

Run:

```bash
uv run pytest -q tests/test_app_object_cli.py -k refresh_ledger_writes_inventory_pointer
```

Expected:

```text
1 passed
```

- [ ] **Step 5: Commit the pointer-write change**

Run:

```bash
git add tests/test_app_object_cli.py ops/domain/app/object_handlers.py
git commit -m "feat: align app ledger pointer with inventory"
```

### Task 4: Full Verification For The Aftercare Slice

**Files:**
- Modify: `tests/test_app_object_cli.py`
- Modify: `ops/domain/app/object_handlers.py`
- Reference: `inventory/apps/catalog.json`
- Reference: `/root/work/sub2api/deploy/op/contract.yaml`
- Reference: `/root/work/sub2api/deploy/op/contract.prod2.yaml`

- [ ] **Step 1: Run the full object test file**

Run:

```bash
uv run pytest -q tests/test_app_object_cli.py
```

Expected:

```text
all tests passed
```

- [ ] **Step 2: Run `app object get` against the real `sub2api` entry on `prod0-main`**

Run:

```bash
uv run python -m ops.cli app object get --target prod0-main --app sub2api --repo-root /root/work/OP_Linux/.worktrees/codex-cli-first-repo-refactor
```

Expected:

```json
{
  "payload": {
    "summary_files": [
      {
        "target": "prod0-main",
        "source": "docs.app_summary_files",
        "exists": true
      }
    ],
    "ledger_status": {
      "json_exists": true,
      "markdown_exists": true,
      "inventory_pointer_ok": true
    }
  }
}
```

- [ ] **Step 3: Run `app object verify` against the real `sub2api` entry on `prod0-main`**

Run:

```bash
uv run python -m ops.cli app object verify --target prod0-main --app sub2api --repo-root /root/work/OP_Linux/.worktrees/codex-cli-first-repo-refactor
```

Expected:

```json
{
  "payload": {
    "ok": true
  }
}
```

- [ ] **Step 4: Run `app object refresh-ledger --write` against the real `sub2api` target**

Run:

```bash
uv run python -m ops.cli app object refresh-ledger --target prod0-main --repo-root /root/work/OP_Linux/.worktrees/codex-cli-first-repo-refactor --write
```

Expected:

```json
{
  "payload": {
    "inventory_pointer": "inventory/servers/prod0-main/ledgers/apps.json"
  }
}
```

- [ ] **Step 5: Re-run `app object verify` after the ledger refresh**

Run:

```bash
uv run python -m ops.cli app object verify --target prod0-main --app sub2api --repo-root /root/work/OP_Linux/.worktrees/codex-cli-first-repo-refactor
```

Expected:

```json
{
  "payload": {
    "ok": true
  }
}
```

- [ ] **Step 6: Commit the final aftercare slice**

Run:

```bash
git add tests/test_app_object_cli.py ops/domain/app/object_handlers.py
git commit -m "feat: complete app object aftercare"
```
