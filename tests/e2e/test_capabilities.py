"""E2E tests for Capabilities view."""

import pytest


@pytest.mark.e2e
class TestCapabilities:
    def test_navigate_to_capabilities(self, capabilities_page):
        """Can navigate to capabilities view."""
        capabilities_page.navigate()
        capabilities_page.expect_topbar_title("能力地图")

    def test_capabilities_loads(self, capabilities_page):
        """Capabilities view loads content without error."""
        capabilities_page.navigate()
        capabilities_page.expect_no_error()

    def test_has_categories(self, capabilities_page):
        """Capabilities view shows categories."""
        capabilities_page.navigate()
        assert capabilities_page.has_content(), "No capability categories rendered"
