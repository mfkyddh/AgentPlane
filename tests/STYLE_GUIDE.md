# 测试风格指南

> 本指南定义 AgentPlane 测试的编写规范。所有新测试必须遵循本指南。
> 来源：2026-05-08 测试体系重构（6,339 行 → 18 文件，755 测试）中提炼的经验。

---

## 1. 测试风格

**新测试必须使用 pytest-native 风格**，不继承 `unittest.TestCase`。

```python
# ✓ 正确
class TestFeatureX:
    def test_does_something(self) -> None:
        assert result == expected

# ✗ 错误
class TestFeatureX(unittest.TestCase):
    def test_does_something(self) -> None:
        self.assertEqual(result, expected)
```

**例外**：已有 `unittest.TestCase` 类不需要迁移，但新增方法应使用 `assert` 风格。

---

## 2. 标记规范

使用文件级 `pytestmark`，不在每个方法上重复标记。

```python
# ✓ 正确 — 文件顶部
pytestmark = pytest.mark.e2e

# ✗ 错误 — 每个方法上
class TestFeature:
    @pytest.mark.e2e
    def test_one(self): ...

    @pytest.mark.e2e
    def test_two(self): ...
```

---

## 3. 断言风格

使用 `assert` 语句，不使用 `self.assert*`。

```python
# ✓ 正确
assert result == expected
assert "error" in str(exc_info.value)
assert len(items) == 3

# ✗ 错误
self.assertEqual(result, expected)
self.assertIn("error", str(exc_info.value))
self.assertEqual(len(items), 3)
```

---

## 4. 临时目录

使用 `tmp_path` fixture 或 `tempfile.TemporaryDirectory()`，**禁止** `tempfile.mkdtemp()`。

```python
# ✓ 正确 — 使用 fixture
def test_something(self, tmp_path: Path) -> None:
    (tmp_dir / "file.txt").write_text("data")

# ✓ 正确 — 使用 context manager
def test_something(self) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        ...

# ✗ 错误 — 无清理
def test_something(self) -> None:
    tmp = tempfile.mkdtemp()
    root = Path(tmp)
    ...
```

**来源**：`test_workbook_parsing.py` 使用 `mkdtemp()` 导致 `/tmp` 下残留目录，修复为 `tmp_path`。

---

## 5. 导入顺序

```python
# 1. 标准库
import json
import tempfile
from pathlib import Path

# 2. 第三方
import pytest
import yaml

# 3. agentplane
from agentplane.domain.app.runtime import _secrets_root

# 4. tests.support
from tests.support.constants import FAKE_HOST_BINDING
from tests.support.cli import run_agentplane_cli as run_cli
```

---

## 6. 共享常量

使用 `tests/support/constants.py` 中定义的常量，禁止在测试中硬编码 fixture 值。

```python
# ✓ 正确
from tests.support.constants import CONTAINER_SUB2API, FAKE_HOST_BINDING
assert container == CONTAINER_SUB2API

# ✗ 错误
assert container == "sub2api-prod"
```

**规则**：
- **fixture 输入值**（域名、IP、端口、容器名、应用 ID）→ 集中到 `tests/support/constants.py`
- **断言期望值** → 留在测试内，不进常量文件
- **bash heredoc 内的值** → 必须保持硬编码（见第 10 节）

---

## 7. 文件命名

- 测试文件：`test_<module>.py`
- 测试类：`Test<Feature>`
- 测试方法：`test_<behavior>`
- conftest：`conftest.py`

---

## 8. 测试粒度

| 层级 | 标记 | 耗时 | 说明 |
|------|------|------|------|
| unit | `@pytest.mark.unit` | <10ms | 纯函数，无 I/O |
| integration | `@pytest.mark.integration` | <100ms | 模块组合，mock 外部 |
| e2e | `@pytest.mark.e2e` | >1s | 完整 CLI 子进程 |

---

## 9. 子目录 conftest.py

每个测试子目录应有 `conftest.py`，提供该目录专用的 fixture。

```python
# tests/app/conftest.py
import pytest
from pathlib import Path

@pytest.fixture
def app_tmpdir(tmp_path: Path) -> Path:
    """Create app test directory skeleton."""
    (tmp_path / "inventory" / "servers").mkdir(parents=True)
    (tmp_path / "secrets" / "ssh").mkdir(parents=True)
    return tmp_path
```

**职责划分**：
| 位置 | 用途 |
|------|------|
| `tests/support/` | 跨目录共享的 setup/assertion helper |
| 子目录 `conftest.py` | 仅该目录使用的 fixture |
| 测试文件内 | 仅该类使用的 private helper（`_` 前缀） |

---

## 10. 文件规模上限

| 维度 | 上限 | 警告阈值 | 处理方式 |
|------|------|---------|---------|
| 单测试文件 | **500 行** | 400 行 | 拆分为多个文件 |
| 单 support 模块 | **400 行** | 300 行 | 拆分职责 |
| 单 conftest.py | **100 行** | 80 行 | fixture 过多说明目录组织有问题 |
| 单测试类 | **30 方法** | 20 方法 | 拆分为多个类 |

**来源**：`test_app_delivery.py`（3,189 行）拆分为 7 个文件后，定位效率大幅提升。拆分后最大文件 `test_delivery_deploy.py` 为 670 行（部署+回滚逻辑耦合），其余均在 500 以内。

**拆分原则**：
- 按功能/命令拆分，不按"行数均匀切割"
- 每个拆分文件保留 `pytestmark` 和必要的 import
- helper 函数随使用它的类走，不留在原文件

---

## 11. Helper 函数归属

当测试文件中存在独立函数（不在 class 内）时，必须明确归属：

| 场景 | 归属 | 示例 |
|------|------|------|
| 跨目录共享 | `tests/support/` | `write_fake_command()`, `run_cli()` |
| 仅该目录使用 | 子目录 `conftest.py` | `app_tmpdir`, `fake_ssh_bin_dir` |
| 仅该文件使用 | 文件内，`_` 前缀 | `_write_catalog()`, `_seed_templates()` |
| 跨文件但不跨目录 | 同目录 support 模块 | `tests/app/app_helpers.py` |

**拆分文件时的陷阱**：helper 函数定义在两个 class 之间时，不属于任何 class。正则提取 class 会遗漏这些函数，必须手动确认归属。

**来源**：拆分 `test_repo_cli.py`、`test_app_object.py`、`test_infra_cli.py` 时反复遇到 helper 遗漏问题，修正了 3+ 次。

---

## 12. Bash Heredoc 例外

**bash heredoc 字符串内的值必须保持硬编码**，不能用 Python 常量替换。

```python
# ✓ 正确 — heredoc 内硬编码
FAKE_SSH_BODY = """#!/bin/bash
echo '{"container": "sub2api-prod"}'
"""

# ✗ 错误 — heredoc 内用 Python 常量
FAKE_SSH_BODY = f"""#!/bin/bash
echo '{{"container": "{CONTAINER_SUB2API}"}}'
"""
```

**原因**：Python 常量在运行时解析，写入文件后 bash 脚本里是字面文本 `CONTAINER_SUB2API` 而不是 `sub2api-prod`。

**来源**：尝试替换 `app_delivery.py` 中 `FAKE_SERVICE_SSH_BODY` 内的容器名，导致 bash 脚本失败，立即回滚。

**例外处理**：如果 heredoc 内的值确实需要动态化，使用 f-string 并在运行时构建，不作为模块级常量。

---

## 13. 覆盖率策略

`fail_under` 必须设在当前实际值以下，然后阶梯提升：

| 时间点 | 目标 | 重点 |
|--------|------|------|
| 当前 | 25% | 基线（2026-05-08 实际 28.76%） |
| 1 个月后 | 35% | 补充 toolchain-setup 测试 |
| 3 个月后 | 50% | domain/ 模块覆盖 |
| GA 前 | 70% | 核心路径全覆盖 |

**规则**：
- 每次提升 `fail_under` 必须同步补充测试，不能只改数字
- 覆盖率报告使用 `--cov --cov-report=term-missing`
- `.coverage` 文件必须在 `.gitignore` 中

**来源**：初始设 `fail_under = 70`，实际覆盖率 28.76%，CI 直接失败。改为 `fail_under = 25` 后通过。

---

## 14. 并行执行隔离

测试间必须零共享状态，确保 `pytest-xdist` 并行执行安全：

| 规则 | 原因 |
|------|------|
| 无全局可变状态 | 多 worker 并行会竞争 |
| 无文件系统副作用 | worker 间文件可见 |
| 使用 `tmp_path` 隔离 | 每个测试独立目录 |
| 同文件测试同 worker | `--dist loadfile` 保证 |
| 避免隐式执行顺序依赖 | 并行时顺序不确定 |

**来源**：添加 `--dist loadfile` 后执行时间从 77s 降到 70s，但更重要的是发现共享状态会导致随机失败。

---

## 15. 防腐化检查清单

每次新增或修改测试时，对照以下清单：

### 写入时（开发者自查）

- [ ] 新测试使用 pytest-native 风格
- [ ] 文件行数 < 500
- [ ] 类方法数 < 30
- [ ] 使用 `tmp_path` 而非 `mkdtemp()`
- [ ] fixture 输入值从 `constants.py` 导入
- [ ] heredoc 内的值保持硬编码
- [ ] helper 函数归属明确

### 提交时（pre-commit hook）

- [ ] 文件行数检查（hook 自动执行）
- [ ] ruff lint 通过
- [ ] commit message 符合 conventional commits

### 合并时（CI 门禁）

- [ ] `uv run python -m agentplane.cli test fast` 通过
- [ ] 覆盖率 >= `fail_under` 阈值
- [ ] 无新增 `unittest.TestCase`（警告）

### 定期（每月）

- [ ] 运行 `python scripts/test_health.py` 健康报告
- [ ] 检查覆盖率趋势
- [ ] 检查文件规模分布
- [ ] 更新 `fail_under` 阈值

---

## 关联文档

- [编码与协作规范](../docs/conventions.md) — 技术栈、编码规则
- [测试健康检查脚本](../scripts/test_health.py) — 自动化健康报告
