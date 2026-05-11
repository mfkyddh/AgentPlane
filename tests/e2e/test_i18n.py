"""E2E tests for i18n locale switching."""

import pytest


@pytest.mark.e2e
class TestI18n:
    def test_default_locale_is_zh(self, page):
        """App starts in Chinese locale."""
        # Nav items should be in Chinese
        overview = page.locator(".nav-item").first
        assert "概览" in overview.inner_text()

    def test_toggle_to_english(self, page):
        """Clicking locale button switches to English."""
        page.click(".sidebar-locale-btn")
        page.wait_for_timeout(500)
        overview = page.locator(".nav-item").first
        assert "Overview" in overview.inner_text()

    def test_toggle_back_to_chinese(self, page):
        """Toggling twice returns to Chinese."""
        page.click(".sidebar-locale-btn")
        page.wait_for_timeout(500)
        page.click(".sidebar-locale-btn")
        page.wait_for_timeout(500)
        overview = page.locator(".nav-item").first
        assert "概览" in overview.inner_text()

    def test_toggle_preserves_current_view(self, page):
        """Switching locale stays on the current view."""
        # Navigate to topology
        page.click(".nav-item >> text=拓扑")
        page.wait_for_timeout(500)
        page.locator(".topbar-title").inner_text() == "拓扑"
        # Toggle locale
        page.click(".sidebar-locale-btn")
        page.wait_for_timeout(500)
        title = page.locator(".topbar-title").inner_text()
        assert title == "Topology", f"Expected 'Topology' after locale toggle, got '{title}'"
