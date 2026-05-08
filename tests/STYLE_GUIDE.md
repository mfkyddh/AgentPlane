# 测试风格指南

> 本指南定义 AgentPlane 测试的编写规范。所有新测试必须遵循本指南。

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

**注意**：仅用于 fixture INPUT 值（域名、IP、端口、容器名），不用于断言期望值。

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
