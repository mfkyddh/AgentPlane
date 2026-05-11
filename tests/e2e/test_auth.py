"""E2E tests for authentication flow."""

import pytest


@pytest.mark.e2e
class TestAuth:
    def test_no_auth_required(self, page, e2e_server):
        """When no token configured, app loads directly without auth page."""
        # If server has no token, auth page should not appear
        auth_page = page.locator(".auth-page")
        # With token=None, should go straight to main app
        assert not auth_page.is_visible(), "Auth page shown when no token required"

    def test_main_app_visible(self, page):
        """Main app sidebar is visible on load (no auth)."""
        sidebar = page.locator(".sidebar")
        assert sidebar.is_visible()
