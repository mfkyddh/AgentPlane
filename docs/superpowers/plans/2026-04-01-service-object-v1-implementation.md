# Service Object V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 `OP_Linux` 落地第一版正式 `service` 对象域，统一承接基础设施与宿主服务对象的 `search / get / verify / plan / apply`。

**Architecture:** 新增 `ops.cli service` 作为统一入口，先覆盖 `postgres`、`redis`、`minio`、`mihomo`、`onepanel_openresty`。CLI 层只负责命令形状和结构化 envelope；服务对象注册、能力矩阵、verify/plan/apply 语义下沉到 `ops/domain/service/` 与 `ops/adapters/service/`。实现采用 tests-first，先冻结统一合同，再逐类接入最小 adapter。

**Tech Stack:** Python 3、`argparse`、`pytest`/`unittest`、Docker/systemd/SSH shell adapters、repo-local Markdown docs

---

## File Map

- Create: `ops/cli/service.py`
- Create: `ops/domain/service/models.py`
- Create: `ops/domain/service/registry.py`
- Create: `ops/domain/service/handlers.py`
- Create: `ops/adapters/service/common.py`
- Create: `ops/adapters/service/docker_runtime.py`
- Create: `ops/adapters/service/systemd_runtime.py`
- Create: `tests/test_service_cli.py`
- Modify: `ops/cli/app.py`
- Modify: `tests/test_cli_entrypoints.py`
- Modify: `README.md`
- Modify: `docs/architecture/control-plane.md`
- Modify: `tests/test_docs_no_legacy_terms.py`

### Task 1: 冻结 `service` CLI 合同

**Files:**
- Modify: `tests/test_cli_entrypoints.py`
- Create: `tests/test_service_cli.py`

- [ ] **Step 1: 写失败测试，要求顶层 help 出现 `service`**

在 `tests/test_cli_entrypoints.py` 中加入：

```python
result = run_cli("--help")
self.assertIn("service", result.stdout)

service_help = run_cli("service", "--help")
self.assertIn("search", service_help.stdout)
self.assertIn("get", service_help.stdout)
self.assertIn("verify", service_help.stdout)
self.assertIn("plan", service_help.stdout)
self.assertIn("apply", service_help.stdout)
```

- [ ] **Step 2: 写失败测试，冻结 `service search/get/verify/plan/apply` 顶层 envelope**

在 `tests/test_service_cli.py` 中覆盖：

```python
payload = json.loads(run_cli("service", "search", "--target", "prod0-main", "--repo-root", str(root)).stdout)
self.assertEqual("service", payload["command"])
self.assertEqual("search", payload["action"])
self.assertEqual("prod0-main", payload["target"])
```

以及 `get` / `verify` / `plan` / `apply` 的相同顶层合同。

- [ ] **Step 3: 写失败测试，冻结能力矩阵**

至少覆盖：

- `postgres` 支持 `restart` / `reconcile`
- `mihomo` 支持 `restart` / `reload`
- `onepanel_openresty` 支持 `reload`
- 不支持的 operation 必须明确返回错误

- [ ] **Step 4: 运行 focused tests，确认先红**

Run:

```bash
cd /root/work/OP_Linux/.worktrees/codex-cli-first-repo-refactor
uv run python -m pytest tests/test_cli_entrypoints.py tests/test_service_cli.py -q
```

Expected:
- `service` 命令尚不存在导致失败

### Task 2: 落地 `service` 注册表与统一 handler

**Files:**
- Create: `ops/domain/service/models.py`
- Create: `ops/domain/service/registry.py`
- Create: `ops/domain/service/handlers.py`

- [ ] **Step 1: 定义服务对象模型**

模型至少包含：

```python
@dataclass(frozen=True)
class ServiceDefinition:
    name: str
    runtime_kind: str
    control_plane: str
    supported_operations: tuple[str, ...]
```

- [ ] **Step 2: 从 inventory 建立 `service v1` 注册表**

第一版固定只注册：

```python
SUPPORTED_SERVICES = ("postgres", "redis", "minio", "mihomo", "onepanel_openresty")
```

- [ ] **Step 3: 统一 `search/get/verify/plan/apply` handler 签名**

要求 handler 输出统一结构，不让 adapter 直接决定 CLI envelope。

- [ ] **Step 4: 运行 focused tests**

Run:

```bash
uv run python -m pytest tests/test_service_cli.py -q
```

Expected:
- 仍可能因 CLI 未接线或 adapter 未实现而失败，但模型与 registry 测试开始转绿

### Task 3: 落地最小 runtime adapter

**Files:**
- Create: `ops/adapters/service/common.py`
- Create: `ops/adapters/service/docker_runtime.py`
- Create: `ops/adapters/service/systemd_runtime.py`

- [ ] **Step 1: 实现统一命令执行结果结构**

至少包含：

```python
{
  "display": "...",
  "returncode": 0,
  "stdout": "...",
  "stderr": "...",
  "ok": True,
}
```

- [ ] **Step 2: 实现 Docker 类服务 adapter**

先支持：

- `postgres`
- `redis`
- `minio`
- `onepanel_openresty`

需要的最小动作：

- `inspect` / `verify`
- `restart`
- `reconcile`（仅 repo-managed compose data services）
- `reload`（仅 `onepanel_openresty`）

- [ ] **Step 3: 实现 systemd 类服务 adapter**

先支持：

- `mihomo`

需要的最小动作：

- `verify`
- `restart`
- `reload`

- [ ] **Step 4: 运行 focused tests**

Run:

```bash
uv run python -m pytest tests/test_service_cli.py -q
```

Expected:
- adapter 行为相关测试开始转绿

### Task 4: 接线 `ops.cli service`

**Files:**
- Create: `ops/cli/service.py`
- Modify: `ops/cli/app.py`

- [ ] **Step 1: 添加 `service` parser**

命令形状固定为：

```python
service search --target <target>
service get --target <target> --name <service>
service verify --target <target> --name <service>
service plan --target <target> --name <service> --operation <op>
service apply --target <target> --name <service> --operation <op> --execute
```

- [ ] **Step 2: 接线统一 handler**

要求：

- `command = "service"`
- `action` 为 `search/get/verify/plan/apply`
- 失败时返回稳定错误或 exit code

- [ ] **Step 3: 生产 `apply` 强制 `--execute`**

没有 `--execute` 时只能返回 plan，不得落地。

- [ ] **Step 4: 运行 focused tests**

Run:

```bash
uv run python -m pytest tests/test_cli_entrypoints.py tests/test_service_cli.py -q
```

Expected:
- `service` CLI 合同通过

### Task 5: 文档与合同同步

**Files:**
- Modify: `README.md`
- Modify: `docs/architecture/control-plane.md`
- Modify: `tests/test_docs_no_legacy_terms.py`

- [ ] **Step 1: 把 `service` 域写入 active 入口**

最小文案应承认：

- `service` 是正式对象域
- 第一版只覆盖基础设施与宿主服务对象

- [ ] **Step 2: 更新文档合同测试**

确保 active 文档中出现：

```python
self.assertIn("uv run python -m ops.cli service search --target", text)
```

- [ ] **Step 3: 运行文档相关回归**

Run:

```bash
uv run python -m pytest tests/test_docs_no_legacy_terms.py tests/test_wsl_first_docs.py -q
```

Expected:
- 文档合同通过

### Task 6: 最小全链路回归

**Files:**
- Verify: `ops/cli/service.py`
- Verify: `ops/domain/service/registry.py`
- Verify: `ops/adapters/service/docker_runtime.py`
- Verify: `ops/adapters/service/systemd_runtime.py`
- Verify: `tests/test_service_cli.py`

- [ ] **Step 1: 运行核心回归**

Run:

```bash
cd /root/work/OP_Linux/.worktrees/codex-cli-first-repo-refactor
uv run python -m pytest \
  tests/test_cli_entrypoints.py \
  tests/test_service_cli.py \
  tests/test_docs_no_legacy_terms.py \
  tests/test_wsl_first_docs.py \
  tests/test_host_cli.py \
  tests/test_app_cli.py \
  -q
```

Expected:
- 新旧对象域共存下全部通过

- [ ] **Step 2: 做 CLI smoke**

Run:

```bash
uv run python -m ops.cli --help
uv run python -m ops.cli service --help
```

Expected:
- help 中出现 `service`
- `service` 子命令齐全

- [ ] **Step 3: 审核变更范围**

Run:

```bash
git status --short
```

Expected:
- 只包含本计划内文件
