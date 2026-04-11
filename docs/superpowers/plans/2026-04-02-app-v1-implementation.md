# App V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 `OP_Linux` 增加正式 `app v1` 双面入口，收口 `app object` 与 `app delivery`，并把公开输入从 `--contract` 收口到 `target + app`。

**Architecture:** 保留 `ops/cli/apps.py` 作为 `app` 域 parser 壳，新增 `ops/domain/app/` 承载 catalog、object 和 delivery 逻辑。`app object` 负责受管应用对象的声明与投影核验，`app delivery` 负责现有交付链；两者都通过 tracked `inventory/apps/catalog.json` 解析 `target + app -> repo_root + contract`。

**Tech Stack:** Python 3.12, `argparse`, `unittest`, 现有 `ops.cli.apps` delivery 实现, 现有 `ops.cli.operations` ledger, 现有 `yaml`/`json` helpers

---

### Task 1: Freeze The Public CLI Contract

**Files:**
- Create: `tests/test_app_object_cli.py`
- Modify: `tests/test_cli_entrypoints.py`
- Modify: `tests/test_app_cli.py`

- [ ] **Step 1: 写顶层帮助与 surface 形状失败测试**

在 `tests/test_cli_entrypoints.py` 先固定新的公开语法：

```python
app_help = run_cli("app", "--help")
self.assertIn("object", app_help.stdout)
self.assertIn("delivery", app_help.stdout)

app_object_help = run_cli("app", "object", "--help")
self.assertIn("search", app_object_help.stdout)
self.assertIn("get", app_object_help.stdout)
self.assertIn("verify", app_object_help.stdout)
self.assertIn("refresh-ledger", app_object_help.stdout)

app_delivery_help = run_cli("app", "delivery", "--help")
self.assertIn("validate-contract", app_delivery_help.stdout)
self.assertIn("build-artifact", app_delivery_help.stdout)
self.assertIn("deploy", app_delivery_help.stdout)
self.assertIn("doc-sync", app_delivery_help.stdout)
```

- [ ] **Step 2: 运行帮助测试，确认当前失败**

Run: `uv run python -m pytest tests/test_cli_entrypoints.py -q -k app`

Expected: FAIL，因为当前 `app` 还是单层动作面，没有 `object` / `delivery` surface。

- [ ] **Step 3: 写 `app object` 最小行为失败测试**

在 `tests/test_app_object_cli.py` 先固定三个最小入口：

```python
payload = run_cli("app", "object", "search", "--target", "prod0-main", "--repo-root", str(root))
self.assertEqual("app", json.loads(payload.stdout)["command"])
self.assertEqual("object.search", json.loads(payload.stdout)["action"])
```

```python
payload = run_cli("app", "object", "get", "--target", "prod0-main", "--app", "sub2api", "--repo-root", str(root))
self.assertEqual("sub2api", json.loads(payload.stdout)["payload"]["app"]["app"])
```

```python
payload = run_cli("app", "object", "verify", "--target", "prod0-main", "--app", "sub2api", "--repo-root", str(root))
self.assertFalse(json.loads(payload.stdout)["payload"]["ok"])
```

- [ ] **Step 4: 把 `tests/test_app_cli.py` 的公开入口调用先冻结成 `delivery` 语法**

把现有代表性调用先改成新语法，至少覆盖：

```python
run_cli("app", "delivery", "validate-contract", "--target", "prod0-main", "--app", "sub2api", "--repo-root", str(root))
run_cli("app", "delivery", "build-artifact", "--target", "prod0-main", "--app", "sub2api", "--repo-root", str(root), "--image-tag", "verify-tag")
run_cli("app", "delivery", "deploy", "--target", "prod0-main", "--app", "sub2api", "--repo-root", str(root), "--dry-run")
```

- [ ] **Step 5: 运行聚焦测试，确认按预期失败**

Run: `uv run python -m pytest tests/test_cli_entrypoints.py tests/test_app_object_cli.py tests/test_app_cli.py -q -k "app and not doc_sync"`

Expected: FAIL，因为 parser 还没切到双 surface，且还没有 catalog。

### Task 2: Add Tracked App Catalog And Catalog Reader

**Files:**
- Create: `ops/domain/app/catalog.py`
- Create: `inventory/apps/catalog.json`
- Modify: `tests/test_app_object_cli.py`
- Modify: `tests/test_app_cli.py`

- [ ] **Step 1: 在对象测试里写 `catalog` 夹具与解析失败测试**

在 `tests/test_app_object_cli.py` 新增仓库夹具：

```python
def write_app_catalog(root: Path) -> Path:
    catalog_root = root / "inventory" / "apps"
    catalog_root.mkdir(parents=True, exist_ok=True)
    file = catalog_root / "catalog.json"
    file.write_text(
        json.dumps(
            {
                "apps": [
                    {
                        "app": "sub2api",
                        "repo_name": "sub2api",
                        "repo_root": str(root / "sub2api"),
                        "service_key": "sub2api",
                        "contracts": {"prod0-main": "deploy/op/contract.yaml", "wsl": "deploy/op/contract.yaml"},
                    }
                ]
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return file
```

并固定缺失 catalog 的错误：

```python
result = run_cli("app", "object", "get", "--target", "prod0-main", "--app", "sub2api", "--repo-root", str(root))
self.assertNotEqual(result.returncode, 0)
self.assertIn("catalog", result.stderr.lower())
```

- [ ] **Step 2: 运行 catalog 相关测试，确认当前失败**

Run: `uv run python -m pytest tests/test_app_object_cli.py -q -k catalog`

Expected: FAIL，因为 `ops.domain.app.catalog` 尚不存在。

- [ ] **Step 3: 实现最小 catalog 读取器**

在 `ops/domain/app/catalog.py` 增加统一解析入口：

```python
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AppCatalogEntry:
    app: str
    repo_name: str
    repo_root: Path
    service_key: str
    contracts: dict[str, str]


def load_app_catalog(repo_root: Path) -> list[AppCatalogEntry]:
    catalog_file = repo_root / "inventory" / "apps" / "catalog.json"
    payload = json.loads(catalog_file.read_text(encoding="utf-8"))
    return [_entry_from_payload(item) for item in payload.get("apps", [])]


def resolve_app_contract(repo_root: Path, *, target: str, app: str) -> tuple[AppCatalogEntry, Path]:
    for entry in load_app_catalog(repo_root):
        if entry.app != app:
            continue
        contract_rel = entry.contracts.get(target)
        if contract_rel:
            return entry, entry.repo_root / contract_rel
    raise ValueError(f"app catalog missing target mapping: target={target} app={app}")
```

- [ ] **Step 4: 补一份最小 tracked catalog 样本**

在 `inventory/apps/catalog.json` 提交一个最小真实样本：

```json
{
  "apps": []
}
```

要求：
- 文件存在并 tracked
- 允许后续增量登记真实 app
- 不在本轮写自动发现逻辑

- [ ] **Step 5: 让 catalog 测试转绿**

Run: `uv run python -m pytest tests/test_app_object_cli.py -q -k catalog`

Expected: PASS

### Task 3: Implement App Object Surface

**Files:**
- Create: `ops/domain/app/models.py`
- Create: `ops/domain/app/object_handlers.py`
- Modify: `ops/cli/apps.py`
- Modify: `tests/test_app_object_cli.py`

- [ ] **Step 1: 写 `search / get / verify / refresh-ledger` 的失败测试**

在 `tests/test_app_object_cli.py` 固定这些行为：

```python
payload = json.loads(run_cli("app", "object", "search", "--target", "prod0-main", "--repo-root", str(root)).stdout)
self.assertEqual(
    [
        {
            "app": "sub2api",
            "service_key": "sub2api",
            "contract_file": str(app_root / "deploy" / "op" / "contract.yaml"),
            "control_plane": "compose",
            "public_url": "https://token.zzzai.cloud:8443",
        }
    ],
    payload["payload"]["items"],
)
```

```python
payload = json.loads(run_cli("app", "object", "get", "--target", "prod0-main", "--app", "sub2api", "--repo-root", str(root)).stdout)
self.assertEqual("sub2api", payload["payload"]["app"]["app"])
self.assertEqual("sub2api", payload["payload"]["app"]["service_key"])
self.assertIn("inventory_entry", payload["payload"])
self.assertIn("summary_files", payload["payload"])
```

```python
payload = json.loads(run_cli("app", "object", "verify", "--target", "prod0-main", "--app", "sub2api", "--repo-root", str(root)).stdout)
self.assertFalse(payload["payload"]["ok"])
self.assertIn("inventory_projection", payload["payload"]["failures"])
```

```python
payload = json.loads(run_cli("app", "object", "refresh-ledger", "--target", "prod0-main", "--repo-root", str(root), "--write").stdout)
self.assertIn("apps.json", payload["payload"]["json_file"])
self.assertIn("apps.md", payload["payload"]["markdown_file"])
```

- [ ] **Step 2: 运行对象测试，确认当前失败**

Run: `uv run python -m pytest tests/test_app_object_cli.py -q`

Expected: FAIL，因为 object handlers 和 ledger 刷新逻辑还没接上。

- [ ] **Step 3: 实现对象模型与聚合 handler**

在 `ops/domain/app/models.py` 定义最小对象：

```python
@dataclass(frozen=True)
class AppObject:
    app: str
    target: str
    repo_name: str
    repo_root: Path
    service_key: str
    contract_file: Path
```

在 `ops/domain/app/object_handlers.py` 提供：

```python
def search_apps(repo_root: Path, target: str) -> dict[str, Any]:
    return {"target": target, "items": _search_items(repo_root, target)}


def get_app(repo_root: Path, target: str, app: str) -> dict[str, Any]:
    obj = _load_app_object(repo_root, target, app)
    return {"app": _object_payload(obj), "inventory_entry": _inventory_entry(repo_root, obj), "summary_files": _summary_files(obj)}


def verify_app_object(repo_root: Path, target: str, app: str) -> dict[str, Any]:
    obj = _load_app_object(repo_root, target, app)
    return _verify_object(repo_root, obj)


def refresh_app_ledger(repo_root: Path, target: str, write: bool) -> dict[str, Any]:
    return _refresh_ledger(repo_root, target, write=write)
```

`verify_app_object()` 只做：
- catalog 命中
- contract 可解析
- `inventory.services.<service_key>` 存在
- 关键投影字段和 contract 对齐

- [ ] **Step 4: 在 `ops/cli/apps.py` 增加 `app object` parser 与路由**

最小 parser 形状：

```python
app_subparsers = app_parser.add_subparsers(dest="app_surface", required=True)
object_parser = app_subparsers.add_parser("object", help="受管应用对象")
object_subparsers = object_parser.add_subparsers(dest="app_object_action", required=True)
```

路由形状：

```python
if args.app_surface == "object" and args.app_object_action == "search":
    return {"command": "app", "action": "object.search", "target": args.target, "payload": search_apps(repo_root, args.target)}
```

- [ ] **Step 5: 让对象测试转绿**

Run: `uv run python -m pytest tests/test_app_object_cli.py tests/test_cli_entrypoints.py -q`

Expected: PASS

### Task 4: Migrate Delivery Surface Without Changing Delivery Semantics

**Files:**
- Create: `ops/domain/app/delivery_handlers.py`
- Modify: `ops/cli/apps.py`
- Modify: `tests/test_app_cli.py`

- [ ] **Step 1: 在 `tests/test_app_cli.py` 先补一组 delivery 入口失败测试**

固定以下行为：

```python
result = run_cli("app", "delivery", "validate-contract", "--target", "prod0-main", "--app", "sub2api", "--repo-root", str(root))
self.assertEqual("delivery.validate-contract", json.loads(result.stdout)["action"])
```

```python
result = run_cli("app", "delivery", "deploy", "--target", "prod0-main", "--app", "sub2api", "--repo-root", str(root), "--dry-run")
self.assertEqual("delivery.deploy", json.loads(result.stdout)["action"])
```

```python
result = run_cli("app", "delivery", "verify", "--target", "prod0-main", "--app", "sub2api", "--repo-root", str(root), "--execute")
self.assertEqual("delivery.verify", json.loads(result.stdout)["action"])
```

- [ ] **Step 2: 运行 app delivery 测试，确认当前失败**

Run: `uv run python -m pytest tests/test_app_cli.py -q -k "validate_contract or build_artifact or render_runtime or deploy or verify or rollback"`

Expected: FAIL，因为公开入口还是旧 parser，且动作还依赖 `--contract`。

- [ ] **Step 3: 把现有 delivery 逻辑搬到 `ops/domain/app/delivery_handlers.py`**

从 `ops/cli/apps.py` 迁出这些入口：

```python
def validate_contract_for_app(repo_root: Path, *, target: str, app: str) -> dict[str, Any]:
    _, contract_file = resolve_app_contract(repo_root, target=target, app=app)
    contract = validate_contract(contract_file, repo_root=repo_root, target=target)
    return {"app": app, "contract_file": str(contract_file), "contract": contract}


def build_artifact_for_app(repo_root: Path, *, target: str, app: str, image_tag: str | None, auto_version: bool, dry_run: bool) -> dict[str, Any]:
    _, contract_file = resolve_app_contract(repo_root, target=target, app=app)
    contract = validate_contract(contract_file, repo_root=repo_root, target=target)
    return build_artifact(contract, repo_root=repo_root, target=target, image_tag=image_tag, auto_version=auto_version, dry_run=dry_run)


def render_runtime_for_app(repo_root: Path, *, target: str, app: str, image_ref: str | None) -> dict[str, Any]:
    _, contract_file = resolve_app_contract(repo_root, target=target, app=app)
    contract = validate_contract(contract_file, repo_root=repo_root, target=target)
    return render_runtime(contract, repo_root=repo_root, target=target, image_ref=image_ref)


def deploy_for_app(repo_root: Path, *, target: str, app: str, image_ref: str | None, dry_run: bool, execute: bool) -> dict[str, Any]:
    _, contract_file = resolve_app_contract(repo_root, target=target, app=app)
    contract = validate_contract(contract_file, repo_root=repo_root, target=target)
    return deploy_app(contract, repo_root=repo_root, target=target, image_ref=image_ref, dry_run=dry_run, execute=execute)
```

实现方式：
- 先用 `resolve_app_contract()` 找到 contract
- 再复用现有 `validate_contract()`、`build_artifact()`、`render_runtime()`、`deploy_app()`、`verify_app()`、`rollback_app()`、`inventory_refresh()`、`doc_sync()`
- 不改内部交付语义，只改公开入口和调用边界

- [ ] **Step 4: 在 `ops/cli/apps.py` 增加 `app delivery` parser 与路由**

最小 parser 形状：

```python
delivery_parser = app_subparsers.add_parser("delivery", help="应用正式交付流程")
delivery_subparsers = delivery_parser.add_subparsers(dest="app_delivery_action", required=True)
```

以 `validate-contract` 为例：

```python
validate = delivery_subparsers.add_parser("validate-contract", help="校验应用交付合同")
validate.add_argument("--target", required=True, choices=SUPPORTED_APP_TARGETS)
validate.add_argument("--app", required=True, help="catalog 中登记的 app")
validate.add_argument("--repo-root", default=".", help="OP_Linux 仓库根目录")
```

- [ ] **Step 5: 把 `tests/test_app_cli.py` 中剩余公开调用统一切到 `delivery` 语法**

统一替换为：

```python
run_cli("app", "delivery", "<action>", "--target", "<target>", "--app", "<app>", "--repo-root", str(root), ...)
```

要求：
- 不再保留旧 `app <action>` 公开测试
- 不新增 `--contract` 兼容公开入口
- `write_contract()` 继续只负责在夹具里生成合同文件，不直接作为 CLI 输入

- [ ] **Step 6: 让 delivery 回归测试转绿**

Run: `uv run python -m pytest tests/test_app_cli.py -q`

Expected: PASS

### Task 5: Sync Docs, Skills, And Catalog Contract

**Files:**
- Modify: `README.md`
- Modify: `docs/architecture/control-plane.md`
- Modify: `docs/architecture/op-linux-app-collaboration.md`
- Modify: `docs/runbooks/app-project-delivery-workflow.md`
- Modify: `.codex/skills/app-delivery-ops/SKILL.md`
- Modify: `.codex/skills/inventory-ledger-ops/SKILL.md`
- Modify: `tests/test_onepanel_plugin_and_skills.py`

- [ ] **Step 1: 先写文档与 skill 合同失败测试**

在 `tests/test_onepanel_plugin_and_skills.py` 固定新入口文本：

```python
self.assertIn("uv run python -m ops.cli app object search --target <target>", repo_skill_text)
self.assertIn("uv run python -m ops.cli app delivery validate-contract --target <target> --app <app>", repo_skill_text)
self.assertIn("uv run python -m ops.cli app delivery inventory-refresh --target <target> --app <app>", repo_skill_text)
```

并固定 README 口径：

```python
self.assertIn("`app` 是正式域；第一版公开 `object` 与 `delivery` 两个 surface", readme_text)
```

- [ ] **Step 2: 运行文档与 skill 测试，确认当前失败**

Run: `uv run python -m pytest tests/test_onepanel_plugin_and_skills.py -q`

Expected: FAIL，因为 README、architecture、skills 还没切到 `object + delivery` 口径。

- [ ] **Step 3: 同步 README、architecture、runbook 和 skills**

README 至少补：

```markdown
- `app` 是正式域；第一版公开 `object` 与 `delivery` 两个 surface。
- `app object` 负责受管应用对象与投影核验。
- `app delivery` 负责合同校验、构建、部署、回滚、交付后核验和投影回写。
```

skill 至少补：

```markdown
uv run python -m ops.cli app object get --target <target> --app <app> --repo-root /root/work/OP_Linux
uv run python -m ops.cli app delivery deploy --target <target> --app <app> --repo-root /root/work/OP_Linux --dry-run
uv run python -m ops.cli app delivery verify --target <target> --app <app> --repo-root /root/work/OP_Linux --execute
```

- [ ] **Step 4: 让文档与 skill 测试转绿**

Run: `uv run python -m pytest tests/test_onepanel_plugin_and_skills.py -q`

Expected: PASS

### Task 6: Final Verification And Cleanup

**Files:**
- Verify only

- [ ] **Step 1: 跑 app 对象面与交付面的聚焦回归**

Run:
- `uv run python -m pytest tests/test_app_object_cli.py -q`
- `uv run python -m pytest tests/test_app_cli.py -q`
- `uv run python -m pytest tests/test_cli_entrypoints.py -q`

Expected: PASS

- [ ] **Step 2: 跑文档与 skill 合同测试**

Run: `uv run python -m pytest tests/test_onepanel_plugin_and_skills.py -q`

Expected: PASS

- [ ] **Step 3: 做最终范围自检**

Checklist:
- 公开入口已经切到 `app object` / `app delivery`
- `target + app` 已成为公开稳定引用
- 未新增 compat / alias / wrapper
- 未进入应用业务仓库运行面
- 未进入应用层运行面
- `app object verify` 没有混入 live deploy probe
- `app delivery` 保持现有 Docker / Compose 交付语义
