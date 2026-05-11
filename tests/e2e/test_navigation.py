"""E2E tests for sidebar navigation."""

import pytest


@pytest.mark.e2e
class TestNavigation:
    def test_all_views_reachable(self, page):
        """All 4 sidebar nav items are clickable and render content."""
        views = [
            ("概览", "概览"),
            ("拓扑", "拓扑"),
            ("能力地图", "能力地图"),
            ("对话", "Agent 对话"),
        ]
        for nav_text, expected_title in views:
            page.click(f".nav-item >> text={nav_text}")
            page.wait_for_timeout(500)
            title = page.locator(".topbar-title").inner_text()
            assert title == expected_title, f"Expected topbar '{expected_title}', got '{title}'"

    def test_sidebar_brand_visible(self, page):
        """Sidebar brand shows AgentPlane."""
        brand = page.locator(".sidebar-brand-text")
        assert brand.inner_text() == "AgentPlane"

    def test_sidebar_status_visible(self, page):
        """Sidebar shows connection status."""
        status = page.locator(".sidebar-footer-status")
        assert status.is_visible()
