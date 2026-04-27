---
status: active
owner: AgentPlane maintainers
last_verified: 2026-04-25
superseded_by: null
audience: both
---

# 测试治理规范

结论：测试按 unit / integration / e2e / smoke 分层，默认并行运行必须保持离线、确定性，并且新增测试要先选择合适 marker 与文件归属。

> 📐 本文档定义测试金字塔、并行策略、文件组织规则和 marker 体系。
> AI 执行测试相关变更时必须遵守。

---

## 1. 测试金字塔与并行契约

| 层级 | Marker | 特征 | 目标耗时 | 并行策略 |
|------|--------|------|----------|----------|
| **单元** | `@pytest.mark.unit` | 纯函数、domain 对象、无 I/O、无全局可变状态 | < 10ms | `-n auto`，worker 间零共享 |
| **集成** | `@pytest.mark.integration` | 模块组合、mock 外部依赖、允许 tmpdir、不走完整 CLI | < 100ms | `-n auto --dist loadfile` |
| **契约/E2E** | `@pytest.mark.e2e` | 完整 CLI 端到端、真实子进程 | 可 > 1s | `-n 4`，限制并发进程数 |
| **冒烟** | `@pytest.mark.smoke` | 每个模块最快的 1-2 个 E2E | — | 同 e2e |

**并行设计原则**：分层时就规定该层必须满足何种并行契约，而非"测完再评估能否并行"。

### 并行安全约束

| 层级 | 约束 |
|------|------|
| unit | 禁止读写文件系统、禁止修改 `os.environ`、禁止访问全局单例 |
| integration | 写入必须走 `tmp_path` / `cli_tmpdir`，禁止写入 `REPO_ROOT`；`monkeypatch` 只影响当前 worker |
| e2e | 必须传 `--repo-root={tmpdir}` 给 CLI；禁止修改 `REPO_ROOT` 下任何文件 |

---

## 2. Marker 定义

```python
@pytest.mark.unit          # 纯函数/无 I/O / 无全局状态
@pytest.mark.integration   # 模块组合 / mock 外部 / 允许 tmpdir
@pytest.mark.e2e           # 完整 CLI 进程 / 可接受 >1s
@pytest.mark.smoke         # 每个模块最快的 e2e，用于快速回归
```

### 现有 marker（保留）

- `live_gate`：需要真实 WSL/SSH/Docker
- `integration_wsl`：需要真实 WSL/Linux
- `integration_remote`：需要真实远程主机
- `external_app`：需要外部应用仓库
- `docker_required`：需要 Docker daemon
- `ssh_required`：需要 SSH 连接

这些 marker 与层级 marker **正交组合**。例如：`@pytest.mark.e2e @pytest.mark.ssh_required`。

### 默认排除

`pyproject.toml` 的 `addopts` 默认排除 `live_gate` / `integration_wsl` / `integration_remote` / `external_app` / `docker_required` / `ssh_required`。
层级 marker（unit/integration/e2e/smoke）**不在排除列表中**。

---

## 3. 文件组织规则

### 规则

1. **一个领域一个文件**：禁止按操作或环境拆分测试文件。
2. **环境是参数，不是文件名**：
   ```python
   # ✅ 正确
   @pytest.mark.parametrize("target", ["prod0-main", "prod2-main", "wsl"])
   def test_lifecycle(target): ...

   # ❌ 错误
   test_app_lifecycle_prod0_main.py
   test_app_lifecycle_prod2_main.py
   test_app_lifecycle_wsl.py
   ```
3. **操作是类或参数，不是文件名**：
   ```python
   # ✅ 正确
   class TestBuild: ...
   class TestValidate: ...

   # ❌ 错误
   test_app_delivery_build_cli.py
   test_app_delivery_validate_cli.py
   ```
4. **单文件行数上限 300 行**：超过则拆分为子领域，而非按操作/环境拆分。
5. **新增测试文件**必须在 PR 中说明"为什么不能合并到现有文件"。

### 当前领域 → 文件映射

| 领域 | 合并前 | 合并后 |
|------|--------|--------|
| app_delivery | 7 个文件 | `test_app_delivery.py` |
| app_lifecycle | 4 个文件 | `test_app_lifecycle.py` |
| runtime | 已聚合 | 保持 |
| 其他 | 各 1 个文件 | 保持 |

---

## 4. Fixture 体系

### 核心 fixture

```python
@pytest.fixture
def cli_tmpdir(tmp_path: Path) -> Path:
    """每个测试（每个 worker）独立的迷你仓库结构。"""
    (tmp_path / "inventory" / "servers").mkdir(parents=True)
    (tmp_path / "secrets" / "ssh").mkdir(parents=True)
    (tmp_path / "templates").mkdir(parents=True)
    return tmp_path
```

### 规则

- 所有 CLI 测试的 `--repo-root` 必须指向 `cli_tmpdir`，禁止使用 `REPO_ROOT`。
- `tests/support/` 下的 helper 函数逐步迁移为 fixture。
- 目标：新增一个测试不需要写超过 5 行 setup。

---

## 5. CLI 入口

```bash
agentplane test          # 等价于 agentplane test fast
agentplane test fast     # unit + integration, -n auto
agentplane test full     # 全量, unit/integration 并行 + e2e -n 4
agentplane test e2e      # 只跑 e2e, -n 4
agentplane test smoke    # 只跑 smoke, -n 4
```

---

## 6. 门禁规则

| 规则 | 触发条件 | 动作 |
|------|----------|------|
| 无 marker | 新增测试未标记 unit/integration/e2e | CI warning → 后期升级为 error |
| 单文件膨胀 | 测试文件 > 300 行 | CI warning |
| unit 层违规 | unit 测试读写文件或修改全局状态 | Code Review 拒绝 |
| 同领域拆文件 | 同领域出现按操作/环境拆分的新文件 | Code Review 拒绝 |

---

## 7. 实施路线

| 优先级 | 动作 | 状态 |
|--------|------|------|
| P0 | 安装 pytest-xdist，给现有全部测试打 `e2e` marker | ✅ |
| P0 | 验证 `pytest -n 4` 效果 | ✅ |
| P1 | 合并 `test_app_delivery_*` → `test_app_delivery.py` | ✅ |
| P1 | 合并 `test_app_lifecycle_*` → `test_app_lifecycle.py` | ✅ |
| P2 | 建立 `conftest.py` fixture 体系 | ✅ |
| P2 | 提取 delivery handler 纯逻辑为 `unit` 层（示范） | ✅ |
| P3 | 扩展 `agentplane test` CLI | ✅ |
| P3 | AGENTS.md 新增 🔴 规则 | ✅ |
