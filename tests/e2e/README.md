# E2E Tests — AgentPlane WebUI

## Quick Start

```bash
# Install dependencies (one-time)
uv pip install playwright pytest-playwright
.venv/Scripts/python.exe -m playwright install chromium

# Run all E2E tests
.venv/Scripts/python.exe -m pytest tests/e2e/ -m e2e -v

# Run a specific test file
.venv/Scripts/python.exe -m pytest tests/e2e/test_dashboard.py -m e2e -v

# Run headed (see browser)
.venv/Scripts/python.exe -m pytest tests/e2e/ -m e2e --headed -v
```

## Architecture

```
tests/e2e/
  conftest.py              # Fixtures: e2e_server, ap_page, page objects
  pages/
    base.py                # BasePage — shared navigation, assertions
    dashboard.py           # DashboardPage — KPI, domain cards, topology
    topology.py            # TopologyPage — targets, expand/collapse, detail panel
    capabilities.py        # CapabilitiesPage — layers, items
    chat.py                # ChatPage — send message, welcome
  test_auth.py             # Auth flow (no-auth mode)
  test_dashboard.py        # Dashboard view
  test_topology.py         # Topology view
  test_capabilities.py     # Capabilities view
  test_chat.py             # Chat view
  test_navigation.py       # Sidebar navigation
  test_i18n.py             # Locale switching (zh ↔ en)
```

## Page Object Model

每个视图有一个 Page Object 类，继承 `BasePage`：

```python
class TopologyPage(BasePage):
    def navigate(self) -> None:
        self.navigate_to("topology")

    def target_count(self) -> int:
        return self.page.locator(".topo-target-header").count()
```

**规则**：
- 定位器（CSS selector）只写在 Page Object 中
- 测试文件只调用 Page Object 方法，不直接写选择器
- 修改 UI 结构时只需更新对应的 Page Object

## Fixtures

| Fixture | Scope | Description |
|---------|-------|-------------|
| `repo_root` | session | 项目根目录 |
| `e2e_server` | session | 启动 FastAPI 测试服务器（随机端口） |
| `ap_page` | function | Playwright Page，已导航到首页 |
| `page` | function | `ap_page` 的别名 |
| `dashboard_page` | function | DashboardPage 实例 |
| `topology_page` | function | TopologyPage 实例 |
| `capabilities_page` | function | CapabilitiesPage 实例 |
| `chat_page` | function | ChatPage 实例 |

## Adding a New View

1. 在 `pages/` 下创建新的 Page Object（继承 `BasePage`）
2. 在 `conftest.py` 中添加 fixture
3. 创建 `test_<view>.py`，使用 `@pytest.mark.e2e` 标记
4. 运行测试验证

## Marker

所有 E2E 测试使用 `@pytest.mark.e2e` 标记。默认 pytest 配置排除 e2e 测试（因为它们较慢），需要显式 `-m e2e` 运行。

## CI Integration

```yaml
# GitHub Actions 示例
- name: E2E tests
  run: |
    uv pip install playwright pytest-playwright
    uv run python -m playwright install chromium --with-deps
    uv run python -m pytest tests/e2e/ -m e2e -v
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `browser_context not found` | 使用 `context` fixture 而非 `browser_context` |
| Server port conflict | `e2e_server` 使用随机端口，不会冲突 |
| Tests skipped | 拓扑测试在无 inventory 数据时自动 skip |
| Timeout | 增加 `page.wait_for_timeout()` 或检查网络 |
